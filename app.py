import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime

# =============================
# Memory + Improvement System (SQLite)
# =============================
import sqlite3
import json
import uuid
from pathlib import Path
import re
import hashlib

DB_PATH = Path("nexture_runs.sqlite")


def _db_connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        app_version TEXT,
        inputs_json TEXT NOT NULL,
        outputs_json TEXT NOT NULL,
        memo_text TEXT,
        diag_text TEXT,
        improve_text TEXT,
        vision_text TEXT,
        user_feedback_label TEXT,
        user_feedback_notes TEXT
    );
    """
    )
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);""")
    conn.commit()
    conn.close()


def save_run(payload: dict) -> str:
    run_id = str(uuid.uuid4())
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO runs (
            run_id, created_at, app_version,
            inputs_json, outputs_json,
            memo_text, diag_text, improve_text, vision_text,
            user_feedback_label, user_feedback_notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            payload.get("app_version", "0.1"),
            json.dumps(payload.get("inputs", {}), ensure_ascii=False),
            json.dumps(payload.get("outputs", {}), ensure_ascii=False),
            payload.get("memo_text", ""),
            payload.get("diag_text", ""),
            payload.get("improve_text", ""),
            payload.get("vision_text", ""),
            None,
            None,
        ),
    )
    conn.commit()
    conn.close()
    return run_id


def update_feedback(run_id: str, label: str | None, notes: str | None):
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE runs
        SET user_feedback_label = ?, user_feedback_notes = ?
        WHERE run_id = ?
        """,
        (label, notes, run_id),
    )
    conn.commit()
    conn.close()


def list_runs(limit: int = 50) -> pd.DataFrame:
    conn = _db_connect()
    df = pd.read_sql_query(
        f"""
        SELECT run_id, created_at, user_feedback_label
        FROM runs
        ORDER BY created_at DESC
        LIMIT {int(limit)}
        """,
        conn,
    )
    conn.close()
    return df


def get_run(run_id: str) -> dict | None:
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_id, created_at, app_version,
               inputs_json, outputs_json,
               memo_text, diag_text, improve_text, vision_text,
               user_feedback_label, user_feedback_notes
        FROM runs
        WHERE run_id = ?
        """,
        (run_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "run_id": row[0],
        "created_at": row[1],
        "app_version": row[2],
        "inputs": json.loads(row[3]) if row[3] else {},
        "outputs": json.loads(row[4]) if row[4] else {},
        "memo_text": row[5] or "",
        "diag_text": row[6] or "",
        "improve_text": row[7] or "",
        "vision_text": row[8] or "",
        "user_feedback_label": row[9],
        "user_feedback_notes": row[10],
    }


def _norm_tokens(s: str) -> set[str]:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    toks = [t for t in s.split() if len(t) >= 3]
    return set(toks)


def _safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default


def find_similar_runs(current_inputs: dict, current_outputs: dict, limit: int = 3) -> list[dict]:
    """
    Lightweight similarity (no embeddings):
    - same channel/category/goal gets boosts
    - similar product description tokens gets boost
    - similar price + margin gets boost
    - prefers runs with positive feedback if available
    """
    conn = _db_connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT run_id, created_at, inputs_json, outputs_json, memo_text, user_feedback_label, user_feedback_notes
        FROM runs
        ORDER BY created_at DESC
        LIMIT 200
        """
    )
    rows = cur.fetchall()
    conn.close()

    curr_desc = current_inputs.get("product_desc", "") or ""
    curr_tokens = _norm_tokens(curr_desc)
    curr_channel = current_inputs.get("sales_channel", "")
    curr_goal = current_inputs.get("business_goal", "")
    curr_category = current_inputs.get("category", "")

    curr_price = _safe_float(current_outputs.get("recommended_price"))
    curr_margin = _safe_float(current_outputs.get("net_margin_pct"))

    scored = []
    for (run_id, created_at, inp_json, out_json, memo_text, fb_label, fb_notes) in rows:
        try:
            inp = json.loads(inp_json) if inp_json else {}
            out = json.loads(out_json) if out_json else {}
        except Exception:
            continue

        score = 0.0

        if inp.get("sales_channel") == curr_channel and curr_channel:
            score += 2.0
        if inp.get("business_goal") == curr_goal and curr_goal:
            score += 1.5
        if inp.get("category") == curr_category and curr_category:
            score += 1.5

        toks = _norm_tokens(inp.get("product_desc", "") or "")
        if curr_tokens and toks:
            jacc = len(curr_tokens & toks) / max(len(curr_tokens | toks), 1)
            score += 3.0 * jacc

        price = _safe_float(out.get("recommended_price"))
        margin = _safe_float(out.get("net_margin_pct"))
        if curr_price > 0 and price > 0:
            rel = abs(curr_price - price) / max(curr_price, 1e-6)
            score += max(0.0, 1.5 - rel * 3.0)
        if abs(curr_margin) > 0 and abs(margin) > 0:
            relm = abs(curr_margin - margin) / max(abs(curr_margin), 1e-6)
            score += max(0.0, 1.5 - relm * 3.0)

        if fb_label == "👍":
            score += 1.0
        elif fb_label == "👎":
            score -= 0.5

        if score > 0:
            scored.append(
                {
                    "run_id": run_id,
                    "created_at": created_at,
                    "score": score,
                    "inputs": inp,
                    "outputs": out,
                    "memo_text": memo_text or "",
                    "feedback": fb_label,
                    "feedback_notes": fb_notes or "",
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def format_similar_snippets(similar: list[dict]) -> str:
    if not similar:
        return "None"
    lines = []
    for s in similar:
        out = s.get("outputs", {})
        inp = s.get("inputs", {})
        lines.append(
            f"- Run {s['run_id']} ({s['created_at']}) "
            f"[channel={inp.get('sales_channel','?')}, category={inp.get('category','?')}, goal={inp.get('business_goal','?')}] "
            f"price=${_safe_float(out.get('recommended_price')):,.2f}, net_margin={_safe_float(out.get('net_margin_pct')):.1f}%, "
            f"health={out.get('health','?')}, verdict={out.get('verdict','?')}, feedback={s.get('feedback') or 'None'}"
        )
    return "\n".join(lines)


# -----------------------------
# Ollama helpers
# -----------------------------
def nexture_local_ai(prompt: str, model: str = "llama3.1:8b") -> str:
    url = "http://localhost:11434/api/generate"
    response = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def _b64_from_upload(uploaded_file) -> str:
    return base64.b64encode(uploaded_file.getvalue()).decode("utf-8")


def nexture_local_vision(prompt: str, uploaded_file, model: str = "llama3.2-vision") -> str:
    url = "http://localhost:11434/api/generate"
    img_b64 = _b64_from_upload(uploaded_file)
    response = requests.post(
        url,
        json={"model": model, "prompt": prompt, "images": [img_b64], "stream": False},
        timeout=240,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


# -----------------------------
# Launch quarter rules (simple + credible MVP)
# -----------------------------
CATEGORY_TO_BEST_QUARTERS = {
    "Gifts & novelty": ["Q4"],
    "Fashion / apparel": ["Q3", "Q4"],
    "Fitness / wellness": ["Q1", "Q2"],
    "Food & beverage": ["Q2", "Q4"],
    "Home / decor": ["Q2", "Q4"],
    "Kids / baby": ["Q1", "Q3"],
    "School / study": ["Q3"],
    "Software / digital product": ["Q1", "Q2", "Q3", "Q4"],
    "Other": ["Q1", "Q2", "Q3", "Q4"],
}


def recommend_launch_quarter(category: str, lead_weeks: int, goal: str) -> tuple[str, str]:
    best = CATEGORY_TO_BEST_QUARTERS.get(category, ["Q1", "Q2", "Q3", "Q4"])

    if lead_weeks >= 12:
        lead_note = f"Lead time (~{lead_weeks} weeks) suggests planning ahead to avoid seasonal crunch."
    elif lead_weeks >= 6:
        lead_note = f"With ~{lead_weeks} weeks lead time, you can target the next seasonal window if you start now."
    else:
        lead_note = f"Short lead time (~{lead_weeks} weeks) means you can test demand quickly."

    if goal == "Maximize profit":
        goal_note = "Favor quarters with higher willingness-to-pay and stronger conversion."
    elif goal == "Break even fast":
        goal_note = "Favor earlier launch so learning + cashflow start sooner."
    elif goal == "Grow market share":
        goal_note = "Favor earlier launch to iterate and capture share."
    else:
        goal_note = "Favor brand-fit timing and a clean launch."

    if goal in ["Break even fast", "Grow market share"]:
        pick = "Q1"
        rationale = f"Speed matters for your goal. {lead_note} {goal_note}"
    else:
        pick = best[0]
        rationale = f"{category} often performs best in {', '.join(best)}. Recommended: {pick}. {lead_note} {goal_note}"

    return pick, rationale


# -----------------------------
# Business benchmarks + heuristics
# -----------------------------
CHANNEL_BENCHMARKS = {
    "Shopify / DTC (Direct-to-Consumer)": {"target_net_margin_pct": 40, "excellent_net_margin_pct": 60},
    "Amazon": {"target_net_margin_pct": 25, "excellent_net_margin_pct": 40},
    "Etsy": {"target_net_margin_pct": 30, "excellent_net_margin_pct": 45},
    "Retail (in-store)": {"target_net_margin_pct": 20, "excellent_net_margin_pct": 35},
    "B2B / Wholesale": {"target_net_margin_pct": 15, "excellent_net_margin_pct": 25},
}


def verdict_from_signals(contribution_margin, break_even_units, effective_demand, profit_down_20):
    if contribution_margin <= 0:
        return "DON’T LAUNCH", "You lose money per unit after fees/shipping/COGS. Fix unit economics first."
    if break_even_units is not None and effective_demand > 0 and break_even_units > (effective_demand * 3):
        return "ADJUST", "Break-even is far above expected demand. Adjust price/costs or validate demand."
    if profit_down_20 < 0:
        return "ADJUST", "This plan is fragile: a 20% demand drop turns profit negative."
    return "GO", "Unit economics are positive and the plan holds under basic sensitivity checks."


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def business_health_score(net_margin_pct, break_even_units, effective_demand, profit_down_20, competitor_low, competitor_high):
    score = 0
    margin_score = clamp((net_margin_pct / 60) * 25, 0, 25)
    score += margin_score

    if effective_demand <= 0 or break_even_units is None:
        be_score = 0
    else:
        ratio = break_even_units / max(effective_demand, 1)
        be_score = 25 * clamp(1 - ((ratio - 1) / 2), 0, 1)
    score += be_score

    sens_score = 20 if profit_down_20 >= 0 else 8
    score += sens_score

    spread = competitor_high - competitor_low
    comp_score = 15 if spread > 0 else 5
    score += comp_score

    input_score = 15
    if competitor_low == 0 or competitor_high == 0:
        input_score -= 7
    score += clamp(input_score, 0, 15)

    return int(round(clamp(score, 0, 100)))


def stable_hash(obj: dict) -> str:
    blob = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


# =============================
# NEW: Founder OS Layer (Readiness + Modes + Must-Be-True)
# =============================
def readiness_breakdown(
    net_margin_pct: float,
    break_even_units,
    effective_demand: int,
    profit_down_20: float,
    sales_channel: str,
    platform_fee_pct: float,
    returns_pct: float,
):
    bench = CHANNEL_BENCHMARKS.get(sales_channel, {"target_net_margin_pct": 30, "excellent_net_margin_pct": 45})
    target_margin = float(bench["target_net_margin_pct"])
    excellent_margin = float(bench["excellent_net_margin_pct"])

    # Margin Strength (0-100)
    if net_margin_pct <= 0:
        margin_score = 0
    elif net_margin_pct < target_margin:
        margin_score = int(clamp((net_margin_pct / target_margin) * 60, 0, 60))
    elif net_margin_pct < excellent_margin:
        margin_score = int(
            60
            + clamp(
                ((net_margin_pct - target_margin) / max(excellent_margin - target_margin, 1e-6)) * 40,
                0,
                40,
            )
        )
    else:
        margin_score = 100

    # Demand Realism (0-100)
    if break_even_units is None or effective_demand <= 0:
        demand_score = 0
    else:
        ratio = float(break_even_units) / max(float(effective_demand), 1.0)
        if ratio <= 1:
            demand_score = 100
        elif ratio <= 2:
            demand_score = int(100 - (ratio - 1) * 40)  # 100 -> 60
        elif ratio <= 3:
            demand_score = int(60 - (ratio - 2) * 30)  # 60 -> 30
        else:
            demand_score = int(clamp(30 - (ratio - 3) * 20, 10, 30))

    # Fragility Risk (higher = better)
    fragility_score = 100 if profit_down_20 >= 0 else 35

    # Channel Fit
    channel_score = 80
    if sales_channel in ["Amazon", "Etsy"] and platform_fee_pct >= 20:
        channel_score -= 25
    if returns_pct >= 10:
        channel_score -= 15
    channel_score = int(clamp(channel_score, 0, 100))

    # Assumption Confidence (starter)
    assumption_score = 65
    if effective_demand <= 0:
        assumption_score -= 25
    if platform_fee_pct <= 0:
        assumption_score -= 10
    assumption_score = int(clamp(assumption_score, 0, 100))

    subs = {
        "Margin Strength": margin_score,
        "Demand Realism": demand_score,
        "Fragility Risk": fragility_score,
        "Channel Fit": channel_score,
        "Assumption Confidence": assumption_score,
    }

    overall = int(
        round(
            subs["Margin Strength"] * 0.30
            + subs["Demand Realism"] * 0.25
            + subs["Fragility Risk"] * 0.20
            + subs["Channel Fit"] * 0.15
            + subs["Assumption Confidence"] * 0.10
        )
    )

    reality_checks = []
    if net_margin_pct < target_margin:
        reality_checks.append(f"⚠️ This plan is below typical {sales_channel} margin targets (~{target_margin}%+).")
    if break_even_units is not None and effective_demand > 0 and float(break_even_units) > float(effective_demand) * 2:
        reality_checks.append("⚠️ This launch relies on optimistic demand assumptions (break-even is >2× expected demand).")
    if profit_down_20 < 0:
        reality_checks.append("⚠️ This plan is fragile: a normal demand dip (-20%) flips profit negative.")
    if platform_fee_pct > 30:
        reality_checks.append("⚠️ Platform fees look extremely high—double-check fees + ad spend assumptions.")
    if returns_pct >= 10:
        reality_checks.append("⚠️ High returns/defects will quietly destroy profit and cashflow if not controlled.")

    return subs, overall, reality_checks


def must_be_true_statements(
    recommended_price: float,
    contribution_margin: float,
    break_even_units,
    platform_fee_pct: float,
    returns_pct: float,
    profit_down_20: float,
    target_margin: float,
    net_margin_pct: float,
):
    lines = []
    lines.append(f"Customers will buy at **${recommended_price:,.2f}** (or you prove it with a test).")
    if break_even_units is not None:
        lines.append(f"You can reach at least **{int(round(break_even_units)):,.0f} units/month** to cover fixed costs.")
    lines.append(f"Contribution stays **> $0** (currently **${contribution_margin:,.2f}/unit** after fees/COGS/shipping).")
    lines.append(f"Fees stay around **{platform_fee_pct:.1f}%** and don’t creep up due to ads/refunds.")
    if returns_pct > 0:
        lines.append(f"Returns/defects stay around **{returns_pct:.1f}%** (or you update your economics).")
    if profit_down_20 < 0:
        lines.append("Demand does *not* drop ~20% without a mitigation plan (because that turns profit negative).")
    if net_margin_pct < target_margin:
        lines.append(f"You improve margin toward **~{target_margin}%+** for your channel (or accept slower growth).")
    return lines


def beginner_summary(verdict: str, recommended_price: float, launch_quarter: str, verdict_reason: str):
    return (
        f"**What I’d do:** {verdict} at **${recommended_price:,.2f}** and aim for **{launch_quarter}**.\n\n"
        f"**Why:** {verdict_reason}\n\n"
        f"**Next:** Run one quick pricing test + one demand test before you spend on inventory/ads."
    )


# -----------------------------
# Page settings + CSS
# -----------------------------
st.set_page_config(page_title="Nexture", page_icon="Nexture_icon.png", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; padding-bottom: 2rem; }
      [data-testid="stMetricValue"] { font-size: 1.6rem; }
      [data-testid="stMetricLabel"] { font-size: 0.9rem; opacity: 0.75; }
      .section-card { padding: 1.2rem; border: 1px solid rgba(255,255,255,0.08);
                      border-radius: 16px; background: rgba(255,255,255,0.03); margin-bottom: 1rem; }
      .small-note { opacity: 0.75; font-size: 0.9rem; }
      section[data-testid="stSidebar"] { width: 400px !important; }
      section[data-testid="stSidebar"] > div { width: 400px !important; }
      .runpill { display:inline-block; padding:0.15rem 0.5rem; border: 1px solid rgba(255,255,255,0.14);
                border-radius: 999px; font-size: 0.85rem; opacity: 0.85; }
      .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
    </style>
    """,
    unsafe_allow_html=True,
)

# init DB once
init_db()

# -----------------------------
# Header
# -----------------------------
col1, col2 = st.columns([2, 8], vertical_alignment="center")
with col1:
    st.image("nexture_logo_transparent.png", width=250)
with col2:
    st.title("AI Pricing & Launch Advisor")
    st.caption("Translate Business Strategies Into Plain English")

st.divider()

# =============================
# Tabs
# =============================
tab_advisor, tab_history = st.tabs(["Advisor", "History"])


# =============================
# Sidebar (always visible)
# =============================
with st.sidebar:
    st.header("Inputs")
    st.caption("Enter what you know. Nexture does the math + strategy.")

    st.subheader("Business context")
    business_goal = st.selectbox(
        "Primary goal",
        ["Maximize profit", "Break even fast", "Grow market share", "Premium positioning"],
        index=0,
    )
    sales_channel = st.selectbox(
        "Sales channel",
        ["Shopify / DTC (Direct-to-Consumer)", "Amazon", "Etsy", "Retail (in-store)", "B2B / Wholesale"],
        index=0,
    )
    differentiation = st.slider(
        "How unique is your product?",
        1, 5, 3,
        help="1 = commodity, 5 = very differentiated/premium.",
    )
    target_customer = st.text_input(
        "Target customer (optional)",
        placeholder="e.g., busy parents, gym beginners, college students...",
    )

    st.divider()
    st.subheader("Launch timing")
    category = st.selectbox(
        "Product category",
        list(CATEGORY_TO_BEST_QUARTERS.keys()),
        index=list(CATEGORY_TO_BEST_QUARTERS.keys()).index("Other"),
    )
    lead_time_weeks = st.number_input("Lead time (weeks)", min_value=0, step=1, value=6)

    st.divider()
    st.subheader("Costs & demand")
    cost_per_unit = st.number_input("Unit cost / COGS ($)", min_value=0.0, step=0.5)
    shipping_per_unit = st.number_input("Shipping/fulfillment per unit ($)", min_value=0.0, step=0.5, value=0.0)
    platform_fee_pct = st.number_input("Platform/payment fee (%)", 0.0, 60.0, 2.9, 0.5)
    returns_pct = st.number_input("Returns/defect allowance (%)", 0.0, 50.0, 0.0, 0.5)
    fixed_costs = st.number_input("Fixed monthly costs ($)", min_value=0.0, step=50.0)
    expected_demand = st.number_input("Expected demand (units/month)", min_value=0, step=10)

    st.divider()
    st.subheader("Competitive pricing")
    competitor_low = st.number_input("Low competitor price ($)", min_value=0.0, step=0.5)
    competitor_high = st.number_input("High competitor price ($)", min_value=0.0, step=0.5)

    st.divider()

    # ✅ NEW: Beginner vs Operator
    st.subheader("Experience")
    experience_mode = st.radio(
        "Mode",
        ["Beginner", "Operator"],
        index=0,
        help="Beginner = plain English + next steps. Operator = full breakdown + hard checks.",
    )

    st.divider()
    st.subheader("AI Mode")
    chain_mode = st.toggle(
        "Operator Chain Mode (3-step AI)",
        value=True,
        help="More reliable but slower.",
    )

    col_model, col_help = st.columns([8, 10], vertical_alignment="center")
    with col_model:
        model_key = st.selectbox("Text model", ["Reasoning", "Instruction"], index=0)

    with col_help:
        with st.expander("❓"):
            st.markdown(
                """
**Reasoning** *(llama3.1:8b)*  
Best for business thinking: tradeoffs, risks, strategy.

**Instruction** *(qwen2.5:7b-instruct)*  
Best for clean formatting: bullet points, structure, following rules.
"""
            )

    model_text = "llama3.1:8b" if model_key == "Reasoning" else "qwen2.5:7b-instruct"

    st.divider()
    analyze = st.button("Run analysis", use_container_width=True)


# =============================
# Advisor tab
# =============================
with tab_advisor:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("Product (Optional)")

    col_img, col_desc = st.columns([3, 7], vertical_alignment="top")
    with col_img:
        uploaded = st.file_uploader(
            "Upload a product image (PNG/JPG)",
            type=["png", "jpg", "jpeg"],
            help="Optional: vision model can infer category, positioning, and competitor search keywords.",
        )
        if uploaded:
            st.image(uploaded, use_container_width=True)

    with col_desc:
        product_desc = st.text_area(
            "Short product description (optional)",
            placeholder="What is it? Who is it for? What problem does it solve? (1–3 sentences)",
            height=120,
        )
        st.caption("Image/description helps positioning. Pricing still depends on costs + demand.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("Recommendation")

    if analyze:
        # Guardrails
        if competitor_high < competitor_low:
            st.error("Competitor high price must be >= competitor low price.")
            st.stop()
        if competitor_high == 0 or competitor_low == 0:
            st.error("Please enter both competitor low and high prices.")
            st.stop()
        if platform_fee_pct > 30:
            st.warning("Platform/payment fee seems high. Double-check.")
        if expected_demand == 0:
            st.warning("Expected demand is 0 units/month. Profit will likely be negative.")

        recommended_price = (competitor_low + competitor_high) / 2
        if recommended_price <= 0:
            st.error("Recommended price must be > 0.")
            st.stop()

        fee_rate = platform_fee_pct / 100.0
        returns_rate = returns_pct / 100.0
        effective_demand = max(int(round(expected_demand * (1.0 - returns_rate))), 0)

        net_revenue_per_unit = recommended_price * (1.0 - fee_rate)
        contribution_margin = net_revenue_per_unit - cost_per_unit - shipping_per_unit
        monthly_profit = contribution_margin * effective_demand - fixed_costs
        net_margin_pct = (contribution_margin / recommended_price) * 100 if recommended_price else 0
        break_even_units = fixed_costs / contribution_margin if contribution_margin > 0 else None

        # Sensitivities
        demand_down = max(int(round(effective_demand * 0.8)), 0)
        demand_up = int(round(effective_demand * 1.2))
        profit_down_20 = contribution_margin * demand_down - fixed_costs
        profit_up_20 = contribution_margin * demand_up - fixed_costs

        cm_cost_up = net_revenue_per_unit - (cost_per_unit * 1.10) - shipping_per_unit
        profit_cost_up_10 = cm_cost_up * effective_demand - fixed_costs

        price_down_10 = recommended_price * 0.90
        net_rev_price_down = price_down_10 * (1.0 - fee_rate)
        cm_price_down = net_rev_price_down - cost_per_unit - shipping_per_unit
        profit_price_down_10 = cm_price_down * effective_demand - fixed_costs

        # Launch
        launch_quarter, launch_rationale = recommend_launch_quarter(category, int(lead_time_weeks), business_goal)

        # Benchmarks
        bench = CHANNEL_BENCHMARKS.get(sales_channel, {"target_net_margin_pct": 30, "excellent_net_margin_pct": 45})
        target_margin = bench["target_net_margin_pct"]
        excellent_margin = bench["excellent_net_margin_pct"]

        # Risk flags
        risk_flags = []
        if contribution_margin <= 0:
            risk_flags.append("Contribution margin is ≤ $0 after fees/COGS/shipping (unit economics broken).")
        if net_margin_pct < target_margin:
            risk_flags.append(f"Net margin ({net_margin_pct:.1f}%) is below typical target for this channel (~{target_margin}%+).")
        if break_even_units is not None and effective_demand > 0 and break_even_units > effective_demand * 2:
            risk_flags.append("Break-even units are >2× your expected demand (plan may be unrealistic).")
        if profit_down_20 < 0:
            risk_flags.append("A 20% demand drop turns profit negative (fragile plan).")
        if platform_fee_pct > 20 and sales_channel in ["Amazon", "Etsy"]:
            risk_flags.append("High platform fees can crush margins—verify fee structure and ad spend assumptions.")
        if returns_pct >= 10:
            risk_flags.append("Returns/defects are high—factor in customer support, replacements, and cashflow risk.")

        verdict, verdict_reason = verdict_from_signals(contribution_margin, break_even_units, effective_demand, profit_down_20)
        health = business_health_score(net_margin_pct, break_even_units, effective_demand, profit_down_20, competitor_low, competitor_high)

        confidence_points = 0
        confidence_points += 2 if expected_demand > 0 else 0
        confidence_points += 2 if competitor_high > competitor_low else 0
        confidence_points += 2 if contribution_margin > 0 else 0
        confidence_points += 1 if (product_desc.strip() if product_desc else "") else 0
        confidence_points += 1 if uploaded else 0
        confidence = "High" if confidence_points >= 7 else ("Medium" if confidence_points >= 4 else "Low")

        assumptions = [
            f"Competitor range entered: ${competitor_low:,.2f}–${competitor_high:,.2f}",
            f"Fees assumed: {platform_fee_pct:.1f}%",
            f"Shipping/fulfillment assumed: ${shipping_per_unit:,.2f}/unit",
            f"Returns allowance assumed: {returns_pct:.1f}%",
            f"Demand assumed: {expected_demand:,} units/month (effective: {effective_demand:,})",
            f"Benchmarks used for {sales_channel}: target net margin ~{target_margin}%+, excellent ~{excellent_margin}%+",
        ]

        # ✅ NEW: Readiness + must-be-true + reality checks
        subs, readiness, reality_checks = readiness_breakdown(
            net_margin_pct=net_margin_pct,
            break_even_units=break_even_units,
            effective_demand=effective_demand,
            profit_down_20=profit_down_20,
            sales_channel=sales_channel,
            platform_fee_pct=platform_fee_pct,
            returns_pct=returns_pct,
        )

        must_be_true = must_be_true_statements(
            recommended_price=recommended_price,
            contribution_margin=contribution_margin,
            break_even_units=break_even_units,
            platform_fee_pct=platform_fee_pct,
            returns_pct=returns_pct,
            profit_down_20=profit_down_20,
            target_margin=target_margin,
            net_margin_pct=net_margin_pct,
        )

        # -----------------------------
        # Similar run memory
        # -----------------------------
        current_inputs_for_memory = {
            "business_goal": business_goal,
            "sales_channel": sales_channel,
            "category": category,
            "lead_time_weeks": int(lead_time_weeks),
            "differentiation": differentiation,
            "target_customer": target_customer,
            "product_desc": product_desc,
            "competitor_low": competitor_low,
            "competitor_high": competitor_high,
        }
        current_outputs_for_memory = {
            "recommended_price": recommended_price,
            "net_margin_pct": net_margin_pct,
            "health": health,
            "verdict": verdict,
        }

        similar = find_similar_runs(current_inputs_for_memory, current_outputs_for_memory, limit=3)
        similar_snips = format_similar_snippets(similar)

        # -----------------------------
        # Vision
        # -----------------------------
        vision_summary = ""
        if uploaded:
            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.subheader("👁️ Product intelligence (Vision model)")

            vision_prompt = f"""
You are Nexture. Analyze the product image and optional description to help pricing and launch strategy.

Return:
1) Likely category + observable features (2-4 bullets)
2) Differentiators / value props (3-5 bullets)
3) Positioning guess: Budget / Mid / Premium (one line + why)
4) 6 competitor search queries (bullets)
5) One missing detail needed to price more accurately (one bullet)

Optional description:
{product_desc.strip() if product_desc and product_desc.strip() else "Not provided"}
"""
            with st.spinner("Analyzing product image with llama3.2-vision..."):
                try:
                    vision_summary = nexture_local_vision(vision_prompt, uploaded, model="llama3.2-vision")
                    st.write(vision_summary)
                except Exception as e:
                    st.error(f"Vision model error: {e}")

            st.caption("Vision informs positioning/keywords—not your math.")
            st.markdown("</div>", unsafe_allow_html=True)

        # -----------------------------
        # Metrics row
        # -----------------------------
        colA, colB, colC, colD, colE = st.columns(5)
        colA.metric("Recommended price", f"${recommended_price:,.2f}")
        colB.metric("Contribution / unit", f"${contribution_margin:,.2f}")
        colC.metric("Net margin %", f"{net_margin_pct:,.1f}%")
        colD.metric("Monthly profit", f"${monthly_profit:,.0f}")
        colE.metric("Business Health", f"{health}/100")

        # ✅ NEW: Launch Readiness dashboard
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Launch Readiness")

        c1, c2 = st.columns([3, 7], vertical_alignment="center")
        with c1:
            st.metric("Launch Readiness", f"{readiness}/100")
            if readiness >= 80:
                st.success("Strong launch foundation.")
            elif readiness >= 60:
                st.warning("Decent foundation, but fix a few things first.")
            else:
                st.error("High risk. Do not scale until the basics are fixed.")

        with c2:
            r1, r2, r3, r4, r5 = st.columns(5)
            r1.metric("Margin", f"{subs['Margin Strength']}/100")
            r2.metric("Demand", f"{subs['Demand Realism']}/100")
            r3.metric("Fragility", f"{subs['Fragility Risk']}/100")
            r4.metric("Channel", f"{subs['Channel Fit']}/100")
            r5.metric("Assumptions", f"{subs['Assumption Confidence']}/100")

        if reality_checks:
            st.markdown("### Founder Reality Check")
            for rc in reality_checks:
                st.write(rc)
            st.caption("This isn’t to scare you — it’s to prevent expensive mistakes.")
        st.markdown("</div>", unsafe_allow_html=True)

        # ✅ Beginner summary if chosen
        if experience_mode == "Beginner":
            st.markdown("<div class='section-card'>", unsafe_allow_html=True)
            st.subheader("Beginner Summary (Plain English)")
            st.write(beginner_summary(verdict, recommended_price, launch_quarter, verdict_reason))
            st.markdown("</div>", unsafe_allow_html=True)

        # Verdict Card
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Operator Verdict")
        st.write(f"**Verdict:** {verdict}")
        st.write(verdict_reason)
        st.write(f"**Confidence:** {confidence}")
        if reality_checks and verdict == "GO":
            st.warning("Even with a GO: the reality checks above are telling you what could break the plan. Validate before spending.")
        st.markdown("</div>", unsafe_allow_html=True)

        # Launch timing
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Suggested launch quarter")
        st.write(f"**Recommendation:** {launch_quarter}")
        st.write(launch_rationale)
        st.caption("MVP note: rules-based seasonality, not live market data.")
        st.markdown("</div>", unsafe_allow_html=True)

        # Risk flags
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Risk flags (hard checks)")
        if risk_flags:
            for r in risk_flags:
                st.write(f"- {r}")
        else:
            st.write("No major red flags detected from the built-in heuristics.")
        st.markdown("</div>", unsafe_allow_html=True)

        # ✅ NEW: What must be true
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("What Must Be True For This Launch To Work")
        for line in must_be_true:
            st.write(f"- {line}")
        st.caption("These are the *bets* you’re making. Validate them before spending real money.")
        st.markdown("</div>", unsafe_allow_html=True)

        # Unit economics explanation
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("What This Means (Unit Economics)")
        if contribution_margin <= 0:
            st.warning("You are not profitable per unit after fees/COGS/shipping. Fix unit economics before scaling.")
        else:
            be_text = "N/A" if break_even_units is None else f"{break_even_units:,.0f}"
            st.write(
                f"At **${recommended_price:,.2f}**, after **{platform_fee_pct:.1f}% fees**, "
                f"**${cost_per_unit:,.2f} COGS**, and **${shipping_per_unit:,.2f} shipping**, "
                f"you keep **${contribution_margin:,.2f} per unit** (≈ **{net_margin_pct:.1f}%** of price)."
            )
            st.write(
                f"To cover **${fixed_costs:,.0f}/month** fixed costs, you need ~**{be_text} units/month**. "
                f"At effective demand (**{effective_demand:,}/month**), projected monthly profit is **${monthly_profit:,.0f}**."
            )
        st.caption(
            f"Sensitivity: Demand -20% → **${profit_down_20:,.0f}** | Demand +20% → **${profit_up_20:,.0f}** | "
            f"COGS +10% → **${profit_cost_up_10:,.0f}** | Price -10% → **${profit_price_down_10:,.0f}**"
        )
        st.markdown("</div>", unsafe_allow_html=True)

        # Scenario table
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Scenario comparison (low / recommended / high)")
        scenarios = [
            ("Low (match low end)", competitor_low),
            ("Recommended (midpoint)", recommended_price),
            ("High (match high end)", competitor_high),
        ]
        rows = []
        for label, price in scenarios:
            net_rev = price * (1.0 - fee_rate)
            cm = net_rev - cost_per_unit - shipping_per_unit
            profit = cm * effective_demand - fixed_costs
            be_units = fixed_costs / cm if cm > 0 else None
            margin_pct = (cm / price) * 100 if price else 0
            rows.append(
                {
                    "Scenario": label,
                    "Price": price,
                    "Contribution/unit": cm,
                    "Net margin %": margin_pct,
                    "Monthly profit": profit,
                    "Break-even units": None if be_units is None else round(be_units),
                }
            )

        df = pd.DataFrame(rows)
        df_display = df.copy()
        df_display["Price"] = df_display["Price"].map(lambda x: f"${x:,.2f}")
        df_display["Contribution/unit"] = df_display["Contribution/unit"].map(lambda x: f"${x:,.2f}")
        df_display["Net margin %"] = df_display["Net margin %"].map(lambda x: f"{x:,.1f}%")
        df_display["Monthly profit"] = df_display["Monthly profit"].map(lambda x: f"${x:,.0f}")
        df_display["Break-even units"] = df_display["Break-even units"].map(lambda x: "N/A" if x is None else f"{x:,}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Memory box
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Memory (Similar Past Runs)")
        if similar:
            st.caption("These are older runs in your local database that look similar. The AI references them to avoid repeating mistakes.")
            st.code(similar_snips)
        else:
            st.caption("No similar past runs yet. After a few uses, this will start helping.")
        st.markdown("</div>", unsafe_allow_html=True)

        # =============================
        # AI Operator Memo (uses memory + readiness + must-be-true)
        # =============================
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Nexture AI Operator Memo (Local)")

        diag, improve, memo = "", "", ""

        must_be_true_block = "\n".join([f"- {x}" for x in must_be_true])
        readiness_block = f"Overall {readiness}/100 | Subscores: {subs}"
        reality_block = "\n".join(reality_checks) if reality_checks else "None"

        def run_operator_chain():
            diagnose_prompt = f"""
You are a CFO + growth operator for non-finance founders.
Only do diagnosis. No solutions yet.

IMPORTANT:
- Use numbers exactly as provided (no recalculation).
- Treat this like an operator review: be direct, concrete, not generic.
- Consider "Similar past runs" as experience: what usually fails, what to validate.

Similar past runs:
{similar_snips}

Launch Readiness:
{readiness_block}

Founder Reality Check:
{reality_block}

What must be true:
{must_be_true_block}

Given:
- Verdict: {verdict}
- Risk flags: {risk_flags if risk_flags else "None"}
- Business Health: {health}/100
- Confidence: {confidence}

Numbers:
Price ${recommended_price:,.2f}, contribution/unit ${contribution_margin:,.2f}, net margin {net_margin_pct:.1f}%,
fixed ${fixed_costs:,.0f}/mo, effective demand {effective_demand}, break-even {"N/A" if break_even_units is None else f"{break_even_units:,.0f}"},
profit ${monthly_profit:,.0f}, profit@-20% ${profit_down_20:,.0f}

Return:
1) Top 3 reasons this fails (bullets, specific)
2) The #1 assumption to validate (one sentence)
"""

            improve_prompt = f"""
You are a CFO + growth operator.
Propose improvements ONLY (no final memo).

Rules:
- Avoid generic advice.
- Use the numbers exactly as given (no recalculation).
- Focus on levers that move readiness + remove reality check items.

Launch Readiness:
{readiness_block}

Reality Check:
{reality_block}

What must be true:
{must_be_true_block}

Context:
Goal {business_goal}, Channel {sales_channel}, Category {category}, Lead {int(lead_time_weeks)}w.
Diagnosis:
{{DIAGNOSIS}}

Return:
1) 3 concrete levers to improve profitability (bullets)
2) 2 concrete levers to increase demand (bullets)
3) 1 pricing experiment (A/B) with a clear success metric
"""

            # Tone changes based on experience_mode
            tone_line = (
                "Write in super simple plain English (Beginner mode). Short sentences. No jargon."
                if experience_mode == "Beginner"
                else "Write like an operator memo (Operator mode). Clear sections. Direct language."
            )

            final_prompt = f"""
You are Nexture. Write the final operator memo.

Rules:
- Use numbers exactly as given (no recalculation).
- Make a decision: GO / ADJUST / DON’T LAUNCH.
- Include a counterargument (what could prove you wrong).
- Include a validation plan (this week).
- Use "Similar past runs" as experience.
- {tone_line}

Similar past runs:
{similar_snips}

Launch Readiness:
{readiness_block}

Founder Reality Check:
{reality_block}

What must be true:
{must_be_true_block}

CONTEXT:
Goal: {business_goal}
Channel: {sales_channel}
Category: {category}
Lead time: {int(lead_time_weeks)} weeks
Differentiation: {differentiation}/5
Target customer: {target_customer if target_customer.strip() else "Not provided"}
Vision insights: {vision_summary if vision_summary else "None"}

NUMBERS:
- Verdict: {verdict} ({verdict_reason})
- Price: ${recommended_price:,.2f}
- Competitor range: ${competitor_low:,.2f}–${competitor_high:,.2f}
- Fees: {platform_fee_pct:.1f}%
- COGS: ${cost_per_unit:,.2f}
- Shipping: ${shipping_per_unit:,.2f}
- Returns: {returns_pct:.1f}%
- Contribution/unit: ${contribution_margin:,.2f}
- Net margin: {net_margin_pct:.1f}%
- Fixed costs: ${fixed_costs:,.0f}/mo
- Effective demand: {effective_demand}/mo
- Break-even units: {"N/A" if break_even_units is None else f"{break_even_units:,.0f}"}
- Monthly profit: ${monthly_profit:,.0f}
- Profit if demand -20%: ${profit_down_20:,.0f}
- Business Health: {health}/100
- Launch Readiness: {readiness}/100
- Risk flags: {risk_flags if risk_flags else "None"}

OUTPUT FORMAT:
A) Verdict (one line)
B) Decision: price + quarter (one sentence)
C) Why (plain English): 4–6 sentences
D) What must be true: 3–5 bullets
E) Risks & mitigations: 3 bullets
F) Counterargument: 2 bullets
G) Validation plan this week: 3 bullets (pricing, demand, cost)
H) Confidence: {confidence} (one sentence why)
"""
            _diag = nexture_local_ai(diagnose_prompt, model=model_text)
            _improve = nexture_local_ai(improve_prompt.replace("{DIAGNOSIS}", _diag), model=model_text)
            _final = nexture_local_ai(final_prompt, model=model_text)
            return _diag, _improve, _final

        try:
            if chain_mode:
                with st.spinner("Running Operator Chain (diagnose → improve → memo)..."):
                    diag, improve, memo = run_operator_chain()
                with st.expander("Step 1: Diagnosis (AI)"):
                    st.write(diag)
                with st.expander("Step 2: Improvements (AI)"):
                    st.write(improve)
                st.subheader("Final Memo")
                st.write(memo)
            else:
                tone_line = (
                    "Write in super simple plain English (Beginner mode). Short sentences. No jargon."
                    if experience_mode == "Beginner"
                    else "Write like an operator memo (Operator mode). Clear sections. Direct language."
                )

                single_prompt = f"""
You are Nexture: CFO + growth operator for non-finance founders.

Rules:
- Use numbers exactly as given (no recalculation).
- Use similar past runs briefly.
- {tone_line}

Similar past runs:
{similar_snips}

Launch Readiness:
{readiness_block}

Reality Check:
{reality_block}

What must be true:
{must_be_true_block}

Verdict: {verdict} ({verdict_reason})
Business Health: {health}/100
Risk flags: {risk_flags if risk_flags else "None"}

Numbers:
Price ${recommended_price:,.2f}, contribution/unit ${contribution_margin:,.2f}, net margin {net_margin_pct:.1f}%,
fixed ${fixed_costs:,.0f}/mo, effective demand {effective_demand}, break-even {"N/A" if break_even_units is None else f"{break_even_units:,.0f}"},
profit ${monthly_profit:,.0f}, profit@-20% ${profit_down_20:,.0f}

Write:
A) Verdict + price + quarter
B) Why (plain English)
C) What must be true (3-5 bullets)
D) Risks & mitigations (3 bullets)
E) Counterargument (2 bullets)
F) Validation plan this week (3 bullets: pricing, demand, cost)
G) Confidence: {confidence} (one sentence)
"""
                with st.spinner("Writing operator memo..."):
                    memo = nexture_local_ai(single_prompt, model=model_text)
                st.write(memo)
        except Exception as e:
            st.error(f"Local AI error: {e}")

        st.markdown("</div>", unsafe_allow_html=True)

        # =============================
        # SAVE RUN (SESSION-SAFE)
        # =============================
        payload = {
            "app_version": "0.3-founder-os",
            "inputs": {
                "business_goal": business_goal,
                "sales_channel": sales_channel,
                "differentiation": differentiation,
                "target_customer": target_customer,
                "category": category,
                "lead_time_weeks": int(lead_time_weeks),
                "cost_per_unit": cost_per_unit,
                "shipping_per_unit": shipping_per_unit,
                "platform_fee_pct": platform_fee_pct,
                "returns_pct": returns_pct,
                "fixed_costs": fixed_costs,
                "expected_demand": expected_demand,
                "competitor_low": competitor_low,
                "competitor_high": competitor_high,
                "product_desc": product_desc,
                "image_uploaded": bool(uploaded),
                "model_text": model_text,
                "chain_mode": chain_mode,
                "experience_mode": experience_mode,
            },
            "outputs": {
                "recommended_price": recommended_price,
                "contribution_margin": contribution_margin,
                "net_margin_pct": net_margin_pct,
                "monthly_profit": monthly_profit,
                "break_even_units": None if break_even_units is None else float(break_even_units),
                "profit_down_20": profit_down_20,
                "profit_up_20": profit_up_20,
                "profit_cost_up_10": profit_cost_up_10,
                "profit_price_down_10": profit_price_down_10,
                "launch_quarter": launch_quarter,
                "launch_rationale": launch_rationale,
                "verdict": verdict,
                "verdict_reason": verdict_reason,
                "health": health,
                "confidence": confidence,
                "risk_flags": risk_flags,
                "readiness": readiness,
                "readiness_subscores": subs,
                "reality_checks": reality_checks,
                "must_be_true": must_be_true,
            },
            "memo_text": memo,
            "diag_text": diag,
            "improve_text": improve,
            "vision_text": vision_summary,
        }

        run_key = stable_hash({"inputs": payload["inputs"], "outputs": payload["outputs"]})

        if st.session_state.get("last_run_key") != run_key:
            run_id = save_run(payload)
            st.session_state["last_run_key"] = run_key
            st.session_state["last_run_id"] = run_id
        else:
            run_id = st.session_state.get("last_run_id")

        st.markdown(
            f"<div class='section-card'><span class='runpill'>Saved run: {run_id}</span>"
            f"<div class='small-note' style='margin-top:0.6rem;'>Stored locally in <b>nexture_runs.sqlite</b> and used as “experience” for future memos.</div></div>",
            unsafe_allow_html=True,
        )

        # Feedback
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("Feedback (helps the system improve)")

        colf1, colf2, colf3 = st.columns([2, 2, 6], vertical_alignment="center")
        with colf1:
            if st.button("👍 Helpful", use_container_width=True):
                update_feedback(run_id, "👍", get_run(run_id).get("user_feedback_notes") if get_run(run_id) else None)
                st.success("Saved 👍 feedback.")
        with colf2:
            if st.button("👎 Not helpful", use_container_width=True):
                update_feedback(run_id, "👎", get_run(run_id).get("user_feedback_notes") if get_run(run_id) else None)
                st.warning("Saved 👎 feedback.")
        with colf3:
            notes = st.text_input(
                "Optional: what was missing / wrong?",
                placeholder="e.g., ignored ad spend, wrong channel assumptions, too optimistic demand...",
                key="feedback_notes_input",
            )
            if st.button("Save note", use_container_width=True):
                if notes.strip():
                    existing = get_run(run_id)
                    existing_label = existing.get("user_feedback_label") if existing else None
                    update_feedback(run_id, existing_label, notes.strip())
                    st.success("Saved feedback note.")

        st.caption("Over time: 👍 runs become examples the AI can imitate, 👎 runs become patterns it avoids.")
        st.markdown("</div>", unsafe_allow_html=True)

        # Export
        st.markdown("<div class='section-card'>", unsafe_allow_html=True)
        st.subheader("⬇️ Export")

        report_lines = [
            "# Nexture Strategy Report",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Run ID: {run_id}",
            "",
            "## Operator verdict",
            f"- Verdict: {verdict}",
            f"- Reason: {verdict_reason}",
            f"- Business health: {health}/100",
            f"- Launch readiness: {readiness}/100",
            f"- Confidence: {confidence}",
            "",
            "## Founder reality check",
            *(["- None"] if not reality_checks else [f"- {x}" for x in reality_checks]),
            "",
            "## What must be true",
            *[f"- {x}" for x in must_be_true],
            "",
            "## Risk flags",
            *(["- None"] if not risk_flags else [f"- {r}" for r in risk_flags]),
            "",
            "## Inputs",
            f"- Goal: {business_goal}",
            f"- Channel: {sales_channel}",
            f"- Category: {category}",
            f"- Lead time: {int(lead_time_weeks)} weeks",
            f"- Differentiation: {differentiation}/5",
            f"- Mode: {experience_mode}",
            f"- Target customer: {target_customer if target_customer.strip() else 'Not provided'}",
            f"- Product description: {product_desc.strip() if product_desc and product_desc.strip() else 'Not provided'}",
            "",
            "## Pricing & unit economics",
            f"- Recommended price: ${recommended_price:,.2f}",
            f"- Competitor range: ${competitor_low:,.2f}–${competitor_high:,.2f}",
            f"- Fees: {platform_fee_pct:.1f}%",
            f"- Shipping: ${shipping_per_unit:,.2f}/unit",
            f"- Returns allowance: {returns_pct:.1f}%",
            f"- COGS: ${cost_per_unit:,.2f}",
            f"- Contribution margin/unit: ${contribution_margin:,.2f}",
            f"- Net margin on price: {net_margin_pct:.1f}%",
            f"- Fixed costs: ${fixed_costs:,.0f}/month",
            f"- Demand: {expected_demand:,} units/month (effective: {effective_demand:,})",
            f"- Break-even units: {'N/A' if break_even_units is None else f'{break_even_units:,.0f}'}",
            f"- Monthly profit: ${monthly_profit:,.0f}",
            "",
            "## Sensitivity",
            f"- Demand -20%: ${profit_down_20:,.0f}",
            f"- Demand +20%: ${profit_up_20:,.0f}",
            f"- COGS +10%: ${profit_cost_up_10:,.0f}",
            f"- Price -10%: ${profit_price_down_10:,.0f}",
            "",
            "## Launch timing",
            f"- Recommended quarter: {launch_quarter}",
            f"- Rationale: {launch_rationale}",
            "",
            "## Assumptions",
            *[f"- {a}" for a in assumptions],
            "",
            "## Similar past runs used (memory)",
            similar_snips,
            "",
            "## Vision insights (if any)",
            vision_summary if vision_summary else "No image provided.",
            "",
            "## Final memo",
            memo or "",
        ]

        report_md = "\n".join(report_lines)
        st.download_button(
            "Download report (.md)",
            data=report_md.encode("utf-8"),
            file_name="nexture_strategy_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
        st.caption("Tip: paste into Google Docs/Notion for a polished deck-ready report.")
        st.markdown("</div>", unsafe_allow_html=True)

    else:
        st.info("Enter inputs in the sidebar, then click Run analysis.")


# =============================
# History tab
# =============================
with tab_history:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("Run History (Local Memory)")

    df_runs = list_runs(limit=50)
    if df_runs.empty:
        st.caption("No saved runs yet. Use the Advisor tab and run an analysis.")
    else:
        st.dataframe(df_runs, use_container_width=True, hide_index=True)

        run_id_pick = st.text_input("Open a run by Run ID", placeholder="Paste a run_id from the table above")
        if run_id_pick.strip():
            r = get_run(run_id_pick.strip())
            if not r:
                st.error("Run ID not found.")
            else:
                st.markdown(
                    f"**Run:** `{r['run_id']}`  •  **Created:** {r['created_at']}  •  **Feedback:** {r['user_feedback_label'] or 'None'}"
                )
                with st.expander("Inputs"):
                    st.json(r["inputs"])
                with st.expander("Outputs"):
                    st.json(r["outputs"])
                with st.expander("Vision"):
                    st.write(r["vision_text"] or "None")
                with st.expander("Diagnosis"):
                    st.write(r["diag_text"] or "None")
                with st.expander("Improvements"):
                    st.write(r["improve_text"] or "None")

                st.subheader("Memo")
                st.write(r["memo_text"] or "")

                st.subheader("Feedback notes")
                st.write(r["user_feedback_notes"] or "None")

                colh1, colh2 = st.columns([2, 8], vertical_alignment="center")
                with colh1:
                    if st.button("Mark 👍", use_container_width=True):
                        update_feedback(r["run_id"], "👍", r["user_feedback_notes"])
                        st.success("Updated feedback to 👍")
                with colh2:
                    new_note = st.text_input("Update feedback note", value=r["user_feedback_notes"] or "")
                    if st.button("Save updated note", use_container_width=True):
                        update_feedback(r["run_id"], r["user_feedback_label"], new_note.strip() if new_note else None)
                        st.success("Saved note.")

    st.caption("Everything is stored locally in nexture_runs.sqlite (same folder as your app).")
    st.markdown("</div>", unsafe_allow_html=True)











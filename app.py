import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime

# -----------------------------
# Ollama helpers
# -----------------------------
def nexture_local_ai(prompt: str, model: str = "llama3.1:8b") -> str:
    url = "http://localhost:11434/api/generate"
    response = requests.post(
        url,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=180
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
        timeout=240
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
                      border-radius: 16px; background: rgba(255,255,255,0.03); }
      .small-note { opacity: 0.75; font-size: 0.9rem; }

      /* Optional: slightly wider sidebar so labels don't wrap awkwardly */
      section[data-testid="stSidebar"] { width: 400px !important; }
      section[data-testid="stSidebar"] > div { width: 400px !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

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

# -----------------------------
# Product image + description
# -----------------------------
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

# -----------------------------
# Sidebar Inputs
# -----------------------------
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
        help="1 = commodity, 5 = very differentiated/premium."
    )
    target_customer = st.text_input(
        "Target customer (optional)",
        placeholder="e.g., busy parents, gym beginners, college students..."
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

    # =============================
    # AI MODE (UPDATED: no vertical letter wrapping)
    # =============================
    st.subheader("AI Mode")

    chain_mode = st.toggle(
        "Operator Chain Mode (3-step AI)",
        value=True,
        help="More reliable but slower."
    )

    # short labels + ❓ expander = clean sidebar layout
    col_model, col_help = st.columns([10, 8], vertical_alignment="center")

    with col_model:
        model_key = st.selectbox(
            "Text model",
            ["Reasoning", "Instruction"],
            index=0
        )

    with col_help:
        with st.expander("❓"):
            st.markdown("""
**Reasoning** *(llama3.1:8b)*  
Best for business thinking: tradeoffs, risks, strategy.

**Instruction** *(qwen2.5:7b-instruct)*  
Best for clean formatting: bullet points, structure, following rules.
""")

    model_text = "llama3.1:8b" if model_key == "Reasoning" else "qwen2.5:7b-instruct"

    st.divider()
    analyze = st.button("Run analysis", use_container_width=True)

# -----------------------------
# Main
# -----------------------------
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

    # Risk flags (hard heuristics)
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

    # Verdict
    verdict, verdict_reason = verdict_from_signals(contribution_margin, break_even_units, effective_demand, profit_down_20)

    # Health score
    health = business_health_score(net_margin_pct, break_even_units, effective_demand, profit_down_20, competitor_low, competitor_high)

    # Confidence
    confidence_points = 0
    confidence_points += 2 if expected_demand > 0 else 0
    confidence_points += 2 if competitor_high > competitor_low else 0
    confidence_points += 2 if contribution_margin > 0 else 0
    confidence_points += 1 if product_desc.strip() else 0
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

    # Metrics row
    colA, colB, colC, colD, colE = st.columns(5)
    colA.metric("Recommended price", f"${recommended_price:,.2f}")
    colB.metric("Contribution / unit", f"${contribution_margin:,.2f}")
    colC.metric("Net margin %", f"{net_margin_pct:,.1f}%")
    colD.metric("Monthly profit", f"${monthly_profit:,.0f}")
    colE.metric("Business Health", f"{health}/100")

    # Verdict Card
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("Operator Verdict")
    st.write(f"**Verdict:** {verdict}")
    st.write(verdict_reason)
    st.write(f"**Confidence:** {confidence}")
    st.markdown("</div>", unsafe_allow_html=True)

    # Launch timing box
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

    # What this means
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("What This Means (Unit Economics)")

    if contribution_margin <= 0:
        st.warning("You are not profitable per unit after fees/COGS/shipping. Fix unit economics before scaling.")
    else:
        be_text = "N/A" if break_even_units is None else f"{break_even_units:,.0f}"
        st.write(
            f"At **${recommended_price:,.2f}**, after **{platform_fee_pct:.1f}% fees**, "
            f"**${cost_per_unit:,.2f} COGS**, and **${shipping_per_unit:,.2f} shipping**, "
            f"you keep **${contribution_margin:,.2f} per unit** (≈ **{net_margin_pct:,.1f}%** of price)."
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
        rows.append({
            "Scenario": label,
            "Price": price,
            "Contribution/unit": cm,
            "Net margin %": margin_pct,
            "Monthly profit": profit,
            "Break-even units": None if be_units is None else round(be_units),
        })

    df = pd.DataFrame(rows)
    df_display = df.copy()
    df_display["Price"] = df_display["Price"].map(lambda x: f"${x:,.2f}")
    df_display["Contribution/unit"] = df_display["Contribution/unit"].map(lambda x: f"${x:,.2f}")
    df_display["Net margin %"] = df_display["Net margin %"].map(lambda x: f"{x:,.1f}%")
    df_display["Monthly profit"] = df_display["Monthly profit"].map(lambda x: f"${x:,.0f}")
    df_display["Break-even units"] = df_display["Break-even units"].map(lambda x: "N/A" if x is None else f"{x:,}")
    st.dataframe(df_display, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Vision analysis (optional)
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

    # AI Strategy Memo (business-intelligent)
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("Nexture AI Operator Memo (Local)")

    def run_operator_chain():
        diagnose_prompt = f"""
You are a CFO + growth operator.
Only do diagnosis. No solutions yet.

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
1) The top 3 reasons this could fail (bullets)
2) The #1 assumption that must be validated (one sentence)
"""
        improve_prompt = f"""
You are a CFO + growth operator.
Propose improvements ONLY (no final memo).

Context:
Goal {business_goal}, Channel {sales_channel}, Category {category}, Lead {int(lead_time_weeks)}w.

Diagnosis:
{{DIAGNOSIS}}

Return:
1) 3 concrete levers to improve profitability (bullets)
2) 2 levers to increase demand (bullets)
3) 1 pricing experiment (A/B) with a clear success metric
"""
        final_prompt = f"""
You are Nexture. Write the final operator memo.
You MUST:
- Use numbers exactly as given (no recalculation).
- Make a decision: GO / ADJUST / DON’T LAUNCH.
- Include a counterargument (what could prove you wrong).
- Give a validation plan (this week).

CONTEXT:
Goal: {business_goal}
Channel: {sales_channel}
Category: {category}
Lead time: {int(lead_time_weeks)} weeks
Differentiation: {differentiation}/5
Target customer: {target_customer if target_customer.strip() else "Not provided"}
Vision insights: {vision_summary if vision_summary else "None"}

NUMBERS (computed):
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
- Risk flags: {risk_flags if risk_flags else "None"}
- Benchmarks for {sales_channel}: target net margin ~{target_margin}%+, excellent ~{excellent_margin}%+

OUTPUT FORMAT:
A) Verdict: GO / ADJUST / DON’T LAUNCH (one line)
B) Decision: price + quarter (one sentence)
C) Why (plain English): 4–6 sentences
D) Risks & mitigations: 3 bullets
E) Counterargument: 2 bullets (what could make this advice wrong)
F) Validation plan this week: 3 bullets (one pricing test, one demand test, one cost test)
G) Confidence: {confidence} (one sentence why)
"""
        diag = nexture_local_ai(diagnose_prompt, model=model_text)
        improve = nexture_local_ai(improve_prompt.replace("{DIAGNOSIS}", diag), model=model_text)
        final = nexture_local_ai(final_prompt, model=model_text)
        return diag, improve, final

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
            single_prompt = f"""
You are Nexture: CFO + growth operator for non-finance founders.
Use numbers exactly as given. No recalculation.

Verdict: {verdict} ({verdict_reason})
Business Health: {health}/100
Risk flags: {risk_flags if risk_flags else "None"}
Benchmarks for {sales_channel}: target net margin ~{target_margin}%+, excellent ~{excellent_margin}%+

Numbers:
Price ${recommended_price:,.2f}, contribution/unit ${contribution_margin:,.2f}, net margin {net_margin_pct:.1f}%,
fixed ${fixed_costs:,.0f}/mo, effective demand {effective_demand}, break-even {"N/A" if break_even_units is None else f"{break_even_units:,.0f}"},
profit ${monthly_profit:,.0f}, profit@-20% ${profit_down_20:,.0f}

Write:
A) Verdict + price + quarter
B) Why (plain English)
C) Tradeoffs (3 bullets)
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

    # Export
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("⬇️ Export")

    report_lines = [
        "# Nexture Strategy Report",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Operator verdict",
        f"- Verdict: {verdict}",
        f"- Reason: {verdict_reason}",
        f"- Business health: {health}/100",
        f"- Confidence: {confidence}",
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
        "## Vision insights (if any)",
        vision_summary if vision_summary else "No image provided.",
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








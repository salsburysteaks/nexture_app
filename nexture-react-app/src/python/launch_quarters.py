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
        lead_note = f"Lead time (~{lead_weeks} weeks) suggests planning ahead."
    elif lead_weeks >= 6:
        lead_note = f"With ~{lead_weeks} weeks lead time, you can target the next seasonal window."
    else:
        lead_note = f"Short lead time (~{lead_weeks} weeks) allows quick tests."

    goal_notes = {
        "Maximize profit": "Favor quarters with higher willingness-to-pay.",
        "Break even fast": "Favor earlier launch for cashflow.",
        "Grow market share": "Favor earlier launch to iterate and capture share."
    }
    goal_note = goal_notes.get(goal, "Favor brand-fit timing and clean launch.")

    if goal in ["Break even fast", "Grow market share"]:
        pick = "Q1"
        rationale = f"Speed matters for your goal. {lead_note} {goal_note}"
    else:
        pick = best[0]
        rationale = f"{category} often performs best in {', '.join(best)}. Recommended: {pick}. {lead_note} {goal_note}"

    return pick, rationale
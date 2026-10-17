"""Local, no-LLM workflow for research, matching, and pitch drafts."""

from investors import load_investors, rank_investors
from market_research import build_market_report
from pitch_generation import generate_pitches


def prepare_startup_workflow(profile: dict, investor_records: list[dict] | None = None) -> dict:
    matches = rank_investors(profile, investor_records if investor_records is not None else load_investors(), limit=3)
    return {
        "profile": profile,
        "report": build_market_report(profile),
        "matches": matches,
        "drafts": generate_pitches(profile, matches),
        "external_actions": [],
    }

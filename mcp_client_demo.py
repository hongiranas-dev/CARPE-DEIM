"""MCP client demo: reuses existing investor ranking and pitch generation."""

import argparse
import asyncio
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from investors import load_investors, rank_investors
from pitch_generation import generate_pitch

ROOT = Path(__file__).resolve().parent


async def run_demo(approved: bool) -> list[dict]:
    if not approved:
        raise ValueError("Founder approval was not provided. Re-run with --approve after reviewing the local demo actions.")

    startup = {
        "startup_name": "Demo Agri Startup",
        "founder_name": "Demo Founder",
        "description": "A crop advisory service for small Indian farmers.",
        "sector": "Agriculture",
        "stage": "Seed",
        "geography": "India",
        "funding_amount": None,
        "funding_currency": "USD million",
    }
    match = rank_investors(startup, load_investors(), limit=1)[0]
    pitch = generate_pitch(startup, match)
    investor_record = {key: match.get(key, "") for key in (
        "name", "firm", "sectors", "cheque_min", "cheque_max", "currency", "cheque_size_range",
        "stage_min", "stage_max", "startup_stage", "past_investments", "geography", "website",
        "evidence_url", "investment_evidence_url", "eligibility_notes", "record_label",
    )}
    params = StdioServerParameters(command=sys.executable, args=[str(ROOT / "mcp_server.py")])
    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            calls = [
                ("create_gmail_draft", {"to": "founder@example.com", "subject": pitch["subject"], "body": pitch["body"], "approved": True}),
                ("append_to_sheet", {"record": investor_record, "approved": True}),
                ("create_calendar_followup", {"title": f"Follow up with {match['firm']}", "due_at": "2026-10-20T10:00:00+05:30", "notes": "Review the investor pitch draft.", "approved": True}),
            ]
            outcomes = []
            for tool_name, arguments in calls:
                result = await session.call_tool(tool_name, arguments)
                structured = result.structuredContent
                if structured is None:
                    structured = {"success": not result.isError, "content": [block.text for block in result.content if hasattr(block, "text")]}
                outcomes.append({"tool": tool_name, **structured})
            return outcomes


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local FounderOS MCP demo (no external services).")
    parser.add_argument("--approve", action="store_true", help="Approve writing the three local demo artifacts.")
    args = parser.parse_args()
    outcomes = asyncio.run(run_demo(args.approve))
    print(json.dumps(outcomes, indent=2, ensure_ascii=False))
    if not all(result.get("success") for result in outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

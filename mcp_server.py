"""FastMCP server exposing FounderOS local/demo execution tools."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_adapters import append_to_sheet as save_investor_row
from mcp_adapters import create_calendar_followup as save_followup
from mcp_adapters import create_gmail_draft as save_email_draft

mcp = FastMCP(
    "FounderOS Local Actions",
    instructions="All tools write local demo files only; they are not Gmail, Google Sheets, or Calendar integrations. Each action requires founder approval.",
)


@mcp.tool()
def create_gmail_draft(to: str, subject: str, body: str, approved: bool = False) -> dict[str, Any]:
    """Save an approved email draft to local storage. Does not connect to Gmail or send."""
    return save_email_draft(to, subject, body, approved)


@mcp.tool()
def append_to_sheet(record: dict[str, Any], approved: bool = False) -> dict[str, Any]:
    """Append an approved investor profile to a local CSV. Does not connect to Google Sheets."""
    return save_investor_row(record, approved)


@mcp.tool()
def create_calendar_followup(title: str, due_at: str, notes: str = "", approved: bool = False) -> dict[str, Any]:
    """Save an approved follow-up reminder locally. Does not connect to Google Calendar."""
    return save_followup(title, due_at, notes, approved)


if __name__ == "__main__":
    mcp.run(transport="stdio")

"""Approved, local-only demo adapters for FounderOS MCP tools."""

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEMO_DIR = ROOT / "data" / "demo_actions"
INVESTOR_COLUMNS = [
    "name", "firm", "sectors", "cheque_min", "cheque_max", "currency",
    "cheque_size_range", "stage_min", "stage_max", "startup_stage",
    "past_investments", "geography", "website", "evidence_url",
    "investment_evidence_url", "eligibility_notes", "record_label",
]


def _failure(message: str) -> dict[str, Any]:
    return {"success": False, "integration": "LOCAL DEMO ONLY", "error": message}


def _approved(approved: bool) -> bool:
    if approved is not True:
        raise ValueError("Founder approval is required before this local demo action.")
    return True


def create_gmail_draft(to: str, subject: str, body: str, approved: bool = False, *, directory: Path = DEMO_DIR) -> dict:
    """Save an email draft locally. Never connects to Gmail or sends email."""
    try:
        _approved(approved)
        if not all(isinstance(value, str) for value in (to, subject, body)):
            raise ValueError("Recipient, subject, and body must be text.")
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", to.strip()):
            raise ValueError("Provide a valid recipient email address.")
        if not subject.strip() or not body.strip():
            raise ValueError("Subject and body are required.")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "email_drafts.jsonl"
        record = {"to": to.strip(), "subject": subject.strip(), "body": body.strip(), "status": "saved_locally_not_sent", "integration": "LOCAL DEMO ONLY"}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"success": True, "integration": "LOCAL DEMO ONLY", "message": "Draft saved locally; no Gmail connection and nothing was sent.", "path": str(path)}
    except (ValueError, OSError) as exc:
        return _failure(str(exc))


def append_to_sheet(record: dict, approved: bool = False, *, directory: Path = DEMO_DIR) -> dict:
    """Append a validated investor profile to a local CSV demo sheet."""
    try:
        _approved(approved)
        if not isinstance(record, dict):
            raise ValueError("Investor record must be an object.")
        name = str(record.get("name", "")).strip()
        firm = str(record.get("firm", "")).strip()
        if not name or not firm:
            raise ValueError("Investor record requires non-empty name and firm.")
        unexpected = set(record) - set(INVESTOR_COLUMNS)
        if unexpected:
            raise ValueError(f"Unsupported investor fields: {', '.join(sorted(unexpected))}.")
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "investor_sheet.csv"
        new_file = not path.exists() or path.stat().st_size == 0
        with path.open("a", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=INVESTOR_COLUMNS, extrasaction="raise")
            if new_file:
                writer.writeheader()
            writer.writerow({column: record.get(column, "") for column in INVESTOR_COLUMNS})
        return {"success": True, "integration": "LOCAL DEMO ONLY", "message": "Investor record appended to local CSV; no Google Sheets connection.", "path": str(path)}
    except (ValueError, OSError) as exc:
        return _failure(str(exc))


def create_calendar_followup(title: str, due_at: str, notes: str = "", approved: bool = False, *, directory: Path = DEMO_DIR) -> dict:
    """Save a follow-up reminder locally. Never connects to Google Calendar."""
    try:
        _approved(approved)
        if not all(isinstance(value, str) for value in (title, due_at, notes)):
            raise ValueError("Title, due_at, and notes must be text.")
        if not title.strip():
            raise ValueError("Reminder title is required.")
        try:
            due = datetime.fromisoformat(due_at.strip().replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise ValueError("due_at must be an ISO-8601 date/time, e.g. 2026-10-20T10:00:00+05:30.") from exc
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "followups.jsonl"
        record = {"title": title.strip(), "due_at": due.isoformat(), "notes": notes.strip(), "status": "saved_locally_not_scheduled", "integration": "LOCAL DEMO ONLY"}
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return {"success": True, "integration": "LOCAL DEMO ONLY", "message": "Reminder saved locally; no Google Calendar connection.", "path": str(path)}
    except (ValueError, OSError) as exc:
        return _failure(str(exc))

import csv
import json
import tempfile
import unittest
from pathlib import Path

from mcp_adapters import append_to_sheet, create_calendar_followup, create_gmail_draft
from mcp_server import mcp


class MCPAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_unapproved_actions_fail_without_writing(self):
        results = [
            create_gmail_draft("founder@example.com", "Hello", "Body", directory=self.directory),
            append_to_sheet({"name": "A", "firm": "B"}, directory=self.directory),
            create_calendar_followup("Call", "2026-10-20T10:00:00+05:30", directory=self.directory),
        ]
        self.assertTrue(all(not result["success"] and "approval" in result["error"].lower() for result in results))
        self.assertFalse(self.directory.exists() and any(self.directory.iterdir()))

    def test_approved_email_draft_is_saved_locally_not_sent(self):
        result = create_gmail_draft("founder@example.com", "Intro", "Draft text", True, directory=self.directory)
        self.assertTrue(result["success"])
        self.assertIn("LOCAL DEMO ONLY", result["integration"])
        saved = json.loads(Path(result["path"]).read_text(encoding="utf-8").strip())
        self.assertEqual(saved["status"], "saved_locally_not_sent")

    def test_investor_record_is_appended_and_validated(self):
        result = append_to_sheet({"name": "Demo", "firm": "Demo Ventures", "sectors": "SaaS"}, True, directory=self.directory)
        self.assertTrue(result["success"])
        with Path(result["path"]).open(encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(rows[0]["firm"], "Demo Ventures")
        invalid = append_to_sheet({"firm": "Missing name"}, True, directory=self.directory)
        self.assertFalse(invalid["success"])

    def test_followup_is_saved_locally_and_bad_datetime_fails(self):
        result = create_calendar_followup("Investor follow-up", "2026-10-20T10:00:00+05:30", "Review deck", True, directory=self.directory)
        self.assertTrue(result["success"])
        saved = json.loads(Path(result["path"]).read_text(encoding="utf-8").strip())
        self.assertEqual(saved["status"], "saved_locally_not_scheduled")
        invalid = create_calendar_followup("Call", "tomorrow", approved=True, directory=self.directory)
        self.assertFalse(invalid["success"])

    def test_fastmcp_registers_exactly_three_tools(self):
        self.assertEqual(set(mcp._tool_manager._tools), {"create_gmail_draft", "append_to_sheet", "create_calendar_followup"})


if __name__ == "__main__":
    unittest.main()

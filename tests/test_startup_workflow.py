import unittest

from investors import load_investors, rank_investors
from market_research import build_market_report
from pitch_generation import generate_pitch
from startup_workflow import prepare_startup_workflow


class StartupWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.records = load_investors()
        self.profile = {
            "startup_name": "Kisan Connect",
            "founder_name": "Asha Rao",
            "description": "A voice-first crop advisory tool for small farmers.",
            "sector": "Agriculture",
            "stage": "Seed",
            "geography": "Pune, India",
            "target_customers": "Small farmers in Maharashtra",
            "business_model": "Subscription paid by farmer collectives",
            "competitors": "",
            "traction": "",
            "funding_amount": 1.0,
            "funding_currency": "USD million",
            "women_led": False,
        }

    def test_csv_contains_verified_sample_profiles_with_sources(self):
        self.assertGreaterEqual(len(self.records), 10)
        self.assertTrue(all(item["record_label"] == "VERIFIED SAMPLE" for item in self.records))
        self.assertTrue(all(item["evidence_url"].startswith("https://") for item in self.records))
        self.assertTrue(all(item["website"].startswith("https://") for item in self.records))

    def test_ranking_uses_published_criteria_and_cxxo_eligibility(self):
        profile = {**self.profile, "sector": "DeepTech / AI", "stage": "Pre-seed", "funding_amount": 10.0, "funding_currency": "INR crore"}
        ranked = rank_investors(profile, self.records, limit=11)
        kalaari = next(item for item in ranked if item["firm"] == "Kalaari Capital")
        self.assertEqual(kalaari["score_breakdown"], {"sector": 1.0, "stage": 1.0, "cheque": 1.0, "geography": 1.0})
        self.assertNotIn("CXXO", [item["firm"] for item in ranked])
        eligible = rank_investors({**profile, "women_led": True}, self.records, limit=11)
        self.assertIn("CXXO (Kalaari initiative)", [item["firm"] for item in eligible])

    def test_unpublished_or_incomparable_cheques_are_not_converted_or_guessed(self):
        ranked = rank_investors({**self.profile, "funding_currency": "INR crore"}, self.records, limit=11)
        blume = next(item for item in ranked if item["firm"] == "Blume Ventures")
        self.assertIsNone(blume["score_breakdown"]["cheque"])
        self.assertIn("no exchange rate", " ".join(blume["reasons"]))

    def test_short_sector_tags_require_whole_word_matches(self):
        profile = {**self.profile, "sector": "DeepTech / AI"}
        ranked = rank_investors(profile, self.records, limit=11)
        omnivore = next(item for item in ranked if item["firm"] == "Omnivore")
        self.assertEqual(omnivore["score_breakdown"]["sector"], 0.0)

    def test_report_marks_market_gaps_instead_of_inventing_tam(self):
        report = build_market_report(self.profile)
        self.assertIn("no source-backed tam", report["market_opportunity"].lower())
        self.assertIn("not evidence that competitors do not exist", report["competitors"])
        self.assertTrue(all(source["source_url"].startswith("https://") for source in report["verified_context"]))

    def test_pitch_uses_profile_and_omits_unprovided_traction(self):
        match = next(item for item in self.records if item["firm"] == "Omnivore")
        draft = generate_pitch(self.profile, match)
        self.assertIn("Kisan Connect", draft["body"])
        self.assertIn("Agriculture", draft["body"])
        self.assertIn("AgNext", draft["body"])
        self.assertNotIn("Current traction:", draft["body"])
        self.assertFalse(draft["sent"])

    def test_complete_workflow_runs_without_external_actions(self):
        result = prepare_startup_workflow(self.profile, self.records)
        self.assertEqual(len(result["matches"]), 3)
        self.assertEqual(len(result["drafts"]), 3)
        self.assertEqual(result["external_actions"], [])


if __name__ == "__main__":
    unittest.main()

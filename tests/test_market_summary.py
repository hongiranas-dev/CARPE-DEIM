import copy
import unittest
from unittest.mock import patch

import market_research
from market_research import generate_market_summary
from sarvam_client import SarvamConfigurationError, SarvamRequestError


class MarketSummaryTests(unittest.TestCase):
    def setUp(self):
        market_research._cached_market_answer.cache_clear()
        self.profile = {
            "description": "A voice-first crop advisory tool for small farmers.",
            "target_customers": "Small farmers in Maharashtra",
            "competitors": "Founder-listed competitor",
            "business_model": "Subscription via farmer collectives",
        }
        self.passage = {
            "text": "A source-grounded excerpt about startup recognition.",
            "title": "Startup India: Recognition",
            "source_url": "https://www.startupindia.gov.in/content/sih/en/startup-scheme.html",
            "publisher": "Startup India",
            "language": "en",
            "passage_type": "official",
            "similarity": 0.82,
        }
        self.report = {
            "problem_statement": self.profile["description"],
            "target_customers": self.profile["target_customers"],
            "competitors": "No competitor evidence is present.",
            "market_opportunity": "No source-backed TAM, SAM, or SOM is available.",
            "business_model": self.profile["business_model"],
            "risks": ["Willingness to pay is unvalidated."],
            "verified_context": [self.passage],
            "corpus_note": "Administrative context only.",
        }

    def tearDown(self):
        market_research._cached_market_answer.cache_clear()

    def test_supported_evidence_generates_summary_with_retrieved_sources_and_labeled_assumptions(self):
        with patch("market_research.generate_answer", return_value="Verified findings [1] [99]. Market size is unknown. See https://invented.example/data") as generate:
            result = generate_market_summary(self.profile, self.report)

        self.assertEqual(result["status"], "generated")
        self.assertIn("[1]", result["text"])
        self.assertNotIn("invented.example", result["text"])
        self.assertNotIn("[99]", result["text"])
        self.assertIn(self.passage["source_url"], result["text"])
        self.assertIn("AI-generated preliminary analysis", result["text"])
        question, evidence = generate.call_args.args
        self.assertIn("Founder-provided startup profile (unverified assumptions)", question)
        self.assertIn("Never invent market size, TAM/SAM/SOM values", question)
        self.assertIn("Competitor landscape and search plan", question)
        self.assertIn("bottom-up method", question)
        self.assertIn("Practical validation steps", question)
        self.assertIn("Small farmers in Maharashtra", question)
        self.assertEqual(evidence[0]["title"], self.passage["title"])
        self.assertEqual(evidence[0]["source_url"], self.passage["source_url"])

    def test_insufficient_evidence_uses_profile_for_hypotheses_but_labels_them(self):
        report = {**self.report, "verified_context": []}
        with patch("market_research.generate_answer", return_value="Competitor categories and search plan.") as generate:
            result = generate_market_summary(self.profile, report)
        self.assertEqual(result["status"], "generated")
        self.assertIn("No relevant verified source passages were retrieved", result["text"])
        self.assertIn("hypotheses, not validated facts", result["text"])
        self.assertIn("No verified source passages retrieved", result["text"])
        self.assertEqual(generate.call_args.args[1], [])
        self.assertIn("generic competitor categories", generate.call_args.args[0])
        self.assertIn("no relevant passages", generate.call_args.args[0])

    def test_generation_failure_keeps_deterministic_report_available(self):
        original_report = copy.deepcopy(self.report)
        with patch("market_research.generate_answer", side_effect=SarvamRequestError("temporary request failure")):
            result = generate_market_summary(self.profile, self.report)
        self.assertEqual(result["status"], "failed")
        self.assertIn("deterministic brief below is unchanged", result["message"])
        self.assertEqual(self.report, original_report)

    def test_missing_sarvam_configuration_keeps_deterministic_fallback(self):
        with patch("market_research.generate_answer", side_effect=SarvamConfigurationError("Sarvam API key is missing.")):
            result = generate_market_summary(self.profile, self.report)
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("API key is missing", result["message"])
        self.assertIn("deterministic brief below is unchanged", result["message"])

    def test_summary_does_not_change_existing_deterministic_calculations(self):
        original_report = copy.deepcopy(self.report)
        with patch("market_research.generate_answer", return_value="Source-grounded narrative."):
            generate_market_summary(self.profile, self.report)
        self.assertEqual(self.report, original_report)

    def test_repeated_identical_summary_uses_cache(self):
        with patch("market_research.generate_answer", return_value="Cached summary.") as generate:
            first = generate_market_summary(self.profile, self.report)
            second = generate_market_summary(self.profile, self.report)
        self.assertEqual(first, second)
        generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()

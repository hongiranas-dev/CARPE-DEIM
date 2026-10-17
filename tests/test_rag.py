import unittest

from rag import retrieve


class RetrievalTests(unittest.TestCase):
    def test_dpiit_retrieval_preserves_source_metadata(self):
        results = retrieve("DPIIT startup recognition eligibility and how to apply")
        self.assertTrue(results)
        self.assertIn("Startup Recognition", results[0]["title"])
        self.assertEqual(results[0]["publisher"], "Startup India, DPIIT, Ministry of Commerce and Industry")
        self.assertTrue(results[0]["source_url"].startswith("https://www.startupindia.gov.in/"))
        self.assertTrue(results[0]["text"])

    def test_unrelated_query_does_not_force_a_citation(self):
        results = retrieve("How do I bake sourdough bread?")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from unittest.mock import patch

from sarvam_client import SarvamConfigurationError, generate_answer


class SarvamClientTests(unittest.TestCase):
    def test_missing_key_fails_without_network_call(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": ""}):
            with self.assertRaisesRegex(SarvamConfigurationError, "SARVAM_API_KEY"):
                generate_answer("What is DPIIT recognition?", [])


if __name__ == "__main__":
    unittest.main()

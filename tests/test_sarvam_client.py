import os
import unittest
from unittest.mock import patch

from sarvam_client import API_URL, MAX_TOKENS, MODEL, SarvamConfigurationError, SarvamRequestError, generate_answer


class FakeResponse:
    def __init__(self, status_code=200, payload=None, *, json_error=None, content_type="application/json"):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error
        self.headers = {"Content-Type": content_type}

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


class SarvamClientTests(unittest.TestCase):
    def test_missing_key_fails_without_network_call(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": ""}):
            with self.assertRaisesRegex(SarvamConfigurationError, "SARVAM_API_KEY"):
                generate_answer("What is DPIIT recognition?", [])

    def test_parses_official_v1_success_and_sends_retrieved_context(self):
        response = FakeResponse(payload={
            "id": "completion-id",
            "object": "chat.completion",
            "model": "sarvam-105b",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "DPIIT recognition is available to eligible startups. [1]"}}],
            "usage": {"completion_tokens": 12},
        })
        passage = {"title": "Startup Recognition", "source_url": "https://startupindia.gov.in/recognition", "text": "Eligibility details."}
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key-do-not-log"}), patch("sarvam_client.requests.post", return_value=response) as post:
            answer = generate_answer("How do I apply?", [passage])
        self.assertEqual(answer, "DPIIT recognition is available to eligible startups. [1]")
        post.assert_called_once()
        args, kwargs = post.call_args
        self.assertEqual(args[0], API_URL)
        self.assertEqual(kwargs["headers"]["api-subscription-key"], "test-key-do-not-log")
        self.assertEqual(kwargs["json"]["model"], MODEL)
        self.assertEqual(kwargs["json"]["reasoning_effort"], None)
        self.assertEqual(kwargs["json"]["max_tokens"], MAX_TOKENS)
        user_message = kwargs["json"]["messages"][1]["content"]
        self.assertIn(passage["source_url"], user_message)
        self.assertIn(passage["text"], user_message)

    def test_empty_answer_includes_finish_reason_without_sensitive_body(self):
        response = FakeResponse(payload={"choices": [{"finish_reason": "stop", "message": {"content": "  "}}]})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_client.requests.post", return_value=response):
            with self.assertRaisesRegex(SarvamRequestError, "finish_reason='stop'"):
                generate_answer("question", [])

    def test_empty_answer_at_token_limit_is_diagnosed(self):
        response = FakeResponse(payload={"choices": [{"finish_reason": "length", "message": {"content": ""}}]})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_client.requests.post", return_value=response):
            with self.assertRaisesRegex(SarvamRequestError, "token limit"):
                generate_answer("question", [])

    def test_null_content_at_token_limit_has_actionable_diagnostic(self):
        response = FakeResponse(payload={"choices": [{"finish_reason": "length", "message": {"content": None}}]})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_client.requests.post", return_value=response):
            with self.assertRaisesRegex(SarvamRequestError, "hit max_tokens.*Reasoning is disabled"):
                generate_answer("question", [])

    def test_non_success_response_reports_safe_error_code_not_message_or_headers(self):
        secret = "do-not-print-this-secret"
        response = FakeResponse(status_code=429, payload={"error": {"type": "rate_limit_error", "code": "quota_exceeded", "message": secret}})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_client.requests.post", return_value=response):
            with self.assertRaises(SarvamRequestError) as caught:
                generate_answer("question", [])
        self.assertIn("HTTP 429", str(caught.exception))
        self.assertIn("quota_exceeded", str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))
        self.assertNotIn("test-key", str(caught.exception))

    def test_unexpected_json_structure_reports_top_level_fields(self):
        response = FakeResponse(payload={"id": "x", "result": "not the V1 choices schema"})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_client.requests.post", return_value=response):
            with self.assertRaisesRegex(SarvamRequestError, "choices.*Top-level fields: id, result"):
                generate_answer("question", [])

    def test_invalid_json_reports_status_and_safe_content_type(self):
        response = FakeResponse(status_code=200, json_error=ValueError("not json"), content_type="text/html")
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_client.requests.post", return_value=response):
            with self.assertRaisesRegex(SarvamRequestError, "HTTP 200.*text/html"):
                generate_answer("question", [])

    def test_empty_choices_and_non_string_content_are_rejected(self):
        cases = [
            (FakeResponse(payload={"choices": []}), "empty 'choices'"),
            (FakeResponse(payload={"choices": [{"finish_reason": "stop", "message": {"content": []}}]}), "expects a string"),
        ]
        for response, expected in cases:
            with self.subTest(expected=expected), patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_client.requests.post", return_value=response):
                with self.assertRaisesRegex(SarvamRequestError, expected):
                    generate_answer("question", [])


if __name__ == "__main__":
    unittest.main()

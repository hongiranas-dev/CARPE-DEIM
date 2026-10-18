import base64
import os
import unittest
from unittest.mock import patch

import requests

from sarvam_voice import (
    MAX_AUDIO_BYTES,
    MAX_TTS_CHARACTERS,
    STT_MODEL,
    STT_URL,
    TTS_LANGUAGES,
    TTS_MODEL,
    TTS_URL,
    SarvamVoiceConfigurationError,
    SarvamVoiceError,
    synthesize_speech,
    transcribe_audio,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, *, json_error=None):
        self.status_code = status_code
        self._payload = payload
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise self._json_error
        return self._payload


def wav_bytes():
    # Minimal RIFF/WAVE-shaped byte sequence for validating the documented format.
    return b"RIFF\x18\x00\x00\x00WAVEfmt " + b"\x00" * 16


class SarvamVoiceTests(unittest.TestCase):
    def test_stt_posts_audio_and_returns_documented_transcript(self):
        response = FakeResponse(payload={"request_id": "request-1", "transcript": "मेरा सवाल", "language_code": "hi-IN"})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post", return_value=response) as post:
            transcript = transcribe_audio(b"sample audio", "question.webm", "audio/webm", "hi-IN")
        self.assertEqual(transcript, "मेरा सवाल")
        args, kwargs = post.call_args
        self.assertEqual(args[0], STT_URL)
        self.assertEqual(kwargs["headers"]["api-subscription-key"], "test-key")
        self.assertEqual(kwargs["files"]["file"], ("question.webm", b"sample audio", "audio/webm"))
        self.assertEqual(kwargs["data"], {"model": STT_MODEL, "language_code": "hi-IN"})
        self.assertEqual(kwargs["timeout"], 45)

    def test_stt_auto_detection_and_pcm_codec_parameters(self):
        response = FakeResponse(payload={"transcript": "recognized", "language_code": "en-IN"})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post", return_value=response) as post:
            transcribe_audio(b"pcm", "audio.pcm", "audio/pcm", input_audio_codec="pcm_s16le")
        self.assertEqual(post.call_args.kwargs["data"], {
            "model": STT_MODEL, "language_code": "unknown", "input_audio_codec": "pcm_s16le",
        })

    def test_stt_rejects_empty_unsupported_and_oversized_audio_before_network(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post") as post:
            cases = [
                ((b"", "x.wav", "audio/wav"), {}, "non-empty"),
                ((b"audio", "x.txt", "text/plain"), {}, "Unsupported audio"),
                ((b"audio", "x.pcm", "audio/pcm"), {}, "requires input_audio_codec"),
                ((b"audio", "x.wav", "audio/wav"), {"language_code": "fr-FR"}, "Unsupported STT language"),
                ((b"x" * (MAX_AUDIO_BYTES + 1), "x.wav", "audio/wav"), {}, "upload limit"),
            ]
            for args, kwargs, expected in cases:
                with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, expected):
                    transcribe_audio(*args, **kwargs)
        post.assert_not_called()

    def test_stt_reports_http_json_timeout_and_empty_transcript_errors(self):
        scenarios = [
            (FakeResponse(413, {"error": {"code": "audio_too_large", "message": "private detail"}}), "HTTP 413.*audio_too_large"),
            (FakeResponse(json_error=ValueError()), "invalid JSON"),
            (FakeResponse(payload={"transcript": "  "}), "no transcript"),
        ]
        for response, expected in scenarios:
            with self.subTest(expected=expected), patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post", return_value=response):
                with self.assertRaisesRegex(SarvamVoiceError, expected) as caught:
                    transcribe_audio(b"audio", "x.wav", "audio/wav")
                self.assertNotIn("private detail", str(caught.exception))

        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post", side_effect=requests.Timeout):
            with self.assertRaisesRegex(SarvamVoiceError, "timed out"):
                transcribe_audio(b"audio", "x.wav", "audio/wav")

    def test_missing_key_fails_without_network_call(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": ""}), patch("sarvam_voice.requests.post") as post:
            with self.assertRaises(SarvamVoiceConfigurationError):
                synthesize_speech("Hello", "en-IN")
        post.assert_not_called()

    def test_tts_posts_documented_payload_and_decodes_wav(self):
        audio = wav_bytes()
        response = FakeResponse(payload={"request_id": "request-2", "audios": [base64.b64encode(audio).decode("ascii")]})
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post", return_value=response) as post:
            decoded, metadata = synthesize_speech("नमस्ते", "hi-IN")
        self.assertEqual(decoded, audio)
        self.assertEqual(metadata, {
            "mime_type": "audio/wav", "format": "wav", "model": TTS_MODEL,
            "language_code": "hi-IN", "sample_rate_hz": 22050, "request_id": "request-2",
        })
        args, kwargs = post.call_args
        self.assertEqual(args[0], TTS_URL)
        self.assertEqual(kwargs["headers"]["api-subscription-key"], "test-key")
        self.assertEqual(kwargs["json"], {
            "text": "नमस्ते", "language_code": "hi-IN", "model": TTS_MODEL,
            "output_audio_codec": "wav", "speech_sample_rate": 22050,
        })

    def test_tts_validates_text_and_language_before_network(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post") as post:
            invalid_inputs = [
                ("", "en-IN", "non-empty"),
                ("x" * (MAX_TTS_CHARACTERS + 1), "en-IN", "TTS limit"),
                ("Hello", "fr-FR", "Unsupported TTS language"),
            ]
            for text, language, expected in invalid_inputs:
                with self.subTest(expected=expected), self.assertRaisesRegex(ValueError, expected):
                    synthesize_speech(text, language)
        post.assert_not_called()
        self.assertIn("hi-IN", TTS_LANGUAGES)

    def test_tts_handles_http_malformed_json_base64_empty_and_bad_wav(self):
        cases = [
            (FakeResponse(429, {"error": {"type": "rate_limit_error"}}), "HTTP 429"),
            (FakeResponse(json_error=ValueError()), "invalid JSON"),
            (FakeResponse(payload={"audios": ["not-base64!"]}), "malformed base64"),
            (FakeResponse(payload={"audios": []}), "no audio data"),
            (FakeResponse(payload={"audios": [base64.b64encode(b"not wave bytes").decode()]}), "not a valid WAV"),
        ]
        for response, expected in cases:
            with self.subTest(expected=expected), patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post", return_value=response):
                with self.assertRaisesRegex(SarvamVoiceError, expected):
                    synthesize_speech("Hello", "en-IN")

    def test_tts_reports_timeout(self):
        with patch.dict(os.environ, {"SARVAM_API_KEY": "test-key"}), patch("sarvam_voice.requests.post", side_effect=requests.Timeout):
            with self.assertRaisesRegex(SarvamVoiceError, "timed out"):
                synthesize_speech("Hello", "en-IN")


if __name__ == "__main__":
    unittest.main()

"""Small, backend-only Sarvam speech-to-text and text-to-speech clients."""

import base64
import binascii
import os
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


STT_URL = "https://api.sarvam.ai/speech-to-text"
TTS_URL = "https://api.sarvam.ai/text-to-speech"
STT_MODEL = "saaras:v4"
TTS_MODEL = "bulbul:v4-flash"
MAX_AUDIO_BYTES = 15 * 1024 * 1024
MAX_TTS_CHARACTERS = 2500
REQUEST_TIMEOUT_SECONDS = 45

STT_LANGUAGES = {
    "unknown", "hi-IN", "bn-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN",
    "ta-IN", "te-IN", "en-IN", "gu-IN", "as-IN", "ur-IN", "ne-IN", "kok-IN",
    "ks-IN", "sd-IN", "sa-IN", "sat-IN", "mni-IN", "brx-IN", "mai-IN", "doi-IN",
}
TTS_LANGUAGES = {
    "hi-IN", "bn-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN",
    "ta-IN", "te-IN", "en-IN", "gu-IN",
}
SUPPORTED_AUDIO_TYPES = {
    "audio/wav", "audio/wave", "audio/x-wav", "audio/mpeg", "audio/mp3", "audio/aac",
    "audio/aiff", "audio/x-aiff", "audio/ogg", "audio/opus", "audio/flac", "audio/mp4",
    "audio/x-m4a", "audio/amr", "audio/x-ms-wma", "audio/webm", "audio/pcm", "audio/l16",
    "application/ogg",
}
PCM_CODECS = {"pcm_s16le", "pcm_l16", "pcm_raw"}

load_dotenv(Path(__file__).resolve().parent / ".env")


class SarvamVoiceError(RuntimeError):
    """Safe error raised when a Sarvam voice request cannot be completed."""


class SarvamVoiceConfigurationError(SarvamVoiceError):
    """Raised when the backend Sarvam API key is not configured."""


def _api_key() -> str:
    key = os.getenv("SARVAM_API_KEY", "").strip()
    if not key or key == "your_sarvam_api_key_here":
        raise SarvamVoiceConfigurationError(
            "Sarvam API key is missing. Add SARVAM_API_KEY to the project .env file."
        )
    return key


def _post_error(response: requests.Response, service: str) -> SarvamVoiceError:
    """Report status and safe provider error identifiers without echoing body/headers."""
    details: list[str] = []
    try:
        payload = response.json()
    except (ValueError, requests.RequestException):
        payload = None
    if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
        error = payload["error"]
        for field in ("code", "type"):
            value = error.get(field)
            if isinstance(value, str) and value and value.replace("_", "").replace("-", "").isalnum():
                details.append(f"{field}={value[:60]}")
        if "message" in error:
            details.append("provider message omitted")
    suffix = f" ({', '.join(details)})" if details else ""
    return SarvamVoiceError(f"Sarvam {service} returned HTTP {response.status_code}{suffix}.")


def _json_response(response: requests.Response, service: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise SarvamVoiceError(f"Sarvam {service} returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise SarvamVoiceError(f"Sarvam {service} returned an unexpected JSON structure.")
    return payload


def transcribe_audio(
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    language_code: str = "unknown",
    *,
    input_audio_codec: str | None = None,
) -> str:
    """Transcribe audio with Saaras v4; language_code='unknown' enables auto-detection.

    The REST endpoint is intended for short interactive clips. Raw PCM audio must be
    16 kHz and specify its codec (pcm_s16le, pcm_l16, or pcm_raw).
    """
    if not isinstance(audio_bytes, bytes) or not audio_bytes:
        raise ValueError("audio_bytes must contain non-empty audio data.")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError(f"Audio exceeds the {MAX_AUDIO_BYTES // (1024 * 1024)} MiB upload limit.")
    if not isinstance(filename, str) or not filename.strip() or any(ch in filename for ch in "\r\n\0"):
        raise ValueError("filename must be a non-empty filename without control characters.")
    if not isinstance(content_type, str) or not content_type.strip():
        raise ValueError("content_type is required.")
    media_type = content_type.split(";", 1)[0].strip().lower()
    if media_type not in SUPPORTED_AUDIO_TYPES:
        raise ValueError("Unsupported audio content type. Provide a supported audio format such as audio/wav or audio/webm.")
    if not isinstance(language_code, str) or language_code not in STT_LANGUAGES:
        raise ValueError("Unsupported STT language_code. Use a documented Sarvam language code or 'unknown'.")
    if input_audio_codec is not None and (not isinstance(input_audio_codec, str) or input_audio_codec not in PCM_CODECS):
        raise ValueError("input_audio_codec must be pcm_s16le, pcm_l16, or pcm_raw when specified.")
    if media_type in {"audio/pcm", "audio/l16"} and input_audio_codec is None:
        raise ValueError("Raw PCM audio requires input_audio_codec and a 16 kHz sample rate.")

    form: dict[str, str] = {"model": STT_MODEL, "language_code": language_code}
    if input_audio_codec is not None:
        form["input_audio_codec"] = input_audio_codec

    try:
        response = requests.post(
            STT_URL,
            headers={"api-subscription-key": _api_key()},
            files={"file": (filename.strip(), audio_bytes, content_type.strip())},
            data=form,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise SarvamVoiceError("Sarvam speech-to-text timed out. Try a shorter audio clip.") from exc
    except requests.RequestException as exc:
        raise SarvamVoiceError("Could not reach Sarvam speech-to-text. Check the connection and retry.") from exc

    if not 200 <= response.status_code < 300:
        raise _post_error(response, "speech-to-text")
    result = _json_response(response, "speech-to-text")
    transcript = result.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        raise SarvamVoiceError("Sarvam speech-to-text returned no transcript.")
    return transcript.strip()


def synthesize_speech(text: str, language_code: str) -> tuple[bytes, dict[str, Any]]:
    """Synthesize text with Bulbul v4-flash and return WAV bytes plus format metadata."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must contain non-empty speech content.")
    clean_text = text.strip()
    if len(clean_text) > MAX_TTS_CHARACTERS:
        raise ValueError(f"text exceeds the {MAX_TTS_CHARACTERS}-character TTS limit.")
    if not isinstance(language_code, str) or language_code not in TTS_LANGUAGES:
        raise ValueError("Unsupported TTS language_code. Use a documented Sarvam language code.")

    payload = {
        "text": clean_text,
        "language_code": language_code,
        "model": TTS_MODEL,
        "output_audio_codec": "wav",
        "speech_sample_rate": 22050,
    }
    try:
        response = requests.post(
            TTS_URL,
            headers={"api-subscription-key": _api_key(), "Content-Type": "application/json"},
            json=payload,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.Timeout as exc:
        raise SarvamVoiceError("Sarvam text-to-speech timed out. Try a shorter response.") from exc
    except requests.RequestException as exc:
        raise SarvamVoiceError("Could not reach Sarvam text-to-speech. Check the connection and retry.") from exc

    if not 200 <= response.status_code < 300:
        raise _post_error(response, "text-to-speech")
    result = _json_response(response, "text-to-speech")
    audios = result.get("audios")
    if not isinstance(audios, list) or not audios or not isinstance(audios[0], str) or not audios[0]:
        raise SarvamVoiceError("Sarvam text-to-speech returned no audio data.")
    try:
        audio_bytes = base64.b64decode(audios[0], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise SarvamVoiceError("Sarvam text-to-speech returned malformed base64 audio.") from exc
    if not audio_bytes:
        raise SarvamVoiceError("Sarvam text-to-speech returned empty audio bytes.")
    if len(audio_bytes) < 12 or audio_bytes[:4] != b"RIFF" or audio_bytes[8:12] != b"WAVE":
        raise SarvamVoiceError("Sarvam text-to-speech response was not a valid WAV audio file.")

    metadata = {
        "mime_type": "audio/wav",
        "format": "wav",
        "model": TTS_MODEL,
        "language_code": language_code,
        "sample_rate_hz": 22050,
        "request_id": result.get("request_id"),
    }
    return audio_bytes, metadata

"""Small backend-only client for Sarvam's documented V1 chat completion API."""

import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv


API_URL = "https://api.sarvam.ai/v1/chat/completions"
MODEL = "sarvam-105b"
MAX_TOKENS = 700
load_dotenv(Path(__file__).resolve().parent / ".env")


class SarvamConfigurationError(RuntimeError):
    pass


class SarvamRequestError(RuntimeError):
    pass


def _safe_error_summary(payload: object) -> str:
    """Return only bounded error codes/types; never echo response bodies or headers."""
    if not isinstance(payload, dict):
        return ""
    error = payload.get("error")
    if error is None:
        return ""
    if not isinstance(error, dict):
        return " Provider returned an error field; its value was omitted."

    details = []
    for field in ("type", "code"):
        value = error.get(field)
        if isinstance(value, str) and value:
            safe_value = re.sub(r"[^A-Za-z0-9_.:-]", "?", value[:80])
            details.append(f"{field}={safe_value}")
    if "message" in error:
        details.append("message=present (omitted)")
    return f" Provider error: {', '.join(details)}." if details else " Provider returned an error object without a safe code."


def _response_fields(payload: object) -> str:
    if isinstance(payload, dict):
        fields = sorted(str(key)[:40] for key in payload.keys())
        return f" Top-level fields: {', '.join(fields) or '(none)'} ."
    return f" JSON root type: {type(payload).__name__}."


def generate_answer(question: str, passages: list[dict]) -> str:
    """Generate a grounded answer from retrieved passages; never log credentials."""
    api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not api_key or api_key == "your_sarvam_api_key_here":
        raise SarvamConfigurationError("Sarvam API key is missing. Add SARVAM_API_KEY to the project .env file.")

    context = "\n\n".join(
        f"[{index}] {item['title']} ({item['source_url']})\n{item['text']}"
        for index, item in enumerate(passages, start=1)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are FounderOS, an Indian startup information assistant. Answer in the language/script the user used. "
                "Use only the supplied evidence for factual claims. If evidence does not answer a part, say what is missing. "
                "Do not invent rules, dates, eligibility details, or links. Refer to sources with [1], [2], etc. "
                "The evidence may include clearly marked curated translations/summaries of official sources."
            ),
        },
        {"role": "user", "content": f"Question: {question}\n\nRetrieved evidence:\n{context}"},
    ]
    try:
        response = requests.post(
            API_URL,
            headers={"api-subscription-key": api_key, "Content-Type": "application/json"},
            json={
                "model": MODEL,
                "messages": messages,
                "temperature": 0.2,
                "max_tokens": MAX_TOKENS,
                # V1 defaults to medium reasoning. Explicit null disables hidden reasoning tokens
                # so the bounded answer budget is available for user-visible text.
                "reasoning_effort": None,
            },
            timeout=45,
        )
    except requests.RequestException as exc:
        raise SarvamRequestError("Could not reach Sarvam. Check your connection and try again.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        content_type = response.headers.get("Content-Type", "unknown")
        raise SarvamRequestError(
            f"Sarvam returned HTTP {response.status_code} with non-JSON content (Content-Type: {content_type})."
        ) from exc

    if not 200 <= response.status_code < 300:
        summary = _safe_error_summary(payload)
        raise SarvamRequestError(f"Sarvam returned HTTP {response.status_code}.{summary}")

    if not isinstance(payload, dict):
        raise SarvamRequestError(f"Sarvam returned HTTP {response.status_code} with an unexpected JSON shape.{_response_fields(payload)}")
    choices = payload.get("choices")
    if not isinstance(choices, list):
        raise SarvamRequestError(
            f"Sarvam returned HTTP {response.status_code}, but 'choices' is missing or is not a list.{_response_fields(payload)}"
        )
    if not choices:
        raise SarvamRequestError(f"Sarvam returned HTTP {response.status_code} with an empty 'choices' list.{_response_fields(payload)}")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise SarvamRequestError("Sarvam returned a choice that is not an object.")

    finish_reason = choice.get("finish_reason")
    if finish_reason is not None and not isinstance(finish_reason, str):
        raise SarvamRequestError("Sarvam returned a non-string finish_reason in its first choice.")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise SarvamRequestError(f"Sarvam returned no message object for its first choice (finish_reason={finish_reason!r}).")
    content = message.get("content")
    if not isinstance(content, str):
        if content is None and finish_reason == "length":
            raise SarvamRequestError(
                "Sarvam returned no answer text because generation hit max_tokens "
                f"({MAX_TOKENS}) (finish_reason='length'). Reasoning is disabled for this request; "
                "increase max_tokens if this persists."
            )
        raise SarvamRequestError(
            f"Sarvam returned message.content as {type(content).__name__}; Chat Completion V1 expects a string "
            f"(finish_reason={finish_reason!r})."
        )
    if not content.strip():
        if finish_reason == "length":
            detail = " Generation stopped at the token limit before producing text."
        elif finish_reason in ("stop", None):
            detail = " The provider completed the request without answer text."
        else:
            detail = f" The provider finished with reason {finish_reason!r} without answer text."
        if finish_reason in ("stop", None, "length"):
            detail += f" finish_reason={finish_reason!r}."
        raise SarvamRequestError(f"Sarvam returned HTTP {response.status_code} with empty message.content.{detail}")
    return content.strip()

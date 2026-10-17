"""Small backend-only client for Sarvam's documented V1 chat completion API."""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


API_URL = "https://api.sarvam.ai/v1/chat/completions"
MODEL = "sarvam-105b"
load_dotenv(Path(__file__).resolve().parent / ".env")


class SarvamConfigurationError(RuntimeError):
    pass


class SarvamRequestError(RuntimeError):
    pass


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
            json={"model": MODEL, "messages": messages, "temperature": 0.2, "max_tokens": 700},
            timeout=45,
        )
    except requests.RequestException as exc:
        raise SarvamRequestError("Could not reach Sarvam. Check your connection and try again.") from exc

    if not response.ok:
        raise SarvamRequestError(f"Sarvam returned HTTP {response.status_code}. Check the API key and account access.")
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise SarvamRequestError("Sarvam returned an unexpected response format.") from exc
    if not isinstance(content, str) or not content.strip():
        raise SarvamRequestError("Sarvam returned an empty answer.")
    return content.strip()

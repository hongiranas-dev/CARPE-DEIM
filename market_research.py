"""Evidence-first, deterministic market-research brief builder."""

import json
import re
from functools import lru_cache
from time import time

from rag import has_sufficient_evidence, retrieve
from sarvam_client import SarvamConfigurationError, SarvamRequestError, generate_answer


def build_market_report(startup: dict) -> dict:
    query = " ".join(
        value for value in (
            startup.get("sector", ""), startup.get("description", ""), startup.get("target_customers", ""),
            "India startup incorporation DPIIT GST official policy",
        ) if value
    )
    passages = retrieve(query, limit=4)
    official_context = []
    seen_urls = set()
    for passage in passages:
        if passage["source_url"] in seen_urls or passage["language"] != "en":
            continue
        seen_urls.add(passage["source_url"])
        official_context.append(passage)

    return {
        "problem_statement": startup.get("description", "").strip() or "Not provided. Add a specific customer problem and current workaround.",
        "problem_label": "Founder-provided hypothesis; not independently validated.",
        "target_customers": startup.get("target_customers", "").strip() or "Not provided. Identify a narrow first customer segment.",
        "customer_label": "Founder-provided hypothesis; validate with customer interviews.",
        "competitors": startup.get("competitors", "").strip() or "No competitor evidence is present in the available official-source corpus. This is a research gap, not evidence that competitors do not exist.",
        "competitor_label": "Founder-provided names are unverified." if startup.get("competitors", "").strip() else "Not researched in the available corpus.",
        "market_opportunity": "No source-backed TAM, SAM, or SOM is available in the current corpus; no market-size figure is estimated.",
        "business_model": startup.get("business_model", "").strip() or "Not provided. Define who pays, what they pay for, and expected pricing.",
        "business_model_label": "Founder-provided hypothesis; not validated." if startup.get("business_model", "").strip() else "Not provided.",
        "risks": [
            "Problem severity and willingness to pay are not validated by the supplied information.",
            "Competitor landscape and customer acquisition costs are not evidenced in this corpus.",
            "Market size remains unquantified; estimate only after defining target geography, customer count, and pricing evidence.",
        ],
        "verified_context": official_context,
        "corpus_note": "The available documents cover startup recognition, GST, and incorporation. They support administrative context, not market sizing or competitive claims.",
    }


def generate_market_summary(startup: dict, report: dict) -> dict:
    """Create an optional source-grounded narrative without changing the deterministic report."""
    passages = report.get("verified_context", [])
    if not has_sufficient_evidence(passages):
        return {
            "status": "insufficient_evidence",
            "text": None,
            "message": "A Sarvam summary was not generated: the retrieved passages do not provide enough relevant evidence. The deterministic brief below remains available.",
        }

    founder_assumptions = {
        "problem_description": startup.get("description", ""),
        "target_customers": startup.get("target_customers", ""),
        "competitors_listed_by_founder": startup.get("competitors", ""),
        "proposed_business_model": startup.get("business_model", ""),
    }
    brief = {
        "problem_statement": report.get("problem_statement"),
        "target_customers": report.get("target_customers"),
        "competitors": report.get("competitors"),
        "market_opportunity": report.get("market_opportunity"),
        "business_model": report.get("business_model"),
        "risks": report.get("risks", []),
        "research_scope_note": report.get("corpus_note", ""),
    }
    question = (
        "Write a concise, readable market-research summary for this startup. Treat the supplied source passages as the only verified facts. "
        "Keep founder-provided assumptions clearly separate and label them unvalidated. Include a section for evidence gaps. "
        "Do not invent TAM, SAM, SOM, revenue, growth rates, competitor facts/statistics, or citations. "
        "If the evidence does not support a market claim, say that it is unknown. Cite source passages only with their numbered [n] references; "
        "the references include the actual source title and URL.\n\n"
        f"Founder-provided assumptions (unverified): {json.dumps(founder_assumptions, ensure_ascii=False)}\n\n"
        f"Existing deterministic brief (preserve its caveats): {json.dumps(brief, ensure_ascii=False)}"
    )
    try:
        text = _cached_market_answer(
            question,
            json.dumps(passages, sort_keys=True, ensure_ascii=False),
            int(time() // 3600),
        )
    except SarvamConfigurationError as exc:
        return {"status": "unavailable", "text": None, "message": f"{exc} The deterministic brief below is unchanged."}
    except SarvamRequestError as exc:
        return {"status": "failed", "text": None, "message": f"Sarvam summary unavailable: {exc} The deterministic brief below is unchanged."}
    except Exception:
        # Keep the local research workflow usable if the optional narrative integration fails.
        return {"status": "failed", "text": None, "message": "Sarvam summary unavailable due to an unexpected error. The deterministic brief below is unchanged."}
    return {"status": "generated", "text": _attach_verified_sources(text, passages), "message": None}


def _attach_verified_sources(text: str, passages: list[dict]) -> str:
    """Remove model-provided links not in retrieved metadata and list only retrieved sources."""
    source_urls = {item["source_url"] for item in passages if item.get("source_url")}
    text = re.sub(
        r"\[(\d+)\]",
        lambda match: match.group(0) if 1 <= int(match.group(1)) <= len(passages) else "",
        text,
    )
    markdown_link = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
    text = markdown_link.sub(lambda match: match.group(0) if match.group(2) in source_urls else match.group(1), text)
    bare_url = re.compile(r"https?://[^\s)\]]+")
    text = bare_url.sub(lambda match: match.group(0) if match.group(0).rstrip(".,;:") in source_urls else "", text)
    source_list = "\n\n**Retrieved sources**\n" + "\n".join(
        f"- [{index}] [{item['title']}]({item['source_url']})"
        for index, item in enumerate(passages, start=1)
    )
    return text.strip() + source_list


@lru_cache(maxsize=64)
def _cached_market_answer(question: str, passages_json: str, hour_bucket: int) -> str:
    """One-hour in-process cache: repeated identical reports do not spend another Sarvam call."""
    return generate_answer(question, json.loads(passages_json))

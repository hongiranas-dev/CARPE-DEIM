"""Evidence-first, deterministic market-research brief builder."""

from rag import retrieve


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

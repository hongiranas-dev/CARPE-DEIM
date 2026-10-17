"""Load sourced investor profiles and rank them with transparent rule-based scoring."""

import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CSV_PATH = ROOT / "data" / "investors.csv"
WEIGHTS = {"sector": 40, "stage": 25, "cheque": 20, "geography": 15}
STAGES = {
    "idea": 0,
    "pre-seed": 1,
    "preseed": 1,
    "seed": 2,
    "post-seed": 2.5,
    "pre-series a": 3,
    "series a": 4,
    "series b": 5,
    "growth": 6,
}
SECTOR_TERMS = {
    "Agriculture": ("agriculture", "agritech", "agrifood", "agri", "food", "farmer", "rural"),
    "Climate": ("climate", "cleantech", "sustainability", "energy", "environment"),
    "DeepTech / AI": ("deeptech", "deep tech", "deep science", "ai", "artificial intelligence", "quantum", "space", "robotics", "advanced materials", "digital infrastructure", "synthetic biology"),
    "Education": ("education", "edtech", "learning", "jobs"),
    "Fintech": ("fintech", "financial services", "financial inclusion", "finance"),
    "Health": ("health", "healthtech", "healthcare", "biotech", "medtech", "digital health", "diagnostics"),
    "SaaS / Enterprise": ("saas", "software", "enterprise", "b2b", "digital infrastructure", "smb digitization"),
    "Consumer / Commerce": ("consumer", "commerce", "marketplace", "brands", "d2c", "media", "social", "gaming"),
    "Mobility / EV": ("mobility", "ev", "electric vehicle", "transport"),
    "Other": (),
}


def load_investors(path: Path = CSV_PATH) -> list[dict]:
    required = {
        "name", "firm", "sectors", "cheque_min", "cheque_max", "currency", "cheque_size_range",
        "stage_min", "stage_max", "startup_stage", "past_investments", "geography", "website",
        "evidence_url", "investment_evidence_url", "eligibility_notes", "record_label",
    }
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not required.issubset(reader.fieldnames or []):
            raise ValueError("Investor CSV is missing required schema columns.")
        records = list(reader)
    for record in records:
        if record["record_label"] != "VERIFIED SAMPLE":
            raise ValueError(f"Investor record {record['name']} is not labeled as a verified sample.")
        if not record["evidence_url"].startswith("https://") or not record["website"].startswith("https://"):
            raise ValueError(f"Investor record {record['name']} is missing an HTTPS source or website.")
        for key in ("cheque_min", "cheque_max"):
            record[key] = float(record[key]) if record[key].strip() else None
    return records


def _stage_value(stage: str) -> float | None:
    normalized = stage.strip().lower().replace("preseed", "pre-seed")
    return STAGES.get(normalized)


def _sector_fit(startup_sector: str, record: dict) -> tuple[float, str]:
    tags = [tag.strip().lower() for tag in record["sectors"].split(";") if tag.strip()]
    if any("sector-agnostic" in tag for tag in tags):
        return 0.5, "The profile describes the investor as sector-agnostic."
    terms = SECTOR_TERMS.get(startup_sector, (startup_sector.lower(),))
    def normalized_words(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def overlaps(tag: str, term: str) -> bool:
        clean_tag = normalized_words(tag)
        clean_term = normalized_words(term)
        # Short labels such as "AI" or "EV" must match whole words only.
        if len(clean_term) <= 2:
            return clean_term in clean_tag.split()
        return clean_term in clean_tag or clean_tag in clean_term

    matches = [tag for tag in tags if any(overlaps(tag, term) for term in terms)]
    if matches:
        return 1.0, f"Published sector focus includes {', '.join(matches[:3])}."
    return 0.0, f"No published {startup_sector} focus matched this profile."


def _stage_fit(startup_stage: str, record: dict) -> tuple[float | None, str]:
    stage = _stage_value(startup_stage)
    minimum = _stage_value(record["stage_min"])
    maximum = _stage_value(record["stage_max"])
    if stage is None or minimum is None or maximum is None:
        return None, f"Stage compatibility is unscored; published stage: {record['startup_stage']}."
    if minimum <= stage <= maximum:
        return 1.0, f"{startup_stage} is within the published {record['startup_stage']} range."
    return 0.0, f"{startup_stage} falls outside the published {record['startup_stage']} range."


def _cheque_fit(ask: float | None, currency: str, record: dict) -> tuple[float | None, str]:
    if ask is None:
        return None, "Cheque compatibility is unscored because no funding ask was supplied."
    if record["cheque_min"] is None and record["cheque_max"] is None:
        return None, f"Cheque compatibility is unscored; {record['cheque_size_range']} is not published."
    if record["currency"].strip().lower() != currency.strip().lower():
        return None, f"Cheque compatibility is unscored; the profile uses {record['currency']} and no exchange rate is applied."
    minimum = record["cheque_min"]
    maximum = record["cheque_max"]
    fits = (minimum is None or ask >= minimum) and (maximum is None or ask <= maximum)
    if fits:
        return 1.0, f"Ask {ask:g} {currency} is within published range {record['cheque_size_range']} (where range bounds are stated)."
    return 0.0, f"Ask {ask:g} {currency} is outside published range {record['cheque_size_range']}."


def _geography_fit(startup_geography: str, record: dict) -> tuple[float | None, str]:
    founder_geo = startup_geography.strip().lower()
    firm_geo = record["geography"].strip().lower()
    countries = ("india", "global", "emerging asia", "sub-saharan africa")
    requested = next((country for country in countries if country in founder_geo), None)
    if requested is None:
        return None, "Geography is unscored; include a country (for example, ‘Pune, India’)."
    profile_regions = [region.strip().lower() for region in firm_geo.split(";")]
    if any(requested in region or (region == "india" and requested == "india") for region in profile_regions):
        return 1.0, f"The investor profile lists {requested.title()} as an investment geography."
    return 0.0, f"The investor profile does not list {requested.title()} as an investment geography."


def rank_investors(
    startup: dict,
    records: list[dict] | None = None,
    limit: int = 3,
) -> list[dict]:
    """Rank sourced profiles; unreported fields are omitted from the score, never guessed."""
    records = records if records is not None else load_investors()
    ranked = []
    for record in records:
        if "women ceo required" in record["eligibility_notes"].lower() and not startup.get("women_led", False):
            continue
        sector_score, sector_reason = _sector_fit(startup.get("sector", "Other"), record)
        stage_score, stage_reason = _stage_fit(startup.get("stage", ""), record)
        cheque_score, cheque_reason = _cheque_fit(startup.get("funding_amount"), startup.get("funding_currency", ""), record)
        geography_score, geography_reason = _geography_fit(startup.get("geography", ""), record)
        components = {"sector": sector_score, "stage": stage_score, "cheque": cheque_score, "geography": geography_score}
        included_weight = sum(WEIGHTS[key] for key, score in components.items() if score is not None)
        score = sum(WEIGHTS[key] * value for key, value in components.items() if value is not None) / included_weight if included_weight else 0.0
        ranked.append({
            **record,
            "score": round(score * 100, 1),
            "score_breakdown": components,
            "reasons": [sector_reason, stage_reason, cheque_reason, geography_reason],
        })
    return sorted(ranked, key=lambda item: (-item["score"], item["name"].lower()))[:limit]

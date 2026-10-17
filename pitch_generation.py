"""Deterministic personalized pitch drafts; does not invent traction or send email."""


def generate_pitch(startup: dict, investor: dict) -> dict:
    startup_name = startup.get("startup_name", "").strip() or "[Startup name]"
    founder_name = startup.get("founder_name", "").strip() or "[Founder name]"
    description = startup.get("description", "").strip() or "[Briefly describe the problem and your product]"
    sector = startup.get("sector", "startup")
    stage = startup.get("stage", "stage not specified")
    ask = startup.get("funding_amount")
    currency = startup.get("funding_currency", "")
    ask_line = f"We are exploring a raise of {ask:g} {currency}." if ask is not None and currency else ""
    traction = startup.get("traction", "").strip()
    traction_line = f"Current traction: {traction}" if traction else ""
    sectors = [item.strip() for item in investor["sectors"].split(";") if item.strip()]
    sector_reference = next((item for item in sectors if item.lower() not in ("sector-agnostic",)), sectors[0] if sectors else sector)
    stage_range = investor["startup_stage"] or "early-stage companies"
    past = [item.strip() for item in investor["past_investments"].split(";") if item.strip()]
    portfolio_line = f"I noticed your published portfolio includes {past[0]}." if past else ""
    body_lines = [
        f"Hello {investor['firm']} team,",
        "",
        f"I’m {founder_name}, founder of {startup_name}. We are building: {description}",
        f"We are currently at the {stage} stage in {sector}.",
        ask_line,
        traction_line,
        "",
        f"I’m reaching out because your published investment focus includes {sector_reference}, and your profile lists {stage_range} companies.",
        portfolio_line,
        "",
        "If this fits your current investment focus, would you be open to a short introductory conversation? I can share a concise deck and answer questions about the product, customer validation, and plan.",
        "",
        "Best,",
        founder_name,
    ]
    body = "\n".join(line for line in body_lines if line is not None)
    subject = f"{startup_name} — {sector} {stage} introduction"
    return {"to": "", "subject": subject, "body": body, "investor": investor["firm"], "sent": False}


def generate_pitches(startup: dict, matches: list[dict]) -> list[dict]:
    return [generate_pitch(startup, investor) for investor in matches]

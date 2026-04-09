"""
Lead scoring engine.

Two modes:
1. Rule-based (fast, deterministic) — used for all leads
2. Claude AI scoring (optional) — for ambiguous leads with moderate signals

Score 0–100:
  ≥ 55 → auto-call (voicebot)
  ≥ 20 → manual review queue
  <  20 → discard
"""
from __future__ import annotations

import json
import os

from loguru import logger

from src.persistence.models import ScoringResult

# Service area ZIPs (Hillsborough + adjacent)
TAMPA_ZIPS = {
    "33602", "33603", "33604", "33605", "33606", "33607", "33608", "33609",
    "33610", "33611", "33612", "33613", "33614", "33615", "33616", "33617",
    "33618", "33619", "33629", "33634", "33635", "33636", "33637", "33647",
    "33510", "33511", "33569", "33543", "33544",
}

IRRIGATION_KEYWORDS = [
    "irrigation", "sprinkler", "drip system", "water system",
    "lawn watering", "yard sprinkler",
]

CALL_THRESHOLD = int(os.getenv("SCORE_CALL_THRESHOLD", "55"))
REVIEW_THRESHOLD = int(os.getenv("SCORE_REVIEW_THRESHOLD", "20"))


def score_lead(lead: dict) -> ScoringResult:
    """
    Rule-based scorer. Fast and deterministic.
    lead dict must match the LeadRaw / Lead field names.
    """
    score = 0
    reasons: list[str] = []

    # --- SOURCE SIGNALS ---
    signal_type = lead.get("signal_type", "unknown")
    if signal_type == "new_construction":
        score += 40
        reasons.append("new construction permit (+40)")
    elif signal_type == "new_owner":
        score += 30
        reasons.append("new homeowner (+30)")
    elif signal_type == "complaint":
        score += 35
        reasons.append("competitor complaint (+35)")
    elif signal_type == "request":
        score += 25
        reasons.append("explicit service request (+25)")

    # --- KEYWORD SIGNALS ---
    signal_text = (lead.get("signal") or "").lower()
    if any(kw in signal_text for kw in IRRIGATION_KEYWORDS):
        score += 25
        reasons.append("irrigation keyword in signal (+25)")

    # --- LOCATION ---
    zip_code = (lead.get("zip_code") or "").strip()[:5]
    if zip_code in TAMPA_ZIPS:
        score += 10
        reasons.append("Tampa service area (+10)")
    elif zip_code:
        score -= 20
        reasons.append("outside service area (−20)")

    # --- CONTACT INFO ---
    if lead.get("phone"):
        score += 10
        reasons.append("has phone (+10)")
    else:
        score -= 30
        reasons.append("no phone (−30)")

    if lead.get("email"):
        score += 5
        reasons.append("has email (+5)")

    # --- PROPERTY TYPE ---
    if lead.get("property_type") == "commercial":
        score += 15
        reasons.append("commercial property (+15)")

    # --- CAP ---
    score = max(0, min(100, score))

    if score >= CALL_THRESHOLD:
        action = "call"
    elif score >= REVIEW_THRESHOLD:
        action = "review"
    else:
        action = "discard"

    return ScoringResult(
        score=score,
        reason="; ".join(reasons) if reasons else "no signals",
        action=action,
    )


def claude_score_lead(lead: dict) -> dict:
    """
    AI-based scoring for ambiguous leads.
    Calls OpenAI API and returns enriched scoring dict.
    Only use when rule-based score is in the 30–55 range.
    """
    try:
        import openai  # lazy import — not required for rule-based path

        client = openai.OpenAI()
        prompt = f"""You are a lead quality analyst for Green Landscape Irrigation in Tampa, FL.
The company specializes in irrigation system installation and sprinkler repair for residential properties.

Analyze this lead and return a JSON object with:
- score: integer 0-100
- intent: "irrigation" | "landscaping" | "unknown"
- urgency: "high" | "medium" | "low"
- property_type: "residential" | "commercial" | "unknown"
- recommendation: "call" | "review" | "discard"
- reason: one sentence explanation

Lead signal: "{lead.get('signal', 'N/A')}"
Source: {lead.get('source', 'N/A')}
Address: {lead.get('address', 'N/A')}, {lead.get('zip_code', 'N/A')}
Signal type: {lead.get('signal_type', 'unknown')}

Return ONLY valid JSON, no markdown or extra text."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(response.choices[0].message.content)

    except Exception as exc:
        logger.warning(f"Claude scoring failed, falling back to rule-based: {exc}")
        result = score_lead(lead)
        return {
            "score": result.score,
            "intent": "unknown",
            "urgency": "medium",
            "property_type": lead.get("property_type", "unknown"),
            "recommendation": result.action,
            "reason": result.reason,
        }

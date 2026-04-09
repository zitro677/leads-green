"""
Phone number enrichment for leads that have an address + owner name but no phone.

Strategy (in order of cost/reliability):
1. SerpAPI Google search — "{owner_name} {city} FL phone" → extract US numbers from results
2. NumLookup validate — confirm any found number is real/active before storing
3. Skip — lead stays at REVIEW score, flagged for manual lookup

After enrichment, leads with a phone are re-scored and may cross the 55 threshold
to be queued for Jimmy to call.
"""
from __future__ import annotations

import os
import re
import time

import httpx
from loguru import logger

from src.persistence.client import get_supabase, update_lead
from src.pipeline.scorer import score_lead

CALL_THRESHOLD = int(os.getenv("SCORE_CALL_THRESHOLD", "55"))

# US phone number pattern — matches (813) 555-1234, 813-555-1234, +18135551234, etc.
_PHONE_RE = re.compile(
    r"\+?1?[-.\s]?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})"
)

# Tampa/Hillsborough area codes
AREA_CODES = {"813", "727", "941", "863"}


def _search_phone_serpapi(name: str, city: str) -> str | None:
    """Search Google via SerpAPI for a person's phone number."""
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        logger.debug("[phone_lookup] SERPAPI_KEY not set — skipping SerpAPI search")
        return None

    query = f'"{name}" "{city}" FL phone'
    try:
        resp = httpx.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": api_key, "num": 5, "gl": "us"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"[phone_lookup] SerpAPI returned {resp.status_code}")
            return None

        data = resp.json()

        # Look for phone numbers in organic results snippets + titles
        text_blobs = []
        for result in data.get("organic_results", []):
            text_blobs.append(result.get("snippet", ""))
            text_blobs.append(result.get("title", ""))

        # Also check answer box and knowledge graph
        if data.get("answer_box"):
            text_blobs.append(str(data["answer_box"]))

        all_text = " ".join(text_blobs)
        phones = _PHONE_RE.findall(all_text)

        for area, prefix, line in phones:
            if area in AREA_CODES:
                number = f"+1{area}{prefix}{line}"
                logger.info(f"[phone_lookup] SerpAPI found local phone for '{name}': {number}")
                return number

        # Accept any US number if no local one found
        if phones:
            area, prefix, line = phones[0]
            number = f"+1{area}{prefix}{line}"
            logger.info(f"[phone_lookup] SerpAPI found phone for '{name}': {number}")
            return number

    except Exception as exc:
        logger.warning(f"[phone_lookup] SerpAPI search failed for '{name}': {exc}")

    return None


def validate_phone_numlookup(phone: str) -> bool:
    """
    Validate a phone number is real/active using NumLookup.
    Returns True if valid (or if NumLookup key not set — fail open).
    """
    api_key = os.getenv("NUMLOOKUP_API_KEY")
    if not api_key:
        return True  # fail open — don't block if key missing

    try:
        resp = httpx.get(
            f"https://api.numlookupapi.com/v1/validate/{phone}",
            params={"apikey": api_key},
            timeout=8,
        )
        if resp.status_code != 200:
            return True  # fail open on API error

        data = resp.json()
        is_valid = data.get("valid", False)
        country = data.get("country_code", "")

        if not is_valid or country != "US":
            logger.debug(f"[phone_lookup] NumLookup: {phone} invalid or non-US")
            return False

        logger.debug(f"[phone_lookup] NumLookup: {phone} validated OK")
        return True

    except Exception as exc:
        logger.warning(f"[phone_lookup] NumLookup validation error for {phone}: {exc}")
        return True  # fail open


def enrich_phone_for_lead(lead: dict) -> str | None:
    """
    Try to find a phone number for a lead that has a name + address.
    Strategy: voter DB first (free, instant), then SerpAPI (costs quota).
    Returns the phone number string if found and validated, None otherwise.
    """
    name = (lead.get("name") or "").strip()
    city = (lead.get("city") or "Tampa").strip()
    zip_code = (lead.get("zip_code") or "").strip()

    if not name:
        logger.debug("[phone_lookup] No owner name — skipping")
        return None

    # 1. Try voter file DB first (free, no quota)
    try:
        from src.pipeline.voter_db import lookup_phone, DB_PATH
        if DB_PATH.exists():
            phone = lookup_phone(name, zip_code)
            if phone:
                logger.info(f"[phone_lookup] Voter DB match for '{name}': {phone}")
                return phone
    except Exception as exc:
        logger.debug(f"[phone_lookup] Voter DB lookup failed: {exc}")

    # 2. Fall back to SerpAPI Google search
    phone = _search_phone_serpapi(name, city)
    if not phone:
        return None

    # Validate with NumLookup before returning
    if not validate_phone_numlookup(phone):
        logger.debug(f"[phone_lookup] Phone {phone} failed validation — discarding")
        return None

    return phone


def run_phone_enrichment(limit: int = 50, delay: float = 1.5) -> dict:
    """
    Batch enrich review leads that have no phone number.
    Pulls leads with status='new' and score between 20-54, tries to find phone,
    re-scores, and updates status to 'queued' if score crosses threshold.

    Args:
        limit: max leads to enrich per run (API quota management)
        delay: seconds between API calls (rate limiting)

    Returns summary dict.
    """
    sb = get_supabase()

    result = (
        sb.table("leads")
        .select("*")
        .eq("status", "new")
        .is_("phone", "null")
        .gte("score", 20)
        .lt("score", CALL_THRESHOLD)
        .not_.is_("name", "null")
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )

    leads = result.data
    logger.info(f"[phone_lookup] Enriching {len(leads)} review leads with no phone")

    enriched = 0
    upgraded = 0
    skipped = 0

    for lead in leads:
        phone = enrich_phone_for_lead(lead)

        if not phone:
            skipped += 1
            time.sleep(delay)
            continue

        enriched += 1

        # Re-score with phone
        lead_with_phone = {**lead, "phone": phone}
        new_scoring = score_lead(lead_with_phone)

        update_fields = {
            "phone": phone,
            "score": new_scoring.score,
            "score_reason": new_scoring.reason,
        }

        if new_scoring.action == "call":
            update_fields["status"] = "queued"
            upgraded += 1
            logger.success(
                f"[phone_lookup] Lead {lead['id'][:8]} upgraded to CALL "
                f"score={new_scoring.score} phone={phone}"
            )
        else:
            logger.info(
                f"[phone_lookup] Lead {lead['id'][:8]} phone found but score "
                f"still {new_scoring.score} — stays in REVIEW"
            )

        update_lead(lead["id"], update_fields)
        time.sleep(delay)

    summary = {
        "processed": len(leads),
        "enriched": enriched,
        "upgraded_to_call": upgraded,
        "skipped": skipped,
    }
    logger.info(f"[phone_lookup] Done: {summary}")
    return summary


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    result = run_phone_enrichment(limit=20)
    print(
        f"\nPhone enrichment complete:\n"
        f"  Processed:        {result['processed']}\n"
        f"  Found phone:      {result['enriched']}\n"
        f"  Upgraded to call: {result['upgraded_to_call']}\n"
        f"  No phone found:   {result['skipped']}\n"
    )

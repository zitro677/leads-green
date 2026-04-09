"""
Email enrichment — finds email addresses for leads using SerpAPI Google search.

Strategy: search for "{owner_name}" "{city}" FL email
Extracts email-like patterns from organic results.

Note: residential homeowner emails are hard to find (~15-25% hit rate).
Commercial/LLC leads have better coverage (~40%).
"""
from __future__ import annotations

import os
import re
import time

import httpx
from loguru import logger

from src.persistence.client import get_supabase, update_lead

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Block generic/spam emails
_BLOCKLIST = {
    "example.com", "test.com", "noreply.com", "donotreply.com",
    "zillow.com", "redfin.com", "realtor.com", "hcpafl.org",
    "hillsboroughcounty.org", "gmail.com",  # too common, likely wrong
}


def _is_valid_email(email: str) -> bool:
    domain = email.split("@")[-1].lower()
    return domain not in _BLOCKLIST and len(email) < 80


def find_email_serpapi(name: str, city: str) -> str | None:
    api_key = os.getenv("SERPAPI_KEY")
    if not api_key:
        return None

    query = f'"{name}" "{city}" FL email contact'
    try:
        resp = httpx.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": api_key, "num": 5, "gl": "us"},
            timeout=15,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        text_blobs = []
        for r in data.get("organic_results", []):
            text_blobs.append(r.get("snippet", ""))
            text_blobs.append(r.get("title", ""))
        if data.get("answer_box"):
            text_blobs.append(str(data["answer_box"]))

        all_text = " ".join(text_blobs)
        emails = _EMAIL_RE.findall(all_text)

        for email in emails:
            if _is_valid_email(email):
                logger.info(f"[email_lookup] Found email for '{name}': {email}")
                return email.lower()

    except Exception as exc:
        logger.warning(f"[email_lookup] SerpAPI search failed for '{name}': {exc}")

    return None


def run_email_enrichment(limit: int = 30, delay: float = 2.0) -> dict:
    """
    Batch enrich leads that have no email.
    Uses SerpAPI — respect free tier quota (100/month).
    """
    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("id,name,city,zip_code,email")
        .is_("email", "null")
        .not_.is_("name", "null")
        .in_("status", ["new", "queued"])
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )

    leads = result.data
    logger.info(f"[email_lookup] Enriching {len(leads)} leads for email")

    found = 0
    skipped = 0

    for lead in leads:
        name = (lead.get("name") or "").strip()
        city = (lead.get("city") or "Tampa").strip()

        email = find_email_serpapi(name, city)
        if email:
            update_lead(lead["id"], {"email": email})
            found += 1
        else:
            skipped += 1

        time.sleep(delay)

    summary = {"processed": len(leads), "found": found, "not_found": skipped}
    logger.info(f"[email_lookup] Done: {summary}")
    return summary


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    result = run_email_enrichment(limit=10)
    print(f"\nEmail enrichment: found={result['found']} / {result['processed']} leads")

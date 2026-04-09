"""
Facebook Groups scraper — finds homeowners in Tampa/Spring Hill area
posting about irrigation needs, sprinkler problems, or lawn work.

Uses Apify's Facebook Posts Scraper actor to pull posts from targeted
local Facebook groups, then filters by irrigation-related keywords.

Apify actor: apify/facebook-posts-scraper
Docs: https://apify.com/apify/facebook-posts-scraper
"""
from __future__ import annotations

import os
import re
import time

import httpx
from loguru import logger

from src.persistence.models import LeadRaw
from src.scrapers.base import BaseScraper

APIFY_BASE = "https://api.apify.com/v2"
ACTOR_ID = "apify~facebook-posts-scraper"

# Tampa Bay + Spring Hill / Hernando County Facebook groups (public)
TARGET_GROUPS = [
    "https://www.facebook.com/groups/tampahomeowners/",
    "https://www.facebook.com/groups/tampabayhomeimprovement/",
    "https://www.facebook.com/groups/springhillflresidents/",
    "https://www.facebook.com/groups/hernandocountyhomeowners/",
    "https://www.facebook.com/groups/tampaneighborhood/",
    "https://www.facebook.com/groups/newportricheyfl/",
    "https://www.facebook.com/groups/wesleyChapelFL/",
    "https://www.facebook.com/groups/landolakesfl/",
    "https://www.facebook.com/groups/lutzflorida/",
    "https://www.facebook.com/groups/brandon.florida/",
    "https://www.facebook.com/groups/riverviewflorida/",
    "https://www.facebook.com/groups/apollobeachfl/",
    "https://www.facebook.com/groups/suncoasthoa/",
]

# Keywords that signal irrigation intent — any post containing one of these is a lead
INTENT_KEYWORDS = [
    "irrigation repair",
    "irrigation install",
    "irrigation system",
    "sprinkler repair",
    "sprinkler install",
    "sprinkler system",
    "sprinkler head",
    "broken sprinkler",
    "fix sprinkler",
    "lawn sprinkler",
    "drip irrigation",
    "irrigation controller",
    "irrigation timer",
    "irrigation company",
    "irrigation contractor",
    "sprinkler company",
    "sprinkler contractor",
    "recommend irrigation",
    "recommend sprinkler",
    "need irrigation",
    "need sprinkler",
    "looking for irrigation",
    "looking for sprinkler",
    "who does irrigation",
    "who does sprinkler",
    "lawn care recommend",
    "landscape recommend",
]

# Patterns to try extracting a phone number from post text
_PHONE_RE = re.compile(r"\b(\+?1?\s*[-.]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b")

# Patterns to detect addresses in post text
_ADDRESS_RE = re.compile(
    r"\b\d{3,5}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:St|Ave|Blvd|Dr|Rd|Ln|Ct|Way|Pl|Cir)\b",
    re.IGNORECASE,
)


def _contains_keyword(text: str) -> str | None:
    """Return the first matching keyword found in text, or None."""
    lower = text.lower()
    for kw in INTENT_KEYWORDS:
        if kw in lower:
            return kw
    return None


def _extract_phone(text: str) -> str | None:
    match = _PHONE_RE.search(text)
    if not match:
        return None
    raw = re.sub(r"[\s().-]", "", match.group(1))
    if raw.startswith("1") and len(raw) == 11:
        raw = raw[1:]
    if len(raw) == 10:
        return f"+1{raw}"
    return None


def _extract_address(text: str) -> str | None:
    match = _ADDRESS_RE.search(text)
    return match.group(0) if match else None


class FacebookGroupsScraper(BaseScraper):
    source = "facebook_groups"
    request_delay = 2.0

    def __init__(self, max_posts_per_group: int = 50, days_back: int = 7):
        self.max_posts_per_group = max_posts_per_group
        self.days_back = days_back

    def scrape(self) -> list[LeadRaw]:
        token = os.getenv("APIFY_TOKEN")
        if not token:
            raise RuntimeError("APIFY_TOKEN not set in .env")

        headers = {"Authorization": f"Bearer {token}"}

        # Start the Apify actor run
        run_id, dataset_id = self._start_run(headers)
        if not run_id:
            return []

        # Poll until done (max 10 minutes)
        if not self._wait_for_run(run_id, headers, timeout=600):
            logger.warning("[facebook_groups] Apify run timed out — no leads collected")
            return []

        # Fetch results and parse
        items = self._fetch_dataset(dataset_id, headers)
        return self._parse_items(items)

    def _start_run(self, headers: dict) -> tuple[str | None, str | None]:
        payload = {
            "startUrls": [{"url": g} for g in TARGET_GROUPS],
            "maxPosts": self.max_posts_per_group,
            "maxPostDate": None,
            "scrapeAbout": False,
            "scrapeReviews": False,
            "scrapePosts": True,
            "scrapeComments": False,
        }
        try:
            resp = httpx.post(
                f"{APIFY_BASE}/acts/{ACTOR_ID}/runs",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            run_id = data.get("id")
            dataset_id = data.get("defaultDatasetId")
            logger.info(f"[facebook_groups] Apify run started: {run_id}")
            return run_id, dataset_id
        except Exception as exc:
            logger.error(f"[facebook_groups] Failed to start Apify run: {exc}")
            return None, None

    def _wait_for_run(self, run_id: str, headers: dict, timeout: int = 600) -> bool:
        deadline = time.time() + timeout
        poll_interval = 15
        while time.time() < deadline:
            try:
                resp = httpx.get(
                    f"{APIFY_BASE}/actor-runs/{run_id}",
                    headers=headers,
                    timeout=15,
                )
                resp.raise_for_status()
                status = resp.json().get("data", {}).get("status")
                logger.debug(f"[facebook_groups] Run {run_id} status: {status}")
                if status == "SUCCEEDED":
                    return True
                if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.error(f"[facebook_groups] Run ended with status: {status}")
                    return False
            except Exception as exc:
                logger.warning(f"[facebook_groups] Poll error: {exc}")
            time.sleep(poll_interval)
        return False

    def _fetch_dataset(self, dataset_id: str, headers: dict) -> list[dict]:
        try:
            resp = httpx.get(
                f"{APIFY_BASE}/datasets/{dataset_id}/items",
                headers=headers,
                params={"format": "json", "limit": 2000},
                timeout=30,
            )
            resp.raise_for_status()
            items = resp.json()
            logger.info(f"[facebook_groups] Fetched {len(items)} posts from Apify")
            return items
        except Exception as exc:
            logger.error(f"[facebook_groups] Failed to fetch dataset: {exc}")
            return []

    def _parse_items(self, items: list[dict]) -> list[LeadRaw]:
        leads = []
        for item in items:
            lead = self._parse_post(item)
            if lead:
                leads.append(lead)
        logger.info(f"[facebook_groups] {len(leads)} irrigation-intent posts found")
        return leads

    def _parse_post(self, post: dict) -> LeadRaw | None:
        text = post.get("text") or post.get("postText") or ""
        if not text:
            return None

        keyword = _contains_keyword(text)
        if not keyword:
            return None

        # Extract what we can from the post
        author = post.get("authorName") or post.get("pageName") or "Facebook User"
        post_url = post.get("url") or post.get("postUrl") or ""
        group_name = post.get("groupName") or "Facebook Group"
        phone = _extract_phone(text)
        address = _extract_address(text)

        # Use post URL as a proxy address if no physical address found
        display_address = address or f"Facebook post — {group_name}"

        signal = f'"{keyword}" — {text[:120].strip()}...' if len(text) > 120 else f'"{keyword}" — {text.strip()}'

        return self._make_lead(
            source_id=post_url or None,
            name=author,
            phone=phone,
            address=display_address,
            city="Tampa",
            signal=signal,
            signal_type="request",
            property_type="residential",
            raw_json={
                "post_text": text[:500],
                "post_url": post_url,
                "group": group_name,
                "keyword_matched": keyword,
            },
        )

"""
Zillow new listings scraper for Tampa Bay area.

Strategy:
- Scrape Zillow's public search pages for recently listed homes in target ZIPs
- Uses Playwright to render JS-heavy Zillow pages
- New listings (< 30 days) = new homeowners who may need irrigation

Note: SerpAPI Zillow engine requires a paid plan. This implementation
scrapes Zillow directly using Playwright as a free alternative.
Respect rate limits — 1 ZIP per 3 seconds max.

Upgrade path: Set SERPAPI_KEY with a paid plan and set USE_SERPAPI=true
in .env to switch to the API-based approach (more reliable, costs ~$50/mo).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from src.persistence.models import LeadRaw
from src.scrapers.base import BaseScraper

# Tampa Bay ZIPs to search
TARGET_ZIPS = [
    "33602", "33603", "33606", "33609", "33611", "33629",
    "33634", "33647", "33510", "33511", "33569",
]

# Zillow search URL template
ZILLOW_SEARCH_URL = "https://www.zillow.com/homes/for_sale/{zip_code}_rb/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class ZillowScraper(BaseScraper):
    source = "zillow"
    request_delay = 3.0  # polite delay between ZIPs

    def __init__(self, max_zips: int = 5, days_listed: int = 30):
        self.max_zips = max_zips
        self.days_listed = days_listed

    def scrape(self) -> list[LeadRaw]:
        leads: list[LeadRaw] = []
        zips_to_search = TARGET_ZIPS[: self.max_zips]

        for zip_code in zips_to_search:
            logger.debug(f"[{self.source}] Searching ZIP {zip_code}")
            try:
                batch = self._scrape_zip(zip_code)
                leads.extend(batch)
                logger.debug(f"[{self.source}] ZIP {zip_code}: {len(batch)} leads")
            except Exception as exc:
                logger.warning(f"[{self.source}] ZIP {zip_code} failed: {exc}")
            self._sleep()

        return leads

    def _scrape_zip(self, zip_code: str) -> list[LeadRaw]:
        url = ZILLOW_SEARCH_URL.format(zip_code=zip_code)
        resp = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)

        if resp.status_code == 403:
            logger.warning(
                f"[{self.source}] Zillow returned 403 for {zip_code} — "
                "consider using Playwright or upgrading SerpAPI plan"
            )
            return []

        resp.raise_for_status()
        return self._parse_page(resp.text, zip_code)

    def _parse_page(self, html: str, zip_code: str) -> list[LeadRaw]:
        """
        Extract listing data from Zillow's embedded JSON (__NEXT_DATA__).
        Zillow embeds all search results as JSON in a script tag.
        """
        soup = BeautifulSoup(html, "lxml")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if not script:
            logger.warning(f"[{self.source}] No __NEXT_DATA__ found — Zillow may have blocked request")
            return []

        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            return []

        # Navigate Zillow's JSON structure to find listings
        try:
            results = (
                data["props"]["pageProps"]["searchPageState"]
                ["cat1"]["searchResults"]["listResults"]
            )
        except (KeyError, TypeError):
            logger.warning(f"[{self.source}] Unexpected Zillow JSON structure for {zip_code}")
            return []

        leads = []
        for listing in results:
            lead = self._parse_listing(listing, zip_code)
            if lead:
                leads.append(lead)

        return leads

    def _parse_listing(self, listing: dict[str, Any], zip_code: str) -> LeadRaw | None:
        days_on = listing.get("daysOnZillow", 999)
        if days_on > self.days_listed:
            return None

        address = listing.get("address", "")
        if not address:
            return None

        zpid = str(listing.get("zpid", ""))
        price = listing.get("price", "")
        beds = listing.get("beds", "")
        baths = listing.get("baths", "")
        area = listing.get("area", "")

        signal = (
            f"New listing {days_on}d ago — {beds}bd/{baths}ba {area}sqft "
            f"at {price}. New homeowner likely needs irrigation assessment."
        )

        return self._make_lead(
            source_id=zpid or None,
            address=address,
            zip_code=zip_code,
            city="Tampa",
            signal=signal,
            signal_type="new_owner",
            property_type="residential",
            raw_json=listing,
        )

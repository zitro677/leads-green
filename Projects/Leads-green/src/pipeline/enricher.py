"""
Lead enrichment.

Currently enriches:
- Phone normalization (E.164 format)
- Address → lat/lon geocoding (via US Census Geocoding API — free)
- Property type inference from address/signal

Future:
- Reverse phone lookup (Numverify / Whitepages API)
- Owner name from county property appraiser API
"""
from __future__ import annotations

import urllib.parse

import httpx
from loguru import logger

from src.persistence.models import LeadRaw
from src.pipeline.dedup import normalize_phone

# Free US Census Geocoding API — no key required
CENSUS_GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"


def enrich(lead: LeadRaw) -> dict:
    """
    Takes a LeadRaw and returns a dict of enrichment fields to merge
    into the DB row before insert.
    """
    enriched: dict = {}

    # --- Phone normalization ---
    if lead.phone:
        normed = normalize_phone(lead.phone)
        if normed:
            enriched["phone"] = normed

    # --- Geocoding ---
    coords = geocode_address(f"{lead.address}, {lead.city}, FL {lead.zip_code or ''}")
    if coords:
        enriched["lat"], enriched["lon"] = coords

    return enriched


def geocode_address(address: str) -> tuple[float, float] | None:
    """
    Returns (lat, lon) or None if geocoding fails.
    Uses US Census Bureau Geocoding API (free, no key).
    """
    try:
        params = {
            "address": address,
            "benchmark": "Public_AR_Current",
            "format": "json",
        }
        resp = httpx.get(CENSUS_GEOCODE_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            return None

        coords = matches[0]["coordinates"]
        return float(coords["y"]), float(coords["x"])  # lat, lon

    except Exception as exc:
        logger.warning(f"[enricher] Geocoding failed for '{address}': {exc}")
        return None

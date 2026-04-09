"""
Hillsborough County Building Permits scraper.

Data source: Hillsborough County ArcGIS PermitsPlus FeatureServer (public).
Endpoint: PermitsPlus/ResidentialCommericalIssuedPermitsCertOccMapService/FeatureServer/0

Confirmed fields (from ArcGIS metadata):
  PERMIT__     — Permit number
  Issued       — Issue date (Unix ms timestamp)
  ADDRESS      — Street address
  CITY_1       — City / ZIP (combined string e.g. "TAMPA 33611")
  PERMIT_TYPE  — Permit type
  JOB_TITLE    — Work description
  STATUS_1     — Permit status

Strategy:
- Pull permits issued in the last N days
- Filter for new construction types that do NOT mention irrigation
- These represent properties that will need irrigation installed
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from src.persistence.models import LeadRaw
from src.scrapers.base import BaseScraper

PERMITS_API = (
    "https://maps.hillsboroughcounty.org/arcgis/rest/services/"
    "PermitsPlus/ResidentialCommericalIssuedPermitsCertOccMapService/"
    "FeatureServer/0/query"
)

# PERMIT_TYPE values to accept (actual values from the ArcGIS layer)
ACCEPTED_PERMIT_TYPES = {"RESIDENTIAL", "COMMERCIAL"}

# JOB_TITLE keywords that suggest new construction (higher score signal)
NEW_CONSTRUCTION_KEYWORDS = [
    "new", "construction", "addition", "build", "dwelling",
    "single family", "duplex", "multi", "install",
]

# If JOB_TITLE contains these, irrigation is already included — skip
IRRIGATION_EXCLUSION_TERMS = ["irrigation", "sprinkler", "drip system"]

# Target service area ZIPs (Hillsborough County)
TARGET_ZIPS = {
    "33602", "33603", "33604", "33605", "33606", "33607", "33608", "33609",
    "33610", "33611", "33612", "33613", "33614", "33615", "33616", "33617",
    "33618", "33619", "33629", "33634", "33635", "33636", "33637", "33647",
    "33510", "33511", "33569", "33543", "33544",
}


class HillsboroughPermitsScraper(BaseScraper):
    source = "hillsborough_permits"
    request_delay = 0.5

    def __init__(self, days_back: int = 7):
        self.days_back = days_back

    def scrape(self) -> list[LeadRaw]:
        since_str = (datetime.utcnow() - timedelta(days=self.days_back)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        params = {
            "where": f"Issued >= TIMESTAMP '{since_str}'",
            "outFields": "PERMIT__,Issued,ADDRESS,CITY_1,PERMIT_TYPE,JOB_TITLE,STATUS_1,CLASS",
            "returnGeometry": "false",
            "resultRecordCount": 2000,
            "orderByFields": "Issued DESC",
            "f": "json",
        }

        logger.debug(f"[{self.source}] Fetching permits (last {self.days_back} days)")
        resp = httpx.get(PERMITS_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        # ArcGIS returns an "error" key when the query fails
        if "error" in data:
            raise RuntimeError(f"ArcGIS error: {data['error']}")

        features = data.get("features", [])
        logger.debug(f"[{self.source}] Raw permits fetched: {len(features)}")

        # Log actual PERMIT_TYPE values so we can tune the filter
        seen_types = {f.get("attributes", {}).get("PERMIT_TYPE", "N/A") for f in features}
        logger.debug(f"[{self.source}] PERMIT_TYPE values in response: {seen_types}")

        leads = []
        for feature in features:
            lead = self._parse_permit(feature.get("attributes", {}))
            if lead:
                leads.append(lead)

        return leads

    def _parse_permit(self, attrs: dict) -> LeadRaw | None:
        permit_type = (attrs.get("PERMIT_TYPE") or "").upper().strip()
        job_title = (attrs.get("JOB_TITLE") or "").lower().strip()
        city_zip = (attrs.get("CITY_1") or "").strip()  # e.g. "TAMPA 33611"

        # Extract ZIP from the combined CITY_1 field
        parts = city_zip.split()
        zip_code = parts[-1] if parts and parts[-1].isdigit() and len(parts[-1]) == 5 else None
        city = " ".join(parts[:-1]) if zip_code else city_zip

        # Accept residential and commercial permits
        if permit_type not in ACCEPTED_PERMIT_TYPES:
            logger.debug(f"[{self.source}] Skipping unknown PERMIT_TYPE: '{permit_type}'")
            return None

        # Skip if outside service area
        if zip_code and zip_code not in TARGET_ZIPS:
            return None

        # Skip if irrigation already included
        if any(term in job_title for term in IRRIGATION_EXCLUSION_TERMS):
            return None

        address = (attrs.get("ADDRESS") or "").strip()
        if not address:
            return None

        permit_num = str(attrs.get("PERMIT__") or "").strip()
        signal = f"{permit_type} permit — {job_title} (#{permit_num})"

        # Determine signal_type from JOB_TITLE keywords
        is_new = any(kw in job_title for kw in NEW_CONSTRUCTION_KEYWORDS)
        signal_type = "new_construction" if is_new else "request"

        return self._make_lead(
            source_id=permit_num or None,
            address=f"{address}, {city_zip}",
            city=city or "Tampa",
            zip_code=zip_code,
            signal=signal,
            signal_type=signal_type,
            property_type="commercial" if permit_type == "COMMERCIAL" else "residential",
            raw_json=attrs,
        )

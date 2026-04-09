"""
Hillsborough County Property Appraiser — New Deed Recordings scraper.

A recorded deed = a confirmed property transfer = a new homeowner.
This is a BETTER signal than Zillow listings because:
  - The sale is complete (not just listed)
  - The new owner physically has the property
  - Public record — no scraping restrictions

Data source: Hillsborough County Property Appraiser ArcGIS REST API
  https://www.hcpafl.org (Property Appraiser)

ArcGIS services: https://maps.hillsboroughcounty.org/arcgis/rest/services/
We use the InfoLayers/HC_Parcels layer which has sale date + owner info.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import httpx
from loguru import logger

from src.persistence.models import LeadRaw
from src.scrapers.base import BaseScraper

# Hillsborough County Parcels — includes recent sale dates and owner info
PARCELS_API = (
    "https://maps.hillsboroughcounty.org/arcgis/rest/services/"
    "InfoLayers/HC_Parcels/MapServer/0/query"
)

# Target service area ZIPs
TARGET_ZIPS = {
    "33602", "33603", "33604", "33605", "33606", "33607", "33608", "33609",
    "33610", "33611", "33612", "33613", "33614", "33615", "33616", "33617",
    "33618", "33619", "33629", "33634", "33635", "33636", "33637", "33647",
    "33510", "33511", "33569", "33543", "33544",
}

# Only residential property classes
RESIDENTIAL_CLASSES = {"SINGLE FAMILY", "RESIDENTIAL", "CONDOMINIUM", "TOWNHOUSE"}


class NewOwnersScraper(BaseScraper):
    source = "new_owners"
    request_delay = 1.0

    def __init__(self, days_back: int = 30):
        self.days_back = days_back

    def scrape(self) -> list[LeadRaw]:
        since_str = (datetime.utcnow() - timedelta(days=self.days_back)).strftime(
            "%Y-%m-%d"
        )

        # Query parcels where sale date is recent (field: S_DATE)
        params = {
            "where": f"S_DATE >= TIMESTAMP '{since_str} 00:00:00'",
            "outFields": (
                "FOLIO,OWNER,ADDR_1,ADDR_2,CITY,STATE,ZIP,"
                "SITE_ADDR,SITE_CITY,SITE_ZIP,"
                "S_DATE,S_AMT,DOR_CODE,LU_GRP,TYPE,"
                "tBEDS,tBATHS"
            ),
            "returnGeometry": "false",
            "resultRecordCount": 2000,
            "orderByFields": "S_DATE DESC",
            "f": "json",
        }

        logger.debug(f"[{self.source}] Fetching new deeds since {since_str}")
        resp = httpx.get(PARCELS_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if "error" in data:
            raise RuntimeError(f"ArcGIS error: {data['error']}")

        features = data.get("features", [])
        logger.debug(f"[{self.source}] Raw deed transfers fetched: {len(features)}")

        # Log land use groups seen for tuning
        classes = {f.get("attributes", {}).get("LU_GRP", "N/A") for f in features}
        logger.debug(f"[{self.source}] LU_GRP values: {classes}")

        leads = []
        for feature in features:
            lead = self._parse_deed(feature.get("attributes", {}))
            if lead:
                leads.append(lead)

        return leads

    def _parse_deed(self, attrs: dict[str, Any]) -> LeadRaw | None:
        site_zip = str(attrs.get("SITE_ZIP") or attrs.get("ZIP") or "").strip()[:5]
        lu_grp = (attrs.get("LU_GRP") or attrs.get("TYPE") or "").upper()

        # Filter to service area
        if site_zip and site_zip not in TARGET_ZIPS:
            return None

        # Filter to residential only
        is_residential = any(rc in lu_grp for rc in RESIDENTIAL_CLASSES)
        if not is_residential:
            return None

        address = (attrs.get("SITE_ADDR") or attrs.get("ADDR_1") or "").strip()
        if not address:
            return None

        owner = (attrs.get("OWNER") or "").strip()
        sale_date = attrs.get("S_DATE", "")
        sale_amt = attrs.get("S_AMT", 0)
        folio = str(attrs.get("FOLIO") or "").strip()
        site_city = attrs.get("SITE_CITY") or attrs.get("CITY") or "Tampa"

        # Format sale date (ArcGIS returns Unix ms)
        sale_date_str = ""
        if isinstance(sale_date, (int, float)) and sale_date > 0:
            sale_date_str = datetime.utcfromtimestamp(sale_date / 1000).strftime("%Y-%m-%d")

        beds = attrs.get("tBEDS", "")
        baths = attrs.get("tBATHS", "")
        home_info = f"{int(beds)}bd/{int(baths)}ba" if beds and baths else ""

        signal = (
            f"New homeowner — deed recorded {sale_date_str}"
            + (f", sale ${int(sale_amt):,}" if sale_amt else "")
            + (f", {home_info}" if home_info else "")
            + f". Property type: {lu_grp}. Likely needs irrigation assessment."
        )

        # Owner-occupied = mailing ZIP matches site ZIP (better lead quality)
        mailing_zip = str(attrs.get("ZIP") or "").strip()[:5]
        is_owner_occupied = mailing_zip == site_zip

        return self._make_lead(
            source_id=folio or None,
            name=owner or None,
            address=f"{address}, {site_city} FL {site_zip}",
            city=site_city,
            zip_code=site_zip or None,
            signal=signal,
            signal_type="new_owner",
            property_type="residential",
            raw_json={**attrs, "owner_occupied": is_owner_occupied},
        )

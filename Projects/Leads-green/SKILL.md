# SKILL: Lead Scraper Development

## Purpose
Guide Claude to add, modify, or debug lead scrapers for Green Landscape Irrigation.

## Scraper Interface Contract

Every scraper must implement this interface:

```python
# src/scrapers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterator

@dataclass
class LeadRaw:
    source: str
    source_id: str
    name: str | None
    phone: str | None
    email: str | None
    address: str
    city: str
    zip_code: str
    signal: str          # raw text that indicates intent
    signal_type: str     # "new_construction" | "new_owner" | "complaint" | "request"
    scraped_at: datetime
    raw_json: dict

class BaseScraper(ABC):
    source_name: str

    @abstractmethod
    def scrape(self) -> Iterator[LeadRaw]:
        """Yield LeadRaw objects. Never raise — log and skip on error."""
        ...

    def validate(self, lead: LeadRaw) -> bool:
        """Returns True if lead has minimum required fields."""
        return bool(lead.address and lead.zip_code and lead.signal)
```

## Adding a New Scraper

1. Create `src/scrapers/{source_name}.py`
2. Extend `BaseScraper`
3. Implement `scrape()` as a generator
4. Add to `src/scrapers/__init__.py` registry
5. Add ADR in `docs/decisions/` if it's a new source type
6. Test with `python tools/scripts/test_scraper.py {source_name}`

## Example: Permits Scraper

```python
# src/scrapers/permits.py
import httpx
from datetime import datetime, timedelta
from .base import BaseScraper, LeadRaw

class HillsboroughPermitsScraper(BaseScraper):
    source_name = "hillsborough_permits"
    BASE_URL = "https://data.hillsboroughcounty.org/resource/permits.json"
    # Hillsborough County uses Socrata Open Data API

    IRRIGATION_KEYWORDS = ["irrigation", "sprinkler", "landscape"]
    INTEREST_TYPES = ["NEW_SINGLE_FAMILY", "NEW_COMMERCIAL", "ADDITION"]

    def scrape(self):
        since = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
        params = {
            "$where": f"issue_date > '{since}'",
            "$limit": 500,
            "$$app_token": "YOUR_TOKEN"  # use env var
        }
        resp = httpx.get(self.BASE_URL, params=params, timeout=30)
        resp.raise_for_status()

        for row in resp.json():
            # Only include permits WITHOUT irrigation already
            desc = (row.get("description") or "").lower()
            if any(kw in desc for kw in self.IRRIGATION_KEYWORDS):
                continue  # already has irrigation — skip
            if row.get("permit_type") not in self.INTEREST_TYPES:
                continue

            yield LeadRaw(
                source=self.source_name,
                source_id=row.get("permit_number", ""),
                name=row.get("owner_name"),
                phone=None,  # permits don't include phone
                email=None,
                address=row.get("site_address", ""),
                city=row.get("city", "Tampa"),
                zip_code=row.get("zip_code", ""),
                signal=f"Building permit: {row.get('description', '')}",
                signal_type="new_construction",
                scraped_at=datetime.now(),
                raw_json=row
            )
```

## Scraper Development Rules

- **Rate limiting**: Add `await asyncio.sleep(1)` between requests
- **Error handling**: Log errors, yield nothing — never crash the pipeline
- **Dedup key**: `{source}:{source_id}` — must be stable across runs
- **Tampa ZIPs only**: Filter to `33602-33619, 33629, 33634-33637, 33647` + Brandon/Riverview
- **No PII beyond what's needed**: Only store name, phone, email, address
- **Test first**: Run with `--dry-run` flag before connecting to Supabase

## Available Scrapers

| File | Source | Status |
|---|---|---|
| `permits.py` | Hillsborough County Permits | ✅ Ready |
| `zillow.py` | Zillow new listings | 🚧 In Progress |
| `serp_local.py` | SerpAPI local intent | 🚧 In Progress |
| `facebook_groups.py` | FB Groups via Apify | 📋 Planned |
| `reddit.py` | Reddit via PRAW | 📋 Planned |
| `gmaps_reviews.py` | Google Maps competitor reviews | 📋 Planned |

## Prompt for Claude: Adding a Scraper

When asked to add a scraper, always:
1. Read `docs/architecture.md` first
2. Check this SKILL.md for the interface
3. Check `docs/decisions/001-lead-sources.md` for source context
4. Use the `BaseScraper` interface — no exceptions
5. Add a test case in `tools/scripts/test_scraper.py`

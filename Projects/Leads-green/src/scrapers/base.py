"""
BaseScraper — all scrapers must implement this interface.

Usage:
    class MySource(BaseScraper):
        source = "my_source"

        def scrape(self) -> list[LeadRaw]:
            ...
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime

from loguru import logger

from src.persistence.models import LeadRaw


class BaseScraper(ABC):
    # Subclasses must define the source name matching the DB enum
    source: str = ""

    # Polite delay between requests in seconds
    request_delay: float = 1.0

    def run(self) -> list[LeadRaw]:
        """
        Public entry point. Wraps scrape() with logging and timing.
        Returns a (possibly empty) list of raw leads.
        """
        logger.info(f"[{self.source}] Starting scrape")
        start = time.time()
        try:
            leads = self.scrape()
            elapsed = time.time() - start
            logger.success(
                f"[{self.source}] Scraped {len(leads)} leads in {elapsed:.1f}s"
            )
            return leads
        except Exception as exc:
            logger.error(f"[{self.source}] Scrape failed: {exc}")
            raise

    @abstractmethod
    def scrape(self) -> list[LeadRaw]:
        """Implement the actual scraping logic. Must return LeadRaw objects."""
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_lead(self, **kwargs) -> LeadRaw:
        """Convenience factory. Sets source and scraped_at automatically."""
        return LeadRaw(
            source=self.source,
            scraped_at=datetime.utcnow(),
            **kwargs,
        )

    def _sleep(self) -> None:
        time.sleep(self.request_delay)

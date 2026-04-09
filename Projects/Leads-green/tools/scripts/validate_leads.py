"""
Validate leads before DB insert.
Run this to sanity-check a batch of leads from a scraper output file.

Usage:
  python tools/scripts/validate_leads.py --file leads.json
  python tools/scripts/validate_leads.py --source permits
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from tabulate import tabulate

# Add project root to path
sys.path.insert(0, str(Path(__file__).parents[2]))

from src.persistence.models import LeadRaw
from src.pipeline.scorer import score_lead


@click.command()
@click.option("--file", "file_path", type=click.Path(exists=True), help="JSON file with leads array")
@click.option("--source", help="Run the named scraper and validate its output")
@click.option("--days-back", default=7, type=int)
@click.option("--max-zips", default=3, type=int, help="Max ZIPs for Zillow scraper")
def main(file_path, source, days_back, max_zips):
    from dotenv import load_dotenv
    from loguru import logger
    import sys
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    load_dotenv()

    leads_raw: list[dict] = []

    if file_path:
        with open(file_path) as f:
            data = json.load(f)
        leads_raw = data if isinstance(data, list) else [data]

    elif source == "permits":
        from src.scrapers.permits import HillsboroughPermitsScraper
        scraper = HillsboroughPermitsScraper(days_back=days_back)
        raw = scraper.run()
        leads_raw = [r.model_dump() for r in raw]

    elif source == "zillow":
        from src.scrapers.zillow import ZillowScraper
        scraper = ZillowScraper(max_zips=max_zips, days_listed=days_back)
        raw = scraper.run()
        leads_raw = [r.model_dump() for r in raw]

    elif source == "new_owners":
        from src.scrapers.new_owners import NewOwnersScraper
        scraper = NewOwnersScraper(days_back=days_back)
        raw = scraper.run()
        leads_raw = [r.model_dump() for r in raw]

    else:
        click.echo("Provide --file or --source", err=True)
        sys.exit(1)

    rows = []
    for item in leads_raw:
        try:
            lead = LeadRaw(**item)
            scoring = score_lead(lead.model_dump())
            rows.append([
                lead.source,
                lead.source_id or "—",
                lead.address[:40],
                lead.zip_code or "—",
                "Y" if lead.phone else "N",
                lead.signal_type,
                scoring.score,
                scoring.action.upper(),
            ])
        except Exception as exc:
            rows.append(["ERROR", str(item)[:40], str(exc), "", "", "", 0, "ERR"])

    headers = ["Source", "ID", "Address", "ZIP", "Phone?", "Signal", "Score", "Action"]
    click.echo(f"\nValidated {len(rows)} leads:\n")
    click.echo(tabulate(rows, headers=headers, tablefmt="rounded_outline"))

    call_count = sum(1 for r in rows if r[7] == "CALL")
    review_count = sum(1 for r in rows if r[7] == "REVIEW")
    discard_count = sum(1 for r in rows if r[7] == "DISCARD")
    click.echo(
        f"\n  CALL: {call_count}  |  REVIEW: {review_count}  |  DISCARD: {discard_count}\n"
    )


if __name__ == "__main__":
    main()

"""
Pipeline runner — processes a list of raw leads through the full pipeline:
  LeadRaw → dedup → enrich → score → Supabase insert → route

Called by:
  - FastAPI POST /ingest
  - n8n webhook handler
  - CLI: python src/pipeline/runner.py --source permits
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from loguru import logger

from src.persistence.client import insert_lead, is_on_dnc
from src.persistence.models import LeadRaw
from src.pipeline.dedup import is_duplicate, normalize_phone
from src.pipeline.enricher import enrich
from src.pipeline.scorer import score_lead


CALL_THRESHOLD = int(os.getenv("SCORE_CALL_THRESHOLD", "55"))
REVIEW_THRESHOLD = int(os.getenv("SCORE_REVIEW_THRESHOLD", "20"))


@dataclass
class PipelineResult:
    total: int
    inserted: int
    duplicates: int
    discarded: int
    queued_for_call: int
    queued_for_review: int
    errors: int


def run_pipeline(leads: list[LeadRaw]) -> PipelineResult:
    """
    Main pipeline entry point.
    Returns a summary of what happened to each lead.
    """
    result = PipelineResult(
        total=len(leads),
        inserted=0,
        duplicates=0,
        discarded=0,
        queued_for_call=0,
        queued_for_review=0,
        errors=0,
    )

    for raw in leads:
        try:
            _process_lead(raw, result)
        except Exception as exc:
            logger.exception(f"[pipeline] Error processing lead {raw.source_id}: {exc}")
            result.errors += 1

    logger.info(
        f"[pipeline] Done — {result.inserted} inserted, "
        f"{result.duplicates} dupes, {result.discarded} discarded, "
        f"{result.queued_for_call} queued to call, "
        f"{result.errors} errors"
    )
    return result


def _process_lead(raw: LeadRaw, result: PipelineResult) -> None:
    # 1. Dedup
    if is_duplicate(raw):
        result.duplicates += 1
        return

    # 2. DNC check (phone)
    phone = normalize_phone(raw.phone)
    if phone and is_on_dnc(phone):
        logger.debug(f"[pipeline] Phone {phone} is on DNC list — skipping")
        result.discarded += 1
        return

    # 3. Enrich
    enrichment = enrich(raw)

    # 4. Score
    lead_dict = raw.model_dump()
    lead_dict.update(enrichment)
    scoring = score_lead(lead_dict)

    if scoring.action == "discard":
        result.discarded += 1
        return

    # 5. Prepare DB row
    row = {
        **lead_dict,
        "phone": phone or raw.phone,  # prefer normalized
        "score": scoring.score,
        "score_reason": scoring.reason,
        "status": "queued" if scoring.action == "call" else "new",
        "scraped_at": (raw.scraped_at or datetime.utcnow()).isoformat(),
        "raw_json": raw.raw_json,
    }
    # Remove UUID fields Supabase will generate
    row.pop("id", None)
    row.pop("created_at", None)
    row.pop("updated_at", None)

    # 6. Insert
    insert_lead(row)
    result.inserted += 1

    if scoring.action == "call":
        result.queued_for_call += 1
        logger.info(
            f"[pipeline] HIGH SCORE lead queued — {raw.source}/{raw.source_id} "
            f"score={scoring.score} phone={phone}"
        )
    else:
        result.queued_for_review += 1
        logger.debug(
            f"[pipeline] Review lead — {raw.source}/{raw.source_id} "
            f"score={scoring.score}"
        )


# ---------------------------------------------------------------------------
# Retry queued calls
# ---------------------------------------------------------------------------

def retry_queued_calls() -> int:
    """
    Fire VAPI calls for all queued leads whose next_call_at has passed.
    Returns number of calls triggered.

    Called by the scheduler every hour (or on demand via POST /leads/retry-queued).
    """
    from src.persistence.client import get_supabase
    from src.voicebot.caller import trigger_call, is_tcpa_window

    if not is_tcpa_window():
        logger.info("[retry] Outside TCPA window — skipping retry run")
        return 0

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Leads ready for retry: queued + next_call_at in the past (or null = immediate)
    result = (
        sb.table("leads")
        .select("*")
        .eq("status", "queued")
        .not_.is_("phone", "null")
        .or_(f"next_call_at.is.null,next_call_at.lte.{now_iso}")
        .limit(50)
        .execute()
    )

    triggered = 0
    for lead in result.data or []:
        try:
            call = trigger_call(lead)
            if call:
                triggered += 1
                logger.info(f"[retry] Call triggered for lead {lead['id']} — VAPI {call.get('id')}")
        except Exception as exc:
            logger.error(f"[retry] Failed to call lead {lead['id']}: {exc}")

    logger.info(f"[retry] Retry run complete — {triggered} calls triggered")
    return triggered


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="Run the lead pipeline for a source")
    parser.add_argument(
        "--source",
        choices=["permits", "zillow", "new_owners", "facebook_groups"],
        required=True,
        help="Which scraper to run",
    )
    parser.add_argument("--days-back", type=int, default=7)
    parser.add_argument("--max-zips", type=int, default=5)
    args = parser.parse_args()

    if args.source == "permits":
        from src.scrapers.permits import HillsboroughPermitsScraper
        scraper = HillsboroughPermitsScraper(days_back=args.days_back)
    elif args.source == "zillow":
        from src.scrapers.zillow import ZillowScraper
        scraper = ZillowScraper(max_zips=args.max_zips, days_listed=args.days_back)
    elif args.source == "new_owners":
        from src.scrapers.new_owners import NewOwnersScraper
        scraper = NewOwnersScraper(days_back=args.days_back)
    elif args.source == "facebook_groups":
        from src.scrapers.facebook_groups import FacebookGroupsScraper
        scraper = FacebookGroupsScraper(days_back=args.days_back)
    else:
        raise ValueError(f"Unknown source: {args.source}")

    raw_leads = scraper.run()
    summary = run_pipeline(raw_leads)
    print(
        f"\nPipeline complete:\n"
        f"  Total:          {summary.total}\n"
        f"  Inserted:       {summary.inserted}\n"
        f"  Duplicates:     {summary.duplicates}\n"
        f"  Discarded:      {summary.discarded}\n"
        f"  Queued (call):  {summary.queued_for_call}\n"
        f"  Queued (review):{summary.queued_for_review}\n"
        f"  Errors:         {summary.errors}\n"
    )

"""
Seed synthetic test leads for all pipeline statuses.
Run AFTER migrations 003 and 004.

Usage:
    conda activate IA
    cd C:/Users/luisz/Projects/Leads-green
    python tools/scripts/seed_test_leads.py

To clean up test data:
    python tools/scripts/seed_test_leads.py --cleanup
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

from src.persistence.client import get_supabase  # noqa: E402

SEED_SOURCE = "seed_test"

TEST_LEADS = [
    {
        "source": SEED_SOURCE,
        "source_id": "test-qualified-001",
        "name": "Maria Gonzalez",
        "phone": "+18135550101",
        "email": "maria.g@email.com",
        "address": "4521 Bayshore Blvd, Tampa, FL 33611",
        "city": "Tampa",
        "zip_code": "33611",
        "lat": 27.8933,
        "lon": -82.4921,
        "property_type": "residential",
        "signal": "New homeowner — purchased 3 weeks ago, no irrigation system on record",
        "signal_type": "new_owner",
        "score": 78,
        "score_reason": "New owner in high-value zip, no irrigation on permit history, expressed interest via Facebook",
        "status": "qualified",
        "retry_count": 1,
        "notes": "Jimmy spoke with Maria — she is interested in a full irrigation system estimate. Prefers weekday mornings.",
        "scraped_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    },
    {
        "source": SEED_SOURCE,
        "source_id": "test-booked-001",
        "name": "James & Patricia Holloway",
        "phone": "+18135550202",
        "email": "jholloway@gmail.com",
        "address": "7832 Palm River Rd, Tampa, FL 33619",
        "city": "Tampa",
        "zip_code": "33619",
        "lat": 27.9342,
        "lon": -82.3801,
        "property_type": "residential",
        "signal": "Building permit issued for new pool — irrigation expansion typically follows",
        "signal_type": "new_construction",
        "score": 91,
        "score_reason": "Pool permit = high irrigation upgrade probability. New construction in active growth corridor.",
        "status": "booked",
        "retry_count": 1,
        "appointment_at": (datetime.now(timezone.utc) + timedelta(days=3, hours=9)).isoformat(),
        "appointment_notes": "Estimate for drip irrigation around new pool deck and extended lawn zones. Client has 0.4 acre lot. Budget ~$2,500.",
        "notes": "Booked via Jimmy — James was very receptive, needs estimate before contractor finishes pool.",
        "scraped_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(),
    },
    {
        "source": SEED_SOURCE,
        "source_id": "test-booked-002",
        "name": "Sunrise HOA — Building C",
        "phone": "+18135550303",
        "email": "manager@sunrisehoa.com",
        "address": "2200 E Hillsborough Ave, Tampa, FL 33610",
        "city": "Tampa",
        "zip_code": "33610",
        "lat": 27.9892,
        "lon": -82.4105,
        "property_type": "commercial",
        "signal": "HOA Facebook post requesting irrigation repair quotes — sprinkler heads broken after mowing",
        "signal_type": "complaint",
        "score": 85,
        "score_reason": "HOA = recurring contract potential. Active complaint = urgent need. Commercial property.",
        "status": "booked",
        "retry_count": 0,
        "appointment_at": (datetime.now(timezone.utc) + timedelta(days=1, hours=14)).isoformat(),
        "appointment_notes": "Walk the entire common area — 12 broken heads plus controller upgrade needed. Decision maker is Linda Reyes (property manager).",
        "scraped_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    },
    {
        "source": SEED_SOURCE,
        "source_id": "test-lost-001",
        "name": "David Chen",
        "phone": "+18135550404",
        "address": "9103 N Dale Mabry Hwy, Tampa, FL 33614",
        "city": "Tampa",
        "zip_code": "33614",
        "lat": 28.0431,
        "lon": -82.5012,
        "property_type": "residential",
        "signal": "Zillow new listing — recently moved in, asking neighbors about irrigation companies",
        "signal_type": "new_owner",
        "score": 62,
        "score_reason": "New owner in mid-range zip. Interest signal from Nextdoor mention.",
        "status": "lost",
        "retry_count": 1,
        "notes": "Jimmy called — David said he already hired another company last week. Not interested.",
        "scraped_at": (datetime.now(timezone.utc) - timedelta(days=4)).isoformat(),
    },
    {
        "source": SEED_SOURCE,
        "source_id": "test-lost-002",
        "name": "Westside Commercial Park",
        "phone": "+18135550505",
        "address": "1450 W Kennedy Blvd, Tampa, FL 33606",
        "city": "Tampa",
        "zip_code": "33606",
        "lat": 27.9481,
        "lon": -82.4772,
        "property_type": "commercial",
        "signal": "Google Maps review complaining about dead grass — existing system failing",
        "signal_type": "complaint",
        "score": 55,
        "score_reason": "Active complaint about irrigation. Commercial — higher ticket but longer sales cycle.",
        "status": "lost",
        "retry_count": 2,
        "notes": "Declined twice — property manager said budget frozen until Q3.",
        "scraped_at": (datetime.now(timezone.utc) - timedelta(days=6)).isoformat(),
    },
]


def seed(sb):
    inserted = 0
    skipped = 0
    for lead in TEST_LEADS:
        # Skip if already exists
        existing = (
            sb.table("leads")
            .select("id")
            .eq("source", lead["source"])
            .eq("source_id", lead["source_id"])
            .limit(1)
            .execute()
        )
        if existing.data:
            print(f"  skip  [{lead['status']}] {lead['name']} — already exists")
            skipped += 1
            continue

        row = {k: v for k, v in lead.items()}
        sb.table("leads").insert(row).execute()
        print(f"  ✓ [{lead['status']:10s}] {lead['name']}")
        inserted += 1

    print(f"\nDone — {inserted} inserted, {skipped} skipped")


def cleanup(sb):
    result = sb.table("leads").delete().eq("source", SEED_SOURCE).execute()
    count = len(result.data) if result.data else 0
    print(f"Deleted {count} test lead(s) with source='{SEED_SOURCE}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true", help="Remove test leads instead of inserting")
    args = parser.parse_args()

    sb = get_supabase()
    print(f"{'Cleaning up' if args.cleanup else 'Seeding'} test leads...\n")

    if args.cleanup:
        cleanup(sb)
    else:
        seed(sb)

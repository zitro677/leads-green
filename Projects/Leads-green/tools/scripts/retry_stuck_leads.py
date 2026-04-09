"""
Re-queue leads that are stuck in 'calling' status (e.g. after a server restart).
Any lead stuck in 'calling' for > 10 minutes is likely orphaned.

Usage:
  python tools/scripts/retry_stuck_leads.py
  python tools/scripts/retry_stuck_leads.py --dry-run
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parents[2]))


@click.command()
@click.option("--dry-run", is_flag=True, help="Show what would be re-queued without changing anything")
@click.option("--stuck-minutes", default=10, type=int, help="Minutes in 'calling' before considered stuck")
def main(dry_run, stuck_minutes):
    from dotenv import load_dotenv
    load_dotenv()

    from src.persistence.client import get_supabase, update_lead

    cutoff = (datetime.utcnow() - timedelta(minutes=stuck_minutes)).isoformat()
    sb = get_supabase()

    result = (
        sb.table("leads")
        .select("id, name, phone, updated_at, retry_count")
        .eq("status", "calling")
        .lt("updated_at", cutoff)
        .execute()
    )

    stuck = result.data
    if not stuck:
        click.echo(f"No leads stuck in 'calling' for > {stuck_minutes} minutes.")
        return

    click.echo(f"Found {len(stuck)} stuck leads:")
    for lead in stuck:
        click.echo(f"  {lead['id'][:8]} — {lead.get('name')} updated_at={lead['updated_at'][:19]}")
        if not dry_run:
            update_lead(lead["id"], {"status": "queued"})

    if dry_run:
        click.echo("\n[dry-run] No changes made.")
    else:
        click.echo(f"\nRe-queued {len(stuck)} leads.")


if __name__ == "__main__":
    main()

"""
Inspect and manage the call queue.

Usage:
  python tools/scripts/call_queue.py --status queued
  python tools/scripts/call_queue.py --status queued --trigger   # actually trigger VAPI calls
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).parents[2]))


@click.command()
@click.option("--status", default="queued", help="Lead status to inspect")
@click.option("--trigger", is_flag=True, help="Actually trigger VAPI calls for queued leads")
@click.option("--limit", default=20, type=int)
def main(status, trigger, limit):
    from dotenv import load_dotenv
    load_dotenv()

    from src.persistence.client import get_leads_by_status

    leads = get_leads_by_status(status, limit=limit)

    if not leads:
        click.echo(f"No leads with status='{status}'.")
        return

    rows = [
        [
            str(l["id"])[:8],
            l.get("name") or "—",
            l.get("phone") or "—",
            l.get("source"),
            l.get("score"),
            l.get("retry_count", 0),
            (l.get("created_at") or "")[:10],
        ]
        for l in leads
    ]
    click.echo(
        tabulate(
            rows,
            headers=["ID (short)", "Name", "Phone", "Source", "Score", "Retries", "Created"],
            tablefmt="rounded_outline",
        )
    )
    click.echo(f"\nTotal: {len(leads)} leads in status='{status}'\n")

    if trigger:
        from src.voicebot.caller import is_tcpa_window, trigger_call

        if not is_tcpa_window():
            click.echo("Outside TCPA calling window (8 AM – 9 PM ET, Mon–Sat). No calls triggered.")
            return

        triggered = 0
        for lead in leads:
            if lead.get("phone"):
                result = trigger_call(lead)
                if result:
                    triggered += 1
                    click.echo(f"  Called: {lead.get('name')} ({lead.get('phone')})")

        click.echo(f"\nTriggered {triggered} calls.")


if __name__ == "__main__":
    main()

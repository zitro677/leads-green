"""
Show pipeline stats for a given time period.

Usage:
  python tools/scripts/stats.py --period 24h
  python tools/scripts/stats.py --period 7d
  python tools/scripts/stats.py --period 30d
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import click
from tabulate import tabulate

sys.path.insert(0, str(Path(__file__).parents[2]))


def parse_period(period: str) -> datetime:
    period = period.lower()
    if period.endswith("h"):
        return datetime.utcnow() - timedelta(hours=int(period[:-1]))
    if period.endswith("d"):
        return datetime.utcnow() - timedelta(days=int(period[:-1]))
    raise ValueError(f"Invalid period: {period}. Use e.g. 24h or 7d")


@click.command()
@click.option("--period", default="24h", help="Time window: 24h, 7d, 30d")
def main(period: str):
    from dotenv import load_dotenv
    load_dotenv()

    from src.persistence.client import get_supabase

    since = parse_period(period)
    sb = get_supabase()

    # Leads by source
    result = (
        sb.table("leads")
        .select("source, status, score")
        .gte("created_at", since.isoformat())
        .execute()
    )
    rows = result.data

    if not rows:
        click.echo(f"No leads found in the last {period}.")
        return

    # Aggregate
    by_source: dict[str, dict] = {}
    for row in rows:
        src = row["source"]
        if src not in by_source:
            by_source[src] = {"total": 0, "booked": 0, "called": 0, "scores": []}
        by_source[src]["total"] += 1
        if row["status"] == "booked":
            by_source[src]["booked"] += 1
        if row["status"] in ("calling", "qualified", "booked"):
            by_source[src]["called"] += 1
        by_source[src]["scores"].append(row["score"])

    table_rows = []
    for src, data in sorted(by_source.items()):
        avg_score = round(sum(data["scores"]) / len(data["scores"]), 1)
        table_rows.append([src, data["total"], data["called"], data["booked"], avg_score])

    click.echo(f"\nStats for last {period} (since {since.strftime('%Y-%m-%d %H:%M')} UTC):\n")
    click.echo(
        tabulate(
            table_rows,
            headers=["Source", "Leads", "Called", "Booked", "Avg Score"],
            tablefmt="rounded_outline",
        )
    )

    total = sum(d["total"] for d in by_source.values())
    booked = sum(d["booked"] for d in by_source.values())
    conv = f"{booked/total*100:.1f}%" if total else "0%"
    click.echo(f"\n  Total: {total} leads | Booked: {booked} | Conversion: {conv}\n")


if __name__ == "__main__":
    main()

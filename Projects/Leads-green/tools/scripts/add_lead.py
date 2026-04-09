"""
Manually add a lead (referrals, walk-ins, etc.).

Usage:
  python tools/scripts/add_lead.py \
    --name "John Smith" \
    --phone "+18135559999" \
    --address "123 Main St Tampa FL 33609" \
    --signal "Referral from existing customer — needs sprinkler repair"
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parents[2]))


@click.command()
@click.option("--name", required=False)
@click.option("--phone", required=False)
@click.option("--email", required=False)
@click.option("--address", required=True)
@click.option("--signal", default="Manual entry", help="Why this person is a lead")
@click.option("--source", default="manual")
@click.option("--zip-code", default=None)
def main(name, phone, email, address, signal, source, zip_code):
    from dotenv import load_dotenv
    load_dotenv()

    from src.persistence.models import LeadRaw
    from src.pipeline.runner import run_pipeline

    raw = LeadRaw(
        source=source,
        name=name,
        phone=phone,
        email=email,
        address=address,
        zip_code=zip_code,
        signal=signal,
        signal_type="request",
    )

    click.echo(f"Adding lead: {name or 'Unknown'} at {address}")
    result = run_pipeline([raw])
    click.echo(
        f"Done — inserted={result.inserted} "
        f"queued_call={result.queued_for_call} "
        f"errors={result.errors}"
    )


if __name__ == "__main__":
    main()

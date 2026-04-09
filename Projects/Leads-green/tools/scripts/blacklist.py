"""
Manage the Do Not Call list.

Usage:
  python tools/scripts/blacklist.py --add "+18135551234" --reason "requested"
  python tools/scripts/blacklist.py --check "+18135551234"
  python tools/scripts/blacklist.py --list
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parents[2]))


@click.command()
@click.option("--add", "phone_add", metavar="PHONE", help="Add phone to DNC list")
@click.option("--check", "phone_check", metavar="PHONE", help="Check if phone is on DNC list")
@click.option("--list", "show_list", is_flag=True, help="Show all DNC entries")
@click.option("--reason", default="requested", help="Reason for DNC (requested/tcpa/competitor)")
def main(phone_add, phone_check, show_list, reason):
    from dotenv import load_dotenv
    load_dotenv()

    from src.persistence.client import add_to_dnc, get_supabase, is_on_dnc

    if phone_add:
        add_to_dnc(phone_add, reason=reason)
        click.echo(f"Added {phone_add} to DNC list (reason: {reason})")

    elif phone_check:
        on_list = is_on_dnc(phone_check)
        status = "ON DNC LIST" if on_list else "not on DNC list"
        click.echo(f"{phone_check}: {status}")

    elif show_list:
        sb = get_supabase()
        result = sb.table("dnc_list").select("*").order("added_at", desc=True).execute()
        if not result.data:
            click.echo("DNC list is empty.")
        else:
            from tabulate import tabulate
            rows = [[r["phone"], r["reason"], r["added_at"][:10]] for r in result.data]
            click.echo(tabulate(rows, headers=["Phone", "Reason", "Added"], tablefmt="rounded_outline"))

    else:
        click.echo("Provide --add, --check, or --list", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Supabase client — singleton pattern.
Uses the service role key for all pipeline writes (bypasses RLS).
"""
from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def insert_lead(lead: dict) -> dict | None:
    """Insert a lead; return the inserted row, or None on failure."""
    sb = get_supabase()
    try:
        result = sb.table("leads").insert(lead).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        from loguru import logger
        logger.error(f"[db] insert_lead failed: {exc} | source_id={lead.get('source_id')}")
        raise


def get_lead_by_source(source: str, source_id: str) -> dict | None:
    """Return existing lead or None (used for dedup)."""
    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("*")
        .eq("source", source)
        .eq("source_id", source_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def update_lead(lead_id: str, fields: dict) -> dict | None:
    sb = get_supabase()
    try:
        result = sb.table("leads").update(fields).eq("id", lead_id).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        from loguru import logger
        logger.error(f"[db] update_lead failed: {exc} | lead_id={lead_id}")
        raise


def get_leads_by_status(status: str, limit: int = 100) -> list[dict]:
    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("*")
        .eq("status", status)
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data


# ---------------------------------------------------------------------------
# Call outcomes
# ---------------------------------------------------------------------------

def insert_call_outcome(outcome: dict) -> dict:
    sb = get_supabase()
    result = sb.table("call_outcomes").insert(outcome).execute()
    return result.data[0]


# ---------------------------------------------------------------------------
# DNC list
# ---------------------------------------------------------------------------

def is_on_dnc(phone: str) -> bool:
    sb = get_supabase()
    result = (
        sb.table("dnc_list")
        .select("id")
        .eq("phone", phone)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


def add_to_dnc(phone: str, reason: str = "requested") -> None:
    sb = get_supabase()
    sb.table("dnc_list").upsert({"phone": phone, "reason": reason}).execute()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_lead_counts_by_source(days: int = 7) -> list[dict]:
    """Raw counts grouped by source for the last N days."""
    sb = get_supabase()
    result = sb.rpc(
        "lead_counts_by_source",
        {"days_back": days},
    ).execute()
    return result.data

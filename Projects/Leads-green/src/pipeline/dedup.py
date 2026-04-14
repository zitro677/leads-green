"""
Deduplication logic.

Primary dedup: source + source_id (DB unique constraint handles this).
Secondary dedup: phone number hash (prevents calling the same person from different sources).
"""
from __future__ import annotations

import hashlib
import re

from loguru import logger

from src.persistence.client import get_lead_by_source, get_supabase
from src.persistence.models import LeadRaw


def normalize_phone(phone: str | None) -> str | None:
    """Strip non-digits, enforce E.164 style for US numbers."""
    if not phone:
        return None
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return None


def phone_hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def is_duplicate(lead: LeadRaw) -> bool:
    """
    Returns True if this lead is already in the DB and should be skipped.

    Check order:
    1. Exact match on source + source_id (fast — indexed)
    2. Phone number match across all sources (if phone present)
    3. Exhausted leads are permanently blocked regardless of source
    """
    # Check 1: exact source+id match
    if lead.source_id:
        existing = get_lead_by_source(lead.source, lead.source_id)
        if existing:
            status = existing.get("status", "")
            if status == "exhausted":
                logger.debug(
                    f"[dedup] Exhausted lead blocked: {lead.source}/{lead.source_id}"
                )
            else:
                logger.debug(
                    f"[dedup] Duplicate by source_id: {lead.source}/{lead.source_id}"
                )
            return True

    # Check 2: phone match (also catches exhausted leads from other sources)
    phone = normalize_phone(lead.phone)
    if phone:
        sb = get_supabase()
        result = (
            sb.table("leads")
            .select("id,status")
            .eq("phone", phone)
            .limit(1)
            .execute()
        )
        if result.data:
            status = result.data[0].get("status", "")
            if status == "exhausted":
                logger.debug(f"[dedup] Exhausted phone blocked: {phone}")
            else:
                logger.debug(f"[dedup] Duplicate by phone: {phone}")
            return True

    return False

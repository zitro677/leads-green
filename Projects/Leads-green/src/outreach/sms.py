"""
SMS sender for Green Landscape outreach via Twilio.

SETUP:
  1. Sign up at twilio.com (free trial gives ~$15 credit = ~1,900 SMS)
  2. Get a Twilio phone number (~$1/month)
  3. Add to .env:
       TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
       TWILIO_AUTH_TOKEN=your_auth_token
       TWILIO_FROM_NUMBER=+18135550000   (your Twilio number)

PRICING: ~$0.0079/SMS outbound in the US (~$0.80 per 100 SMS)
TCPA compliance: Only send within 8AM-9PM ET, Mon-Sat. Respect STOP replies.
"""
from __future__ import annotations

import os
import time

import httpx
from loguru import logger

from src.outreach.templates import sms_intro, sms_followup
from src.voicebot.caller import is_tcpa_window

TWILIO_BASE = "https://api.twilio.com/2010-04-01"


def _send_sms(to: str, body: str) -> bool:
    """Send a single SMS via Twilio REST API. Returns True on success."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_FROM_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        logger.warning("[sms] TWILIO_ACCOUNT_SID / AUTH_TOKEN / FROM_NUMBER not set — skipping")
        return False

    try:
        resp = httpx.post(
            f"{TWILIO_BASE}/Accounts/{account_sid}/Messages.json",
            auth=(account_sid, auth_token),
            data={"From": from_number, "To": to, "Body": body},
            timeout=15,
        )
        data = resp.json()
        if resp.status_code in (200, 201):
            logger.success(f"[sms] Sent to {to} — SID: {data.get('sid')}")
            return True
        else:
            logger.error(f"[sms] Twilio error {resp.status_code}: {data.get('message')}")
            return False

    except Exception as exc:
        logger.error(f"[sms] Failed to send to {to}: {exc}")
        return False


def send_intro_sms(lead: dict) -> bool:
    """Send the intro SMS to a lead. Respects TCPA window."""
    phone = lead.get("phone")
    if not phone:
        return False

    if not is_tcpa_window():
        logger.info(f"[sms] Outside TCPA window — skipping SMS to {phone}")
        return False

    from src.persistence.client import is_on_dnc
    if is_on_dnc(phone):
        logger.info(f"[sms] {phone} is on DNC — skipping")
        return False

    body = sms_intro(lead)
    return _send_sms(phone, body)


def send_followup_sms(lead: dict) -> bool:
    """Send a follow-up SMS 48h after intro."""
    phone = lead.get("phone")
    if not phone:
        return False

    if not is_tcpa_window():
        return False

    from src.persistence.client import is_on_dnc
    if is_on_dnc(phone):
        return False

    body = sms_followup(lead)
    return _send_sms(phone, body)


def run_sms_outreach(limit: int = 50, delay: float = 1.0) -> dict:
    """
    Send intro SMS to all queued leads that have a phone but no SMS yet.
    """
    from datetime import datetime, timezone
    from src.persistence.client import get_supabase, update_lead

    if not is_tcpa_window():
        logger.info("[sms] Outside TCPA window — aborting batch")
        return {"skipped": "outside_tcpa_window"}

    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("*")
        .not_.is_("phone", "null")
        .is_("sms_sent_at", "null")
        .in_("status", ["queued", "new"])
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )

    leads = result.data
    logger.info(f"[sms] Sending intro SMS to {len(leads)} leads")

    sent = 0
    failed = 0
    skipped = 0

    for lead in leads:
        ok = send_intro_sms(lead)
        if ok:
            update_lead(lead["id"], {"sms_sent_at": datetime.now(timezone.utc).isoformat()})
            sent += 1
        else:
            failed += 1
        time.sleep(delay)

    summary = {"processed": len(leads), "sent": sent, "failed": failed, "skipped": skipped}
    logger.info(f"[sms] Done: {summary}")
    return summary

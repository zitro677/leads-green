"""
VAPI outbound call trigger.

Called by n8n WF-003 (voicebot_caller) after a lead scores >= 55.
Also callable directly from CLI for manual triggers.

TCPA compliance:
- Only call 8 AM – 9 PM ET (Mon–Sat)
- Check DNC before calling
- Max 3 attempts per lead, 24h between attempts
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
import pytz
from loguru import logger

from src.persistence.client import add_to_dnc, is_on_dnc, update_lead

VAPI_API_URL = "https://api.vapi.ai/call/phone"

ET = pytz.timezone("America/New_York")

CALL_WINDOW_START = 8   # 8 AM ET
CALL_WINDOW_END = 21    # 9 PM ET
MAX_ATTEMPTS = int(os.getenv("MAX_CALL_ATTEMPTS", "2"))
RETRY_HOURS = int(os.getenv("CALL_RETRY_HOURS", "24"))


def is_tcpa_window() -> bool:
    """Returns True if current ET time is within the allowed call window."""
    now_et = datetime.now(ET)
    hour = now_et.hour
    weekday = now_et.weekday()  # 0=Mon … 6=Sun
    return (
        CALL_WINDOW_START <= hour < CALL_WINDOW_END
        and weekday != 6  # no Sunday calls
    )


def trigger_call(lead: dict) -> dict | None:
    """
    Initiates an outbound VAPI call for the given lead.

    Returns the VAPI call object on success, None if skipped.
    Raises httpx.HTTPStatusError on API failure.
    """
    lead_id = str(lead.get("id", ""))
    phone = lead.get("phone")
    name = (lead.get("name") or "there")[:40]

    if not phone:
        logger.warning(f"[caller] Lead {lead_id} has no phone — skipping")
        return None

    # DNC check
    if is_on_dnc(phone):
        logger.info(f"[caller] {phone} is on DNC — skipping lead {lead_id}")
        return None

    # TCPA window check
    if not is_tcpa_window():
        logger.info(f"[caller] Outside TCPA window — queuing lead {lead_id} for later")
        update_lead(lead_id, {"status": "queued"})
        return None

    # Max attempts check
    retry_count = lead.get("retry_count", 0)
    if retry_count >= MAX_ATTEMPTS:
        logger.info(f"[caller] Lead {lead_id} exhausted {MAX_ATTEMPTS} attempts — marking discarded")
        update_lead(lead_id, {"status": "exhausted"})
        return None

    # Retry window check — don't call before next_call_at
    next_call_at = lead.get("next_call_at")
    if next_call_at:
        next_call_dt = datetime.fromisoformat(next_call_at.replace("Z", "+00:00"))
        if datetime.now(timezone.utc) < next_call_dt:
            logger.info(f"[caller] Lead {lead_id} not ready for retry until {next_call_at}")
            return None

    payload = {
        "assistantId": os.getenv("VAPI_ASSISTANT_ID", ""),
        "phoneNumberId": os.getenv("VAPI_PHONE_NUMBER_ID", ""),
        "customer": {
            "number": phone,
            "name": name,
        },
        "assistantOverrides": {
            "variableValues": {
                "lead_name": name,
                "lead_source": lead.get("source", ""),
                "lead_signal": lead.get("signal", ""),
            }
        },
    }

    logger.info(f"[caller] Initiating call to {phone} for lead {lead_id}")

    resp = httpx.post(
        VAPI_API_URL,
        headers={
            "Authorization": f"Bearer {os.getenv('VAPI_API_KEY', '')}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if not resp.is_success:
        logger.error(f"[caller] VAPI error {resp.status_code}: {resp.text}")
        raise ValueError(f"VAPI call failed ({resp.status_code}): {resp.text}")
    call_data = resp.json()

    vapi_call_id = call_data.get("id")
    update_lead(
        lead_id,
        {
            "status": "calling",
            "vapi_call_id": vapi_call_id,
            "retry_count": retry_count + 1,
        },
    )

    logger.success(
        f"[caller] Call started — VAPI call_id={vapi_call_id} lead={lead_id}"
    )
    return call_data


def handle_vapi_outcome(webhook_payload: dict) -> dict:
    """
    Processes the end-of-call-report webhook from VAPI.
    Returns a summary dict for logging/Telegram.
    """
    from src.persistence.client import get_supabase, insert_call_outcome

    call = webhook_payload.get("call", {})
    vapi_call_id = call.get("id")
    phone = call.get("customer", {}).get("number")
    duration = call.get("durationSeconds", 0)
    transcript = call.get("transcript", "")
    summary = call.get("summary", "")

    # Map VAPI success evaluation to outcome
    success = call.get("successEvaluation", "").lower()
    if success == "true" or "book" in summary.lower():
        outcome = "booked"
    elif "voicemail" in summary.lower():
        outcome = "voicemail"
    elif "not interested" in summary.lower() or "no" in success:
        outcome = "not_interested"
    elif duration < 10:
        outcome = "no_answer"
    else:
        outcome = "qualified"

    # Find lead by vapi_call_id
    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("id,phone")
        .eq("vapi_call_id", vapi_call_id)
        .limit(1)
        .execute()
    )
    lead_row = result.data[0] if result.data else None
    lead_id = lead_row["id"] if lead_row else None

    if not lead_id:
        logger.warning(f"[caller] No lead found for vapi_call_id={vapi_call_id} — outcome not recorded")
        return {"lead_id": None, "outcome": outcome, "duration_seconds": duration}

    # Insert call outcome
    outcome_row = {
        "lead_id": lead_id,
        "vapi_call_id": vapi_call_id,
        "duration_seconds": duration,
        "outcome": outcome,
        "transcript": transcript,
        "summary": summary,
    }
    if lead_id:
        insert_call_outcome(outcome_row)

    # Update lead status — schedule retry or exhaust if no answer/voicemail
    if lead_id:
        from src.persistence.client import update_lead
        lead_row_full = (
            sb.table("leads").select("retry_count").eq("id", lead_id).limit(1).execute()
        )
        current_retry = (lead_row_full.data[0].get("retry_count", 0) if lead_row_full.data else 0)

        if outcome in ("no_answer", "voicemail"):
            if current_retry >= MAX_ATTEMPTS:
                update_lead(lead_id, {"status": "exhausted"})
                logger.info(f"[caller] Lead {lead_id} exhausted after {current_retry} attempts")
            else:
                next_call_at = (datetime.now(timezone.utc) + timedelta(hours=RETRY_HOURS)).isoformat()
                update_lead(lead_id, {"status": "queued", "next_call_at": next_call_at})
                logger.info(f"[caller] Lead {lead_id} queued for retry at {next_call_at}")
        else:
            status_map = {
                "booked": "booked",
                "not_interested": "lost",
                "qualified": "qualified",
            }
            new_status = status_map.get(outcome, "queued")
            extra = {}
            if outcome == "booked":
                # Store appointment info — Calendly sends exact time in assistantOverrides;
                # fall back to +2 business days if not present.
                appt_time = (
                    webhook_payload.get("call", {})
                    .get("assistantOverrides", {})
                    .get("variableValues", {})
                    .get("appointment_at")
                )
                if not appt_time:
                    from datetime import timedelta as _td
                    appt_time = (datetime.now(timezone.utc) + _td(days=2)).isoformat()
                extra["appointment_at"] = appt_time
                extra["appointment_notes"] = summary or "Appointment booked via Jimmy"
            update_lead(lead_id, {"status": new_status, **extra})

    # DNC if not interested
    if outcome == "not_interested" and phone:
        add_to_dnc(phone, reason="not_interested")

    logger.info(
        f"[caller] Outcome recorded — call_id={vapi_call_id} "
        f"outcome={outcome} lead_id={lead_id}"
    )
    return {
        "lead_id": lead_id,
        "outcome": outcome,
        "duration_seconds": duration,
    }

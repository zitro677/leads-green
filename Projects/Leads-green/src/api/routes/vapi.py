"""
POST /vapi/outcome — VAPI webhook handler.
Receives end-of-call-report events from VAPI and updates Supabase.
"""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request
from loguru import logger

router = APIRouter(tags=["voicebot"])


@router.post("/vapi/outcome")
async def vapi_outcome_webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    event_type = payload.get("type")

    if event_type != "end-of-call-report":
        # Acknowledge other event types without processing
        return {"status": "ignored", "type": event_type}

    # Process in background so VAPI gets a fast 200 response
    background_tasks.add_task(_process_outcome, payload)
    return {"status": "accepted"}


async def _process_outcome(payload: dict) -> None:
    try:
        from src.voicebot.caller import handle_vapi_outcome
        result = handle_vapi_outcome(payload)
        logger.info(f"[vapi] Outcome processed: {result}")

        # Send Telegram notification for booked outcomes
        if result.get("outcome") == "booked":
            await _notify_booked(result, payload)

    except Exception as exc:
        logger.error(f"[vapi] Outcome processing error: {exc}")


async def _notify_booked(result: dict, payload: dict) -> None:
    import os
    import httpx

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return

    call = payload.get("call", {})
    name = call.get("customer", {}).get("name", "Unknown")
    phone = call.get("customer", {}).get("number", "")
    duration = result.get("duration_seconds", 0)

    text = (
        f"BOOKED! {name} ({phone})\n"
        f"Duration: {duration}s\n"
        f"Lead ID: {result.get('lead_id', 'N/A')}"
    )

    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
                timeout=5,
            )
    except Exception as exc:
        logger.warning(f"[vapi] Telegram notification failed: {exc}")

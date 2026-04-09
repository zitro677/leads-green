"""
Email sender for Green Landscape outreach.

Uses Gmail SMTP with App Password — completely free.

SETUP (one-time):
  1. Go to myaccount.google.com → Security → 2-Step Verification (enable it)
  2. Go to myaccount.google.com → Security → App Passwords
  3. Create app password for "Mail" → copy the 16-char password
  4. Add to .env:
       EMAIL_FROM=your@gmail.com
       EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
       EMAIL_FROM_NAME=Green Landscape Irrigation

ALTERNATIVELY use any SMTP provider:
  - Outlook/Hotmail: smtp.office365.com:587
  - Zoho: smtp.zoho.com:587
  - Set EMAIL_SMTP_HOST and EMAIL_SMTP_PORT in .env to override Gmail defaults
"""
from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from loguru import logger

from src.outreach.templates import EMAIL_SUBJECT, email_html, email_text


SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))


def send_email(to_address: str, lead: dict) -> bool:
    """
    Send the intro email to a lead.
    Returns True on success, False on failure.
    """
    sender = os.getenv("EMAIL_FROM")
    password = os.getenv("EMAIL_APP_PASSWORD")
    from_name = os.getenv("EMAIL_FROM_NAME", "Green Landscape Irrigation")

    if not sender or not password:
        logger.warning("[emailer] EMAIL_FROM or EMAIL_APP_PASSWORD not set — skipping")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = EMAIL_SUBJECT
    msg["From"] = f"{from_name} <{sender}>"
    msg["To"] = to_address
    msg["Reply-To"] = sender

    msg.attach(MIMEText(email_text(lead), "plain"))
    msg.attach(MIMEText(email_html(lead), "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, to_address, msg.as_string())

        logger.success(f"[emailer] Email sent to {to_address} for lead {str(lead.get('id',''))[:8]}")
        return True

    except Exception as exc:
        logger.error(f"[emailer] Failed to send to {to_address}: {exc}")
        return False


def run_email_outreach(limit: int = 50) -> dict:
    """
    Send intro emails to all leads that have an email but haven't been contacted yet.
    Marks leads with email_sent_at timestamp after sending.
    """
    from datetime import datetime, timezone
    from src.persistence.client import get_supabase, update_lead

    sb = get_supabase()
    result = (
        sb.table("leads")
        .select("*")
        .not_.is_("email", "null")
        .is_("email_sent_at", "null")
        .in_("status", ["new", "queued"])
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )

    leads = result.data
    logger.info(f"[emailer] Sending intro emails to {len(leads)} leads")

    sent = 0
    failed = 0

    for lead in leads:
        email = lead.get("email", "").strip()
        if not email:
            continue

        ok = send_email(email, lead)
        if ok:
            update_lead(lead["id"], {"email_sent_at": datetime.now(timezone.utc).isoformat()})
            sent += 1
        else:
            failed += 1

    summary = {"processed": len(leads), "sent": sent, "failed": failed}
    logger.info(f"[emailer] Done: {summary}")
    return summary

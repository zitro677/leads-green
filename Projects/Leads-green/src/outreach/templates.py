"""
Email and SMS templates for Green Landscape Irrigation outreach.

Edit the content here — all messaging flows from this file.
"""
from __future__ import annotations


def _first_name(full_name: str) -> str:
    """Extract first name from 'JOHN AND JANE SMITH' or 'John Smith'."""
    name = full_name.strip().title()
    # Handle "And" compounds — take first word before "And"
    parts = name.replace(" And ", " & ").split()
    first = parts[0] if parts else "Neighbor"
    # Ignore generic LLC / Corp names
    if first.lower() in {"llc", "corp", "inc", "trust", "estate"}:
        return "Neighbor"
    return first


# ---------------------------------------------------------------------------
# EMAIL
# ---------------------------------------------------------------------------

EMAIL_SUBJECT = "Free Irrigation Assessment — Welcome to Your New Home"

def email_html(lead: dict) -> str:
    name = _first_name(lead.get("name") or "Neighbor")
    address = lead.get("address", "your new property")
    city = lead.get("city", "Tampa")
    return f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto;color:#222;">
  <div style="background:#166534;padding:24px 32px;border-radius:8px 8px 0 0;">
    <h1 style="color:white;margin:0;font-size:22px;">Green Landscape Irrigation</h1>
    <p style="color:#bbf7d0;margin:4px 0 0;">Tampa Bay's Irrigation Specialists</p>
  </div>
  <div style="padding:32px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;">
    <p>Hi <strong>{name}</strong>,</p>
    <p>Congratulations on your new home at <strong>{address}</strong>! 🎉</p>
    <p>We're <strong>Green Landscape Irrigation</strong> — {city}'s trusted irrigation specialists.
       As a new homeowner, we'd like to offer you a <strong>FREE irrigation system assessment</strong>,
       no strings attached.</p>
    <p>We'll check:</p>
    <ul>
      <li>✅ Existing irrigation coverage &amp; efficiency</li>
      <li>✅ Water waste and leak detection</li>
      <li>✅ Upgrade recommendations to protect your lawn</li>
    </ul>
    <div style="text-align:center;margin:32px 0;">
      <a href="https://greenlandscapingirrigation.com"
         style="background:#16a34a;color:white;padding:14px 32px;border-radius:8px;
                text-decoration:none;font-weight:bold;font-size:16px;">
        Schedule My Free Assessment
      </a>
    </div>
    <p>Or just reply to this email — we'll get right back to you.</p>
    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;" />
    <p style="color:#6b7280;font-size:13px;">
      Green Landscape Irrigation · Tampa, FL<br>
      <a href="https://greenlandscapingirrigation.com" style="color:#16a34a;">greenlandscapingirrigation.com</a><br>
      <br>
      <em>You received this because you recently purchased a property in our service area.
      To unsubscribe, reply UNSUBSCRIBE.</em>
    </p>
  </div>
</html></body>
""".strip()


def email_text(lead: dict) -> str:
    name = _first_name(lead.get("name") or "Neighbor")
    address = lead.get("address", "your new property")
    return (
        f"Hi {name},\n\n"
        f"Congratulations on your new home at {address}!\n\n"
        f"We're Green Landscape Irrigation — Tampa Bay's irrigation specialists. "
        f"As a new homeowner, we'd like to offer you a FREE irrigation assessment, no strings attached.\n\n"
        f"We'll check existing coverage, detect water waste, and recommend upgrades to protect your lawn.\n\n"
        f"Reply to this email or visit greenlandscapingirrigation.com to schedule.\n\n"
        f"Green Landscape Irrigation | Tampa, FL\n"
        f"To unsubscribe, reply UNSUBSCRIBE."
    )


# ---------------------------------------------------------------------------
# SMS
# ---------------------------------------------------------------------------

def sms_intro(lead: dict) -> str:
    """First SMS — introduction + offer."""
    name = _first_name(lead.get("name") or "")
    address = lead.get("address", "your new home")
    greeting = f"Hi {name}! " if name != "Neighbor" else "Hi! "
    return (
        f"{greeting}This is Green Landscape Irrigation in Tampa. "
        f"Congrats on your new home at {address}! "
        f"We offer FREE irrigation assessments for new homeowners. "
        f"Interested? Reply YES or visit greenlandscapingirrigation.com. "
        f"Reply STOP to opt out."
    )


def sms_followup(lead: dict) -> str:
    """Follow-up SMS — sent 48h after intro if no response."""
    name = _first_name(lead.get("name") or "")
    greeting = f"Hi {name}, " if name != "Neighbor" else ""
    return (
        f"{greeting}Green Landscape Irrigation here. "
        f"Just following up on our free irrigation assessment offer for your new home. "
        f"Takes only 30 minutes and could save you money on your water bill. "
        f"Call us or reply YES to schedule. Reply STOP to opt out."
    )

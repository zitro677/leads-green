# ADR-002 — Voicebot Stack Selection

**Date**: 2025-04  
**Status**: Accepted

---

## Context

Leads need to be contacted within **5 minutes** of capture to maximize conversion (Harvard Business Review: 100x more likely to qualify if contacted within 5 min vs 30 min). A human team cannot do this consistently. We need a voicebot that:

- Calls outbound
- Speaks naturally (no robotic voice)
- Qualifies the lead (3–4 questions)
- Books an estimate on Calendly
- Hands off to human if requested

---

## Decision: VAPI + ElevenLabs

### VAPI (Voice AI Platform)
- **Role**: Call orchestration, telephony, conversation management
- **Pros**: Native outbound calls, webhook-driven, cheap ($0.05/min), great LLM integration
- **Cons**: Requires prompt engineering discipline

### ElevenLabs
- **Role**: Voice synthesis for "Jimmy"
- **Voice profile**: Male, warm, professional, American English — Tampa-friendly
- **Pros**: Most natural voice synthesis available, cloning option
- **Latency**: ~300ms (acceptable for conversation)

### LLM: Claude (via VAPI integration)
- **Model**: claude-sonnet-4-20250514
- **Role**: Conversation logic, objection handling, qualification
- **System prompt**: See `tools/prompts/jimmy_v1.md`

---

## Jimmy's Qualification Script (Summary)

```
1. INTRO (15s)
   "Hi, this is Jimmy calling from Green Landscape Irrigation in Tampa.
    Is this [Name]? We noticed you recently [moved in / pulled a permit / 
    posted about landscaping]. Do you have 2 minutes?"

2. QUALIFY (60–90s)
   Q1: "Are you looking for irrigation repair, a new system installation, 
        or general landscaping help?"
   Q2: "Is this for a home or commercial property?"
   Q3: "Are you looking to get this done in the next few weeks, or 
        more of a future project?"

3. BOOK (30s)
   "We'd love to offer you a free estimate. I can book you for [Day] 
    at [Time] — does that work?"
   → Calendly API booking

4. HANDOFF
   "Great! You'll get a confirmation text. If you have any questions 
    before then, feel free to call us at [number]."
```

---

## Call Timing Rules (TCPA)

```python
CALL_WINDOW = {
    "start": "08:00",   # 8 AM ET
    "end": "21:00",     # 9 PM ET
    "timezone": "America/New_York",
    "days": ["MON", "TUE", "WED", "THU", "FRI", "SAT"]
}
MAX_ATTEMPTS_PER_LEAD = 3
MIN_HOURS_BETWEEN_ATTEMPTS = 24
```

---

## Voicebot → Human Escalation Triggers

- Lead says "speak to a person"
- Lead shows frustration (tone analysis)
- Lead is a **commercial property** (high value → human touch)
- Lead wants to negotiate price
- Jimmy cannot answer a technical question

Escalation: send Telegram alert to owner with transcript.

---

## Alternatives Rejected

| Option | Why Rejected |
|---|---|
| Bland.ai | More expensive, less flexible |
| Twilio + custom | Too much infrastructure overhead |
| Retell AI | Higher latency, less customizable |
| Human SDR | Cost $15–25/hour, can't scale to 5-min response |
| Flowise voicebot | Not optimized for telephony |

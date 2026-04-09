"""
Pydantic models matching the Supabase schema.
Source of truth: schema.sql
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SignalType = Literal["new_construction", "new_owner", "complaint", "request", "unknown"]
LeadStatus = Literal["new", "queued", "calling", "qualified", "booked", "lost", "exhausted"]
PropertyType = Literal["residential", "commercial"]
CallOutcomeType = Literal[
    "no_answer", "voicemail", "not_interested", "qualified", "booked", "escalated"
]


class LeadRaw(BaseModel):
    """Raw lead from a scraper before enrichment/scoring."""

    source: str
    source_id: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str
    city: str = "Tampa"
    zip_code: str | None = None
    signal: str | None = None
    signal_type: SignalType = "unknown"
    property_type: PropertyType = "residential"
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    raw_json: dict[str, Any] | None = None


class Lead(BaseModel):
    """Enriched + scored lead stored in Supabase."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    source: str
    source_id: str | None = None
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str
    city: str = "Tampa"
    zip_code: str | None = None
    lat: float | None = None
    lon: float | None = None
    property_type: PropertyType = "residential"
    signal: str | None = None
    signal_type: SignalType = "unknown"
    score: int = 0
    score_reason: str | None = None
    status: LeadStatus = "new"
    retry_count: int = 0
    vapi_call_id: str | None = None
    assigned_to: str | None = None
    notes: str | None = None
    email_sent_at: datetime | None = None
    sms_sent_at: datetime | None = None
    raw_json: dict[str, Any] | None = None
    scraped_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CallOutcome(BaseModel):
    """Record of a VAPI call attempt."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    lead_id: uuid.UUID
    vapi_call_id: str
    attempt_number: int = 1
    duration_seconds: int | None = None
    outcome: CallOutcomeType | None = None
    transcript: str | None = None
    summary: str | None = None
    booked_at: datetime | None = None
    calendly_event_id: str | None = None
    recording_url: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ScoringResult(BaseModel):
    score: int
    reason: str
    action: Literal["call", "review", "discard"]

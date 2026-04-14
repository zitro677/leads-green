-- Migration 004: appointment fields on leads
-- Stores the booked appointment date and any notes from the VAPI call.

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS appointment_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS appointment_notes TEXT;

COMMENT ON COLUMN leads.appointment_at    IS 'Scheduled appointment date/time (set when status = booked)';
COMMENT ON COLUMN leads.appointment_notes IS 'Summary from VAPI call or manual notes for the appointment';

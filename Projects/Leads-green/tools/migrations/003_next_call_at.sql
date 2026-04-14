-- Migration 003: add next_call_at to leads
-- Allows scheduling retries 24 hours after a no-answer or voicemail.

ALTER TABLE leads
    ADD COLUMN IF NOT EXISTS next_call_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_leads_next_call_at
    ON leads(next_call_at)
    WHERE status = 'queued' AND next_call_at IS NOT NULL;

COMMENT ON COLUMN leads.next_call_at IS
    'Earliest timestamp when a retry call may be placed. NULL = call immediately.';

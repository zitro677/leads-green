-- ============================================
-- Green Landscape Irrigation — Supabase Schema
-- ============================================

-- LEADS TABLE
CREATE TABLE leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,           -- "hillsborough_permits", "zillow", "facebook", etc.
    source_id TEXT,                 -- unique ID from source system
    name TEXT,
    phone TEXT,
    email TEXT,
    address TEXT NOT NULL,
    city TEXT DEFAULT 'Tampa',
    zip_code TEXT,
    lat FLOAT,
    lon FLOAT,
    property_type TEXT DEFAULT 'residential',  -- "residential" | "commercial"
    signal TEXT,                    -- raw text that triggered capture
    signal_type TEXT,               -- "new_construction" | "new_owner" | "complaint" | "request"
    score INTEGER DEFAULT 0,        -- 0–100
    score_reason TEXT,
    status TEXT DEFAULT 'new',      -- "new" | "queued" | "calling" | "qualified" | "booked" | "lost" | "exhausted"
    retry_count INTEGER DEFAULT 0,
    vapi_call_id TEXT,
    assigned_to TEXT,
    notes TEXT,
    email_sent_at TIMESTAMPTZ,
    sms_sent_at TIMESTAMPTZ,
    raw_json JSONB,
    scraped_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(source, source_id)       -- prevent duplicates
);

-- CALL OUTCOMES TABLE
CREATE TABLE call_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID REFERENCES leads(id) ON DELETE CASCADE,
    vapi_call_id TEXT UNIQUE,
    attempt_number INTEGER DEFAULT 1,
    duration_seconds INTEGER,
    outcome TEXT,                   -- "no_answer" | "voicemail" | "not_interested" | "qualified" | "booked" | "escalated"
    transcript TEXT,
    summary TEXT,
    booked_at TIMESTAMPTZ,          -- Calendly booking time
    calendly_event_id TEXT,
    recording_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- DO NOT CALL LIST
CREATE TABLE dnc_list (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone TEXT UNIQUE NOT NULL,
    reason TEXT,                    -- "requested" | "tcpa" | "competitor"
    added_at TIMESTAMPTZ DEFAULT now()
);

-- SOURCE STATS (for weekly report)
CREATE TABLE source_stats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    week_start DATE NOT NULL,
    source TEXT NOT NULL,
    leads_captured INTEGER DEFAULT 0,
    leads_called INTEGER DEFAULT 0,
    leads_booked INTEGER DEFAULT 0,
    avg_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(week_start, source)
);

-- INDEXES
CREATE INDEX idx_leads_status ON leads(status);
CREATE INDEX idx_leads_score ON leads(score DESC);
CREATE INDEX idx_leads_source ON leads(source);
CREATE INDEX idx_leads_created ON leads(created_at DESC);
CREATE INDEX idx_leads_zip ON leads(zip_code);
CREATE INDEX idx_call_outcomes_lead ON call_outcomes(lead_id);
CREATE INDEX idx_leads_phone ON leads(phone);
CREATE INDEX idx_leads_vapi_call_id ON leads(vapi_call_id);

-- AUTO-UPDATE updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER leads_updated_at
    BEFORE UPDATE ON leads
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- VIEW: Dashboard summary
CREATE VIEW dashboard_summary AS
SELECT
    date_trunc('week', created_at) as week,
    source,
    COUNT(*) as total_leads,
    COUNT(*) FILTER (WHERE score >= 55) as high_score_leads,
    COUNT(*) FILTER (WHERE status = 'booked') as booked,
    ROUND(AVG(score), 1) as avg_score
FROM leads
GROUP BY 1, 2
ORDER BY 1 DESC, 3 DESC;

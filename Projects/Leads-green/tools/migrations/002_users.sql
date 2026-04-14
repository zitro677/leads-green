-- Migration 002: users table for JWT login + role-based access
-- Run once against your Supabase project (SQL Editor or psql)

CREATE TABLE IF NOT EXISTS users (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username     TEXT        UNIQUE NOT NULL,
    hashed_password TEXT     NOT NULL,
    role         TEXT        NOT NULL DEFAULT 'viewer'
                             CHECK (role IN ('admin', 'viewer')),
    is_active    BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Trigger to keep updated_at fresh
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS users_updated_at ON users;
CREATE TRIGGER users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Seed: initial admin (password must be changed after first login)
-- Password here is: changeme123  — replace immediately in production
-- Hash generated with: python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('changeme123'))"
-- Default password: changeme123  — CHANGE THIS IMMEDIATELY after first login
INSERT INTO users (username, hashed_password, role)
VALUES (
    'admin',
    '$2b$12$xZiBl6p6WPprNS2KH8gL/emBqA0WCymm1XqRsv.gB.ty8omHI5FLa',
    'admin'
)
ON CONFLICT (username) DO NOTHING;

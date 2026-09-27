-- Kasir JWT auth: stateful refresh tokens (revocable/rotatable), see
-- ppob-api/docs/backend-architecture.md and api/services/auth_service.py.
-- Only token_hash (SHA-256 of the opaque refresh token) is stored, never the
-- token itself — same reasoning as password hashing.

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INT NOT NULL REFERENCES users(id),
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Demo Kasir account for local testing (matches ppop-frontend's existing
-- hardcoded demo login kasir1/kasir123). No registration endpoint exists;
-- Kasir accounts are provisioned manually.
INSERT INTO users (username, password) VALUES
    ('kasir1', '$2b$12$U3plfjzrKP3kz56M1P7xd.b/lkpAdI5dygEXej6mgm4VeqMJkaORK')
ON CONFLICT (username) DO NOTHING;

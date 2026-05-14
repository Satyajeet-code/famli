-- =============================================================================
-- Retirement Chatbot Schema (Postgres)
-- =============================================================================
-- Apply with: psql "$DATABASE_URL" -f schema.sql
-- Idempotent: safe to re-run.
-- =============================================================================


-- Priority enum for retirement goal importance.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'priority_enum') THEN
        CREATE TYPE priority_enum AS ENUM ('Essential', 'Important', 'Aspirational');
    END IF;
END
$$;


-- =============================================================================
-- users_dummy
-- =============================================================================
CREATE TABLE IF NOT EXISTS users_dummy (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    first_name    VARCHAR(100) NOT NULL,
    last_name     VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);


-- =============================================================================
-- chat_history_dummy
-- =============================================================================
-- Append-only log of chat turns between user and the retirement bot.
-- =============================================================================
CREATE TABLE IF NOT EXISTS chat_history_dummy (
    id         BIGSERIAL    PRIMARY KEY,
    user_id    INTEGER      NOT NULL REFERENCES users_dummy(id) ON DELETE CASCADE,
    role       VARCHAR(20)  NOT NULL CHECK (role IN ('user', 'assistant')),
    message    TEXT         NOT NULL,
    created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_history_dummy_user_created
    ON chat_history_dummy (user_id, created_at);


-- =============================================================================
-- retirement_inputs_dummy
-- =============================================================================
-- One row per user. Upserted as the chatbot extracts values. NULL columns
-- mean "not yet collected"; populated columns are used as defaults the next
-- time the user starts the conversation.
-- =============================================================================
CREATE TABLE IF NOT EXISTS retirement_inputs_dummy (
    user_id         INTEGER       PRIMARY KEY REFERENCES users_dummy(id) ON DELETE CASCADE,
    goal_name       TEXT          NULL,
    priority        priority_enum NULL,
    beneficiary     TEXT          NULL,
    current_age     INTEGER       NULL,
    retirement_age  INTEGER       NULL,
    life_expectancy INTEGER       NULL,
    monthly_expense NUMERIC(15,2) NULL,
    inflation_rate  NUMERIC(5,4)  NULL,  -- 0.06 == 6%
    expected_return NUMERIC(5,4)  NULL,  -- 0.07 == 7%
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

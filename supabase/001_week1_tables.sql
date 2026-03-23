-- ============================================================
-- STRATEGY 5.x GROWTH SYSTEM — WEEK 1 DATABASE SCHEMA
-- Target: Supabase PostgreSQL
-- Created: 2026-03-23
-- Tables: positions, rules, scoring_runs, alerts,
--         pipeline_candidates, precommitment_plans
-- ============================================================
-- Run this script in the Supabase SQL Editor (or via psql).
-- It is idempotent-safe for first run. For re-runs, drop
-- tables in reverse order or use a fresh project.
-- ============================================================

-- Enable UUID generation (Supabase has this by default, but be explicit)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- UTILITY: updated_at trigger function
-- Reused by all mutable tables
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- TABLE 1: positions
-- Current live portfolio state — single source of truth
-- Lifecycle: Mutable — rows upserted on each Moomoo sync
-- ============================================================
CREATE TABLE positions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id   TEXT NOT NULL,
    ticker              TEXT NOT NULL,
    security_name       TEXT,
    asset_type          TEXT NOT NULL DEFAULT 'equity',
    quantity            NUMERIC(18,4) NOT NULL,
    avg_cost            NUMERIC(18,6) NOT NULL,
    last_price          NUMERIC(18,6),
    market_value        NUMERIC(18,2),
    unrealized_pnl      NUMERIC(18,2),
    unrealized_pnl_pct  NUMERIC(8,4),
    currency            TEXT NOT NULL DEFAULT 'USD',
    fx_rate_to_sgd      NUMERIC(18,6),
    catalyst_date       DATE,
    catalyst_type       TEXT,
    playbook            TEXT,
    binary_risk_flag    BOOLEAN NOT NULL DEFAULT false,
    status              TEXT NOT NULL DEFAULT 'open',
    source_ref          TEXT NOT NULL,
    source_fresh_at     TIMESTAMPTZ NOT NULL,
    position_hash       TEXT NOT NULL,
    notes               TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: one row per ticker per broker account
    CONSTRAINT uq_positions_broker_ticker UNIQUE (broker_account_id, ticker),

    -- CHECK constraints
    CONSTRAINT chk_positions_status CHECK (status IN ('open', 'closed', 'pending')),
    CONSTRAINT chk_positions_asset_type CHECK (asset_type IN ('equity', 'etf', 'option', 'other')),
    CONSTRAINT chk_positions_playbook CHECK (
        playbook IS NULL OR playbook IN ('A', 'B', 'C', 'D', 'E')
    ),
    CONSTRAINT chk_positions_catalyst_type CHECK (
        catalyst_type IS NULL OR catalyst_type IN (
            'PDUFA', 'ADCOM', 'PHASE3_READOUT', 'PHASE2_READOUT',
            'REGEN', 'EARNINGS', 'MACRO', 'OTHER'
        )
    ),
    CONSTRAINT chk_positions_quantity_positive CHECK (quantity > 0 OR status = 'closed')
);

-- Indexes
CREATE INDEX idx_positions_ticker ON positions(ticker);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_broker_account ON positions(broker_account_id);
CREATE INDEX idx_positions_catalyst_date ON positions(catalyst_date) WHERE catalyst_date IS NOT NULL;
CREATE INDEX idx_positions_binary_risk ON positions(binary_risk_flag) WHERE binary_risk_flag = true;

-- Auto-update updated_at on every UPDATE
CREATE TRIGGER trg_positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ============================================================
-- TABLE 2: rules
-- Versioned Constitution rules — append-only
-- Hard Bans, scoring thresholds, concentration caps
-- ============================================================
CREATE TABLE rules (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_version          INTEGER NOT NULL,
    rule_code             TEXT NOT NULL,
    rule_category         TEXT NOT NULL,
    rule_name             TEXT NOT NULL,
    rule_text             TEXT NOT NULL,
    rule_logic            JSONB NOT NULL,
    severity              TEXT NOT NULL,
    playbooks_applicable  TEXT[] NOT NULL DEFAULT '{A,B,C,D,E}',
    is_immutable          BOOLEAN NOT NULL DEFAULT false,
    active                BOOLEAN NOT NULL DEFAULT true,
    effective_from        TIMESTAMPTZ NOT NULL DEFAULT now(),
    supersedes_rule_id    UUID REFERENCES rules(id),
    changed_by            TEXT NOT NULL,
    change_reason         TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: same rule code cannot have duplicate version numbers
    CONSTRAINT uq_rules_code_version UNIQUE (rule_code, rule_version),

    -- CHECK constraints
    CONSTRAINT chk_rules_severity CHECK (severity IN ('block', 'warn', 'info')),
    CONSTRAINT chk_rules_category CHECK (
        rule_category IN (
            'hard_ban', 'concentration', 'scoring_threshold',
            'position_sizing', 'data_quality', 'playbook_gate',
            'risk_management', 'other'
        )
    ),
    CONSTRAINT chk_rules_change_reason_notempty CHECK (length(trim(change_reason)) > 0)
);

-- Indexes
CREATE INDEX idx_rules_code_active ON rules(rule_code, active);
CREATE INDEX idx_rules_version ON rules(rule_version);
CREATE INDEX idx_rules_category ON rules(rule_category);
CREATE INDEX idx_rules_active ON rules(active) WHERE active = true;


-- ============================================================
-- TABLE 3: scoring_runs
-- Immutable record of every scoring event — core audit table
-- Append-only: once written, never modified
-- ============================================================
CREATE TABLE scoring_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type                TEXT NOT NULL,
    ticker                  TEXT NOT NULL,
    candidate_id            UUID,  -- FK added after pipeline_candidates is created
    position_id             UUID REFERENCES positions(id),
    strategy_version        TEXT NOT NULL,
    rule_version            INTEGER NOT NULL,
    playbook                TEXT NOT NULL,
    input_data              JSONB NOT NULL DEFAULT '{}',
    input_price             NUMERIC(18,6),
    input_price_ts          TIMESTAMPTZ,
    sc1                     NUMERIC(4,2),
    sc2                     NUMERIC(4,2),
    sc3                     NUMERIC(4,2),
    sc4                     NUMERIC(4,2),
    sc5                     NUMERIC(4,2),
    sc6                     NUMERIC(4,2),
    sc7                     NUMERIC(4,2),
    sc8                     NUMERIC(4,2),
    composite_score         NUMERIC(5,2),
    scoring_method          TEXT NOT NULL DEFAULT 'deterministic',
    data_sources            JSONB NOT NULL DEFAULT '{}',
    bull_summary            TEXT,
    bear_summary            TEXT NOT NULL,
    da_verdict              TEXT NOT NULL,
    da_details              JSONB NOT NULL DEFAULT '{}',
    da_dissent_text         TEXT,
    da_override             BOOLEAN NOT NULL DEFAULT false,
    da_override_reason      TEXT,
    invalidation_conditions JSONB NOT NULL DEFAULT '[]',
    verdict                 TEXT NOT NULL,
    verdict_reason          TEXT NOT NULL,
    portfolio_context       JSONB NOT NULL DEFAULT '{}',
    run_status              TEXT NOT NULL DEFAULT 'complete',
    idempotency_key         TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: prevents duplicate scoring runs from retried jobs
    CONSTRAINT uq_scoring_runs_idempotency UNIQUE (idempotency_key),

    -- CHECK constraints
    CONSTRAINT chk_scoring_runs_run_type CHECK (
        run_type IN ('radar', 'manual', 'review', 'event_recheck', 'scheduled', 'requalify')
    ),
    CONSTRAINT chk_scoring_runs_playbook CHECK (playbook IN ('A', 'B', 'C', 'D', 'E')),
    CONSTRAINT chk_scoring_runs_da_verdict CHECK (
        da_verdict IN ('PROCEED', 'CAUTION', 'BLOCK')
    ),
    CONSTRAINT chk_scoring_runs_verdict CHECK (
        verdict IN ('entry_ready', 'watch', 'monitor', 'hold', 'trim', 'exit', 'block', 'eliminate')
    ),
    CONSTRAINT chk_scoring_runs_run_status CHECK (
        run_status IN ('complete', 'partial', 'invalid', 'error')
    ),
    CONSTRAINT chk_scoring_runs_scoring_method CHECK (
        scoring_method IN ('deterministic', 'ai_only', 'hybrid', 'manual')
    ),
    -- All SC axes must be 0-10 range
    CONSTRAINT chk_scoring_runs_sc_range CHECK (
        (sc1 IS NULL OR (sc1 >= 0 AND sc1 <= 10)) AND
        (sc2 IS NULL OR (sc2 >= 0 AND sc2 <= 10)) AND
        (sc3 IS NULL OR (sc3 >= 0 AND sc3 <= 10)) AND
        (sc4 IS NULL OR (sc4 >= 0 AND sc4 <= 10)) AND
        (sc5 IS NULL OR (sc5 >= 0 AND sc5 <= 10)) AND
        (sc6 IS NULL OR (sc6 >= 0 AND sc6 <= 10)) AND
        (sc7 IS NULL OR (sc7 >= 0 AND sc7 <= 10)) AND
        (sc8 IS NULL OR (sc8 >= 0 AND sc8 <= 10))
    ),
    -- If DA override, must provide reason
    CONSTRAINT chk_scoring_runs_override_reason CHECK (
        da_override = false OR (da_override = true AND length(trim(da_override_reason)) > 0)
    ),
    -- Bear summary is forced — DA presence required
    CONSTRAINT chk_scoring_runs_bear_notempty CHECK (length(trim(bear_summary)) > 0)
);

-- Indexes
CREATE INDEX idx_scoring_runs_ticker ON scoring_runs(ticker);
CREATE INDEX idx_scoring_runs_created ON scoring_runs(created_at);
CREATE INDEX idx_scoring_runs_candidate ON scoring_runs(candidate_id) WHERE candidate_id IS NOT NULL;
CREATE INDEX idx_scoring_runs_run_type ON scoring_runs(run_type);
CREATE INDEX idx_scoring_runs_verdict ON scoring_runs(verdict);
CREATE INDEX idx_scoring_runs_playbook ON scoring_runs(playbook);


-- ============================================================
-- TABLE 4: alerts
-- Alert queue, delivery log, acknowledgment tracking
-- Mixed: created as append-only, delivery fields updated
-- ============================================================
CREATE TABLE alerts (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type                  TEXT NOT NULL,
    priority                    TEXT NOT NULL,
    ticker                      TEXT,
    position_id                 UUID REFERENCES positions(id),
    scoring_run_id              UUID REFERENCES scoring_runs(id),
    title                       TEXT NOT NULL,
    body                        TEXT NOT NULL,
    precommitted_plan_summary   TEXT,
    action_required             BOOLEAN NOT NULL DEFAULT false,
    action_payload              JSONB,
    channel                     TEXT NOT NULL DEFAULT 'telegram',
    delivery_status             TEXT NOT NULL DEFAULT 'queued',
    delivery_attempts           INTEGER NOT NULL DEFAULT 0,
    telegram_message_id         TEXT,
    dedupe_key                  TEXT NOT NULL,
    sent_at                     TIMESTAMPTZ,
    delivered_at                TIMESTAMPTZ,
    acknowledged_at             TIMESTAMPTZ,
    user_response               TEXT,
    expires_at                  TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: prevents duplicate alerts for the same event
    CONSTRAINT uq_alerts_dedupe UNIQUE (dedupe_key),

    -- CHECK constraints
    CONSTRAINT chk_alerts_type CHECK (
        alert_type IN (
            'catalyst', 'price_move', 'stale_data', 'rule_break',
            'morning_brief', 'heartbeat', 'countdown', 'reflection_prompt',
            'concentration_warning', 'system_error'
        )
    ),
    CONSTRAINT chk_alerts_priority CHECK (
        priority IN ('critical', 'high', 'normal', 'silent')
    ),
    CONSTRAINT chk_alerts_channel CHECK (
        channel IN ('telegram', 'email', 'both')
    ),
    CONSTRAINT chk_alerts_delivery_status CHECK (
        delivery_status IN (
            'queued', 'sending', 'sent', 'delivered',
            'acknowledged', 'failed', 'expired', 'superseded'
        )
    )
);

-- Indexes
CREATE INDEX idx_alerts_status ON alerts(delivery_status);
CREATE INDEX idx_alerts_type_created ON alerts(alert_type, created_at);
CREATE INDEX idx_alerts_ticker ON alerts(ticker) WHERE ticker IS NOT NULL;
CREATE INDEX idx_alerts_pending ON alerts(delivery_status)
    WHERE delivery_status IN ('queued', 'sending');
CREATE INDEX idx_alerts_unacked ON alerts(delivery_status, action_required)
    WHERE delivery_status = 'delivered' AND action_required = true;


-- ============================================================
-- TABLE 5: pipeline_candidates
-- Candidate lifecycle: radar → watchlist → scored → deployed
-- Mutable: status field changes as candidates progress
-- ============================================================
CREATE TABLE pipeline_candidates (
    id                                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker                            TEXT NOT NULL,
    company_name                      TEXT,
    status                            TEXT NOT NULL DEFAULT 'candidate',
    status_history                    JSONB NOT NULL DEFAULT '[]',
    playbook                          TEXT,
    catalyst_date                     DATE,
    catalyst_type                     TEXT,
    catalyst_confidence               TEXT NOT NULL DEFAULT 'unverified',
    source_radar_session_id           UUID,  -- FK added in Week 2 when radar_sessions is created
    discovery_source                  TEXT NOT NULL,
    latest_scoring_run_id             UUID REFERENCES scoring_runs(id),
    latest_composite_score            NUMERIC(5,2),
    rejection_reason                  TEXT,
    requalify_trigger                 TEXT,
    requalify_date                    DATE,
    false_negative_flag               BOOLEAN NOT NULL DEFAULT false,
    false_negative_price_at_rejection NUMERIC(18,6),
    false_negative_peak_price         NUMERIC(18,6),
    owner_note                        TEXT,
    discovered_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: one candidate entry per ticker per catalyst event
    CONSTRAINT uq_pipeline_ticker_catalyst UNIQUE (ticker, catalyst_date),

    -- CHECK constraints
    CONSTRAINT chk_pipeline_status CHECK (
        status IN (
            'candidate', 'watchlist', 'scoring', 'entry_ready',
            'deployed', 'rejected', 'eliminated', 'p3_watch', 'archived'
        )
    ),
    CONSTRAINT chk_pipeline_playbook CHECK (
        playbook IS NULL OR playbook IN ('A', 'B', 'C', 'D', 'E')
    ),
    CONSTRAINT chk_pipeline_catalyst_type CHECK (
        catalyst_type IS NULL OR catalyst_type IN (
            'PDUFA', 'ADCOM', 'PHASE3_READOUT', 'PHASE2_READOUT',
            'REGEN', 'EARNINGS', 'MACRO', 'OTHER'
        )
    ),
    CONSTRAINT chk_pipeline_catalyst_confidence CHECK (
        catalyst_confidence IN ('confirmed', 'tentative', 'unverified', 'postponed')
    ),
    CONSTRAINT chk_pipeline_discovery_source CHECK (
        discovery_source IN (
            'radar_lane_1', 'radar_lane_2', 'radar_lane_3', 'radar_lane_4',
            'radar_lane_5', 'radar_lane_6', 'radar_lane_7', 'radar_lane_8',
            'radar_lane_9', 'radar_lane_10', 'manual', 'biopharmcatalyst',
            'tip', 'news', 'existing_position'
        )
    )
);

-- Indexes
CREATE INDEX idx_pipeline_ticker ON pipeline_candidates(ticker);
CREATE INDEX idx_pipeline_status ON pipeline_candidates(status);
CREATE INDEX idx_pipeline_catalyst_date ON pipeline_candidates(catalyst_date) WHERE catalyst_date IS NOT NULL;
CREATE INDEX idx_pipeline_false_negative ON pipeline_candidates(false_negative_flag) WHERE false_negative_flag = true;
CREATE INDEX idx_pipeline_requalify ON pipeline_candidates(requalify_date) WHERE status = 'p3_watch';

-- Auto-update updated_at
CREATE TRIGGER trg_pipeline_candidates_updated_at
    BEFORE UPDATE ON pipeline_candidates
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Deferred FK: scoring_runs.candidate_id → pipeline_candidates.id
ALTER TABLE scoring_runs
    ADD CONSTRAINT fk_scoring_runs_candidate
    FOREIGN KEY (candidate_id)
    REFERENCES pipeline_candidates(id);

-- NOTE: FK from pipeline_candidates.source_radar_session_id → radar_sessions.id
-- will be added in 002_week2_tables.sql after radar_sessions is created.


-- ============================================================
-- TABLE 6: precommitment_plans
-- Pre-committed action plans for binary catalyst positions
-- Append-only: revisions create new rows via supersedes_plan_id
-- ============================================================
CREATE TABLE precommitment_plans (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id             UUID NOT NULL REFERENCES positions(id),
    candidate_id            UUID REFERENCES pipeline_candidates(id),
    ticker                  TEXT NOT NULL,
    catalyst_date           DATE NOT NULL,
    catalyst_type           TEXT NOT NULL,
    if_approval             JSONB NOT NULL,
    if_rejection            JSONB NOT NULL,
    if_mixed                JSONB,
    if_no_news              JSONB,
    position_size_at_plan   NUMERIC(18,4) NOT NULL,
    entry_price_at_plan     NUMERIC(18,6) NOT NULL,
    max_acceptable_loss     NUMERIC(18,2),
    stop_price              NUMERIC(18,6),
    is_active               BOOLEAN NOT NULL DEFAULT true,
    supersedes_plan_id      UUID REFERENCES precommitment_plans(id),
    plan_followed           BOOLEAN,
    plan_deviation_notes    TEXT,
    confirmed_at            TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- CHECK constraints
    CONSTRAINT chk_precommit_catalyst_type CHECK (
        catalyst_type IN (
            'PDUFA', 'ADCOM', 'PHASE3_READOUT', 'PHASE2_READOUT',
            'REGEN', 'EARNINGS', 'MACRO', 'OTHER'
        )
    ),
    -- JSONB action plans must contain an "action" key
    CONSTRAINT chk_precommit_approval_valid CHECK (
        if_approval ? 'action' AND (if_approval->>'action') IS NOT NULL
    ),
    CONSTRAINT chk_precommit_rejection_valid CHECK (
        if_rejection ? 'action' AND (if_rejection->>'action') IS NOT NULL
    )
);

-- Partial unique index: only one active plan per position
CREATE UNIQUE INDEX uq_precommit_active_per_position
    ON precommitment_plans(position_id)
    WHERE is_active = true;

-- Indexes
CREATE INDEX idx_precommit_position ON precommitment_plans(position_id);
CREATE INDEX idx_precommit_catalyst_date ON precommitment_plans(catalyst_date);
CREATE INDEX idx_precommit_active ON precommitment_plans(is_active) WHERE is_active = true;
CREATE INDEX idx_precommit_ticker ON precommitment_plans(ticker);


-- ============================================================
-- ROW LEVEL SECURITY (RLS)
-- Single-user system: enable RLS for Supabase best practice,
-- but allow all operations for now. Tighten in production.
-- ============================================================
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE scoring_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE precommitment_plans ENABLE ROW LEVEL SECURITY;

-- Permissive policies — allow all for authenticated users
CREATE POLICY "Allow all for authenticated" ON positions
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON rules
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON scoring_runs
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON alerts
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON pipeline_candidates
    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON precommitment_plans
    FOR ALL USING (true) WITH CHECK (true);

-- service_role key automatically bypasses RLS in Supabase (for Python scripts)


-- ============================================================
-- SEED DATA: Constitution Rules (v1)
-- Hard Bans, concentration caps, scoring thresholds, gates
-- ============================================================

INSERT INTO rules (
    rule_version, rule_code, rule_category, rule_name, rule_text,
    rule_logic, severity, playbooks_applicable, is_immutable,
    changed_by, change_reason
) VALUES

-- Hard Ban 1: No Leveraged/Inverse ETFs
(1, 'hard_ban_leveraged_etf', 'hard_ban', 'No Leveraged/Inverse ETFs',
 'BAN 1: No positions in leveraged or inverse ETFs including but not limited to 2x, 3x, -1x products.',
 '{"type": "asset_type_ban", "banned_keywords": ["leveraged", "inverse", "2x", "3x", "-1x", "ultra"]}',
 'block', '{A,B,C,D,E}', true, 'system_init', 'Initial Constitution load'),

-- Hard Ban 3: No Position Without Dated Catalyst (Playbooks A/B)
(1, 'hard_ban_no_catalyst', 'hard_ban', 'No Position Without Dated Catalyst (A/B)',
 'BAN 3: For Playbooks A and B, no position may be opened without a confirmed catalyst date.',
 '{"type": "field_required", "field": "catalyst_date", "condition": "not_null", "playbooks": ["A", "B"]}',
 'block', '{A,B}', true, 'system_init', 'Initial Constitution load'),

-- Hard Ban 4: No Deployment Beyond DEPLOY Balance
(1, 'hard_ban_deploy_budget', 'hard_ban', 'No Deployment Beyond DEPLOY Balance',
 'BAN 4: No new position may exceed the current DEPLOY bucket balance.',
 '{"type": "budget_check", "compare": "position_cost <= deploy_balance"}',
 'block', '{A,B,C,D,E}', true, 'system_init', 'Initial Constitution load'),

-- Concentration: Binary Exposure Cap 10%
(1, 'concentration_binary_10pct', 'concentration', 'Binary Exposure Cap 10%',
 'No more than 10% of portfolio NAV may be exposed to binary catalyst events within a 14-day window.',
 '{"type": "concentration_check", "max_pct": 10, "window_days": 14, "flag_field": "binary_risk_flag"}',
 'block', '{A,B,C}', true, 'system_init', 'Initial Constitution load'),

-- Risk Management: Margin Utilization Cap 40%
(1, 'margin_utilization_40pct', 'risk_management', 'Margin Utilization Cap 40%',
 'If Total Position Market Value / NAV exceeds 40%, no new positions may be opened.',
 '{"type": "margin_check", "max_pct": 40}',
 'block', '{A,B,C,D,E}', true, 'system_init', 'Initial Constitution load'),

-- Scoring Threshold: SC5 Going Concern Gate
(1, 'sc5_going_concern', 'scoring_threshold', 'SC5 Going Concern Gate',
 'If SC5 (Company Financial Health) scores below 3.0, candidate is automatically blocked regardless of other axes.',
 '{"type": "axis_floor", "axis": "sc5", "min_score": 3.0, "action": "block"}',
 'block', '{A,B,C}', false, 'system_init', 'Initial Constitution load'),

-- Data Quality: Provenance Tags Required
(1, 'data_provenance_required', 'data_quality', 'Data Provenance Tags Required',
 'Every externally-sourced data point must carry a provenance tag: [CSV], [SEARCH], [FINANCE], [CALC], [PRIOR], [UNVERIFIED].',
 '{"type": "metadata_required", "field": "data_sources", "condition": "not_empty"}',
 'warn', '{A,B,C,D,E}', true, 'system_init', 'Initial Constitution load'),

-- Playbook Gate: D/E Gated Until N=15
(1, 'playbook_d_e_gate', 'playbook_gate', 'Playbooks D/E Gated Until N=15',
 'Playbooks D (MACRO) and E (OTHER) are not active until at least 15 completed round-trips in Playbooks A/B/C.',
 '{"type": "playbook_gate", "gated_playbooks": ["D", "E"], "required_n": 15, "count_playbooks": ["A", "B", "C"]}',
 'block', '{D,E}', false, 'system_init', 'Initial Constitution load — complexity freeze');


-- ============================================================
-- END OF WEEK 1 DDL
-- Next: 002_week2_tables.sql (trades, radar_sessions)
-- ============================================================

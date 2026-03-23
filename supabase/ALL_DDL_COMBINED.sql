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
-- ============================================================
-- STRATEGY 5.x GROWTH SYSTEM — WEEK 2 DATABASE SCHEMA
-- Target: Supabase PostgreSQL
-- Created: 2026-03-23
-- Tables: trades, radar_sessions
-- Depends on: 001_week1_tables.sql
-- ============================================================

-- ============================================================
-- TABLE 7: trades
-- Executed entry/exit records with full audit linkage
-- Append-only: trade records immutable once written
-- ============================================================
CREATE TABLE trades (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    broker_account_id       TEXT NOT NULL,
    broker_trade_id         TEXT,
    ticker                  TEXT NOT NULL,
    side                    TEXT NOT NULL,
    quantity                NUMERIC(18,4) NOT NULL,
    fill_price              NUMERIC(18,6) NOT NULL,
    fill_value              NUMERIC(18,2) NOT NULL,
    commission              NUMERIC(18,2),
    filled_at               TIMESTAMPTZ NOT NULL,
    position_id             UUID REFERENCES positions(id),
    scoring_run_id          UUID REFERENCES scoring_runs(id),
    precommitment_plan_id   UUID REFERENCES precommitment_plans(id),
    trade_context           TEXT NOT NULL,
    catalyst_outcome        TEXT,
    plan_adherence          TEXT,
    deviation_reason        TEXT,
    realized_pnl            NUMERIC(18,2),
    realized_pnl_pct        NUMERIC(8,4),
    holding_period_days     INTEGER,
    is_entry                BOOLEAN NOT NULL,
    linked_entry_trade_id   UUID REFERENCES trades(id),
    source_ref              TEXT NOT NULL,
    user_confirmed          BOOLEAN NOT NULL DEFAULT false,
    reflection_completed    BOOLEAN NOT NULL DEFAULT false,
    reflection_prompt_sent_at TIMESTAMPTZ,
    notes                   TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: dedup by broker trade ID if available
    CONSTRAINT uq_trades_broker_trade_id UNIQUE (broker_trade_id),

    -- CHECK constraints
    CONSTRAINT chk_trades_side CHECK (side IN ('BUY', 'SELL')),
    CONSTRAINT chk_trades_quantity_positive CHECK (quantity > 0),
    CONSTRAINT chk_trades_fill_price_positive CHECK (fill_price > 0),
    CONSTRAINT chk_trades_trade_context CHECK (
        trade_context IN (
            'catalyst_entry', 'catalyst_exit', 'scoring_entry',
            'stop_loss', 'take_profit', 'rebalance', 'manual',
            'dca', 'trim', 'close_all', 'other'
        )
    ),
    CONSTRAINT chk_trades_catalyst_outcome CHECK (
        catalyst_outcome IS NULL OR catalyst_outcome IN (
            'approval', 'CRL', 'mixed', 'no_news', 'positive_data',
            'negative_data', 'not_applicable'
        )
    ),
    CONSTRAINT chk_trades_plan_adherence CHECK (
        plan_adherence IS NULL OR plan_adherence IN ('followed', 'deviated', 'no_plan')
    ),
    CONSTRAINT chk_trades_source_ref_notempty CHECK (length(trim(source_ref)) > 0)
);

-- Indexes
CREATE INDEX idx_trades_ticker ON trades(ticker);
CREATE INDEX idx_trades_filled_at ON trades(filled_at);
CREATE INDEX idx_trades_position ON trades(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX idx_trades_broker_account ON trades(broker_account_id);
CREATE INDEX idx_trades_side ON trades(side);
CREATE INDEX idx_trades_is_entry ON trades(is_entry);
CREATE INDEX idx_trades_scoring_run ON trades(scoring_run_id) WHERE scoring_run_id IS NOT NULL;

-- RLS
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for authenticated" ON trades
    FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- TABLE 8: radar_sessions
-- Immutable log of each radar scan
-- Append-only: radar sessions are immutable records
-- ============================================================
CREATE TABLE radar_sessions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_type            TEXT NOT NULL,
    trigger                 TEXT NOT NULL,
    lanes_executed          TEXT[] NOT NULL,
    lanes_succeeded         TEXT[] NOT NULL DEFAULT '{}',
    lanes_failed            TEXT[] NOT NULL DEFAULT '{}',
    total_candidates_found  INTEGER NOT NULL DEFAULT 0,
    candidates_after_dedup  INTEGER NOT NULL DEFAULT 0,
    candidates_promoted     INTEGER NOT NULL DEFAULT 0,
    candidates_excluded     INTEGER NOT NULL DEFAULT 0,
    exclusion_list_used     JSONB NOT NULL DEFAULT '[]',
    data_sources            JSONB NOT NULL DEFAULT '{}',
    run_status              TEXT NOT NULL DEFAULT 'complete',
    error_log               JSONB,
    duration_seconds        INTEGER,
    started_at              TIMESTAMPTZ NOT NULL,
    completed_at            TIMESTAMPTZ,
    idempotency_key         TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: prevents duplicate radar sessions from retried jobs
    CONSTRAINT uq_radar_sessions_idempotency UNIQUE (idempotency_key),

    -- CHECK constraints
    CONSTRAINT chk_radar_session_type CHECK (
        session_type IN ('scheduled_weekly', 'manual', 'event_triggered', 'ad_hoc')
    ),
    CONSTRAINT chk_radar_run_status CHECK (
        run_status IN ('complete', 'partial', 'failed', 'running')
    ),
    CONSTRAINT chk_radar_candidates_nonneg CHECK (
        total_candidates_found >= 0 AND
        candidates_after_dedup >= 0 AND
        candidates_promoted >= 0 AND
        candidates_excluded >= 0
    )
);

-- Indexes
CREATE INDEX idx_radar_sessions_created ON radar_sessions(created_at);
CREATE INDEX idx_radar_sessions_type ON radar_sessions(session_type);
CREATE INDEX idx_radar_sessions_status ON radar_sessions(run_status);

-- RLS
ALTER TABLE radar_sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for authenticated" ON radar_sessions
    FOR ALL USING (true) WITH CHECK (true);

-- Now add the deferred FK from pipeline_candidates to radar_sessions
ALTER TABLE pipeline_candidates
    ADD CONSTRAINT fk_pipeline_radar_session
    FOREIGN KEY (source_radar_session_id)
    REFERENCES radar_sessions(id);


-- ============================================================
-- END OF WEEK 2 DDL
-- Next: 003_week3_tables.sql (score_outcomes, behavioral_metrics)
-- ============================================================
-- ============================================================
-- STRATEGY 5.x GROWTH SYSTEM — WEEK 3 DATABASE SCHEMA
-- Target: Supabase PostgreSQL
-- Created: 2026-03-23
-- Tables: score_outcomes, behavioral_metrics
-- Depends on: 001_week1_tables.sql, 002_week2_tables.sql
-- ============================================================

-- ============================================================
-- TABLE 9: score_outcomes
-- Per-axis 2×2 outcome tracking (TP/FP/TN/FN)
-- Links each SC axis score to actual trade result
-- Append-only: written once when a trade closes
-- ============================================================
CREATE TABLE score_outcomes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scoring_run_id  UUID NOT NULL REFERENCES scoring_runs(id),
    trade_id        UUID NOT NULL REFERENCES trades(id),
    ticker          TEXT NOT NULL,
    axis_name       TEXT NOT NULL,
    axis_score      NUMERIC(4,2) NOT NULL,
    threshold       NUMERIC(4,2) NOT NULL,
    above_threshold BOOLEAN NOT NULL,
    trade_outcome   TEXT NOT NULL,
    trade_pnl_pct   NUMERIC(8,4) NOT NULL,
    classification  TEXT NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: one outcome per axis per scoring-run-trade pair
    CONSTRAINT uq_score_outcomes_run_trade_axis UNIQUE (scoring_run_id, trade_id, axis_name),

    -- CHECK constraints
    CONSTRAINT chk_score_outcomes_axis_name CHECK (
        axis_name IN ('sc1', 'sc2', 'sc3', 'sc4', 'sc5', 'sc6', 'sc7', 'sc8')
    ),
    CONSTRAINT chk_score_outcomes_axis_range CHECK (
        axis_score >= 0 AND axis_score <= 10
    ),
    CONSTRAINT chk_score_outcomes_threshold_range CHECK (
        threshold >= 0 AND threshold <= 10
    ),
    CONSTRAINT chk_score_outcomes_trade_outcome CHECK (
        trade_outcome IN ('win', 'loss', 'breakeven')
    ),
    CONSTRAINT chk_score_outcomes_classification CHECK (
        classification IN ('true_positive', 'false_positive', 'true_negative', 'false_negative')
    )
);

-- Indexes
CREATE INDEX idx_score_outcomes_scoring_run ON score_outcomes(scoring_run_id);
CREATE INDEX idx_score_outcomes_trade ON score_outcomes(trade_id);
CREATE INDEX idx_score_outcomes_axis ON score_outcomes(axis_name);
CREATE INDEX idx_score_outcomes_classification ON score_outcomes(classification);
CREATE INDEX idx_score_outcomes_ticker ON score_outcomes(ticker);

-- RLS
ALTER TABLE score_outcomes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for authenticated" ON score_outcomes
    FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- TABLE 10: behavioral_metrics
-- Tracks user behavior patterns: override rates, time-to-decision,
-- plan adherence, alert response times
-- Append-only: each metric observation is point-in-time
-- ============================================================
CREATE TABLE behavioral_metrics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_type     TEXT NOT NULL,
    reference_type  TEXT NOT NULL,
    reference_id    UUID NOT NULL,
    ticker          TEXT,
    metric_value    NUMERIC(18,4) NOT NULL,
    metric_unit     TEXT NOT NULL,
    context         JSONB,
    observed_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Uniqueness: one metric per event
    CONSTRAINT uq_behavioral_metric_event UNIQUE (metric_type, reference_id, reference_type),

    -- CHECK constraints
    CONSTRAINT chk_behavioral_metric_type CHECK (
        metric_type IN (
            'alert_response_time', 'da_override', 'plan_adherence',
            'time_to_decision', 'reflection_timeliness', 'plan_deviation',
            'override_frequency', 'position_hold_duration'
        )
    ),
    CONSTRAINT chk_behavioral_reference_type CHECK (
        reference_type IN ('alert', 'trade', 'scoring_run', 'precommitment_plan')
    ),
    CONSTRAINT chk_behavioral_metric_unit CHECK (
        metric_unit IN (
            'seconds', 'minutes', 'hours', 'days',
            'boolean', 'count', 'percentage', 'ratio'
        )
    )
);

-- Indexes
CREATE INDEX idx_behavioral_metric_type ON behavioral_metrics(metric_type);
CREATE INDEX idx_behavioral_created ON behavioral_metrics(created_at);
CREATE INDEX idx_behavioral_reference ON behavioral_metrics(reference_type, reference_id);
CREATE INDEX idx_behavioral_ticker ON behavioral_metrics(ticker) WHERE ticker IS NOT NULL;

-- RLS
ALTER TABLE behavioral_metrics ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for authenticated" ON behavioral_metrics
    FOR ALL USING (true) WITH CHECK (true);


-- ============================================================
-- END OF WEEK 3 DDL
-- All 10 mandatory tables are now created.
-- Next: 004_views.sql (utility views)
-- ============================================================
-- ============================================================
-- STRATEGY 5.x GROWTH SYSTEM — UTILITY VIEWS
-- Target: Supabase PostgreSQL
-- Created: 2026-03-23
-- Views: v_active_positions, v_upcoming_catalysts,
--        v_portfolio_concentration, v_recent_alerts
-- Depends on: 001_week1_tables.sql
-- ============================================================

-- ============================================================
-- VIEW 1: v_active_positions
-- All open positions with pre-commitment plan context
-- and days-to-catalyst countdown
-- ============================================================
CREATE OR REPLACE VIEW v_active_positions AS
SELECT
    p.id,
    p.ticker,
    p.security_name,
    p.quantity,
    p.avg_cost,
    p.last_price,
    p.market_value,
    p.unrealized_pnl,
    p.unrealized_pnl_pct,
    p.currency,
    p.catalyst_date,
    p.catalyst_type,
    p.playbook,
    p.binary_risk_flag,
    p.source_fresh_at,
    p.notes,
    p.updated_at,
    -- Pre-commitment plan linkage
    pp.id AS active_plan_id,
    pp.if_approval,
    pp.if_rejection,
    pp.confirmed_at AS plan_confirmed_at,
    -- Computed: days until catalyst
    CASE
        WHEN p.catalyst_date IS NOT NULL
        THEN p.catalyst_date - CURRENT_DATE
        ELSE NULL
    END AS days_to_catalyst,
    -- Computed: staleness flag (>15 min since last sync)
    CASE
        WHEN p.source_fresh_at < now() - INTERVAL '15 minutes'
        THEN true
        ELSE false
    END AS is_stale
FROM positions p
LEFT JOIN precommitment_plans pp
    ON pp.position_id = p.id AND pp.is_active = true
WHERE p.status = 'open';

COMMENT ON VIEW v_active_positions IS
    'Open positions with active pre-commitment plans and catalyst countdown. Includes staleness flag.';


-- ============================================================
-- VIEW 2: v_upcoming_catalysts
-- Pipeline candidates with catalyst_date in the next 30 days
-- Ordered by urgency (nearest catalyst first)
-- ============================================================
CREATE OR REPLACE VIEW v_upcoming_catalysts AS
SELECT
    pc.id,
    pc.ticker,
    pc.company_name,
    pc.status,
    pc.playbook,
    pc.catalyst_date,
    pc.catalyst_type,
    pc.catalyst_confidence,
    pc.latest_composite_score,
    pc.discovery_source,
    pc.owner_note,
    -- Days until catalyst
    pc.catalyst_date - CURRENT_DATE AS days_to_catalyst,
    -- Is this ticker currently held?
    EXISTS (
        SELECT 1 FROM positions p
        WHERE p.ticker = pc.ticker AND p.status = 'open'
    ) AS is_held,
    -- Current position size if held
    (
        SELECT p.quantity FROM positions p
        WHERE p.ticker = pc.ticker AND p.status = 'open'
        LIMIT 1
    ) AS held_quantity
FROM pipeline_candidates pc
WHERE
    pc.catalyst_date IS NOT NULL
    AND pc.catalyst_date >= CURRENT_DATE
    AND pc.catalyst_date <= CURRENT_DATE + INTERVAL '30 days'
    AND pc.status NOT IN ('eliminated', 'archived')
ORDER BY pc.catalyst_date ASC, pc.latest_composite_score DESC NULLS LAST;

COMMENT ON VIEW v_upcoming_catalysts IS
    'Pipeline candidates with catalysts in the next 30 days, ordered by urgency. Shows held status.';


-- ============================================================
-- VIEW 3: v_portfolio_concentration
-- Position weights as % of total portfolio value
-- Includes binary risk breakdown
-- ============================================================
CREATE OR REPLACE VIEW v_portfolio_concentration AS
WITH portfolio_totals AS (
    SELECT
        COALESCE(SUM(market_value), 0) AS total_market_value,
        COUNT(*) AS position_count
    FROM positions
    WHERE status = 'open' AND market_value IS NOT NULL
)
SELECT
    p.id,
    p.ticker,
    p.security_name,
    p.quantity,
    p.avg_cost,
    p.last_price,
    p.market_value,
    p.playbook,
    p.catalyst_date,
    p.catalyst_type,
    p.binary_risk_flag,
    -- Weight as % of total portfolio
    CASE
        WHEN pt.total_market_value > 0
        THEN ROUND((p.market_value / pt.total_market_value) * 100, 2)
        ELSE 0
    END AS weight_pct,
    -- Portfolio totals (denormalized for convenience)
    pt.total_market_value,
    pt.position_count
FROM positions p
CROSS JOIN portfolio_totals pt
WHERE p.status = 'open' AND p.market_value IS NOT NULL
ORDER BY p.market_value DESC NULLS LAST;

COMMENT ON VIEW v_portfolio_concentration IS
    'Position-level portfolio weights as % of total market value. Use for concentration checks.';


-- ============================================================
-- VIEW 4: v_recent_alerts
-- Last 50 alerts with delivery status
-- Prioritized by recency and severity
-- ============================================================
CREATE OR REPLACE VIEW v_recent_alerts AS
SELECT
    a.id,
    a.alert_type,
    a.priority,
    a.ticker,
    a.title,
    a.body,
    a.precommitted_plan_summary,
    a.action_required,
    a.channel,
    a.delivery_status,
    a.delivery_attempts,
    a.sent_at,
    a.delivered_at,
    a.acknowledged_at,
    a.user_response,
    a.expires_at,
    a.created_at,
    -- Computed: response time in seconds (null if not acknowledged)
    CASE
        WHEN a.acknowledged_at IS NOT NULL AND a.sent_at IS NOT NULL
        THEN EXTRACT(EPOCH FROM (a.acknowledged_at - a.sent_at))
        ELSE NULL
    END AS response_time_seconds,
    -- Computed: is this alert expired?
    CASE
        WHEN a.expires_at IS NOT NULL AND a.expires_at < now()
        THEN true
        ELSE false
    END AS is_expired,
    -- Computed: needs attention?
    CASE
        WHEN a.action_required = true
             AND a.acknowledged_at IS NULL
             AND a.delivery_status IN ('delivered', 'sent')
             AND (a.expires_at IS NULL OR a.expires_at > now())
        THEN true
        ELSE false
    END AS needs_attention
FROM alerts a
ORDER BY a.created_at DESC
LIMIT 50;

COMMENT ON VIEW v_recent_alerts IS
    'Last 50 alerts with delivery status, response times, and attention flags.';


-- ============================================================
-- BONUS VIEW: v_pipeline_funnel
-- Pipeline candidate counts by status (from schema spec)
-- ============================================================
CREATE OR REPLACE VIEW v_pipeline_funnel AS
SELECT
    status,
    COUNT(*) AS count,
    ROUND(AVG(latest_composite_score), 2) AS avg_score,
    MIN(catalyst_date) AS nearest_catalyst
FROM pipeline_candidates
WHERE status NOT IN ('archived', 'eliminated')
GROUP BY status
ORDER BY
    CASE status
        WHEN 'entry_ready' THEN 1
        WHEN 'scoring' THEN 2
        WHEN 'watchlist' THEN 3
        WHEN 'candidate' THEN 4
        WHEN 'deployed' THEN 5
        WHEN 'p3_watch' THEN 6
        WHEN 'rejected' THEN 7
    END;

COMMENT ON VIEW v_pipeline_funnel IS
    'Pipeline funnel summary: candidate counts, avg scores, and nearest catalysts by status.';


-- ============================================================
-- BONUS VIEW: v_pending_alerts
-- Alerts that need immediate attention
-- ============================================================
CREATE OR REPLACE VIEW v_pending_alerts AS
SELECT *
FROM alerts
WHERE delivery_status IN ('queued', 'sending')
   OR (delivery_status = 'delivered' AND action_required = true AND acknowledged_at IS NULL)
ORDER BY
    CASE priority
        WHEN 'critical' THEN 1
        WHEN 'high' THEN 2
        WHEN 'normal' THEN 3
        WHEN 'silent' THEN 4
    END,
    created_at;

COMMENT ON VIEW v_pending_alerts IS
    'Alerts queued for delivery or delivered but unacknowledged. Ordered by priority.';


-- ============================================================
-- END OF VIEWS DDL
-- ============================================================
-- ============================================================
-- STRATEGY 5.x GROWTH SYSTEM — SEED: CURRENT PORTFOLIO
-- Target: Supabase PostgreSQL
-- Created: 2026-03-23
-- Portfolio snapshot as of: 2026-03-19
-- Broker: Moomoo account #8352
-- Currency: USD
-- ============================================================
-- This seeds the positions table with the user's actual
-- portfolio. Run AFTER 001_week1_tables.sql.
--
-- Computed fields (market_value, unrealized_pnl, etc.) are
-- calculated inline. These will be overwritten on the first
-- live Moomoo sync.
-- ============================================================

INSERT INTO positions (
    broker_account_id,
    ticker,
    security_name,
    asset_type,
    quantity,
    avg_cost,
    last_price,
    market_value,
    unrealized_pnl,
    unrealized_pnl_pct,
    currency,
    catalyst_type,
    playbook,
    binary_risk_flag,
    status,
    source_ref,
    source_fresh_at,
    position_hash,
    notes
) VALUES

-- 1. AXSM — Axsome Therapeutics (ALS PDUFA, Playbook A)
(
    '8352', 'AXSM', 'Axsome Therapeutics Inc', 'equity',
    15.0000, 162.650000, 158.880000,
    2383.20,                                     -- 15 × 158.88
    ROUND((158.88 - 162.65) * 15, 2),            -- -56.55
    ROUND(((158.88 - 162.65) / 162.65) * 100, 4), -- -2.3181%
    'USD', 'PDUFA', 'A', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_AXSM_15_162.65_158.88'),
    'ALS PDUFA pending. Orphan drug designation.'
),

-- 2. DNLI — Denali Therapeutics (Neuro pipeline, Playbook B)
(
    '8352', 'DNLI', 'Denali Therapeutics Inc', 'equity',
    188.0000, 21.220000, 19.750000,
    3713.00,                                      -- 188 × 19.75
    ROUND((19.75 - 21.22) * 188, 2),             -- -276.16
    ROUND(((19.75 - 21.22) / 21.22) * 100, 4),   -- -6.9274%
    'USD', NULL, 'B', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_DNLI_188_21.22_19.75'),
    'Neuro pipeline. Multiple readouts expected.'
),

-- 3. KPTI — Karyopharm Therapeutics (Oncology, Playbook B)
(
    '8352', 'KPTI', 'Karyopharm Therapeutics Inc', 'equity',
    188.0000, 7.058000, 7.730000,
    1453.24,                                      -- 188 × 7.73
    ROUND((7.73 - 7.058) * 188, 2),              -- 126.34
    ROUND(((7.73 - 7.058) / 7.058) * 100, 4),    -- 9.5214%
    'USD', NULL, 'B', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_KPTI_188_7.058_7.73'),
    'Oncology — selinexor franchise.'
),

-- 4. KYTX — Kyverna Therapeutics (Cell therapy, Playbook A)
(
    '8352', 'KYTX', 'Kyverna Therapeutics Inc', 'equity',
    100.0000, 8.389000, 8.540000,
    854.00,                                       -- 100 × 8.54
    ROUND((8.54 - 8.389) * 100, 2),              -- 15.10
    ROUND(((8.54 - 8.389) / 8.389) * 100, 4),    -- 1.8000%
    'USD', NULL, 'A', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_KYTX_100_8.389_8.54'),
    'CAR-T cell therapy for autoimmune diseases.'
),

-- 5. RCKT — Rocket Pharmaceuticals (Gene therapy, Playbook B)
(
    '8352', 'RCKT', 'Rocket Pharmaceuticals Inc', 'equity',
    188.0000, 4.960000, 4.390000,
    825.32,                                       -- 188 × 4.39
    ROUND((4.39 - 4.96) * 188, 2),               -- -107.16
    ROUND(((4.39 - 4.96) / 4.96) * 100, 4),      -- -11.4919%
    'USD', NULL, 'B', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_RCKT_188_4.96_4.39'),
    'Gene therapy platform. Fanconi Anemia + other programs.'
),

-- 6. RLAY — Relay Therapeutics (Precision oncology, Playbook B)
(
    '8352', 'RLAY', 'Relay Therapeutics Inc', 'equity',
    68.0000, 10.029000, 10.000000,
    680.00,                                       -- 68 × 10.00
    ROUND((10.00 - 10.029) * 68, 2),             -- -1.97
    ROUND(((10.00 - 10.029) / 10.029) * 100, 4), -- -0.2892%
    'USD', NULL, 'B', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_RLAY_68_10.029_10.00'),
    'Precision oncology. PI3K alpha program.'
),

-- 7. RYTM — Rhythm Pharmaceuticals (Rare disease, Playbook A)
(
    '8352', 'RYTM', 'Rhythm Pharmaceuticals Inc', 'equity',
    50.0000, 94.500000, 90.310000,
    4515.50,                                      -- 50 × 90.31
    ROUND((90.31 - 94.50) * 50, 2),              -- -209.50
    ROUND(((90.31 - 94.50) / 94.50) * 100, 4),   -- -4.4339%
    'USD', NULL, 'A', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_RYTM_50_94.50_90.31'),
    'Rare obesity — setmelanotide franchise. Expansion indications.'
),

-- 8. VIR — Vir Biotechnology (Infectious disease, Playbook B)
(
    '8352', 'VIR', 'Vir Biotechnology Inc', 'equity',
    188.0000, 6.591000, 9.380000,
    1763.44,                                      -- 188 × 9.38
    ROUND((9.38 - 6.591) * 188, 2),              -- 524.33
    ROUND(((9.38 - 6.591) / 6.591) * 100, 4),    -- 42.3153%
    'USD', NULL, 'B', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_VIR_188_6.591_9.38'),
    'Infectious disease + oncology pipeline. HBV focus.'
),

-- 9. VNDA — Vanda Pharmaceuticals (Established revenue, Playbook C)
(
    '8352', 'VNDA', 'Vanda Pharmaceuticals Inc', 'equity',
    100.0000, 6.684000, 8.570000,
    857.00,                                       -- 100 × 8.57
    ROUND((8.57 - 6.684) * 100, 2),              -- 188.60
    ROUND(((8.57 - 6.684) / 6.684) * 100, 4),    -- 28.2167%
    'USD', NULL, 'C', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_VNDA_100_6.684_8.57'),
    'Established revenue from Hetlioz. Value play.'
),

-- 10. WVE — Wave Life Sciences (RNA therapeutics, Playbook B)
(
    '8352', 'WVE', 'Wave Life Sciences Ltd', 'equity',
    288.0000, 14.444000, 12.120000,
    3490.56,                                      -- 288 × 12.12
    ROUND((12.12 - 14.444) * 288, 2),            -- -669.31
    ROUND(((12.12 - 14.444) / 14.444) * 100, 4), -- -16.0955%
    'USD', NULL, 'B', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_WVE_288_14.444_12.12'),
    'RNA therapeutics — DMD program lead. ADAR editing platform.'
),

-- 11. XENE — Xenon Pharmaceuticals (Epilepsy, Playbook A)
(
    '8352', 'XENE', 'Xenon Pharmaceuticals Inc', 'equity',
    19.0000, 41.568000, 55.170000,
    1048.23,                                      -- 19 × 55.17
    ROUND((55.17 - 41.568) * 19, 2),             -- 258.44
    ROUND(((55.17 - 41.568) / 41.568) * 100, 4), -- 32.7001%
    'USD', NULL, 'A', false, 'open',
    '[FINANCE]manual_seed_20260319',
    '2026-03-19T16:00:00Z',
    md5('8352_XENE_19_41.568_55.17'),
    'Epilepsy — azetukalner (XEN1101). Phase 3 readouts upcoming.'
);


-- ============================================================
-- VERIFY: Quick sanity check after insert
-- ============================================================
-- Run these SELECT queries manually to verify:
--
-- SELECT ticker, quantity, avg_cost, last_price, market_value,
--        unrealized_pnl, playbook
-- FROM positions
-- WHERE broker_account_id = '8352' AND status = 'open'
-- ORDER BY market_value DESC;
--
-- Expected: 11 rows, total market_value ≈ $21,583
-- ============================================================

-- ============================================================
-- END OF PORTFOLIO SEED DATA
-- ============================================================

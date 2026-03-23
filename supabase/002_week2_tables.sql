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

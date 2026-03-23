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

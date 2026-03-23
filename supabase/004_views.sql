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

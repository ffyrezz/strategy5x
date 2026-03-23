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

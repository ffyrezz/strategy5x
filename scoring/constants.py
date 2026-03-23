"""
Scoring thresholds, FDA approval base rates, and SC axis definitions.

All constants here are referenced by engine.py and da_checks.py.
"""

# ── SC1: Catalyst Timing ─────────────────────────────────────────────────────
# Score curve based on days until catalyst event.
# Closer catalysts = higher urgency/score.
SC1_CURVE: list[tuple[int, float]] = [
    # (max_days_inclusive, score)
    (3, 10.0),    # T-3 or less: maximum urgency
    (7, 9.0),     # T-4 to T-7
    (14, 8.0),    # T-8 to T-14
    (21, 7.0),    # T-15 to T-21
    (30, 6.0),    # T-22 to T-30
    (45, 5.0),    # T-31 to T-45
    (60, 4.0),    # T-46 to T-60
    (90, 3.0),    # T-61 to T-90
    (180, 2.0),   # T-91 to T-180
    (9999, 1.0),  # >180 days out
]

# ── SC5: Going Concern / Financial Health ─────────────────────────────────────
# Score based on cash runway in months.
SC5_CURVE: list[tuple[int, float]] = [
    (6, 2.0),      # <6 months: critical concern
    (12, 4.0),     # 6-12 months: caution
    (18, 6.0),     # 12-18 months: acceptable
    (24, 7.0),     # 18-24 months: comfortable
    (36, 8.0),     # 24-36 months: strong
    (48, 9.0),     # 36-48 months: very strong
    (9999, 10.0),  # >48 months: fortress balance sheet
]

# ── SC6: Liquidity / Tradability ──────────────────────────────────────────────
# Score based on 30-day average daily volume (in USD).
SC6_CURVE: list[tuple[float, float]] = [
    (500_000, 2.0),        # <$500K ADV: illiquid, hard to trade
    (1_000_000, 3.0),      # $500K-$1M
    (2_000_000, 4.0),      # $1M-$2M
    (5_000_000, 5.0),      # $2M-$5M
    (10_000_000, 6.0),     # $5M-$10M
    (20_000_000, 7.0),     # $10M-$20M
    (50_000_000, 8.0),     # $20M-$50M
    (100_000_000, 9.0),    # $50M-$100M
    (float("inf"), 10.0),  # >$100M: highly liquid
]

# ── SC7: Risk/Reward Ratio ───────────────────────────────────────────────────
# Score based on upside/downside ratio.
SC7_CURVE: list[tuple[float, float]] = [
    (0.5, 1.0),        # <0.5x: terrible R:R
    (0.8, 2.0),        # 0.5-0.8x
    (1.0, 3.0),        # 0.8-1.0x: negative EV
    (1.2, 4.0),        # 1.0-1.2x: marginal
    (1.5, 5.0),        # 1.2-1.5x
    (2.0, 6.0),        # 1.5-2.0x
    (2.5, 7.0),        # 2.0-2.5x
    (3.0, 8.0),        # 2.5-3.0x
    (4.0, 9.0),        # 3.0-4.0x
    (float("inf"), 10.0),  # >4.0x: excellent
]

# ── FDA Base Rates ───────────────────────────────────────────────────────────
# Default approval probabilities by catalyst type.
FDA_BASE_RATES: dict[str, float] = {
    "NDA": 0.90,
    "BLA": 0.85,
    "sNDA": 0.92,
    "PDUFA": 0.85,
    "CRL_RESPONSE": 0.60,
    "PHASE3_READOUT": 0.58,
    "ADCOM": 0.75,
    "DEFAULT": 0.68,
}

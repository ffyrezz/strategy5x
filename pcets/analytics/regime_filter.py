"""PCETS Regime Filter Helper
Determines current PCETS regime based on XBI and VIX.
Used by scoring engine and morning brief job.
"""
import yfinance as yf
import pandas as pd

def get_vix() -> float:
    """Fetch live VIX. Never hardcode."""
    vix = yf.Ticker('^VIX')
    hist = vix.history(period='1d')
    return round(float(hist['Close'].iloc[-1]), 2)

def get_xbi_regime() -> str:
    """Returns 'Bull', 'Neutral', or 'Bear' based on XBI vs 50-day MA."""
    xbi = yf.Ticker('XBI')
    hist = xbi.history(period='60d')
    if len(hist) < 50:
        return 'UNKNOWN'
    current = hist['Close'].iloc[-1]
    ma50 = hist['Close'].rolling(50).mean().iloc[-1]
    pct_diff = (current - ma50) / ma50 * 100
    if pct_diff > 5:
        return 'Bull'
    elif pct_diff < -5:
        return 'Bear'
    else:
        return 'Neutral'

def get_vix_regime(vix: float) -> str:
    if vix < 18:
        return 'Normal'
    elif vix < 22:
        return 'Normal-Cautious'
    elif vix < 26:
        return 'Elevated'
    elif vix < 30:
        return 'High-Risk'
    else:
        return 'Crisis'

def full_regime_check() -> dict:
    vix = get_vix()
    xbi_regime = get_xbi_regime()
    vix_regime = get_vix_regime(vix)
    entry_blocked = vix >= 30
    entry_caution = 26 <= vix < 30
    sc11_required = xbi_regime in ('Neutral', 'Bear')
    size_haircut = entry_caution or xbi_regime == 'Bear'
    return {
        'vix': vix,
        'vix_regime': vix_regime,
        'xbi_regime': xbi_regime,
        'entry_blocked': entry_blocked,
        'entry_caution': entry_caution,
        'sc11_required': sc11_required,
        'size_haircut': size_haircut,
    }

if __name__ == '__main__':
    result = full_regime_check()
    print('=== PCETS Regime Check ===')
    for k, v in result.items():
        print(f'{k}: {v}')

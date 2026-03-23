"""
Data provenance tagging.

Every externally-sourced value carries a tag so downstream consumers know
where the data came from and how much to trust it.

Tags: [CSV], [SEARCH], [FINANCE], [CALC], [PRIOR], [UNVERIFIED], [MANUAL]
"""


def tag(source: str, detail: str = "") -> str:
    """Build a provenance string, e.g. tag('FINANCE', 'yfinance') -> '[FINANCE]yfinance'."""
    base = f"[{source.upper()}]"
    if detail:
        base += detail
    return base


# Convenience shortcuts
FINANCE = lambda detail="": tag("FINANCE", detail)
CALC = lambda detail="": tag("CALC", detail)
CSV = lambda detail="": tag("CSV", detail)
SEARCH = lambda detail="": tag("SEARCH", detail)
MANUAL = lambda detail="": tag("MANUAL", detail)
UNVERIFIED = lambda detail="": tag("UNVERIFIED", detail)
PRIOR = lambda detail="": tag("PRIOR", detail)

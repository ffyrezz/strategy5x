"""SGT / UTC conversion helpers."""

from datetime import datetime, timezone, timedelta

SGT = timezone(timedelta(hours=8))
UTC = timezone.utc


def now_utc() -> datetime:
    """Current time in UTC."""
    return datetime.now(UTC)


def now_sgt() -> datetime:
    """Current time in SGT."""
    return datetime.now(SGT)


def utc_to_sgt(dt: datetime) -> datetime:
    """Convert a UTC datetime to SGT."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(SGT)


def sgt_to_utc(dt: datetime) -> datetime:
    """Convert an SGT datetime to UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SGT)
    return dt.astimezone(UTC)


def format_sgt(dt: datetime, fmt: str = "%H:%M SGT") -> str:
    """Format a datetime as SGT string."""
    return utc_to_sgt(dt).strftime(fmt)


def is_quiet_hours() -> bool:
    """Return True if current SGT time is between 00:00 and 06:00."""
    hour = now_sgt().hour
    return 0 <= hour < 6

"""Quiet hours and business-day maths, all in Eastern time."""
from datetime import date, datetime, time, timedelta

import holidays

from .config import QUIET_END_HOUR, QUIET_START_HOUR, TZ

_ON = holidays.Canada(subdiv="ON")


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("naive datetime; always pass timezone-aware values")
    return dt.astimezone(TZ)


def in_quiet_hours(dt: datetime) -> bool:
    h = to_local(dt).hour
    return h >= QUIET_START_HOUR or h < QUIET_END_HOUR


def reply_clock_start(received: datetime) -> datetime:
    """Inquiry time, or the next 7 a.m. Eastern if it arrived in quiet hours."""
    local = to_local(received)
    if not in_quiet_hours(local):
        return local
    day = local.date() if local.hour < QUIET_END_HOUR else local.date() + timedelta(days=1)
    return datetime.combine(day, time(QUIET_END_HOUR), tzinfo=TZ)


def is_business_day(d: date) -> bool:
    return d.weekday() < 5 and d not in _ON


def add_business_days(start: date, n: int) -> date:
    d = start
    while n > 0:
        d += timedelta(days=1)
        if is_business_day(d):
            n -= 1
    return d

"""Timezone helpers for SRTime's local business clock.

Attendance devices usually send wall-clock date/time values without timezone
metadata. SRTime keeps that storage contract and applies the configured zone
only when comparing, scheduling, or calculating spans.
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, time as Time
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from core.config import load_application_env


DEFAULT_TIMEZONE = "America/Argentina/Buenos_Aires"
logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_timezone() -> ZoneInfo:
    """Return the configured business timezone, falling back to SRTime default."""
    load_application_env()
    timezone_name = os.getenv("TIMEZONE", DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning("Invalid TIMEZONE '%s'; falling back to %s", timezone_name, DEFAULT_TIMEZONE)
        return ZoneInfo(DEFAULT_TIMEZONE)


def local_now() -> datetime:
    """Current aware datetime in the configured SRTime business timezone."""
    return datetime.now(get_timezone())


def local_today() -> date:
    """Current date in the configured SRTime business timezone."""
    return local_now().date()


def local_datetime(day: date, value: Time) -> datetime:
    """Attach the configured timezone to a stored local date/time pair."""
    return datetime.combine(day, value, tzinfo=get_timezone())


def clear_timezone_cache() -> None:
    """Testing helper for environment changes."""
    get_timezone.cache_clear()

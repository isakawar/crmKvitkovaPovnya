import logging
from datetime import date, time, datetime
from typing import Optional

logger = logging.getLogger(__name__)


def parse_ymd(s: str) -> date:
    """Parse 'YYYY-MM-DD' string to date; raises ValueError on bad input."""
    return datetime.strptime(s, '%Y-%m-%d').date()


def parse_hm(s: str) -> time:
    """Parse 'HH:MM' string to time; raises ValueError on bad input."""
    return datetime.strptime(s, '%H:%M').time()


def parse_eta(date_str: str, eta_str: str) -> Optional[datetime]:
    """Parse combined date + 'HH:MM' ETA; returns None on any bad input."""
    if not eta_str:
        return None
    try:
        return datetime.strptime(f'{date_str} {eta_str}', '%Y-%m-%d %H:%M')
    except ValueError:
        logger.warning('Invalid ETA value %r, skipping planned_arrival', eta_str)
        return None

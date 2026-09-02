"""Best-effort URL shortening for Google Maps route links in courier messages.

Order of preference: short.io → is.gd → original URL. Any failure (missing
config, network error, non-2xx, unexpected body) silently falls through to the
next option, so a caller always gets a usable link.
"""
import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)

_SHORTIO_ENDPOINT = 'https://api.short.io/links'
_ISGD_ENDPOINT = 'https://is.gd/create.php'
_TIMEOUT = 5


def _shorten_via_shortio(long_url: str) -> str | None:
    api_key = current_app.config.get('SHORTIO_API_KEY', '')
    domain = current_app.config.get('SHORTIO_DOMAIN', '')
    if not api_key or not domain:
        return None
    try:
        resp = requests.post(
            _SHORTIO_ENDPOINT,
            json={'originalURL': long_url, 'domain': domain},
            headers={'Authorization': api_key, 'Content-Type': 'application/json'},
            timeout=_TIMEOUT,
        )
        if resp.status_code in (200, 201):
            short = (resp.json() or {}).get('shortURL')
            if isinstance(short, str) and short.startswith('http'):
                return short
        logger.warning('short.io returned %s: %s', resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning('short.io request failed: %s', exc)
    return None


def _shorten_via_isgd(long_url: str) -> str | None:
    try:
        resp = requests.get(
            _ISGD_ENDPOINT,
            params={'format': 'simple', 'url': long_url},
            timeout=_TIMEOUT,
        )
        if resp.status_code == 200 and resp.text.startswith('http'):
            return resp.text.strip()
        logger.warning('is.gd returned %s: %s', resp.status_code, resp.text[:200])
    except Exception as exc:
        logger.warning('is.gd request failed: %s', exc)
    return None


def shorten_url(long_url: str) -> str:
    """Return a shortened link, or ``long_url`` unchanged if every provider fails."""
    if not long_url:
        return long_url
    return (
        _shorten_via_shortio(long_url)
        or _shorten_via_isgd(long_url)
        or long_url
    )

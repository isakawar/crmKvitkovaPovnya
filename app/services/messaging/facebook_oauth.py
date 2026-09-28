"""Facebook Login for Business — connects a Page's linked Instagram account
without the owner ever touching Meta App Dashboard or copying tokens.

Flow (see app/blueprints/settings/routes.py messaging_facebook_*):
  1. authorize_url(state) -> redirect the manager to Meta's OAuth dialog
  2. Meta redirects back with `code` -> exchange_code_for_user_token
  3. exchange_long_lived_token -> a ~60-day user token
  4. list_connected_pages -> Pages the user manages, with their linked IG
     Business account (if any) and a ready-to-use Page Access Token

Uses graph.facebook.com (not graph.instagram.com) — the Page Access Token is
what authorizes IG messaging once the account is Page-linked.
"""
from __future__ import annotations

import urllib.parse

import requests
from flask import current_app

_TIMEOUT = 30
_OAUTH_SCOPES = (
    'pages_show_list,pages_manage_metadata,pages_messaging,'
    'instagram_basic,instagram_manage_messages'
)


def _graph_version() -> str:
    return current_app.config.get('INBOX_INSTAGRAM_GRAPH_VERSION') or 'v23.0'


def _app_id() -> str:
    app_id = current_app.config.get('FACEBOOK_APP_ID')
    if not app_id:
        raise RuntimeError('FACEBOOK_APP_ID не налаштовано')
    return app_id


def _app_secret() -> str:
    # Same Meta App as the Instagram webhook signature — one App, two products.
    secret = current_app.config.get('INBOX_INSTAGRAM_APP_SECRET')
    if not secret:
        raise RuntimeError('INBOX_INSTAGRAM_APP_SECRET не налаштовано')
    return secret


def redirect_uri() -> str:
    base = (current_app.config.get('CRM_PUBLIC_URL') or '').rstrip('/')
    if not base:
        raise RuntimeError('CRM_PUBLIC_URL не налаштовано — Facebook OAuth потребує публічний HTTPS URL')
    return f'{base}/settings/messaging/facebook/callback'


def authorize_url(state: str) -> str:
    params = {
        'client_id': _app_id(),
        'redirect_uri': redirect_uri(),
        'state': state,
        'scope': _OAUTH_SCOPES,
        'response_type': 'code',
    }
    return f'https://www.facebook.com/{_graph_version()}/dialog/oauth?' + urllib.parse.urlencode(params)


def exchange_code_for_user_token(code: str) -> str:
    r = requests.get(
        f'https://graph.facebook.com/{_graph_version()}/oauth/access_token',
        params={
            'client_id': _app_id(),
            'client_secret': _app_secret(),
            'redirect_uri': redirect_uri(),
            'code': code,
        },
        timeout=_TIMEOUT,
    )
    body = r.json()
    if r.status_code >= 400 or 'access_token' not in body:
        raise RuntimeError((body.get('error') or {}).get('message') or f'HTTP {r.status_code}')
    return body['access_token']


def exchange_long_lived_token(short_lived_token: str) -> str:
    r = requests.get(
        f'https://graph.facebook.com/{_graph_version()}/oauth/access_token',
        params={
            'grant_type': 'fb_exchange_token',
            'client_id': _app_id(),
            'client_secret': _app_secret(),
            'fb_exchange_token': short_lived_token,
        },
        timeout=_TIMEOUT,
    )
    body = r.json()
    if r.status_code >= 400 or 'access_token' not in body:
        raise RuntimeError((body.get('error') or {}).get('message') or f'HTTP {r.status_code}')
    return body['access_token']


def exchange_embedded_signup_code(code: str) -> str:
    """Token exchange for a code returned by the JS-SDK Embedded Signup popup
    (WhatsApp) — unlike the redirect-based flow above, no redirect_uri is
    involved since the code never travels through a browser navigation."""
    r = requests.get(
        f'https://graph.facebook.com/{_graph_version()}/oauth/access_token',
        params={'client_id': _app_id(), 'client_secret': _app_secret(), 'code': code},
        timeout=_TIMEOUT,
    )
    body = r.json()
    if r.status_code >= 400 or 'access_token' not in body:
        raise RuntimeError((body.get('error') or {}).get('message') or f'HTTP {r.status_code}')
    return body['access_token']


def list_connected_pages(user_token: str) -> list[dict]:
    """Pages the authorizing user manages, each with its linked IG Business
    account (id/username) when one exists, and a Page Access Token ready to
    use for sending/receiving. Pages without a linked IG account are skipped;
    if none is left, raises NoInstagramPagesError naming the Pages returned."""
    r = requests.get(
        f'https://graph.facebook.com/{_graph_version()}/me/accounts',
        params={
            'fields': 'id,name,access_token,instagram_business_account{id,username}',
            'access_token': user_token,
        },
        timeout=_TIMEOUT,
    )
    body = r.json()
    if r.status_code >= 400:
        raise RuntimeError((body.get('error') or {}).get('message') or f'HTTP {r.status_code}')
    raw_pages = body.get('data', [])
    # Never log tokens — only what's needed to see why a Page was skipped.
    current_app.logger.warning(
        'Facebook OAuth: /me/accounts returned %d page(s) as (id, name, linked IG username): %s',
        len(raw_pages),
        [(p.get('id'), p.get('name'), (p.get('instagram_business_account') or {}).get('username'))
         for p in raw_pages],
    )
    pages = []
    for page in raw_pages:
        ig = page.get('instagram_business_account')
        if not ig:
            continue
        pages.append({
            'page_id': page['id'],
            'page_name': page.get('name') or page['id'],
            'page_access_token': page['access_token'],
            'ig_id': ig['id'],
            'ig_username': ig.get('username') or ig['id'],
        })
    if not pages:
        _log_granted_assets(user_token)
        raise NoInstagramPagesError(_no_instagram_message(raw_pages))
    return pages


def _log_granted_assets(user_token: str) -> None:
    """Diagnostics only: which Pages / IG accounts the user actually granted
    in the Business Login asset picker (debug_token granular_scopes). Tells
    "Page not ticked" apart from "ticked but /me/accounts still empty".
    Never raises — a failure here must not mask the real error."""
    try:
        r = requests.get(
            f'https://graph.facebook.com/{_graph_version()}/debug_token',
            params={'input_token': user_token, 'access_token': f'{_app_id()}|{_app_secret()}'},
            timeout=_TIMEOUT,
        )
        data = r.json().get('data')
        if not isinstance(data, dict):
            current_app.logger.warning('Facebook OAuth: debug_token returned no data (HTTP %s)', r.status_code)
            return
        current_app.logger.warning(
            'Facebook OAuth: granted scopes -> target ids: %s',
            {g.get('scope'): g.get('target_ids', 'all') for g in data.get('granular_scopes', [])},
        )
    except Exception as exc:  # noqa: BLE001 — diagnostics must never break the flow
        current_app.logger.warning('Facebook OAuth: debug_token failed: %s', exc)


class NoInstagramPagesError(RuntimeError):
    """None of the Pages the user granted has a linked IG Business account."""


def _no_instagram_message(raw_pages: list[dict]) -> str:
    if not raw_pages:
        return ('Facebook не повернув жодної сторінки. Під час підключення на кроці вибору сторінок '
                'відмітьте ту, до якої прив\'язаний Instagram, і сам Instagram-акаунт на наступному кроці')
    names = ', '.join(p.get('name') or p.get('id') or '?' for p in raw_pages)
    return (f'Жодна з вибраних сторінок ({names}) не має прив\'язаного Instagram Business акаунту. '
            'Прив\'яжіть Instagram до сторінки в Meta Business Suite і підключіть ще раз')

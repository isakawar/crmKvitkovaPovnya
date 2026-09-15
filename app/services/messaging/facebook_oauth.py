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
    use for sending/receiving. Pages without a linked IG account are skipped."""
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
    pages = []
    for page in body.get('data', []):
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
    return pages

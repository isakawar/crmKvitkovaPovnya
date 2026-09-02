"""url_shortener_service: short.io → is.gd → original URL fallback chain."""
from unittest.mock import MagicMock, patch

import pytest

from app.services import url_shortener_service as svc

LONG = 'https://www.google.com/maps/dir/A/B/C'


def _resp(status=200, json_body=None, text=''):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json.return_value = json_body if json_body is not None else {}
    return r


@pytest.fixture
def shortio_configured(app):
    app.config['SHORTIO_API_KEY'] = 'k_test'
    app.config['SHORTIO_DOMAIN'] = 'go.example.gy'
    return app


def test_shortio_success(shortio_configured):
    with patch.object(svc.requests, 'post',
                      return_value=_resp(200, {'shortURL': 'https://go.example.gy/abc'})) as post, \
         patch.object(svc.requests, 'get') as get:
        assert svc.shorten_url(LONG) == 'https://go.example.gy/abc'
        post.assert_called_once()
        get.assert_not_called()


def test_shortio_fails_falls_back_to_isgd(shortio_configured):
    with patch.object(svc.requests, 'post', return_value=_resp(500, text='err')), \
         patch.object(svc.requests, 'get',
                      return_value=_resp(200, text='https://is.gd/xyz')) as get:
        assert svc.shorten_url(LONG) == 'https://is.gd/xyz'
        get.assert_called_once()


def test_no_config_skips_shortio_uses_isgd(app):
    app.config['SHORTIO_API_KEY'] = ''
    app.config['SHORTIO_DOMAIN'] = ''
    with patch.object(svc.requests, 'post') as post, \
         patch.object(svc.requests, 'get', return_value=_resp(200, text='https://is.gd/q')):
        assert svc.shorten_url(LONG) == 'https://is.gd/q'
        post.assert_not_called()


def test_all_providers_fail_returns_original(shortio_configured):
    with patch.object(svc.requests, 'post', side_effect=Exception('boom')), \
         patch.object(svc.requests, 'get', side_effect=Exception('boom')):
        assert svc.shorten_url(LONG) == LONG


def test_empty_url_returned_as_is(app):
    assert svc.shorten_url('') == ''


def test_shortio_bad_body_falls_through(shortio_configured):
    with patch.object(svc.requests, 'post', return_value=_resp(200, {'nope': 1})), \
         patch.object(svc.requests, 'get', return_value=_resp(200, text='https://is.gd/z')):
        assert svc.shorten_url(LONG) == 'https://is.gd/z'

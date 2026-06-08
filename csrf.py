"""Lightweight CSRF protection for SPA + JSON API.

Strategy: double-submit cookie.
- On every response, a CSRF token is set in a readable cookie (`csrf_token`).
- JS reads the cookie and sends it back in the `X-CSRF-Token` header.
- The server validates that the header matches the cookie.
- State-changing methods (POST/PUT/DELETE/PATCH) are protected.
- Safe methods (GET/HEAD/OPTIONS) are exempt.
- The webhook endpoint is exempt (uses HMAC auth instead).
"""
import os
import hmac
import hashlib

from flask import request, session, abort, g

_EXEMPT_ENDPOINTS = frozenset()
_EXEMPT_PREFIXES = ('/webhook/',)
_SAFE_METHODS = frozenset(('GET', 'HEAD', 'OPTIONS'))


def _generate_token():
    raw = os.urandom(32)
    secret = session.get('_csrf_secret')
    if not secret:
        secret = os.urandom(32).hex()
        session['_csrf_secret'] = secret
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _get_or_refresh_token():
    token = session.get('_csrf_token')
    if not token:
        token = _generate_token()
        session['_csrf_token'] = token
    return token


def init_csrf(app):
    """Register before/after hooks on the Flask app."""

    @app.after_request
    def _set_csrf_cookie(response):
        if 'authenticated' in session:
            token = _get_or_refresh_token()
            response.set_cookie(
                'csrf_token',
                token,
                httponly=False,
                samesite='Lax',
                secure=not app.debug,
                path='/',
            )
        return response

    @app.before_request
    def _check_csrf():
        if request.method in _SAFE_METHODS:
            return
        for prefix in _EXEMPT_PREFIXES:
            if request.path.startswith(prefix):
                return
        if request.endpoint and request.endpoint in _EXEMPT_ENDPOINTS:
            return
        # API-token (Bearer) requests are machine-to-machine — no CSRF needed.
        # Check both: already-set flag (from login_required) or raw header presence.
        if getattr(g, 'api_token_auth', False):
            return
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            # Will be validated by login_required; skip CSRF here.
            return
        if 'authenticated' not in session:
            return
        expected = session.get('_csrf_token')
        provided = request.headers.get('X-CSRF-Token', '')
        if not expected or not hmac.compare_digest(expected, provided):
            abort(403)

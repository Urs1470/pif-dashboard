# Budget Tracker Blueprint
# Provides /budget/* routes with PIN authentication (same as app.py)

from flask import Blueprint, send_from_directory, jsonify, request, session, current_app, make_response
from pathlib import Path
from datetime import datetime
import json
import hashlib
import urllib.request
import urllib.error
import urllib.parse
import time

budget_bp = Blueprint('budget', __name__, url_prefix='/budget')

STATIC_DIR = Path(__file__).resolve().parent.parent / 'static' / 'budget'

AUDIT_VALUE_MAX = 200
AUDIT_MAX_CHANGES_PER_SAVE = 60

# In-memory quote cache: {symbol: (timestamp, payload)}
_QUOTE_CACHE = {}
QUOTE_CACHE_TTL = 300  # 5 minutes


# ============================================================
# Asset versioning — a short content hash of the budget SPA's
# static files. Drives cache-busting (?v=) and the in-app
# "new version available" check (see /api/version below).
# ============================================================
_VERSIONED_FILES = ('index.html', 'budget-tracker.js', 'budget.css')
_VERSION_CACHE = {'sig': None, 'version': None}


def _budget_version():
    """Return a 10-char content hash of the budget app's static assets.

    Recomputed only when a file's mtime or size changes, so repeated
    /api/version polls stay cheap.
    """
    sig_parts = []
    for name in _VERSIONED_FILES:
        try:
            st = (STATIC_DIR / name).stat()
            sig_parts.append('%s:%d:%d' % (name, st.st_mtime_ns, st.st_size))
        except OSError:
            sig_parts.append('%s:0:0' % name)
    sig = '|'.join(sig_parts)
    if _VERSION_CACHE['sig'] == sig:
        return _VERSION_CACHE['version']
    h = hashlib.md5()
    for name in _VERSIONED_FILES:
        try:
            h.update((STATIC_DIR / name).read_bytes())
        except OSError:
            pass
    version = h.hexdigest()[:10]
    _VERSION_CACHE['sig'] = sig
    _VERSION_CACHE['version'] = version
    return version


def _get_db():
    from database import get_db as _get
    return _get()


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


def _trunc(v):
    if v is None:
        return None
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= AUDIT_VALUE_MAX else s[:AUDIT_VALUE_MAX] + '…'


# Keys excluded from the audit diff: bookkeeping + VWCE market data that
# churns on every hourly price refresh (not user decisions worth logging).
AUDIT_SKIP_KEYS = {
    'priceHistory', 'lastUpdate', 'lastUpdateLocal',
    'pretCurent', 'previousClose', 'change', 'changePct', 'cursRon',
}


def diff_state(old, new, path=''):
    """Yield (path, old, new) tuples for every leaf change between two JSON-like values."""
    if old == new:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old.keys()) | set(new.keys()), key=str):
            # Skip internal/bookkeeping keys (_idSeq) and churning market data.
            if isinstance(k, str) and (k.startswith('_') or k in AUDIT_SKIP_KEYS):
                continue
            sub = f"{path}.{k}" if path else k
            yield from diff_state(old.get(k), new.get(k), sub)
    elif isinstance(old, list) and isinstance(new, list):
        if len(old) == len(new):
            for i, (a, b) in enumerate(zip(old, new)):
                yield from diff_state(a, b, f"{path}[{i}]")
        else:
            yield (path or '(root)', _trunc(old), _trunc(new))
    else:
        yield (path or '(root)', _trunc(old), _trunc(new))


@budget_bp.route('/')
@login_required
def index():
    # Render the SPA shell with the current asset version stamped in, so a
    # new deploy busts the budget.css / budget-tracker.js caches automatically.
    version = _budget_version()
    try:
        html = (STATIC_DIR / 'index.html').read_text(encoding='utf-8')
    except OSError:
        return send_from_directory(STATIC_DIR, 'index.html')
    resp = make_response(html.replace('__BUDGET_ASSET_VER_b9f23__', version))
    # The shell is tiny and must always reflect the live deploy.
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@budget_bp.route('/<path:filename>')
@login_required
def static_files(filename):
    resp = send_from_directory(STATIC_DIR, filename)
    # Assets are requested with a content-hash ?v= param, so a given URL
    # always maps to the same bytes — let the browser cache them hard.
    if request.args.get('v'):
        resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp


@budget_bp.route('/api/state', methods=['GET'])
@login_required
def get_state():
    db = _get_db()
    row = db.execute(
        "SELECT data, updated FROM budget_state WHERE user = 'ion'"
    ).fetchone()
    if not row:
        return jsonify({'data': None, 'updated': None})
    return jsonify({
        'data': json.loads(row['data']),
        'updated': row['updated']
    })


@budget_bp.route('/api/state', methods=['POST'])
@login_required
def set_state():
    payload = request.get_json(silent=True)
    if not payload or 'data' not in payload:
        return jsonify({'error': 'missing data field'}), 400

    db = _get_db()
    now = datetime.now().isoformat()
    new_data = payload['data']
    data_json = json.dumps(new_data, ensure_ascii=False)
    migrated = bool(payload.get('migrated'))

    try:
        prev = db.execute(
            "SELECT data, updated FROM budget_state WHERE user = 'ion'"
        ).fetchone()

        # Optimistic concurrency: if the client sent the snapshot it started
        # from, reject when the stored version moved on (another tab/device).
        if 'base_updated' in payload and prev is not None:
            if payload.get('base_updated') != prev['updated']:
                return jsonify({
                    'error': 'conflict',
                    'current': {
                        'data': json.loads(prev['data']) if prev['data'] else None,
                        'updated': prev['updated'],
                    },
                }), 409

        old_data = json.loads(prev['data']) if prev and prev['data'] else None

        db.execute("""
            INSERT INTO budget_state(user, data, updated)
            VALUES('ion', ?, ?)
            ON CONFLICT(user) DO UPDATE SET data = excluded.data, updated = excluded.updated
        """, (data_json, now))

        if old_data is None:
            db.execute("""
                INSERT INTO budget_audit(ts, user, action, field, old_value, new_value)
                VALUES(?, 'ion', 'init', NULL, NULL, ?)
            """, (now, _trunc(new_data)))
        elif migrated:
            # First save after a client-side schema migration. Diffing the
            # pre/post-migration blob yields dozens of spurious leaf changes,
            # so record a single 'migrate' entry instead.
            db.execute("""
                INSERT INTO budget_audit(ts, user, action, field, old_value, new_value)
                VALUES(?, 'ion', 'migrate', NULL, NULL, ?)
            """, (now, 'migrare automata a structurii datelor'))
        else:
            changes = list(diff_state(old_data, new_data))
            for path, old_val, new_val in changes[:AUDIT_MAX_CHANGES_PER_SAVE]:
                db.execute("""
                    INSERT INTO budget_audit(ts, user, action, field, old_value, new_value)
                    VALUES(?, 'ion', 'update', ?, ?, ?)
                """, (now, path, old_val, new_val))
            if len(changes) > AUDIT_MAX_CHANGES_PER_SAVE:
                extra = len(changes) - AUDIT_MAX_CHANGES_PER_SAVE
                db.execute("""
                    INSERT INTO budget_audit(ts, user, action, field, old_value, new_value)
                    VALUES(?, 'ion', 'update', '(truncated)', ?, NULL)
                """, (now, f"{extra} schimbari suplimentare omise"))

        db.commit()
        return jsonify({'ok': True, 'updated': now})
    except Exception as e:
        db.rollback()
        current_app.logger.exception('budget set_state failed')
        return jsonify({'error': 'save failed', 'detail': str(e)}), 500


@budget_bp.route('/api/audit', methods=['GET'])
@login_required
def get_audit():
    try:
        limit = min(int(request.args.get('limit', 50)), 500)
    except (TypeError, ValueError):
        limit = 50
    if limit < 1:
        limit = 50
    db = _get_db()
    rows = db.execute("""
        SELECT ts, action, field, old_value, new_value FROM budget_audit
        WHERE user = 'ion' ORDER BY ts DESC, id DESC LIMIT ?
    """, (limit,)).fetchall()
    return jsonify([dict(r) for r in rows])


@budget_bp.route('/api/version', methods=['GET'])
@login_required
def get_version():
    """Current deployed asset version — polled by the client to show the
    'new version available' banner without a service worker."""
    return jsonify({'version': _budget_version()})


# ============================================================
# Live market quotes (Yahoo Finance proxy, CORS-safe)
# ============================================================
ALLOWED_QUOTE_SYMBOLS = {
    # ETF / index symbols we whitelist. Add more as needed.
    'VWCE.DE', 'VWCE.AS', 'VWCE.SW', 'VWCE.MI',
    'IWDA.AS', 'EUNL.DE', 'CSPX.AS', 'SPY', 'VOO', 'QQQ', 'VTI',
    'EXSA.DE', 'EXSP.DE', 'EUNK.DE',
    # FX pairs
    'EURRON=X', 'EURUSD=X', 'USDRON=X',
}


def _fetch_yahoo_chart(symbol, interval='1d', rng='3mo'):
    # Defense-in-depth: URL-encode the symbol even though it is whitelisted,
    # so a future whitelist entry can never inject into the URL path.
    safe_symbol = urllib.parse.quote(symbol, safe='')
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{safe_symbol}?interval={interval}&range={rng}'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; PIFDashboard/1.0)',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))


@budget_bp.route('/api/quote/<symbol>', methods=['GET'])
@login_required
def get_quote(symbol):
    """Proxy a single security quote from Yahoo Finance.

    Whitelist-only to avoid abuse. Returns price, currency, previous close,
    daily change and exchange name. Cached 5 minutes in-process.
    """
    symbol = symbol.upper()
    if symbol not in ALLOWED_QUOTE_SYMBOLS:
        return jsonify({'error': 'symbol not whitelisted', 'symbol': symbol}), 400

    rng = request.args.get('range', '3mo')
    if rng not in ('5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'):
        rng = '3mo'

    cache_key = f'{symbol}:{rng}'
    now = time.time()
    cached = _QUOTE_CACHE.get(cache_key)
    if cached and (now - cached[0]) < QUOTE_CACHE_TTL:
        payload = dict(cached[1])
        payload['cached'] = True
        return jsonify(payload)

    try:
        data = _fetch_yahoo_chart(symbol, rng=rng)
        result = (data.get('chart') or {}).get('result') or []
        if not result:
            return jsonify({'error': 'no data from upstream', 'symbol': symbol}), 502
        r0 = result[0]
        meta = r0.get('meta') or {}
        price = meta.get('regularMarketPrice')
        prev = meta.get('chartPreviousClose') or meta.get('previousClose')
        change = (price - prev) if (price is not None and prev is not None) else None
        change_pct = (change / prev * 100.0) if (change is not None and prev) else None
        # Build historical series
        ts = r0.get('timestamp') or []
        closes = (((r0.get('indicators') or {}).get('quote') or [{}])[0]).get('close') or []
        series = []
        for i, t in enumerate(ts):
            c = closes[i] if i < len(closes) else None
            if c is None:
                continue
            series.append({'t': t, 'c': round(c, 4)})
        payload = {
            'symbol': symbol,
            'price': price,
            'currency': meta.get('currency'),
            'previousClose': prev,
            'change': change,
            'changePct': change_pct,
            'exchange': meta.get('exchangeName') or meta.get('fullExchangeName'),
            'longName': meta.get('longName') or meta.get('shortName') or symbol,
            'ts': meta.get('regularMarketTime'),
            'range': rng,
            'series': series,
            'fetchedAt': datetime.utcnow().isoformat() + 'Z',
            'cached': False,
        }
        _QUOTE_CACHE[cache_key] = (now, payload)
        return jsonify(payload)
    except urllib.error.HTTPError as e:
        return jsonify({'error': f'upstream HTTP {e.code}', 'symbol': symbol}), 502
    except Exception as e:
        return jsonify({'error': str(e), 'symbol': symbol}), 500

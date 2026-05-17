# Budget Tracker Blueprint
# Provides /budget/* routes with PIN authentication (same as app.py)

from flask import Blueprint, send_from_directory, jsonify, request, session, current_app
from pathlib import Path
from datetime import datetime
import json

budget_bp = Blueprint('budget', __name__, url_prefix='/budget')

STATIC_DIR = Path(__file__).resolve().parent.parent / 'static' / 'budget'

AUDIT_VALUE_MAX = 200
AUDIT_MAX_CHANGES_PER_SAVE = 60


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


def diff_state(old, new, path=''):
    """Yield (path, old, new) tuples for every leaf change between two JSON-like values."""
    if old == new:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old.keys()) | set(new.keys())):
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
    return send_from_directory(STATIC_DIR, 'index.html')


@budget_bp.route('/<path:filename>')
@login_required
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


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

    prev = db.execute(
        "SELECT data FROM budget_state WHERE user = 'ion'"
    ).fetchone()
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


@budget_bp.route('/api/audit', methods=['GET'])
@login_required
def get_audit():
    limit = min(int(request.args.get('limit', 50)), 500)
    db = _get_db()
    rows = db.execute("""
        SELECT ts, action, field, old_value, new_value FROM budget_audit
        WHERE user = 'ion' ORDER BY ts DESC, id DESC LIMIT ?
    """, (limit,)).fetchall()
    return jsonify([dict(r) for r in rows])

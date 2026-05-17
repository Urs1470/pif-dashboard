# Budget Tracker Blueprint
# Provides /budget/* routes with PIN authentication (same as app.py)

from flask import Blueprint, send_from_directory, jsonify, request, session, current_app
from pathlib import Path
from datetime import datetime
import json

budget_bp = Blueprint('budget', __name__, url_prefix='/budget')

STATIC_DIR = Path(__file__).resolve().parent.parent / 'static' / 'budget'


def _get_db():
    """Get DB connection using Flask app context."""
    from database import get_db as _get
    return _get()


def login_required(f):
    """Decorator: require PIN authentication."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated


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
    data_json = json.dumps(payload['data'], ensure_ascii=False)

    prev = db.execute(
        "SELECT data FROM budget_state WHERE user = 'ion'"
    ).fetchone()
    old_value = prev['data'] if prev else None

    db.execute("""
        INSERT INTO budget_state(user, data, updated)
        VALUES('ion', ?, ?)
        ON CONFLICT(user) DO UPDATE SET data = excluded.data, updated = excluded.updated
    """, (data_json, now))

    if old_value != data_json:
        db.execute("""
            INSERT INTO budget_audit(ts, user, action, field, old_value, new_value)
            VALUES(?, 'ion', 'update_state', 'full_state', ?, ?)
        """, (now,
              old_value[:200] if old_value else None,
              data_json[:200]))

    db.commit()
    return jsonify({'ok': True, 'updated': now})


@budget_bp.route('/api/audit', methods=['GET'])
@login_required
def get_audit():
    limit = min(int(request.args.get('limit', 50)), 500)
    db = _get_db()
    rows = db.execute("""
        SELECT ts, action, field FROM budget_audit
        WHERE user = 'ion' ORDER BY ts DESC LIMIT ?
    """, (limit,)).fetchall()
    return jsonify([dict(r) for r in rows])

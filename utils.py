import os
import uuid
import functools
from datetime import datetime

from flask import session, request, jsonify, redirect, url_for, abort, make_response
from database import get_db


def get_json_or_400():
    """Parsed JSON body as dict, or abort with a 400 JSON error."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(make_response(jsonify({'error': 'Body JSON invalid sau lipsa'}), 400))
    return data


VALID_TABLES = {
    'proiecte', 'tasks', 'task_subtasks', 'checklist_pif', 'jurnal',
    'timer_sessions', 'atasamente', 'echipamente', 'clienti',
    'global_tasks', 'global_task_sessions', 'checklist_categorii',
    'fault_codes', 'project_templates',
    'parametri_master',
}

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def safe_table(table_name):
    if table_name not in VALID_TABLES:
        raise ValueError(f"Invalid table name: {table_name}")
    return table_name


def generate_uuid():
    return str(uuid.uuid4())


def _check_api_token():
    """Validate Bearer token from Authorization header against PIF_API_TOKEN env var.
    Returns True if token is valid, False otherwise.  Sets g.api_token_auth = True
    so CSRF can skip its check for machine-to-machine requests."""
    from flask import g
    token = os.environ.get('PIF_API_TOKEN', '').strip()
    if not token:
        return False
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer ') and len(auth) > 7:
        import hmac as _hmac
        provided = auth[7:].strip()
        if _hmac.compare_digest(token, provided):
            g.api_token_auth = True
            return True
    return False


def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' in session:
            return f(*args, **kwargs)
        # Machine-to-machine: Accept Bearer token from Cowork / external tools
        if _check_api_token():
            return f(*args, **kwargs)
        if request.path.startswith('/api/'):
            return jsonify({'error': 'Unauthorized'}), 401
        return redirect(url_for('login_page'))
    return decorated_function


def get_app_setting(key, default=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM app_settings WHERE key = ?', (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default


def set_app_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) '
        'ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at',
        (key, value, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

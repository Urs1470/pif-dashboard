import os
import uuid
import functools
from datetime import datetime

from flask import session, request, jsonify, redirect, url_for
from database import get_db

VALID_TABLES = {
    'proiecte', 'tasks', 'task_subtasks', 'checklist_pif', 'jurnal',
    'timer_sessions', 'atasamente', 'echipamente', 'clienti',
    'global_tasks', 'global_task_sessions', 'checklist_categorii',
    'fault_codes', 'project_templates', 'budget_state', 'budget_audit',
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


def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Unauthorized'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
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

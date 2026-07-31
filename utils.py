import os
import re
import uuid
import functools
from datetime import datetime

from flask import session, request, jsonify, redirect, url_for, abort, make_response
from database import get_db


# ============ DATE CALENDARISTICE ============
# Regula: nu stocam niciodata o data pe care nu o putem citi. Formularele scriu
# deja ISO (DatePicker), dar API-ul accepta orice string — asa a ajuns in baza
# `23.02.2026` pe un proiect si `02.07.2026` pe un task, invizibile in Calendar
# fiindca nimic nu le putea plasa pe o zi.

# `data_incepere` a plecat in v36, `data_planificata` in v33 — nu mai exista coloane
# cu numele lor, deci n-au ce cauta aici.
DATE_FIELDS = frozenset({
    'data_start', 'data_sfarsit', 'data_scadenta', 'data_finalizare',
})

_ISO_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}')
_ZI_LUNA_AN = re.compile(r'^(\d{1,2})[./-](\d{1,2})[./-](\d{2}|\d{4})$')


def norm_date(value, camp='data'):
    """String ISO ('YYYY-MM-DD', sau un timestamp ISO neatins) pentru o data pe
    care o putem citi. Ridica ValueError pentru orice altceva.

    Gol ramane gol — nu inventam date. Valorile care incep deja cu ISO se intorc
    NEMODIFICATE, ca sa nu ciuntim timestampurile (`data_finalizare`).
    """
    if value is None:
        return value
    if not isinstance(value, str):
        raise ValueError(f'Campul „{camp}” trebuie sa fie text, nu {type(value).__name__}')
    v = value.strip()
    if not v:
        return ''
    if _ISO_PREFIX.match(v):
        # Validam ziua, ca sa nu treaca 2026-02-31.
        try:
            datetime.strptime(v[:10], '%Y-%m-%d')
        except ValueError:
            raise ValueError(f'Campul „{camp}”: data „{v}” nu exista in calendar')
        return v
    m = _ZI_LUNA_AN.match(v)
    if m:
        zi, luna, an = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if an < 100:
            an += 2000
        try:
            return datetime(an, luna, zi).strftime('%Y-%m-%d')
        except ValueError:
            raise ValueError(f'Campul „{camp}”: data „{v}” nu exista in calendar')
    raise ValueError(
        f'Campul „{camp}”: nu inteleg data „{v}”. Foloseste ZZ.LL.AAAA sau AAAA-LL-ZZ.')


def _norm_dates(obj, adancime=0):
    """Normalizeaza pe loc campurile de data dintr-un body JSON, oricat de
    adanc (importul de debrief are proiect + taskuri[] + implementari[])."""
    if adancime > 12:
        return obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in DATE_FIELDS:
                obj[k] = norm_date(v, k)
            else:
                _norm_dates(v, adancime + 1)
    elif isinstance(obj, list):
        for item in obj:
            _norm_dates(item, adancime + 1)
    return obj


def get_json_or_400():
    """Parsed JSON body as dict, or abort with a 400 JSON error.

    Palnia unica pentru toate scrierile JSON (28 de endpointuri), deci si locul
    potrivit pentru normalizarea datelor: o data aici, nu la fiecare INSERT.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(make_response(jsonify({'error': 'Body JSON invalid sau lipsa'}), 400))
    try:
        _norm_dates(data)
    except ValueError as e:
        abort(make_response(jsonify({'error': str(e)}), 400))
    return data


VALID_TABLES = {
    'proiecte', 'tasks', 'task_subtasks', 'task_dependencies',
    'clienti', 'global_tasks', 'implementari', 'calcule', 'app_settings',
}

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Planul intregului departament SRP sta intr-o aplicatie externa, partajat printr-un
# link care contine cheia de acces in FRAGMENT (dupa #), deci nu ajunge niciodata la
# serverul lor prin cererea HTTP. Il tinem in app_settings — baza de date e gitignored
# — si NU in cod sau in wiki, care sunt urmarite de git.
# Acelasi domeniu apare in CSP (`frame-src` in app.py): daca se schimba, se schimba
# in ambele locuri, altfel iframe-ul ramane alb fara nicio explicatie.
PLAN_DEPT_KEY = 'plan_departament_url'
PLAN_DEPT_HOST = 'app.projectplan-powerpoint.com'


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

import os
import time
import logging
import hashlib
import hmac
import secrets
import subprocess
import threading

from datetime import timedelta
from logging.handlers import RotatingFileHandler
from flask import (
    Flask, request, jsonify, render_template,
    session, redirect, url_for, send_from_directory,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from database import get_db, init_db, close_db
from utils import login_required, get_json_or_400, PLAN_DEPT_HOST
from csrf import init_csrf

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# ============ BLUEPRINTS ============

from blueprints.projects import projects_bp
from blueprints.tasks import tasks_bp
from blueprints.obsidian import obsidian_bp
from blueprints.admin import admin_bp

app.register_blueprint(projects_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(obsidian_bp)
app.register_blueprint(admin_bp)

init_csrf(app)

# ============ CLIENT IP ============


def _client_ip():
    """Real client IP, preferring CF-Connecting-IP (set by Cloudflare Tunnel)."""
    return (request.headers.get('CF-Connecting-IP') or request.remote_addr or '127.0.0.1')


# ============ SECRET KEY ============

SECRET_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.secret_key')


def get_or_create_secret_key():
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key
    if os.path.exists(SECRET_KEY_FILE):
        with open(SECRET_KEY_FILE, 'rb') as f:
            return f.read()
    key = os.urandom(32)
    with open(SECRET_KEY_FILE, 'wb') as f:
        f.write(key)
    return key


app.secret_key = get_or_create_secret_key()
app.teardown_appcontext(close_db)

# ============ VERSION HASH ============

_USE_DIST = os.environ.get('PIF_USE_DIST', 'true').lower() in ('1', 'true', 'yes')


def file_hash(filepath):
    try:
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except FileNotFoundError:
        # Resolve relative to this file so a non-root CWD (e.g. the preview
        # runner) still finds the asset instead of falling back to 'dev'.
        try:
            abspath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)
            with open(abspath, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:8]
        except FileNotFoundError:
            # logger is defined later in this module; file_hash runs at import
            # time (before setup_logging), so fetch the named logger directly.
            logging.getLogger('pif_dashboard').warning(f"Asset not found for hashing: {filepath}")
            return 'dev'


def _asset_path(name):
    """Return 'dist/<name>' when minified builds are active, else '<name>'."""
    if _USE_DIST and os.path.isfile(os.path.join('static', 'dist', name)):
        return f'dist/{name}'
    return name


_asset_versions = {
    # Only the login page remains a server-rendered template; it versions
    # login.css via `style_version`. The Svelte SPA self-versions its assets.
    'style_version': file_hash('static/login.css'),
}


@app.context_processor
def inject_version():
    ctx = dict(_asset_versions)
    ctx['use_dist'] = _USE_DIST
    ctx['asset_path'] = _asset_path
    ctx['csp_nonce'] = getattr(request, '_csp_nonce', '')
    return ctx


# ============ SESSION CONFIG ============

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() not in ('0', 'false', 'no')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'


@app.before_request
def make_session_permanent():
    session.permanent = True


# ============ LOGGING ============

LOGS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOGS_FOLDER, exist_ok=True)


def setup_logging():
    _logger = logging.getLogger('pif_dashboard')
    _logger.setLevel(logging.INFO)
    if _logger.handlers:
        return _logger
    handler = RotatingFileHandler(
        os.path.join(LOGS_FOLDER, 'app.log'),
        maxBytes=1024 * 1024,
        backupCount=10,
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S',
    ))
    _logger.addHandler(handler)
    return _logger


logger = setup_logging()

# ============ RATE LIMITING ============

rate_limit_store = {}
# 60/minut e potrivit pentru un singur utilizator care navigheaza normal, dar
# prea putin cand deschizi zeci de pagini la rand: testul de fum (scripts/smoke_ui.py)
# ridica pragul prin PIF_RATE_LIMIT. In productie ramane 60.
RATE_LIMIT = int(os.environ.get('PIF_RATE_LIMIT', '60'))
RATE_WINDOW = 60
_RATE_MAX_IPS = 10000
_rate_last_evict = 0.0


def check_rate_limit():
    global _rate_last_evict
    client_ip = _client_ip()
    now = time.time()

    if now - _rate_last_evict > RATE_WINDOW:
        stale = [ip for ip, entries in rate_limit_store.items()
                 if all(now - ts >= RATE_WINDOW for ts, _ in entries)]
        for ip in stale:
            del rate_limit_store[ip]
        _rate_last_evict = now

    if len(rate_limit_store) >= _RATE_MAX_IPS and client_ip not in rate_limit_store:
        return False

    if client_ip in rate_limit_store:
        rate_limit_store[client_ip] = [
            (ts, count) for ts, count in rate_limit_store[client_ip]
            if now - ts < RATE_WINDOW
        ]

    request_count = sum(count for ts, count in rate_limit_store.get(client_ip, []))
    if request_count >= RATE_LIMIT:
        return False

    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []
    rate_limit_store[client_ip].append((now, 1))
    return True


# Limita dedicata, stricta, pe login: 5 incercari / 5 minute per IP.
# Limita generala (60/min, in-memory per worker, golita la fiecare autodeploy)
# permitea brute-force pe un PIN scurt.
LOGIN_LIMIT = 5
LOGIN_WINDOW = 300
_login_attempts = {}


def check_login_rate_limit():
    client_ip = _client_ip()
    now = time.time()
    attempts = [ts for ts in _login_attempts.get(client_ip, []) if now - ts < LOGIN_WINDOW]
    if len(attempts) >= LOGIN_LIMIT:
        _login_attempts[client_ip] = attempts
        return False
    attempts.append(now)
    _login_attempts[client_ip] = attempts
    if len(_login_attempts) > 5000:
        for ip in [ip for ip, a in _login_attempts.items() if all(now - ts >= LOGIN_WINDOW for ts in a)]:
            del _login_attempts[ip]
    return True


# ============ STARTUP + BEFORE/AFTER REQUEST ============

_startup_initialized = False
_startup_lock = threading.Lock()


@app.before_request
def before_request_func():
    global _startup_initialized

    if not _startup_initialized:
        with _startup_lock:
            if not _startup_initialized:
                with app.app_context():
                    init_db()
                if not os.environ.get('PIF_DASHBOARD_PIN'):
                    if app.debug:
                        logger.warning("PIF_DASHBOARD_PIN nu este setat — mod DEBUG, se foloseste fallback.")
                    else:
                        logger.critical("PIF_DASHBOARD_PIN nu este setat! Loginul va esua. Seteaza Environment=PIF_DASHBOARD_PIN=... in systemd.")
                _startup_initialized = True
                logger.info("PIF Dashboard initialized")

    _rl_api = request.path.startswith('/api/') and request.path not in ('/api/login', '/api/healthz')
    _rl_login = request.path in ('/login', '/login-hash') and request.method == 'POST'
    if _rl_login and not check_login_rate_limit():
        logger.warning(f"Login rate limit exceeded for IP: {_client_ip()}")
        return jsonify({'error': 'Prea multe incercari de login. Reincearca in cateva minute.'}), 429, {'Retry-After': str(LOGIN_WINDOW)}
    if _rl_api or _rl_login:
        if not check_rate_limit():
            logger.warning(f"Rate limit exceeded for IP: {_client_ip()} on {request.path}")
            return jsonify({'error': 'Rate limit exceeded. Maximum 60 requests per minute.'}), 429, {'Retry-After': str(RATE_WINDOW)}

    request._csp_nonce = secrets.token_urlsafe(16)

    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - IP: {request.remote_addr}")


@app.after_request
def after_request_func(response):
    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - Status: {response.status_code}")
    # HTML shell must never be served stale: without this, the browser's
    # heuristic HTTP cache (and the SW's fetch passing through it) keeps the
    # old index.html with old ?v= asset hashes after a deploy.
    if response.content_type and response.content_type.startswith('text/html'):
        response.headers.setdefault('Cache-Control', 'no-cache, must-revalidate')
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'same-origin')
    response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    # Vizualizatorul PDF.js (gazduit local) are nevoie de worker/wasm/blob — CSP dedicat doar pe calea lui.
    if request.path.startswith('/static/pdfjs/'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'wasm-unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: blob:; "
            "font-src 'self' data: blob:; "
            "worker-src 'self' blob:; "
            "connect-src 'self' blob: data:; "
            "frame-ancestors 'none'; base-uri 'self'"
        )
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; "
        "img-src 'self' data: blob: https:; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "connect-src 'self' https://query1.finance.yahoo.com; "
        # Planul de departament (aplicatie externa) se afiseaza incorporat in
        # pagina /departament. Exact acest domeniu, nimic mai larg. Constanta e
        # in utils.PLAN_DEPT_HOST — daca se schimba, se schimba in ambele locuri.
        f"frame-src https://{PLAN_DEPT_HOST}; "
        "frame-ancestors 'none'; "
        "base-uri 'self'"
    )
    return response


# ============ AUTH ============

def get_hashed_pin():
    pin = os.environ.get('PIF_DASHBOARD_PIN')
    if not pin:
        raise RuntimeError("PIF_DASHBOARD_PIN nu este setat! Seteaza variabila de mediu.")
    if not hasattr(get_hashed_pin, '_hash'):
        get_hashed_pin._hash = generate_password_hash(pin)
    return get_hashed_pin._hash


def _git_commit():
    """Return current git commit hash (short), cached."""
    if not hasattr(_git_commit, '_hash'):
        try:
            r = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'],
                               capture_output=True, text=True, timeout=5,
                               cwd=os.path.dirname(os.path.abspath(__file__)))
            _git_commit._hash = r.stdout.strip() if r.returncode == 0 else '?'
        except Exception:
            _git_commit._hash = '?'
    return _git_commit._hash


@app.route('/api/healthz')
def healthz():
    return jsonify({'status': 'ok', 'timestamp': int(time.time()),
                    'commit': _git_commit()})


@app.route('/api/health')
def health_redirect():
    return redirect('/api/healthz', code=301)


@app.route('/api/me')
def whoami():
    """Stare autentificare (public). Folosit de /calc ca sa afiseze extrasele de carti
    (protejate) doar daca esti logat, fara a le expune colegilor anonimi."""
    return jsonify({'authenticated': bool(session.get('authenticated'))})


@app.route('/login')
def login_page():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    data = get_json_or_400()
    pin = data.get('pin', '')
    if check_password_hash(get_hashed_pin(), pin):
        session['authenticated'] = True
        logger.info(f"Login successful for IP: {request.remote_addr}")
        return jsonify({'success': True})
    logger.warning(f"Login failed for IP: {request.remote_addr}")
    return jsonify({'error': 'Invalid PIN'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))


@app.route('/login-hash', methods=['POST'])
def login_hash():
    data = get_json_or_400()
    pin_hash = data.get('pin_hash', '')
    if not pin_hash:
        return jsonify({'error': 'Missing pin_hash'}), 400
    pin = os.environ.get('PIF_DASHBOARD_PIN')
    if not pin:
        return jsonify({'error': 'Server misconfigured'}), 500
    expected_hash = hashlib.sha256(pin.encode()).hexdigest()
    if hmac.compare_digest(str(pin_hash), expected_hash):
        session['authenticated'] = True
        return jsonify({'success': True})
    return jsonify({'error': 'Invalid hash'}), 401


# ============ FRONTEND ROUTES ============

_DIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'dist')


def _serve_frontend():
    """Serve the Svelte build (the only frontend; the legacy vanilla-JS app and
    its `/m` mobile twin were removed — the responsive SPA covers both)."""
    return send_from_directory(_DIST_DIR, 'index.html')


@app.route('/')
@login_required
def index():
    return _serve_frontend()


@app.route('/assets/<path:filename>')
def dist_assets(filename):
    """Serve Vite-built assets (JS/CSS with content hashes)."""
    return send_from_directory(os.path.join(_DIST_DIR, 'assets'), filename)


@app.route('/favicon.svg')
def favicon():
    return send_from_directory(_DIST_DIR, 'favicon.svg')


@app.route('/manifest.json')
def manifest():
    return send_from_directory(_DIST_DIR, 'manifest.json')


@app.route('/calc')
def calc_public():
    """Calculator actionari electrice — varianta de sine statatoare, PUBLICA (fara login),
    de impartit cu echipa. Doar calculatorul (fara sidebar/proiecte/date). Build: calc.html."""
    return send_from_directory(_DIST_DIR, 'calc.html')


_DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'private_docs')


@app.route('/docs/<path:filename>')
def protected_docs(filename):
    """Extrase din manuale (DOAR paginile citate, drept de autor respectat) — accesibile public,
    inclusiv din /calc. Folosit de linkurile 'Documentatie' din calculator (vizualizatorul PDF.js).
    X-Robots-Tag: noindex/noarchive ca extrasele sa nu fie indexate de motoarele de cautare."""
    resp = send_from_directory(_DOCS_DIR, filename)
    resp.headers['X-Robots-Tag'] = 'noindex, noarchive'
    return resp


# ============ PWA ROUTES ============

@app.route('/service-worker.js')
def service_worker():
    return app.send_static_file('service-worker.js')


@app.after_request
def add_sw_header(response):
    if request.path == '/service-worker.js':
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Cache-Control'] = 'no-cache'
    return response


# ============ AUTO-DEPLOY WEBHOOK ============
# GitHub push -> this endpoint -> git fetch+reset --hard origin/master -> restart.
# HMAC-authenticated (X-Hub-Signature-256), CSRF-exempt via the /webhook/ prefix.
# NOTE: this route was accidentally dropped during the blueprint refactor, which
# silently broke auto-deploy. Restored here; keep it in app.py (deploy infra,
# not a domain route).

DEPLOY_SECRET_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.deploy_secret')

# Recent X-GitHub-Delivery IDs — replay guard for the deploy webhook.
_webhook_seen_deliveries = []


def get_deploy_secret():
    if os.path.exists(DEPLOY_SECRET_FILE):
        with open(DEPLOY_SECRET_FILE, 'r') as f:
            return f.read().strip()
    return None


@app.route('/webhook/deploy', methods=['POST'])
def webhook_deploy():
    secret = get_deploy_secret()
    if not secret:
        return 'Webhook not configured', 500

    signature = request.headers.get('X-Hub-Signature-256', '')
    if not signature.startswith('sha256='):
        return 'Invalid signature', 403

    expected = 'sha256=' + hmac.new(
        secret.encode(), request.data, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return 'Bad signature', 403

    # Replay guard: reject a delivery already processed.
    delivery_id = request.headers.get('X-GitHub-Delivery', '')
    if delivery_id:
        if delivery_id in _webhook_seen_deliveries:
            logger.warning(f"Webhook replay rejected: {delivery_id}")
            return 'Duplicate delivery', 409
        _webhook_seen_deliveries.append(delivery_id)
        if len(_webhook_seen_deliveries) > 200:
            del _webhook_seen_deliveries[:-200]

    payload = request.get_json(silent=True) or {}
    ref = payload.get('ref', '')
    if ref != 'refs/heads/master':
        return 'Not master branch, skipping', 200

    project_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        # fetch + reset --hard makes the deploy idempotent even if the server
        # worktree is dirty (audit scripts regenerate tracked JSONs in-place).
        fetch = subprocess.run(
            ['git', 'fetch', 'origin', 'master'],
            cwd=project_dir, capture_output=True, text=True, timeout=30
        )
        if fetch.returncode != 0:
            logger.error(f"Auto-deploy git fetch failed: {fetch.stderr}")
            return 'Fetch failed - check server logs', 500
        result = subprocess.run(
            ['git', 'reset', '--hard', 'origin/master'],
            cwd=project_dir, capture_output=True, text=True, timeout=30
        )
        logger.info(f"Auto-deploy git reset: {result.stdout.strip()}")
        if result.returncode != 0:
            logger.error(f"Auto-deploy git reset failed: {result.stderr}")
            return 'Reset failed - check server logs', 500
    except Exception:
        logger.exception("Auto-deploy error")
        return 'Deploy error - check server logs', 500

    # Install new deps (prevents "no module X" when a commit adds dependencies).
    venv_pip = os.path.join(project_dir, 'venv', 'bin', 'pip')
    venv_python = os.path.join(project_dir, 'venv', 'bin', 'python')
    req_file = os.path.join(project_dir, 'requirements.txt')
    if os.path.exists(req_file):
        pip_cmds = []
        if os.path.exists(venv_python):
            pip_cmds.append([venv_python, '-m', 'pip', 'install', '-r', req_file, '--quiet'])
        if os.path.exists(venv_pip):
            pip_cmds.append([venv_pip, 'install', '-r', req_file, '--quiet'])
        for pip_cmd in pip_cmds:
            try:
                pip_result = subprocess.run(
                    pip_cmd, cwd=project_dir, capture_output=True, text=True, timeout=120
                )
                if pip_result.returncode != 0:
                    logger.error(f"Auto-deploy pip install failed ({pip_cmd[0]}): {pip_result.stderr}")
                else:
                    logger.info(f"Auto-deploy pip install OK ({pip_cmd[0]})")
                    break
            except Exception as e:
                logger.error(f"Auto-deploy pip install error ({pip_cmd[0]}): {e}")

    subprocess.Popen(
        ['sudo', 'systemctl', 'restart', 'pif-dashboard'],
        cwd=project_dir
    )

    return 'Deploy triggered', 200


@app.route('/api/deploy', methods=['POST'])
def api_deploy():
    """Deploy via Bearer token (PIF_API_TOKEN).

    Simpler alternative to the GitHub webhook for machine-to-machine deploys
    when the HMAC secret is not available (e.g. different network).
    """
    from utils import _check_api_token
    if not _check_api_token():
        return jsonify({'error': 'Unauthorized'}), 401

    project_dir = os.path.dirname(os.path.abspath(__file__))
    try:
        fetch = subprocess.run(
            ['git', 'fetch', 'origin', 'master'],
            cwd=project_dir, capture_output=True, text=True, timeout=30
        )
        if fetch.returncode != 0:
            return jsonify({'error': f'Fetch failed: {fetch.stderr}'}), 500
        result = subprocess.run(
            ['git', 'reset', '--hard', 'origin/master'],
            cwd=project_dir, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return jsonify({'error': f'Reset failed: {result.stderr}'}), 500
        git_msg = result.stdout.strip()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    # Install deps
    venv_pip = os.path.join(project_dir, 'venv', 'bin', 'pip')
    venv_python = os.path.join(project_dir, 'venv', 'bin', 'python')
    req_file = os.path.join(project_dir, 'requirements.txt')
    if os.path.exists(req_file):
        pip_cmds = []
        if os.path.exists(venv_python):
            pip_cmds.append([venv_python, '-m', 'pip', 'install', '-r', req_file, '--quiet'])
        if os.path.exists(venv_pip):
            pip_cmds.append([venv_pip, 'install', '-r', req_file, '--quiet'])
        for pip_cmd in pip_cmds:
            try:
                pip_result = subprocess.run(pip_cmd, cwd=project_dir, capture_output=True, text=True, timeout=120)
                if pip_result.returncode == 0:
                    break
            except Exception:
                pass

    # Restart service
    subprocess.Popen(['sudo', 'systemctl', 'restart', 'pif-dashboard'], cwd=project_dir)
    logger.info(f"API deploy triggered: {git_msg}")

    return jsonify({'status': 'ok', 'git': git_msg}), 200


# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def page_not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Endpoint inexistent'}), 404
    return '<h1>404</h1><p>Pagina nu a fost gasita.</p>', 404


@app.errorhandler(500)
def internal_error(e):
    logger.error(f"500 Internal Server Error: {e}")
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Eroare interna a serverului'}), 500
    return '<h1>500</h1><p>Eroare interna a serverului.</p>', 500


if __name__ == '__main__':
    init_db()
    logger.info("PIF Dashboard starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)

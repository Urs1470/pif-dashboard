import os
import time
import logging
import hashlib
import hmac
import secrets
import threading

from datetime import timedelta
from logging.handlers import RotatingFileHandler
from flask import (
    Flask, request, jsonify, render_template,
    session, redirect, url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from database import get_db, init_db, close_db
from utils import login_required
from csrf import init_csrf

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# ============ BLUEPRINTS ============

from blueprints.budget import budget_bp
from blueprints.assistant import assistant_bp
from blueprints.projects import projects_bp
from blueprints.tasks import tasks_bp
from blueprints.timer import timer_bp
from blueprints.parametri import parametri_bp
from blueprints.obsidian import obsidian_bp
from blueprints.admin import admin_bp

app.register_blueprint(budget_bp)
app.register_blueprint(assistant_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(timer_bp)
app.register_blueprint(parametri_bp)
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

_USE_DIST = os.environ.get('PIF_USE_DIST', '').lower() in ('1', 'true', 'yes')


def file_hash(filepath):
    try:
        with open(filepath, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:8]
    except FileNotFoundError:
        logger.warning(f"Asset not found for hashing: {filepath}")
        return 'dev'


def _asset_path(name):
    """Return 'dist/<name>' when minified builds are active, else '<name>'."""
    if _USE_DIST and os.path.isfile(os.path.join('static', 'dist', name)):
        return f'dist/{name}'
    return name


_asset_versions = {
    'js_version': file_hash('static/mobile.js'),
    'sw_version': file_hash('static/service-worker.js'),
    'app_version': file_hash('static/app.js'),
    'core_version': file_hash('static/core.js'),
    'style_version': file_hash('static/style.css'),
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
RATE_LIMIT = 60
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
                    try:
                        from blueprints.projects import init_default_templates
                        init_default_templates()
                    except Exception as e:
                        logger.warning(f"init_default_templates failed: {e}")
                if not os.environ.get('PIF_DASHBOARD_PIN'):
                    if app.debug:
                        logger.warning("PIF_DASHBOARD_PIN nu este setat — mod DEBUG, se foloseste fallback.")
                    else:
                        logger.critical("PIF_DASHBOARD_PIN nu este setat! Loginul va esua. Seteaza Environment=PIF_DASHBOARD_PIN=... in systemd.")
                _startup_initialized = True
                logger.info("PIF Dashboard initialized")

    _rl_api = request.path.startswith('/api/') and request.path not in ('/api/login', '/api/healthz')
    _rl_login = request.path in ('/login', '/login-hash') and request.method == 'POST'
    if _rl_api or _rl_login:
        if not check_rate_limit():
            logger.warning(f"Rate limit exceeded for IP: {request.remote_addr} on {request.path}")
            return jsonify({'error': 'Rate limit exceeded. Maximum 60 requests per minute.', 'retry_after': RATE_WINDOW}), 429

    request._csp_nonce = secrets.token_urlsafe(16)

    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - IP: {request.remote_addr}")


@app.after_request
def after_request_func(response):
    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - Status: {response.status_code}")
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'same-origin')
    response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; "
        "img-src 'self' data: blob: https:; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "connect-src 'self' https://query1.finance.yahoo.com; "
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


@app.route('/api/healthz')
def healthz():
    return jsonify({'status': 'ok', 'timestamp': int(time.time())})


@app.route('/api/health')
def health_redirect():
    return redirect('/api/healthz', code=301)


@app.route('/login')
def login_page():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    return render_template('login.html')


@app.route('/login', methods=['POST'])
def login():
    data = request.json
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
    data = request.json
    pin_hash = data.get('pin_hash', '')
    if not pin_hash:
        return jsonify({'success': False, 'error': 'Missing pin_hash'}), 400
    pin = os.environ.get('PIF_DASHBOARD_PIN')
    if not pin:
        return jsonify({'success': False, 'error': 'Server misconfigured'}), 500
    expected_hash = hashlib.sha256(pin.encode()).hexdigest()
    if hmac.compare_digest(str(pin_hash), expected_hash):
        session['authenticated'] = True
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid hash'}), 401


# ============ FRONTEND ROUTES ============

@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/parametri')
@app.route('/notite')
@app.route('/administrativ')
@login_required
def spa_catchall():
    return render_template('index.html')


# ============ PWA ROUTES ============

@app.route('/m')
@login_required
def mobile():
    """Mobile PWA shell — separate template, separate JS bundle.
    Optimized for field use: bottom-nav, quick-capture FAB, offline IndexedDB."""
    return render_template('mobile.html')


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
    from blueprints.projects import init_default_templates
    init_default_templates()
    logger.info("PIF Dashboard starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)

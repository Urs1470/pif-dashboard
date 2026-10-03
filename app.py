import os
import time
import logging
import functools
import hashlib
import hmac
import ipaddress
import secrets
import subprocess
import threading

from datetime import timedelta
from logging.handlers import RotatingFileHandler
from flask import (
    Flask, request, jsonify, render_template,
    session, redirect, url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix

from database import init_db, close_db
from utils import get_json_or_400, safe_next_url
from csrf import init_csrf

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

# ============ BLUEPRINTS ============

from blueprints.projects import projects_bp
from blueprints.tasks import tasks_bp
from blueprints.obsidian import obsidian_bp
from blueprints.admin import admin_bp
from blueprints.app_update import app_update_bp
from blueprints.sync import sync_bp
from blueprints.torqa_web import torqa_web_bp, SesiuneFaraStatice, CSP_TORQA, PREFIX_URL

app.register_blueprint(projects_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(obsidian_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(app_update_bp)
app.register_blueprint(sync_bp)
app.register_blueprint(torqa_web_bp)

# Fisierele statice ale Torqa web (/torqa/<fisier>) nu citesc si nu scriu sesiunea: altfel
# fiecare ar purta `Set-Cookie` si `Vary: Cookie`, iar browserul nu le-ar mai tine in cache.
# Orice alta cerere merge ca inainte — vezi blueprints/torqa_web.py.
app.session_interface = SesiuneFaraStatice()

init_csrf(app)

# ============ CLIENT IP ============

# Cum ajunge o cerere la gunicorn. DIN DEPOZIT SE STIE doar ca site-ul sta in spatele unui
# Cloudflare Tunnel (CLAUDE.md) si ca `ProxyFix(x_for=1)` crede un singur hop. Adresa pe care
# asculta gunicorn si de unde se conecteaza `cloudflared` stau in unitatea systemd de pe
# server, nu in repo (docs/decizii/2026-10-03-curatenie-dupa-retragere.md). PRESUPUNEREA de
# aici: cloudflared ruleaza pe aceeasi masina si ajunge la gunicorn de la loopback (sau pe un
# socket UNIX), iar Cloudflare a pus deja in cerere `CF-Connecting-IP` (adresa reala,
# suprascrisa pe marginea lor) si `X-Forwarded-For`. Daca nu e asa, cererile din tunel apar in
# log cu adresa lui cloudflared: se repara cu `PIF_TRUSTED_PROXIES`, fara cod.
#
# Antetele astea le poate scrie ORICINE ajunge direct la gunicorn (un client din LAN, daca
# portul nu e legat doar la loopback). `ProxyFix` mai jos le crede fara sa intrebe de unde vin,
# deci `request.remote_addr` se poate falsifica cu un `X-Forwarded-For`, iar un
# `CF-Connecting-IP` inventat ar da fiecarei incercari de PIN o „adresa" noua: limita de 5 /
# 5 minute n-ar mai limita nimic. De aceea antetele conteaza doar daca SOCKETUL care a
# ajuns la gunicorn e al unui proxy de incredere; altfel adresa clientului e adresa socketului.
#
# Implicit proxy-ul de incredere e loopback-ul. Daca `cloudflared` ajunge la gunicorn pe alta
# adresa (de pilda IP-ul din LAN al masinii), se adauga in `PIF_TRUSTED_PROXIES` (adrese sau
# retele CIDR, separate prin virgula).
PROXY_DE_INCREDERE_IMPLICIT = '127.0.0.1,::1'


@functools.lru_cache(maxsize=8)
def _retele_de_incredere(brut):
    retele = []
    for parte in brut.split(','):
        parte = parte.strip()
        if not parte:
            continue
        try:
            retele.append(ipaddress.ip_network(parte, strict=False))
        except ValueError:
            logging.getLogger('pif_dashboard').error(
                "PIF_TRUSTED_PROXIES: ignor %r (nu e adresa sau retea)", parte)
    return tuple(retele)


def _ip_valid(text):
    """`ipaddress.ip_address(text)` sau None. IPv4 mapat in IPv6 (`::ffff:1.2.3.4`) devine IPv4."""
    try:
        ip = ipaddress.ip_address(str(text).strip())
    except ValueError:
        return None
    if ip.version == 6 and ip.ipv4_mapped is not None:
        return ip.ipv4_mapped
    return ip


def _proxy_de_incredere(adresa):
    # Gunicorn pe un socket UNIX (`--bind unix:...`) nu are adresa de peer (REMOTE_ADDR gol sau o
    # cale): la un socket UNIX ajung doar procese de pe aceeasi masina, deci proxy-ul e local.
    if not str(adresa).strip() or str(adresa).startswith('/'):
        return True
    ip = _ip_valid(adresa)
    if ip is None:
        return False
    brut = os.environ.get('PIF_TRUSTED_PROXIES', PROXY_DE_INCREDERE_IMPLICIT)
    return any(ip.version == net.version and ip in net for net in _retele_de_incredere(brut))


def _adresa_socket():
    """Adresa socketului care a ajuns la gunicorn, asa cum era INAINTE de `ProxyFix`."""
    orig = request.environ.get('werkzeug.proxy_fix.orig') or {}
    return orig.get('REMOTE_ADDR') or request.environ.get('REMOTE_ADDR') or ''


def _client_ip():
    """Adresa clientului, pentru limitele de cereri si pentru log.

    De la un proxy de incredere (cloudflared, local): `CF-Connecting-IP`, altfel adresa din
    `X-Forwarded-For` pe care `ProxyFix` a pus-o in `remote_addr`. De la oricine altcineva:
    adresa socketului, fara sa se uite la antete."""
    socket_ = _adresa_socket()
    if _proxy_de_incredere(socket_):
        for candidat in (request.headers.get('CF-Connecting-IP', ''), request.remote_addr or ''):
            ip = _ip_valid(candidat)
            if ip is not None:
                return str(ip)
        return '127.0.0.1'
    return socket_


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


_asset_versions = {
    # The login page is the only server-rendered template; it versions login.css
    # via `style_version`. (The Svelte SPA that used to self-version its assets
    # was retired on 2026-10-03.)
    'style_version': file_hash('static/login.css'),
}


@app.context_processor
def inject_version():
    ctx = dict(_asset_versions)
    ctx['csp_nonce'] = getattr(request, '_csp_nonce', '')
    return ctx


# ============ SESSION CONFIG ============

# UN AN, NU O LUNA (cerut de Ion, 2026-08-07: „nu vreau sa introduc pinul de
# fiecare data"). De cand exista aplicatia de pe telefon, reautentificarea nu mai
# e o masura de siguranta, e o taxa: aplicatia sta in spatele ecranului blocat al
# telefonului, care e granita reala. Cine deschide telefonul deschide si
# dashboardul — asumat, pentru o unealta personala cu un singur utilizator.
# Cookie-ul se reinnoieste la fiecare cerere (`session.permanent = True` mai jos
# + `SESSION_REFRESH_EACH_REQUEST`, implicit adevarat), deci anul se numara de la
# ultima folosire, nu de la login.
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
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
# prea putin cand o proba trimite zeci de cereri la rand: serverul de proba al
# scripts/banc.py ridica pragul prin PIF_RATE_LIMIT. In productie ramane 60.
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
    _rl_login = request.path == '/login' and request.method == 'POST'
    if _rl_login and not check_login_rate_limit():
        logger.warning(f"Login rate limit exceeded for IP: {_client_ip()}")
        return jsonify({'error': 'Prea multe incercari de login. Reincearca in cateva minute.'}), 429, {'Retry-After': str(LOGIN_WINDOW)}
    if _rl_api or _rl_login:
        if not check_rate_limit():
            logger.warning(f"Rate limit exceeded for IP: {_client_ip()} on {request.path}")
            return jsonify({'error': 'Rate limit exceeded. Maximum 60 requests per minute.'}), 429, {'Retry-After': str(RATE_WINDOW)}

    request._csp_nonce = secrets.token_urlsafe(16)

    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - IP: {_client_ip()}")


def _default_csp(nonce):
    """Politica de continut a tot ce nu e Torqa web (`/torqa/` si-o are pe a lui, `CSP_TORQA`).

    Cat serveste serverul fara Torqa: pagina de login (`templates/login.html`), `/admin/db-upload`,
    raspunsurile JSON ale API-ului, paginile de eroare si fisierele din `/static/`. Nimic din exterior
    (pana pe 2026-10-03 mai listau CDN-uri, Google Fonts si `query1.finance.yahoo.com`, ramase de la
    SPA si calculator), si niciun script sau stil inline fara nonce-ul cererii: nici `'unsafe-inline'`,
    nici atribute `style` sau handlere `onclick=`/`onsubmit=` in pagini (un test le cauta).

    Nonce-ul il pune `before_request_func` pe cerere si il ia in template `inject_version`
    (`csp_nonce`), deci e acelasi in antet si in pagina. Un raspuns dat inainte sa existe nonce
    (429 de la limita de cereri, 403 de la CSRF) primeste politica fara el: n-are nimic inline.
    """
    n = " 'nonce-%s'" % nonce if nonce else ''
    return (
        "default-src 'self'; "
        "img-src 'self' data:; "          # `data:` = iconita paginii de login
        "script-src 'self'%s; "
        "style-src 'self'%s; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'" % (n, n)
    )


@app.after_request
def after_request_func(response):
    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - Status: {response.status_code}")
    # HTML (the login page, error pages) must never be served stale: without this,
    # the browser's heuristic HTTP cache keeps the old page with the old
    # login.css ?v= hash after a deploy.
    if response.content_type and response.content_type.startswith('text/html'):
        response.headers.setdefault('Cache-Control', 'no-cache, must-revalidate')
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'same-origin')
    response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
    # Torqa web (build Angular) are politica lui, pe calea lui: cere `unsafe-eval` (runtime-ul
    # de pluginuri) si nu cere nimic din exterior. Motivele, linie cu linie, stau langa
    # constanta, in blueprints/torqa_web.py.
    if request.path == '/torqa' or request.path.startswith('/torqa/'):
        response.headers['Content-Security-Policy'] = CSP_TORQA
    response.headers.setdefault('Content-Security-Policy',
                                _default_csp(getattr(request, '_csp_nonce', '')))
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


@app.route('/login')
def login_page():
    # `?next=` = unde te intorci dupa PIN (ex. /torqa/). Doar o cale a acestui site;
    # orice altceva devine `/` — vezi utils.safe_next_url.
    nxt = safe_next_url(request.args.get('next'))
    if session.get('authenticated'):
        return redirect(nxt)
    return render_template('login.html', next_url=nxt)


@app.route('/login', methods=['POST'])
def login():
    data = get_json_or_400()
    pin = data.get('pin', '')
    if check_password_hash(get_hashed_pin(), pin):
        session['authenticated'] = True
        logger.info(f"Login successful for IP: {_client_ip()}")
        # Serverul decide unde duce redirectul: pagina de login primeste `next` din query,
        # dar tot ce vine de la client se valideaza din nou aici.
        return jsonify({'success': True, 'next': safe_next_url(data.get('next'))})
    logger.warning(f"Login failed for IP: {_client_ip()}")
    return jsonify({'error': 'Invalid PIN'}), 401


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))



# ============ INTRARE ============

@app.route('/')
def index():
    """Interfata veche (SPA-ul Svelte) a fost retrasa pe 2026-10-03; serverul e backend-ul
    Torqa. Radacina duce la Torqa web (`/torqa/`), care cere singur sesiunea si trimite la
    `/login?next=/torqa/` cand lipseste. Fara login_required aici: redirectul nu da nimic."""
    return redirect(PREFIX_URL)


# ============ SERVICE WORKER (RETRAS) ============
# `/service-worker.js` serveste worker-ul care se retrage singur (static/service-worker.js):
# browserele care au instalat interfata veche il gasesc aici, il instaleaza peste cel vechi,
# iar el isi sterge cache-urile si se dezinregistreaza. Ruta trebuie sa ramana.

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


# `POST /api/deploy` (acelasi deploy, cu tokenul de masina in loc de HMAC) a plecat pe 2026-10-03:
# nu-l chema nimic; deploy-ul merge prin `/webhook/deploy`, la push pe master.


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

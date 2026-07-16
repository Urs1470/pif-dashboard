# Obsidian Vault Integration Blueprint (read-only)
# Ion keeps study notes in an Obsidian vault synced to the laptop-server via
# InSync (Google Drive). The app reads .md files directly -- never writes -- so
# there is no risk of sync conflicts. The vault path is configured at runtime
# from the Administrativ tab and stored in app_settings.

import os
import re
import subprocess
import threading
import time

from flask import Blueprint, jsonify, request

from database import get_db
from utils import get_app_setting, set_app_setting, login_required

obsidian_bp = Blueprint('obsidian', __name__)

# ---------------------------------------------------------------------------
# Constants & cache
# ---------------------------------------------------------------------------

OBSIDIAN_SETTING_KEY = 'obsidian_vault_path'
OBSIDIAN_FOLDERS_KEY = 'obsidian_folders'
_obsidian_cache = {'path': None, 'sig': None, 'notes': None}
_OBSIDIAN_SKIP_DIRS = {'.obsidian', '.trash', '.git', '.smart-env', 'node_modules'}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _obsidian_vault():
    """Return the configured vault path, or None if unset/missing."""
    path = (get_app_setting(OBSIDIAN_SETTING_KEY) or '').strip()
    if not path or not os.path.isdir(path):
        return None
    return path


def _obsidian_allowed_folders():
    """Comma-separated top-level folder tokens to include. Empty list => all."""
    raw = (get_app_setting(OBSIDIAN_FOLDERS_KEY) or '').strip()
    return [t.strip() for t in raw.split(',') if t.strip()]


def _obsidian_top_allowed(top, allowed):
    """True if a top-level folder name matches one of the allowed tokens.
    Token '10' matches '10', '10_Library', '10 Library', '10-Library'."""
    if not allowed:
        return True
    if not top:
        return False  # root-level note -- excluded once a filter is active
    for tok in allowed:
        if top == tok or top.startswith(tok + '_') \
                or top.startswith(tok + ' ') or top.startswith(tok + '-'):
            return True
    return False


def _obsidian_safe_path(vault, rel):
    """Resolve a vault-relative path safely (defends against path traversal).
    Returns an absolute path only if it stays inside the vault AND is a .md file."""
    if not vault or not rel:
        return None
    rel = str(rel).replace('\\', '/').lstrip('/')
    candidate = os.path.realpath(os.path.join(vault, rel))
    vault_real = os.path.realpath(vault)
    inside = candidate == vault_real or candidate.startswith(vault_real + os.sep)
    if not inside or not candidate.lower().endswith('.md'):
        return None
    return candidate


def _obsidian_walk(vault):
    """Walk the vault, yielding (relpath, abspath, mtime, size) for every .md
    file, skipping Obsidian/system folders and honouring the top-level folder
    filter (Ion only cares about folders 10/30/99)."""
    vault_real = os.path.realpath(vault)
    allowed = _obsidian_allowed_folders()
    out = []
    for root, dirs, files in os.walk(vault_real):
        dirs[:] = [d for d in dirs if d not in _OBSIDIAN_SKIP_DIRS and not d.startswith('.')]
        # At the vault root, prune to allowed top-level folders so we don't even
        # descend into the excluded ones.
        if allowed and os.path.realpath(root) == vault_real:
            dirs[:] = [d for d in dirs if _obsidian_top_allowed(d, allowed)]
        for fname in files:
            if not fname.lower().endswith('.md'):
                continue
            abspath = os.path.join(root, fname)
            try:
                st = os.stat(abspath)
            except OSError:
                continue
            rel = os.path.relpath(abspath, vault_real).replace('\\', '/')
            top = rel.split('/', 1)[0] if '/' in rel else ''
            if not _obsidian_top_allowed(top, allowed):
                continue
            out.append((rel, abspath, st.st_mtime, st.st_size))
    return out


def _obsidian_index(vault):
    """Return a cached list of note dicts {path, title, folder, content, mtime,
    size}. Rebuilds only when the set of files or their mtimes changed."""
    files = _obsidian_walk(vault)
    sig = tuple(sorted((rel, mtime) for rel, _a, mtime, _s in files))
    if (_obsidian_cache['path'] == vault and _obsidian_cache['sig'] == sig
            and _obsidian_cache['notes'] is not None):
        return _obsidian_cache['notes']

    notes = []
    for rel, abspath, mtime, size in files:
        try:
            with open(abspath, 'r', encoding='utf-8', errors='ignore') as fh:
                content = fh.read()
        except OSError:
            content = ''
        folder = os.path.dirname(rel)
        title = os.path.basename(rel)[:-3]  # strip .md
        notes.append({
            'path': rel, 'title': title, 'folder': folder,
            'content': content, 'mtime': mtime, 'size': size,
        })
    notes.sort(key=lambda n: n['path'].lower())
    _obsidian_cache.update({'path': vault, 'sig': sig, 'notes': notes})
    return notes


def _obsidian_config_dict():
    """Current Obsidian config as a JSON-serialisable dict."""
    raw = (get_app_setting(OBSIDIAN_SETTING_KEY) or '').strip()
    folders = (get_app_setting(OBSIDIAN_FOLDERS_KEY) or '').strip()
    vault = _obsidian_vault()
    note_count = len(_obsidian_index(vault)) if vault else 0
    return {
        'configured': bool(raw),
        'vault_path': raw,
        'folders': folders,
        'valid': vault is not None,
        'note_count': note_count,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@obsidian_bp.route('/api/obsidian/config', methods=['GET'])
@login_required
def obsidian_config_get():
    return jsonify(_obsidian_config_dict())


@obsidian_bp.route('/api/obsidian/config', methods=['PUT'])
@login_required
def obsidian_config_set():
    data = request.get_json(silent=True) or {}
    if 'vault_path' in data:
        path = (data.get('vault_path') or '').strip()
        if path and not os.path.isdir(path):
            return jsonify({'error': 'Calea nu există sau nu este un folder'}), 400
        set_app_setting(OBSIDIAN_SETTING_KEY, path)
    if 'folders' in data:
        set_app_setting(OBSIDIAN_FOLDERS_KEY, (data.get('folders') or '').strip())
    _obsidian_cache.update({'path': None, 'sig': None, 'notes': None})  # invalidate
    return jsonify(_obsidian_config_dict())


@obsidian_bp.route('/api/obsidian/notes', methods=['GET'])
@login_required
def obsidian_notes_list():
    vault = _obsidian_vault()
    if not vault:
        return jsonify({'error': 'Vault Obsidian neconfigurat', 'notes': []}), 200
    _maybe_refresh_vault(vault)
    notes = [
        {'path': n['path'], 'title': n['title'], 'folder': n['folder'],
         'mtime': n['mtime'], 'size': n['size']}
        for n in _obsidian_index(vault)
    ]
    return jsonify({'notes': notes})


@obsidian_bp.route('/api/obsidian/note', methods=['GET'])
@login_required
def obsidian_note_get():
    vault = _obsidian_vault()
    if not vault:
        return jsonify({'error': 'Vault Obsidian neconfigurat'}), 400
    rel = request.args.get('path', '')
    abspath = _obsidian_safe_path(vault, rel)
    if not abspath or not os.path.isfile(abspath):
        return jsonify({'error': 'Nota nu a fost găsită'}), 404
    try:
        with open(abspath, 'r', encoding='utf-8', errors='ignore') as fh:
            content = fh.read()
    except OSError as e:
        return jsonify({'error': f'Eroare la citire: {e}'}), 500
    rel_norm = str(rel).replace('\\', '/').lstrip('/')
    return jsonify({
        'path': rel_norm,
        'title': os.path.basename(rel_norm)[:-3],
        'content': content,
    })


# ---------------------------------------------------------------------------
# Vault repo sync (clone/pull the Knowledge git repo on this server)
# ---------------------------------------------------------------------------

DEFAULT_VAULT_REPO_HTTPS = 'https://github.com/Urs1470/Knowledge.git'
DEFAULT_VAULT_REPO_SSH = 'git@github.com:Urs1470/Knowledge.git'
DEFAULT_VAULT_DEST = os.path.expanduser('~/Projects/Knowledge')
DEFAULT_VAULT_BRANCH = 'main'
VAULT_DEPLOY_KEY = os.path.expanduser('~/.ssh/vault_deploy_key')
VAULT_REFRESH_SECONDS = 600  # mirror-ul se împrospătează la accesare, max o dată la 10 min
_vault_refresh_lock = threading.Lock()
_vault_refreshing = False


def _scrub_secrets(text):
    """Strip embedded https credentials (user:token@) from git output."""
    return re.sub(r'https://[^@/\s]+@', 'https://', text or '')


def _git_env():
    """Use the vault deploy key for ssh remotes, if it exists."""
    env = dict(os.environ)
    if os.path.isfile(VAULT_DEPLOY_KEY):
        env['GIT_SSH_COMMAND'] = (
            f'ssh -i {VAULT_DEPLOY_KEY} -o IdentitiesOnly=yes '
            f'-o StrictHostKeyChecking=accept-new'
        )
    return env


def _git(args, cwd=None, timeout=90):
    r = subprocess.run(['git'] + args, cwd=cwd, capture_output=True, text=True,
                       timeout=timeout, env=_git_env())
    return r.returncode, _scrub_secrets(r.stdout.strip()), _scrub_secrets(r.stderr.strip())


def _default_vault_repo():
    """SSH cu deploy key dacă există, altfel https (merge doar pe repo public)."""
    return DEFAULT_VAULT_REPO_SSH if os.path.isfile(VAULT_DEPLOY_KEY) else DEFAULT_VAULT_REPO_HTTPS


def _maybe_refresh_vault(vault):
    """Fire-and-forget: if the vault is a git clone and its last fetch is older
    than VAULT_REFRESH_SECONDS, refresh it in a background thread (fetch +
    reset --hard). Callers keep serving the current copy — the next request
    sees the fresh one. No cron needed."""
    global _vault_refreshing
    if not vault:
        return
    git_dir = os.path.join(vault, '.git')
    if not os.path.isdir(git_dir):
        return
    marker = os.path.join(git_dir, 'FETCH_HEAD')
    try:
        last = os.path.getmtime(marker) if os.path.isfile(marker) else 0
    except OSError:
        last = 0
    if time.time() - last < VAULT_REFRESH_SECONDS:
        return
    with _vault_refresh_lock:
        if _vault_refreshing:
            return
        _vault_refreshing = True

    def _refresh():
        global _vault_refreshing
        try:
            rc, _o, _e = _git(['fetch', '--depth', '1', 'origin', DEFAULT_VAULT_BRANCH], cwd=vault)
            if rc == 0:
                _git(['reset', '--hard', f'origin/{DEFAULT_VAULT_BRANCH}'], cwd=vault)
                _obsidian_cache.update({'path': None, 'sig': None, 'notes': None})
        except Exception:
            pass
        finally:
            _vault_refreshing = False

    threading.Thread(target=_refresh, daemon=True).start()


def _dashboard_git_credentials():
    """If this repo's own origin URL embeds https credentials (how the deploy
    webhook authenticates), reuse them for the vault repo. Returns 'user:token'
    or None. The value never leaves the server (_scrub_secrets on all output)."""
    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        r = subprocess.run(['git', 'config', 'remote.origin.url'], cwd=repo_dir,
                           capture_output=True, text=True, timeout=10)
        m = re.match(r'https://([^@/]+)@', r.stdout.strip())
        return m.group(1) if m else None
    except Exception:
        return None


@obsidian_bp.route('/api/obsidian/vault-key', methods=['POST'])
@login_required
def obsidian_vault_key():
    """Generate (once) an ed25519 deploy key for the vault repo and return the
    PUBLIC half. Register it on GitHub: repo Knowledge -> Settings -> Deploy
    keys -> Add (read-only). The private key never leaves the server."""
    pub_path = VAULT_DEPLOY_KEY + '.pub'
    if not os.path.isfile(VAULT_DEPLOY_KEY):
        os.makedirs(os.path.dirname(VAULT_DEPLOY_KEY), exist_ok=True)
        r = subprocess.run(
            ['ssh-keygen', '-t', 'ed25519', '-N', '', '-C', 'pif-dashboard-vault',
             '-f', VAULT_DEPLOY_KEY],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return jsonify({'ok': False, 'error': r.stderr.strip()}), 500
    try:
        with open(pub_path, 'r', encoding='utf-8') as f:
            pubkey = f.read().strip()
    except OSError as e:
        return jsonify({'ok': False, 'error': str(e)}), 500
    return jsonify({'ok': True, 'public_key': pubkey,
                    'hint': 'GitHub -> Urs1470/Knowledge -> Settings -> Deploy keys -> Add deploy key (read-only)'})


@obsidian_bp.route('/api/obsidian/vault-sync', methods=['POST'])
@login_required
def obsidian_vault_sync():
    """Clone (first run) or update (fetch + reset --hard) the vault git repo on
    this server, then point obsidian_vault_path at it if unset/invalid. The
    server copy is a read-only mirror — reset --hard is always safe here.
    Body (all optional): {repo_url, dest, branch}."""
    data = request.get_json(silent=True) or {}
    repo = (data.get('repo_url') or _default_vault_repo()).strip()
    dest = os.path.expanduser((data.get('dest') or DEFAULT_VAULT_DEST).strip())
    branch = (data.get('branch') or DEFAULT_VAULT_BRANCH).strip()
    steps = []

    try:
        if os.path.isdir(os.path.join(dest, '.git')):
            action = 'pull'
            rc, out, err = _git(['fetch', '--depth', '1', 'origin', branch], cwd=dest)
            steps.append(f'fetch: rc={rc} {err or out}')
            if rc == 0:
                rc, out, err = _git(['reset', '--hard', f'origin/{branch}'], cwd=dest)
                steps.append(f'reset: rc={rc} {err or out}')
        else:
            action = 'clone'
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            rc, out, err = _git(['clone', '--depth', '1', '--branch', branch, repo, dest])
            steps.append(f'clone: rc={rc} {err or out}')
            if rc != 0:  # probabil auth pe repo privat — reîncearcă cu credențialele repo-ului dashboard
                creds = _dashboard_git_credentials()
                if creds:
                    auth_repo = repo.replace('https://', f'https://{creds}@', 1)
                    rc, out, err = _git(['clone', '--depth', '1', '--branch', branch, auth_repo, dest])
                    steps.append(f'clone(cu credentialele repo-ului dashboard): rc={rc} {err or out}')
    except subprocess.TimeoutExpired:
        return jsonify({'ok': False, 'error': 'git a depășit timeout-ul', 'steps': steps}), 500
    except Exception as e:
        return jsonify({'ok': False, 'error': _scrub_secrets(str(e)), 'steps': steps}), 500

    if rc != 0:
        return jsonify({'ok': False, 'action': action, 'steps': steps}), 500

    # Point the vault at the fresh clone if the current setting is unset/broken.
    current = (get_app_setting(OBSIDIAN_SETTING_KEY) or '').strip()
    if not current or not os.path.isdir(current):
        set_app_setting(OBSIDIAN_SETTING_KEY, dest)
        steps.append(f'obsidian_vault_path -> {dest}')
    _obsidian_cache.update({'path': None, 'sig': None, 'notes': None})

    return jsonify({'ok': True, 'action': action, 'dest': dest, 'steps': steps,
                    'vault': _obsidian_config_dict()})


def _obsidian_safe_dir(vault, rel):
    """Resolve a vault-relative FOLDER path safely (path-traversal safe).
    Returns an absolute dir path only if it stays inside the vault."""
    if not vault or not rel:
        return None
    rel = str(rel).replace('\\', '/').strip('/')
    candidate = os.path.realpath(os.path.join(vault, rel))
    vault_real = os.path.realpath(vault)
    inside = candidate == vault_real or candidate.startswith(vault_real + os.sep)
    if not inside or not os.path.isdir(candidate):
        return None
    return candidate


@obsidian_bp.route('/api/proiecte/<project_id>/wiki', methods=['GET'])
@login_required
def project_wiki_notes(project_id):
    """List the .md notes in the project's linked vault folder (proiecte.vault_folder,
    e.g. 'wiki/job/projects/imsat-biochem-podari'). Content is fetched per-note via
    the existing GET /api/obsidian/note?path=<rel>. Bypasses the top-level folder
    filter (that filter is for the study-notes browser, not for project wikis)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT vault_folder FROM proiecte WHERE id = ?', (project_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return jsonify({'error': 'Project not found'}), 404

    folder = (row['vault_folder'] or '').strip().replace('\\', '/').strip('/')
    vault = _obsidian_vault()
    result = {
        'configured': vault is not None,
        'folder': folder or None,
        'valid': False,
        'notes': [],
    }
    if not folder or not vault:
        return jsonify(result)

    _maybe_refresh_vault(vault)
    absdir = _obsidian_safe_dir(vault, folder)
    if not absdir:
        return jsonify(result)  # folder set but missing on this vault copy

    vault_real = os.path.realpath(vault)
    notes = []
    for root, dirs, files in os.walk(absdir):
        dirs[:] = [d for d in dirs if d not in _OBSIDIAN_SKIP_DIRS and not d.startswith('.')]
        for fname in files:
            if not fname.lower().endswith('.md'):
                continue
            abspath = os.path.join(root, fname)
            try:
                st = os.stat(abspath)
            except OSError:
                continue
            rel = os.path.relpath(abspath, vault_real).replace('\\', '/')
            notes.append({
                'path': rel,
                'title': fname[:-3],
                'folder': os.path.dirname(rel),
                'mtime': st.st_mtime,
                'size': st.st_size,
            })
    # README first, then shallow-before-deep, then alphabetical.
    notes.sort(key=lambda n: (n['title'].lower() != 'readme',
                              n['path'].count('/'), n['path'].lower()))
    result.update({'valid': True, 'notes': notes})
    return jsonify(result)


@obsidian_bp.route('/api/obsidian/search', methods=['GET'])
@login_required
def obsidian_search():
    vault = _obsidian_vault()
    if not vault:
        return jsonify({'error': 'Vault Obsidian neconfigurat', 'results': []}), 200
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify({'results': []})
    q_low = query.lower()
    results = []
    for n in _obsidian_index(vault):
        content_low = n['content'].lower()
        title_low = n['title'].lower()
        in_title = q_low in title_low
        hits = content_low.count(q_low)
        if not in_title and hits == 0:
            continue
        # Snippet: context window around the first content match.
        snippet = ''
        idx = content_low.find(q_low)
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(n['content']), idx + len(query) + 90)
            snippet = ('…' if start > 0 else '') + n['content'][start:end].strip() \
                      + ('…' if end < len(n['content']) else '')
        score = hits + (50 if in_title else 0)
        results.append({
            'path': n['path'], 'title': n['title'], 'folder': n['folder'],
            'snippet': snippet, 'hits': hits, 'score': score,
        })
    results.sort(key=lambda r: r['score'], reverse=True)
    return jsonify({'results': results[:50], 'query': query})



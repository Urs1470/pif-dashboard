# Obsidian Vault Integration Blueprint (read-only)
# Ion keeps study notes in an Obsidian vault synced to the laptop-server via
# InSync (Google Drive). The app reads .md files directly -- never writes -- so
# there is no risk of sync conflicts. The vault path is configured at runtime
# from the Administrativ tab and stored in app_settings.

import os
import re

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

@obsidian_bp.route('/api/obsidian', methods=['GET'])
@login_required
def obsidian_index():
    """Base Obsidian API endpoint - returns available sub-endpoints."""
    return jsonify({
        'endpoints': ['/config', '/notes', '/note', '/search', '/mentions'],
        'vault_configured': bool(_obsidian_vault()),
    })


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
            return jsonify({'error': 'Calea nu există sau nu este un folder', 'valid': False}), 400
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


@obsidian_bp.route('/api/obsidian/mentions', methods=['GET'])
@login_required
def obsidian_mentions():
    """Notes that mention a given term -- used to auto-link notes to a parameter
    or project from their detail view. Token-boundary match to avoid noise."""
    vault = _obsidian_vault()
    if not vault:
        return jsonify({'mentions': []}), 200
    term = (request.args.get('term') or '').strip()
    if not term or len(term) < 2:
        return jsonify({'mentions': []})
    pat = re.compile(r'(?<![\w.])' + re.escape(term) + r'(?![\w.])', re.IGNORECASE)
    mentions = []
    for n in _obsidian_index(vault):
        if pat.search(n['content']) or pat.search(n['title']):
            mentions.append({'path': n['path'], 'title': n['title'], 'folder': n['folder']})
    return jsonify({'mentions': mentions[:25], 'term': term})

import os
import json
import math
import re

from flask import Blueprint, request, jsonify, send_file

from database import get_db, row_to_dict
from utils import safe_table, login_required

parametri_bp = Blueprint('parametri', __name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRODUCATOR_FAMILII = {
    'ABB': ['ACS580', 'ACS880'],
    'Danfoss': ['Danfoss_VLT_FC302'],
    'Lenze': ['Lenze_i550', 'Lenze_i950'],
    'Siemens': ['SINAMICS_G120', 'SINAMICS_G130_G150', 'SINAMICS_S120_S150'],
}

MANUALS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'manuals')

# ---------------------------------------------------------------------------
# Parametri API
# ---------------------------------------------------------------------------

@parametri_bp.route('/api/parametri/familii', methods=['GET'])
@login_required
def get_parametri_familii():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT familie, COUNT(*) as count FROM parametri_master GROUP BY familie ORDER BY familie")
    families = [{'familie': row['familie'], 'count': row['count']} for row in cursor.fetchall()]
    conn.close()
    return jsonify({'families': families})


@parametri_bp.route('/api/parametri', methods=['GET'])
@login_required
def get_parametri():
    conn = get_db()
    cursor = conn.cursor()

    search = request.args.get('search', '')
    familie = request.args.get('familie', '')
    page = request.args.get('page', 1, type=int)
    page = max(page, 1)
    limit = min(max(request.args.get('limit', 50, type=int), 1), 500)
    offset = (page - 1) * limit

    # Build count query first
    count_query = "SELECT COUNT(*) FROM parametri_master WHERE 1=1"
    query = "SELECT id, familie, parametru, descriere_scurta, descriere, acces, tip_date, valoare_default, valoare_default_str, min, max, unitate, pagina, creat_la, conditie_vizibilitate FROM parametri_master WHERE 1=1"
    params = []

    if search:
        clause = " AND (parametru LIKE ? OR descriere LIKE ?)"
        count_query += clause
        query += clause
        params.extend([f'%{search}%', f'%{search}%'])

    if familie:
        clause = " AND familie = ?"
        count_query += clause
        query += clause
        params.append(familie)

    # Get total count
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Get paginated results
    query += " ORDER BY familie, parametru LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify({
        'params': rows,
        'total': total,
        'page': page,
        'limit': limit,
        'totalPages': max(1, (total + limit - 1) // limit)
    })


@parametri_bp.route('/api/parametri/search', methods=['GET'])
@login_required
def search_parametri():
    """Search parametri by text query - used by mobile app.
    Mobile app calls /api/parametri/search?q=query"""
    conn = get_db()
    cursor = conn.cursor()

    q = request.args.get('q', '')
    familie = request.args.get('familie', '')
    limit = min(max(request.args.get('limit', 50, type=int), 1), 500)

    query = "SELECT id, familie, parametru, descriere_scurta, descriere, acces, tip_date, valoare_default, valoare_default_str, min, max, unitate, pagina, creat_la, conditie_vizibilitate FROM parametri_master WHERE 1=1"
    count_query = "SELECT COUNT(*) FROM parametri_master WHERE 1=1"
    params = []

    if q:
        clause = " AND (parametru LIKE ? OR descriere LIKE ?)"
        count_query += clause
        query += clause
        params.extend([f'%{q}%', f'%{q}%'])

    if familie:
        clause = " AND familie = ?"
        count_query += clause
        query += clause
        params.append(familie)

    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    query += " ORDER BY familie, parametru LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify({
        'params': rows,
        'total': total,
        'limit': limit
    })


# ============ BULK PARAMS (lightweight, for mobile cache) ============

@parametri_bp.route('/api/parametri/bulk', methods=['GET'])
@login_required
def get_parametri_bulk():
    """Returnează parametrii FĂRĂ explicatie/influenteaza (lightweight).

    Backward compatible: without `limit` query param returns the full list
    (legacy shape). With `limit` set, returns a paginated envelope.
    """
    has_limit = request.args.get('limit') is not None
    limit = min(int(request.args.get('limit', 1000)), 5000)
    offset = max(int(request.args.get('offset', 0)), 0)

    conn = get_db()
    cursor = conn.cursor()

    if has_limit:
        cursor.execute("SELECT COUNT(*) FROM parametri_master")
        total = cursor.fetchone()[0]
        cursor.execute('''
            SELECT id, familie, parametru, descriere_scurta, descriere, acces, tip_date,
                   valoare_default, valoare_default_str, min, max, unitate,
                   pagina, creat_la
            FROM parametri_master
            ORDER BY familie, parametru
            LIMIT ? OFFSET ?
        ''', (limit, offset))
    else:
        cursor.execute('''
            SELECT id, familie, parametru, descriere_scurta, descriere, acces, tip_date,
                   valoare_default, valoare_default_str, min, max, unitate,
                   pagina, creat_la
            FROM parametri_master
            ORDER BY familie, parametru
        ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    # Sanitize: JSON nu suportă Infinity/NaN — înlocuiește cu null
    for row in rows:
        for key in ('min', 'max'):
            if row.get(key) is not None:
                try:
                    v = float(row[key])
                    if math.isinf(v) or math.isnan(v):
                        row[key] = None
                except (ValueError, TypeError):
                    pass

    if has_limit:
        return jsonify({
            'data': rows,
            'total': total,
            'limit': limit,
            'offset': offset,
        })
    return jsonify(rows)


# ---------------------------------------------------------------------------
# Parametri by producator
# ---------------------------------------------------------------------------

@parametri_bp.route('/api/parametri/by-producator/<producator>', methods=['GET'])
@login_required
def get_parametri_by_producator(producator):
    """Returnează parametrii pentru toate familiile unui producător.

    Cu `?q=` activeaza modul typeahead (LIMIT 50, filtrare LIKE pe
    parametru + descriere_scurta). Fara `q` returneaza pana la 1000
    randuri (safety cap — Siemens are 7000+ in DB).
    """
    familii = PRODUCATOR_FAMILII.get(producator, [])
    if not familii:
        return jsonify([])
    q = (request.args.get('q') or '').strip()
    conn = get_db()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(familii))
    if q:
        like = f'%{q}%'
        cursor.execute(
            f'SELECT id, parametru, descriere_scurta, familie FROM parametri_master '
            f'WHERE familie IN ({placeholders}) AND (parametru LIKE ? OR descriere_scurta LIKE ?) '
            f'LIMIT 50',
            list(familii) + [like, like]
        )
    else:
        cursor.execute(
            f'SELECT id, parametru, descriere_scurta, familie FROM parametri_master '
            f'WHERE familie IN ({placeholders})',
            familii
        )
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ============ FAULT CODES API ============
# Drive fault / alarm / warning codes extracted from the manufacturer manuals.
# Sibling dataset to parametri_master; same producator -> familie -> list shape.

def _fault_row(row):
    """Row -> dict, decoding extra_json into an `extra` object."""
    d = dict(row)
    raw = d.pop('extra_json', None)
    if raw:
        try:
            d['extra'] = json.loads(raw)
        except (ValueError, TypeError):
            d['extra'] = None
    else:
        d['extra'] = None
    return d


@parametri_bp.route('/api/fault-codes/familii', methods=['GET'])
@login_required
def get_fault_familii():
    """Producator + familie + count, for the fault-code navigation picker."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''SELECT producator, familie, COUNT(*) AS count
                      FROM fault_codes
                      GROUP BY producator, familie
                      ORDER BY producator, familie''')
    families = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'families': families})


@parametri_bp.route('/api/fault-codes', methods=['GET'])
@login_required
def get_fault_codes():
    """List/filter fault codes. Query: familie, producator, search, tip, page, limit."""
    conn = get_db()
    cursor = conn.cursor()

    search = request.args.get('search', '').strip()
    familie = request.args.get('familie', '').strip()
    producator = request.args.get('producator', '').strip()
    tip = request.args.get('tip', '').strip()
    page = request.args.get('page', 1, type=int)
    page = max(page, 1)
    limit = min(max(request.args.get('limit', 50, type=int), 1), 500)
    offset = (page - 1) * limit

    where = ' WHERE 1=1'
    params = []
    if familie:
        where += ' AND familie = ?'
        params.append(familie)
    if producator:
        where += ' AND producator = ?'
        params.append(producator)
    if tip:
        where += ' AND tip = ?'
        params.append(tip)
    if search:
        where += ' AND (cod LIKE ? OR cod_secundar LIKE ? OR nume LIKE ? OR cauza LIKE ?)'
        s = f'%{search}%'
        params.extend([s, s, s, s])

    cursor.execute(f'SELECT COUNT(*) FROM {safe_table("fault_codes")}{where}', params)
    total = cursor.fetchone()[0]

    cursor.execute(
        f'''SELECT id, producator, familie, cod, cod_secundar, tip, nume, pagina
            FROM {safe_table("fault_codes")}{where} ORDER BY cod LIMIT ? OFFSET ?''',
        params + [limit, offset])
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()

    return jsonify({
        'codes': rows,
        'total': total,
        'page': page,
        'limit': limit,
        'totalPages': max(1, (total + limit - 1) // limit),
    })


@parametri_bp.route('/api/fault-codes/lookup', methods=['GET'])
@login_required
def lookup_fault_code():
    """Quick lookup by code. Query: cod (required), producator/familie (optional).
    Matches cod or cod_secundar, case-insensitive."""
    cod = request.args.get('cod', '').strip()
    if not cod:
        return jsonify({'error': 'cod lipsa'}), 400
    producator = request.args.get('producator', '').strip()
    familie = request.args.get('familie', '').strip()

    conn = get_db()
    cursor = conn.cursor()
    where = ' WHERE (cod = ? COLLATE NOCASE OR cod_secundar = ? COLLATE NOCASE)'
    params = [cod, cod]
    if producator:
        where += ' AND producator = ?'
        params.append(producator)
    if familie:
        where += ' AND familie = ?'
        params.append(familie)
    cursor.execute(f'SELECT * FROM {safe_table("fault_codes")}{where} ORDER BY producator, familie', params)
    matches = [_fault_row(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify({'matches': matches, 'count': len(matches)})


@parametri_bp.route('/api/fault-codes/<int:code_id>', methods=['GET'])
@login_required
def get_fault_code(code_id):
    """Full detail for one fault code."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM fault_codes WHERE id = ?', (code_id,))
    row = cursor.fetchone()
    conn.close()
    if row is None:
        return jsonify({'error': 'Codul nu a fost găsit'}), 404
    return jsonify(_fault_row(row))


# ---------------------------------------------------------------------------
# Parametri audit
# ---------------------------------------------------------------------------

@parametri_bp.route('/api/parametri/audit', methods=['GET'])
@login_required
def parametri_audit():
    """Audit raport calitate DB parametri_master.
    Detectează anomalii grupate pe categorii, cu sample-uri.
    Optional: ?familie=ACS580 restricționează la o familie.
    """
    familie_filter = request.args.get('familie', '').strip()
    conn = get_db()
    cursor = conn.cursor()

    # Build WHERE for optional familie scope
    where = ''
    params = []
    if familie_filter:
        where = ' WHERE familie = ?'
        params = [familie_filter]

    # Total count
    cursor.execute(f'SELECT COUNT(*) FROM {safe_table("parametri_master")}{where}', params)
    total = cursor.fetchone()[0]

    # Per-familie breakdown
    cursor.execute(f'''
        SELECT familie, COUNT(*) as total,
            SUM(CASE WHEN descriere_scurta IS NULL OR TRIM(descriere_scurta)='' THEN 1 ELSE 0 END) as missing_desc,
            SUM(CASE WHEN explicatie IS NULL OR TRIM(explicatie)='' THEN 1 ELSE 0 END) as missing_explicatie,
            SUM(CASE WHEN pagina IS NULL THEN 1 ELSE 0 END) as missing_pagina,
            SUM(CASE WHEN unitate IS NULL OR TRIM(unitate)='' THEN 1 ELSE 0 END) as missing_unitate,
            SUM(CASE WHEN acces IS NULL OR TRIM(acces)='' THEN 1 ELSE 0 END) as missing_acces
        FROM {safe_table("parametri_master")}{where}
        GROUP BY familie ORDER BY familie
    ''', params)
    per_familie = [dict(r) for r in cursor.fetchall()]

    issues = {}

    # Single-pass count: 7 categories in one table scan (HIGH-P4).
    # Avoids 7 separate COUNT queries against parametri_master.
    cursor.execute(f'''
        SELECT
            SUM(CASE WHEN (descriere_scurta IS NULL OR TRIM(descriere_scurta)='') THEN 1 ELSE 0 END) AS c_missing_desc,
            SUM(CASE WHEN LENGTH(TRIM(descriere_scurta)) BETWEEN 1 AND 10 THEN 1 ELSE 0 END) AS c_short_desc,
            SUM(CASE WHEN TRIM(descriere_scurta) = TRIM(parametru) THEN 1 ELSE 0 END) AS c_desc_eq_code,
            SUM(CASE WHEN (explicatie IS NULL OR TRIM(explicatie)='') THEN 1 ELSE 0 END) AS c_missing_explicatie,
            SUM(CASE WHEN pagina IS NULL THEN 1 ELSE 0 END) AS c_missing_pagina,
            SUM(CASE WHEN (LENGTH(TRIM(parametru)) < 2
                OR (familie LIKE 'ACS%' AND parametru NOT LIKE '%.%')
                OR (familie LIKE 'Danfoss%' AND parametru NOT LIKE '%-%')
                OR (familie LIKE 'Lenze%' AND parametru NOT LIKE '0x%')
                OR (familie LIKE 'SINAMICS%' AND NOT (parametru GLOB 'p[0-9]*' OR parametru GLOB 'r[0-9]*'))
                ) THEN 1 ELSE 0 END) AS c_suspect_code,
            SUM(CASE WHEN (unitate IS NULL OR TRIM(unitate)='')
                AND (descriere_scurta LIKE '%Hz%' OR descriere_scurta LIKE '%kW%' OR descriere_scurta LIKE '%rpm%' OR descriere_scurta LIKE '%°C%' OR descriere_scurta LIKE '%percent%')
                THEN 1 ELSE 0 END) AS c_missing_unitate
        FROM {safe_table("parametri_master")}{where}
    ''', params)
    counts_row = cursor.fetchone()
    counts = {
        'missing_desc': counts_row[0] or 0,
        'short_desc': counts_row[1] or 0,
        'desc_eq_code': counts_row[2] or 0,
        'missing_explicatie': counts_row[3] or 0,
        'missing_pagina': counts_row[4] or 0,
        'suspect_code': counts_row[5] or 0,
        'missing_unitate': counts_row[6] or 0,
    }

    # 1. Missing descriere_scurta
    cursor.execute(f'''
        SELECT id, parametru, familie FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')} (descriere_scurta IS NULL OR TRIM(descriere_scurta)='')
        LIMIT 30
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    issues['missing_descriere_scurta'] = {
        'count': counts['missing_desc'],
        'label': 'Parametri fără descriere scurtă',
        'severity': 'high',
        'samples': rows,
    }

    # 2. Descriere_scurta foarte scurtă (probabil placeholder)
    cursor.execute(f'''
        SELECT id, parametru, descriere_scurta, familie FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')} LENGTH(TRIM(descriere_scurta)) BETWEEN 1 AND 10
        LIMIT 30
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    issues['short_descriere'] = {
        'count': counts['short_desc'],
        'label': 'Descriere foarte scurtă (≤10 caractere)',
        'severity': 'medium',
        'samples': rows,
    }

    # 3. Descriere = parametru (placeholder evident)
    cursor.execute(f'''
        SELECT id, parametru, descriere_scurta, familie FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')} TRIM(descriere_scurta) = TRIM(parametru)
        LIMIT 30
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    issues['descriere_equals_code'] = {
        'count': counts['desc_eq_code'],
        'label': 'Descriere = codul parametrului (placeholder)',
        'severity': 'high',
        'samples': rows,
    }

    # 4. Lipsă explicație tehnică
    cursor.execute(f'''
        SELECT id, parametru, descriere_scurta, familie FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')} (explicatie IS NULL OR TRIM(explicatie)='')
        LIMIT 30
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    issues['missing_explicatie'] = {
        'count': counts['missing_explicatie'],
        'label': 'Fără explicație tehnică detaliată',
        'severity': 'medium',
        'samples': rows,
    }

    # 5. Lipsă pagină manual
    cursor.execute(f'''
        SELECT id, parametru, descriere_scurta, familie FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')} pagina IS NULL
        LIMIT 30
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    issues['missing_pagina'] = {
        'count': counts['missing_pagina'],
        'label': 'Fără referință la pagina manualului',
        'severity': 'medium',
        'samples': rows,
    }

    # 6. Cod parametru suspect — formatul valid diferă per producător:
    #    ABB 'Group.Index' (30.11), Danfoss 'G-P' (5-40), Lenze hex (0x2540:001),
    #    Siemens p/r+cifre (p0304). Familii necunoscute nu sunt flagate.
    cursor.execute(f'''
        SELECT id, parametru, descriere_scurta, familie FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')} (LENGTH(TRIM(parametru)) < 2
            OR (familie LIKE 'ACS%' AND parametru NOT LIKE '%.%')
            OR (familie LIKE 'Danfoss%' AND parametru NOT LIKE '%-%')
            OR (familie LIKE 'Lenze%' AND parametru NOT LIKE '0x%')
            OR (familie LIKE 'SINAMICS%' AND NOT (parametru GLOB 'p[0-9]*' OR parametru GLOB 'r[0-9]*'))
        )
        LIMIT 30
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    issues['suspect_code'] = {
        'count': counts['suspect_code'],
        'label': 'Cod parametru suspect (prea scurt sau format neașteptat)',
        'severity': 'low',
        'samples': rows,
    }

    # 7. Descrieri identice la 5+ parametri (probabil placeholder)
    cursor.execute(f'''
        SELECT descriere_scurta, COUNT(*) as cnt
        FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')} TRIM(descriere_scurta) != ''
        GROUP BY descriere_scurta HAVING cnt >= 5
        ORDER BY cnt DESC LIMIT 20
    ''', params)
    dupes = [dict(r) for r in cursor.fetchall()]
    issues['duplicate_descrieri'] = {
        'count': sum(d['cnt'] for d in dupes),
        'label': 'Descrieri duplicate (5+ parametri cu același text)',
        'severity': 'medium',
        'samples': dupes,
    }

    # 8. Lipsă unitate când titlul sugerează una (SQLite n-are REGEXP, folosim LIKE)
    cursor.execute(f'''
        SELECT id, parametru, descriere_scurta, familie FROM {safe_table("parametri_master")}
        {where + (' AND ' if where else ' WHERE ')}
        (unitate IS NULL OR TRIM(unitate)='')
        AND (descriere_scurta LIKE '%Hz%' OR descriere_scurta LIKE '%kW%' OR descriere_scurta LIKE '%rpm%' OR descriere_scurta LIKE '%°C%' OR descriere_scurta LIKE '%percent%')
        LIMIT 30
    ''', params)
    rows = [dict(r) for r in cursor.fetchall()]
    issues['missing_unitate_suggested'] = {
        'count': counts['missing_unitate'],
        'label': 'Lipsă unitate când descrierea sugerează una',
        'severity': 'low',
        'samples': rows,
    }

    conn.close()

    # Health score: cât din total NU are probleme grave (missing desc + descriere=code + missing explicatie)
    severe_count = (
        issues['missing_descriere_scurta']['count'] +
        issues['descriere_equals_code']['count']
    )
    health_pct = round(100 * (total - severe_count) / total, 1) if total else 0

    return jsonify({
        'total': total,
        'familie_filter': familie_filter or None,
        'health_pct': health_pct,
        'per_familie': per_familie,
        'issues': issues,
    })


# ---------------------------------------------------------------------------
# Parametri detail
# ---------------------------------------------------------------------------

@parametri_bp.route('/api/parametri/<int:param_id>', methods=['GET'])
@login_required
def get_parametru_detail(param_id):
    """Returnează detaliul complet al unui parametru.

    Include:
      - toate coloanele din parametri_master
      - `influentat_de`: lista params din aceeași familie care îl referențiază
        în câmpul lor `influenteaza` (computed reverse, nu coloană separată).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM parametri_master WHERE id = ?', (param_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Not found'}), 404
    result = dict(row)

    # Reverse lookup: who references this parameter's code?
    code = result.get('parametru')
    familie = result.get('familie')
    if code and familie:
        # influenteaza is stored as comma-separated codes (e.g. "30.12, 21.13").
        # Match the code as a standalone token to avoid p100 catching p1000.
        # SQLite REGEXP isn't built-in by default, so use LIKE with delimiters.
        like1 = f'%{code}%'
        cursor.execute(
            'SELECT id, parametru, descriere_scurta, influenteaza FROM parametri_master '
            'WHERE familie = ? AND id != ? AND influenteaza IS NOT NULL AND influenteaza LIKE ?',
            (familie, param_id, like1)
        )
        candidates = cursor.fetchall()
        # Refine: code appears as a comma/space-delimited token (avoid p100 catching p1000)
        token_pat = re.compile(r'(?:^|[,\s])' + re.escape(code) + r'(?:$|[,\s])')
        influentat_de = [
            {'id': c['id'], 'parametru': c['parametru'], 'descriere_scurta': c['descriere_scurta']}
            for c in candidates
            if c['influenteaza'] and token_pat.search(c['influenteaza'])
        ]
        result['influentat_de'] = influentat_de
    else:
        result['influentat_de'] = []

    conn.close()
    return jsonify(result)


# ============ MANUALS API ============

@parametri_bp.route('/api/manuals', methods=['GET'])
@login_required
def get_manuals():
    """List available PDF manuals with metadata"""
    manuals = []
    if os.path.isdir(MANUALS_DIR):
        for fname in sorted(os.listdir(MANUALS_DIR)):
            if fname.endswith('.pdf'):
                fpath = os.path.join(MANUALS_DIR, fname)
                size_kb = round(os.path.getsize(fpath) / 1024, 1)
                # Derive family from filename
                name_display = fname.replace('.pdf', '').replace('_', ' ')
                manuals.append({
                    'filename': fname,
                    'name': name_display,
                    'size_kb': size_kb,
                    'url': f'/manuals/{fname}'
                })
    return jsonify({'manuals': manuals})


@parametri_bp.route('/manuals/<path:filename>', methods=['GET'])
def serve_manual(filename):
    """Serve a PDF manual file (no auth — public technical docs)"""
    safe_name = os.path.basename(filename)
    fpath = os.path.join(MANUALS_DIR, safe_name)
    if not os.path.isfile(fpath):
        return 'Manual not found', 404
    return send_file(fpath)

# Projects Blueprint
# Provides all project-related CRUD routes extracted from app.py

import os
import shutil
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

from database import get_db, row_to_dict
from utils import (
    safe_table, generate_uuid, login_required, UPLOAD_FOLDER,
    get_app_setting, set_app_setting, get_json_or_400,
)

from scripts.parse_params.siemens_starter import parse_archive
from scripts.parse_params.abb import parse as parse_abb, read_drive_info as abb_drive_info

logger = logging.getLogger('pif_dashboard')

projects_bp = Blueprint('projects', __name__)


# ============ PROJECTS ============

@projects_bp.route('/api/proiecte', methods=['GET'])
@login_required
def get_proiecte():
    conn = get_db()
    cursor = conn.cursor()

    status = request.args.get('status')
    tip = request.args.get('tip')
    producator = request.args.get('producator')

    # Pagination parameters
    limit = min(max(request.args.get('limit', 100, type=int), 1), 500)
    offset = max(request.args.get('offset', 0, type=int), 0)

    # `urmatoarea` = prima perioada care nu s-a incheiat inca. A luat locul
    # deadline-ului (scos in v30): e data pe care chiar te bazezi, nu una impusa.
    query = '''SELECT p.*,
        (SELECT i.data_start FROM implementari i
          WHERE i.proiect_id = p.id
            AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date('now')
          ORDER BY i.data_start LIMIT 1) AS urmatoarea,
        (SELECT i.faza FROM implementari i
          WHERE i.proiect_id = p.id
            AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date('now')
          ORDER BY i.data_start LIMIT 1) AS urmatoarea_faza
        FROM proiecte p WHERE 1=1'''
    params = []

    if status:
        query += ' AND p.status = ?'
        params.append(status)
    if tip:
        query += ' AND p.tip = ?'
        params.append(tip)
    if producator:
        query += ' AND p.producator = ?'
        params.append(producator)

    query += ' ORDER BY p.created_at DESC'

    # Apply pagination
    query += ' LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return jsonify([row_to_dict(row) for row in rows])

@projects_bp.route('/api/proiecte', methods=['POST'])
@login_required
def create_proiect():
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    project_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO proiecte (
            id, tip, nume, client, locatie, echipament_principal, producator,
            cod_proiect, pm, folder_server, data_incepere, data_crearii,
            status, observatii, nr_comanda, nr_contract, service_before, service_after,
            confirmat_client, client_nume_confirmare, created_at, updated_at, vault_folder
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id,
        data.get('tip', 'PIF'),
        data.get('nume', ''),
        data.get('client', ''),
        data.get('locatie', ''),
        data.get('echipament_principal', ''),
        data.get('producator', 'Altul'),
        data.get('cod_proiect', ''),
        data.get('pm', ''),
        data.get('folder_server', ''),
        data.get('data_incepere', ''),
        data.get('data_crearii', now[:10]),
        data.get('status', 'in_lucru'),
        data.get('observatii', ''),
        data.get('nr_comanda', ''),
        data.get('nr_contract', ''),
        data.get('service_before', ''),
        data.get('service_after', ''),
        data.get('confirmat_client', 0),
        data.get('client_nume_confirmare', ''),
        now,
        now,
        data.get('vault_folder', '')
    ))

    conn.commit()
    conn.close()

    logger.info(f"Project created: {project_id} - {data.get('nume', '')}")
    return jsonify({'id': project_id, 'message': 'Project created'}), 201

@projects_bp.route('/api/proiecte/<project_id>', methods=['GET'])
@login_required
def get_proiect(project_id):
    conn = get_db()
    cursor = conn.cursor()
    # Ca in lista: `urmatoarea` a luat locul deadline-ului (scos in v30).
    cursor.execute('''SELECT p.*,
        (SELECT i.data_start FROM implementari i
          WHERE i.proiect_id = p.id
            AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date('now')
          ORDER BY i.data_start LIMIT 1) AS urmatoarea,
        (SELECT i.data_sfarsit FROM implementari i
          WHERE i.proiect_id = p.id
            AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date('now')
          ORDER BY i.data_start LIMIT 1) AS urmatoarea_sfarsit,
        (SELECT i.faza FROM implementari i
          WHERE i.proiect_id = p.id
            AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date('now')
          ORDER BY i.data_start LIMIT 1) AS urmatoarea_faza
        FROM proiecte p WHERE p.id = ?''', (project_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'error': 'Project not found'}), 404

    return jsonify(row_to_dict(row))

@projects_bp.route('/api/proiecte/<project_id>', methods=['PUT'])
@login_required
def update_proiect(project_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    # Get current project status
    cursor.execute('SELECT status, nume FROM proiecte WHERE id = ?', (project_id,))
    current = cursor.fetchone()
    old_status = current['status'] if current else None
    project_name = current['nume'] if current else ''

    cursor.execute('''
        UPDATE proiecte SET
            tip = COALESCE(?, tip),
            nume = COALESCE(?, nume),
            client = COALESCE(?, client),
            locatie = COALESCE(?, locatie),
            echipament_principal = COALESCE(?, echipament_principal),
            producator = COALESCE(?, producator),
            cod_proiect = COALESCE(?, cod_proiect),
            pm = COALESCE(?, pm),
            folder_server = COALESCE(?, folder_server),
            data_incepere = COALESCE(?, data_incepere),
            status = COALESCE(?, status),
            observatii = COALESCE(?, observatii),
            nr_comanda = COALESCE(?, nr_comanda),
            nr_contract = COALESCE(?, nr_contract),
            service_before = COALESCE(?, service_before),
            service_after = COALESCE(?, service_after),
            confirmat_client = COALESCE(?, confirmat_client),
            client_nume_confirmare = COALESCE(?, client_nume_confirmare),
            vault_folder = COALESCE(?, vault_folder),
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('tip'),
        data.get('nume'),
        data.get('client'),
        data.get('locatie'),
        data.get('echipament_principal'),
        data.get('producator'),
        data.get('cod_proiect'),
        data.get('pm'),
        data.get('folder_server'),
        data.get('data_incepere'),
        data.get('status'),
        data.get('observatii'),
        data.get('nr_comanda'),
        data.get('nr_contract'),
        data.get('service_before'),
        data.get('service_after'),
        data.get('confirmat_client'),
        data.get('client_nume_confirmare'),
        data.get('vault_folder'),
        now,
        project_id
    ))

    conn.commit()

    # Dashboard -> wiki: oglindește statusul în frontmatter-ul README-ului de
    # proiect din vault (commit + push, în fundal, best-effort). Deadline-ul a
    # plecat in v30 — nu se lua nimeni dupa el.
    if data.get('status'):
        cursor.execute('SELECT vault_folder, status FROM proiecte WHERE id = ?', (project_id,))
        fresh = cursor.fetchone()
        if fresh and fresh['vault_folder']:
            from blueprints.obsidian import sync_project_frontmatter
            sync_project_frontmatter(fresh['vault_folder'], {'status': fresh['status']})

    conn.close()

    logger.info(f"Project updated: {project_id}")
    return jsonify({'message': 'Project updated'})

@projects_bp.route('/api/proiecte/<project_id>', methods=['DELETE'])
@login_required
def delete_proiect(project_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Subtasks are keyed by task_id (not proiect_id) — remove them first.
        cursor.execute(
            'DELETE FROM task_subtasks WHERE task_id IN (SELECT id FROM tasks WHERE proiect_id = ?)',
            (project_id,)
        )
        tables = ['tasks']
        for table in tables:
            cursor.execute(f'DELETE FROM {safe_table(table)} WHERE proiect_id = ?', (project_id,))
        cursor.execute('DELETE FROM proiecte WHERE id = ?', (project_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({'error': 'Stergerea proiectului a esuat.'}), 500
    conn.close()
    # Remove the project's uploaded files from disk (orphans otherwise).
    try:
        shutil.rmtree(os.path.join(UPLOAD_FOLDER, project_id), ignore_errors=True)
    except Exception as e:
        logger.warning(f"Failed to remove uploads for {project_id}: {e}")
    logger.info(f"Project deleted: {project_id}")
    return jsonify({'message': 'Project deleted'})


# ============ BATCH OPERATIONS ============

@projects_bp.route('/api/proiecte/batch', methods=['POST'])
@login_required
def batch_proiecte():
    """Batch update or delete multiple projects"""
    data = get_json_or_400()
    action = data.get('action')  # 'update_status' or 'delete'
    if action not in ('update_status', 'delete'):
        return jsonify({'error': 'Invalid action'}), 400
    project_ids = data.get('project_ids', [])
    if not isinstance(project_ids, list) or len(project_ids) > 500:
        return jsonify({'error': 'Lista invalida (max 500)'}), 400

    if not project_ids:
        return jsonify({'error': 'No projects selected'}), 400

    conn = get_db()
    cursor = conn.cursor()

    try:
        if action == 'update_status':
            new_status = data.get('status')
            if not new_status:
                return jsonify({'error': 'Status required for update'}), 400

            now = datetime.now().isoformat()
            for pid in project_ids:
                cursor.execute('UPDATE proiecte SET status = ?, updated_at = ? WHERE id = ?', (new_status, now, pid))

            conn.commit()
            logger.info(f"Batch updated {len(project_ids)} projects to status: {new_status}")
            return jsonify({'message': f'{len(project_ids)} projects updated'})

        elif action == 'delete':
            for pid in project_ids:
                cursor.execute(
                    'DELETE FROM task_subtasks WHERE task_id IN (SELECT id FROM tasks WHERE proiect_id = ?)',
                    (pid,)
                )
                cursor.execute('DELETE FROM tasks WHERE proiect_id = ?', (pid,))
                cursor.execute('DELETE FROM proiecte WHERE id = ?', (pid,))

            conn.commit()
            for pid in project_ids:
                shutil.rmtree(os.path.join(UPLOAD_FOLDER, pid), ignore_errors=True)
            logger.info(f"Batch deleted {len(project_ids)} projects")
            return jsonify({'message': f'{len(project_ids)} projects deleted'})

        else:
            return jsonify({'error': 'Invalid action'}), 400

    except Exception as e:
        conn.rollback()
        logger.error(f"Batch operation error: {e}")
        return jsonify({'error': 'Batch operation failed'}), 500


# ============ CLIENTS ============

@projects_bp.route('/api/clienti', methods=['GET'])
@login_required
def get_clienti():
    conn = get_db()
    cursor = conn.cursor()

    search = request.args.get('search', '')

    if search:
        cursor.execute(
            'SELECT * FROM clienti WHERE nume LIKE ? OR adresa LIKE ? OR telefon LIKE ? ORDER BY nume',
            (f'%{search}%', f'%{search}%', f'%{search}%')
        )
    else:
        cursor.execute('SELECT * FROM clienti ORDER BY nume')

    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

def _normalize_client_name(name):
    """Title-case client name, preserving all-caps words (ABB, SRL, SA, GmbH)."""
    if not name:
        return ''
    words = name.strip().split()
    return ' '.join(
        w if w.isupper() and len(w) >= 2 else w.capitalize()
        for w in words
    )


@projects_bp.route('/api/clienti', methods=['POST'])
@login_required
def create_client():
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    client_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO clienti (id, nume, adresa, telefon, email, contact_principal, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        client_id,
        _normalize_client_name(data.get('nume', '')),
        data.get('adresa', ''),
        data.get('telefon', ''),
        data.get('email', ''),
        data.get('contact_principal', ''),
        data.get('note', ''),
        now
    ))

    conn.commit()
    conn.close()

    logger.info(f"Client created: {client_id} - {data.get('nume', '')}")
    return jsonify({'id': client_id, 'message': 'Client created'}), 201

@projects_bp.route('/api/clienti/<client_id>', methods=['GET'])
@login_required
def get_client(client_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM clienti WHERE id = ?', (client_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'error': 'Client not found'}), 404

    return jsonify(row_to_dict(row))

@projects_bp.route('/api/clienti/<client_id>', methods=['PUT'])
@login_required
def update_client(client_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    raw_name = data.get('nume')
    normalized_name = _normalize_client_name(raw_name) if raw_name else None
    cursor.execute('''
        UPDATE clienti SET
            nume = COALESCE(?, nume),
            adresa = COALESCE(?, adresa),
            telefon = COALESCE(?, telefon),
            email = COALESCE(?, email),
            contact_principal = COALESCE(?, contact_principal),
            note = COALESCE(?, note)
        WHERE id = ?
    ''', (
        normalized_name,
        data.get('adresa'),
        data.get('telefon'),
        data.get('email'),
        data.get('contact_principal'),
        data.get('note'),
        client_id
    ))

    conn.commit()
    conn.close()

    logger.info(f"Client updated: {client_id}")
    return jsonify({'message': 'Client updated'})

@projects_bp.route('/api/clienti/<client_id>', methods=['DELETE'])
@login_required
def delete_client(client_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM clienti WHERE id = ?', (client_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Client not found'}), 404
        logger.info(f"Client deleted: {client_id}")
        return jsonify({'message': 'Client deleted'})
    finally:
        conn.close()


# ============ PROJECT SNAPSHOT (Cowork sync) ============

@projects_bp.route('/api/proiecte/<project_id>/snapshot', methods=['GET'])
@login_required
def get_project_snapshot(project_id):
    """Full project export as JSON — consumed by Cowork to build debriefs.

    Returns the same schema shape as the debrief import, so Cowork can
    read what it wrote + everything the user added on site (real params,
    checked items, observations).
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM proiecte WHERE id = ?', (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return jsonify({'error': 'Project not found'}), 404

    p = row_to_dict(project)

    # Client
    client_data = None
    if p.get('client'):
        cursor.execute('SELECT * FROM clienti WHERE nume = ?', (p['client'],))
        crow = cursor.fetchone()
        if crow:
            client_data = row_to_dict(crow)

    # Tasks + subtasks
    cursor.execute('SELECT * FROM tasks WHERE proiect_id = ? ORDER BY created_at', (project_id,))
    tasks = []
    for r in cursor.fetchall():
        t = row_to_dict(r)
        cursor.execute('SELECT * FROM task_subtasks WHERE task_id = ? ORDER BY ordine', (t['id'],))
        t['subtasks'] = [row_to_dict(s) for s in cursor.fetchall()]
        tasks.append(t)

    conn.close()

    snapshot = {
        'meta': {
            'version': '1.0',
            'sursa': 'pif-dashboard',
            'exported_at': datetime.now().isoformat(),
            'project_id': project_id,
        },
        'client': client_data,
        'proiect': {
            'tip': p.get('tip', ''),
            'nume': p.get('nume', ''),
            'client': p.get('client', ''),
            'locatie': p.get('locatie', ''),
            'producator': p.get('producator', ''),
            'echipament_principal': p.get('echipament_principal', ''),
            'cod_proiect': p.get('cod_proiect', ''),
            'nr_comanda': p.get('nr_comanda', ''),
            'nr_contract': p.get('nr_contract', ''),
            'pm': p.get('pm', ''),
            'folder_server': p.get('folder_server', ''),
            'data_incepere': p.get('data_incepere', ''),
            'data_crearii': p.get('data_crearii', ''),
            'status': p.get('status', ''),
            'observatii': p.get('observatii', ''),
            'confirmat_client': p.get('confirmat_client', 0),
            'client_nume_confirmare': p.get('client_nume_confirmare', ''),
            'service_before': p.get('service_before', ''),
            'service_after': p.get('service_after', ''),
        },
        'tasks': [{
            'titlu': t.get('titlu', ''),
            'descriere': t.get('descriere', ''),
            'status': t.get('status', ''),
            'prioritate': t.get('prioritate', ''),
            'data_scadenta': t.get('data_scadenta', ''),
            'subtasks': [{'titlu': s.get('titlu', ''), 'done': bool(s.get('done'))} for s in t.get('subtasks', [])],
        } for t in tasks],
    }

    return jsonify(snapshot)


# ============ IMPORT PARAMETRI DIN EXPORT PRODUCATOR ============

def _familie_from_echipament(producator: str, model: str) -> str:
    """Mapeaza producator+model la familia de drive (eticheta din preview).

    Numele familiilor in DB (validat cu scripts/audit_pdf.py FAMILIES):
        ACS580, ACS880, Danfoss_VLT_FC302, Lenze_i550, Lenze_i950,
        SINAMICS_G120, SINAMICS_G130_G150, SINAMICS_S120_S150
    """
    producator = (producator or '').strip()
    model = (model or '').strip()
    p_low = producator.lower()
    m_low = model.lower()
    if 'danfoss' in p_low:
        return 'Danfoss_VLT_FC302'
    if 'abb' in p_low:
        if '880' in m_low: return 'ACS880'
        return 'ACS580'
    if 'siemens' in p_low:
        if 's120' in m_low or 's150' in m_low: return 'SINAMICS_S120_S150'
        if 'g130' in m_low or 'g150' in m_low: return 'SINAMICS_G130_G150'
        return 'SINAMICS_G120'
    if 'lenze' in p_low:
        if '950' in m_low: return 'Lenze_i950'
        return 'Lenze_i550'
    return ''


# ============ IMPORT MULTI-FILE ABB (.dcparamsbak) ============

@projects_bp.route('/api/import-abb-multi/preview', methods=['POST'])
# PUBLIC (fara login): doar parseaza fisierul incarcat -> nu atinge DB/date private.
# Permite importul de placuta in calculatorul public /calc pentru colegi.
def preview_import_abb_multi():
    """Parsează multiple fișiere .dcparamsbak ABB și returnează preview multi-drive.

    Form fields:
      files: unul sau mai multe fișiere .dcparamsbak
      model: optional, hint pentru familia (ACS580 vs ACS880)

    Returnează aceeași structură ca /import-archive/preview. Consumatorul e
    Calculatorul (completează plăcuța motorului); din v28 nu mai există
    persistare în DB — parametrii citiți se folosesc pe loc.
    """
    if (request.content_length or 0) > 30 * 1024 * 1024:
        return jsonify({'error': 'Fisier prea mare (max 30 MB)'}), 413
    files = request.files.getlist('files')
    if not files or all(not f.filename for f in files):
        return jsonify({'error': 'Niciun fișier selectat (field "files")'}), 400

    model_hint = (request.form.get('model') or '').strip()
    drives = []
    errors = []

    for upload in files:
        if not upload.filename:
            continue
        try:
            raw = upload.read()
        except Exception as e:
            errors.append(f'{upload.filename}: eroare citire ({e})')
            continue

        # Parse parameters (only non-default, non-signal)
        parsed = parse_abb(raw, upload.filename)
        # Extract drive metadata
        info = abb_drive_info(raw)

        if not parsed and not info:
            errors.append(f'{upload.filename}: nu s-a putut parsa')
            continue

        # Determine family
        family_raw = info.get('Family', '')
        model_raw = info.get('DriveModel', '')
        # INU/ISU modules in Multidrive cabinets have empty DriveModel —
        # construct fallback from Kind + ControlBoardType
        if not model_raw:
            kind = info.get('Kind') or info.get('ProductFamily') or family_raw or ''
            board = info.get('ControlBoardType', '')
            model_raw = f"{kind} ({board})" if board else kind
        familie = _familie_from_echipament('ABB', model_raw or model_hint or family_raw)

        # Build params dict {db_id: value} + parser descriptions
        params = {}
        parser_descrieri = {}
        for p in parsed:
            params[p['db_id']] = p['value']
            if p.get('name'):
                parser_descrieri[p['db_id']] = p['name']

        # Use drive name from backup, fallback to filename stem
        filename_stem = os.path.splitext(upload.filename)[0]
        drive_name = info.get('Name') or filename_stem

        firmware = info.get('Software') or info.get('SystemSoftwareVersion') or ''

        drives.append({
            'nume': drive_name,
            'producator': 'ABB',
            'model': model_raw,
            'firmware': firmware,
            'familie': familie,
            'serial_number': '',
            'params': params,
            'parser_descrieri': parser_descrieri,
            'filename': upload.filename,
        })

    if not drives:
        msg = 'Nu s-au putut parsa fișierele.'
        if errors:
            msg += ' Erori: ' + '; '.join(errors)
        return jsonify({'error': msg}), 400

    # v28: fara catalog de parametri -> meta e {}; filtrul ramane pe defaults
    # cunoscute de parser
    meta = _familie_param_meta(drives)
    _filter_drive_params(drives, meta)

    resp = {
        'filename': f'{len(drives)} fișiere ABB',
        'count': len(drives),
        'skipped_default': sum(d.get('skipped_default', 0) for d in drives),
        'drives': drives,
    }
    if errors:
        resp['warnings'] = errors

    return jsonify(resp)


# ============ IMPORT ARHIVA PROIECT (Siemens STARTER) ============

def _familie_param_meta(drives):
    """Stub din v28: tabela `parametri_master` a fost stearsa.

    Inainte, aici se citeau descrierile si valorile de fabrica ale parametrilor
    din catalogul intern, ca sa imbogateasca preview-ul de backup si sa filtreze
    parametrii ramasi la default. Catalogul nu mai exista — preview-ul arata
    exact ce scrie in fisierul de backup, fara imbogatire.

    Returneaza {} — exact comportamentul pe care il avea deja un deploy fara
    seed de parametri, deci `_filter_drive_params` stie sa il trateze.
    """
    return {}


def _equals_default(value, default):
    """True dacă valoarea curentă coincide cu default-ul de fabrică.

    Comparație numerică tolerantă (single-float repr) cu fallback pe string.
    Default necunoscut/gol => nu putem decide => False (păstrăm parametrul).
    """
    if default is None or str(default).strip() == '':
        return False
    a, b = str(value).strip(), str(default).strip()
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (ValueError, TypeError):
        return False


def _is_zeroish(value):
    """True dacă valoarea e zero numeric (0, 0.0, 0.00...)."""
    try:
        return float(str(value).strip()) == 0.0
    except (ValueError, TypeError):
        return False


def _filter_drive_params(drives, meta):
    """Elimină parametrii la valoarea de fabrică (zgomot) din fiecare drive.

    Reguli:
      - dacă valoarea == default cunoscut (din parser) => omis;
      - dacă parametrul lipsește din DB ȘI valoarea e 0 => omis (aproape sigur
        un connector BICO / funcție dezactivată neatinsă, nu o setare reală);
      - Siemens: dacă codul p are echivalent r în DB => e parametru read-only
        (monitorizare/diagnostic), omis — STARTER exportă r-params ca p-params;
      - restul se păstrează.
    Adaugă pe fiecare drive `descrieri`, `params` filtrat, `modified_count`,
    `skipped_default`.
    """
    for d in drives:
        fam = d.get('familie') or ''
        fam_meta = meta.get(fam, {})
        is_siemens = 'SINAMICS' in fam or 'MICROMASTER' in fam
        params = d.get('params', {})
        parser_desc = d.get('parser_descrieri') or {}
        kept, descrieri, skipped = {}, {}, 0
        for code, val in params.items():
            # Siemens: skip read-only monitoring params (r-prefix in DB)
            # STARTER exports r-params (r0026=DC link voltage) with p-prefix
            if is_siemens and code.startswith('p'):
                base = code.split('[')[0] if '[' in code else code
                r_code = 'r' + base[1:]
                if fam_meta.get(r_code):
                    skipped += 1
                    continue

            m = fam_meta.get(code)
            # Indexed params (p0114[2]) — try base param if exact not found
            if m is None and '[' in code:
                base = code.split('[')[0]
                m = fam_meta.get(base)
            # Siemens: try r-prefix for description even if param stays
            if m is None and is_siemens and code.startswith('p'):
                base = code.split('[')[0] if '[' in code else code
                r_code = 'r' + base[1:]
                r_m = fam_meta.get(r_code)
                if r_m and r_m.get('desc'):
                    # r-param exists but we didn't skip it (wasn't in r-check above)
                    # Still use its description
                    descrieri[code] = r_m['desc']
            if m is not None:
                if _equals_default(val, m['default']):
                    skipped += 1
                    continue
                if m.get('desc'):
                    descrieri[code] = m['desc']
                elif parser_desc.get(code):
                    descrieri[code] = parser_desc[code]
            elif _is_zeroish(val):
                # necunoscut în DB + valoare 0 => zgomot
                skipped += 1
                continue
            else:
                # fara catalog intern — folosim descrierea de la parser
                if parser_desc.get(code):
                    descrieri[code] = parser_desc[code]
            kept[code] = val
        d['params'] = kept
        d['descrieri'] = descrieri
        d['modified_count'] = len(kept)
        d['skipped_default'] = skipped


@projects_bp.route('/api/import-archive/preview', methods=['POST'])
# PUBLIC (fara login): doar parseaza arhiva incarcata -> nu atinge DB/date private.
def preview_import_archive():
    """Parsează o arhivă ZIP de proiect Siemens STARTER și returnează drive-urile.

    Form fields:
      file: arhiva .zip a proiectului STARTER (conține Project.mcp)

    Nu modifică DB — din v28 nu mai există persistare de echipamente;
    rezultatul alimentează direct Calculatorul.
    """
    if (request.content_length or 0) > 30 * 1024 * 1024:
        return jsonify({'error': 'Fisier prea mare (max 30 MB)'}), 413
    if 'file' not in request.files:
        return jsonify({'error': 'Fișier lipsă (field "file")'}), 400
    upload = request.files['file']
    if not upload.filename:
        return jsonify({'error': 'Fișier gol'}), 400

    try:
        raw = upload.read()
    except Exception as e:
        logger.exception("Eroare citire arhivă import")
        return jsonify({'error': f'Eroare citire fișier: {e}'}), 400

    try:
        result = parse_archive(raw)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        logger.exception("Eroare parsare arhivă STARTER")
        return jsonify({'error': f'Eroare la parsarea arhivei: {e}'}), 400

    drives = result.get('drives', [])
    meta = _familie_param_meta(drives)
    # Filtrează parametrii la valoarea de fabrică (elimină zgomotul de 0-uri).
    _filter_drive_params(drives, meta)

    return jsonify({
        'project_name': result.get('project_name', ''),
        'filename': upload.filename,
        'count': len(drives),
        'skipped_default': sum(d.get('skipped_default', 0) for d in drives),
        'drives': drives,
    })


# ============ STRUCTURED IMPORT (Cowork AI debrief) ============

@projects_bp.route('/api/import/debrief', methods=['POST'])
@login_required
def import_debrief():
    """Structured import from an external AI tool (Cowork).

    Receives a single JSON payload describing a project debrief and
    creates/updates entities in the correct dependency order:
      1. Client (upsert by name)
      2. Proiect (upsert by name+client) — jurnal[] narrative folds into
         observatii (PIF) / service_after (Service); ore[] is ignored since
         v22 (orele se ponteaza in e100, nu in dashboard)

    `echipamente[]` este acceptat dar IGNORAT din v28 — tabela nu mai exista.
    Parametrii de drive stau in wiki (skill-ul drive-backup), nu in dashboard.
    Numarul de echipamente ignorate e raportat in `sumar.echipamente_ignorate`
    ca sa fie vizibil, nu inghitit in tacere.

    Returns the project ID and a summary of what was created.
    """
    data = get_json_or_400()
    if not data:
        return jsonify({'error': 'JSON body required'}), 400

    proiect_data = data.get('proiect') or {}
    if not proiect_data.get('nume'):
        return jsonify({'error': 'proiect.nume is required'}), 400

    # ── Idempotency guard ──────────────────────────────────────────────
    # meta.debrief_id uniquely identifies a Cowork debrief. If we've imported
    # it before, return the existing project instead of inserting duplicate
    # equipment / task rows.
    #
    # BUT: only treat it as a duplicate if that project STILL EXISTS. If the
    # user deleted the imported project and wants to re-import, the stale
    # debrief_id record must not block them — it gets overwritten with the new
    # project id on success below.
    meta = data.get('meta') or {}
    debrief_id = (meta.get('debrief_id') or '').strip()
    if debrief_id:
        prev_pid = get_app_setting(f'import_debrief:{debrief_id}')
        if prev_pid:
            _c = get_db()
            try:
                still_exists = _c.cursor().execute(
                    'SELECT 1 FROM proiecte WHERE id = ?', (prev_pid,)
                ).fetchone() is not None
            finally:
                _c.close()
            if still_exists:
                logger.info(f"Import debrief: duplicate debrief_id={debrief_id} -> existing {prev_pid}")
                return jsonify({
                    'success': True,
                    'duplicate': True,
                    'proiect_id': prev_pid,
                    'proiect_url': f'/proiecte/{prev_pid}',
                    'creat': False,
                    'sumar': {'echipamente_ignorate': 0},
                }), 200
            logger.info(f"Import debrief: prior project {prev_pid} for debrief_id={debrief_id} was deleted — allowing re-import")

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    sumar = {
        # v28: tabela `echipamente` a fost stearsa. Raportam cate au venit in
        # payload si au fost ignorate, ca sa nu para ca s-au importat.
        'echipamente_ignorate': len(data.get('echipamente') or []),
    }

    try:
        # ── 1. Client ──────────────────────────────────────────────
        client_data = data.get('client') or {}
        client_id = None
        client_name = (client_data.get('nume') or proiect_data.get('client') or '').strip()

        if client_name:
            cursor.execute(
                'SELECT id FROM clienti WHERE LOWER(nume) = LOWER(?)',
                (client_name,)
            )
            row = cursor.fetchone()
            if row:
                client_id = row['id']
            else:
                client_id = generate_uuid()
                cursor.execute('''
                    INSERT INTO clienti (id, nume, adresa, telefon, email, contact_principal, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    client_id,
                    client_name,
                    client_data.get('adresa', ''),
                    client_data.get('telefon', ''),
                    client_data.get('email', ''),
                    client_data.get('contact_principal', ''),
                    client_data.get('note', ''),
                    now,
                ))
                logger.info(f"Import debrief: created client '{client_name}' ({client_id})")

        # ── 2. Proiect ─────────────────────────────────────────────
        proiect_nume = proiect_data['nume'].strip()
        proiect_client = client_name or proiect_data.get('client', '')

        # Detailed narrative (from jurnal[]) -> goes to observatii (PIF) or
        # service_after (Service). Since v22 there is no jurnal table anymore —
        # this fold-in IS the journal. Each block: "YYYY-MM-DD: text".
        _detail_blocks = []
        for _e in (data.get('jurnal') or []):
            _t = (_e.get('continut') or _e.get('text') or '').strip()
            if _t:
                _ed = (_e.get('data') or '').strip()
                _detail_blocks.append(f"{_ed}: {_t}" if _ed else _t)
        detail = "\n\n".join(_detail_blocks)
        is_service = (proiect_data.get('tip', 'PIF') == 'Service')

        # observatii: PIF gets the detail; Service keeps its own short observatii
        # (the detail goes to service_after instead). observatii_pv belongs to
        # Cowork's PV — the dashboard ignores it.
        if is_service:
            observatii_val = proiect_data.get('observatii', '')
        else:
            observatii_val = detail or proiect_data.get('observatii', '')

        # service_after: Service folds Cowork's value + the detail; PIF leaves it.
        if is_service:
            _sa = (proiect_data.get('service_after') or '').strip()
            if _sa and detail:
                service_after_val = _sa + "\n\n" + detail
            else:
                service_after_val = _sa or detail
        else:
            service_after_val = proiect_data.get('service_after', '')

        cursor.execute(
            'SELECT id FROM proiecte WHERE LOWER(nume) = LOWER(?) AND LOWER(COALESCE(client, \'\')) = LOWER(?)',
            (proiect_nume, proiect_client.lower())
        )
        existing = cursor.fetchone()
        proiect_creat = existing is None

        if existing:
            project_id = existing['id']
            logger.info(f"Import debrief: found existing project '{proiect_nume}' ({project_id})")
        else:
            project_id = proiect_data.get('id') or generate_uuid()
            cursor.execute('''
                INSERT INTO proiecte (
                    id, tip, nume, client, locatie, echipament_principal, producator,
                    cod_proiect, pm, folder_server, data_incepere, data_crearii,
                    status, observatii, nr_comanda, nr_contract, service_before, service_after,
                    confirmat_client, client_nume_confirmare, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_id,
                proiect_data.get('tip', 'PIF'),
                proiect_nume,
                proiect_client,
                proiect_data.get('locatie', ''),
                proiect_data.get('echipament_principal', ''),
                proiect_data.get('producator', 'Altul'),
                proiect_data.get('cod_proiect', ''),
                proiect_data.get('pm', ''),
                proiect_data.get('folder_server', ''),
                proiect_data.get('data_incepere', ''),
                proiect_data.get('data_crearii', now[:10]),
                proiect_data.get('status', 'in_lucru'),
                observatii_val,
                proiect_data.get('nr_comanda', ''),
                proiect_data.get('nr_contract', ''),
                proiect_data.get('service_before', ''),
                service_after_val,
                proiect_data.get('confirmat_client', 0),
                proiect_data.get('client_nume_confirmare', ''),
                now, now,
            ))
            logger.info(f"Import debrief: created project '{proiect_nume}' ({project_id})")

        # echipamente[] se ignora din v28 — tabela nu mai exista; parametrii de
        # drive stau in wiki (skill-ul drive-backup, extractie determinista din
        # .dcparamsbak / STARTER). Numarul lor e deja in sumar.
        if sumar['echipamente_ignorate']:
            logger.info(
                f"Import debrief: {sumar['echipamente_ignorate']} echipamente ignorate "
                f"(v28) pentru proiectul {project_id}")

        # jurnal[] s-a pliat deja in observatii/service_after (sectiunea 2);
        # ore[] se ignora — orele se ponteaza in e100, nu in dashboard (v22).

        conn.commit()

    except Exception as e:
        conn.rollback()
        logger.exception(f"Import debrief failed: {e}")
        return jsonify({'error': 'Importul a esuat — verifica formatul JSON (detalii in logurile serverului).'}), 500
    finally:
        conn.close()

    # Record the debrief_id AFTER a successful commit so a future re-import of
    # the same debrief is recognised as a duplicate (see idempotency guard).
    if debrief_id:
        try:
            set_app_setting(f'import_debrief:{debrief_id}', project_id)
        except Exception:
            logger.warning(f"Import debrief: could not record debrief_id={debrief_id}")

    logger.info(f"Import debrief OK: project={project_id}, creat={proiect_creat}, debrief_id={debrief_id or '-'}, sumar={sumar}")
    return jsonify({
        'success': True,
        'duplicate': False,
        'proiect_id': project_id,
        'proiect_url': f'/proiecte/{project_id}',
        'creat': proiect_creat,
        'sumar': sumar,
    }), 201


# ---------------------------------------------------------------------------
# Perioade de implementare (separate de taskuri): Site (santier) / Sediu EGB
# ---------------------------------------------------------------------------

_IMPL_LOC = ('site', 'sediu')
# Faza e INDEPENDENTA de locatie: PIF-ul poate fi si la sediu, si in site, uneori
# in doua etape. „Unde esti" si „in ce faza esti" sunt doua fapte separate.
_IMPL_FAZA = ('pregatire', 'implementare')


def _impl_row(r):
    d = row_to_dict(r)
    return {
        'id': d['id'],
        'proiect_id': d['proiect_id'],
        'data_start': d.get('data_start') or '',
        'data_sfarsit': d.get('data_sfarsit') or '',
        'locatie': d.get('locatie') or 'site',
        'faza': d.get('faza') or 'implementare',
        'eticheta': d.get('eticheta') or '',
        'ordine': d.get('ordine') or 0,
    }


@projects_bp.route('/api/proiecte/<project_id>/implementari', methods=['GET'])
@login_required
def get_implementari(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM implementari WHERE proiect_id = ? ORDER BY data_start ASC, ordine ASC', (project_id,))
    rows = [_impl_row(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


@projects_bp.route('/api/proiecte/<project_id>/implementari', methods=['POST'])
@login_required
def create_implementare(project_id):
    data = get_json_or_400()
    loc = (data.get('locatie') or 'site').strip().lower()
    if loc not in _IMPL_LOC:
        loc = 'site'
    faza = (data.get('faza') or 'implementare').strip().lower()
    if faza not in _IMPL_FAZA:
        faza = 'implementare'
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM proiecte WHERE id = ?', (project_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Proiect inexistent'}), 404
    impl_id = data.get('id') or generate_uuid()
    cursor.execute('''INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit, locatie, faza, eticheta, ordine, created_at)
                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                   (impl_id, project_id, (data.get('data_start') or ''), (data.get('data_sfarsit') or ''),
                    loc, faza, (data.get('eticheta') or ''), data.get('ordine', 0), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return jsonify({'id': impl_id}), 201


@projects_bp.route('/api/implementari/<impl_id>', methods=['PUT'])
@login_required
def update_implementare(impl_id):
    data = get_json_or_400()
    loc = data.get('locatie')
    if loc is not None:
        loc = loc.strip().lower()
        if loc not in _IMPL_LOC:
            loc = None  # keep existing on invalid
    faza = data.get('faza')
    if faza is not None:
        faza = faza.strip().lower()
        if faza not in _IMPL_FAZA:
            faza = None
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''UPDATE implementari SET
                        data_start = COALESCE(?, data_start),
                        data_sfarsit = COALESCE(?, data_sfarsit),
                        locatie = COALESCE(?, locatie),
                        faza = COALESCE(?, faza),
                        eticheta = COALESCE(?, eticheta),
                        ordine = COALESCE(?, ordine)
                      WHERE id = ?''',
                   (data.get('data_start'), data.get('data_sfarsit'), loc, faza,
                    data.get('eticheta'), data.get('ordine'), impl_id))
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    if updated == 0:
        return jsonify({'error': 'Perioada inexistenta'}), 404
    return jsonify({'message': 'ok'})


@projects_bp.route('/api/implementari/<impl_id>', methods=['DELETE'])
@login_required
def delete_implementare(impl_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM implementari WHERE id = ?', (impl_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    if deleted == 0:
        return jsonify({'error': 'Perioada inexistenta'}), 404
    return jsonify({'message': 'ok'})

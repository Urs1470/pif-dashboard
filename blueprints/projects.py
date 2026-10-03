# Projects Blueprint
# Provides all project-related CRUD routes extracted from app.py

import os
import json
import shutil
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

from database import get_db, row_to_dict
from utils import (
    safe_table, generate_uuid, login_required, UPLOAD_FOLDER, id_ocupat,
    get_app_setting, set_app_setting, get_json_or_400, refuse_device_token_fields,
)

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
    refuse_device_token_fields(data)
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    project_id = data.get('id') or generate_uuid()
    if data.get('id'):
        ocupat = id_ocupat(cursor, 'proiecte', project_id)
        if ocupat:
            conn.close()
            return ocupat

    # Invariantul din CLAUDE.md: `data_finalizare` exista daca si numai daca
    # statusul e `finalizat`. Crearea nu scria coloana DELOC, iar `status` vine din
    # corpul cererii — deci un POST cu `status: 'finalizat'` (masinile o pot face:
    # ruta accepta Bearer) nastea un proiect inchis fara ziua inchiderii. Efectul
    # se vede abia in Calendar, unde taierea perioadelor cade pe `date('now')` cand
    # data lipseste: deplasarea ramane afisata pana azi in loc sa se opreasca
    # atunci. Aceeasi gaura fusese deja astupata pe drumul de import debrief; asta
    # era celalalt capat al ei.
    status_nou = data.get('status', 'pregatire')
    data_final = (data.get('data_finalizare') or now[:10]) if status_nou == 'finalizat' else ''

    cursor.execute('''
        INSERT INTO proiecte (
            id, tip, nume, client, locatie, echipament_principal, producator,
            cod_proiect, folder_server, data_crearii,
            status, data_finalizare, observatii, nr_comanda, service_before, service_after,
            confirmat_client, client_nume_confirmare, created_at, updated_at, vault_folder
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        project_id,
        data.get('tip', 'PIF'),
        data.get('nume', ''),
        data.get('client', ''),
        data.get('locatie', ''),
        data.get('echipament_principal', ''),
        data.get('producator', 'Altul'),
        data.get('cod_proiect', ''),
        data.get('folder_server', ''),
        data.get('data_crearii', now[:10]),
        status_nou,
        data_final,
        data.get('observatii', ''),
        data.get('nr_comanda', ''),
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
    refuse_device_token_fields(data)
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    # Get current project status
    cursor.execute('SELECT status FROM proiecte WHERE id = ?', (project_id,))
    current = cursor.fetchone()
    old_status = current['status'] if current else None

    cursor.execute('''
        UPDATE proiecte SET
            tip = COALESCE(?, tip),
            nume = COALESCE(?, nume),
            client = COALESCE(?, client),
            locatie = COALESCE(?, locatie),
            echipament_principal = COALESCE(?, echipament_principal),
            producator = COALESCE(?, producator),
            cod_proiect = COALESCE(?, cod_proiect),
            folder_server = COALESCE(?, folder_server),
            status = COALESCE(?, status),
            data_finalizare = COALESCE(?, data_finalizare),
            observatii = COALESCE(?, observatii),
            nr_comanda = COALESCE(?, nr_comanda),
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
        data.get('folder_server'),
        data.get('status'),
        data.get('data_finalizare'),
        data.get('observatii'),
        data.get('nr_comanda'),
        data.get('service_before'),
        data.get('service_after'),
        data.get('confirmat_client'),
        data.get('client_nume_confirmare'),
        data.get('vault_folder'),
        now,
        project_id
    ))

    # Ziua inchiderii, nu ziua in care te uiti: perioadele unui proiect finalizat
    # se taie la `data_finalizare` (vezi /api/calendar).
    #
    # Regula e un INVARIANT, nu o curatenie: data exista daca si numai daca
    # proiectul e finalizat. Altfel formularul o tine agatata cand redeschizi
    # (DatePicker-ul se ascunde, dar valoarea rămâne in form) si la o eventuala
    # re-inchidere ai reveni in tacere la ziua veche.
    #
    # Ramura de inchidere e scrisa ca o CONDITIE PE RAND, nu pe tranzitie: „e
    # finalizat si n-are data -> pune azi". Varianta veche cerea in plus
    # `old_status != 'finalizat'`, deci vindeca doar inchiderea de acum; un rand
    # deja inchis dar cu data goala — venit dintr-un import, dintr-o restaurare,
    # sau de dinainte de v35 — nu si-o mai lua niciodata, oricate salvari ar fi
    # urmat. Garda `TRIM(data_finalizare) = ''` face ca datele existente sa nu
    # poata fi calcate: nu e o suprascriere, e o completare.
    status_efectiv = data.get('status') or old_status
    if status_efectiv != 'finalizat':
        cursor.execute("UPDATE proiecte SET data_finalizare = '' WHERE id = ?",
                       (project_id,))
    else:
        cursor.execute(
            """UPDATE proiecte SET data_finalizare = ?
               WHERE id = ? AND status = 'finalizat'
                 AND (data_finalizare IS NULL OR TRIM(data_finalizare) = '')""",
            (now[:10], project_id))

    # LA INCHIDERE, PERIOADELE TRECUTE SE BIFEAZA SINGURE (cerut de Ion,
    # 2026-08-10). Motivul practic care a scos regula la iveala: doua proiecte
    # inchise pe 5 august aveau perioade din 29-30 iulie nebifate, iar v39
    # stinge intrebarea „s-a facut?" la inchidere — deci perioadele ramaneau
    # pentru totdeauna fara eticheta „Făcut", fara niciun drum de a o pune.
    # Semantica e onesta: inchizi un proiect DUPA ce lucrul s-a facut, deci o
    # perioada deja trecuta la inchidere s-a intamplat. Doar cele TRECUTE:
    # o perioada viitoare ramasa in calendar e o planificare gresita, nu un
    # fapt — aia se sterge sau se muta, nu se bifeaza din oficiu.
    if status_efectiv == 'finalizat' and old_status != 'finalizat':
        cursor.execute(
            """UPDATE implementari
               SET confirmata = 1
               WHERE proiect_id = ?
                 AND COALESCE(confirmata, 0) = 0
                 AND date(COALESCE(NULLIF(data_sfarsit, ''), data_start)) < date(?)""",
            (project_id, now[:10]))

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

#  a plecat pe 2026-08-15: zero consumatori, in SPA si in
# afara lui. Avea si un defect care ar fi lovit exact la folosire — ramura de
# stergere scotea `task_subtasks`, `tasks` si `proiecte`, dar NU si
# `implementari`/`task_dependencies`, spre deosebire de stergerea unui singur
# proiect. Adica ar fi lasat perioade orfane in Calendar.

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

    # Calcule atasate (v37). Intra in snapshot pentru ca de aici le ia debrief-ul
    # ca sa nu le mai retastezi in PV.
    try:
        cursor.execute('SELECT * FROM calcule WHERE proiect_id = ? ORDER BY created_at', (project_id,))
        calcule = [_calc_row(r) for r in cursor.fetchall()]
    except Exception:
        calcule = []   # deploy vechi, fara tabela

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
            'folder_server': p.get('folder_server', ''),
            'data_crearii': p.get('data_crearii', ''),
            'status': p.get('status', ''),
            # Invariantul v35 (`data_finalizare` exista <=> status == 'finalizat') se
            # VERIFICA din snapshot de catre debrief. Lipsea din lista asta, deci
            # snapshotul raporta `null` pe un proiect care avea data in baza si in
            # `GET /api/proiecte` — iar debrief-ul re-PUT-a degeaba, crezand ca repara
            # o incalcare de invariant (E-100, 26_162).
            'data_finalizare': p.get('data_finalizare') or '',
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
            'data_scadenta': t.get('data_scadenta', ''),
            'subtasks': [{'titlu': s.get('titlu', ''), 'done': bool(s.get('done'))} for s in t.get('subtasks', [])],
        } for t in tasks],
        'calcule': [{
            'titlu': c.get('titlu', ''),
            'modul': c.get('modul_titlu', ''),
            'intrari': c.get('intrari', {}),
            'rezultate': c.get('rezultate', {}),
            'verdicte': c.get('verdicte', {}),
            'stare': c.get('stare'),
            'nota': c.get('nota', ''),
            'data': c.get('created_at', ''),
        } for c in calcule],
    }

    return jsonify(snapshot)


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
    refuse_device_token_fields(data, proiect_data)
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
        # Cate taskuri au intrat efectiv. Pana pe 2026-08-15 `tasks[]` era acceptat
        # de JSON si NU era scris nicaieri: un debrief cu taskuri se importa cu
        # succes si le pierdea in tacere, fara eroare si fara nimic in sumar.
        'taskuri_create': 0,
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
            # Invariantul din CLAUDE.md: `data_finalizare` exista daca si numai daca
            # statusul e `finalizat`. Importul nu o scria deloc, deci un debrief
            # inchis (cazul NORMAL — debrief-ul se face la finalul lucrarii) crea un
            # proiect inchis fara ziua inchiderii. Efectul se vedea abia in Calendar:
            # taierea perioadelor cade pe `date('now')` cand data lipseste, deci
            # deplasarea ramanea afisata pana azi in loc sa se opreasca atunci.
            status_val = proiect_data.get('status', 'pregatire')
            data_final = (proiect_data.get('data_finalizare') or now[:10]
                          ) if status_val == 'finalizat' else ''
            cursor.execute('''
                INSERT INTO proiecte (
                    id, tip, nume, client, locatie, echipament_principal, producator,
                    cod_proiect, folder_server, data_crearii,
                    status, data_finalizare, observatii, nr_comanda,
                    service_before, service_after,
                    confirmat_client, client_nume_confirmare, vault_folder,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_id,
                proiect_data.get('tip', 'PIF'),
                proiect_nume,
                proiect_client,
                proiect_data.get('locatie', ''),
                proiect_data.get('echipament_principal', ''),
                proiect_data.get('producator', 'Altul'),
                proiect_data.get('cod_proiect', ''),
                proiect_data.get('folder_server', ''),
                proiect_data.get('data_crearii', now[:10]),
                status_val,
                data_final,
                observatii_val,
                proiect_data.get('nr_comanda', ''),
                proiect_data.get('service_before', ''),
                service_after_val,
                proiect_data.get('confirmat_client', 0),
                proiect_data.get('client_nume_confirmare', ''),
                # Legatura cu dosarul din vault: `wiki/job/projects/<client>/<slug>/`.
                # Fara ea, tabul Wiki al proiectului nou importat e gol.
                proiect_data.get('vault_folder', ''),
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

        # ── 3. Taskuri ─────────────────────────────────────────────
        # Se scriu DUPA proiect, ca sa existe parintele. La un proiect existent se
        # adauga la coada, nu se rescriu cele de acolo: un re-import nu are voie sa
        # stearga ce a bifat omul intre timp.
        taskuri = data.get('tasks') or []
        if taskuri:
            cursor.execute(
                'SELECT MAX(ordine) AS m FROM tasks WHERE proiect_id = ?', (project_id,))
            r = cursor.fetchone()
            ordine = (r['m'] if r and r['m'] is not None else 0)
            for t in taskuri:
                titlu = (t.get('titlu') or t.get('title') or '').strip()
                if not titlu:
                    continue                      # un task fara titlu n-are ce afisa
                ordine += 1
                stare = t.get('status', 'to_do')
                cursor.execute('''
                    INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta,
                                       data_finalizare, ordine, created_at, descriere,
                                       recurenta, updated_at, ordine_agenda)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    t.get('id') or generate_uuid(),
                    project_id,
                    titlu,
                    stare,
                    t.get('data_scadenta', ''),
                    # Aceeasi regula ca la proiect: data de finalizare exista doar
                    # daca e chiar facut.
                    (t.get('data_finalizare') or now[:10]) if stare == 'done' else '',
                    ordine,
                    now,
                    t.get('descriere', ''),
                    t.get('recurenta', ''),
                    now,
                    t.get('ordine_agenda', 0),
                ))
                sumar['taskuri_create'] += 1

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
        # v39: perioada s-a facut. Raspunsul la „a trecut, s-a facut?" sta aici,
        # nu pe statusul proiectului — dupa implementare mai raman PV-uri, si
        # poate o vizita pe care inca n-o poti data.
        'confirmata': 1 if d.get('confirmata') else 0,
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
    if data.get('id'):
        ocupat = id_ocupat(cursor, 'implementari', impl_id)
        if ocupat:
            conn.close()
            return ocupat
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
    # Confirmarea se muta in ambele sensuri: se bifeaza dintr-o singura apasare,
    # deci trebuie sa se poata si scoate din una. Mutarea perioadei NU o reseteaza
    # — „am fost pe 5, nu pe 4" e o corectare de consemnare, nu o replanificare.
    confirmata = data.get('confirmata')
    if confirmata is not None:
        confirmata = 1 if confirmata in (1, True, '1', 'true') else 0
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''UPDATE implementari SET
                        data_start = COALESCE(?, data_start),
                        data_sfarsit = COALESCE(?, data_sfarsit),
                        locatie = COALESCE(?, locatie),
                        faza = COALESCE(?, faza),
                        eticheta = COALESCE(?, eticheta),
                        ordine = COALESCE(?, ordine),
                        confirmata = COALESCE(?, confirmata)
                      WHERE id = ?''',
                   (data.get('data_start'), data.get('data_sfarsit'), loc, faza,
                    data.get('eticheta'), data.get('ordine'), confirmata, impl_id))
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


# ============ CALCULE (Calculator -> proiect) ============
# Un calcul atasat unui proiect e o consemnare, nu o formula vie: intrarile,
# rezultatele si verdictele se salveaza inghetate (vezi migratia v37). De aia
# ruta nu recalculeaza nimic — primeste ce s-a vazut pe ecran si asta pastreaza.

_CALC_STARI = {'ok', 'atentie', 'critic'}


def _calc_row(row):
    """Randul din DB -> JSON, cu campurile JSON desfacute inapoi in obiecte."""
    d = row_to_dict(row)
    for k in ('intrari', 'rezultate', 'verdicte'):
        raw = d.get(k)
        if not raw:
            d[k] = {}
            continue
        try:
            d[k] = json.loads(raw)
        except (ValueError, TypeError):
            # Nu aruncam: un rand cu JSON stricat nu trebuie sa rupa toata lista.
            d[k] = {}
    return d

# Cele trei rute `calcule` (GET/POST pe proiect, DELETE pe calcul) au plecat pe
# 2026-08-15: tabul Calcule al paginii de proiect — singurul lor consumator — a
# fost scos la redesignul din 8 august, iar un buton care salveaza intr-un loc pe
# care nu-l mai poti deschide e mai rau decat lipsa lui.
#
# TABELA `calcule` RAMANE si e VIE: o citeste `/api/proiecte/<id>/snapshot`, de
# unde skill-ul `pif-debrief` ia calculele ca sa nu le retastezi in PV. Se scrie
# doar prin import/restore. `_calc_row` ramane, il foloseste snapshotul.

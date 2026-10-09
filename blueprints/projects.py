# Projects Blueprint
# Provides all project-related CRUD routes extracted from app.py

import os
import re
import shutil
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

from database import get_db, row_to_dict
from labels import PROJECT_STATUS_LABELS
from utils import (
    safe_table, generate_uuid, login_required, UPLOAD_FOLDER, id_ocupat,
    get_json_or_400, refuse_device_token_fields,
)

logger = logging.getLogger('pif_dashboard')

projects_bp = Blueprint('projects', __name__)

# Statusul vine din corpul cererii, inclusiv de la tokenul de dispozitiv, si ajunge in baza si in
# frontmatter-ul README-ului din vault (se comite in Knowledge). Primeste doar cele doua valori
# ale invariantului 2; cheile vechi din labels.py (`in_lucru`...) se strang in `pregatire`, ca un
# `pif-sync.py create` cu un frontmatter vechi sa nu pice.
def status_proiect(valoare):
    """'pregatire' | 'finalizat' pentru o valoare cunoscuta, altfel None."""
    if not isinstance(valoare, str):
        return None
    valoare = valoare.strip()
    if valoare not in PROJECT_STATUS_LABELS:
        return None
    return 'finalizat' if valoare == 'finalizat' else 'pregatire'


_STATUS_NECUNOSCUT = 'Status necunoscut: pregatire sau finalizat'

# In `uploads/` stau si dosarele aplicatiei (APK-urile, build-ul Torqa web); un id de proiect nu
# are voie sa le ia locul, nici sa iasa din `uploads/` (`..`).
_DOSARE_APLICATIEI = ('app', 'torqa-web')
_ID_DE_DOSAR = re.compile(r'[A-Za-z0-9_-]{1,64}')


def dosar_de_incarcari(project_id):
    """Calea reala a lui `uploads/<project_id>`, sau None daca id-ul nu poate fi un dosar de
    proiect: alt format decat UUID / nanoid, numele unui dosar al aplicatiei, ori o cale care
    nu iese direct sub `uploads/` (legatura simbolica)."""
    if not isinstance(project_id, str) or not _ID_DE_DOSAR.fullmatch(project_id):
        return None
    if project_id.lower() in _DOSARE_APLICATIEI:
        return None
    baza = os.path.realpath(UPLOAD_FOLDER)
    cale = os.path.realpath(os.path.join(baza, project_id))
    if os.path.normcase(os.path.dirname(cale)) != os.path.normcase(baza):
        return None
    return cale


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
    status_nou = status_proiect(data['status']) if 'status' in data else 'pregatire'
    if status_nou is None:
        conn.close()
        return jsonify({'error': _STATUS_NECUNOSCUT}), 400
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
    if data.get('status') is not None:
        data['status'] = status_proiect(data['status'])
        if data['status'] is None:
            return jsonify({'error': _STATUS_NECUNOSCUT}), 400
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
    # Un proiect care nu exista da 404, inainte de orice stergere (Torqa tine 404 drept „sters
    # deja", deci nu se strica nimic la o reincercare).
    cursor.execute('SELECT 1 FROM proiecte WHERE id = ?', (project_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Project not found'}), 404
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
        dosar = dosar_de_incarcari(project_id)
        if dosar is None:
            logger.warning("Uploads not removed for project id with no safe folder name")
        else:
            shutil.rmtree(dosar, ignore_errors=True)
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
    }

    return jsonify(snapshot)


# Importul structurat de debrief (`POST /api/import/debrief`) a plecat pe 2026-10-03, cu tabela
# `clienti` pe care o umplea (v43): nu-l mai chema nimic din iulie, iar debrief-ul scrie direct prin
# rutele de proiect si task (skill-ul `proiect`, modul pif-debrief).


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

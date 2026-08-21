import calendar
import logging
import re
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from database import get_db, row_to_dict
from utils import generate_uuid, login_required, get_json_or_400

tasks_bp = Blueprint('tasks', __name__)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _skip_weekend(d):
    """Ion nu lucreaza in weekend: o scadenta care cade sambata sau duminica se
    muta pe lunea urmatoare (inainte, nu inapoi). weekday(): luni=0 .. duminica=6."""
    if d.weekday() == 5:        # sambata -> +2 zile = luni
        return d + timedelta(days=2)
    if d.weekday() == 6:        # duminica -> +1 zi = luni
        return d + timedelta(days=1)
    return d


def _next_recurrence_date(base_str, recurenta):
    """base_str: 'YYYY-MM-DD' (flatpickr format) or empty. Returns the next
    occurrence date as 'YYYY-MM-DD'. Falls back to today when base is unparsable.
    Sare peste weekend: o aparitie care ar cadea sambata/duminica se muta luni
    (ex. un task zilnic terminat vineri revine luni, nu sambata)."""
    try:
        base = datetime.strptime((base_str or '')[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        base = datetime.now().date()
    if recurenta == 'zilnic':
        nxt = base + timedelta(days=1)
    elif recurenta == 'saptamanal':
        nxt = base + timedelta(days=7)
    elif recurenta == 'lunar':
        m = base.month + 1
        y = base.year + (1 if m > 12 else 0)
        if m > 12:
            m -= 12
        d = min(base.day, calendar.monthrange(y, m)[1])
        nxt = datetime(y, m, d).date()
    else:
        return base_str or ''
    return _skip_weekend(nxt).isoformat()


def _spawn_recurring_task(cursor, existing, recurenta):
    """Create the next occurrence of a recurring task that was just completed.
    Copies title/priority/description/recurrence and fresh (unchecked) subtasks.
    `existing` is the sqlite Row of the completed task. Returns the new id."""
    new_id = generate_uuid()
    now = datetime.now().isoformat()
    next_scad = _next_recurrence_date(existing['data_scadenta'] or '', recurenta)
    cursor.execute('SELECT MAX(ordine) FROM tasks WHERE proiect_id = ?', (existing['proiect_id'],))
    max_ordine = cursor.fetchone()[0] or 0
    # ordine_agenda e deliberat NECOPIAT: urmatoarea
    # occurrence is born unplanned and surfaces on the Astazi board later via its
    # future data_scadenta, not the moment the current one is completed.
    cursor.execute('''
        INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta,
                           data_finalizare, ordine, created_at, descriere, recurenta, updated_at)
        VALUES (?, ?, ?, 'to_do', ?, '', ?, ?, ?, ?, ?)
    ''', (new_id, existing['proiect_id'], existing['titlu'],
          next_scad, max_ordine + 1, now, existing['descriere'] or '', recurenta, now))
    # Carry the subtasks over, all unchecked -- a recurring checklist repeats clean.
    cursor.execute('SELECT titlu, ordine FROM task_subtasks WHERE task_id = ? ORDER BY ordine', (existing['id'],))
    for srow in cursor.fetchall():
        cursor.execute(
            'INSERT INTO task_subtasks (id, task_id, titlu, done, ordine, created_at) VALUES (?, ?, ?, 0, ?, ?)',
            (generate_uuid(), new_id, srow['titlu'], srow['ordine'], now)
        )
    return new_id


def _spawn_recurring_global_task(cursor, existing, recurenta):
    """Spawn the next occurrence of a completed recurring daily task. Copies
    title/priority/category/description + fresh subtasks. Returns the new id."""
    new_id = generate_uuid()
    now = datetime.now().isoformat()
    next_scad = _next_recurrence_date(existing['data_scadenta'] or '', recurenta)
    # ordine_agenda deliberat necopiat (vezi _spawn_recurring_task). `sfera` se
    # copiaza OBLIGATORIU: altfel un task personal recurent ar migra in lista
    # de munca la prima bifare (INSERT-ul ar cadea pe default-ul 'munca').
    # `ora` (v41) se copiaza din ACELASI motiv, si e cazul cel mai probabil sa se
    # observe: un task personal recurent ARE ora tocmai pentru ca se repeta la
    # aceeasi ora („zilnic la 7:30"). Necopiata, ea ar dispărea la prima bifare —
    # adica exact atunci cand taskul isi dovedeste recurenta.
    # `.keys()`, nu acces direct: randul vine dintr-un `SELECT *` facut inainte de
    # migrare in bazele care n-au apucat-o (restaurare veche), si atunci cheia
    # lipseste cu totul.
    ora_veche = (existing['ora'] if 'ora' in existing.keys() else '') or ''
    cursor.execute('''
        INSERT INTO global_tasks (id, titlu, descriere, status, categorie, sfera,
                                  data_scadenta, data_finalizare, created_at, updated_at, recurenta, ora)
        VALUES (?, ?, ?, 'to_do', ?, ?, ?, '', ?, ?, ?, ?)
    ''', (new_id, existing['titlu'], existing['descriere'] or '',
          existing['categorie'], existing['sfera'] or 'munca',
          next_scad, now, now, recurenta, ora_veche))
    cursor.execute('SELECT titlu, ordine FROM task_subtasks WHERE task_id = ? ORDER BY ordine', (existing['id'],))
    for srow in cursor.fetchall():
        cursor.execute(
            'INSERT INTO task_subtasks (id, task_id, titlu, done, ordine, created_at) VALUES (?, ?, ?, 0, ?, ?)',
            (generate_uuid(), new_id, srow['titlu'], srow['ordine'], now)
        )
    return new_id

# ---------------------------------------------------------------------------
# Project tasks CRUD
# ---------------------------------------------------------------------------

@tasks_bp.route('/api/proiecte/<project_id>/tasks', methods=['GET'])
@login_required
def get_tasks(project_id):
    conn = get_db()
    cursor = conn.cursor()

    # 1) Fetch all tasks for this project (single query).
    cursor.execute('''
        SELECT t.* FROM tasks t WHERE t.proiect_id = ?
        ORDER BY t.ordine ASC, t.created_at DESC
    ''', (project_id,))
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return jsonify([])

    task_ids = [r['id'] for r in rows]
    placeholders = ','.join('?' * len(task_ids))

    # 2) Batch-fetch subtask counts (one query for all tasks).
    cursor.execute(f'''
        SELECT task_id,
               COUNT(*) AS subtask_total,
               SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS subtask_done
        FROM task_subtasks
        WHERE task_id IN ({placeholders})
        GROUP BY task_id
    ''', task_ids)
    subtask_map = {}
    for r in cursor.fetchall():
        subtask_map[r['task_id']] = {'subtask_total': r['subtask_total'],
                                      'subtask_done': r['subtask_done']}

    conn.close()

    # 4) Merge results in Python.
    result = []
    for row in rows:
        d = row_to_dict(row)
        sc = subtask_map.get(d['id'], {})
        d['subtask_total'] = sc.get('subtask_total', 0)
        d['subtask_done'] = sc.get('subtask_done', 0)
        result.append(d)

    return jsonify(result)


@tasks_bp.route('/api/proiecte/<project_id>/tasks', methods=['POST'])
@login_required
def create_task(project_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    task_id = data.get('id') or generate_uuid()

    # Get max ordine for this project
    cursor.execute('SELECT MAX(ordine) as max_ordine FROM tasks WHERE proiect_id = ?', (project_id,))
    result = cursor.fetchone()
    max_ordine = result['max_ordine'] if result and result['max_ordine'] is not None else 0

    cursor.execute('''
        INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta,
                           data_finalizare, ordine, created_at, descriere, recurenta, updated_at,
                           ordine_agenda, data_start, progres, is_milestone)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        task_id,
        project_id,
        data.get('titlu', ''),
        data.get('status', 'to_do'),
        data.get('data_scadenta', ''),
        data.get('data_finalizare', ''),
        max_ordine + 1,
        now,
        data.get('descriere', ''),
        data.get('recurenta', ''),
        now,
        data.get('ordine_agenda', 0),
        data.get('data_start', ''),
        data.get('progres', 0),
        1 if data.get('is_milestone') else 0
    ))

    conn.commit()
    conn.close()

    return jsonify({'id': task_id}), 201


@tasks_bp.route('/api/tasks/<task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    existing = cursor.fetchone()
    if existing is None:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    old_status = existing['status']

    # Tranzitia la 'done' e atomica (WHERE status != 'done'): doua PUT-uri
    # concurente (dublu-click / 2 workere) nu mai spawneaza doua recurente.
    transitioned_to_done = False
    if data.get('status') == 'done' and old_status != 'done':
        cursor.execute("UPDATE tasks SET status = 'done' WHERE id = ? AND status != 'done'", (task_id,))
        transitioned_to_done = cursor.rowcount == 1

    cursor.execute('''
        UPDATE tasks SET
            titlu = COALESCE(?, titlu),
            status = COALESCE(?, status),
            data_scadenta = COALESCE(?, data_scadenta),
            data_finalizare = COALESCE(?, data_finalizare),
            ordine = COALESCE(?, ordine),
            descriere = COALESCE(?, descriere),
            recurenta = COALESCE(?, recurenta),
            ordine_agenda = COALESCE(?, ordine_agenda),
            data_start = COALESCE(?, data_start),
            progres = COALESCE(?, progres),
            is_milestone = COALESCE(?, is_milestone),
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('titlu'),
        data.get('status'),
        data.get('data_scadenta'),
        data.get('data_finalizare'),
        data.get('ordine'),
        data.get('descriere'),
        data.get('recurenta'),
        data.get('ordine_agenda'),
        data.get('data_start'),
        data.get('progres'),
        (1 if data.get('is_milestone') else 0) if data.get('is_milestone') is not None else None,
        datetime.now().isoformat(),
        task_id
    ))

    # A recurring task just completed -> spawn the next occurrence.
    spawned_id = None
    next_scad = None
    if transitioned_to_done and (existing['recurenta'] or '').strip():
        recurenta = existing['recurenta'].strip()
        spawned_id = _spawn_recurring_task(cursor, existing, recurenta)
        next_scad = _next_recurrence_date(existing['data_scadenta'] or '', recurenta)

    conn.commit()
    conn.close()

    resp = {'message': 'Task updated'}
    if spawned_id:
        resp['recurring_spawned'] = spawned_id
        resp['recurring_next'] = next_scad
    return jsonify(resp)


@tasks_bp.route('/api/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM task_subtasks WHERE task_id = ?', (task_id,))
        cursor.execute('DELETE FROM task_dependencies WHERE predecessor_id = ? OR successor_id = ?', (task_id, task_id))
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify({'message': 'Task deleted'})
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Task subtasks (lightweight checklist under a task)
# ---------------------------------------------------------------------------

@tasks_bp.route('/api/tasks/<task_id>/subtasks', methods=['GET'])
@login_required
def get_subtasks(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM task_subtasks WHERE task_id = ? ORDER BY ordine ASC, created_at ASC', (task_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(r) for r in rows])


@tasks_bp.route('/api/tasks/<task_id>/subtasks', methods=['POST'])
@login_required
def create_subtask(task_id):
    data = get_json_or_400()
    titlu = (data.get('titlu') or '').strip()
    if not titlu:
        return jsonify({'error': 'Titlu required'}), 400
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT COALESCE(MAX(ordine), -1) + 1 FROM task_subtasks WHERE task_id = ?', (task_id,))
        next_ordine = cursor.fetchone()[0]
        sid = generate_uuid()
        cursor.execute(
            'INSERT INTO task_subtasks (id, task_id, titlu, done, ordine, created_at) VALUES (?, ?, ?, 0, ?, ?)',
            (sid, task_id, titlu, next_ordine, datetime.now().isoformat())
        )
        conn.commit()
        return jsonify({'id': sid}), 201
    finally:
        conn.close()


@tasks_bp.route('/api/subtasks/<subtask_id>', methods=['PUT'])
@login_required
def update_subtask(subtask_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE task_subtasks SET titlu = COALESCE(?, titlu), done = COALESCE(?, done) WHERE id = ?',
        (data.get('titlu'), data.get('done'), subtask_id)
    )
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@tasks_bp.route('/api/subtasks/<subtask_id>', methods=['DELETE'])
@login_required
def delete_subtask(subtask_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM task_subtasks WHERE id = ?', (subtask_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Subtask not found'}), 404
        return jsonify({'ok': True})
    finally:
        conn.close()

# ---------------------------------------------------------------------------
# Global tasks CRUD
# ---------------------------------------------------------------------------

# Sferele taskurilor globale. Lipsa parametrului = 'munca' (fail-closed: un
# consumator neactualizat — Cowork, un client vechi — vede exact ce vedea inainte
# de v38; personalul e opt-in explicit). Valoare necunoscuta = 400, nu coercitie:
# aceeasi filosofie ca norm_date — nu accepta tacut ce nu poti citi.
SFERE = ('munca', 'personal')


def _sfera_or_none(value):
    """Valideaza o sfera primita din request. Intoarce sfera sau None daca e invalida."""
    return value if value in SFERE else None


# ORA UNUI TASK (v41). Acceptata la intrare in formele pe care le scrie mana —
# „9:00", „09:00", „9.00" — si stocata INTOTDEAUNA ca 'HH:MM' pe 24 de ore.
# Normalizarea e la SCRIERE, nu la citire, din acelasi motiv ca `utils.norm_date`:
# o valoare pe care n-o poti citi cu o singura regula nu trebuie sa intre in baza.
_RE_ORA = re.compile(r'^(\d{1,2})[:.](\d{2})$')


def norm_ora(value):
    """None = neatins (COALESCE il lasa cum era). '' = scoate ora. 'HH:MM' = pune-o.

    TREI rezultate, nu doua, si de asta nu e un simplu validator: `PUT` foloseste
    `COALESCE(?, ora)`, deci „nu trimite nimic" si „sterge ce era" trebuie sa arate
    diferit — `None` si `''`. Aceeasi convenţie ca `data_scadenta`, care se goleste
    tot cu `''` (vezi `setTermenData` in frontend).

    Arunca `ValueError` pe orice altceva: o ora care nu se poate citi n-are voie sa
    ajunga in coloana, fiindca de acolo o ia interfata ca text si o afiseaza ca atare.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return ''
    m = _RE_ORA.match(s)
    if not m:
        raise ValueError('ora invalidă (format acceptat: HH:MM)')
    h, mi = int(m.group(1)), int(m.group(2))
    if h > 23 or mi > 59:
        raise ValueError('ora invalidă (0–23 : 0–59)')
    return '%02d:%02d' % (h, mi)


@tasks_bp.route('/api/global-tasks', methods=['GET'])
@login_required
def get_global_tasks():
    # `toate` intoarce AMBELE sfere intr-un singur raspuns (fiecare rand isi
    # poarta `sfera`), ca /tasks sa comute Munca/Personal instant, din memorie —
    # inainte fiecare comutare astepta un dus-intors cu serverul, iar Ion o
    # simtea ca „deficienta" pe telefon. Implicitul ramane 'munca', pentru
    # consumatorii vechi (Cowork, scripturi).
    sfera = request.args.get('sfera') or 'munca'
    if sfera != 'toate' and _sfera_or_none(sfera) is None:
        return jsonify({'error': "sfera invalidă (acceptat: 'munca', 'personal' sau 'toate')"}), 400

    conn = get_db()
    cursor = conn.cursor()

    status = request.args.get('status')

    categorie = request.args.get('categorie')
    arhiva = request.args.get('arhiva')

    # 1) Fetch the global tasks (single query, no correlated subqueries).
    if sfera == 'toate':
        query = 'SELECT g.* FROM global_tasks g WHERE 1=1'
        params = []
    else:
        query = 'SELECT g.* FROM global_tasks g WHERE g.sfera = ?'
        params = [sfera]

    if arhiva == 'true':
        query += " AND status = 'done'"
    else:
        query += " AND status != 'done'"

    if status and arhiva != 'true':
        query += ' AND status = ?'
        params.append(status)
    if categorie:
        query += ' AND categorie = ?'
        params.append(categorie)

    query += ' ORDER BY created_at DESC'

    cursor.execute(query, params)
    rows = cursor.fetchall()
    if not rows:
        conn.close()
        return jsonify([])

    task_ids = [r['id'] for r in rows]
    placeholders = ','.join('?' * len(task_ids))

    # 2) Batch-fetch subtask counts (one query for all tasks).
    cursor.execute(f'''
        SELECT task_id,
               COUNT(*) AS subtask_total,
               SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS subtask_done
        FROM task_subtasks
        WHERE task_id IN ({placeholders})
        GROUP BY task_id
    ''', task_ids)
    subtask_map = {}
    for r in cursor.fetchall():
        subtask_map[r['task_id']] = {'subtask_total': r['subtask_total'],
                                      'subtask_done': r['subtask_done']}

    conn.close()

    # 4) Merge results in Python — response shape identical to the old
    #    correlated-subquery version (same keys, same 0 defaults).
    result = []
    for row in rows:
        d = row_to_dict(row)
        sc = subtask_map.get(d['id'], {})
        d['subtask_total'] = sc.get('subtask_total', 0)
        d['subtask_done'] = sc.get('subtask_done', 0)
        result.append(d)

    return jsonify(result)


@tasks_bp.route('/api/global-tasks', methods=['POST'])
@login_required
def create_global_task():
    data = get_json_or_400()
    sfera = data.get('sfera') or 'munca'
    if _sfera_or_none(sfera) is None:
        return jsonify({'error': "sfera invalidă (acceptat: 'munca' sau 'personal')"}), 400
    try:
        ora = norm_ora(data.get('ora')) or ''
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    task_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO global_tasks (id, titlu, descriere, status, categorie, sfera,
                                  data_scadenta, data_finalizare, created_at, updated_at, recurenta,
                                  ordine_agenda, ora)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        task_id,
        data.get('titlu', ''),
        data.get('descriere', ''),
        data.get('status', 'to_do'),
        data.get('categorie', 'General'),
        sfera,
        data.get('data_scadenta', ''),
        data.get('data_finalizare', ''),
        now,
        now,
        data.get('recurenta', ''),
        data.get('ordine_agenda', 0),
        ora
    ))

    conn.commit()
    conn.close()

    return jsonify({'id': task_id}), 201


@tasks_bp.route('/api/global-tasks/<task_id>', methods=['GET'])
@login_required
def get_global_task(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM global_tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(row_to_dict(row))


@tasks_bp.route('/api/global-tasks/<task_id>', methods=['PUT'])
@login_required
def update_global_task(task_id):
    data = get_json_or_400()
    # Patch de sfera permis (portita API pentru un task creat in sfera gresita);
    # fara UI de mutare deocamdata. None = neatins (COALESCE).
    if data.get('sfera') is not None and _sfera_or_none(data.get('sfera')) is None:
        return jsonify({'error': "sfera invalidă (acceptat: 'munca' sau 'personal')"}), 400
    try:
        ora = norm_ora(data.get('ora'))
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM global_tasks WHERE id = ?', (task_id,))
    existing = cursor.fetchone()
    if existing is None:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    old_status = existing['status']
    now = datetime.now().isoformat()

    # Tranzitie atomica la 'done' — vezi update_task (guard anti-dublu-spawn).
    transitioned_to_done = False
    if data.get('status') == 'done' and old_status != 'done':
        cursor.execute("UPDATE global_tasks SET status = 'done' WHERE id = ? AND status != 'done'", (task_id,))
        transitioned_to_done = cursor.rowcount == 1

    cursor.execute('''
        UPDATE global_tasks SET
            titlu = COALESCE(?, titlu),
            descriere = COALESCE(?, descriere),
            status = COALESCE(?, status),
            categorie = COALESCE(?, categorie),
            data_scadenta = COALESCE(?, data_scadenta),
            data_finalizare = COALESCE(?, data_finalizare),
            recurenta = COALESCE(?, recurenta),
            ordine_agenda = COALESCE(?, ordine_agenda),
            sfera = COALESCE(?, sfera),
            ora = COALESCE(?, ora),
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('titlu'),
        data.get('descriere'),
        data.get('status'),
        data.get('categorie'),
        data.get('data_scadenta'),
        data.get('data_finalizare'),
        data.get('recurenta'),
        data.get('ordine_agenda'),
        data.get('sfera'),
        ora,
        now,
        task_id
    ))

    # A recurring daily task just completed -> spawn the next occurrence.
    spawned_id = None
    next_scad = None
    if transitioned_to_done and (existing['recurenta'] or '').strip():
        recurenta = existing['recurenta'].strip()
        spawned_id = _spawn_recurring_global_task(cursor, existing, recurenta)
        next_scad = _next_recurrence_date(existing['data_scadenta'] or '', recurenta)

    conn.commit()
    conn.close()

    resp = {'message': 'Task updated'}
    if spawned_id:
        resp['recurring_spawned'] = spawned_id
        resp['recurring_next'] = next_scad
    return jsonify(resp)


@tasks_bp.route('/api/global-tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_global_task(task_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        # Clean up orphan subtasks: task_subtasks has no FK so DELETE on global_tasks
        # doesn't cascade. Sessions cascade via FK ON DELETE CASCADE (v11).
        cursor.execute('DELETE FROM task_subtasks WHERE task_id = ?', (task_id,))
        cursor.execute('DELETE FROM global_tasks WHERE id = ?', (task_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify({'message': 'Task deleted'})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Agenda — "Astazi", boardul cu care Ion isi incepe ziua
#
# UN TASK ARE O SINGURA DATA (v33). Ion: „mutarea este practic un deadline (…)
# trebuie sa fie adaugat ca deadline pur, sa nu mai dublam atat notiunile."
# Deci boardul de azi = ce e scadent azi SAU restant. A pune un task pe azi
# inseamna a-i da termenul de azi; a-l muta pe alta zi ii muta termenul.
# Boardul uneste taskurile globale (tip='global') si cele de proiect ('proiect').
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _resolve_today():
    """Local 'today' from the client (?today=YYYY-MM-DD); SQLite date('now') is
    UTC and can be off near midnight. Falls back to the server's local date."""
    t = (request.args.get('today') or '').strip()
    if _DATE_RE.match(t):
        return t
    return datetime.now().strftime('%Y-%m-%d')


def _agenda_item(d, tip, today):
    """Normalize a task row (dict) into the flat shape the board consumes."""
    scad = (d.get('data_scadenta') or '').strip()[:10]
    return {
        'tip': tip,
        'id': d['id'],
        'titlu': d.get('titlu') or '',
        'status': d.get('status') or 'to_do',
        'data_scadenta': d.get('data_scadenta') or '',
        'data_finalizare': d.get('data_finalizare') or '',
        'ordine_agenda': d.get('ordine_agenda') or 0,
        'recurenta': d.get('recurenta') or '',
        'categorie': (d.get('categorie') or '') if tip == 'global' else '',
        'sfera': (d.get('sfera') or 'munca') if tip == 'global' else 'munca',
        'proiect_id': d.get('proiect_id') if tip == 'proiect' else None,
        'proiect_nume': d.get('proiect_nume') if tip == 'proiect' else None,
        'is_scadent_azi': bool(scad) and scad == today,
        'is_restant': bool(scad) and scad < today,
    }


# Ce intra pe boardul de azi: taskurile deschise scadente AZI sau RESTANTE. Cu o
# singura data, regula are o singura linie — inainte avea trei ramuri si o exceptie,
# fiindca planul si termenul se puteau contrazice. Recurentele viitoare raman
# ascunse, ca o ocurenta abia generata sa nu apara inainte de vreme.
_AGENDA_WHERE = '''
        {alias}.status != 'done'
        AND {alias}.data_scadenta IS NOT NULL AND TRIM({alias}.data_scadenta) <> ''
        AND date({alias}.data_scadenta) <= date(:today)
        AND NOT (
            {alias}.recurenta IS NOT NULL AND TRIM({alias}.recurenta) <> ''
            AND {alias}.data_scadenta IS NOT NULL AND date({alias}.data_scadenta) > date(:today)
        )
'''


@tasks_bp.route('/api/agenda/today', methods=['GET'])
@login_required
def get_agenda_today():
    today = _resolve_today()
    conn = get_db()
    cursor = conn.cursor()

    # Sfera sta LITERAL la fiecare call-site, nu in _AGENDA_WHERE: un grep pe
    # "FROM global_tasks" trebuie sa arate decizia de sfera pe acelasi ecran.
    cursor.execute(
        "SELECT g.* FROM global_tasks g WHERE g.sfera = 'munca' AND " + _AGENDA_WHERE.format(alias='g'),
        {'today': today})
    items = [_agenda_item(row_to_dict(r), 'global', today) for r in cursor.fetchall()]

    # UN PROIECT INCHIS NU MAI TRIMITE NIMIC PE ACASA. Filtrul scria
    # `p.status != 'anulat'` — un status care NU MAI EXISTA din v31 (doua stari:
    # `pregatire` si `finalizat`), deci nu excludea absolut nimic. Aceeasi
    # conditie ca in `/api/plan`, cuvant cu cuvant: Planificatorul decisese deja
    # ca lucrarile incheiate ies din lumea planificarii, si nu se poate ca aceeasi
    # intrebare sa aiba doua raspunsuri pe doua rute care hranesc acelasi ecran.
    cursor.execute(
        '''SELECT t.*, p.nume AS proiect_nume
           FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
           WHERE p.status NOT IN ('anulat', 'finalizat') AND ''' + _AGENDA_WHERE.format(alias='t'),
        {'today': today})
    items += [_agenda_item(row_to_dict(r), 'proiect', today) for r in cursor.fetchall()]

    # Taskurile personale scadente azi/restante — cheie SEPARATA in raspuns, ca
    # boardul sa le randeze in sectiunea lor; randurile nu se amesteca niciodata.
    cursor.execute(
        "SELECT g.* FROM global_tasks g WHERE g.sfera = 'personal' AND " + _AGENDA_WHERE.format(alias='g'),
        {'today': today})
    personale = [_agenda_item(row_to_dict(r), 'global', today) for r in cursor.fetchall()]

    # Subtask counts, one query for every item on the board (same batch pattern as
    # /api/global-tasks). Without them the board could not show the "1/4" chip that
    # the task lists show, so the same task looked different depending on the page.
    ids = [d['id'] for d in items + personale if d.get('id')]
    if ids:
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f'''
            SELECT task_id,
                   COUNT(*) AS subtask_total,
                   SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS subtask_done
            FROM task_subtasks
            WHERE task_id IN ({placeholders})
            GROUP BY task_id
        ''', ids)
        counts = {r['task_id']: (r['subtask_total'], r['subtask_done']) for r in cursor.fetchall()}
        for d in items + personale:
            total, done = counts.get(d['id'], (0, 0))
            d['subtask_total'] = total
            d['subtask_done'] = done or 0

    conn.close()

    # Restante first, then by board order (unordered = 0 sinks to the bottom), then title.
    items.sort(key=lambda d: (
        0 if d['is_restant'] else 1,
        d['ordine_agenda'] if d['ordine_agenda'] else 1_000_000,
        (d['titlu'] or '').lower(),
    ))
    # Sectiunea personala nu are reordonare — restante primele, apoi alfabetic.
    personale.sort(key=lambda d: (0 if d['is_restant'] else 1, (d['titlu'] or '').lower()))
    return jsonify({'today': today, 'items': items, 'personale': personale})


@tasks_bp.route('/api/agenda/candidates', methods=['GET'])
@login_required
def get_agenda_candidates():
    """Not-done tasks (global + project) that can be added to today, excluding
    those already planned for today. Optional ?q= title search."""
    today = _resolve_today()
    q = (request.args.get('q') or '').strip()
    conn = get_db()
    cursor = conn.cursor()

    # Candidatii = ce NU e deja pe board. Cu o singura data asta inseamna: fara
    # termen, sau cu termen in viitor. Restantele sunt deja pe board.
    # Doar munca: pickerul alimenteaza boardul de MUNCA de pe Acasa.
    gq = '''SELECT g.* FROM global_tasks g
            WHERE g.sfera = 'munca' AND g.status != 'done'
              AND (g.data_scadenta IS NULL OR TRIM(g.data_scadenta) = ''
                   OR date(g.data_scadenta) > date(:today))
              AND NOT (
                g.recurenta IS NOT NULL AND TRIM(g.recurenta) <> ''
                AND g.data_scadenta IS NOT NULL AND date(g.data_scadenta) > date(:today)
              )'''
    gp = {'today': today}
    if q:
        gq += ' AND g.titlu LIKE :q'
        gp['q'] = f'%{q}%'
    gq += ' ORDER BY g.titlu COLLATE NOCASE LIMIT 100'
    cursor.execute(gq, gp)
    items = [_agenda_item(row_to_dict(r), 'global', today) for r in cursor.fetchall()]

    # Ion, 2026-08-21: „imi apar acasa ca optiune de adaugare si taskuri din
    # proiecte finalizate." Cauza: `p.status != 'anulat'`, un status scos in v31 —
    # deci filtrul se citea ca o precautie si nu excludea nimic. Un task ramas
    # deschis intr-o lucrare incheiata nu e o optiune: nu-l poti PLANIFICA, e o
    # urma de curatat din pagina proiectului.
    tq = '''SELECT t.*, p.nume AS proiect_nume
            FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
            WHERE t.status != 'done' AND p.status NOT IN ('anulat', 'finalizat')
              AND (t.data_scadenta IS NULL OR TRIM(t.data_scadenta) = ''
                   OR date(t.data_scadenta) > date(:today))
              AND NOT (
                t.recurenta IS NOT NULL AND TRIM(t.recurenta) <> ''
                AND t.data_scadenta IS NOT NULL AND date(t.data_scadenta) > date(:today)
              )'''
    tp = {'today': today}
    if q:
        tq += ' AND t.titlu LIKE :q'
        tp['q'] = f'%{q}%'
    tq += ' ORDER BY t.titlu COLLATE NOCASE LIMIT 100'
    cursor.execute(tq, tp)
    items += [_agenda_item(row_to_dict(r), 'proiect', today) for r in cursor.fetchall()]

    conn.close()
    return jsonify({'today': today, 'items': items})


@tasks_bp.route('/api/agenda/reorder', methods=['POST'])
@login_required
def reorder_agenda():
    """Persist the board order for a mixed list of global + project tasks.
    Body: {"order": [{"tip": "global"|"proiect", "id": "..."}, ...]}.
    Writes ordine_agenda = position+1 (1-based, so 0 stays 'unordered')."""
    data = get_json_or_400()
    order = data.get('order') or []
    conn = get_db()
    cursor = conn.cursor()
    try:
        for i, item in enumerate(order):
            tip = (item or {}).get('tip')
            tid = (item or {}).get('id')
            if not tid:
                continue
            if tip == 'global':
                cursor.execute('UPDATE global_tasks SET ordine_agenda = ? WHERE id = ?', (i + 1, tid))
            elif tip == 'proiect':
                cursor.execute('UPDATE tasks SET ordine_agenda = ? WHERE id = ?', (i + 1, tid))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.exception("reorder_agenda a esuat: %s", e)
        return jsonify({'error': 'Reordonarea a esuat.'}), 500
    conn.close()
    return jsonify({'message': 'ok', 'count': len(order)})


def _span_intersects(d1, d2, start_s, end_s):
    """True if the day-span [min(d1,d2), max(d1,d2)] intersects the window
    [start_s, end_s) (all 'YYYY-MM-DD'; end exclusive). Empty dates ignored;
    a single present date is treated as a 1-day span."""
    ds = [x for x in ((d1 or '')[:10], (d2 or '')[:10]) if x]
    if not ds:
        return False
    lo, hi = min(ds), max(ds)
    return lo < end_s and hi >= start_s


@tasks_bp.route('/api/plan', methods=['GET'])
@login_required
def get_plan():
    """Operational 14-day planner ("Planificator"): project lanes (each with its
    overall interval data_incepere -> ultima perioada planificata) containing their
    tasks, plus a "Globale" lane. A task appears where its span
    data_scadenta cade in fereastra. Din v33 taskul are o singura data, deci
    fiecare task e un semn de o zi, nu un interval — intervalul plan->termen era
    o distinctie pe care nimeni n-o folosea (3 randuri din 37, toate de o zi).

    Deadline-ul de proiect a plecat in v30 — nu se lua nimeni dupa el. Capatul
    din dreapta al benzii e acum ultima zi pe care chiar ai planificat-o."""
    today = _resolve_today()
    start = (request.args.get('start') or '').strip()
    if not _DATE_RE.match(start):
        start = today
    try:
        days = int(request.args.get('days') or 14)
    except (TypeError, ValueError):
        days = 14
    days = max(1, min(days, 370))  # up to ~1 an; UI merge pana la 6 luni (180)
    show_done = (request.args.get('done') or '').lower() in ('1', 'true', 'yes')
    start_d = datetime.strptime(start, '%Y-%m-%d').date()
    start_s = start_d.isoformat()
    end_s = (start_d + timedelta(days=days)).isoformat()  # exclusive

    # A task belongs in the window if its plan->due span intersects it; a finished
    # task with no plan/due can still qualify via its completion date.
    def _in_window(item):
        if _span_intersects(item['data_scadenta'], item['data_scadenta'], start_s, end_s):
            return True
        fin = (item.get('data_finalizare') or '')[:10]
        return bool(fin) and start_s <= fin < end_s

    # CE A SCAPAT INAINTEA FERESTREI NU MAI DISPARE.
    # Fereastra porneste mereu din ziua de azi, deci un task cu termen ieri cadea
    # inaintea ei: `_in_window` il respingea, iar in sertarul „fara termen" nu intra
    # (acolo intra doar cele fara data). Practic Planificatorul nu putea arata
    # restantul — iar regulile scrise pentru el (`.bar.urgent`, `.mt-pin.urgent`)
    # nu se puteau aplica niciodata. Ele nu tin de fereastra, deci nu primesc
    # geometrie: se desenea intr-o coloana proprie, lipita la stanga grilei.
    def _restant(item):
        scad = (item.get('data_scadenta') or '')[:10]
        return bool(scad) and scad < start_s and item.get('status') != 'done'

    conn = get_db()
    cursor = conn.cursor()

    status_clause = '' if show_done else "{alias}.status != 'done' AND "

    # Candidate project lanes (skip cancelled / finished).
    cursor.execute(
        "SELECT id, nume, tip, status FROM proiecte "
        "WHERE status NOT IN ('anulat', 'finalizat')")
    projects = [row_to_dict(r) for r in cursor.fetchall()]

    # Project tasks (exclude future recurrences, same idiom as the agenda).
    cursor.execute(
        '''SELECT t.* FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
           WHERE ''' + status_clause.format(alias='t') + '''p.status NOT IN ('anulat', 'finalizat')
             AND NOT (
               t.recurenta IS NOT NULL AND TRIM(t.recurenta) <> ''
               AND t.data_scadenta IS NOT NULL AND date(t.data_scadenta) > date(:today)
             )''',
        {'today': today})
    tasks_by_project = {}
    restante_by_project = {}
    for r in cursor.fetchall():
        item = _agenda_item(row_to_dict(r), 'proiect', today)
        if _in_window(item):
            tasks_by_project.setdefault(item['proiect_id'], []).append(item)
        elif _restant(item):
            restante_by_project.setdefault(item['proiect_id'], []).append(item)

    def _task_sort_key(t):
        cand = [x for x in ((t['data_scadenta'] or '')[:10],) if x]
        return (min(cand) if cand else '9999-99-99', (t['titlu'] or '').lower())

    # Implementation periods (Site / Sediu EGB) per project, for lane bands.
    impl_by_project = {}
    proj_ids = [p['id'] for p in projects]
    if proj_ids:
        ph = ','.join('?' * len(proj_ids))
        cursor.execute(f'SELECT * FROM implementari WHERE proiect_id IN ({ph})', proj_ids)
        for r in [row_to_dict(x) for x in cursor.fetchall()]:
            # `faza` merge la client, nu doar `locatie`: Planificatorul are nevoie
            # de ea ca sa nu numere o zi de PREGATIRE ca etapa de implementare —
            # o astfel de zi nu rupe golul de pregatire, se deseneaza peste el.
            impl_by_project.setdefault(r['proiect_id'], []).append({
                'id': r['id'], 'data_start': (r.get('data_start') or '')[:10],
                'data_sfarsit': (r.get('data_sfarsit') or '')[:10],
                'locatie': r.get('locatie') or 'site', 'eticheta': r.get('eticheta') or '',
                'faza': r.get('faza') or 'implementare'})

    lanes = []
    for proj in projects:
        pid = proj['id']
        ptasks = sorted(tasks_by_project.get(pid, []), key=_task_sort_key)
        # Banda proiectului se intinde intre PERIOADE, nu de la un camp scris cu
        # mana: `data_incepere` a plecat in v36 (5 randuri din 18, si dubla prima
        # perioada). Capatul de sus e prima zi planificata, cel de jos ultima —
        # niciunul nu e un deadline impus (vezi v30).
        toate_impl = impl_by_project.get(pid, [])
        inc = min((im.get('data_start') or '' for im in toate_impl if im.get('data_start')),
                  default='')
        ultima = max((im.get('data_sfarsit') or im.get('data_start') or ''
                      for im in toate_impl), default='')
        band = _span_intersects(inc, ultima, start_s, end_s)
        pimpl = [im for im in toate_impl
                 if _span_intersects(im['data_start'], im['data_sfarsit'], start_s, end_s)]
        prestante = sorted(restante_by_project.get(pid, []), key=_task_sort_key)
        if not ptasks and not band and not pimpl and not prestante:
            continue
        lanes.append({
            'tip': 'proiect',
            'id': pid,
            'nume': proj.get('nume') or '',
            'tip_proiect': proj.get('tip') or '',
            'status': proj.get('status') or '',
            'prima_zi': inc,
            'ultima_zi': ultima,
            'tasks': ptasks,
            'restante': prestante,
            'implementari': pimpl,
        })

    # Global tasks lane. Doar munca: Planificatorul e suprafata de planificare
    # a MUNCII; personalul cu termen traieste pe Acasa si in vederea lui de pe /tasks.
    cursor.execute(
        '''SELECT g.* FROM global_tasks g
           WHERE g.sfera = 'munca' AND ''' + status_clause.format(alias='g') + '''NOT (
               g.recurenta IS NOT NULL AND TRIM(g.recurenta) <> ''
               AND g.data_scadenta IS NOT NULL AND date(g.data_scadenta) > date(:today)
             )''',
        {'today': today})
    gtasks = []
    grestante = []
    for r in cursor.fetchall():
        item = _agenda_item(row_to_dict(r), 'global', today)
        if _in_window(item):
            gtasks.append(item)
        elif _restant(item):
            grestante.append(item)
    if gtasks or grestante:
        lanes.append({
            'tip': 'global', 'id': '__global__', 'nume': 'Globale',
            'tip_proiect': '', 'status': '', 'prima_zi': '', 'ultima_zi': '',
            'tasks': sorted(gtasks, key=_task_sort_key),
            'restante': sorted(grestante, key=_task_sort_key), 'implementari': [],
        })

    # Backlog: open tasks with NO plan and NO deadline — nowhere to place on the
    # timeline, so they surface in a side rail from which they can be scheduled.
    def _backlog_item(d, tip):
        return {
            'tip': tip, 'id': d['id'], 'titlu': d.get('titlu') or '',
                'categorie': (d.get('categorie') or '') if tip == 'global' else '',
            'proiect_id': d.get('proiect_id') if tip == 'proiect' else None,
            'proiect_nume': d.get('proiect_nume') if tip == 'proiect' else None,
        }

    undated = '''({a}.data_scadenta IS NULL OR TRIM({a}.data_scadenta) = '')'''
    cursor.execute(
        '''SELECT t.*, p.nume AS proiect_nume FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
           WHERE t.status != 'done' AND p.status NOT IN ('anulat', 'finalizat')
             AND ''' + undated.format(a='t') + '''
           ORDER BY t.titlu COLLATE NOCASE LIMIT 300''')
    backlog = [_backlog_item(row_to_dict(r), 'proiect') for r in cursor.fetchall()]
    cursor.execute(
        '''SELECT g.* FROM global_tasks g WHERE g.sfera = 'munca' AND g.status != 'done'
             AND ''' + undated.format(a='g') + '''
           ORDER BY g.titlu COLLATE NOCASE LIMIT 300''')
    backlog += [_backlog_item(row_to_dict(r), 'global') for r in cursor.fetchall()]

    # Numarul de subtaskuri, o singura interogare pentru toate randurile din plan
    # (acelasi tipar ca la /api/global-tasks si /api/agenda). Fara el, chipul „1/4"
    # ar lipsi tocmai in Planificator, deci acelasi task ar arata altfel decat in
    # celelalte trei liste.
    toate = [x for l in lanes for x in l.get('tasks', []) + l.get('restante', [])] + backlog
    ids = [x['id'] for x in toate if x.get('id')]
    if ids:
        ph = ','.join('?' * len(ids))
        cursor.execute(f'''
            SELECT task_id,
                   COUNT(*) AS subtask_total,
                   SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS subtask_done
            FROM task_subtasks
            WHERE task_id IN ({ph})
            GROUP BY task_id
        ''', ids)
        counts = {r['task_id']: (r['subtask_total'], r['subtask_done']) for r in cursor.fetchall()}
        for x in toate:
            total, done = counts.get(x['id'], (0, 0))
            x['subtask_total'] = total
            x['subtask_done'] = done or 0

    conn.close()

    # Lane order: projects by earliest in-window activity, Globale last. Restantele
    # NU intra in cheie: fiind toate inaintea ferestrei, ar da acelasi minim tuturor
    # benzilor care au vreuna si ar rupe ordinea celor care chiar au treaba maine.
    def _lane_key(l):
        dates = []
        for t in l['tasks']:
            for k in ('data_scadenta',):
                v = (t.get(k) or '')[:10]
                if v:
                    dates.append(v)
        if l['prima_zi']:
            dates.append(l['prima_zi'])
        return (1 if l['tip'] == 'global' else 0, min(dates) if dates else '9999-99-99')

    lanes.sort(key=_lane_key)
    return jsonify({'start': start_s, 'days': days, 'today': today, 'lanes': lanes, 'backlog': backlog})

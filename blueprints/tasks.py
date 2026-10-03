import calendar
import re
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from database import get_db, row_to_dict
from utils import generate_uuid, login_required, get_json_or_400, id_ocupat as _id_ocupat

tasks_bp = Blueprint('tasks', __name__)

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

    cursor.execute('SELECT 1 FROM proiecte WHERE id = ?', (project_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Proiect inexistent'}), 404
    if data.get('id'):
        ocupat = _id_ocupat(cursor, 'tasks', task_id)
        if ocupat:
            conn.close()
            return ocupat

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
        # Parintele e un task de proiect sau unul global. task_subtasks n-are cheie straina
        # (a pierdut-o ca sa le primeasca pe amandoua), deci un parinte lipsa se prinde aici,
        # altfel subtaskul ar ramane orfan, nevazut nicaieri.
        cursor.execute('SELECT 1 FROM tasks WHERE id = ? UNION ALL SELECT 1 FROM global_tasks WHERE id = ?',
                       (task_id, task_id))
        if cursor.fetchone() is None:
            return jsonify({'error': 'Task inexistent'}), 404
        sid = data.get('id') or generate_uuid()
        if data.get('id'):
            ocupat = _id_ocupat(cursor, 'task_subtasks', sid)
            if ocupat:
                return ocupat
        cursor.execute('SELECT COALESCE(MAX(ordine), -1) + 1 FROM task_subtasks WHERE task_id = ?', (task_id,))
        next_ordine = cursor.fetchone()[0]
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
    if data.get('id'):
        ocupat = _id_ocupat(cursor, 'global_tasks', task_id)
        if ocupat:
            conn.close()
            return ocupat

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

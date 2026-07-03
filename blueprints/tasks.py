import calendar
import logging
import os
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

def _delete_task_attachments(cursor, column, task_id):
    """Remove attachment files from disk and their rows for a task being
    deleted. column: 'task_id' or 'global_task_id'."""
    cursor.execute(f'SELECT cale_locala FROM atasamente WHERE {column} = ?', (task_id,))
    for row in cursor.fetchall():
        try:
            if row['cale_locala'] and os.path.exists(row['cale_locala']):
                os.remove(row['cale_locala'])
        except OSError:
            pass
    cursor.execute(f'DELETE FROM atasamente WHERE {column} = ?', (task_id,))

def _next_recurrence_date(base_str, recurenta):
    """base_str: 'YYYY-MM-DD' (flatpickr format) or empty. Returns the next
    occurrence date as 'YYYY-MM-DD'. Falls back to today when base is unparsable."""
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
    return nxt.isoformat()


def _spawn_recurring_task(cursor, existing, recurenta):
    """Create the next occurrence of a recurring task that was just completed.
    Copies title/priority/description/recurrence and fresh (unchecked) subtasks.
    `existing` is the sqlite Row of the completed task. Returns the new id."""
    new_id = generate_uuid()
    now = datetime.now().isoformat()
    next_scad = _next_recurrence_date(existing['data_scadenta'] or '', recurenta)
    cursor.execute('SELECT MAX(ordine) FROM tasks WHERE proiect_id = ?', (existing['proiect_id'],))
    max_ordine = cursor.fetchone()[0] or 0
    # data_planificata / ordine_agenda are deliberately NOT copied: the next
    # occurrence is born unplanned and surfaces on the Astazi board later via its
    # future data_scadenta, not the moment the current one is completed.
    cursor.execute('''
        INSERT INTO tasks (id, proiect_id, titlu, status, prioritate, data_scadenta,
                           data_finalizare, ordine, created_at, descriere, recurenta, updated_at)
        VALUES (?, ?, ?, 'to_do', ?, ?, '', ?, ?, ?, ?, ?)
    ''', (new_id, existing['proiect_id'], existing['titlu'], existing['prioritate'],
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
    # data_planificata / ordine_agenda deliberately not copied (see _spawn_recurring_task).
    cursor.execute('''
        INSERT INTO global_tasks (id, titlu, descriere, prioritate, status, categorie,
                                  data_scadenta, data_finalizare, created_at, updated_at, recurenta)
        VALUES (?, ?, ?, ?, 'to_do', ?, ?, '', ?, ?, ?)
    ''', (new_id, existing['titlu'], existing['descriere'] or '', existing['prioritate'],
          existing['categorie'], next_scad, now, now, recurenta))
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

    # 3) Batch-fetch attachment counts (one query for all tasks).
    cursor.execute(f'''
        SELECT task_id, COUNT(*) AS atasamente_count
        FROM atasamente
        WHERE task_id IN ({placeholders})
        GROUP BY task_id
    ''', task_ids)
    att_map = {r['task_id']: r['atasamente_count'] for r in cursor.fetchall()}

    conn.close()

    # 4) Merge results in Python.
    result = []
    for row in rows:
        d = row_to_dict(row)
        sc = subtask_map.get(d['id'], {})
        d['subtask_total'] = sc.get('subtask_total', 0)
        d['subtask_done'] = sc.get('subtask_done', 0)
        d['atasamente_count'] = att_map.get(d['id'], 0)
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
        INSERT INTO tasks (id, proiect_id, titlu, status, prioritate, data_scadenta,
                           data_finalizare, ordine, created_at, descriere, recurenta, updated_at,
                           data_planificata, ordine_agenda)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        task_id,
        project_id,
        data.get('titlu', ''),
        data.get('status', 'to_do'),
        data.get('prioritate', 'normal'),
        data.get('data_scadenta', ''),
        data.get('data_finalizare', ''),
        max_ordine + 1,
        now,
        data.get('descriere', ''),
        data.get('recurenta', ''),
        now,
        data.get('data_planificata', ''),
        data.get('ordine_agenda', 0)
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
            prioritate = COALESCE(?, prioritate),
            data_scadenta = COALESCE(?, data_scadenta),
            data_finalizare = COALESCE(?, data_finalizare),
            ordine = COALESCE(?, ordine),
            descriere = COALESCE(?, descriere),
            recurenta = COALESCE(?, recurenta),
            data_planificata = COALESCE(?, data_planificata),
            ordine_agenda = COALESCE(?, ordine_agenda),
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('titlu'),
        data.get('status'),
        data.get('prioritate'),
        data.get('data_scadenta'),
        data.get('data_finalizare'),
        data.get('ordine'),
        data.get('descriere'),
        data.get('recurenta'),
        data.get('data_planificata'),
        data.get('ordine_agenda'),
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
        _delete_task_attachments(cursor, 'task_id', task_id)
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

@tasks_bp.route('/api/global-tasks', methods=['GET'])
@login_required
def get_global_tasks():
    conn = get_db()
    cursor = conn.cursor()

    status = request.args.get('status')
    prioritate = request.args.get('prioritate')
    categorie = request.args.get('categorie')
    arhiva = request.args.get('arhiva')

    # 1) Fetch the global tasks (single query, no correlated subqueries).
    query = 'SELECT g.* FROM global_tasks g WHERE 1=1'
    params = []

    if arhiva == 'true':
        query += " AND status = 'done'"
    else:
        query += " AND status != 'done'"

    if status and arhiva != 'true':
        query += ' AND status = ?'
        params.append(status)
    if prioritate:
        query += ' AND prioritate = ?'
        params.append(prioritate)
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

    # 3) Batch-fetch attachment counts (one query for all tasks).
    cursor.execute(f'''
        SELECT global_task_id, COUNT(*) AS atasamente_count
        FROM atasamente
        WHERE global_task_id IN ({placeholders})
        GROUP BY global_task_id
    ''', task_ids)
    att_map = {r['global_task_id']: r['atasamente_count'] for r in cursor.fetchall()}

    conn.close()

    # 4) Merge results in Python — response shape identical to the old
    #    correlated-subquery version (same keys, same 0 defaults).
    result = []
    for row in rows:
        d = row_to_dict(row)
        sc = subtask_map.get(d['id'], {})
        d['subtask_total'] = sc.get('subtask_total', 0)
        d['subtask_done'] = sc.get('subtask_done', 0)
        d['atasamente_count'] = att_map.get(d['id'], 0)
        result.append(d)

    return jsonify(result)


@tasks_bp.route('/api/global-tasks', methods=['POST'])
@login_required
def create_global_task():
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    task_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO global_tasks (id, titlu, descriere, prioritate, status, categorie,
                                  data_scadenta, data_finalizare, created_at, updated_at, recurenta,
                                  data_planificata, ordine_agenda)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        task_id,
        data.get('titlu', ''),
        data.get('descriere', ''),
        data.get('prioritate', 'Normal'),
        data.get('status', 'to_do'),
        data.get('categorie', 'General'),
        data.get('data_scadenta', ''),
        data.get('data_finalizare', ''),
        now,
        now,
        data.get('recurenta', ''),
        data.get('data_planificata', ''),
        data.get('ordine_agenda', 0)
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
            prioritate = COALESCE(?, prioritate),
            status = COALESCE(?, status),
            categorie = COALESCE(?, categorie),
            data_scadenta = COALESCE(?, data_scadenta),
            data_finalizare = COALESCE(?, data_finalizare),
            recurenta = COALESCE(?, recurenta),
            data_planificata = COALESCE(?, data_planificata),
            ordine_agenda = COALESCE(?, ordine_agenda),
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('titlu'),
        data.get('descriere'),
        data.get('prioritate'),
        data.get('status'),
        data.get('categorie'),
        data.get('data_scadenta'),
        data.get('data_finalizare'),
        data.get('recurenta'),
        data.get('data_planificata'),
        data.get('ordine_agenda'),
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
        _delete_task_attachments(cursor, 'global_task_id', task_id)
        cursor.execute('DELETE FROM global_tasks WHERE id = ?', (task_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Task not found'}), 404
        return jsonify({'message': 'Task deleted'})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Agenda — "Astazi" daily planner board (Home tab)
#
# Planning is a SEPARATE dimension from the deadline: data_planificata ("plan it
# for this day") never touches data_scadenta ("the deadline"). The board unifies
# global tasks (tip='global') and project tasks (tip='proiect') for a single day.
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
    plan = (d.get('data_planificata') or '').strip()[:10]
    scad = (d.get('data_scadenta') or '').strip()[:10]
    return {
        'tip': tip,
        'id': d['id'],
        'titlu': d.get('titlu') or '',
        'status': d.get('status') or 'to_do',
        'prioritate': d.get('prioritate') or '',
        'data_scadenta': d.get('data_scadenta') or '',
        'data_planificata': d.get('data_planificata') or '',
        'ordine_agenda': d.get('ordine_agenda') or 0,
        'recurenta': d.get('recurenta') or '',
        'categorie': (d.get('categorie') or '') if tip == 'global' else '',
        'proiect_id': d.get('proiect_id') if tip == 'proiect' else None,
        'proiect_nume': d.get('proiect_nume') if tip == 'proiect' else None,
        'is_planificat_azi': bool(plan) and plan == today,
        'is_restant': bool(plan) and plan < today,
        'is_scadent_azi': bool(scad) and scad == today,
    }


# Open tasks that belong on today's board: planned today, rolled over (planned in
# the past, still open) or due today. The due-today clause is a SUGGESTION that only
# applies when the task isn't explicitly planned for another day — so "move to
# tomorrow" (which sets data_planificata ahead) actually removes a due-today task
# from the board, instead of the deadline pinning it here. Future recurrences are
# hidden (same idiom as the dashboard) so a just-spawned next occurrence doesn't show.
_AGENDA_WHERE = '''
        {alias}.status != 'done'
        AND (
            date({alias}.data_planificata) = date(:today)
            OR (
                {alias}.data_planificata IS NOT NULL AND TRIM({alias}.data_planificata) <> ''
                AND date({alias}.data_planificata) < date(:today)
            )
            OR (
                date({alias}.data_scadenta) = date(:today)
                AND (
                    {alias}.data_planificata IS NULL OR TRIM({alias}.data_planificata) = ''
                    OR date({alias}.data_planificata) = date(:today)
                )
            )
        )
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

    cursor.execute(
        'SELECT g.* FROM global_tasks g WHERE ' + _AGENDA_WHERE.format(alias='g'),
        {'today': today})
    items = [_agenda_item(row_to_dict(r), 'global', today) for r in cursor.fetchall()]

    cursor.execute(
        '''SELECT t.*, p.nume AS proiect_nume
           FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
           WHERE p.status != 'anulat' AND ''' + _AGENDA_WHERE.format(alias='t'),
        {'today': today})
    items += [_agenda_item(row_to_dict(r), 'proiect', today) for r in cursor.fetchall()]

    conn.close()

    # Restante first, then by board order (unordered = 0 sinks to the bottom), then title.
    items.sort(key=lambda d: (
        0 if d['is_restant'] else 1,
        d['ordine_agenda'] if d['ordine_agenda'] else 1_000_000,
        (d['titlu'] or '').lower(),
    ))
    return jsonify({'today': today, 'items': items})


@tasks_bp.route('/api/agenda/candidates', methods=['GET'])
@login_required
def get_agenda_candidates():
    """Not-done tasks (global + project) that can be added to today, excluding
    those already planned for today. Optional ?q= title search."""
    today = _resolve_today()
    q = (request.args.get('q') or '').strip()
    conn = get_db()
    cursor = conn.cursor()

    # COALESCE(date(col),'') so unplanned (NULL/'') rows are kept; only today's are excluded.
    gq = '''SELECT g.* FROM global_tasks g
            WHERE g.status != 'done'
              AND COALESCE(date(g.data_planificata), '') <> date(:today)
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

    tq = '''SELECT t.*, p.nume AS proiect_nume
            FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
            WHERE t.status != 'done' AND p.status != 'anulat'
              AND COALESCE(date(t.data_planificata), '') <> date(:today)
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
    overall interval data_incepere->deadline) containing their tasks, plus a
    "Globale" lane. A task appears where its span data_planificata->data_scadenta
    intersects the window; tasks with only a deadline show as a single-day marker.
    No schema change — reuses the existing agenda planning semantics."""
    today = _resolve_today()
    start = (request.args.get('start') or '').strip()
    if not _DATE_RE.match(start):
        start = today
    try:
        days = int(request.args.get('days') or 14)
    except (TypeError, ValueError):
        days = 14
    days = max(1, min(days, 60))
    start_d = datetime.strptime(start, '%Y-%m-%d').date()
    start_s = start_d.isoformat()
    end_s = (start_d + timedelta(days=days)).isoformat()  # exclusive

    conn = get_db()
    cursor = conn.cursor()

    # Candidate project lanes (skip cancelled / finished).
    cursor.execute(
        "SELECT id, nume, tip, status, data_incepere, deadline FROM proiecte "
        "WHERE status NOT IN ('anulat', 'finalizat')")
    projects = [row_to_dict(r) for r in cursor.fetchall()]

    # Open project tasks (exclude future recurrences, same idiom as the agenda).
    cursor.execute(
        '''SELECT t.* FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
           WHERE t.status != 'done' AND p.status NOT IN ('anulat', 'finalizat')
             AND NOT (
               t.recurenta IS NOT NULL AND TRIM(t.recurenta) <> ''
               AND t.data_scadenta IS NOT NULL AND date(t.data_scadenta) > date(:today)
             )''',
        {'today': today})
    tasks_by_project = {}
    for r in cursor.fetchall():
        item = _agenda_item(row_to_dict(r), 'proiect', today)
        if _span_intersects(item['data_planificata'], item['data_scadenta'], start_s, end_s):
            tasks_by_project.setdefault(item['proiect_id'], []).append(item)

    def _task_sort_key(t):
        cand = [x for x in ((t['data_planificata'] or '')[:10], (t['data_scadenta'] or '')[:10]) if x]
        return (min(cand) if cand else '9999-99-99', (t['titlu'] or '').lower())

    lanes = []
    for proj in projects:
        pid = proj['id']
        ptasks = sorted(tasks_by_project.get(pid, []), key=_task_sort_key)
        inc = (proj.get('data_incepere') or '')[:10]
        ddl = (proj.get('deadline') or '')[:10]
        band = _span_intersects(inc, ddl, start_s, end_s)
        if not ptasks and not band:
            continue
        lanes.append({
            'tip': 'proiect',
            'id': pid,
            'nume': proj.get('nume') or '',
            'tip_proiect': proj.get('tip') or '',
            'status': proj.get('status') or '',
            'data_incepere': inc,
            'deadline': ddl,
            'tasks': ptasks,
        })

    # Global tasks lane.
    cursor.execute(
        '''SELECT g.* FROM global_tasks g
           WHERE g.status != 'done'
             AND NOT (
               g.recurenta IS NOT NULL AND TRIM(g.recurenta) <> ''
               AND g.data_scadenta IS NOT NULL AND date(g.data_scadenta) > date(:today)
             )''',
        {'today': today})
    gtasks = []
    for r in cursor.fetchall():
        item = _agenda_item(row_to_dict(r), 'global', today)
        if _span_intersects(item['data_planificata'], item['data_scadenta'], start_s, end_s):
            gtasks.append(item)
    if gtasks:
        lanes.append({
            'tip': 'global', 'id': '__global__', 'nume': 'Globale',
            'tip_proiect': '', 'status': '', 'data_incepere': '', 'deadline': '',
            'tasks': sorted(gtasks, key=_task_sort_key),
        })

    conn.close()

    # Lane order: projects by earliest in-window activity, Globale last.
    def _lane_key(l):
        dates = []
        for t in l['tasks']:
            for k in ('data_planificata', 'data_scadenta'):
                v = (t.get(k) or '')[:10]
                if v:
                    dates.append(v)
        if l['data_incepere']:
            dates.append(l['data_incepere'])
        return (1 if l['tip'] == 'global' else 0, min(dates) if dates else '9999-99-99')

    lanes.sort(key=_lane_key)
    return jsonify({'start': start_s, 'days': days, 'today': today, 'lanes': lanes})

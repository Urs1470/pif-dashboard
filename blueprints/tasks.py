import calendar
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from database import get_db, row_to_dict
from utils import generate_uuid, login_required

tasks_bp = Blueprint('tasks', __name__)

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

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

    # 3) Batch-fetch timer totals and running state (one query for all tasks).
    #    Joins task_subtasks to also capture time logged against subtasks.
    cursor.execute(f'''
        SELECT t_id,
               COALESCE(SUM(CASE WHEN ts.durata_secunde IS NOT NULL THEN ts.durata_secunde ELSE 0 END), 0) AS timp_secunde,
               MAX(CASE WHEN ts.stop_time IS NULL THEN 1 ELSE 0 END) AS timer_running
        FROM (
            SELECT ts.durata_secunde, ts.stop_time, ts.task_id AS t_id
            FROM timer_sessions ts
            WHERE ts.task_id IN ({placeholders})
            UNION ALL
            SELECT ts.durata_secunde, ts.stop_time, st.task_id AS t_id
            FROM timer_sessions ts
            JOIN task_subtasks st ON ts.subtask_id = st.id
            WHERE st.task_id IN ({placeholders})
        ) ts
        GROUP BY t_id
    ''', task_ids + task_ids)
    timer_map = {}
    for r in cursor.fetchall():
        timer_map[r['t_id']] = {'timp_secunde': r['timp_secunde'],
                                 'timer_running': r['timer_running']}

    conn.close()

    # 4) Merge results in Python.
    result = []
    for row in rows:
        d = row_to_dict(row)
        sc = subtask_map.get(d['id'], {})
        d['subtask_total'] = sc.get('subtask_total', 0)
        d['subtask_done'] = sc.get('subtask_done', 0)
        tm = timer_map.get(d['id'], {})
        d['timp_secunde'] = tm.get('timp_secunde', 0)
        d['timer_running'] = tm.get('timer_running', 0)
        result.append(d)

    return jsonify(result)


@tasks_bp.route('/api/proiecte/<project_id>/tasks', methods=['POST'])
@login_required
def create_task(project_id):
    data = request.json
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
                           data_finalizare, ordine, created_at, descriere, recurenta, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        now
    ))

    conn.commit()
    conn.close()

    return jsonify({'id': task_id}), 201


@tasks_bp.route('/api/tasks/<task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    data = request.json or {}
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    existing = cursor.fetchone()
    if existing is None:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    old_status = existing['status']

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
        datetime.now().isoformat(),
        task_id
    ))

    # A recurring task just completed -> spawn the next occurrence.
    spawned_id = None
    if (data.get('status') == 'done' and old_status != 'done'
            and (existing['recurenta'] or '').strip()):
        spawned_id = _spawn_recurring_task(cursor, existing, existing['recurenta'].strip())

    conn.commit()
    conn.close()

    resp = {'message': 'Task updated'}
    if spawned_id:
        resp['recurring_spawned'] = spawned_id
    return jsonify(resp)


@tasks_bp.route('/api/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM task_subtasks WHERE task_id = ?', (task_id,))
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
    data = request.json or {}
    titlu = (data.get('titlu') or '').strip()
    if not titlu:
        return jsonify({'error': 'Titlu required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COALESCE(MAX(ordine), -1) + 1 FROM task_subtasks WHERE task_id = ?', (task_id,))
    next_ordine = cursor.fetchone()[0]
    sid = generate_uuid()
    cursor.execute(
        'INSERT INTO task_subtasks (id, task_id, titlu, done, ordine, created_at) VALUES (?, ?, ?, 0, ?, ?)',
        (sid, task_id, titlu, next_ordine, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return jsonify({'id': sid}), 201


@tasks_bp.route('/api/subtasks/<subtask_id>', methods=['PUT'])
@login_required
def update_subtask(subtask_id):
    data = request.json or {}
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

    query = ('SELECT g.*, '
             '(SELECT COUNT(*) FROM task_subtasks s WHERE s.task_id = g.id) AS subtask_total, '
             '(SELECT COUNT(*) FROM task_subtasks s WHERE s.task_id = g.id AND s.done = 1) AS subtask_done, '
             '(SELECT COALESCE(SUM(durata_secunde), 0) FROM global_task_sessions gs '
             'WHERE gs.global_task_id = g.id) AS timp_secunde, '
             '(SELECT COUNT(*) > 0 FROM global_task_sessions gs '
             'WHERE gs.global_task_id = g.id AND gs.stop_time IS NULL) AS timer_running '
             'FROM global_tasks g WHERE 1=1')
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
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])


@tasks_bp.route('/api/global-tasks', methods=['POST'])
@login_required
def create_global_task():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    task_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO global_tasks (id, titlu, descriere, prioritate, status, categorie,
                                  data_scadenta, data_finalizare, created_at, updated_at, recurenta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data.get('recurenta', '')
    ))

    conn.commit()
    conn.close()

    return jsonify({'id': task_id}), 201


@tasks_bp.route('/api/global-tasks/<task_id>', methods=['GET'])
@login_required
def get_global_task(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''SELECT g.*,
        (SELECT COALESCE(SUM(durata_secunde), 0) FROM global_task_sessions gs
         WHERE gs.global_task_id = g.id) AS timp_secunde
        FROM global_tasks g WHERE g.id = ?''', (task_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(row_to_dict(row))


@tasks_bp.route('/api/global-tasks/<task_id>', methods=['PUT', 'POST'])
@login_required
def update_global_task(task_id):
    data = request.json or {}
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM global_tasks WHERE id = ?', (task_id,))
    existing = cursor.fetchone()
    if existing is None:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    old_status = existing['status']
    now = datetime.now().isoformat()

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
        now,
        task_id
    ))

    # A recurring daily task just completed -> spawn the next occurrence.
    spawned_id = None
    if (data.get('status') == 'done' and old_status != 'done'
            and (existing['recurenta'] or '').strip()):
        spawned_id = _spawn_recurring_global_task(cursor, existing, existing['recurenta'].strip())

    conn.commit()
    conn.close()

    resp = {'message': 'Task updated'}
    if spawned_id:
        resp['recurring_spawned'] = spawned_id
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

# Timer Blueprint
# All timer routes: project timer, per-task timer, per-subtask timer,
# global-task timer, and manual time entries.

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from database import get_db, row_to_dict
from utils import generate_uuid, login_required

timer_bp = Blueprint('timer', __name__)

# ──────────────────────────────────────────────────────────────────
# Helpers & whitelists
# ──────────────────────────────────────────────────────────────────

_TIMER_TABLES = {'timer_sessions', 'global_task_sessions'}
_TIMER_COLS = {'subtask_id', 'task_id', 'global_task_id', 'proiect_id'}


def _sum_timer(col, val, table='timer_sessions', cursor=None):
    """Sum of durata_secunde where col=val.  Pass *cursor* to read inside an
    in-flight transaction; otherwise opens its own short-lived connection.
    Whitelists table/col so the f-string can't be turned into injection."""
    if table not in _TIMER_TABLES:
        raise ValueError(f"Invalid table: {table}")
    if col not in _TIMER_COLS:
        raise ValueError(f"Invalid col: {col}")
    sql = (f"SELECT COALESCE(SUM(durata_secunde), 0) FROM {table} "
           f"WHERE {col}=? AND durata_secunde IS NOT NULL")
    if cursor is not None:
        cursor.execute(sql, (val,))
        return cursor.fetchone()[0]
    conn = get_db()
    try:
        c = conn.cursor()
        c.execute(sql, (val,))
        return c.fetchone()[0]
    finally:
        conn.close()


def _manual_session_times(data_str, durata_secunde):
    """Manual time entry -> (start_iso, stop_iso).  Anchors the session at noon
    on the given date so timezone math can never shift it to another day."""
    try:
        d = datetime.fromisoformat((data_str or '')[:10])
    except (ValueError, TypeError):
        d = datetime.now()
    start = d.replace(hour=12, minute=0, second=0, microsecond=0)
    stop = start + timedelta(seconds=int(durata_secunde))
    return start.isoformat(), stop.isoformat()


# ──────────────────────────────────────────────────────────────────
# PROJECT TIMER (standalone — task_id IS NULL)
# ──────────────────────────────────────────────────────────────────

@timer_bp.route('/api/proiecte/<project_id>/timer', methods=['GET'])
@login_required
def get_timer_sessions(project_id):
    conn = get_db()
    cursor = conn.cursor()
    # Standalone project timer only — per-task sessions are shown in the task modal.
    cursor.execute('''
        SELECT * FROM timer_sessions
        WHERE proiect_id = ? AND task_id IS NULL
        ORDER BY start_time DESC
    ''', (project_id,))
    rows = cursor.fetchall()
    conn.close()

    sessions = [row_to_dict(row) for row in rows]
    total = sum(s['durata_secunde'] or 0 for s in sessions)

    return jsonify({'sessions': sessions, 'total_secunde': total})


@timer_bp.route('/api/proiecte/<project_id>/timer/start', methods=['POST'])
@login_required
def start_timer(project_id):
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    session_id = generate_uuid()

    cursor.execute('''
        INSERT INTO timer_sessions (id, proiect_id, start_time)
        VALUES (?, ?, ?)
    ''', (session_id, project_id, now))

    conn.commit()
    conn.close()

    return jsonify({'id': session_id, 'start_time': now})


@timer_bp.route('/api/proiecte/<project_id>/timer/stop', methods=['POST'])
@login_required
def stop_timer(project_id):
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    # Find active session — only the standalone project timer (task_id IS NULL),
    # never a per-task timer session.
    cursor.execute('''
        SELECT * FROM timer_sessions
        WHERE proiect_id = ? AND stop_time IS NULL AND task_id IS NULL
        ORDER BY start_time DESC LIMIT 1
    ''', (project_id,))
    session = cursor.fetchone()

    if session is None:
        conn.close()
        return jsonify({'error': 'No active timer session'}), 404

    start_time = datetime.fromisoformat(session['start_time'])
    stop_time = datetime.fromisoformat(now)
    duration = int((stop_time - start_time).total_seconds())

    cursor.execute('''
        UPDATE timer_sessions
        SET stop_time = ?, durata_secunde = ?
        WHERE id = ?
    ''', (now, duration, session['id']))

    conn.commit()
    conn.close()

    return jsonify({'id': session['id'], 'stop_time': now, 'durata_secunde': duration})


@timer_bp.route('/api/proiecte/<project_id>/timer/stop-with-note', methods=['POST'])
@login_required
def stop_timer_with_note(project_id):
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    cursor.execute('''
        SELECT * FROM timer_sessions
        WHERE proiect_id = ? AND stop_time IS NULL AND task_id IS NULL
        ORDER BY start_time DESC LIMIT 1
    ''', (project_id,))
    timer_session = cursor.fetchone()

    if timer_session is None:
        conn.close()
        return jsonify({'error': 'No active timer session'}), 404

    start_time = datetime.fromisoformat(timer_session['start_time'])
    stop_time = datetime.fromisoformat(now)
    duration = int((stop_time - start_time).total_seconds())

    cursor.execute('''
        UPDATE timer_sessions
        SET stop_time = ?, durata_secunde = ?
        WHERE id = ?
    ''', (now, duration, timer_session['id']))

    data = request.json or {}
    titlu = data.get('titlu', 'Activitate')
    note = data.get('note', '')

    hours = duration / 3600
    continut = f"[{titlu}] {note} — {hours:.1f}h ({duration // 60}min)".strip()

    entry_id = generate_uuid()
    cursor.execute('''
        INSERT INTO jurnal (id, proiect_id, data, continut, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (entry_id, project_id, now[:10], continut, now))

    conn.commit()
    conn.close()

    return jsonify({
        'timer_id': timer_session['id'],
        'jurnal_id': entry_id,
        'durata_secunde': duration,
        'continut': continut
    })


@timer_bp.route('/api/proiecte/<project_id>/timer/manual', methods=['POST'])
@login_required
def add_manual_timer(project_id):
    """Manual time entry on the project's standalone timer."""
    data = request.json or {}
    try:
        dur = int(data.get('durata_secunde') or 0)
    except (ValueError, TypeError):
        dur = 0
    if dur <= 0:
        return jsonify({'error': 'Durata invalidă'}), 400
    start, stop = _manual_session_times(data.get('data'), dur)
    conn = get_db()
    cursor = conn.cursor()
    sid = generate_uuid()
    cursor.execute('INSERT INTO timer_sessions (id, proiect_id, start_time, stop_time, durata_secunde) '
                   'VALUES (?, ?, ?, ?, ?)', (sid, project_id, start, stop, dur))
    conn.commit()
    conn.close()
    return jsonify({'id': sid, 'durata_secunde': dur})


@timer_bp.route('/api/timer/<session_id>', methods=['DELETE'])
@login_required
def delete_timer_session(session_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM timer_sessions WHERE id = ?', (session_id,))
        deleted = cursor.rowcount
        conn.commit()
    finally:
        conn.close()
    if deleted == 0:
        return jsonify({'error': 'Timer session not found'}), 404
    return jsonify({'message': 'Timer session deleted'})


# ──────────────────────────────────────────────────────────────────
# PER-TASK TIMER
# Time tracked against a specific task.  Stored in timer_sessions with task_id
# set, kept isolated from the standalone project timer (which uses task_id NULL).
# ──────────────────────────────────────────────────────────────────

@timer_bp.route('/api/tasks/<task_id>/timer', methods=['GET'])
@login_required
def get_task_timer(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT start_time FROM timer_sessions
        WHERE task_id = ? AND stop_time IS NULL
        ORDER BY start_time DESC LIMIT 1
    ''', (task_id,))
    running = cursor.fetchone()
    cursor.execute('SELECT * FROM timer_sessions WHERE task_id = ? ORDER BY start_time DESC', (task_id,))
    sessions = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    total = _sum_timer('task_id', task_id)
    return jsonify({
        'running': running is not None,
        'running_since': running['start_time'] if running else None,
        'total_secunde': total,
        'sessions': sessions,
    })


@timer_bp.route('/api/tasks/<task_id>/timer/start', methods=['POST'])
@login_required
def start_task_timer(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT proiect_id FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    now = datetime.now().isoformat()
    # Close any already-running session for this task (avoid duplicates).
    cursor.execute('SELECT id, start_time FROM timer_sessions WHERE task_id = ? AND stop_time IS NULL', (task_id,))
    for r in cursor.fetchall():
        dur = int((datetime.fromisoformat(now) - datetime.fromisoformat(r['start_time'])).total_seconds())
        cursor.execute('UPDATE timer_sessions SET stop_time = ?, durata_secunde = ? WHERE id = ?',
                       (now, dur, r['id']))
    session_id = generate_uuid()
    cursor.execute(
        'INSERT INTO timer_sessions (id, proiect_id, task_id, start_time) VALUES (?, ?, ?, ?)',
        (session_id, task['proiect_id'], task_id, now)
    )
    conn.commit()
    conn.close()
    return jsonify({'id': session_id, 'start_time': now})


@timer_bp.route('/api/tasks/<task_id>/timer/stop', methods=['POST'])
@login_required
def stop_task_timer(task_id):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''
        SELECT id, start_time FROM timer_sessions
        WHERE task_id = ? AND stop_time IS NULL
        ORDER BY start_time DESC LIMIT 1
    ''', (task_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return jsonify({'error': 'No running timer for this task'}), 404
    dur = int((datetime.fromisoformat(now) - datetime.fromisoformat(session['start_time'])).total_seconds())
    cursor.execute('UPDATE timer_sessions SET stop_time = ?, durata_secunde = ? WHERE id = ?',
                   (now, dur, session['id']))
    conn.commit()
    conn.close()
    total = _sum_timer('task_id', task_id)
    return jsonify({'durata_secunde': dur, 'total_secunde': total})


@timer_bp.route('/api/tasks/<task_id>/timer/manual', methods=['POST'])
@login_required
def add_manual_task_timer(task_id):
    """Manual time entry on a project task."""
    data = request.json or {}
    try:
        dur = int(data.get('durata_secunde') or 0)
    except (ValueError, TypeError):
        dur = 0
    if dur <= 0:
        return jsonify({'error': 'Durata invalidă'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT proiect_id FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    start, stop = _manual_session_times(data.get('data'), dur)
    sid = generate_uuid()
    cursor.execute('INSERT INTO timer_sessions (id, proiect_id, task_id, start_time, stop_time, durata_secunde) '
                   'VALUES (?, ?, ?, ?, ?, ?)', (sid, task['proiect_id'], task_id, start, stop, dur))
    cursor.execute('SELECT COALESCE(SUM(durata_secunde), 0) FROM timer_sessions '
                   'WHERE task_id = ? AND durata_secunde IS NOT NULL', (task_id,))
    total = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({'id': sid, 'durata_secunde': dur, 'total_secunde': total})


# ──────────────────────────────────────────────────────────────────
# PER-SUBTASK TIMER
# Time tracked against a specific subtask.  Stored in timer_sessions
# with subtask_id set.
# ──────────────────────────────────────────────────────────────────

@timer_bp.route('/api/subtasks/<subtask_id>/timer', methods=['GET'])
@login_required
def get_subtask_timer(subtask_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM task_subtasks WHERE id = ?', (subtask_id,))
    subtask = cursor.fetchone()
    if not subtask:
        conn.close()
        return jsonify({'error': 'Subtask not found'}), 404
    cursor.execute('SELECT start_time FROM timer_sessions WHERE subtask_id = ? AND stop_time IS NULL ORDER BY start_time DESC LIMIT 1', (subtask_id,))
    running = cursor.fetchone()
    cursor.execute('SELECT * FROM timer_sessions WHERE subtask_id = ? ORDER BY start_time DESC', (subtask_id,))
    sessions = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    total = _sum_timer('subtask_id', subtask_id)
    return jsonify({
        'running': running is not None,
        'running_since': running['start_time'] if running else None,
        'total_secunde': total,
        'sessions': sessions,
    })


@timer_bp.route('/api/subtasks/<subtask_id>/timer/start', methods=['POST'])
@login_required
def start_subtask_timer(subtask_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM task_subtasks WHERE id = ?', (subtask_id,))
    subtask = cursor.fetchone()
    if not subtask:
        conn.close()
        return jsonify({'error': 'Subtask not found'}), 404
    now = datetime.now().isoformat()
    cursor.execute('SELECT id, start_time FROM timer_sessions WHERE subtask_id = ? AND stop_time IS NULL', (subtask_id,))
    for r in cursor.fetchall():
        dur = int((datetime.fromisoformat(now) - datetime.fromisoformat(r['start_time'])).total_seconds())
        cursor.execute('UPDATE timer_sessions SET stop_time = ?, durata_secunde = ? WHERE id = ?', (now, dur, r['id']))
    cursor.execute('SELECT t.proiect_id FROM tasks t JOIN task_subtasks s ON s.task_id = t.id WHERE s.id = ?', (subtask_id,))
    task_row = cursor.fetchone()
    proj_id = task_row['proiect_id'] if task_row else None
    session_id = generate_uuid()
    cursor.execute(
        'INSERT INTO timer_sessions (id, proiect_id, subtask_id, start_time) VALUES (?, ?, ?, ?)',
        (session_id, proj_id, subtask_id, now)
    )
    conn.commit()
    conn.close()
    return jsonify({'id': session_id, 'start_time': now})


@timer_bp.route('/api/subtasks/<subtask_id>/timer/stop', methods=['POST'])
@login_required
def stop_subtask_timer(subtask_id):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('SELECT * FROM timer_sessions WHERE subtask_id = ? AND stop_time IS NULL ORDER BY start_time DESC LIMIT 1', (subtask_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return jsonify({'error': 'No running timer for this subtask'}), 404
    dur = int((datetime.fromisoformat(now) - datetime.fromisoformat(session['start_time'])).total_seconds())
    cursor.execute('UPDATE timer_sessions SET stop_time = ?, durata_secunde = ? WHERE id = ?', (now, dur, session['id']))
    conn.commit()
    conn.close()
    total = _sum_timer('subtask_id', subtask_id)
    return jsonify({'durata_secunde': dur, 'total_secunde': total})


@timer_bp.route('/api/subtasks/<subtask_id>/timer/manual', methods=['POST'])
@login_required
def add_manual_subtask_timer(subtask_id):
    """Manual time entry on a subtask."""
    data = request.json or {}
    try:
        dur = int(data.get('durata_secunde') or 0)
    except (ValueError, TypeError):
        dur = 0
    if dur <= 0:
        return jsonify({'error': 'Durata invalidă'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM task_subtasks WHERE id = ?', (subtask_id,))
    subtask = cursor.fetchone()
    if not subtask:
        conn.close()
        return jsonify({'error': 'Subtask not found'}), 404
    cursor.execute('SELECT t.proiect_id FROM tasks t WHERE t.id = ?', (subtask['task_id'],))
    task_row = cursor.fetchone()
    proj_id = task_row['proiect_id'] if task_row else None
    start, stop = _manual_session_times(data.get('data'), dur)
    sid = generate_uuid()
    cursor.execute('INSERT INTO timer_sessions (id, proiect_id, subtask_id, start_time, stop_time, durata_secunde) '
                   'VALUES (?, ?, ?, ?, ?, ?)', (sid, proj_id, subtask_id, start, stop, dur))
    conn.commit()
    conn.close()
    total = _sum_timer('subtask_id', subtask_id)
    return jsonify({'id': sid, 'durata_secunde': dur, 'total_secunde': total})


# ──────────────────────────────────────────────────────────────────
# GLOBAL TASK TIMER
# Time tracking for daily (global) tasks.  Stored in global_task_sessions,
# kept separate from timer_sessions (which is project-scoped, proiect_id NOT NULL).
# ──────────────────────────────────────────────────────────────────

@timer_bp.route('/api/global-tasks/<task_id>/timer', methods=['GET'])
@login_required
def get_global_task_timer(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''SELECT start_time FROM global_task_sessions
                      WHERE global_task_id = ? AND stop_time IS NULL
                      ORDER BY start_time DESC LIMIT 1''', (task_id,))
    running = cursor.fetchone()
    cursor.execute('SELECT * FROM global_task_sessions WHERE global_task_id = ? '
                   'ORDER BY start_time DESC', (task_id,))
    sessions = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()
    total = _sum_timer('global_task_id', task_id, table='global_task_sessions')
    return jsonify({
        'running': running is not None,
        'running_since': running['start_time'] if running else None,
        'total_secunde': total,
        'sessions': sessions,
    })


@timer_bp.route('/api/global-tasks/<task_id>/timer/start', methods=['POST'])
@login_required
def start_global_task_timer(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM global_tasks WHERE id = ?', (task_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    now = datetime.now().isoformat()
    # Close any already-running session for this task (avoid duplicates).
    cursor.execute('SELECT id, start_time FROM global_task_sessions '
                   'WHERE global_task_id = ? AND stop_time IS NULL', (task_id,))
    for r in cursor.fetchall():
        dur = int((datetime.fromisoformat(now) - datetime.fromisoformat(r['start_time'])).total_seconds())
        cursor.execute('UPDATE global_task_sessions SET stop_time = ?, durata_secunde = ? WHERE id = ?',
                       (now, max(0, dur), r['id']))
    session_id = generate_uuid()
    cursor.execute('INSERT INTO global_task_sessions (id, global_task_id, start_time) VALUES (?, ?, ?)',
                   (session_id, task_id, now))
    conn.commit()
    conn.close()
    return jsonify({'id': session_id, 'start_time': now})


@timer_bp.route('/api/global-tasks/<task_id>/timer/stop', methods=['POST'])
@login_required
def stop_global_task_timer(task_id):
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute('''SELECT id, start_time FROM global_task_sessions
                      WHERE global_task_id = ? AND stop_time IS NULL
                      ORDER BY start_time DESC LIMIT 1''', (task_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        return jsonify({'error': 'No running timer for this task'}), 404
    dur = max(0, int((datetime.fromisoformat(now) - datetime.fromisoformat(session['start_time'])).total_seconds()))
    cursor.execute('UPDATE global_task_sessions SET stop_time = ?, durata_secunde = ? WHERE id = ?',
                   (now, dur, session['id']))
    cursor.execute('SELECT COALESCE(SUM(durata_secunde), 0) FROM global_task_sessions '
                   'WHERE global_task_id = ? AND durata_secunde IS NOT NULL', (task_id,))
    total = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({'durata_secunde': dur, 'total_secunde': total})


@timer_bp.route('/api/global-tasks/<task_id>/timer/manual', methods=['POST'])
@login_required
def add_manual_global_task_timer(task_id):
    """Manual time entry on a daily (global) task."""
    data = request.json or {}
    try:
        dur = int(data.get('durata_secunde') or 0)
    except (ValueError, TypeError):
        dur = 0
    if dur <= 0:
        return jsonify({'error': 'Durata invalidă'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM global_tasks WHERE id = ?', (task_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Task not found'}), 404
    start, stop = _manual_session_times(data.get('data'), dur)
    sid = generate_uuid()
    cursor.execute('INSERT INTO global_task_sessions (id, global_task_id, start_time, stop_time, durata_secunde) '
                   'VALUES (?, ?, ?, ?, ?)', (sid, task_id, start, stop, dur))
    cursor.execute('SELECT COALESCE(SUM(durata_secunde), 0) FROM global_task_sessions '
                   'WHERE global_task_id = ? AND durata_secunde IS NOT NULL', (task_id,))
    total = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({'id': sid, 'durata_secunde': dur, 'total_secunde': total})


@timer_bp.route('/api/global-task-timer/<session_id>', methods=['DELETE'])
@login_required
def delete_global_task_session(session_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM global_task_sessions WHERE id = ?', (session_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Session not found'}), 404
        return jsonify({'message': 'Session deleted'})
    finally:
        conn.close()


# ── Active timers (any kind) for the global sticky banner ──
@timer_bp.route('/api/timer/active', methods=['GET'])
@login_required
def get_active_timers():
    """Return all currently-running timers across project/task/subtask/global.
    Used by the persistent timer banner to show whatever is ticking right now.
    Returns at most one item per kind; UI shows the most recently started.
    """
    conn = get_db()
    cursor = conn.cursor()
    results = []

    # Project-level timer (project, no task/subtask)
    cursor.execute("""
        SELECT ts.id, ts.proiect_id, ts.start_time, p.nume AS project_name
        FROM timer_sessions ts JOIN proiecte p ON ts.proiect_id = p.id
        WHERE ts.stop_time IS NULL AND ts.task_id IS NULL AND ts.subtask_id IS NULL
        ORDER BY ts.start_time DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        results.append({
            'kind': 'project',
            'session_id': row['id'],
            'project_id': row['proiect_id'],
            'project_name': row['project_name'],
            'start_time': row['start_time'],
            'label': row['project_name'],
        })

    # Task-level timer
    cursor.execute("""
        SELECT ts.id, ts.task_id, ts.proiect_id, ts.start_time,
               t.titlu AS task_title, p.nume AS project_name
        FROM timer_sessions ts
        JOIN tasks t ON ts.task_id = t.id
        LEFT JOIN proiecte p ON ts.proiect_id = p.id
        WHERE ts.stop_time IS NULL AND ts.task_id IS NOT NULL AND ts.subtask_id IS NULL
        ORDER BY ts.start_time DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        results.append({
            'kind': 'task',
            'session_id': row['id'],
            'task_id': row['task_id'],
            'project_id': row['proiect_id'],
            'project_name': row['project_name'],
            'task_title': row['task_title'],
            'start_time': row['start_time'],
            'label': row['task_title'] + (f" · {row['project_name']}" if row['project_name'] else ''),
        })

    # Subtask-level timer
    cursor.execute("""
        SELECT ts.id, ts.subtask_id, ts.start_time,
               st.titlu AS subtask_title, t.titlu AS task_title, p.nume AS project_name
        FROM timer_sessions ts
        JOIN task_subtasks st ON ts.subtask_id = st.id
        LEFT JOIN tasks t ON st.task_id = t.id
        LEFT JOIN proiecte p ON ts.proiect_id = p.id
        WHERE ts.stop_time IS NULL AND ts.subtask_id IS NOT NULL
        ORDER BY ts.start_time DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        results.append({
            'kind': 'subtask',
            'session_id': row['id'],
            'subtask_id': row['subtask_id'],
            'start_time': row['start_time'],
            'label': row['subtask_title'] + (f" · {row['task_title']}" if row['task_title'] else ''),
        })

    # Global task timer
    cursor.execute("""
        SELECT gs.id, gs.global_task_id, gs.start_time, gt.titlu AS task_title
        FROM global_task_sessions gs
        JOIN global_tasks gt ON gs.global_task_id = gt.id
        WHERE gs.stop_time IS NULL
        ORDER BY gs.start_time DESC LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        results.append({
            'kind': 'global_task',
            'session_id': row['id'],
            'global_task_id': row['global_task_id'],
            'start_time': row['start_time'],
            'label': row['task_title'],
        })

    conn.close()

    # Sort by start_time desc — most-recently-started timer first
    results.sort(key=lambda r: r['start_time'], reverse=True)
    return jsonify({'timers': results, 'active': len(results) > 0})

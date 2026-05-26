#!/usr/bin/env python3
lines = open('app.py').readlines()
insert_at = 1480
code = '''


@app.route('/api/subtasks/<subtask_id>/timer/manual', methods=['POST'])
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
    cursor.execute('SELECT COALESCE(SUM(durata_secunde), 0) FROM timer_sessions '
                   'WHERE subtask_id = ? AND durata_secunde IS NOT NULL', (subtask_id,))
    total = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return jsonify({'id': sid, 'durata_secunde': dur, 'total_secunde': total})
'''
lines = lines[:insert_at] + [code] + lines[insert_at:]
open('app.py', 'w').writelines(lines)
print(f'Inserted at line {insert_at}, total lines: {len(lines)}')

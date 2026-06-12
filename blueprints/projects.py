# Projects Blueprint
# Provides all project-related CRUD routes extracted from app.py

import os
import json
import shutil
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename

from database import get_db, row_to_dict
from utils import (
    safe_table, generate_uuid, login_required, UPLOAD_FOLDER, VALID_TABLES,
    get_app_setting, set_app_setting, get_json_or_400,
)
from scripts.parse_params import parse_for_producator
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

    query = 'SELECT * FROM proiecte WHERE 1=1'
    params = []

    if status:
        query += ' AND status = ?'
        params.append(status)
    if tip:
        query += ' AND tip = ?'
        params.append(tip)
    if producator:
        query += ' AND producator = ?'
        params.append(producator)

    query += ' ORDER BY created_at DESC'

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
            cod_proiect, pm, folder_server, data_incepere, deadline, data_crearii,
            status, observatii, nr_comanda, nr_contract, service_before, service_after,
            confirmat_client, client_nume_confirmare, created_at, updated_at
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
        data.get('deadline', ''),
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
        now
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
    cursor.execute('SELECT * FROM proiecte WHERE id = ?', (project_id,))
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
            deadline = COALESCE(?, deadline),
            status = COALESCE(?, status),
            observatii = COALESCE(?, observatii),
            nr_comanda = COALESCE(?, nr_comanda),
            nr_contract = COALESCE(?, nr_contract),
            service_before = COALESCE(?, service_before),
            service_after = COALESCE(?, service_after),
            confirmat_client = COALESCE(?, confirmat_client),
            client_nume_confirmare = COALESCE(?, client_nume_confirmare),
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
        data.get('deadline'),
        data.get('status'),
        data.get('observatii'),
        data.get('nr_comanda'),
        data.get('nr_contract'),
        data.get('service_before'),
        data.get('service_after'),
        data.get('confirmat_client'),
        data.get('client_nume_confirmare'),
        now,
        project_id
    ))

    conn.commit()

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
        tables = ['tasks', 'checklist_pif', 'checklist_categorii', 'jurnal',
                  'timer_sessions', 'atasamente', 'echipamente']
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
                tables = ['tasks', 'checklist_pif', 'checklist_categorii', 'jurnal',
                          'timer_sessions', 'atasamente', 'echipamente']
                for table in tables:
                    cursor.execute(f'DELETE FROM {safe_table(table)} WHERE proiect_id = ?', (pid,))
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


# ============ CHECKLIST PIF ============

@projects_bp.route('/api/proiecte/<project_id>/checklist', methods=['GET'])
@login_required
def get_checklist(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM checklist_pif WHERE proiect_id = ? ORDER BY ordine', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@projects_bp.route('/api/proiecte/<project_id>/checklist', methods=['POST'])
@login_required
def create_checklist_item(project_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    item_id = data.get('id') or generate_uuid()
    cat_id = data.get('categorie_id')
    # Accept '' / 'null' / 0 as "no category" -> NULL
    if cat_id in ('', 'null', 0, '0'):
        cat_id = None

    cursor.execute('''
        INSERT INTO checklist_pif (id, proiect_id, titlu, completed, note, ordine, categorie_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        item_id,
        project_id,
        data.get('titlu', ''),
        data.get('completed', 0),
        data.get('note', ''),
        data.get('ordine', 0),
        cat_id
    ))

    conn.commit()
    conn.close()

    return jsonify({'id': item_id}), 201

@projects_bp.route('/api/checklist/<item_id>', methods=['PUT'])
@login_required
def update_checklist_item(item_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    # categorie_id needs an explicit "no value" sentinel so 'UNSET' means "do not touch"
    # while None / 0 means "clear category".
    cat_present = 'categorie_id' in data
    cat_id = data.get('categorie_id')
    if cat_id in ('', 'null', 0, '0'):
        cat_id = None

    if cat_present:
        cursor.execute('''
            UPDATE checklist_pif SET
                titlu = COALESCE(?, titlu),
                completed = COALESCE(?, completed),
                note = COALESCE(?, note),
                ordine = COALESCE(?, ordine),
                categorie_id = ?
            WHERE id = ?
        ''', (
            data.get('titlu'),
            data.get('completed'),
            data.get('note'),
            data.get('ordine'),
            cat_id,
            item_id
        ))
    else:
        cursor.execute('''
            UPDATE checklist_pif SET
                titlu = COALESCE(?, titlu),
                completed = COALESCE(?, completed),
                note = COALESCE(?, note),
                ordine = COALESCE(?, ordine)
            WHERE id = ?
        ''', (
            data.get('titlu'),
            data.get('completed'),
            data.get('note'),
            data.get('ordine'),
            item_id
        ))

    conn.commit()
    conn.close()

    return jsonify({'message': 'Checklist item updated'})

@projects_bp.route('/api/checklist/<item_id>', methods=['DELETE'])
@login_required
def delete_checklist_item(item_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM checklist_pif WHERE id = ?', (item_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Checklist item not found'}), 404
        return jsonify({'message': 'Checklist item deleted'})
    finally:
        conn.close()

# ============ CHECKLIST CATEGORII (per-project dynamic) ============

@projects_bp.route('/api/proiecte/<project_id>/checklist-categorii', methods=['GET'])
@login_required
def list_checklist_categorii(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, proiect_id, nume, ordine, created_at FROM checklist_categorii WHERE proiect_id = ? ORDER BY ordine, id', (project_id,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

@projects_bp.route('/api/proiecte/<project_id>/checklist-categorii', methods=['POST'])
@login_required
def create_checklist_categorie(project_id):
    data = get_json_or_400()
    nume = (data.get('nume') or '').strip()
    if not nume:
        return jsonify({'error': 'Nume required'}), 400
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT COALESCE(MAX(ordine), -1) + 1 FROM checklist_categorii WHERE proiect_id = ?', (project_id,))
    next_ordine = cursor.fetchone()[0]
    cursor.execute(
        'INSERT INTO checklist_categorii(proiect_id, nume, ordine, created_at) VALUES (?, ?, ?, ?)',
        (project_id, nume, next_ordine, datetime.now().isoformat())
    )
    new_id = cursor.lastrowid
    conn.commit()
    cursor.execute('SELECT id, proiect_id, nume, ordine, created_at FROM checklist_categorii WHERE id = ?', (new_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return jsonify(row), 201

@projects_bp.route('/api/checklist-categorii/<int:cat_id>', methods=['PUT'])
@login_required
def update_checklist_categorie(cat_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()
    if 'nume' in data:
        nume = (data.get('nume') or '').strip()
        if not nume:
            return jsonify({'error': 'Nume required'}), 400
        cursor.execute('UPDATE checklist_categorii SET nume = ? WHERE id = ?', (nume, cat_id))
    if 'ordine' in data:
        cursor.execute('UPDATE checklist_categorii SET ordine = ? WHERE id = ?', (int(data['ordine']), cat_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@projects_bp.route('/api/checklist-categorii/<int:cat_id>', methods=['DELETE'])
@login_required
def delete_checklist_categorie(cat_id):
    # ?move=1 (default) -> orphan the items into "Fara categorie".
    # ?move=0           -> hard delete the items together with the category.
    move = request.args.get('move', '1') == '1'
    conn = get_db()
    try:
        cursor = conn.cursor()
        if move:
            cursor.execute('UPDATE checklist_pif SET categorie_id = NULL WHERE categorie_id = ?', (cat_id,))
        else:
            cursor.execute('DELETE FROM checklist_pif WHERE categorie_id = ?', (cat_id,))
        cursor.execute('DELETE FROM checklist_categorii WHERE id = ?', (cat_id,))
        conn.commit()
        return jsonify({'ok': True, 'moved': move})
    finally:
        conn.close()

# ============ JURNAL ============

@projects_bp.route('/api/proiecte/<project_id>/jurnal', methods=['GET'])
@login_required
def get_jurnal(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jurnal WHERE proiect_id = ? ORDER BY data DESC', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@projects_bp.route('/api/proiecte/<project_id>/jurnal', methods=['POST'])
@login_required
def create_jurnal_entry(project_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    entry_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO jurnal (id, proiect_id, data, continut, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        entry_id,
        project_id,
        data.get('data', now[:10]),
        data.get('continut', ''),
        now
    ))

    conn.commit()
    conn.close()

    return jsonify({'id': entry_id}), 201

@projects_bp.route('/api/jurnal/<entry_id>', methods=['DELETE'])
@login_required
def delete_jurnal_entry(entry_id):
    conn = get_db()
    try:
        cursor = conn.cursor()

        # If this jurnal entry was created by stop-with-note, there is a paired
        # timer_session row with stop_time within ~2 min of jurnal.created_at.
        # Cascade-delete it so the user doesn't need two clicks (delete the note,
        # then delete the leftover "Timer fara nota" that pops up afterward).
        cursor.execute(
            'SELECT proiect_id, created_at FROM jurnal WHERE id = ?',
            (entry_id,)
        )
        row = cursor.fetchone()
        if row:
            try:
                j_time = datetime.fromisoformat(row['created_at'])
                cursor.execute('''
                    SELECT id, stop_time FROM timer_sessions
                    WHERE proiect_id = ? AND stop_time IS NOT NULL
                ''', (row['proiect_id'],))
                for s in cursor.fetchall():
                    s_stop = datetime.fromisoformat(s['stop_time'])
                    if abs((s_stop - j_time).total_seconds()) < 120:
                        cursor.execute('DELETE FROM timer_sessions WHERE id = ?', (s['id'],))
                        break
            except (ValueError, TypeError):
                pass

        cursor.execute('DELETE FROM jurnal WHERE id = ?', (entry_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Jurnal entry not found'}), 404
        return jsonify({'message': 'Jurnal entry deleted'})
    finally:
        conn.close()

@projects_bp.route('/api/jurnal/all', methods=['GET'])
@login_required
def get_all_jurnal():
    """Returneaza toate intrarile de jurnal cu numele proiectului."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT j.id, j.proiect_id, j.data, j.continut, j.created_at, p.nume as project_name
        FROM jurnal j
        JOIN proiecte p ON j.proiect_id = p.id
        ORDER BY j.data DESC
        LIMIT 200
    ''')
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return jsonify(rows)


# ============ ATTACHMENTS ============

ATTACHMENT_TIP_MAP = {
    '.pdf': 'PDF',
    '.jpg': 'IMG', '.jpeg': 'IMG', '.png': 'IMG',
    '.gif': 'IMG', '.bmp': 'IMG', '.webp': 'IMG',
    '.msg': 'EMAIL', '.eml': 'EMAIL',
    '.doc': 'DOC', '.docx': 'DOC',
    '.xls': 'XLS', '.xlsx': 'XLS',
    '.zip': 'ZIP', '.rar': 'ZIP'
}


def _store_uploaded_file(file, subfolder):
    """Save an uploaded file under UPLOAD_FOLDER/<subfolder>/ and return
    (attachment_id, original_name, tip, size, filepath). Sanitizes the
    client-supplied name — never trust it for a filesystem path (blocks
    ../ traversal and overwriting server files)."""
    attachment_id = generate_uuid()
    folder = os.path.join(UPLOAD_FOLDER, subfolder)
    os.makedirs(folder, exist_ok=True)

    original_name = file.filename
    safe_name = secure_filename(original_name) or ('fisier_' + attachment_id[:8])
    filepath = os.path.join(folder, safe_name)
    if os.path.exists(filepath):
        safe_name = attachment_id[:8] + '_' + safe_name
        filepath = os.path.join(folder, safe_name)
    file.save(filepath)

    size = os.path.getsize(filepath)
    # Type from the original name — keeps the real extension
    ext = os.path.splitext(original_name)[1].lower()
    tip = ATTACHMENT_TIP_MAP.get(ext, 'ALT')
    return attachment_id, original_name, tip, size, filepath


def _require_upload_file():
    if 'file' not in request.files:
        return None, (jsonify({'error': 'No file provided'}), 400)
    file = request.files['file']
    if file.filename == '':
        return None, (jsonify({'error': 'No file selected'}), 400)
    return file, None


@projects_bp.route('/api/proiecte/<project_id>/atasamente', methods=['POST'])
@login_required
def upload_atasament(project_id):
    file, err = _require_upload_file()
    if err:
        return err

    attachment_id, original_name, tip, size, filepath = _store_uploaded_file(file, project_id)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO atasamente (id, proiect_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (attachment_id, project_id, original_name, tip, size, datetime.now().isoformat()[:10], filepath))
    conn.commit()
    conn.close()

    return jsonify({'id': attachment_id}), 201


@projects_bp.route('/api/tasks/<task_id>/atasamente', methods=['GET'])
@login_required
def get_task_atasamente(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM atasamente WHERE task_id = ? ORDER BY data DESC', (task_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])


@projects_bp.route('/api/tasks/<task_id>/atasamente', methods=['POST'])
@login_required
def upload_task_atasament(task_id):
    file, err = _require_upload_file()
    if err:
        return err

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT proiect_id FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Task not found'}), 404

    # Files live in the project folder so the project Atasamente tab sees them too.
    attachment_id, original_name, tip, size, filepath = _store_uploaded_file(file, task['proiect_id'])
    cursor.execute('''
        INSERT INTO atasamente (id, proiect_id, task_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (attachment_id, task['proiect_id'], task_id, original_name, tip, size, datetime.now().isoformat()[:10], filepath))
    conn.commit()
    conn.close()

    return jsonify({'id': attachment_id}), 201


@projects_bp.route('/api/global-tasks/<task_id>/atasamente', methods=['GET'])
@login_required
def get_global_task_atasamente(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM atasamente WHERE global_task_id = ? ORDER BY data DESC', (task_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])


@projects_bp.route('/api/global-tasks/<task_id>/atasamente', methods=['POST'])
@login_required
def upload_global_task_atasament(task_id):
    file, err = _require_upload_file()
    if err:
        return err

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM global_tasks WHERE id = ?', (task_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Task not found'}), 404

    attachment_id, original_name, tip, size, filepath = _store_uploaded_file(file, os.path.join('global-tasks', task_id))
    cursor.execute('''
        INSERT INTO atasamente (id, global_task_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (attachment_id, task_id, original_name, tip, size, datetime.now().isoformat()[:10], filepath))
    conn.commit()
    conn.close()

    return jsonify({'id': attachment_id}), 201

@projects_bp.route('/api/proiecte/<project_id>/atasamente', methods=['GET'])
@login_required
def get_atasamente(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM atasamente WHERE proiect_id = ? ORDER BY data DESC', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@projects_bp.route('/api/atasamente/<attachment_id>/download', methods=['GET'])
@login_required
def download_atasament(attachment_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM atasamente WHERE id = ?', (attachment_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'error': 'Attachment not found'}), 404

    filepath = row['cale_locala']
    real_path = os.path.realpath(filepath)
    safe_root = os.path.realpath(UPLOAD_FOLDER)
    if not real_path.startswith(safe_root + os.sep):
        return jsonify({'error': 'Invalid file path'}), 403
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found on disk'}), 404

    ext = os.path.splitext(row['nume_fisier'])[1].lower()
    inline_types = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    as_attachment = ext not in inline_types
    return send_file(filepath, as_attachment=as_attachment, download_name=row['nume_fisier'])

@projects_bp.route('/api/atasamente/<attachment_id>', methods=['DELETE'])
@login_required
def delete_atasament(attachment_id):
    conn = get_db()
    try:
        cursor = conn.cursor()

        cursor.execute('SELECT cale_locala FROM atasamente WHERE id = ?', (attachment_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({'error': 'Attachment not found'}), 404

        filepath = row['cale_locala']
        if os.path.exists(filepath):
            os.remove(filepath)

        cursor.execute('DELETE FROM atasamente WHERE id = ?', (attachment_id,))

        conn.commit()
        return jsonify({'message': 'Attachment deleted'})
    finally:
        conn.close()


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


# ============ EQUIPMENT ============

@projects_bp.route('/api/proiecte/<project_id>/echipamente', methods=['GET'])
@login_required
def get_echipamente(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM echipamente WHERE proiect_id = ? ORDER BY created_at DESC', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@projects_bp.route('/api/proiecte/<project_id>/echipamente', methods=['POST'])
@login_required
def create_echipament(project_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    echipament_id = data.get('id') or generate_uuid()

    # Parse params_text into key-value pairs
    params_text = data.get('params_text', '')
    params_dict = {}
    if params_text:
        for line in params_text.strip().split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                params_dict[key.strip()] = value.strip()

    cursor.execute('''
        INSERT INTO echipamente (id, proiect_id, nume, producator, model, serial_number, params_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        echipament_id,
        project_id,
        data.get('nume', ''),
        data.get('producator', 'Altul'),
        data.get('model', ''),
        data.get('serial_number', ''),
        json.dumps(params_dict),
        now,
        now
    ))

    conn.commit()
    conn.close()

    logger.info(f"Equipment created: {echipament_id} for project {project_id}")
    return jsonify({'id': echipament_id, 'message': 'Equipment created'}), 201

@projects_bp.route('/api/echipamente/<echipament_id>', methods=['GET'])
@login_required
def get_echipament(echipament_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM echipamente WHERE id = ?', (echipament_id,))
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({'error': 'Equipment not found'}), 404

    return jsonify(row_to_dict(row))

@projects_bp.route('/api/echipamente/<echipament_id>', methods=['PUT'])
@login_required
def update_echipament(echipament_id):
    data = get_json_or_400()
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    # Parse params_text if provided
    params_json = data.get('params_json')
    if data.get('params_text'):
        params_text = data.get('params_text', '')
        params_dict = {}
        if params_text:
            for line in params_text.strip().split('\n'):
                line = line.strip()
                if '=' in line:
                    key, value = line.split('=', 1)
                    params_dict[key.strip()] = value.strip()
        params_json = json.dumps(params_dict)

    # descrieri_json — merge incoming with existing
    descrieri_json = None
    if data.get('descrieri_json'):
        descrieri_json = data['descrieri_json']
        if isinstance(descrieri_json, dict):
            descrieri_json = json.dumps(descrieri_json)

    cursor.execute('''
        UPDATE echipamente SET
            nume = COALESCE(?, nume),
            producator = COALESCE(?, producator),
            model = COALESCE(?, model),
            serial_number = COALESCE(?, serial_number),
            params_json = COALESCE(?, params_json),
            descrieri_json = COALESCE(?, descrieri_json),
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('nume'),
        data.get('producator'),
        data.get('model'),
        data.get('serial_number'),
        params_json,
        descrieri_json,
        now,
        echipament_id
    ))

    conn.commit()
    conn.close()

    logger.info(f"Equipment updated: {echipament_id}")
    return jsonify({'message': 'Equipment updated'})

@projects_bp.route('/api/echipamente/<echipament_id>', methods=['DELETE'])
@login_required
def delete_echipament(echipament_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM echipamente WHERE id = ?', (echipament_id,))
        deleted = cursor.rowcount
        conn.commit()
        if deleted == 0:
            return jsonify({'error': 'Equipment not found'}), 404
        logger.info(f"Equipment deleted: {echipament_id}")
        return jsonify({'message': 'Equipment deleted'})
    finally:
        conn.close()


# ============ PROJECT SNAPSHOT (Cowork sync) ============

@projects_bp.route('/api/proiecte/<project_id>/snapshot', methods=['GET'])
@login_required
def get_project_snapshot(project_id):
    """Full project export as JSON — consumed by Cowork to build debriefs.

    Returns the same schema shape as the debrief import, so Cowork can
    read what it wrote + everything the user added on site (real params,
    timer hours, checked items, observations).
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

    # Echipamente
    cursor.execute('SELECT * FROM echipamente WHERE proiect_id = ? ORDER BY created_at', (project_id,))
    echipamente = []
    for row in cursor.fetchall():
        eq = row_to_dict(row)
        # Parse params_json for clean output
        try:
            eq['params_json'] = json.loads(eq.get('params_json') or '{}')
        except (json.JSONDecodeError, TypeError):
            eq['params_json'] = {}
        echipamente.append(eq)

    # Checklist categorii + items
    cursor.execute('SELECT * FROM checklist_categorii WHERE proiect_id = ? ORDER BY ordine', (project_id,))
    categorii = [row_to_dict(r) for r in cursor.fetchall()]
    cursor.execute('SELECT * FROM checklist_pif WHERE proiect_id = ? ORDER BY ordine', (project_id,))
    checklist_items = []
    for r in cursor.fetchall():
        item = row_to_dict(r)
        # Find category name
        cat_match = next((c for c in categorii if str(c['id']) == str(item.get('categorie_id'))), None)
        item['categorie'] = cat_match['nume'] if cat_match else None
        checklist_items.append(item)

    # Jurnal
    cursor.execute('SELECT * FROM jurnal WHERE proiect_id = ? ORDER BY data, created_at', (project_id,))
    jurnal = [row_to_dict(r) for r in cursor.fetchall()]

    # Timer sessions
    cursor.execute('SELECT * FROM timer_sessions WHERE proiect_id = ? ORDER BY start_time', (project_id,))
    sessions = [row_to_dict(r) for r in cursor.fetchall()]
    total_secunde = sum(s.get('durata_secunde', 0) or 0 for s in sessions)

    # Tasks + subtasks
    cursor.execute('SELECT * FROM tasks WHERE proiect_id = ? ORDER BY created_at', (project_id,))
    tasks = []
    for r in cursor.fetchall():
        t = row_to_dict(r)
        cursor.execute('SELECT * FROM task_subtasks WHERE task_id = ? ORDER BY ordine', (t['id'],))
        t['subtasks'] = [row_to_dict(s) for s in cursor.fetchall()]
        tasks.append(t)

    conn.close()

    # Build ore[] summary: group timer sessions by date
    ore_by_date = {}
    for s in sessions:
        d = (s.get('start_time') or '')[:10]
        if d:
            ore_by_date.setdefault(d, 0)
            ore_by_date[d] += s.get('durata_secunde', 0) or 0
    ore = [{'data': d, 'durata_secunde': sec} for d, sec in sorted(ore_by_date.items())]

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
            'deadline': p.get('deadline', ''),
            'data_crearii': p.get('data_crearii', ''),
            'status': p.get('status', ''),
            'observatii': p.get('observatii', ''),
            'confirmat_client': p.get('confirmat_client', 0),
            'client_nume_confirmare': p.get('client_nume_confirmare', ''),
            'service_before': p.get('service_before', ''),
            'service_after': p.get('service_after', ''),
        },
        'echipamente': [{
            'id': eq['id'],
            'nume': eq.get('nume', ''),
            'producator': eq.get('producator', ''),
            'model': eq.get('model', ''),
            'serial_number': eq.get('serial_number', ''),
            'params_json': eq.get('params_json', {}),
        } for eq in echipamente],
        'checklist_categorii': [{'nume': c['nume'], 'ordine': c.get('ordine', 0)} for c in categorii],
        'checklist_items': [{
            'categorie': it.get('categorie'),
            'titlu': it.get('titlu', ''),
            'completed': bool(it.get('completed')),
            'ordine': it.get('ordine', 0),
        } for it in checklist_items],
        'jurnal': [{
            'data': j.get('data', ''),
            'continut': j.get('continut', ''),
            'created_at': j.get('created_at', ''),
        } for j in jurnal],
        'ore': ore,
        'ore_total_secunde': total_secunde,
        'tasks': [{
            'titlu': t.get('titlu', ''),
            'descriere': t.get('descriere', ''),
            'status': t.get('status', ''),
            'prioritate': t.get('prioritate', ''),
            'data_scadenta': t.get('data_scadenta', ''),
            'subtasks': [{'titlu': s.get('titlu', ''), 'done': bool(s.get('done'))} for s in t.get('subtasks', [])],
        } for t in tasks],
        'timer_sessions': [{
            'start_time': s.get('start_time', ''),
            'stop_time': s.get('stop_time', ''),
            'durata_secunde': s.get('durata_secunde', 0),
        } for s in sessions],
    }

    return jsonify(snapshot)


# ============ IMPORT PARAMETRI DIN EXPORT PRODUCATOR ============

def _familie_from_echipament(producator: str, model: str) -> str:
    """Mapeaza producator+model la familie pentru join cu parametri_master.

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


@projects_bp.route('/api/import-params/preview', methods=['POST'])
@login_required
def preview_import_params():
    """Parseaza un export de parametri modificati (producator software) si returneaza preview.

    Form fields:
      file: fisierul exportat (text Danfoss .txt, in viitor PDF Lenze/Siemens)
      producator: numele producatorului (Danfoss, Lenze, Siemens, ABB)
      model: optional, pentru determinarea familiei (ACS580 vs ACS880 etc)

    Preview-ul nu modifica DB. Persistarea se face prin PUT /api/echipamente/<id>
    cu params_json deja merge-uit pe client.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Fisier lipsa (field "file")'}), 400
    upload = request.files['file']
    if not upload.filename:
        return jsonify({'error': 'Fisier gol'}), 400

    producator = (request.form.get('producator') or '').strip()
    model = (request.form.get('model') or '').strip()
    if not producator:
        return jsonify({'error': 'producator lipsa'}), 400

    try:
        raw = upload.read()
    except Exception as e:
        logger.exception("Eroare citire fisier import params")
        return jsonify({'error': f'Eroare citire fisier: {e}'}), 400

    detected, parsed = parse_for_producator(producator, raw, upload.filename or '')
    if detected is None or parsed is None:
        return jsonify({
            'error': f'Producator "{producator}" nu este inca suportat pentru import. Suportate: Danfoss, Lenze, Siemens, ABB.'
        }), 400

    # Imbogateste cu descriere_scurta din parametri_master
    familie = _familie_from_echipament(producator, model)
    if familie and parsed:
        conn = get_db()
        cursor = conn.cursor()
        codes = [p['db_id'] for p in parsed]
        placeholders = ','.join('?' * len(codes))
        cursor.execute(
            f'SELECT parametru, descriere_scurta FROM parametri_master WHERE familie = ? AND parametru IN ({placeholders})',
            [familie] + codes
        )
        desc_map = {r['parametru']: r['descriere_scurta'] for r in cursor.fetchall()}
        conn.close()
        for p in parsed:
            ds = desc_map.get(p['db_id'])
            if ds:
                p['descriere_db'] = ds

    return jsonify({
        'producator_detected': detected,
        'familie': familie,
        'filename': upload.filename,
        'count': len(parsed),
        'conflicts': sum(1 for p in parsed if p.get('conflict')),
        'params': parsed,
    })


# ============ IMPORT MULTI-FILE ABB (.dcparamsbak) ============

@projects_bp.route('/api/import-abb-multi/preview', methods=['POST'])
@login_required
def preview_import_abb_multi():
    """Parsează multiple fișiere .dcparamsbak ABB și returnează preview multi-drive.

    Form fields:
      files: unul sau mai multe fișiere .dcparamsbak
      model: optional, hint pentru familia (ACS580 vs ACS880)

    Returnează aceeași structură ca /import-archive/preview, compatibilă cu
    POST .../echipamente/import-archive pentru persistare.
    """
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

    # Enrich with parametri_master descriptions + filter factory defaults
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
    """Returnează {familie: {cod: {'desc': str, 'default': str}}} din parametri_master.

    Un singur SELECT per familie. Nemodificator pe DB. Folosit pentru a îmbogăți
    descrierile ȘI pentru a filtra parametrii care sunt la valoarea de fabrică.

    Pentru familii Siemens (SINAMICS), caută și versiunile r-prefix ale codurilor
    p-prefix — STARTER exportă toți parametrii cu prefix p, dar parametrii
    read-only sunt stocați în DB ca r (r0026 = DC link voltage smoothed).
    """
    by_familie = {}
    for d in drives:
        fam = d.get('familie') or ''
        if fam:
            by_familie.setdefault(fam, set()).update(d.get('params', {}).keys())
    if not by_familie:
        return {}

    meta = {}
    conn = get_db()
    cursor = conn.cursor()
    for fam, codes in by_familie.items():
        codes = list(codes)
        meta[fam] = {}

        # Lookup codurile exacte (p0304, 1.01, etc.)
        for i in range(0, len(codes), 900):
            chunk = codes[i:i + 900]
            placeholders = ','.join('?' * len(chunk))
            cursor.execute(
                f'SELECT parametru, descriere_scurta, valoare_default, valoare_default_str '
                f'FROM parametri_master WHERE familie = ? AND parametru IN ({placeholders})',
                [fam] + chunk
            )
            for r in cursor.fetchall():
                default = r['valoare_default']
                if default is None or str(default).strip() == '':
                    default = r['valoare_default_str']
                meta[fam][r['parametru']] = {
                    'desc': r['descriere_scurta'],
                    'default': default,
                }

        # Indexed params — look up base codes (p0114[2] → p0114)
        indexed_bases = set()
        for c in codes:
            if '[' in c:
                indexed_bases.add(c.split('[')[0])
        indexed_bases -= set(meta[fam].keys())
        if indexed_bases:
            indexed_list = list(indexed_bases)
            for i in range(0, len(indexed_list), 900):
                chunk = indexed_list[i:i + 900]
                placeholders = ','.join('?' * len(chunk))
                cursor.execute(
                    f'SELECT parametru, descriere_scurta, valoare_default, valoare_default_str '
                    f'FROM parametri_master WHERE familie = ? AND parametru IN ({placeholders})',
                    [fam] + chunk
                )
                for r in cursor.fetchall():
                    if r['parametru'] not in meta[fam]:
                        default = r['valoare_default']
                        if default is None or str(default).strip() == '':
                            default = r['valoare_default_str']
                        meta[fam][r['parametru']] = {
                            'desc': r['descriere_scurta'],
                            'default': default,
                        }

        # Siemens: caută r-prefix cross-family (read-only params)
        # r0027 poate fi în G130 dar nu în G120 — e read-only în ambele.
        # Caut fără filtru de familie, apoi stochez sub familia curentă.
        if 'SINAMICS' in fam or 'MICROMASTER' in fam:
            r_codes = set()
            for c in codes:
                base = c.split('[')[0] if '[' in c else c
                if base.startswith('p'):
                    r_codes.add('r' + base[1:])
            r_codes = list(r_codes)
            for i in range(0, len(r_codes), 900):
                chunk = r_codes[i:i + 900]
                placeholders = ','.join('?' * len(chunk))
                # Cross-family: orice r-param din orice familie Siemens
                cursor.execute(
                    f'SELECT DISTINCT parametru, descriere_scurta, valoare_default, valoare_default_str '
                    f'FROM parametri_master WHERE parametru IN ({placeholders})',
                    chunk
                )
                for r in cursor.fetchall():
                    if r['parametru'] not in meta[fam]:
                        default = r['valoare_default']
                        if default is None or str(default).strip() == '':
                            default = r['valoare_default_str']
                        meta[fam][r['parametru']] = {
                            'desc': r['descriere_scurta'],
                            'default': default,
                        }

            # Cross-family p-prefix: some params exist in other Siemens families
            missing_p = set()
            for c in codes:
                base = c.split('[')[0] if '[' in c else c
                if base not in meta[fam]:
                    missing_p.add(base)
            if missing_p:
                missing_list = list(missing_p)
                for i in range(0, len(missing_list), 900):
                    chunk = missing_list[i:i + 900]
                    placeholders = ','.join('?' * len(chunk))
                    cursor.execute(
                        f'SELECT DISTINCT parametru, descriere_scurta, valoare_default, valoare_default_str '
                        f'FROM parametri_master WHERE parametru IN ({placeholders})',
                        chunk
                    )
                    for r in cursor.fetchall():
                        if r['parametru'] not in meta[fam]:
                            default = r['valoare_default']
                            if default is None or str(default).strip() == '':
                                default = r['valoare_default_str']
                            meta[fam][r['parametru']] = {
                                'desc': r['descriere_scurta'],
                                'default': default,
                            }
    conn.close()
    return meta


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
      - dacă valoarea == default cunoscut din parametri_master => omis;
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
                # param not in parametri_master — use parser description
                if parser_desc.get(code):
                    descrieri[code] = parser_desc[code]
            kept[code] = val
        d['params'] = kept
        d['descrieri'] = descrieri
        d['modified_count'] = len(kept)
        d['skipped_default'] = skipped


@projects_bp.route('/api/import-archive/preview', methods=['POST'])
@login_required
def preview_import_archive():
    """Parsează o arhivă ZIP de proiect Siemens STARTER și returnează drive-urile.

    Form fields:
      file: arhiva .zip a proiectului STARTER (conține Project.mcp)

    Nu modifică DB. Persistarea se face prin POST .../echipamente/import-archive.
    """
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


@projects_bp.route('/api/proiecte/<project_id>/echipamente/import-archive', methods=['POST'])
@login_required
def import_archive_echipamente(project_id):
    """Creează câte un echipament per drive dintr-un import de arhivă STARTER.

    Body JSON: { "drives": [ {nume, producator, model, serial_number, firmware,
                              params: {code: value}}, ... ] }

    Fiecare drive devine un rând separat în `echipamente`, cu parametrii
    modificați stocați în params_json.
    """
    data = get_json_or_400()
    drives = data.get('drives') or []
    if not drives:
        return jsonify({'error': 'Niciun drive de importat'}), 400

    conn = get_db()
    cursor = conn.cursor()

    # validează existența proiectului (FK ar prinde oricum, dar mesaj mai clar)
    cursor.execute('SELECT id FROM proiecte WHERE id = ?', (project_id,))
    if cursor.fetchone() is None:
        conn.close()
        return jsonify({'error': 'Proiectul nu există'}), 404

    created = []
    now = datetime.now().isoformat()
    for drive in drives:
        params = drive.get('params') or {}
        if not isinstance(params, dict):
            params = {}
        # serializează valorile ca string-uri (consistent cu create_echipament)
        params_dict = {str(k): str(v) for k, v in params.items()}
        # descrieri din parser + parametri_master (populated by _filter_drive_params)
        descrieri = drive.get('descrieri') or {}
        descrieri_json = json.dumps(descrieri) if descrieri else None
        echipament_id = generate_uuid()
        model = drive.get('model', '')
        firmware = drive.get('firmware', '')
        if firmware and firmware not in model:
            model = f'{model} {firmware}'.strip()
        cursor.execute('''
            INSERT INTO echipamente (id, proiect_id, nume, producator, model, serial_number, params_json, descrieri_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            echipament_id,
            project_id,
            drive.get('nume', '') or 'Drive',
            drive.get('producator', 'Siemens') or 'Siemens',
            model,
            drive.get('serial_number', '') or '',
            json.dumps(params_dict),
            descrieri_json,
            now,
            now,
        ))
        created.append({
            'id': echipament_id,
            'nume': drive.get('nume', ''),
            'params': len(params_dict),
        })

    conn.commit()
    conn.close()

    logger.info(f"Import arhivă: {len(created)} echipamente create în proiect {project_id}")
    return jsonify({
        'message': f'{len(created)} echipamente importate',
        'count': len(created),
        'created': created,
    }), 201


# ============ PROJECT TEMPLATES CRUD ============

@projects_bp.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM project_templates ORDER BY name')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

# ============ DEFAULT TEMPLATES INIT ============

def init_default_templates():
    """Create default PIF Standard template if none exists"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) as count FROM project_templates')
    count = cursor.fetchone()['count']

    if count == 0:
        now = datetime.now().isoformat()
        template_id = generate_uuid()

        default_checklist = [
            'Verificare documentație',
            'Verificare conexiuni electrice',
            'Verificare parametri',
            'Test funcțional',
            'Probe de sarcină',
            'Întocmire raport PIF'
        ]

        default_tasks = [
            {'titlu': 'Revizuire documentație tehnică', 'prioritate': 'Normal'},
            {'titlu': 'Verificare hardware și conexiuni', 'prioritate': 'Urgent'},
            {'titlu': 'Configurare parametri sistem', 'prioritate': 'Normal'},
            {'titlu': 'Testare funcțională', 'prioritate': 'Normal'},
            {'titlu': 'Elaborare raport PIF', 'prioritate': 'Normal'}
        ]

        cursor.execute('''
            INSERT INTO project_templates (id, name, tip, default_checklist_json, default_tasks_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            template_id,
            'PIF Standard',
            'PIF',
            json.dumps(default_checklist),
            json.dumps(default_tasks),
            now
        ))

        conn.commit()
        logger.info("Created default 'PIF Standard' template")

    conn.close()


# ============ STRUCTURED IMPORT (Cowork AI debrief) ============

def _manual_session_times_local(data_str, durata_secunde):
    """Duplicate of timer._manual_session_times — avoids cross-blueprint import.
    Anchors a manual time entry at noon on the given date."""
    from datetime import timedelta
    try:
        d = datetime.fromisoformat((data_str or '')[:10])
    except (ValueError, TypeError):
        d = datetime.now()
    start = d.replace(hour=12, minute=0, second=0, microsecond=0)
    stop = start + timedelta(seconds=int(durata_secunde))
    return start.isoformat(), stop.isoformat()


@projects_bp.route('/api/import/debrief', methods=['POST'])
@login_required
def import_debrief():
    """Structured import from an external AI tool (Cowork).

    Receives a single JSON payload describing a project debrief and
    creates/updates entities in the correct dependency order:
      1. Client (upsert by name)
      2. Proiect (upsert by name+client)
      3. Echipamente
      4. Checklist categorii + items
      5. Jurnal entries
      6. Ore (timer_sessions via manual-time helper)

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
    # equipment / checklist / journal / hours (re-import would otherwise
    # double the logged time — a billing footgun).
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
                    'sumar': {'echipamente': 0, 'jurnal_entries': 0, 'ore_total_secunde': 0, 'checklist_items': 0},
                }), 200
            logger.info(f"Import debrief: prior project {prev_pid} for debrief_id={debrief_id} was deleted — allowing re-import")

    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    sumar = {
        'echipamente': 0,
        'jurnal_entries': 0,
        'ore_total_secunde': 0,
        'checklist_items': 0,
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
        # service_after (Service). The journal ROWS themselves are kept SHORT,
        # built from ore[] further below. Each block: "YYYY-MM-DD: text".
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
                    cod_proiect, pm, folder_server, data_incepere, deadline, data_crearii,
                    status, observatii, nr_comanda, nr_contract, service_before, service_after,
                    confirmat_client, client_nume_confirmare, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                proiect_data.get('deadline', ''),
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

        # ── 3. Echipamente ─────────────────────────────────────────
        for eq in (data.get('echipamente') or []):
            eq_id = eq.get('id') or generate_uuid()
            params = eq.get('params_json') or eq.get('params') or {}
            if isinstance(params, dict):
                params = json.dumps(params)
            cursor.execute('''
                INSERT INTO echipamente (id, proiect_id, nume, producator, model, serial_number, params_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                eq_id, project_id,
                eq.get('nume', ''),
                eq.get('producator', 'Altul'),
                eq.get('model', ''),
                eq.get('serial_number', ''),
                params if isinstance(params, str) else json.dumps(params),
                now, now,
            ))
            sumar['echipamente'] += 1

        # ── 4. Checklist categorii ─────────────────────────────────
        cat_name_to_id = {}
        for cat in (data.get('checklist_categorii') or []):
            cat_name = (cat.get('nume') or '').strip()
            if not cat_name:
                continue
            cursor.execute(
                'INSERT INTO checklist_categorii (proiect_id, nume, ordine, created_at) VALUES (?, ?, ?, ?)',
                (project_id, cat_name, cat.get('ordine', 0), now)
            )
            cat_name_to_id[cat_name.lower()] = cursor.lastrowid

        # ── 5. Checklist items ─────────────────────────────────────
        for item in (data.get('checklist_items') or []):
            item_id = item.get('id') or generate_uuid()
            cat_ref = (item.get('categorie') or '').strip().lower()
            cat_id = cat_name_to_id.get(cat_ref)  # None if not found or empty
            # Accept both schema variants:
            #   titlu/completed (prompt v1.1)  and  text/bifat (skill v1.2+)
            titlu = item.get('titlu') or item.get('text') or ''
            done_raw = item.get('completed', item.get('bifat', 0))
            completed = 1 if done_raw in (1, True, '1', 'true', 'True', 'da', 'yes') else 0
            cursor.execute('''
                INSERT INTO checklist_pif (id, proiect_id, titlu, completed, note, ordine, categorie_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_id, project_id,
                titlu,
                completed,
                item.get('note', ''),
                item.get('ordine', 0),
                cat_id,
            ))
            sumar['checklist_items'] += 1

        # ── 6 + 7. Timer-with-note per day ─────────────────────────
        # Each ore[] entry becomes a TIMER SESSION paired with a short NOTE
        # (activity label from ore[].descriere). The frontend pairs a jurnal entry
        # to a timer when jurnal.created_at is within ~2 min of timer.stop_time
        # (see loadJurnal in app.js), then shows ONE "timer cu notă" row — duration
        # badge + note — instead of a bare "Timer fără notă" plus a separate entry.
        # So we set the note's created_at == the session stop_time. The detailed
        # narrative already went to observatii / service_after (section 2).

        # date -> detailed jurnal text, used as the label fallback when a given
        # ore[] entry has no descriere.
        jurnal_text_by_date = {}
        for _e in (data.get('jurnal') or []):
            _t = (_e.get('continut') or _e.get('text') or '').strip()
            _d = (_e.get('data') or '')[:10]
            if _t and _d and _d not in jurnal_text_by_date:
                jurnal_text_by_date[_d] = _t

        ore_list = data.get('ore') or []
        if ore_list:
            for ore_entry in ore_list:
                try:
                    dur = int(ore_entry.get('durata_secunde') or 0)
                except (ValueError, TypeError):
                    dur = 0
                edate = ore_entry.get('data') or now[:10]
                # Short activity label: descriere -> fallback to a slice of the
                # day's detailed jurnal text -> generic "Lucru". No "— Xh" suffix:
                # the duration shows as the timer badge on the paired row.
                label = (ore_entry.get('descriere') or '').strip()
                if not label:
                    fb = jurnal_text_by_date.get(edate[:10], '')
                    label = (fb[:60].rstrip() + '…') if len(fb) > 60 else (fb or 'Lucru')
                if dur > 0:
                    # Timer session first, then the paired note (created_at = stop).
                    start, stop = _manual_session_times_local(edate, dur)
                    cursor.execute(
                        'INSERT INTO timer_sessions (id, proiect_id, start_time, stop_time, durata_secunde) '
                        'VALUES (?, ?, ?, ?, ?)',
                        (generate_uuid(), project_id, start, stop, dur)
                    )
                    sumar['ore_total_secunde'] += dur
                    note_created = stop
                else:
                    note_created = now
                cursor.execute('''
                    INSERT INTO jurnal (id, proiect_id, data, continut, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (generate_uuid(), project_id, edate, label, note_created))
                sumar['jurnal_entries'] += 1
        else:
            # No ore[] — keep a short journal row per jurnal[] entry so the day
            # log isn't lost (no hours available for these).
            for _e in (data.get('jurnal') or []):
                _t = (_e.get('continut') or _e.get('text') or '').strip()
                if not _t:
                    continue
                short = (_t[:80].rstrip() + '…') if len(_t) > 80 else _t
                cursor.execute('''
                    INSERT INTO jurnal (id, proiect_id, data, continut, created_at)
                    VALUES (?, ?, ?, ?, ?)
                ''', (generate_uuid(), project_id, (_e.get('data') or now[:10]), short, now))
                sumar['jurnal_entries'] += 1

        conn.commit()

    except Exception as e:
        conn.rollback()
        logger.exception(f"Import debrief failed: {e}")
        return jsonify({'error': f'Import failed: {e}'}), 500
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

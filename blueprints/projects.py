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
    get_app_setting, set_app_setting,
)
from scripts.parse_params import parse_for_producator

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
    limit = request.args.get('limit', 100, type=int)
    offset = request.args.get('offset', 0, type=int)

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
    data = request.json
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
    data = request.json
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
    data = request.json
    action = data.get('action')  # 'update_status' or 'delete'
    project_ids = data.get('project_ids', [])

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
    data = request.json
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
    data = request.json
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
    data = request.json or {}
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
    data = request.json or {}
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
    data = request.json
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

@projects_bp.route('/api/proiecte/<project_id>/atasamente', methods=['POST'])
@login_required
def upload_atasament(project_id):
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    attachment_id = generate_uuid()

    # Create project folder if not exists
    project_folder = os.path.join(UPLOAD_FOLDER, project_id)
    os.makedirs(project_folder, exist_ok=True)

    # Save file — sanitize the client-supplied name; never trust it for a
    # filesystem path (blocks ../ traversal and overwriting server files).
    original_name = file.filename
    safe_name = secure_filename(original_name) or ('fisier_' + attachment_id[:8])
    filepath = os.path.join(project_folder, safe_name)
    if os.path.exists(filepath):
        safe_name = attachment_id[:8] + '_' + safe_name
        filepath = os.path.join(project_folder, safe_name)
    file.save(filepath)

    # Get file size
    size = os.path.getsize(filepath)

    # Determine file type (from the original name — keeps the real extension)
    ext = os.path.splitext(original_name)[1].lower()
    tip_map = {
        '.pdf': 'PDF',
        '.jpg': 'IMG', '.jpeg': 'IMG', '.png': 'IMG',
        '.gif': 'IMG', '.bmp': 'IMG', '.webp': 'IMG',
        '.msg': 'EMAIL', '.eml': 'EMAIL',
        '.doc': 'DOC', '.docx': 'DOC',
        '.xls': 'XLS', '.xlsx': 'XLS',
        '.zip': 'ZIP', '.rar': 'ZIP'
    }
    tip = tip_map.get(ext, 'ALT')

    cursor.execute('''
        INSERT INTO atasamente (id, proiect_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (attachment_id, project_id, original_name, tip, size, now[:10], filepath))

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

@projects_bp.route('/api/clienti', methods=['POST'])
@login_required
def create_client():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    client_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO clienti (id, nume, adresa, telefon, email, contact_principal, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        client_id,
        data.get('nume', ''),
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
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

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
        data.get('nume'),
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
    data = request.json
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
    data = request.json
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

    cursor.execute('''
        UPDATE echipamente SET
            nume = COALESCE(?, nume),
            producator = COALESCE(?, producator),
            model = COALESCE(?, model),
            serial_number = COALESCE(?, serial_number),
            params_json = COALESCE(?, params_json),
            updated_at = ?
        WHERE id = ?
    ''', (
        data.get('nume'),
        data.get('producator'),
        data.get('model'),
        data.get('serial_number'),
        params_json,
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
    data = request.json
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
                # Accept observatii_pv as a fallback (older skill variants put the
                # detailed write-up there); never silently drop it.
                (proiect_data.get('observatii') or proiect_data.get('observatii_pv') or ''),
                proiect_data.get('nr_comanda', ''),
                proiect_data.get('nr_contract', ''),
                proiect_data.get('service_before', ''),
                proiect_data.get('service_after', ''),
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

        # ── 6. Jurnal ──────────────────────────────────────────────
        # Mirror the stop-with-note convention: embed the day's logged time in
        # the journal text (e.g. "... — 12h"), so each entry shows the effort.
        # Hours still go into timer_sessions (section 7) for totals/billing.
        ore_by_date = {}
        for oe in (data.get('ore') or []):
            try:
                _d = int(oe.get('durata_secunde') or 0)
            except (ValueError, TypeError):
                _d = 0
            if _d > 0:
                _dt = (oe.get('data') or '')[:10]
                ore_by_date[_dt] = ore_by_date.get(_dt, 0) + _d
        _hours_shown = set()  # annotate only the first journal entry per date

        for entry in (data.get('jurnal') or []):
            entry_id = entry.get('id') or generate_uuid()
            edate = entry.get('data') or now[:10]
            # Accept 'text' as alias for 'continut' (skill v1.2+)
            continut = (entry.get('continut') or entry.get('text') or '')
            secs = ore_by_date.get(edate[:10])
            if secs and edate[:10] not in _hours_shown:
                htxt = f"{secs / 3600:.1f}".rstrip('0').rstrip('.')
                continut = (continut.rstrip() + f"  — {htxt}h").strip()
                _hours_shown.add(edate[:10])
            cursor.execute('''
                INSERT INTO jurnal (id, proiect_id, data, continut, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                entry_id, project_id,
                edate,
                continut,
                now,
            ))
            sumar['jurnal_entries'] += 1

        # ── 7. Ore ─────────────────────────────────────────────────
        for ore_entry in (data.get('ore') or []):
            try:
                dur = int(ore_entry.get('durata_secunde') or 0)
            except (ValueError, TypeError):
                dur = 0
            if dur <= 0:
                continue
            start, stop = _manual_session_times_local(ore_entry.get('data'), dur)
            sid = generate_uuid()
            cursor.execute(
                'INSERT INTO timer_sessions (id, proiect_id, start_time, stop_time, durata_secunde) '
                'VALUES (?, ?, ?, ?, ?)',
                (sid, project_id, start, stop, dur)
            )
            sumar['ore_total_secunde'] += dur

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

import os
import uuid
import json
import functools
import time
import logging
import requests
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from io import BytesIO
from flask import Flask, request, jsonify, send_file, render_template, session, redirect, url_for
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from database import get_db, init_db, row_to_dict

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))
CORS(app)

# ============ PHASE 2a: STRUCTURED LOGGING ============
LOGS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
os.makedirs(LOGS_FOLDER, exist_ok=True)

def setup_logging():
    logger = logging.getLogger('pif_dashboard')
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Rotating file handler - 10 files, 1MB each
    handler = RotatingFileHandler(
        os.path.join(LOGS_FOLDER, 'app.log'),
        maxBytes=1024 * 1024,  # 1MB
        backupCount=10
    )
    handler.setLevel(logging.INFO)
    
    # Format: [YYYY-MM-DD HH:MM:SS] LEVEL - message
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger

logger = setup_logging()

# ============ PHASE 2a: API RATE LIMITING ============
rate_limit_store = {}  # {ip: [(timestamp, count), ...]}
RATE_LIMIT = 60  # requests per minute
RATE_WINDOW = 60  # seconds

def check_rate_limit():
    """Simple token-bucket rate limiter. Returns True if allowed, False if exceeded."""
    client_ip = request.remote_addr or '127.0.0.1'
    now = time.time()
    
    # Clean old entries
    if client_ip in rate_limit_store:
        rate_limit_store[client_ip] = [
            (ts, count) for ts, count in rate_limit_store[client_ip]
            if now - ts < RATE_WINDOW
        ]
    
    # Count requests in current window
    request_count = 0
    if client_ip in rate_limit_store:
        request_count = sum(count for ts, count in rate_limit_store[client_ip])
    
    if request_count >= RATE_LIMIT:
        return False
    
    # Record this request
    if client_ip not in rate_limit_store:
        rate_limit_store[client_ip] = []
    rate_limit_store[client_ip].append((now, 1))
    
    return True

# Phase 2c: One-time startup initialization
_startup_initialized = False

@app.before_request
def before_request_func():
    global _startup_initialized

    # Run one-time initialization (migrations, templates)
    if not _startup_initialized:
        with app.app_context():
            init_db()
            try:
                init_default_templates()
            except:
                pass  # Templates may already exist
        _startup_initialized = True
        logger.info("PIF Dashboard initialized")

    # Apply rate limiting to all /api/* routes except login
    if request.path.startswith('/api/') and request.path != '/api/login':
        if not check_rate_limit():
            logger.warning(f"Rate limit exceeded for IP: {request.remote_addr} on {request.path}")
            return jsonify({'error': 'Rate limit exceeded. Maximum 60 requests per minute.', 'retry_after': RATE_WINDOW}), 429
    
    # Log all requests
    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - IP: {request.remote_addr}")

@app.after_request
def after_request_func(response):
    # Log API responses
    if request.path.startswith('/api/'):
        logger.info(f"{request.method} {request.path} - Status: {response.status_code}")
    return response

# ============ END PHASE 2a SETUP ============

# ============ PHASE 2c: TELEGRAM NOTIFICATIONS ============
TELEGRAM_BOT_TOKEN = os.environ.get('PIF_TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.environ.get('PIF_TELEGRAM_CHAT_ID', '')

def send_telegram_message(message):
    """Send message via Telegram bot"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram bot token or chat ID not configured")
        return False
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info(f"Telegram notification sent: {message[:50]}...")
            return True
        else:
            logger.error(f"Telegram API error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False

def notify_project_completed(project_name, project_id):
    """Send notification when project is marked as completed"""
    message = f"✅ <b>Proiect Finalizat</b>\n\n"
    message += f"📁 {project_name}\n"
    message += f"🆔 {project_id}\n"
    message += f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    return send_telegram_message(message)

def notify_deadline_approaching(project_name, project_id, deadline):
    """Send notification when project deadline is within 48 hours"""
    message = f"⏰ <b>Deadline Apropiat</b>\n\n"
    message += f"📁 {project_name}\n"
    message += f"🆔 {project_id}\n"
    message += f"📅 Termen: {deadline}\n"
    message += f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    return send_telegram_message(message)

def check_deadline_notifications():
    """Check all projects for approaching deadlines and send notifications"""
    conn = get_db()
    cursor = conn.cursor()
    
    now = datetime.now()
    deadline_threshold = now + timedelta(hours=48)
    
    cursor.execute('''
        SELECT id, nume, deadline, notify_on_deadline 
        FROM proiecte 
        WHERE status != 'finalizat' 
        AND deadline IS NOT NULL 
        AND deadline != ''
        AND notify_on_deadline = 1
    ''')
    
    for row in cursor.fetchall():
        try:
            deadline_date = datetime.strptime(row['deadline'], '%Y-%m-%d')
            if deadline_date <= deadline_threshold and deadline_date >= now:
                notify_deadline_approaching(row['nume'], row['id'], row['deadline'])
        except (ValueError, TypeError):
            continue
    
    conn.close()


# PIN configuration - use environment variable
def get_hashed_pin():
    """Get hashed PIN from environment variable"""
    pin = os.environ.get('PIF_DASHBOARD_PIN', 'pif2024')
    # Generate hash on first call if not cached
    if not hasattr(get_hashed_pin, '_hash'):
        get_hashed_pin._hash = generate_password_hash(pin)
    return get_hashed_pin._hash

# Login required decorator
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ============ TELEGRAM NOTIFICATIONS ============

@app.route('/api/notify/telegram', methods=['POST'])
@login_required
def test_telegram_notification():
    """Test endpoint to send a Telegram notification"""
    data = request.json or {}
    message = data.get('message', 'Test from PIF Dashboard')
    
    if send_telegram_message(message):
        return jsonify({'success': True, 'message': 'Notification sent'})
    else:
        return jsonify({'error': 'Failed to send notification. Check bot token and chat ID configuration.'}), 500

# ============ END TELEGRAM NOTIFICATIONS ============

# Serve the login page
@app.route('/login')
def login_page():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    return render_template('login.html')

# Login endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    pin = data.get('pin', '')
    
    if check_password_hash(get_hashed_pin(), pin):
        session['authenticated'] = True
        logger.info(f"Login successful for IP: {request.remote_addr}")
        return jsonify({'success': True})
    logger.warning(f"Login failed for IP: {request.remote_addr}")
    return jsonify({'error': 'Invalid PIN'}), 401

# Logout endpoint
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_page'))

# Serve the frontend
@app.route('/')
@login_required
def index():
    return render_template('index.html')

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def generate_uuid():
    return str(uuid.uuid4())

# ============ PROJECTS ============

@app.route('/api/proiecte', methods=['GET'])
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

@app.route('/api/proiecte', methods=['POST'])
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

@app.route('/api/proiecte/<project_id>', methods=['GET'])
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

@app.route('/api/proiecte/<project_id>', methods=['PUT'])
@login_required
def update_proiect(project_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # Get current project status for notification check
    cursor.execute('SELECT status, nume, notify_on_complete FROM proiecte WHERE id = ?', (project_id,))
    current = cursor.fetchone()
    old_status = current['status'] if current else None
    project_name = current['nume'] if current else ''
    notify_on_complete = current['notify_on_complete'] if current else 1
    
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
    
    # Phase 2c: Check if project was marked as completed
    new_status = data.get('status')
    if (old_status != 'finalizat' and new_status == 'finalizat' and notify_on_complete):
        notify_project_completed(project_name, project_id)
    
    conn.close()
    
    # Phase 2c: Check deadline notifications after update
    check_deadline_notifications()
    
    logger.info(f"Project updated: {project_id}")
    return jsonify({'message': 'Project updated'})

@app.route('/api/proiecte/<project_id>', methods=['DELETE'])
@login_required
def delete_proiect(project_id):
    conn = get_db()
    cursor = conn.cursor()
    try:
        tables = ['tasks', 'checklist_pif', 'jurnal', 'timer_sessions', 'atasamente', 'echipamente']
        for table in tables:
            cursor.execute(f'DELETE FROM {table} WHERE proiect_id = ?', (project_id,))
        cursor.execute('DELETE FROM proiecte WHERE id = ?', (project_id,))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error deleting project {project_id}: {e}")
        return jsonify({'error': str(e)}), 500
    conn.close()
    logger.info(f"Project deleted: {project_id}")
    return jsonify({'message': 'Project deleted'})

# ============ BATCH OPERATIONS ============

@app.route('/api/proiecte/batch', methods=['POST'])
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
                # Delete related data first
                tables = ['tasks', 'checklist_pif', 'jurnal', 'timer_sessions', 'atasamente', 'echipamente']
                for table in tables:
                    cursor.execute(f'DELETE FROM {table} WHERE proiect_id = ?', (pid,))
                cursor.execute('DELETE FROM proiecte WHERE id = ?', (pid,))
            
            conn.commit()
            logger.info(f"Batch deleted {len(project_ids)} projects")
            return jsonify({'message': f'{len(project_ids)} projects deleted'})
        
        else:
            return jsonify({'error': 'Invalid action'}), 400
    
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Batch operation error: {e}")
        return jsonify({'error': str(e)}), 500

# ============ TASKS ============

@app.route('/api/proiecte/<project_id>/tasks', methods=['GET'])
@login_required
def get_tasks(project_id):
    conn = get_db()
    cursor = conn.cursor()
    # Phase 2c: Sort by ordine for drag-and-drop reordering
    cursor.execute('SELECT * FROM tasks WHERE proiect_id = ? ORDER BY ordine ASC, created_at DESC', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@app.route('/api/proiecte/<project_id>/tasks', methods=['POST'])
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
        INSERT INTO tasks (id, proiect_id, titlu, status, prioritate, data_scadenta, data_finalizare, ordine, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        task_id,
        project_id,
        data.get('titlu', ''),
        data.get('status', 'to_do'),
        data.get('prioritate', 'normal'),
        data.get('data_scadenta', ''),
        data.get('data_finalizare', ''),
        max_ordine + 1,
        now
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'id': task_id}), 201

@app.route('/api/tasks/<task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    # Phase 2c: Support ordine field for drag-and-drop reordering
    cursor.execute('''
        UPDATE tasks SET
            titlu = COALESCE(?, titlu),
            status = COALESCE(?, status),
            prioritate = COALESCE(?, prioritate),
            data_scadenta = COALESCE(?, data_scadenta),
            data_finalizare = COALESCE(?, data_finalizare),
            ordine = COALESCE(?, ordine)
        WHERE id = ?
    ''', (
        data.get('titlu'),
        data.get('status'),
        data.get('prioritate'),
        data.get('data_scadenta'),
        data.get('data_finalizare'),
        data.get('ordine'),
        task_id
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Task updated'})

@app.route('/api/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Task deleted'})

# ============ GLOBAL TASKS ============

@app.route('/api/global-tasks', methods=['GET'])
@login_required
def get_global_tasks():
    conn = get_db()
    cursor = conn.cursor()

    status = request.args.get('status')
    prioritate = request.args.get('prioritate')
    categorie = request.args.get('categorie')
    arhiva = request.args.get('arhiva')

    query = 'SELECT * FROM global_tasks WHERE 1=1'
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

@app.route('/api/global-tasks', methods=['POST'])
@login_required
def create_global_task():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    now = datetime.now().isoformat()
    task_id = data.get('id') or generate_uuid()

    cursor.execute('''
        INSERT INTO global_tasks (id, titlu, descriere, prioritate, status, categorie, data_scadenta, data_finalizare, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        now
    ))

    conn.commit()
    conn.close()

    return jsonify({'id': task_id}), 201

@app.route('/api/global-tasks/<task_id>', methods=['GET'])
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

@app.route('/api/global-tasks/<task_id>', methods=['PUT'])
@login_required
def update_global_task(task_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

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
        now,
        task_id
    ))

    conn.commit()
    conn.close()

    return jsonify({'message': 'Task updated'})

@app.route('/api/global-tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_global_task(task_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM global_tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Task deleted'})

# ============ CHECKLIST PIF ============

@app.route('/api/proiecte/<project_id>/checklist', methods=['GET'])
@login_required
def get_checklist(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM checklist_pif WHERE proiect_id = ? ORDER BY ordine', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@app.route('/api/proiecte/<project_id>/checklist', methods=['POST'])
@login_required
def create_checklist_item(project_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    item_id = data.get('id') or generate_uuid()
    
    cursor.execute('''
        INSERT INTO checklist_pif (id, proiect_id, titlu, completed, note, ordine)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        item_id,
        project_id,
        data.get('titlu', ''),
        data.get('completed', 0),
        data.get('note', ''),
        data.get('ordine', 0)
    ))
    
    conn.commit()
    conn.close()
    
    return jsonify({'id': item_id}), 201

@app.route('/api/checklist/<item_id>', methods=['PUT'])
@login_required
def update_checklist_item(item_id):
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
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

@app.route('/api/checklist/<item_id>', methods=['DELETE'])
@login_required
def delete_checklist_item(item_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM checklist_pif WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Checklist item deleted'})

# ============ JURNAL ============

@app.route('/api/proiecte/<project_id>/jurnal', methods=['GET'])
@login_required
def get_jurnal(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jurnal WHERE proiect_id = ? ORDER BY data DESC', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@app.route('/api/proiecte/<project_id>/jurnal', methods=['POST'])
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

@app.route('/api/jurnal/<entry_id>', methods=['DELETE'])
@login_required
def delete_jurnal_entry(entry_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM jurnal WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Jurnal entry deleted'})

# ============ TIMER ============

@app.route('/api/proiecte/<project_id>/timer/start', methods=['POST'])
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

@app.route('/api/proiecte/<project_id>/timer/stop', methods=['POST'])
@login_required
def stop_timer(project_id):
    conn = get_db()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    
    # Find active session
    cursor.execute('''
        SELECT * FROM timer_sessions 
        WHERE proiect_id = ? AND stop_time IS NULL 
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

@app.route('/api/timer/<session_id>', methods=['DELETE'])
@login_required
def delete_timer_session(session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM timer_sessions WHERE id = ?', (session_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Timer session deleted'})

@app.route('/api/proiecte/<project_id>/timer', methods=['GET'])
@login_required
def get_timer_sessions(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM timer_sessions 
        WHERE proiect_id = ? 
        ORDER BY start_time DESC
    ''', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    
    sessions = [row_to_dict(row) for row in rows]
    total = sum(s['durata_secunde'] or 0 for s in sessions)
    
    return jsonify({'sessions': sessions, 'total_secunde': total})

# ============ ATTACHMENTS ============

@app.route('/api/proiecte/<project_id>/atasamente', methods=['POST'])
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
    
    # Save file
    filename = file.filename
    filepath = os.path.join(project_folder, filename)
    file.save(filepath)
    
    # Get file size
    size = os.path.getsize(filepath)
    
    # Determine file type
    ext = os.path.splitext(filename)[1].lower()
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
    ''', (attachment_id, project_id, filename, tip, size, now[:10], filepath))
    
    conn.commit()
    conn.close()
    
    return jsonify({'id': attachment_id}), 201

@app.route('/api/proiecte/<project_id>/atasamente', methods=['GET'])
@login_required
def get_atasamente(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM atasamente WHERE proiect_id = ? ORDER BY data DESC', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@app.route('/api/atasamente/<attachment_id>/download', methods=['GET'])
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

@app.route('/api/atasamente/<attachment_id>', methods=['DELETE'])
@login_required
def delete_atasament(attachment_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT cale_locala FROM atasamente WHERE id = ?', (attachment_id,))
    row = cursor.fetchone()
    
    if row:
        filepath = row['cale_locala']
        if os.path.exists(filepath):
            os.remove(filepath)
        
        cursor.execute('DELETE FROM atasamente WHERE id = ?', (attachment_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Attachment deleted'})

# ============ STATS ============

@app.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'in_lucru' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN status = 'finalizat' THEN 1 ELSE 0 END) as finished
        FROM proiecte
    """)
    row = cursor.fetchone()
    conn.close()
    return jsonify({
        'total': row['total'] or 0,
        'active': row['active'] or 0,
        'finished': row['finished'] or 0
    })

@app.route('/api/stats/extended', methods=['GET'])
@login_required
def get_extended_stats():
    """Extended statistics for Chart.js dashboard"""
    conn = get_db()
    cursor = conn.cursor()

    # Projects by status
    cursor.execute("""
        SELECT status, COUNT(*) as count
        FROM proiecte
        GROUP BY status
    """)
    by_status = [{'status': row['status'], 'count': row['count']} for row in cursor.fetchall()]

    # Projects by manufacturer
    cursor.execute("""
        SELECT producator, COUNT(*) as count
        FROM proiecte
        GROUP BY producator
        ORDER BY count DESC
    """)
    by_manufacturer = [{'producator': row['producator'], 'count': row['count']} for row in cursor.fetchall()]

    # Projects per month (last 12 months)
    cursor.execute("""
        SELECT
            strftime('%Y-%m', created_at) as month,
            COUNT(*) as count
        FROM proiecte
        WHERE created_at >= date('now', '-12 months')
        GROUP BY month
        ORDER BY month ASC
    """)
    by_month = [{'month': row['month'], 'count': row['count']} for row in cursor.fetchall()]

    # Billable hours per project
    cursor.execute("""
        SELECT
            p.id,
            p.nume,
            COALESCE(SUM(t.durata_secunde), 0) as total_seconds
        FROM proiecte p
        LEFT JOIN timer_sessions t ON p.id = t.proiect_id AND t.durata_secunde IS NOT NULL
        GROUP BY p.id
        HAVING total_seconds > 0
        ORDER BY total_seconds DESC
        LIMIT 20
    """)
    hours_per_project = [{
        'id': row['id'],
        'nume': row['nume'],
        'hours': round(row['total_seconds'] / 3600, 2)
    } for row in cursor.fetchall()]

    # Total billable hours
    cursor.execute("""
        SELECT COALESCE(SUM(durata_secunde), 0) as total
        FROM timer_sessions
        WHERE durata_secunde IS NOT NULL
    """)
    total_hours_row = cursor.fetchone()
    total_hours = round(total_hours_row['total'] / 3600, 2) if total_hours_row else 0

    conn.close()

    return jsonify({
        'by_status': by_status,
        'by_manufacturer': by_manufacturer,
        'by_month': by_month,
        'hours_per_project': hours_per_project,
        'total_billable_hours': total_hours
    })

# ============ PHASE 2b: EXCEL EXPORT ============

@app.route('/api/export/excel', methods=['GET'])
@login_required
def export_excel():
    """Export data to Excel format"""
    export_type = request.args.get('type', 'projects')
    
    conn = get_db()
    cursor = conn.cursor()
    
    wb = Workbook()
    
    # Define styles
    header_font = Font(bold=True, color='FFFFFF')
    header_fill = PatternFill(start_color='3B82F6', end_color='3B82F6', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center')
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    def style_header(ws, row=1):
        for cell in ws[row]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
    
    def auto_width(ws):
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
    
    if export_type == 'projects':
        ws = wb.active
        ws.title = 'Proiecte'
        
        headers = ['Nume', 'Client', 'Tip', 'Producător', 'Status', 'Data Start', 'Deadline', 'Locație']
        ws.append(headers)
        style_header(ws)
        
        cursor.execute('''
            SELECT nume, client, tip, producator, status, data_incepere, deadline, locatie
            FROM proiecte ORDER BY created_at DESC
        ''')
        for row in cursor.fetchall():
            # Map status to Romanian
            status_map = {'in_lucru': 'În Lucru', 'finalizat': 'Finalizat', 'blocat': 'Blocat', 'in_așteptare': 'În Așteptare'}
            row_data = list(row)
            row_data[4] = status_map.get(row_data[4], row_data[4])
            ws.append(row_data)
        
        auto_width(ws)
        
    elif export_type == 'tasks':
        ws = wb.active
        ws.title = 'Task-uri'
        
        headers = ['Proiect', 'Task', 'Status', 'Prioritate', 'Data Scadență', 'Data Finalizare']
        ws.append(headers)
        style_header(ws)
        
        cursor.execute('''
            SELECT p.nume, t.titlu, t.status, t.prioritate, t.data_scadenta, t.data_finalizare
            FROM tasks t
            JOIN proiecte p ON t.proiect_id = p.id
            ORDER BY t.created_at DESC
        ''')
        for row in cursor.fetchall():
            # Map status to Romanian
            status_map = {'to_do': 'To Do', 'in_lucru': 'În Lucru', 'done': 'Finalizat'}
            priority_map = {'urgent': 'Urgent', 'normal': 'Normal', 'minor': 'Minor'}
            row_data = list(row)
            row_data[2] = status_map.get(row_data[2], row_data[2])
            row_data[3] = priority_map.get(row_data[3], row_data[3])
            ws.append(row_data)
        
        auto_width(ws)
        
    elif export_type == 'hours':
        ws = wb.active
        ws.title = 'Ore'
        
        headers = ['Proiect', 'Start', 'Stop', 'Durată (ore)']
        ws.append(headers)
        style_header(ws)
        
        cursor.execute('''
            SELECT p.nume, t.start_time, t.stop_time, 
                   ROUND(CAST(t.durata_secunde AS FLOAT) / 3600, 2) as hours
            FROM timer_sessions t
            JOIN proiecte p ON t.proiect_id = p.id
            WHERE t.durata_secunde IS NOT NULL
            ORDER BY t.start_time DESC
        ''')
        for row in cursor.fetchall():
            ws.append(list(row))
        
        auto_width(ws)
    
    conn.close()
    
    # Save to BytesIO
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f'pif_export_{export_type}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    logger.info(f"Excel export: {export_type} - {filename}")
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )

# ============ PHASE 2c: PDF EXPORT ============

@app.route('/api/export/pdf', methods=['GET'])
@login_required
def export_pdf():
    """Export project to PDF format"""
    project_id = request.args.get('project_id')
    
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Get project info
    cursor.execute('SELECT * FROM proiecte WHERE id = ?', (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return jsonify({'error': 'Project not found'}), 404
    
    project_dict = row_to_dict(project)
    
    # Get tasks
    cursor.execute('SELECT * FROM tasks WHERE proiect_id = ? ORDER BY ordine ASC', (project_id,))
    tasks = [row_to_dict(row) for row in cursor.fetchall()]
    
    # Get checklist
    cursor.execute('SELECT * FROM checklist_pif WHERE proiect_id = ? ORDER BY ordine ASC', (project_id,))
    checklist = [row_to_dict(row) for row in cursor.fetchall()]
    
    # Get journal entries
    cursor.execute('SELECT * FROM jurnal WHERE proiect_id = ? ORDER BY data DESC', (project_id,))
    jurnal = [row_to_dict(row) for row in cursor.fetchall()]
    
    # Get equipment
    cursor.execute('SELECT * FROM echipamente WHERE proiect_id = ?', (project_id,))
    echipamente = [row_to_dict(row) for row in cursor.fetchall()]
    
    # Get timer sessions
    cursor.execute('SELECT * FROM timer_sessions WHERE proiect_id = ?', (project_id,))
    timer_sessions = [row_to_dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Calculate total hours
    total_seconds = sum(ts['durata_secunde'] or 0 for ts in timer_sessions)
    total_hours = total_seconds / 3600
    
    # Status mapping
    status_map = {'in_lucru': 'În Lucru', 'finalizat': 'Finalizat', 'blocat': 'Blocat', 'in_așteptare': 'În Așteptare'}
    task_status_map = {'to_do': 'To Do', 'in_lucru': 'În Lucru', 'done': 'Finalizat'}
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=20, alignment=TA_CENTER)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=12, spaceBefore=15, spaceAfter=10)
    normal_style = styles['Normal']
    
    elements = []
    
    # Header
    elements.append(Paragraph(f"Raport Proiect: {project_dict.get('nume', '')}", title_style))
    elements.append(Spacer(1, 10))
    
    # Project Info Table
    project_info = [
        ['Client:', project_dict.get('client', '-')],
        ['Tip:', project_dict.get('tip', '-')],
        ['Producător:', project_dict.get('producator', '-')],
        ['Status:', status_map.get(project_dict.get('status', ''), project_dict.get('status', '-'))],
        ['Data Începere:', project_dict.get('data_incepere', '-')],
        ['Deadline:', project_dict.get('deadline', '-')],
        ['Locație:', project_dict.get('locatie', '-')],
        ['Nr. Comandă:', project_dict.get('nr_comanda', '-')],
        ['Nr. Contract:', project_dict.get('nr_contract', '-')],
    ]
    
    info_table = Table(project_info, colWidths=[5*cm, 10*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))
    
    # Equipment Section
    if echipamente:
        elements.append(Paragraph("Echipamente", heading_style))
        equip_data = [['Nume', 'Producător', 'Model', 'Serial Number']]
        for eq in echipamente:
            equip_data.append([
                eq.get('nume', '-'),
                eq.get('producator', '-'),
                eq.get('model', '-'),
                eq.get('serial_number', '-')
            ])
        equip_table = Table(equip_data, colWidths=[5*cm, 4*cm, 4*cm, 3*cm])
        equip_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(equip_table)
        elements.append(Spacer(1, 15))
    
    # Tasks Section
    if tasks:
        elements.append(Paragraph("Task-uri", heading_style))
        task_data = [['#', 'Titlu', 'Status', 'Prioritate']]
        for i, task in enumerate(tasks, 1):
            task_data.append([
                str(i),
                task.get('titlu', '-'),
                task_status_map.get(task.get('status', ''), task.get('status', '-')),
                task.get('prioritate', '-').capitalize()
            ])
        task_table = Table(task_data, colWidths=[1*cm, 10*cm, 3*cm, 2*cm])
        task_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(task_table)
        elements.append(Spacer(1, 15))
    
    # Checklist Section
    if checklist:
        elements.append(Paragraph("Checklist PIF", heading_style))
        check_data = [['✓', 'Titlu', 'Completat']]
        for item in checklist:
            check_mark = '✓' if item.get('completed') else '○'
            check_data.append([
                check_mark,
                item.get('titlu', '-'),
                'Da' if item.get('completed') else 'Nu'
            ])
        check_table = Table(check_data, colWidths=[1.5*cm, 12*cm, 2.5*cm])
        check_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(check_table)
        elements.append(Spacer(1, 15))
    
    # Journal Section
    if jurnal:
        elements.append(Paragraph("Jurnal de Lucru", heading_style))
        for entry in jurnal[:20]:  # Limit to 20 entries
            elements.append(Paragraph(f"<b>{entry.get('data', '-')}</b>: {entry.get('continut', '-')}", normal_style))
        elements.append(Spacer(1, 15))
    
    # Timer Summary
    elements.append(Paragraph("Timer Summary", heading_style))
    elements.append(Paragraph(f"Total ore lucrate: {total_hours:.2f} ore", normal_style))
    
    # Build PDF
    doc.build(elements)
    
    buffer.seek(0)
    filename = f"pif_report_{project_dict.get('nume', 'project').replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    logger.info(f"PDF export: {filename}")
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/export/pdf/all', methods=['GET'])
@login_required
def export_all_projects_pdf():
    """Export summary of all projects to PDF"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM proiecte ORDER BY created_at DESC')
    projects = [row_to_dict(row) for row in cursor.fetchall()]
    conn.close()
    
    status_map = {'in_lucru': 'În Lucru', 'finalizat': 'Finalizat', 'blocat': 'Blocat', 'in_așteptare': 'În Așteptare'}
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, spaceAfter=20, alignment=TA_CENTER)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=12, spaceBefore=15, spaceAfter=10)
    
    elements = []
    elements.append(Paragraph("Raport Sumar Proiecte PIF", title_style))
    elements.append(Spacer(1, 10))
    
    # Summary table
    summary_data = [['#', 'Nume', 'Client', 'Tip', 'Status', 'Deadline']]
    for i, proj in enumerate(projects, 1):
        summary_data.append([
            str(i),
            proj.get('nume', '-')[:30],
            proj.get('client', '-')[:20],
            proj.get('tip', '-'),
            status_map.get(proj.get('status', ''), proj.get('status', '-')),
            proj.get('deadline', '-')
        ])
    
    summary_table = Table(summary_data, colWidths=[1*cm, 5*cm, 3.5*cm, 2*cm, 3*cm, 2.5*cm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(summary_table)
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"pif_all_projects_{datetime.now().strftime('%Y%m%d')}.pdf"
    logger.info(f"PDF export all projects: {filename}")
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# ============ END PDF EXPORT ============

# ============ BACKUP / RESTORE ============

@app.route('/api/backup', methods=['GET'])
@login_required
def backup_database():
    conn = get_db()
    cursor = conn.cursor()
    
    backup = {}
    
    tables = ['proiecte', 'tasks', 'checklist_pif', 'jurnal', 'timer_sessions', 'atasamente', 'global_tasks', 'clienti', 'echipamente', 'project_templates']
    for table in tables:
        cursor.execute(f'SELECT * FROM {table}')
        rows = cursor.fetchall()
        backup[table] = [row_to_dict(row) for row in rows]
    
    conn.close()
    
    return jsonify(backup)

@app.route('/api/restore', methods=['POST'])
@login_required
def restore_database():
    data = request.json
    
    conn = get_db()
    cursor = conn.cursor()
    
    try:
        # Clear existing data
        tables = ['proiecte', 'tasks', 'checklist_pif', 'jurnal', 'timer_sessions', 'atasamente', 'global_tasks', 'clienti', 'echipamente', 'project_templates']
        for table in tables:
            cursor.execute(f'DELETE FROM {table}')

        conn.execute('BEGIN TRANSACTION')
        # Restore proiecte
        for p in data.get('proiecte', []):
            cursor.execute('''
                INSERT INTO proiecte (id, tip, nume, client, locatie, echipament_principal, producator,
                    cod_proiect, pm, folder_server, data_incepere, deadline, data_crearii,
                    status, observatii, nr_comanda, nr_contract, service_before, service_after,
                    confirmat_client, client_nume_confirmare, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                p.get('id'), p.get('tip'), p.get('nume'), p.get('client'), p.get('locatie'),
                p.get('echipament_principal'), p.get('producator'), p.get('cod_proiect'),
                p.get('pm'), p.get('folder_server'), p.get('data_incepere'), p.get('deadline'),
                p.get('data_crearii'), p.get('status'), p.get('observatii'), p.get('nr_comanda'),
                p.get('nr_contract'), p.get('service_before'), p.get('service_after'),
                p.get('confirmat_client', 0), p.get('client_nume_confirmare'),
                p.get('created_at'), p.get('updated_at')
            ))
        
        # Restore tasks
        for t in data.get('tasks', []):
            cursor.execute('''
                INSERT INTO tasks (id, proiect_id, titlu, status, prioritate, data_scadenta, data_finalizare, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t.get('id'), t.get('proiect_id'), t.get('titlu'), t.get('status'),
                  t.get('prioritate'), t.get('data_scadenta'), t.get('data_finalizare'), t.get('created_at')))
        
        # Restore checklist
        for c in data.get('checklist_pif', []):
            cursor.execute('''
                INSERT INTO checklist_pif (id, proiect_id, titlu, completed, note, ordine)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (c.get('id'), c.get('proiect_id'), c.get('titlu'), c.get('completed'),
                  c.get('note'), c.get('ordine', 0)))
        
        # Restore jurnal
        for j in data.get('jurnal', []):
            cursor.execute('''
                INSERT INTO jurnal (id, proiect_id, data, continut, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (j.get('id'), j.get('proiect_id'), j.get('data'), j.get('continut'), j.get('created_at')))
        
        # Restore timer_sessions
        for ts in data.get('timer_sessions', []):
            cursor.execute('''
                INSERT INTO timer_sessions (id, proiect_id, start_time, stop_time, durata_secunde)
                VALUES (?, ?, ?, ?, ?)
            ''', (ts.get('id'), ts.get('proiect_id'), ts.get('start_time'),
                  ts.get('stop_time'), ts.get('durata_secunde')))
        
        # Restore atasamente (paths need to exist)
        for a in data.get('atasamente', []):
            if os.path.exists(a.get('cale_locala', '')):
                cursor.execute('''
                    INSERT INTO atasamente (id, proiect_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (a.get('id'), a.get('proiect_id'), a.get('nume_fisier'), a.get('tip_fisier'),
                      a.get('dimensiune'), a.get('data'), a.get('cale_locala')))
        
        # Restore global_tasks
        for gt in data.get('global_tasks', []):
            cursor.execute('''
                INSERT INTO global_tasks (id, titlu, descriere, prioritate, status, categorie, data_scadenta, data_finalizare, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (gt.get('id'), gt.get('titlu'), gt.get('descriere'), gt.get('prioritate'),
                  gt.get('status'), gt.get('categorie'), gt.get('data_scadenta'),
                  gt.get('data_finalizare'), gt.get('created_at'), gt.get('updated_at')))
        
        # Restore clienti
        for c in data.get('clienti', []):
            cursor.execute('''
                INSERT INTO clienti (id, nume, adresa, telefon, email, contact_principal, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (c.get('id'), c.get('nume'), c.get('adresa'), c.get('telefon'),
                  c.get('email'), c.get('contact_principal'), c.get('note'), c.get('created_at')))
        
        # Restore echipamente
        for e in data.get('echipamente', []):
            cursor.execute('''
                INSERT INTO echipamente (id, proiect_id, nume, producator, model, serial_number, params_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (e.get('id'), e.get('proiect_id'), e.get('nume'), e.get('producator'),
                  e.get('model'), e.get('serial_number'), e.get('params_json'),
                  e.get('created_at'), e.get('updated_at')))
        
        # Restore project_templates
        for t in data.get('project_templates', []):
            cursor.execute('''
                INSERT INTO project_templates (id, name, tip, default_checklist_json, default_tasks_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (t.get('id'), t.get('name'), t.get('tip'), t.get('default_checklist_json'),
                  t.get('default_tasks_json'), t.get('created_at')))
        
        conn.commit()
        conn.close()
        
        logger.info("Database restored successfully")
        return jsonify({'message': 'Database restored successfully'})
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error restoring database: {e}")
        return jsonify({'error': str(e)}), 500

# ============ PHASE 2a: CLIENTI CRUD ============

@app.route('/api/clienti', methods=['GET'])
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

@app.route('/api/clienti', methods=['POST'])
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

@app.route('/api/clienti/<client_id>', methods=['GET'])
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

@app.route('/api/clienti/<client_id>', methods=['PUT'])
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

@app.route('/api/clienti/<client_id>', methods=['DELETE'])
@login_required
def delete_client(client_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM clienti WHERE id = ?', (client_id,))
    conn.commit()
    conn.close()
    
    logger.info(f"Client deleted: {client_id}")
    return jsonify({'message': 'Client deleted'})

# ============ PHASE 2a: ECHIPAMENTE CRUD ============

@app.route('/api/proiecte/<project_id>/echipamente', methods=['GET'])
@login_required
def get_echipamente(project_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM echipamente WHERE proiect_id = ? ORDER BY created_at DESC', (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@app.route('/api/proiecte/<project_id>/echipamente', methods=['POST'])
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

@app.route('/api/echipamente/<echipament_id>', methods=['GET'])
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

@app.route('/api/echipamente/<echipament_id>', methods=['PUT'])
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

@app.route('/api/echipamente/<echipament_id>', methods=['DELETE'])
@login_required
def delete_echipament(echipament_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM echipamente WHERE id = ?', (echipament_id,))
    conn.commit()
    conn.close()
    
    logger.info(f"Equipment deleted: {echipament_id}")
    return jsonify({'message': 'Equipment deleted'})

# ============ PHASE 2a: PROJECT TEMPLATES CRUD ============

@app.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM project_templates ORDER BY name')
    rows = cursor.fetchall()
    conn.close()
    return jsonify([row_to_dict(row) for row in rows])

@app.route('/api/templates', methods=['POST'])
@login_required
def create_template():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    template_id = data.get('id') or generate_uuid()
    
    cursor.execute('''
        INSERT INTO project_templates (id, name, tip, default_checklist_json, default_tasks_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        template_id,
        data.get('name', ''),
        data.get('tip', 'PIF'),
        json.dumps(data.get('default_checklist', [])),
        json.dumps(data.get('default_tasks', [])),
        now
    ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Template created: {template_id} - {data.get('name', '')}")
    return jsonify({'id': template_id, 'message': 'Template created'}), 201

@app.route('/api/templates/<template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM project_templates WHERE id = ?', (template_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row is None:
        return jsonify({'error': 'Template not found'}), 404
    
    return jsonify(row_to_dict(row))

@app.route('/api/templates/<template_id>', methods=['DELETE'])
@login_required
def delete_template(template_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM project_templates WHERE id = ?', (template_id,))
    conn.commit()
    conn.close()
    
    logger.info(f"Template deleted: {template_id}")
    return jsonify({'message': 'Template deleted'})

@app.route('/api/templates/create-from-project/<project_id>', methods=['POST'])
@login_required
def create_template_from_project(project_id):
    """Create a new template from an existing project's checklist and tasks"""
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    now = datetime.now().isoformat()
    template_id = generate_uuid()
    
    # Get project info
    cursor.execute('SELECT tip FROM proiecte WHERE id = ?', (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return jsonify({'error': 'Project not found'}), 404
    
    # Get checklist items
    cursor.execute('SELECT titlu FROM checklist_pif WHERE proiect_id = ?', (project_id,))
    checklist_items = [row['titlu'] for row in cursor.fetchall()]
    
    # Get tasks
    cursor.execute('SELECT titlu, prioritate FROM tasks WHERE proiect_id = ?', (project_id,))
    task_items = [{'titlu': row['titlu'], 'prioritate': row['prioritate']} for row in cursor.fetchall()]
    
    cursor.execute('''
        INSERT INTO project_templates (id, name, tip, default_checklist_json, default_tasks_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        template_id,
        data.get('name', 'Template from Project'),
        project['tip'],
        json.dumps(checklist_items),
        json.dumps(task_items),
        now
    ))
    
    conn.commit()
    conn.close()
    
    logger.info(f"Template created from project {project_id}: {template_id}")
    return jsonify({'id': template_id, 'message': 'Template created from project'}), 201

# ============ INIT DEFAULT TEMPLATES ============

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

if __name__ == '__main__':
    init_db()
    init_default_templates()
    logger.info("PIF Dashboard starting...")
    app.run(host='0.0.0.0', port=5000, debug=False)

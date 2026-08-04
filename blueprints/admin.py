# Admin Blueprint
# Provides stats, export (Excel/PDF), backup/restore, DB management,
# global search, and dashboard home routes.

import os
import shutil
import tempfile
import re
import hmac
import secrets
import logging
import html
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO

from flask import (
    Blueprint, request, jsonify, send_file, Response, session,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_LEFT

from urllib.parse import urlparse

from utils import (
    safe_table, login_required, get_json_or_400,
    get_app_setting, set_app_setting, PLAN_DEPT_KEY, PLAN_DEPT_HOST,
    _check_api_token,
)
from database import get_db, row_to_dict, DATABASE_PATH
from labels import project_status_label, task_status_label

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)

# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@admin_bp.route('/api/stats', methods=['GET'])
@login_required
def get_stats():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'pregatire' THEN 1 ELSE 0 END) as active,
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

# ---------------------------------------------------------------------------
# PDF export — palette & helpers
# ---------------------------------------------------------------------------

# PIF design palette (matches the web UI tokens 1:1)
_PIF_BG = colors.HexColor('#11161e')
_PIF_ACCENT = colors.HexColor('#58d1c9')
_PIF_ACCENT_SOFT = colors.HexColor('#1d3835')
_PIF_TEXT = colors.HexColor('#1f2937')
_PIF_TEXT_DIM = colors.HexColor('#5a6473')
_PIF_LINE = colors.HexColor('#dbe1ea')
_PIF_SUCCESS = colors.HexColor('#16a34a')
_PIF_DANGER = colors.HexColor('#dc2626')
_PIF_WARNING = colors.HexColor('#d97706')


def _pdf_safe_text(text):
    """Escape HTML special chars and normalize line breaks for ReportLab Paragraph.

    Mixed content from WYSIWYG: existing <br>/<div> tags are stripped, newlines
    become <br/>, and remaining HTML chars are escaped to literal text.
    """
    if not text:
        return ''
    t = re.sub(r'<br\s*/?>', '\n', text)
    t = re.sub(r'</?div[^>]*>', '', t)
    t = html.escape(t)
    return t.replace('\n', '<br/>')


def _pdf_make_styles():
    """ParagraphStyle palette used across the PDF report."""
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'PIFTitle', parent=base['Heading1'],
            fontSize=18, leading=22, spaceAfter=4,
            textColor=_PIF_BG, alignment=TA_LEFT, fontName='Helvetica-Bold'),
        'subtitle': ParagraphStyle(
            'PIFSubtitle', parent=base['Normal'],
            fontSize=10, leading=14, textColor=_PIF_TEXT_DIM, spaceAfter=18, fontName='Helvetica'),
        'heading': ParagraphStyle(
            'PIFHeading', parent=base['Heading2'],
            fontSize=12, leading=16, spaceBefore=14, spaceAfter=8,
            textColor=_PIF_ACCENT, fontName='Helvetica-Bold'),
        'subheading': ParagraphStyle(
            'PIFSubHeading', parent=base['Heading3'],
            fontSize=10.5, leading=14, spaceBefore=8, spaceAfter=4,
            textColor=_PIF_BG, fontName='Helvetica-Bold'),
        'normal': ParagraphStyle(
            'PIFNormal', parent=base['Normal'],
            fontSize=9.5, leading=14, textColor=_PIF_TEXT, fontName='Helvetica'),
        'small': ParagraphStyle(
            'PIFSmall', parent=base['Normal'],
            fontSize=8, leading=11, textColor=_PIF_TEXT_DIM, fontName='Helvetica'),
    }


def _pdf_section_header(elements, project_dict, is_pif, styles):
    """Header band -- accent tip-label + project name + meta line."""
    tip_label = 'PIF' if is_pif else 'Service'
    elements.append(Paragraph(
        f"<font color='#58d1c9'>{tip_label}</font> — {project_dict.get('nume', '')}",
        styles['title']))
    meta_bits = []
    if project_dict.get('client'): meta_bits.append(project_dict['client'])
    if project_dict.get('locatie'): meta_bits.append(project_dict['locatie'])
    meta_bits.append(f"export {datetime.now().strftime('%d.%m.%Y')}")
    elements.append(Paragraph(' · '.join(meta_bits), styles['subtitle']))


def _pdf_section_admin(elements, project_dict, styles):
    """1. Detalii administrative -- fixed two-column info table."""
    elements.append(Paragraph("1. Detalii administrative", styles['heading']))
    project_info = [
        ['Client', project_dict.get('client') or '-'],
        ['Locație', project_dict.get('locatie') or '-'],
        ['Producător', project_dict.get('producator') or '-'],
        ['Echipament principal', project_dict.get('echipament_principal') or '-'],
        ['Status', project_status_label(project_dict.get('status', '')) or '-'],
        ['Nr. comandă', project_dict.get('nr_comanda') or '-'],
        ['Cod proiect', project_dict.get('cod_proiect') or '-'],
    ]
    info_table = Table(project_info, colWidths=[4.5*cm, 11*cm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TEXTCOLOR', (0, 0), (0, -1), _PIF_TEXT_DIM),
        ('TEXTCOLOR', (1, 0), (1, -1), _PIF_TEXT),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, _PIF_LINE),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))


def _pdf_section_tech(elements, project_dict, is_pif, styles):
    """2. Conținut tehnic -- PIF observații or Service before/after."""
    if is_pif and project_dict.get('observatii'):
        elements.append(Paragraph("2. Observații tehnice", styles['heading']))
        elements.append(Paragraph(_pdf_safe_text(project_dict.get('observatii', '')), styles['normal']))
        elements.append(Spacer(1, 6))
    if not is_pif and (project_dict.get('service_before') or project_dict.get('service_after')):
        elements.append(Paragraph("2. Fișă intervenție", styles['heading']))
        if project_dict.get('service_before'):
            elements.append(Paragraph("Constatări înainte de intervenție", styles['subheading']))
            elements.append(Paragraph(_pdf_safe_text(project_dict.get('service_before', '')), styles['normal']))
            elements.append(Spacer(1, 4))
        if project_dict.get('service_after'):
            elements.append(Paragraph("Acțiuni efectuate și rezultat", styles['subheading']))
            elements.append(Paragraph(_pdf_safe_text(project_dict.get('service_after', '')), styles['normal']))
            elements.append(Spacer(1, 4))


def _pdf_section_tasks(elements, tasks, section_n, styles):
    """N. Listă taskuri -- table of project tasks."""
    elements.append(Paragraph(f"{section_n}. Listă taskuri", styles['heading']))
    task_data = [['#', 'Titlu', 'Status', 'Prioritate', 'Termen']]
    for i, t in enumerate(tasks, 1):
        task_data.append([
            str(i),
            t.get('titlu', '-'),
            task_status_label(t.get('status', '')) or '-',
            t.get('data_scadenta') or '-',
        ])
    task_table = Table(task_data, colWidths=[0.8*cm, 8.5*cm, 2.2*cm, 1.8*cm, 2.2*cm])
    task_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), _PIF_ACCENT),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, _PIF_LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
    ]))
    elements.append(task_table)
    elements.append(Spacer(1, 10))


# ---------------------------------------------------------------------------
# PDF export routes
# ---------------------------------------------------------------------------

@admin_bp.route('/api/export/pdf', methods=['GET'])
@login_required
def export_pdf():
    """Export project to PDF format"""
    project_id = request.args.get('project_id')
    if not project_id:
        return jsonify({'error': 'project_id is required'}), 400

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM proiecte WHERE id = ?', (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        return jsonify({'error': 'Project not found'}), 404
    project_dict = row_to_dict(project)

    cursor.execute('SELECT * FROM tasks WHERE proiect_id = ? ORDER BY ordine ASC', (project_id,))
    tasks = [row_to_dict(row) for row in cursor.fetchall()]
    conn.close()

    is_pif = (project_dict.get('tip') == 'PIF')

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.8*cm, leftMargin=1.8*cm, topMargin=2*cm, bottomMargin=2*cm,
        title=f"PIF Report — {re.sub(r'[<>]', '', project_dict.get('nume', '') or '')}",
        author='PIF Dashboard'
    )

    styles = _pdf_make_styles()
    elements = []

    _pdf_section_header(elements, project_dict, is_pif, styles)
    _pdf_section_admin(elements, project_dict, styles)
    _pdf_section_tech(elements, project_dict, is_pif, styles)

    n_tasks = 3

    if tasks:
        _pdf_section_tasks(elements, tasks, n_tasks, styles)

    # Footer
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(
        f"<font color='#5a6473'>Document generat automat din PIF Dashboard · {datetime.now().strftime('%d.%m.%Y %H:%M')} · Ion Ursu</font>",
        styles['small']))

    doc.build(elements)

    buffer.seek(0)
    safe_name = (project_dict.get('nume', 'project') or 'project').replace(' ', '_').replace('/', '_')
    if project_dict.get('cod_proiect'):
        filename = f"{project_dict['cod_proiect']}_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    else:
        filename = f"pif_report_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
    logger.info(f"PDF export: {filename}")

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

ICS_FEED_KEY = 'ics_feed_key'


def _ics_feed_key():
    """Cheia secreta a feed-ului .ics — generata la prima cerere, tinuta in
    app_settings (baza e gitignored, deci cheia nu ajunge in git). Exista pentru
    ca Google Calendar descarca URL-ul de abonare de pe SERVERELE lui, fara
    sesiune si fara headere — singura autentificare posibila e in URL."""
    key = get_app_setting(ICS_FEED_KEY)
    if not key:
        key = secrets.token_urlsafe(32)
        set_app_setting(ICS_FEED_KEY, key)
    return key


@admin_bp.route('/api/export/ics-key', methods=['GET'])
@login_required
def export_ics_key():
    """Cheia feed-ului, pentru clientul care construieste URL-ul de abonare."""
    return jsonify({'key': _ics_feed_key()})


@admin_bp.route('/api/export/ics', methods=['GET'])
def export_ics():
    """Calendarul de abonat din telefon (Google/Apple Calendar).

    `?sfera=munca` (implicit): perioadele de implementare + scadente de taskuri
    de munca. `?sfera=personal`: DOAR scadentele taskurilor personale — feed
    separat, ca in Google Calendar sa fie un calendar propriu, cu culoarea lui,
    care se poate ascunde independent. Nu exista un feed combinat: sferele nu
    se amesteca nici aici.

    Continutul muncii, in ordinea utilitatii:
      1. PERIOADELE de implementare — unde esti efectiv in fiecare zi, cu faza
         (pregatire / implementare). Sunt singurul lucru planificat cu adevarat.
      2. scadente de taskuri (proiect + globale)

    Deadline-urile de proiect au plecat in v30: nu se lua nimeni dupa ele.
    """
    # Fara @login_required: pe langa sesiune si Bearer, feed-ul se serveste si
    # cu cheia secreta din URL (`?key=`) — drumul prin care se aboneaza Google
    # Calendar. Comparatia e constant-time, ca la Bearer.
    if 'authenticated' not in session and not _check_api_token():
        key = request.args.get('key') or ''
        if not key or not hmac.compare_digest(_ics_feed_key(), key):
            return jsonify({'error': 'Unauthorized'}), 401

    sfera = request.args.get('sfera') or 'munca'
    if sfera not in ('munca', 'personal'):
        return jsonify({'error': "sfera invalidă (acceptat: 'munca' sau 'personal')"}), 400
    personal = sfera == 'personal'

    conn = get_db()
    cur = conn.cursor()
    now = datetime.now().strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//PIF Dashboard//RO',
             'CALSCALE:GREGORIAN',
             'X-WR-CALNAME:PIF Personal' if personal else 'X-WR-CALNAME:PIF Dashboard']

    def esc(s):
        return (str(s or '')).replace('\\', '\\\\').replace(';', '\\;').replace(',', '\\,').replace('\n', '\\n')

    def date_only(iso):
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(iso or ''))
        return (m.group(1) + m.group(2) + m.group(3)) if m else None

    def add_event(uid, dt, summary, desc='', dt_end=None, loc=''):
        d = date_only(dt)
        if not d:
            return
        lines.extend(['BEGIN:VEVENT', f'UID:{uid}@pif.iupif.org', f'DTSTAMP:{now}',
                      f'DTSTART;VALUE=DATE:{d}'])
        # DTEND e EXCLUSIV in iCalendar: o iesire 29->30 se scrie ca 29 -> 31,
        # altfel telefonul o arata pe o singura zi.
        de = date_only(dt_end)
        if de:
            end_d = datetime.strptime(de, '%Y%m%d').date() + timedelta(days=1)
            lines.append(f'DTEND;VALUE=DATE:{end_d.strftime("%Y%m%d")}')
        lines.append(f'SUMMARY:{esc(summary)}')
        if loc:
            lines.append(f'LOCATION:{esc(loc)}')
        if desc:
            lines.append(f'DESCRIPTION:{esc(desc)}')
        lines.append('END:VEVENT')

    try:
        if personal:
            # Fara prefixul „Scadenta:" — intr-un calendar care se numeste deja
            # „PIF Personal", prefixul pe fiecare eveniment ar fi zgomot.
            cur.execute("SELECT id, titlu, data_scadenta FROM global_tasks WHERE sfera = 'personal' "
                        "AND data_scadenta IS NOT NULL "
                        "AND TRIM(data_scadenta) <> '' AND (data_finalizare IS NULL OR TRIM(data_finalizare) = '')")
            for r in cur.fetchall():
                add_event(f"gtask-{r['id']}", r['data_scadenta'], r['titlu'], 'Task personal')
        else:
            cur.execute("""
                SELECT i.id, i.data_start,
                       CASE WHEN p.status = 'finalizat'
                             AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) > date(COALESCE(NULLIF(p.data_finalizare, ''), date('now')))
                            THEN date(COALESCE(NULLIF(p.data_finalizare, ''), date('now')))
                            ELSE i.data_sfarsit END AS data_sfarsit,
                       i.eticheta, i.locatie, i.faza,
                       p.nume, p.client, p.locatie AS locatie_proiect
                FROM implementari i JOIN proiecte p ON p.id = i.proiect_id
                WHERE i.data_start IS NOT NULL AND TRIM(i.data_start) <> ''
                  -- vezi /api/calendar: un proiect inchis nu mai ocupa zile de dupa
                  -- ziua inchiderii
                  AND (p.status != 'finalizat' OR date(i.data_start) <= date(COALESCE(NULLIF(p.data_finalizare, ''), date('now'))))
                ORDER BY i.data_start
            """)
            for r in cur.fetchall():
                la_sediu = (r['locatie'] or 'site') == 'sediu'
                titlu = r['eticheta'] or r['nume']
                unde = 'Sediu EGB' if la_sediu else (r['locatie_proiect'] or r['client'] or '')
                # Faza intra in titlu doar cand e pregatire: implementarea e cazul
                # obisnuit, iar un prefix pe fiecare eveniment ar fi zgomot in telefon.
                if (r['faza'] or 'implementare') == 'pregatire':
                    titlu = f'Pregătire · {titlu}'
                add_event(f"impl-{r['id']}", r['data_start'],
                          f"{'Sediu' if la_sediu else (r['client'] or 'Teren')}: {titlu}",
                          desc=r['nume'], dt_end=r['data_sfarsit'] or r['data_start'], loc=unde)

            cur.execute("SELECT t.id, t.titlu, t.data_scadenta, p.nume AS pnume FROM tasks t "
                        "JOIN proiecte p ON t.proiect_id = p.id WHERE t.data_scadenta IS NOT NULL "
                        "AND TRIM(t.data_scadenta) <> '' AND (t.data_finalizare IS NULL OR TRIM(t.data_finalizare) = '')")
            for r in cur.fetchall():
                add_event(f"task-{r['id']}", r['data_scadenta'], f"Scadenta: {r['titlu']}", f"Proiect: {r['pnume']}")

            cur.execute("SELECT id, titlu, data_scadenta FROM global_tasks WHERE sfera = 'munca' "
                        "AND data_scadenta IS NOT NULL "
                        "AND TRIM(data_scadenta) <> '' AND (data_finalizare IS NULL OR TRIM(data_finalizare) = '')")
            for r in cur.fetchall():
                add_event(f"gtask-{r['id']}", r['data_scadenta'], f"Scadenta: {r['titlu']}", 'Task global')
    finally:
        conn.close()

    lines.append('END:VCALENDAR')
    ics = '\r\n'.join(lines) + '\r\n'
    fname = 'pif-personal.ics' if personal else 'pif-calendar.ics'
    return Response(ics, mimetype='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

@admin_bp.route('/api/backup', methods=['GET'])
@login_required
def backup_database():
    conn = get_db()
    cursor = conn.cursor()

    backup = {}

    tables = ['proiecte', 'tasks', 'task_subtasks', 'task_dependencies',
                  'implementari', 'calcule', 'global_tasks', 'clienti', 'app_settings']
    # sarim tabelele absente
    # ca sa nu pice backup-ul cu 500.
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing = {row[0] for row in cursor.fetchall()}
    for table in tables:
        if table not in existing:
            backup[table] = []
            continue
        cursor.execute(f'SELECT * FROM {safe_table(table)}')
        rows = cursor.fetchall()
        backup[table] = [row_to_dict(row) for row in rows]

    conn.close()

    return jsonify(backup)


@admin_bp.route('/api/restore', methods=['POST'])
@login_required
def restore_database():
    data = get_json_or_400()

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Run the whole clear + restore inside ONE transaction, so a bad payload
        # rolls the deletes back instead of leaving the database wiped.
        conn.execute('BEGIN TRANSACTION')
        # Clear existing data (skip tables absent on this deploy)
        tables = ['proiecte', 'tasks', 'task_subtasks', 'task_dependencies',
                  'implementari', 'calcule', 'global_tasks', 'clienti', 'app_settings']
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing = {row[0] for row in cursor.fetchall()}
        for table in tables:
            if table in existing:
                cursor.execute(f'DELETE FROM {safe_table(table)}')

        # Restore proiecte
        for p in data.get('proiecte', []):
            cursor.execute('''
                INSERT INTO proiecte (id, tip, nume, client, locatie, echipament_principal, producator,
                    cod_proiect, folder_server, data_crearii,
                    status, observatii, nr_comanda, service_before, service_after,
                    confirmat_client, client_nume_confirmare, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                p.get('id'), p.get('tip'), p.get('nume'), p.get('client'), p.get('locatie'),
                p.get('echipament_principal'), p.get('producator'), p.get('cod_proiect'),
                p.get('folder_server'),
                p.get('data_crearii'), p.get('status'), p.get('observatii'), p.get('nr_comanda'),
                p.get('service_before'), p.get('service_after'),
                p.get('confirmat_client', 0), p.get('client_nume_confirmare'),
                p.get('created_at'), p.get('updated_at')
            ))

        # Restore tasks. `data_planificata` din backup-uri vechi (dinainte de v33)
        # se ignora: taskul are o singura data acum, iar migrarea a mutat deja
        # planul in termen acolo unde termenul lipsea.
        for t in data.get('tasks', []):
            cursor.execute('''
                INSERT INTO tasks (id, proiect_id, titlu, descriere, status,
                    data_scadenta, data_finalizare, ordine, recurenta, created_at, updated_at,
                    ordine_agenda)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t.get('id'), t.get('proiect_id'), t.get('titlu'), t.get('descriere'),
                  t.get('status'),
                  t.get('data_scadenta') or t.get('data_planificata'),
                  t.get('data_finalizare'), t.get('ordine', 0), t.get('recurenta'),
                  t.get('created_at'), t.get('updated_at'),
                  t.get('ordine_agenda', 0)))

        # jurnal / timer_sessions din backup-uri vechi se ignora (v22 a scos featureul)
        # checklist_pif / checklist_categorii / project_templates din backup-uri vechi
        # se ignora (v23 a sters featureurile Checklist + Template)

        # Restore global_tasks — vezi nota de mai sus despre `data_planificata`.
        for gt in data.get('global_tasks', []):
            cursor.execute('''
                INSERT INTO global_tasks (id, titlu, descriere, status, categorie, sfera,
                    data_scadenta, data_finalizare, recurenta, created_at, updated_at,
                    ordine_agenda)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (gt.get('id'), gt.get('titlu'), gt.get('descriere'),
                  gt.get('status'), gt.get('categorie'),
                  gt.get('sfera') or 'munca',
                  gt.get('data_scadenta') or gt.get('data_planificata'),
                  gt.get('data_finalizare'), gt.get('recurenta'),
                  gt.get('created_at'), gt.get('updated_at'),
                  gt.get('ordine_agenda', 0)))

        # Restore clienti
        for c in data.get('clienti', []):
            cursor.execute('''
                INSERT INTO clienti (id, nume, adresa, telefon, email, contact_principal, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (c.get('id'), c.get('nume'), c.get('adresa'), c.get('telefon'),
                  c.get('email'), c.get('contact_principal'), c.get('note'), c.get('created_at')))

        # Restore task_subtasks (schema: id, task_id, titlu, done, ordine, created_at)
        for s in data.get('task_subtasks', []):
            cursor.execute('''
                INSERT INTO task_subtasks (id, task_id, titlu, done, ordine, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (s.get('id'), s.get('task_id'), s.get('titlu'),
                  s.get('done', 0), s.get('ordine', 0), s.get('created_at')))

        # Restore implementari (perioadele de implementare — planificarea reala
        # a lui Ion). Lipseau din backup pana in 2026-07-27: un restore le pierdea
        # in tacere.
        for im in data.get('implementari', []):
            cursor.execute('''
                INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit,
                    locatie, faza, eticheta, ordine, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (im.get('id'), im.get('proiect_id'), im.get('data_start'),
                  im.get('data_sfarsit'), im.get('locatie') or 'site',
                  im.get('faza') or 'implementare',
                  im.get('eticheta'), im.get('ordine', 0), im.get('created_at')))

        # Calcule atasate proiectelor (v37). Campurile JSON se scriu ca text, asa
        # cum stau in tabela — restore-ul nu le interpreteaza.
        for c in data.get('calcule', []):
            cursor.execute('''
                INSERT INTO calcule (id, proiect_id, titlu, modul_id, modul_titlu,
                    intrari, rezultate, verdicte, stare, nota, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (c.get('id'), c.get('proiect_id'), c.get('titlu'), c.get('modul_id'),
                  c.get('modul_titlu'), c.get('intrari'), c.get('rezultate'),
                  c.get('verdicte'), c.get('stare'), c.get('nota'), c.get('created_at')))

        # Restore task_dependencies (dupa tasks — FK pe ambele capete)
        for dep in data.get('task_dependencies', []):
            cursor.execute('''
                INSERT INTO task_dependencies (id, proiect_id, predecessor_id,
                    successor_id, tip, lag, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (dep.get('id'), dep.get('proiect_id'), dep.get('predecessor_id'),
                  dep.get('successor_id'), dep.get('tip') or 'FS',
                  dep.get('lag', 0), dep.get('created_at')))

        # Restore app_settings (vault Obsidian, cheile de idempotenta debrief).
        # assistant_memory din backup-uri vechi se ignora (v23 a sters Hermes).
        for s in data.get('app_settings', []):
            cursor.execute('INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)',
                           (s.get('key'), s.get('value'), s.get('updated_at')))

        conn.commit()
        conn.close()

        logger.info("Database restored successfully")
        return jsonify({'message': 'Database restored successfully'})
    except Exception as e:
        conn.rollback()
        conn.close()
        logger.error(f"Error restoring database: {e}")
        return jsonify({'error': 'Restaurare esuata — modificarile au fost anulate.'}), 500

# ---------------------------------------------------------------------------
# Admin DB management
# ---------------------------------------------------------------------------

@admin_bp.route('/admin/db-upload', methods=['GET'])
@login_required
def admin_db_upload_page():
    """Minimal HTML form for uploading a local DB file."""
    return '''<!doctype html>
<html><head><meta charset="utf-8"><title>DB upload</title>
<style>
body{background:#0a0d12;color:#e3e8ef;font-family:system-ui,sans-serif;
     max-width:560px;margin:60px auto;padding:0 24px}
h1{font-size:20px;margin:0 0 16px}
.box{background:#161c26;border:1px solid #232a36;border-radius:10px;padding:24px}
input[type=file]{margin:16px 0;color:#e3e8ef}
button{background:#58d1c9;color:#0a0d12;border:0;padding:10px 18px;
       border-radius:8px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}
.note{color:#9aa4b2;font-size:13px;margin-top:14px}
pre{background:#0a0d12;border:1px solid #232a36;border-radius:6px;
    padding:10px;font-size:12px;overflow:auto;max-height:280px}
.ok{color:#66d19e}.err{color:#f97066}
</style></head>
<body><div class="box">
<h1>Upload DB SQLite</h1>
<form id="f">
<input type="file" name="db" accept=".db" required>
<br><button id="submit" type="submit">Upload (inlocuieste DB serverului)</button>
</form>
<div class="note">DB-ul curent va fi salvat in <code>backups/</code> automat inainte de inlocuire.</div>
<pre id="out"></pre>
</div>
<script>
const f=document.getElementById('f'),btn=document.getElementById('submit'),out=document.getElementById('out');
f.addEventListener('submit',async e=>{
  e.preventDefault();btn.disabled=true;out.textContent='Uploading...';
  const fd=new FormData(f);
  try{
    const r=await fetch('/api/admin/db-upload',{method:'POST',body:fd});
    const j=await r.json();
    out.textContent=JSON.stringify(j,null,2);
    out.className=r.ok?'ok':'err';
  }catch(err){out.textContent=err.message;out.className='err';}
  btn.disabled=false;
});
</script>
</body></html>'''


@admin_bp.route('/api/admin/db-upload', methods=['POST'])
@login_required
def admin_db_upload():
    """Replace the server SQLite DB with an uploaded copy.
    Expects a multipart form field named 'db' with a .db file.
    Validates SQLite header, backs up the existing DB, then atomic-replaces it.
    """
    if 'db' not in request.files:
        return jsonify({'error': "missing form field 'db'"}), 400
    f = request.files['db']
    if not f or f.filename == '':
        return jsonify({'error': 'empty file'}), 400

    dir_name = os.path.dirname(DATABASE_PATH) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='dbupload_', suffix='.db', dir=dir_name)
    os.close(fd)
    try:
        f.save(tmp_path)
        with open(tmp_path, 'rb') as fh:
            magic = fh.read(16)
        if not magic.startswith(b'SQLite format 3'):
            os.unlink(tmp_path)
            return jsonify({'error': 'not a valid SQLite database'}), 400

        # Beyond the magic header: verify the file is a sound SQLite DB and
        # actually looks like a PIF database before replacing the live one.
        try:
            _chk = sqlite3.connect(tmp_path)
            _integrity = _chk.execute('PRAGMA integrity_check').fetchone()
            _has_core = _chk.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='proiecte'"
            ).fetchone()
            _chk.close()
        except (sqlite3.Error, OSError):
            os.unlink(tmp_path)
            return jsonify({'error': 'fisierul nu este o baza SQLite utilizabila'}), 400
        if not _integrity or _integrity[0] != 'ok':
            os.unlink(tmp_path)
            return jsonify({'error': 'baza incarcata a esuat integrity_check'}), 400
        if not _has_core:
            os.unlink(tmp_path)
            return jsonify({'error': 'baza incarcata nu contine structura PIF (tabelul proiecte)'}), 400

        backups_dir = os.path.join(dir_name, 'backups')
        os.makedirs(backups_dir, exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = os.path.join(backups_dir, f'pif_dashboard_pre_upload_{stamp}.db')
        if os.path.exists(DATABASE_PATH):
            shutil.copy2(DATABASE_PATH, backup_path)

        # Checkpoint WAL into the main DB file so the *-wal/*-shm files are
        # truncated. Without this, the OLD WAL can persist after replace and
        # corrupt reads against the NEW DB.
        try:
            from database import close_db
            conn = get_db()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            close_db(None)
        except Exception as e:
            logger.warning(f"WAL checkpoint before db replace failed: {e}")

        os.replace(tmp_path, DATABASE_PATH)

        return jsonify({
            'status': 'ok',
            'backup': backup_path,
            'replaced': DATABASE_PATH,
            'size': os.path.getsize(DATABASE_PATH),
        })
    except Exception as e:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        logger.error(f"db-upload failed: {e}")
        return jsonify({'error': 'Incarcarea bazei a esuat.'}), 500


@admin_bp.route('/api/admin/db-dump', methods=['GET'])
@login_required
def admin_db_dump():
    """Stream o copie consistenta a DB-ului SQLite pentru audit local.
    Foloseste sqlite3 backup API ca sa nu blocheze scrieri concurente.
    """
    import sqlite3 as _sql3
    from flask import after_this_request

    if not os.path.exists(DATABASE_PATH):
        return jsonify({'error': 'DB not found on server'}), 404

    # Hot backup la un fisier temporar (safe vs WAL)
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    src = _sql3.connect(DATABASE_PATH)
    dst = _sql3.connect(tmp.name)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    # Schedule cleanup of the temp file once the response is sent -- without
    # this the temp dir slowly fills up (~40 MB per download).
    @after_this_request
    def _cleanup(response):
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        return response

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        tmp.name,
        as_attachment=True,
        download_name=f'pif_dashboard_{timestamp}.db',
        mimetype='application/octet-stream',
    )

# ---------------------------------------------------------------------------
# Global search
# ---------------------------------------------------------------------------

def _search_snippet(text, query, width=80):
    """A short context window around the first match of `query` in `text`."""
    if not text:
        return ''
    text = str(text)
    low = text.lower()
    idx = low.find(query.lower())
    if idx < 0:
        return text[:width].strip()
    start = max(0, idx - 32)
    end = min(len(text), idx + len(query) + width)
    return ('…' if start > 0 else '') + text[start:end].strip() + ('…' if end < len(text) else '')


@admin_bp.route('/api/search', methods=['GET'])
@login_required
def global_search():
    """Unified search across everything in the app for the command palette."""
    q = (request.args.get('q') or '').strip()
    if len(q) < 2:
        return jsonify({'results': [], 'query': q})
    like = f'%{q}%'
    results = []
    conn = get_db()
    cur = conn.cursor()

    cur.execute('SELECT id, nume, client FROM proiecte '
                'WHERE nume LIKE ? OR client LIKE ? OR cod_proiect LIKE ? OR locatie LIKE ? LIMIT 8',
                (like, like, like, like))
    for r in cur.fetchall():
        results.append({'type': 'proiect', 'id': r['id'], 'title': r['nume'],
                        'subtitle': r['client'] or '', 'snippet': '', 'proiect_id': r['id']})

    cur.execute('SELECT id, nume, observatii FROM proiecte WHERE observatii LIKE ? LIMIT 8', (like,))
    for r in cur.fetchall():
        results.append({'type': 'observatie', 'id': r['id'], 'title': f"Observații — {r['nume']}",
                        'subtitle': '', 'snippet': _search_snippet(r['observatii'], q), 'proiect_id': r['id']})

    cur.execute('SELECT t.id, t.titlu, t.descriere, t.proiect_id, p.nume AS pnume FROM tasks t '
                'JOIN proiecte p ON t.proiect_id = p.id '
                'WHERE t.titlu LIKE ? OR t.descriere LIKE ? LIMIT 12', (like, like))
    for r in cur.fetchall():
        results.append({'type': 'task', 'id': r['id'], 'title': r['titlu'],
                        'subtitle': r['pnume'], 'snippet': _search_snippet(r['descriere'], q),
                        'proiect_id': r['proiect_id']})

    # Cautarea e SINGURA suprafata cross-sfera — dar eticheteaza sfera in subtitlu.
    cur.execute('SELECT id, titlu, descriere, categorie, sfera FROM global_tasks '
                'WHERE titlu LIKE ? OR descriere LIKE ? LIMIT 10', (like, like))
    for r in cur.fetchall():
        subtitle = 'Personal' if r['sfera'] == 'personal' else (r['categorie'] or 'Task zilnic')
        results.append({'type': 'global_task', 'id': r['id'], 'title': r['titlu'],
                        'subtitle': subtitle, 'snippet': _search_snippet(r['descriere'], q),
                        'sfera': r['sfera'] or 'munca'})

    cur.execute('SELECT id, nume, telefon FROM clienti WHERE nume LIKE ? OR contact_principal LIKE ? LIMIT 6',
                (like, like))
    for r in cur.fetchall():
        results.append({'type': 'client', 'id': r['id'], 'title': r['nume'],
                        'subtitle': 'Client', 'snippet': r['telefon'] or ''})

    conn.close()

    return jsonify({'results': results, 'query': q, 'count': len(results)})

@admin_bp.route('/api/settings/plan-departament', methods=['GET'])
@login_required
def plan_departament_get():
    """Linkul catre planul intregului departament (aplicatie externa).

    Contine cheia de acces, deci sta in app_settings (baza e gitignored) si se
    intoarce doar unei sesiuni autentificate.
    """
    return jsonify({'url': get_app_setting(PLAN_DEPT_KEY, '') or '', 'host': PLAN_DEPT_HOST})


@admin_bp.route('/api/settings/plan-departament', methods=['PUT'])
@login_required
def plan_departament_set():
    data = get_json_or_400()
    url = (data.get('url') or '').strip()
    if url:
        p = urlparse(url)
        # Verificat pe server, nu doar in CSP: altfel un link gresit ar da un
        # iframe alb, fara nicio explicatie de ce nu merge.
        if p.scheme != 'https' or (p.hostname or '').lower() != PLAN_DEPT_HOST:
            return jsonify({
                'error': f'Se acceptă doar linkuri https către {PLAN_DEPT_HOST}'
            }), 400
    set_app_setting(PLAN_DEPT_KEY, url)
    return jsonify({'url': url, 'host': PLAN_DEPT_HOST})


@admin_bp.route('/api/calendar', methods=['GET'])
@login_required
def calendar_view():
    """Calendarul personal: unde esti in fiecare zi.

    Ion e o singura persoana, iar planificarea lui reala sunt PERIOADELE de
    implementare, fiecare cu faza ei (pregatire / implementare in site).
    Deci intrebarea la care raspunde ecranul asta e „unde sunt marti", si tot
    aici stau si deciziile — nu intr-o lista separata.

    `necesita_decizie` = perioada s-a terminat, dar proiectul n-a fost mutat.
    Ori s-a facut si trebuie inchis, ori a alunecat si trebuie replanificat.

    `neplanificate` = proiecte active fara nicio perioada viitoare. Ele stau in
    banda laterala, de unde se trag pe o zi ca sa devina perioade.
    """
    start = (request.args.get('start') or '').strip()
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', start):
        start = datetime.now().date().replace(day=1).isoformat()
    try:
        zile = int(request.args.get('zile') or 42)
    except (TypeError, ValueError):
        zile = 42
    zile = max(7, min(zile, 200))
    start_d = datetime.strptime(start, '%Y-%m-%d').date()
    end_s = (start_d + timedelta(days=zile)).isoformat()

    conn = get_db()
    cursor = conn.cursor()

    # O perioada intra in fereastra daca se intersecteaza cu ea, nu doar daca
    # incepe in ea — altfel un bloc de 4 zile care trece peste 1 ale lunii dispare.
    # Proiect FINALIZAT inainte de vreme: zilele ramase nu mai au ce cauta in
    # calendar — nu vei fi acolo. Dar trecutul ramane: chiar ai fost. Deci pentru
    # proiectele inchise taiem perioada la ZIUA DE AZI si excludem complet ce
    # incepe dupa. (Ion: „daca am finalizat un proiect inainte de vreme nu se
    # scoate din calendar".)
    cursor.execute("""
        SELECT i.id, i.data_start,
               CASE WHEN p.status = 'finalizat'
                     AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) > date(COALESCE(NULLIF(p.data_finalizare, ''), date('now')))
                    THEN date(COALESCE(NULLIF(p.data_finalizare, ''), date('now')))
                    ELSE i.data_sfarsit END AS data_sfarsit,
               i.eticheta, i.locatie, i.faza,
               p.id AS proiect_id, p.nume, p.client, p.locatie AS locatie_proiect,
               p.status, p.tip,
               (SELECT COUNT(*) FROM tasks t
                 WHERE t.proiect_id = p.id AND t.status != 'done') AS taskuri_deschise,
               (CASE WHEN p.status != 'finalizat'
                      AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) < date('now')
                     THEN 1 ELSE 0 END) AS necesita_decizie
        FROM implementari i JOIN proiecte p ON p.id = i.proiect_id
        WHERE (p.status != 'finalizat' OR date(i.data_start) <= date(COALESCE(NULLIF(p.data_finalizare, ''), date('now'))))
          AND date(i.data_start) < date(?)
          AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date(?)
        ORDER BY i.data_start, p.client, p.nume
    """, (end_s, start))
    perioade = [dict(r) for r in cursor.fetchall()]

    # Tot ce cere o decizie, chiar daca a ramas in urma ferestrei afisate —
    # altfel navighezi pe luna viitoare si semnalul dispare.
    cursor.execute("""
        SELECT i.id, i.data_start, i.data_sfarsit, i.eticheta, i.locatie, i.faza,
               p.id AS proiect_id, p.nume, p.client, p.status
        FROM implementari i JOIN proiecte p ON p.id = i.proiect_id
        WHERE p.status NOT IN ('finalizat', 'anulat')
          AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) < date('now')
        ORDER BY i.data_start
    """)
    de_decis = [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT id AS proiect_id, nume, client, status, tip
        FROM proiecte p
        WHERE p.status NOT IN ('finalizat', 'anulat')
          AND NOT EXISTS (
            SELECT 1 FROM implementari i
            WHERE i.proiect_id = p.id
              AND date(COALESCE(NULLIF(i.data_sfarsit, ''), i.data_start)) >= date('now')
          )
        ORDER BY p.status DESC, p.nume
    """)
    neplanificate = [dict(r) for r in cursor.fetchall()]

    # Nimic nu dispare in tacere. O data pe care SQLite nu o poate interpreta
    # (`date()` intoarce NULL) nu se aseaza pe nicio zi, deci randul lipseste din
    # calendar FARA niciun semn — asa a stat `23.02.2026` nevazut pe un proiect.
    # De la v29 intrarea e pazita de utils.norm_date(), dar o restaurare dintr-un
    # backup vechi sau o scriere directa in baza pot reintroduce asa ceva.
    probleme = []
    cursor.execute("""
        SELECT p.id AS proiect_id, p.nume, 'perioada' AS unde,
               CASE WHEN date(i.data_start) IS NULL THEN 'inceput' ELSE 'sfarsit' END AS camp,
               CASE WHEN date(i.data_start) IS NULL THEN i.data_start ELSE i.data_sfarsit END AS valoare
        FROM implementari i JOIN proiecte p ON p.id = i.proiect_id
        WHERE p.status != 'anulat'
          AND (date(i.data_start) IS NULL
               OR (TRIM(COALESCE(i.data_sfarsit, '')) <> '' AND date(i.data_sfarsit) IS NULL))
    """)
    probleme += [dict(r) for r in cursor.fetchall()]

    cursor.execute("""
        SELECT p.id AS proiect_id, p.nume, 'task' AS unde, 'termen' AS camp,
               t.data_scadenta AS valoare
        FROM tasks t JOIN proiecte p ON p.id = t.proiect_id
        WHERE t.status != 'done'
          AND t.data_scadenta IS NOT NULL AND TRIM(t.data_scadenta) <> ''
          AND date(t.data_scadenta) IS NULL
    """)
    probleme += [dict(r) for r in cursor.fetchall()]

    conn.close()
    return jsonify({
        'start': start,
        'zile': zile,
        'today': datetime.now().date().isoformat(),
        'perioade': perioade,
        'de_decis': de_decis,
        'neplanificate': neplanificate,
        'probleme': probleme,
    })

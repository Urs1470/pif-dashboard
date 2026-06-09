# Admin Blueprint
# Provides stats, export (Excel/PDF), backup/restore, DB management,
# global search, and dashboard home routes.

import os
import json
import shutil
import tempfile
import re
import logging
import html
import sqlite3
from datetime import datetime, timedelta
from io import BytesIO

from flask import (
    Blueprint, request, jsonify, send_file, render_template,
)
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from utils import safe_table, generate_uuid, login_required, UPLOAD_FOLDER, VALID_TABLES
from database import get_db, row_to_dict, DATABASE_PATH, init_db
from labels import project_status_label, task_status_label
from scripts.parse_params.abb import parse_full as abb_parse_full, read_drive_info as abb_drive_info

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

@admin_bp.route('/api/stats/extended', methods=['GET'])
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

# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

@admin_bp.route('/api/export/excel', methods=['GET'])
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
                except Exception as e:
                    logger.warning(f"auto_width cell length compute failed: {e}")
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
            row_data = list(row)
            row_data[4] = project_status_label(row_data[4])
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
            priority_map = {'urgent': 'Urgent', 'normal': 'Normal', 'minor': 'Minor'}
            row_data = list(row)
            row_data[2] = task_status_label(row_data[2])
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


def _pdf_section_admin(elements, project_dict, total_hours_label, styles):
    """1. Detalii administrative -- fixed two-column info table."""
    elements.append(Paragraph("1. Detalii administrative", styles['heading']))
    project_info = [
        ['Client', project_dict.get('client') or '-'],
        ['Locație', project_dict.get('locatie') or '-'],
        ['Producător', project_dict.get('producator') or '-'],
        ['Echipament principal', project_dict.get('echipament_principal') or '-'],
        ['Status', project_status_label(project_dict.get('status', '')) or '-'],
        ['Data începere', project_dict.get('data_incepere') or '-'],
        ['Deadline', project_dict.get('deadline') or '-'],
        ['PM', project_dict.get('pm') or '-'],
        ['Nr. comandă', project_dict.get('nr_comanda') or '-'],
        ['Nr. contract', project_dict.get('nr_contract') or '-'],
        ['Cod proiect', project_dict.get('cod_proiect') or '-'],
        ['Total ore lucrate', total_hours_label],
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


def _pdf_section_checklist(elements, checklist, checklist_cat, styles):
    """3. Checklist PIF -- items grouped by category, with an uncategorized bucket."""
    elements.append(Paragraph("3. Checklist PIF", styles['heading']))
    by_cat = {}
    for it in checklist:
        key = str(it.get('categorie_id')) if it.get('categorie_id') is not None else '0'
        by_cat.setdefault(key, []).append(it)
    ordered = sorted(checklist_cat, key=lambda c: (c.get('ordine') or 0))

    def _render_cat_block(cat_name, items):
        done = sum(1 for i in items if i.get('completed'))
        elements.append(Paragraph(f"{cat_name} ({done}/{len(items)})", styles['subheading']))
        rows = [['', 'Item']]
        for it in items:
            mark = '✓' if it.get('completed') else '○'
            rows.append([mark, it.get('titlu', '-')])
        t = Table(rows, colWidths=[0.7*cm, 14*cm])
        t.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (-1, 0), _PIF_TEXT_DIM),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, _PIF_ACCENT),
            ('LINEBELOW', (0, 1), (-1, -1), 0.25, _PIF_LINE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('TEXTCOLOR', (0, 1), (0, -1), _PIF_SUCCESS),
            ('FONTSIZE', (0, 1), (0, -1), 12),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6))

    for cat in ordered:
        its = by_cat.get(str(cat['id']), [])
        if its:
            _render_cat_block(cat.get('nume', '?'), its)
    uncategorized = by_cat.get('0', [])
    if uncategorized:
        _render_cat_block('Fără categorie', uncategorized)


def _pdf_section_tasks(elements, tasks, section_n, styles):
    """N. Listă taskuri -- table of project tasks."""
    elements.append(Paragraph(f"{section_n}. Listă taskuri", styles['heading']))
    task_data = [['#', 'Titlu', 'Status', 'Prioritate', 'Termen']]
    for i, t in enumerate(tasks, 1):
        task_data.append([
            str(i),
            t.get('titlu', '-'),
            task_status_label(t.get('status', '')) or '-',
            (t.get('prioritate') or 'Normal').capitalize(),
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


def _pdf_section_equipment(elements, echipamente, section_n, styles):
    """N. Echipamente -- equipment table."""
    elements.append(Paragraph(f"{section_n}. Echipamente", styles['heading']))
    equip_data = [['Nume', 'Producător', 'Model', 'Serial']]
    for eq in echipamente:
        equip_data.append([
            eq.get('nume') or '-',
            eq.get('producator') or '-',
            eq.get('model') or '-',
            eq.get('serial_number') or '-',
        ])
    equip_table = Table(equip_data, colWidths=[5*cm, 3.5*cm, 4*cm, 3*cm])
    equip_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), _PIF_ACCENT),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, _PIF_LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(equip_table)
    elements.append(Spacer(1, 10))


def _pdf_section_journal(elements, jurnal, timer_sessions, section_n, styles):
    """N. Jurnal de lucru -- entries with +/-2 min timer-session dedupe."""
    elements.append(Paragraph(f"{section_n}. Jurnal de lucru", styles['heading']))
    # Match each jurnal entry to a session with matching stop_time within 2 min.
    sessions = list(timer_sessions)
    matched = set()
    for j in jurnal:
        jt_raw = j.get('created_at') or j.get('data')
        try: jt = datetime.fromisoformat(jt_raw).timestamp() if jt_raw else 0
        except Exception: jt = 0
        if jt:
            for s in sessions:
                if s['id'] in matched: continue
                et_raw = s.get('stop_time')
                if not et_raw: continue
                try: et = datetime.fromisoformat(et_raw).timestamp()
                except Exception: continue
                if abs(jt - et) < 120:
                    matched.add(s['id'])
                    j['_dur'] = s.get('durata_secunde') or 0
                    break
    for entry in sorted(jurnal, key=lambda e: e.get('data') or '', reverse=False)[-30:]:
        dur = entry.get('_dur')
        dur_suffix = ''
        if dur:
            dh = int(dur // 3600); dm = int((dur % 3600) // 60)
            dur_suffix = f" · <font color='#58d1c9'>{dh}h {dm}m</font>" if dh > 0 else f" · <font color='#58d1c9'>{dm}m</font>"
        elements.append(Paragraph(f"<b>{entry.get('data', '-')}</b>{dur_suffix}", styles['subheading']))
        elements.append(Paragraph(_pdf_safe_text(entry.get('continut') or ''), styles['normal']))
        elements.append(Spacer(1, 4))
    # Timer fără notă
    unmatched = [s for s in sessions if s['id'] not in matched and s.get('stop_time')]
    if unmatched:
        elements.append(Paragraph("Sesiuni timer fără notă", styles['subheading']))
        for s in unmatched[:20]:
            dur = s.get('durata_secunde') or 0
            dh = int(dur // 3600); dm = int((dur % 3600) // 60)
            date = (s.get('start_time') or '')[:10]
            elements.append(Paragraph(f"{date} · {dh}h {dm}m" if dh > 0 else f"{date} · {dm}m", styles['small']))

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
    cursor.execute('SELECT * FROM checklist_pif WHERE proiect_id = ? ORDER BY ordine ASC', (project_id,))
    checklist = [row_to_dict(row) for row in cursor.fetchall()]
    cursor.execute('SELECT * FROM jurnal WHERE proiect_id = ? ORDER BY data DESC', (project_id,))
    jurnal = [row_to_dict(row) for row in cursor.fetchall()]
    cursor.execute('SELECT * FROM echipamente WHERE proiect_id = ?', (project_id,))
    echipamente = [row_to_dict(row) for row in cursor.fetchall()]
    cursor.execute('SELECT * FROM timer_sessions WHERE proiect_id = ?', (project_id,))
    timer_sessions = [row_to_dict(row) for row in cursor.fetchall()]

    try:
        cursor.execute('SELECT id, nume, ordine FROM checklist_categorii WHERE proiect_id = ? ORDER BY ordine, id', (project_id,))
        checklist_cat = [row_to_dict(row) for row in cursor.fetchall()]
    except sqlite3.OperationalError:
        checklist_cat = []  # Pre-v5 schema fallback

    conn.close()

    total_seconds = sum(ts['durata_secunde'] or 0 for ts in timer_sessions)
    total_h = int(total_seconds / 3600)
    total_m = int((total_seconds % 3600) / 60)
    total_hours_label = f"{total_h}h {total_m}m" if total_h > 0 else f"{total_m}m"

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
    _pdf_section_admin(elements, project_dict, total_hours_label, styles)
    _pdf_section_tech(elements, project_dict, is_pif, styles)

    # Section numbering preserves the original quirk: when section 2 (tech) is
    # absent, later sections do NOT renumber; only the optional checklist
    # (section 3, PIF-only) shifts subsequent numbers.
    checklist_present = is_pif and bool(checklist)
    if checklist_present:
        _pdf_section_checklist(elements, checklist, checklist_cat, styles)

    n_tasks = 4 if checklist_present else 3
    n_equip = 5 if checklist_present else 4
    n_jurnal = 6 if checklist_present else 5

    if tasks:
        _pdf_section_tasks(elements, tasks, n_tasks, styles)
    if echipamente:
        _pdf_section_equipment(elements, echipamente, n_equip, styles)
    if jurnal or timer_sessions:
        _pdf_section_journal(elements, jurnal, timer_sessions, n_jurnal, styles)

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

@admin_bp.route('/api/export/pdf/all', methods=['GET'])
@login_required
def export_all_projects_pdf():
    """Export summary of all projects to PDF"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM proiecte ORDER BY created_at DESC')
    projects = [row_to_dict(row) for row in cursor.fetchall()]
    conn.close()

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
            project_status_label(proj.get('status', '')) or '-',
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

# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

@admin_bp.route('/api/backup', methods=['GET'])
@login_required
def backup_database():
    conn = get_db()
    cursor = conn.cursor()

    backup = {}

    tables = ['proiecte', 'tasks', 'task_subtasks', 'checklist_pif', 'checklist_categorii', 'jurnal', 'timer_sessions', 'global_task_sessions', 'atasamente', 'global_tasks', 'clienti', 'echipamente', 'project_templates', 'fault_codes', 'budget_state', 'budget_audit', 'parametri_master']
    for table in tables:
        cursor.execute(f'SELECT * FROM {safe_table(table)}')
        rows = cursor.fetchall()
        backup[table] = [row_to_dict(row) for row in rows]

    conn.close()

    return jsonify(backup)


# ---------------------------------------------------------------------------
# Enrich parametri_master from ABB .dcparamsbak
# ---------------------------------------------------------------------------

@admin_bp.route('/api/admin/enrich-params', methods=['POST'])
@login_required
def enrich_params_from_backup():
    """Upload a .dcparamsbak file and enrich parametri_master with its data.

    Form fields:
      file: .dcparamsbak backup file
      family: optional target family (default: auto-detect from backup)
      apply: "true" to actually write changes (default: dry-run report only)

    Returns a JSON report of what was/would be changed.
    """
    if 'file' not in request.files:
        return jsonify({'error': 'Fișier lipsă (field "file")'}), 400
    upload = request.files['file']
    if not upload.filename:
        return jsonify({'error': 'Fișier gol'}), 400

    family_hint = (request.form.get('family') or '').strip()
    apply = (request.form.get('apply') or '').lower() in ('true', '1', 'yes')

    try:
        raw = upload.read()
    except Exception as e:
        return jsonify({'error': f'Eroare citire fișier: {e}'}), 400

    # Read drive info for family detection
    info = abb_drive_info(raw)
    if not family_hint:
        family_raw = info.get('Family', '')
        model_raw = info.get('DriveModel', '')
        if '880' in family_raw or '880' in model_raw:
            family_hint = 'ACS880'
        elif '580' in family_raw or '580' in model_raw:
            family_hint = 'ACS580'
        else:
            family_hint = 'ACS880'

    # Parse ALL params (including signals and at-default)
    all_params = abb_parse_full(raw, upload.filename or '')
    if not all_params:
        return jsonify({'error': 'Nu s-au putut parsa parametrii din fișier'}), 400

    signals = [p for p in all_params if p['is_signal']]
    config = [p for p in all_params if not p['is_signal']]

    # Load existing DB params
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT parametru, descriere_scurta, unitate, valoare_default,
               valoare_default_str, min, max, enum_labels
        FROM parametri_master WHERE familie = ?
    ''', (family_hint,))
    db_params = {}
    for row in cursor.fetchall():
        db_params[row['parametru']] = {
            'descriere_scurta': row['descriere_scurta'] or '',
            'unitate': row['unitate'] or '',
            'valoare_default': row['valoare_default'],
            'valoare_default_str': row['valoare_default_str'] or '',
            'min': row['min'],
            'max': row['max'],
            'enum_labels': row['enum_labels'] or '',
        }

    # Compare
    new_params = []
    fill_unit = []
    fill_default = []
    fill_min_max = []
    different_default = []
    enum_available = []

    for p in all_params:
        code = p['db_id']
        db = db_params.get(code)

        if p.get('value_names'):
            enum_available.append(p)

        if db is None:
            new_params.append(p)
            continue

        if not db['unitate'] and p['unit']:
            fill_unit.append((code, p['unit']))

        backup_default = p['default_value']
        db_default = str(db['valoare_default']) if db['valoare_default'] is not None else db['valoare_default_str']
        if backup_default and db_default:
            try:
                if abs(float(backup_default) - float(db_default)) > 1e-6:
                    different_default.append({'code': code, 'db': db_default, 'backup': backup_default})
            except (ValueError, TypeError):
                if backup_default != db_default:
                    different_default.append({'code': code, 'db': db_default, 'backup': backup_default})
        elif backup_default and not db_default:
            fill_default.append((code, backup_default))

        if (db['min'] is None or str(db['min']).strip() == '') and p['min']:
            fill_min_max.append((code, 'min', p['min']))
        if (db['max'] is None or str(db['max']).strip() == '') and p['max']:
            fill_min_max.append((code, 'max', p['max']))

    enum_for_existing = [p for p in enum_available if p['db_id'] in db_params]
    enum_missing = [p for p in enum_for_existing if not db_params[p['db_id']].get('enum_labels')]

    report = {
        'drive_info': info,
        'family': family_hint,
        'total_params': len(all_params),
        'signals': len(signals),
        'config': len(config),
        'existing_in_db': len(db_params),
        'new_params': len(new_params),
        'fill_unit': len(fill_unit),
        'fill_default': len(fill_default),
        'fill_min_max': len(fill_min_max),
        'different_default': len(different_default),
        'enum_available': len(enum_available),
        'enum_missing_in_db': len(enum_missing),
        'applied': apply,
        'new_params_sample': [{'code': p['db_id'], 'name': p['name'], 'unit': p['unit'],
                               'signal': p['is_signal']} for p in new_params[:30]],
        'different_default_sample': different_default[:20],
    }

    if apply:
        inserted = 0
        for p in new_params:
            if p['is_signal']:
                continue
            try:
                cursor.execute('''
                    INSERT INTO parametri_master (id, familie, parametru, descriere_scurta,
                        unitate, valoare_default, min, max, enum_labels, creat_la)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ''', (
                    generate_uuid(), family_hint, p['db_id'], p['name'],
                    p['unit'] or None, p['default_value'] or None,
                    p['min'] or None, p['max'] or None,
                    json.dumps(p['value_names']) if p.get('value_names') else None,
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                pass

        for code, unit in fill_unit:
            cursor.execute(
                'UPDATE parametri_master SET unitate = ? WHERE familie = ? AND parametru = ? AND (unitate IS NULL OR unitate = "")',
                (unit, family_hint, code))

        for code, default in fill_default:
            cursor.execute(
                'UPDATE parametri_master SET valoare_default = ? WHERE familie = ? AND parametru = ? AND valoare_default IS NULL',
                (default, family_hint, code))

        for code, field, val in fill_min_max:
            cursor.execute(
                f'UPDATE parametri_master SET [{field}] = ? WHERE familie = ? AND parametru = ? AND ([{field}] IS NULL OR [{field}] = "")',
                (val, family_hint, code))

        stored_enums = 0
        for p in enum_missing:
            if p.get('value_names'):
                cursor.execute(
                    'UPDATE parametri_master SET enum_labels = ? WHERE familie = ? AND parametru = ? AND (enum_labels IS NULL OR enum_labels = "")',
                    (json.dumps(p['value_names']), family_hint, p['db_id']))
                stored_enums += 1

        conn.commit()
        report['inserted'] = inserted
        report['updated_units'] = len(fill_unit)
        report['updated_defaults'] = len(fill_default)
        report['updated_min_max'] = len(fill_min_max)
        report['stored_enums'] = stored_enums
        logger.info(f"Enrich params ({family_hint}): +{inserted} new, {len(fill_unit)} units, {stored_enums} enums")

    conn.close()
    return jsonify(report)


@admin_bp.route('/api/restore', methods=['POST'])
@login_required
def restore_database():
    data = request.json

    conn = get_db()
    cursor = conn.cursor()

    try:
        # Run the whole clear + restore inside ONE transaction, so a bad payload
        # rolls the deletes back instead of leaving the database wiped.
        conn.execute('BEGIN TRANSACTION')
        # Clear existing data
        tables = ['proiecte', 'tasks', 'task_subtasks', 'checklist_pif', 'checklist_categorii', 'jurnal', 'timer_sessions', 'global_task_sessions', 'atasamente', 'global_tasks', 'clienti', 'echipamente', 'project_templates', 'fault_codes', 'budget_state', 'budget_audit', 'parametri_master']
        for table in tables:
            cursor.execute(f'DELETE FROM {safe_table(table)}')

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

        # Restore tasks (v8+ columns: descriere, recurenta, updated_at, ordine)
        for t in data.get('tasks', []):
            cursor.execute('''
                INSERT INTO tasks (id, proiect_id, titlu, descriere, status, prioritate,
                    data_scadenta, data_finalizare, ordine, recurenta, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (t.get('id'), t.get('proiect_id'), t.get('titlu'), t.get('descriere'),
                  t.get('status'), t.get('prioritate'), t.get('data_scadenta'),
                  t.get('data_finalizare'), t.get('ordine', 0), t.get('recurenta'),
                  t.get('created_at'), t.get('updated_at')))

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

        # Restore timer_sessions (v8+ column: task_id)
        for ts in data.get('timer_sessions', []):
            cursor.execute('''
                INSERT INTO timer_sessions (id, proiect_id, task_id, start_time, stop_time, durata_secunde)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (ts.get('id'), ts.get('proiect_id'), ts.get('task_id'),
                  ts.get('start_time'), ts.get('stop_time'), ts.get('durata_secunde')))

        # Restore atasamente -- but only paths that resolve INSIDE UPLOAD_FOLDER.
        # A backup payload from an untrusted source could otherwise register
        # /etc/passwd or .assistant_config as an "attachment" and then read it
        # back through the download endpoint (path-traversal hardening).
        upload_root_real = os.path.realpath(UPLOAD_FOLDER)
        for a in data.get('atasamente', []):
            cale = (a.get('cale_locala') or '').strip()
            if not cale:
                continue
            try:
                cale_real = os.path.realpath(cale)
            except (OSError, ValueError):
                continue
            if not (cale_real == upload_root_real or cale_real.startswith(upload_root_real + os.sep)):
                logger.warning(f"Restore skipped attachment with path outside UPLOAD_FOLDER: {cale}")
                continue
            if not os.path.exists(cale_real):
                continue
            cursor.execute('''
                INSERT INTO atasamente (id, proiect_id, nume_fisier, tip_fisier, dimensiune, data, cale_locala)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (a.get('id'), a.get('proiect_id'), a.get('nume_fisier'), a.get('tip_fisier'),
                  a.get('dimensiune'), a.get('data'), a.get('cale_locala')))

        # Restore global_tasks (v9+ column: recurenta)
        for gt in data.get('global_tasks', []):
            cursor.execute('''
                INSERT INTO global_tasks (id, titlu, descriere, prioritate, status, categorie,
                    data_scadenta, data_finalizare, recurenta, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (gt.get('id'), gt.get('titlu'), gt.get('descriere'), gt.get('prioritate'),
                  gt.get('status'), gt.get('categorie'), gt.get('data_scadenta'),
                  gt.get('data_finalizare'), gt.get('recurenta'),
                  gt.get('created_at'), gt.get('updated_at')))

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

        # Restore task_subtasks (schema: id, task_id, titlu, done, ordine, created_at)
        for s in data.get('task_subtasks', []):
            cursor.execute('''
                INSERT INTO task_subtasks (id, task_id, titlu, done, ordine, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (s.get('id'), s.get('task_id'), s.get('titlu'),
                  s.get('done', 0), s.get('ordine', 0), s.get('created_at')))

        # Restore global_task_sessions
        for gts in data.get('global_task_sessions', []):
            cursor.execute('''
                INSERT INTO global_task_sessions (id, global_task_id, start_time, stop_time, durata_secunde)
                VALUES (?, ?, ?, ?, ?)
            ''', (gts.get('id'), gts.get('global_task_id'), gts.get('start_time'),
                  gts.get('stop_time'), gts.get('durata_secunde')))

        # Restore checklist_categorii
        for cat in data.get('checklist_categorii', []):
            cursor.execute('''
                INSERT INTO checklist_categorii (id, proiect_id, nume, ordine, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (cat.get('id'), cat.get('proiect_id'), cat.get('nume'),
                  cat.get('ordine', 0), cat.get('created_at')))

        # Restore fault_codes (actual schema from database.py)
        for fc in data.get('fault_codes', []):
            cursor.execute('''
                INSERT INTO fault_codes (id, producator, familie, cod, cod_secundar, tip,
                    nume, cauza, remediu, reactie, confirmare, extra_json, pagina, sursa)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (fc.get('id'), fc.get('producator'), fc.get('familie'), fc.get('cod'),
                  fc.get('cod_secundar'), fc.get('tip'), fc.get('nume'), fc.get('cauza'),
                  fc.get('remediu'), fc.get('reactie'), fc.get('confirmare'),
                  fc.get('extra_json'), fc.get('pagina'), fc.get('sursa')))

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
        except Exception:
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

    cur.execute('SELECT id, titlu, descriere, categorie FROM global_tasks '
                'WHERE titlu LIKE ? OR descriere LIKE ? LIMIT 10', (like, like))
    for r in cur.fetchall():
        results.append({'type': 'global_task', 'id': r['id'], 'title': r['titlu'],
                        'subtitle': r['categorie'] or 'Task zilnic', 'snippet': _search_snippet(r['descriere'], q)})

    cur.execute('SELECT c.id, c.titlu, c.proiect_id, p.nume AS pnume FROM checklist_pif c '
                'JOIN proiecte p ON c.proiect_id = p.id WHERE c.titlu LIKE ? LIMIT 10', (like,))
    for r in cur.fetchall():
        results.append({'type': 'checklist', 'id': r['id'], 'title': r['titlu'],
                        'subtitle': f"Checklist · {r['pnume']}", 'snippet': '', 'proiect_id': r['proiect_id']})

    cur.execute('SELECT j.id, j.continut, j.proiect_id, p.nume AS pnume FROM jurnal j '
                'JOIN proiecte p ON j.proiect_id = p.id WHERE j.continut LIKE ? LIMIT 10', (like,))
    for r in cur.fetchall():
        results.append({'type': 'jurnal', 'id': r['id'], 'title': _search_snippet(r['continut'], q, 50),
                        'subtitle': f"Jurnal · {r['pnume']}", 'snippet': _search_snippet(r['continut'], q),
                        'proiect_id': r['proiect_id']})

    cur.execute('SELECT e.id, e.nume, e.model, e.proiect_id, p.nume AS pnume FROM echipamente e '
                'JOIN proiecte p ON e.proiect_id = p.id '
                'WHERE e.nume LIKE ? OR e.model LIKE ? OR e.serial_number LIKE ? LIMIT 8',
                (like, like, like))
    for r in cur.fetchall():
        results.append({'type': 'echipament', 'id': r['id'], 'title': r['nume'],
                        'subtitle': f"Echipament · {r['pnume']}", 'snippet': r['model'] or '',
                        'proiect_id': r['proiect_id']})

    cur.execute('SELECT id, nume, telefon FROM clienti WHERE nume LIKE ? OR contact_principal LIKE ? LIMIT 6',
                (like, like))
    for r in cur.fetchall():
        results.append({'type': 'client', 'id': r['id'], 'title': r['nume'],
                        'subtitle': 'Client', 'snippet': r['telefon'] or ''})

    cur.execute('SELECT id, familie, parametru, descriere FROM parametri_master '
                'WHERE parametru LIKE ? OR descriere LIKE ? ORDER BY familie, parametru LIMIT 12',
                (like, like))
    for r in cur.fetchall():
        results.append({'type': 'parametru', 'id': r['id'], 'title': f"{r['parametru']} — {r['familie']}",
                        'subtitle': 'Parametru', 'snippet': _search_snippet(r['descriere'], q),
                        'familie': r['familie'], 'cod': r['parametru']})

    cur.execute('SELECT id, producator, familie, cod, tip, nume, cauza FROM fault_codes '
                'WHERE cod LIKE ? OR cod_secundar LIKE ? OR nume LIKE ? OR cauza LIKE ? '
                'ORDER BY producator, cod LIMIT 12', (like, like, like, like))
    for r in cur.fetchall():
        tip = r['tip'] or 'eroare'
        results.append({'type': 'fault_code', 'id': r['id'],
                        'title': f"{r['cod']} — {r['nume'] or ''}".strip(' —'),
                        'subtitle': f"Cod {tip} · {r['familie']}",
                        'snippet': _search_snippet(r['cauza'], q),
                        'familie': r['familie'], 'producator': r['producator'], 'cod': r['cod']})

    conn.close()

    from blueprints.obsidian import _obsidian_vault, _obsidian_index

    vault = _obsidian_vault()
    if vault:
        q_low = q.lower()
        n_added = 0
        for n in _obsidian_index(vault):
            if q_low not in n['title'].lower() and q_low not in n['content'].lower():
                continue
            results.append({'type': 'obsidian', 'id': n['path'], 'title': n['title'],
                            'subtitle': n['folder'] or 'Notită',
                            'snippet': _search_snippet(n['content'], q), 'path': n['path']})
            n_added += 1
            if n_added >= 12:
                break

    return jsonify({'results': results, 'query': q, 'count': len(results)})

# ---------------------------------------------------------------------------
# Dashboard home
# ---------------------------------------------------------------------------

@admin_bp.route('/api/dashboard/home', methods=['GET'])
@login_required
def dashboard_home():
    conn = get_db()
    cursor = conn.cursor()

    # Active projects count
    cursor.execute("SELECT COUNT(*) FROM proiecte WHERE status NOT IN ('finalizat', 'anulat')")
    active_projects = cursor.fetchone()[0]

    # Total projects
    cursor.execute("SELECT COUNT(*) FROM proiecte")
    total_projects = cursor.fetchone()[0]

    # Weekly hours (last 7 days)
    cursor.execute("""
        SELECT COALESCE(SUM(durata_secunde), 0) FROM timer_sessions
        WHERE start_time >= datetime('now', '-7 days')
    """)
    weekly_seconds = cursor.fetchone()[0]
    weekly_hours = round(weekly_seconds / 3600, 1)

    # Hours previous 7-day window for delta
    cursor.execute("""
        SELECT COALESCE(SUM(durata_secunde), 0) FROM timer_sessions
        WHERE start_time >= datetime('now', '-14 days')
          AND start_time < datetime('now', '-7 days')
    """)
    prev_weekly_hours = round(cursor.fetchone()[0] / 3600, 1)
    weekly_delta = round(weekly_hours - prev_weekly_hours, 1)

    # Urgent tasks — global + project-level (UNION)
    cursor.execute("""
        SELECT * FROM (
            SELECT id, titlu, prioritate, data_scadenta, categorie,
                   NULL as proiect_id, NULL as proiect_nume
            FROM global_tasks
            WHERE LOWER(prioritate) = 'urgent' AND status != 'done'

            UNION ALL

            SELECT t.id, t.titlu, t.prioritate, t.data_scadenta, '' as categorie,
                   t.proiect_id, p.nume as proiect_nume
            FROM tasks t JOIN proiecte p ON t.proiect_id = p.id
            WHERE LOWER(t.prioritate) = 'urgent' AND t.status != 'done'
              AND p.status NOT IN ('finalizat', 'anulat')
        )
        ORDER BY data_scadenta IS NULL, data_scadenta
        LIMIT 10
    """)
    urgent_tasks = [dict(r) for r in cursor.fetchall()]
    urgent_count = len(urgent_tasks)

    # Upcoming project deadlines (next 7 days)
    cursor.execute("""
        SELECT id, nume, client, deadline
        FROM proiecte
        WHERE deadline IS NOT NULL
          AND deadline >= date('now')
          AND deadline <= date('now', '+7 days')
          AND status NOT IN ('finalizat', 'anulat')
        ORDER BY deadline LIMIT 5
    """)
    upcoming_deadlines = [dict(r) for r in cursor.fetchall()]
    deadline_count = len(upcoming_deadlines)

    # Active timer -- only the standalone project timer, not per-task sessions
    # (per-task rows also have proiect_id set; without this filter the banner
    # could mis-attribute a per-task timer to the project as a whole).
    cursor.execute("""
        SELECT ts.id, ts.proiect_id as project_id, ts.start_time, p.nume as project_name
        FROM timer_sessions ts JOIN proiecte p ON ts.proiect_id = p.id
        WHERE ts.stop_time IS NULL AND ts.task_id IS NULL
        ORDER BY ts.start_time DESC LIMIT 1
    """)
    active_timer = cursor.fetchone()
    if active_timer:
        active_timer = dict(active_timer)

    # Today's tasks
    cursor.execute("""
        SELECT id, titlu, status, prioritate, categorie FROM global_tasks
        WHERE date(created_at) = date('now') OR status = 'to_do'
        ORDER BY
            CASE prioritate WHEN 'Urgent' THEN 0 WHEN 'Normal' THEN 1 ELSE 2 END,
            created_at DESC LIMIT 5
    """)
    todays_tasks = [dict(r) for r in cursor.fetchall()]

    # Recent journal
    cursor.execute("""
        SELECT j.id, j.proiect_id, j.data, j.continut, j.created_at, p.nume as project_name
        FROM jurnal j JOIN proiecte p ON j.proiect_id = p.id
        ORDER BY j.created_at DESC LIMIT 5
    """)
    recent_journal = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return jsonify({
        'stats': {
            'active_projects': active_projects,
            'total_projects': total_projects,
            'weekly_hours': weekly_hours,
            'weekly_delta': weekly_delta,
            'urgent_count': urgent_count,
            'deadline_count': deadline_count
        },
        'urgent_tasks': urgent_tasks,
        'upcoming_deadlines': upcoming_deadlines,
        'active_timer': active_timer,
        'todays_tasks': todays_tasks,
        'recent_journal': recent_journal
    })


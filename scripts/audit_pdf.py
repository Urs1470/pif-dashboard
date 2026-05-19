#!/usr/bin/env python3
"""
Audit parametri DB contra manualelor PDF.

Pentru fiecare familie, extrage parametrii din PDF-ul oficial și compară:
  - Parametri în DB care NU apar în PDF (fantome)
  - Parametri în PDF care NU sunt în DB (lipsuri)
  - Denumiri diferite (matched după cod)
  - Pagini reale per parametru (pentru fix pe câmpul `pagina`)

Usage:
    python scripts/audit_pdf.py ABB ACS580
    python scripts/audit_pdf.py --all
    python scripts/audit_pdf.py ABB ACS580 --apply-pagini   # update DB cu pagini reale

Output: scripts/audit_reports/audit_<FAMILIE>.json
"""
import os
import re
import sys
import json
import sqlite3
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANUALS_DIR = ROOT / 'manuals'
DB_PATH = ROOT / 'pif_dashboard.db'  # fallback; --db CLI flag overrides
REPORTS_DIR = ROOT / 'scripts' / 'audit_reports'

# Map familie → fișier PDF + parser type
FAMILIE_PDF_MAP = {
    'ACS580':              {'pdf': 'ACS580_Firmware_Manual.pdf',         'parser': 'abb'},
    'ACS880':              {'pdf': 'ACS880_Primary_Firmware_Manual.pdf', 'parser': 'abb'},
    'Danfoss_VLT_FC302':   {'pdf': 'Danfoss_VLT_FC302_Programming_Guide.pdf', 'parser': 'danfoss'},
    'Lenze_i550':          {'pdf': 'Lenze_i550_Manual.pdf',              'parser': 'lenze'},
    'Lenze_i950':          {'pdf': 'Lenze_i950_Manual.pdf',              'parser': 'lenze'},
    'SINAMICS_G120':       {'pdf': 'SINAMICS_G120_List_Manual.pdf',      'parser': 'siemens'},
    'SINAMICS_G130_G150':  {'pdf': 'SINAMICS_G130_G150_List_Manual.pdf', 'parser': 'siemens'},
    'SINAMICS_S120_S150':  {'pdf': 'SINAMICS_S120_S150_List_Manual.pdf', 'parser': 'siemens'},
}


def normalize(s):
    """Normalize a name for comparison: lowercase, strip, collapse whitespace."""
    if not s:
        return ''
    return re.sub(r'\s+', ' ', s.lower().strip())


# ---------- PDF parsers ----------

def parse_abb(pdf_path):
    """
    ABB ACS580/ACS880 firmware manuals. Uses pymupdf (fitz) for layout-aware
    extraction because pdfplumber collapses inter-word spaces on these PDFs.

    Layout (on a parameter definition page) per row group:
        col No.       (x < 60)   : "NN.NN"
        col Name      (60..128)  : "Param name"
        col Desc      (128..300) : "Description first line(s)"
        col Def/Type  (x >= 300) : "default ; unit" then "type"
    Range row appears one line below at x ~ 60, containing "min ... max unit".
    """
    try:
        import fitz  # pymupdf
    except ImportError:
        sys.stderr.write("ERROR: pymupdf not installed. Run: pip install pymupdf\n")
        sys.exit(2)

    out = {}
    code_re = re.compile(r'^\d{1,3}\.\d{1,3}(?:\.\d{1,3})?$')
    type_token_re = re.compile(r'^(?:u?int\d+|real\d+|bool|enum|hex|string)$', re.IGNORECASE)
    range_re = re.compile(r'^([+-]?[\d.,]+)\s*\.{2,3}\s*([+-]?[\d.,]+)\s*([A-Za-z°%/]+)?', re.IGNORECASE)
    enum_re = re.compile(r'^(\d+)\s*=\s*(.+?)\s*$')
    warning_re = re.compile(r'^WARNING!?\s*$', re.IGNORECASE)
    note_label_re = re.compile(r'^(Note|Notice|Example|Caution|Recommendation)\s*:\s*(.*)$', re.IGNORECASE)

    doc = fitz.open(pdf_path)
    try:
        for pno in range(doc.page_count):
            page = doc.load_page(pno)
            words = page.get_text("words")
            if not words:
                continue
            rows = {}
            for w in words:
                x0, y0, _, _, txt, *_ = w
                key = round(y0 / 3) * 3
                rows.setdefault(key, []).append((x0, txt))
            sorted_keys = sorted(rows.keys())

            # Auto-detect column boundaries from the page header
            x_name = 60
            x_desc = 128
            x_deftype = 300
            for ykey in sorted_keys[:8]:
                row = sorted(rows[ykey], key=lambda t: t[0])
                texts_lower = [t.lower() for _, t in row]
                if 'no.' in texts_lower and 'description' in texts_lower:
                    for x, t in row:
                        tl = t.lower()
                        if tl in ('name', 'name/value', 'name/range'):
                            x_name = int(x) - 5
                        elif tl == 'description':
                            x_desc = int(x) - 3
                        elif tl in ('def', 'def/type', 'def/fbeq16'):
                            x_deftype = int(x) - 3
                    break

            # Identify all param header rows
            param_starts = []  # list of (row_idx, code)
            for ri, ykey in enumerate(sorted_keys):
                row = sorted(rows[ykey], key=lambda t: t[0])
                if not row:
                    continue
                first_x, first_tok = row[0]
                if first_x >= x_name or not code_re.match(first_tok):
                    continue
                param_starts.append((ri, first_tok))

            # For each param, walk its rows up to the next param header
            for idx, (ri, code) in enumerate(param_starts):
                end_ri = param_starts[idx + 1][0] if idx + 1 < len(param_starts) else len(sorted_keys)

                header_row = sorted(rows[sorted_keys[ri]], key=lambda t: t[0])
                name_toks = [t for x, t in header_row if x_name <= x < x_desc]
                deftype_first = [t for x, t in header_row if x >= x_deftype]

                name = ' '.join(name_toks).strip()
                if len(name) < 3:
                    continue

                # Collect description lines + side-sections by walking inner rows.
                # Default/Type comes ONLY from the header row's right column — later
                # rows' right column tokens are typically value keys or FbEq scales.
                desc_parts = []
                deftype_parts = list(deftype_first)
                min_val = max_val = ''
                unit = ''
                warnings = []
                notes = []
                examples = []
                cautions = []
                recommendations = []
                values = []
                current_section = 'desc'  # what we're currently appending to

                # Header row's own description tokens
                head_desc = ' '.join(t for x, t in header_row if x_desc <= x < x_deftype).strip()
                if head_desc:
                    desc_parts.append(head_desc)

                range_found = False
                for rj in range(ri + 1, end_ri):
                    sub = sorted(rows[sorted_keys[rj]], key=lambda t: t[0])
                    if not sub:
                        continue
                    # Tokens grouped by x-column
                    left_toks = [t for x, t in sub if x < x_name]      # range row min/max
                    name_continuation = [t for x, t in sub if x_name <= x < x_desc]
                    body_toks = [t for x, t in sub if x_desc <= x < x_deftype]
                    right_toks = [t for x, t in sub if x >= x_deftype]
                    body_str = ' '.join(body_toks).strip()
                    full_left = ' '.join((t for x, t in sub if x < x_desc)).strip()

                    # Range row detection: tokens in name column form "min ... max unit"
                    # Check if the leftmost text matches range pattern
                    if not range_found and (name_continuation or left_toks):
                        candidate = ' '.join((name_continuation or left_toks)).strip()
                        rm = range_re.match(candidate)
                        if rm:
                            min_val = rm.group(1)
                            max_val = rm.group(2)
                            unit = unit or (rm.group(3) or '')
                            range_found = True
                            continue
                        # Range token might be split across two y-rows: "0.00..." line and "rpm" line
                        # Skip detection here; pattern below handles "0.00 ...10000.00 rpm" inline.

                    # Detect enum line: "1 = Scalar" form
                    if name_continuation and not body_toks:
                        em = enum_re.match(' '.join(name_continuation))
                        if em:
                            values.append({'key': em.group(1), 'label': em.group(2)})
                            current_section = 'values'
                            continue

                    # Detect section labels within description body
                    if body_str:
                        if warning_re.match(body_str):
                            current_section = 'warning'
                            warnings.append('')
                            continue
                        nm = note_label_re.match(body_str)
                        if nm:
                            label = nm.group(1).lower()
                            content = nm.group(2).strip()
                            if label == 'note':
                                notes.append(content)
                                current_section = 'note'
                            elif label == 'notice':
                                notes.append(content)
                                current_section = 'notice'
                            elif label == 'example':
                                examples.append(content)
                                current_section = 'example'
                            elif label == 'caution':
                                cautions.append(content)
                                current_section = 'caution'
                            elif label == 'recommendation':
                                recommendations.append(content)
                                current_section = 'recommendation'
                            continue
                        # Append to whatever section we're in
                        if current_section == 'desc':
                            desc_parts.append(body_str)
                        elif current_section == 'warning' and warnings:
                            warnings[-1] = (warnings[-1] + ' ' + body_str).strip()
                        elif current_section in ('note', 'notice') and notes:
                            notes[-1] = (notes[-1] + ' ' + body_str).strip()
                        elif current_section == 'example' and examples:
                            examples[-1] = (examples[-1] + ' ' + body_str).strip()
                        elif current_section == 'caution' and cautions:
                            cautions[-1] = (cautions[-1] + ' ' + body_str).strip()
                        elif current_section == 'recommendation' and recommendations:
                            recommendations[-1] = (recommendations[-1] + ' ' + body_str).strip()
                        elif current_section == 'values' and values:
                            # Values can wrap onto next line
                            values[-1]['label'] = (values[-1]['label'] + ' ' + body_str).strip()

                    # NOTE: do NOT accumulate right_toks from inner rows — those are
                    # value-key + FbEq scale columns, not the parameter's own default.

                description = ' '.join(desc_parts).strip()
                deftype = ' '.join(deftype_parts).strip()

                default_val = ''
                data_type = ''
                if deftype:
                    parts = deftype.replace('/', ' ').split()
                    for tok in reversed(parts):
                        if type_token_re.match(tok):
                            data_type = tok
                            break
                    rest = ' '.join(p for p in parts if not type_token_re.match(p)).strip()
                    rm = re.match(r'^(.+?)\s+([A-Za-z°%/]+)$', rest)
                    if rm:
                        default_val = rm.group(1).strip()
                        if not unit:
                            unit = rm.group(2)
                    else:
                        default_val = rest

                pdf_extra = {}
                if values:
                    pdf_extra['values'] = values
                if warnings:
                    pdf_extra['warnings'] = [w for w in warnings if w]
                if notes:
                    pdf_extra['notes'] = notes
                if examples:
                    pdf_extra['examples'] = examples
                if cautions:
                    pdf_extra['cautions'] = cautions
                if recommendations:
                    pdf_extra['recommendations'] = recommendations

                # Score: prefer entries with real range row + longer description.
                # When the same code appears in multiple places (TOC, cross-ref,
                # primary definition), the primary one wins.
                score = len(description)
                if min_val or max_val:
                    score += 500
                if pdf_extra:
                    score += 200
                if data_type:
                    score += 100

                existing = out.get(code)
                if existing and existing.get('_score', 0) >= score:
                    continue

                out[code] = {
                    'name': name,
                    'page': pno + 1,
                    'description': description,
                    'access': '',
                    'data_type': data_type,
                    'default': default_val,
                    'min': min_val,
                    'max': max_val,
                    'unit': unit,
                    'pdf_extra': pdf_extra if pdf_extra else None,
                    '_score': score,
                }
    finally:
        doc.close()
    # Strip the internal scoring key before returning
    for v in out.values():
        v.pop('_score', None)
    return out


def parse_danfoss(pdf_path):
    """
    Danfoss FC302 programming guide. Each parameter is a 3-row × 3-col table:

        Row 0: "<NN-NN> ParamName"   (single merged cell)
        Row 1: "Range: Function:"   or  "Option: Function:"
        Row 2: <default>* | [<min> - <max>\\n<unit>]  |  <description, multi-line>

    For "Option:" type (enumerated), there is no min/max range. We capture what we can.
    """
    try:
        import pdfplumber
    except ImportError:
        sys.stderr.write("ERROR: pdfplumber not installed.\n")
        sys.exit(2)

    out = {}
    header_re = re.compile(r'^\s*(\d{1,3}-\d{1,3})\s+(.+?)\s*$')
    range_re = re.compile(r'^\[\s*([^\-\]]+?)\s*-\s*([^\]]+?)\s*\]$')

    def clean(s):
        return re.sub(r'\s+', ' ', str(s or '').strip())

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for t in tables:
                if not t or len(t) < 2:
                    continue
                first_cell = clean(t[0][0]) if t[0] else ''
                hm = header_re.match(first_cell)
                if not hm:
                    continue
                code = hm.group(1)
                name = hm.group(2).strip()
                # Row 1 is column labels; data starts row 2 (sometimes row 1 if no labels)
                data_row = None
                ptype = ''  # "Range" or "Option"
                for ri in range(1, min(4, len(t))):
                    row = t[ri]
                    cells = [clean(c) for c in row]
                    joined = ' '.join(cells)
                    if 'Range:' in joined and 'Function:' in joined:
                        ptype = 'Range'
                        continue
                    if 'Option:' in joined and 'Function:' in joined:
                        ptype = 'Option'
                        continue
                    if any(cells):
                        data_row = cells
                        break
                if data_row is None:
                    if code not in out:
                        out[code] = {
                            'name': name, 'page': pno, 'description': '',
                            'access': '', 'data_type': ptype, 'default': '',
                            'min': '', 'max': '', 'unit': '', 'pdf_extra': None,
                        }
                    continue

                # data_row: 3 cells in normal case
                default_val = data_row[0] if len(data_row) > 0 else ''
                range_cell = data_row[1] if len(data_row) > 1 else ''
                desc_cell = data_row[2] if len(data_row) > 2 else ''
                # Default may carry trailing "*"
                default_val = default_val.rstrip('*').strip()

                min_val = max_val = unit = ''
                # range_cell normalized may be "[ 0 - par. 4-14 Hz]" or "[20 - 1000 Hz]"
                # We split on " - " to get [min, max+unit], then peel unit from end of max
                rc_inner = range_cell.strip()
                if rc_inner.startswith('[') and rc_inner.endswith(']'):
                    rc_inner = rc_inner[1:-1].strip()
                if ' - ' in rc_inner:
                    parts = rc_inner.split(' - ', 1)
                    min_val = parts[0].strip()
                    rest = parts[1].strip()
                    # Pull unit (last word, alphabetic+symbols) off the end if max is a number
                    um = re.match(r'^(.+?)\s+([A-Za-z°%/]+\d*)$', rest)
                    if um and re.match(r'^[+-]?[\d.,]+$', um.group(1).strip()):
                        max_val = um.group(1).strip()
                        unit = um.group(2)
                    else:
                        max_val = rest

                description = desc_cell.replace('\n', ' ').strip()

                # For Option type, harvest ALL data rows of this table as values
                pdf_extra = {}
                if ptype == 'Option':
                    values = []
                    for ri in range(2, len(t)):
                        row = t[ri]
                        if not row:
                            continue
                        cells = [clean(c) for c in row]
                        # Typical Option row: ['[0]', 'Label', 'Description']
                        # Sometimes ['', 'Label', 'Description'] if key empty
                        key = cells[0].strip('[]') if cells and cells[0] else ''
                        label_parts = []
                        if len(cells) > 1 and cells[1]:
                            label_parts.append(cells[1])
                        if len(cells) > 2 and cells[2]:
                            label_parts.append(cells[2])
                        label = ' '.join(label_parts).strip()
                        if key and label:
                            values.append({'key': key, 'label': label})
                    if values:
                        pdf_extra['values'] = values

                # Detect NOTICE boxes in description text
                if 'NOTICE' in description:
                    notice_parts = re.findall(r'NOTICE\s+(.+?)(?:\s+NOTICE|\s*$)', description)
                    if notice_parts:
                        pdf_extra['notices'] = [p.strip() for p in notice_parts]
                        # Remove NOTICE blocks from main description
                        description = re.sub(r'\s*NOTICE\s+.+?(?=\s+NOTICE|\s*$)', '', description).strip()

                if code not in out:
                    out[code] = {
                        'name': name,
                        'page': pno,
                        'description': description,
                        'access': '',
                        'data_type': ptype,
                        'default': default_val,
                        'min': min_val,
                        'max': max_val,
                        'unit': unit,
                        'pdf_extra': pdf_extra if pdf_extra else None,
                    }

        # Fallback: text-linear pass for any param not caught by the table extractor
        line_re = re.compile(r'^\s*(\d{1,3}-\d{1,3})\s+([A-Z][^\n]{2,100})')
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                m = line_re.match(line)
                if not m:
                    continue
                code = m.group(1)
                if code in out:
                    continue
                name = m.group(2).strip()
                if len(name) > 80:
                    name = name[:80].rsplit(' ', 1)[0]
                out[code] = {
                    'name': name, 'page': pno, 'description': '',
                    'access': '', 'data_type': '', 'default': '',
                    'min': '', 'max': '', 'unit': '', 'pdf_extra': None,
                }
    return out


def parse_lenze(pdf_path):
    """
    Lenze i550/i950 commissioning manuals lay parameters out in 3-column tables:

        Address    | Name / setting range / [default setting]               | Information
        0x2942:004 | Current controller parameters: d-axis gain             | Current controller parameters for
                   | 0.00 ... [26.00]* ... 750.00 V/A                       | "SLSM-PSM" motor control mode...

    Cells are multi-line (\\n-separated). The "Name" column packs three pieces:
      line 1 = parameter name
      line 2+ = setting range "MIN ... [DEFAULT] ... MAX UNIT" (optionally with footnote *)
    The "Information" column is the description. Access/data_type are not in PDF.
    """
    try:
        import pdfplumber
    except ImportError:
        sys.stderr.write("ERROR: pdfplumber not installed.\n")
        sys.exit(2)

    out = {}
    code_cell_re = re.compile(r'^\s*(0x[0-9A-F]{4,5}(?::\d{1,3})?)\s*$', re.IGNORECASE)
    # Lenze range: "MIN ... [DEFAULT] ... MAX [UNIT]" with possible footnote *
    range_re = re.compile(
        r'^\s*([+-]?[\d.,]+)\s*\.{2,3}\s*\[\s*([+-]?[\d.,]+)\s*\]\*?\s*\.{2,3}\s*([+-]?[\d.,]+)\s*([^\s*]*)\s*\*?\s*$'
    )

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.extract_tables() or []
            except Exception:
                tables = []
            for table in tables:
                if not table or len(table) < 2:
                    continue
                header = [str(c or '').strip() for c in table[0]]
                # Recognise parameter tables by their characteristic header
                if not any('Address' in h for h in header):
                    continue
                name_col = info_col = None
                for ci, h in enumerate(header):
                    hl = h.lower()
                    if 'setting range' in hl or hl == 'name' or 'name /' in hl:
                        name_col = ci
                    elif 'information' in hl:
                        info_col = ci
                if name_col is None:
                    name_col = 1 if len(header) > 1 else 0
                if info_col is None and len(header) > 2:
                    info_col = 2

                for row in table[1:]:
                    if not row:
                        continue
                    if len(row) <= name_col:
                        continue
                    addr = str(row[0] or '').strip()
                    cm = code_cell_re.match(addr)
                    if not cm:
                        continue
                    code = cm.group(1)
                    # Normalise hex letters to uppercase but keep "0x" prefix lowercase
                    if ':' in code:
                        h, idx = code.split(':')
                        code = h[:2] + h[2:].upper() + ':' + idx
                    else:
                        code = code[:2] + code[2:].upper()

                    name_cell = str(row[name_col] or '').strip()
                    info_cell = str(row[info_col] or '').strip() if info_col is not None and info_col < len(row) else ''

                    name_lines = [ln.strip() for ln in name_cell.split('\n') if ln.strip()]
                    name = name_lines[0] if name_lines else ''
                    min_val = max_val = default_val = unit = ''
                    for nl in name_lines[1:]:
                        rm = range_re.match(nl)
                        if rm:
                            min_val = rm.group(1)
                            default_val = rm.group(2)
                            max_val = rm.group(3)
                            unit = rm.group(4) or ''
                            break

                    description = info_cell.replace('\n', ' ').strip()
                    if len(name) < 2:
                        continue

                    # Build pdf_extra from Lenze conventions:
                    #   - Bullet-list values inside `info_cell`: lines starting with "•"
                    #   - "Note!" / "Notes:" inline blocks
                    #   - "Associated event ID:" entries
                    pdf_extra = {}
                    info_lines = [ln.strip() for ln in info_cell.split('\n') if ln.strip()]
                    bullets = [ln.lstrip('•').strip() for ln in info_lines if ln.startswith('•')]
                    if bullets:
                        # Values typically formatted "key: label" or just plain entries
                        values = []
                        for b in bullets:
                            vm = re.match(r'^(\d+|0x[0-9A-Fa-f]+)\s*[:=]?\s*(.+)$', b)
                            if vm:
                                values.append({'key': vm.group(1), 'label': vm.group(2).strip()})
                        if values:
                            pdf_extra['values'] = values
                        else:
                            pdf_extra['bullets'] = bullets

                    notes_match = re.search(r'Notes?!?\s*[:.]?\s*(.+?)$', info_cell, re.IGNORECASE)
                    if notes_match:
                        pdf_extra.setdefault('notes', []).append(notes_match.group(1).strip())

                    if code not in out:
                        out[code] = {
                            'name': name,
                            'page': pno,
                            'description': description,
                            'access': '',
                            'data_type': '',
                            'default': default_val,
                            'min': min_val,
                            'max': max_val,
                            'unit': unit,
                            'pdf_extra': pdf_extra if pdf_extra else None,
                        }

        # Fallback: catch params that pdfplumber didn't recognise as tables
        # (e.g. pages where table borders are missing). Linear regex on raw text
        # gets at least name + page; other fields stay empty.
        line_re = re.compile(
            r'^\s*(0x[0-9A-F]{4,5}(?::\d{1,3})?)\s+([A-Z][^\n]{2,120})',
            re.IGNORECASE
        )
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                m = line_re.match(line)
                if not m:
                    continue
                raw = m.group(1)
                if ':' in raw:
                    h, idx = raw.split(':')
                    code = h[:2] + h[2:].upper() + ':' + idx
                else:
                    code = raw[:2] + raw[2:].upper()
                if code in out:
                    continue
                name = m.group(2).strip()
                # Trim trailing description bleed: keep up to first long pause or sentence end
                # but Lenze names rarely exceed 80 chars in practice — clip there.
                if len(name) > 80:
                    name = name[:80].rsplit(' ', 1)[0]
                out[code] = {
                    'name': name,
                    'page': pno,
                    'description': '',
                    'access': '',
                    'data_type': '',
                    'default': '',
                    'min': '',
                    'max': '',
                    'unit': '',
                    'pdf_extra': None,
                }
    return out


def parse_siemens(pdf_path):
    """
    SINAMICS list manuals: each parameter block has a fixed multi-line layout:

        pNNNNN[idx] [PREFIX:] Name / Abbrev
        [HW tag e.g. CU240E-2]   Access level: N   Calculated: -   Data type: TYPE
        ...                      Can be changed: T   Scaling: -    Dyn. index: -
        ...                      Units group: -      Unit selection: - Func. diagram: -
        Min       Max          Factory setting
        <min> [unit]  <max> [unit]  <default> [unit]
        Description: <text spanning N lines until next field/param>
        [Dependency: / Notice: / Note: / ...]

    Extract: code, name, description, access, data_type, default, min, max, unit, page.
    """
    try:
        import pdfplumber
    except ImportError:
        sys.stderr.write("ERROR: pdfplumber not installed.\n")
        sys.exit(2)

    out = {}
    code_re = re.compile(r'^\s*([pr]\d{4,5})(?:\[[^\]]+\])?(?:\.\d+(?:\.{2,3}\d+)?)?\s+([^\n]+?)\s*$')
    access_re = re.compile(r'Access\s*level\s*:\s*(\S+)', re.IGNORECASE)
    # Data type can be "U32 / Binary", "FloatingPoint32", "Integer16" etc.
    # Stop at next field keyword (Dyn. index / Dynamic index / Scaling / Func.) or end-of-line.
    data_type_re = re.compile(
        r'Data\s*type\s*:\s*(.+?)(?:\s+(?:Dyn(?:amic|\.)?\s*index|Scaling|Func\.|Units?\s*group|P-Group|Expert\s*list)\b|$)',
        re.IGNORECASE
    )
    min_max_header_re = re.compile(r'^\s*Min\s+Max\s+Factory\s*setting\s*$', re.IGNORECASE)
    # Value-row tokens: number-or-dash optionally followed by [unit]
    val_token_re = re.compile(r'^(?:-|[+-]?\d[\d.,eE+\-]*(?:%|°[CF])?|0+[xb]?[0-9A-Fa-f]+[bh]?|FFFFh|[0-9A-Fa-f]+h)$')
    desc_re = re.compile(r'^Description\s*:\s*(.*)$', re.IGNORECASE)
    field_section_re = re.compile(
        r'^\s*(Description|Value|Dependency|Notice|Note|Recommend(?:ation|\.)?|Caution|WARNING|Refer to|Bit field|Example|Examples|Formula)\s*:\s*(.*)$',
        re.IGNORECASE
    )
    # Field sections that mark a structural break (used when extracting description, etc.)
    field_break_re = re.compile(
        r'^\s*(?:Dependency|Notice|Note|Recommend\.|Recommendation|Caution|WARNING|Refer to|Bit field|Value|Example|Examples|Formula|P-Group|Calculated|Can be changed|Scaling|Dyn\. index|Units group|Unit selection|Func\. diagram|Expert list|Not for motor)\s*:',
        re.IGNORECASE
    )
    # Footer line bleeding into descriptions on Siemens manuals
    footer_re = re.compile(
        r'(?:Siemens\s*AG|All\s*Rights\s*Reserved|SINAMICS\s*[A-Z\d/]+|List\s*Manual|©|6SL\d+-)',
        re.IGNORECASE
    )
    value_row_re = re.compile(r'^\s*([\-+]?\d+(?:\.\d+)?|0x[0-9A-Fa-f]+|[A-Z]+)\s*:\s*(.+?)\s*$')
    refer_codes_re = re.compile(r'[pr]\d{3,5}(?:\[\d+\])?|[A-Z]\d{3,5}')
    prefix_re = re.compile(r'^(?:[CB][IO](?:/[CB][IO])?\s*:\s*)+')
    abbrev_re = re.compile(r'\s*/\s*\S+\s*$')

    def parse_value_row(line):
        """Parse a Min/Max/Factory value row into (min,max,default,unit).
        Tokens are whitespace-separated; bracketed units attach to the preceding value:
            "0 [ms]   5000 [ms]   100 [ms]"  -> ('0','5000','100','ms')
            "0 2 1"                          -> ('0','2','1','')
            "- - -"                          -> ('','','','')
            "0000h FFFFh 0"                  -> ('0000h','FFFFh','0','')
        """
        toks = line.split()
        # Greedy pair "VAL [UNIT]" into one logical token, dropping the brackets.
        # Also handle Siemens hex/bin suffix: "0000 hex FFFF hex C000 hex" -> values "0000h"/"FFFFh"/"C000h"
        merged = []
        unit = ''
        i = 0
        while i < len(toks):
            t = toks[i]
            if i + 1 < len(toks) and toks[i + 1].startswith('[') and toks[i + 1].endswith(']'):
                merged.append(t)
                unit = unit or toks[i + 1].strip('[]')
                i += 2
            elif i + 1 < len(toks) and toks[i + 1].lower() in ('hex', 'bin', 'h', 'b'):
                merged.append(t + toks[i + 1].lower()[0])  # "0000h"
                i += 2
            else:
                merged.append(t)
                i += 1
        if len(merged) < 3:
            return '', '', '', ''
        # Convert "-" sentinels to empty string
        norm = ['' if m == '-' else m for m in merged[:3]]
        return norm[0], norm[1], norm[2], unit

    with pdfplumber.open(pdf_path) as pdf:
        all_pages = []
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                all_pages.append((pno, line))

    n = len(all_pages)
    i = 0
    while i < n:
        pno, line = all_pages[i]
        m = code_re.match(line)
        if not m:
            i += 1
            continue
        # Look ahead up to 6 lines for "Access level"
        access = ''
        access_idx = None
        for j in range(i + 1, min(i + 7, n)):
            am = access_re.search(all_pages[j][1])
            if am:
                access = am.group(1).strip().rstrip(':,')
                access_idx = j
                break
        if access_idx is None:
            i += 1
            continue

        code = m.group(1)
        name = m.group(2).strip()
        name = prefix_re.sub('', name)
        name = abbrev_re.sub('', name).strip()
        if len(name) < 3:
            i += 1
            continue

        # Extract data type within ~5 lines around access_idx
        data_type = ''
        for j in range(access_idx, min(access_idx + 5, n)):
            dm = data_type_re.search(all_pages[j][1])
            if dm:
                data_type = dm.group(1).strip()
                break

        # Find Min/Max/Factory header within ~12 lines after access
        min_val = max_val = default_val = ''
        unit = ''
        for j in range(access_idx, min(access_idx + 12, n)):
            if min_max_header_re.match(all_pages[j][1]):
                # Value row is usually j+1, sometimes j+2 (page break inserts a header)
                for k in range(j + 1, min(j + 4, n)):
                    candidate = all_pages[k][1].strip()
                    if not candidate:
                        continue
                    # Skip lines that are clearly not value rows (description start, page header)
                    if desc_re.match(candidate) or code_re.match(candidate):
                        break
                    mn, mx, dv, u = parse_value_row(candidate)
                    if mn or mx or dv:
                        min_val, max_val, default_val, unit = mn, mx, dv, u
                        break
                break

        # Walk forward from access_idx, segmenting into sections.
        # End-of-block markers: next param header, or having seen all expected sections
        # and hit a hardware re-declaration. We cap at 80 lines as safety.
        sections = {}  # name -> list of text lines
        current_section = None
        block_end = min(access_idx + 80, n)
        for j in range(access_idx, block_end):
            ln = all_pages[j][1]
            if code_re.match(ln) and j > access_idx + 2:
                # Next parameter starts here
                block_end = j
                break
            # Skip footer bleed lines (Siemens "© Siemens AG..." etc.)
            if footer_re.search(ln):
                current_section = None  # stop appending until next labeled section
                continue
            # Hardware re-tag rows like "PM230" / "CU240E-2" with no colon: ignore
            if min_max_header_re.match(ln):
                current_section = None
                continue
            fm = field_section_re.match(ln)
            if fm:
                current_section = fm.group(1).lower().rstrip('.')
                # Normalise variants
                if current_section in ('recommend', 'recommendation'):
                    current_section = 'recommendation'
                elif current_section in ('examples',):
                    current_section = 'example'
                sections.setdefault(current_section, []).append(fm.group(2).strip())
                continue
            if current_section is None:
                continue
            stripped = ln.strip()
            if not stripped:
                continue
            sections[current_section].append(stripped)

        # Build pdf_extra structure
        description = ' '.join(sections.get('description', [])).strip()
        pdf_extra = {}

        # values: parse "key: label" rows from Value section
        if 'value' in sections:
            values = []
            current_label = None
            for raw in sections['value']:
                vm = value_row_re.match(raw)
                if vm:
                    if current_label and values:
                        # finalise previous accumulated label
                        pass
                    values.append({'key': vm.group(1), 'label': vm.group(2)})
                else:
                    if values:
                        values[-1]['label'] = (values[-1]['label'] + ' ' + raw).strip()
            if values:
                pdf_extra['values'] = values

        for key in ('dependency', 'notice', 'note', 'recommendation', 'caution', 'warning', 'bit field', 'example', 'formula'):
            if key in sections:
                txt = ' '.join(sections[key]).strip()
                if txt:
                    pdf_extra[key.replace(' ', '_')] = txt

        # Refer to: extract comma-separated codes
        if 'refer to' in sections:
            refs_text = ' '.join(sections['refer to'])
            codes = list(dict.fromkeys(refer_codes_re.findall(refs_text)))
            if codes:
                pdf_extra['refer_to'] = codes

        if code not in out:
            out[code] = {
                'name': name,
                'page': pno,
                'description': description,
                'access': access,
                'data_type': data_type,
                'default': default_val,
                'min': min_val,
                'max': max_val,
                'unit': unit,
                'pdf_extra': pdf_extra if pdf_extra else None,
            }
        i = access_idx + 1
    return out


PARSERS = {'abb': parse_abb, 'danfoss': parse_danfoss, 'lenze': parse_lenze, 'siemens': parse_siemens}


# ---------- DB ----------

DB_FIELDS = ['descriere_scurta', 'descriere', 'acces', 'tip_date',
             'valoare_default_str', 'min', 'max', 'unitate', 'pagina', 'pdf_extra']

PDF_TO_DB = {
    'name': 'descriere_scurta',
    'description': 'descriere',
    'access': 'acces',
    'data_type': 'tip_date',
    'default': 'valoare_default_str',
    'min': 'min',
    'max': 'max',
    'unit': 'unitate',
    'page': 'pagina',
    'pdf_extra': 'pdf_extra',  # JSON serialized
}


def fetch_db_params(db_path, familie):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cols = ['id', 'parametru'] + DB_FIELDS
    cur.execute(
        f'SELECT {", ".join(cols)} FROM parametri_master WHERE familie = ?',
        (familie,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def apply_pagini_fix(db_path, updates):
    """updates: list of (id, new_page) tuples"""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany('UPDATE parametri_master SET pagina = ? WHERE id = ?',
                    [(p, i) for (i, p) in updates])
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected


def _to_float(s):
    """Best-effort string -> float; return None on failure."""
    if s is None:
        return None
    s = str(s).strip()
    if not s or s == '-':
        return None
    # Strip common suffix like "h", "b", "%" used in Siemens hex/bin notation
    if s.endswith('h') and re.fullmatch(r'[0-9A-Fa-f]+h', s):
        try:
            return float(int(s[:-1], 16))
        except ValueError:
            return None
    s2 = s.replace(',', '.').rstrip('%')
    try:
        return float(s2)
    except ValueError:
        return None


def apply_delete_orphans(db_path, ids):
    """Delete rows by id list. Returns number of rows actually removed."""
    if not ids:
        return 0
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.executemany('DELETE FROM parametri_master WHERE id = ?', [(i,) for i in ids])
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected


def apply_insert_new(db_path, familie, new_params):
    """Bulk INSERT params not yet in DB. new_params: list of (code, pdf_dict)."""
    if not new_params:
        return 0
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    rows = []
    for code, p in new_params:
        extra = p.get('pdf_extra')
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
        rows.append((
            familie,
            code,
            p.get('description') or '',
            p.get('access') or '',
            p.get('data_type') or '',
            _to_float(p.get('default')),
            p.get('default') or '',
            _to_float(p.get('min')),
            _to_float(p.get('max')),
            p.get('unit') or '',
            p.get('page'),
            code if code.startswith('0x') else '',
            p.get('name') or '',
            extra_json,
        ))
    cur.executemany('''
        INSERT OR IGNORE INTO parametri_master
            (familie, parametru, descriere, acces, tip_date,
             valoare_default, valoare_default_str, min, max, unitate,
             pagina, cod_hex, descriere_scurta, pdf_extra)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rows)
    conn.commit()
    affected = cur.rowcount
    conn.close()
    return affected


def apply_all_fields(db_path, updates):
    """updates: list of (id, dict_of_pdf_fields) — overwrite all non-empty PDF-derived fields.
    Only updates DB columns where the PDF value is non-empty (avoid clobbering with blanks).
    `pdf_extra` is serialized to JSON before writing.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    affected = 0
    for row_id, fields in updates:
        set_parts = []
        params = []
        for pdf_key, db_col in PDF_TO_DB.items():
            v = fields.get(pdf_key)
            if v in (None, '') or v == {}:
                continue
            if pdf_key == 'pdf_extra':
                v = json.dumps(v, ensure_ascii=False)
            set_parts.append(f'{db_col} = ?')
            params.append(v)
        if not set_parts:
            continue
        params.append(row_id)
        cur.execute(
            f'UPDATE parametri_master SET {", ".join(set_parts)} WHERE id = ?', params
        )
        affected += cur.rowcount
    conn.commit()
    conn.close()
    return affected


# ---------- Audit logic ----------

def audit_familie(producator, familie, db_path,
                  apply_pagini=False, apply_all=False,
                  delete_orphans=False, insert_new=False):
    info = FAMILIE_PDF_MAP.get(familie)
    if not info:
        return {'error': f'No PDF mapping for familie={familie}'}
    pdf_path = MANUALS_DIR / info['pdf']
    if not pdf_path.exists():
        return {'error': f'PDF not found: {pdf_path}'}

    parser_fn = PARSERS[info['parser']]
    print(f'[{familie}] Parsing {info["pdf"]}…', file=sys.stderr)
    pdf_params = parser_fn(pdf_path)
    print(f'[{familie}] Found {len(pdf_params)} params in PDF', file=sys.stderr)

    db_params = fetch_db_params(db_path, familie)
    print(f'[{familie}] DB has {len(db_params)} params', file=sys.stderr)

    db_codes = {p['parametru']: p for p in db_params}

    in_db_not_pdf = []
    name_mismatch = []
    page_fix = []
    diff_field_names = ['descriere', 'acces', 'tip_date', 'valoare_default_str',
                        'min', 'max', 'unitate', 'pdf_extra']
    field_diff_samples = {f: [] for f in diff_field_names}
    field_diff_count = {f: 0 for f in diff_field_names}
    field_missing = {f: 0 for f in diff_field_names}  # DB lipsește dar PDF are
    full_field_updates = []  # for --apply-all

    for code, dbp in db_codes.items():
        pdfp = pdf_params.get(code)
        if not pdfp:
            in_db_not_pdf.append({'id': dbp['id'], 'code': code, 'descriere': dbp.get('descriere_scurta')})
            continue

        # Name diff
        db_name = normalize(dbp.get('descriere_scurta') or '')
        pdf_name = normalize(pdfp['name'])
        if db_name and pdf_name and db_name not in pdf_name and pdf_name not in db_name:
            name_mismatch.append({
                'id': dbp['id'], 'code': code,
                'db_name': dbp.get('descriere_scurta'),
                'pdf_name': pdfp['name'],
            })

        # Page diff
        if dbp.get('pagina') != pdfp['page']:
            page_fix.append((dbp['id'], pdfp['page']))

        # Other field diffs (only when PDF actually has a value)
        for pdf_key, db_col in PDF_TO_DB.items():
            if db_col in ('descriere_scurta', 'pagina'):
                continue
            raw = pdfp.get(pdf_key)
            if isinstance(raw, dict):
                pdf_val = json.dumps(raw, ensure_ascii=False) if raw else ''
            elif isinstance(raw, str):
                pdf_val = raw.strip()
            else:
                pdf_val = raw
            if not pdf_val:
                continue
            db_val = dbp.get(db_col)
            if db_val is None or str(db_val).strip() == '':
                field_missing[db_col] += 1
                continue
            if normalize(str(db_val)) != normalize(str(pdf_val)):
                field_diff_count[db_col] += 1
                if len(field_diff_samples[db_col]) < 50:
                    field_diff_samples[db_col].append({
                        'id': dbp['id'], 'code': code,
                        'db': str(db_val)[:120], 'pdf': str(pdf_val)[:120],
                    })

        full_field_updates.append((dbp['id'], pdfp))

    in_pdf_not_db = []
    for code, pdfp in pdf_params.items():
        if code not in db_codes:
            in_pdf_not_db.append({
                'code': code,
                'name': pdfp.get('name', ''),
                'page': pdfp.get('page'),
                'description': (pdfp.get('description') or '')[:200],
            })

    report = {
        'producator': producator,
        'familie': familie,
        'pdf_file': info['pdf'],
        'totals': {
            'db_count': len(db_params),
            'pdf_count': len(pdf_params),
            'in_db_not_pdf': len(in_db_not_pdf),
            'in_pdf_not_db': len(in_pdf_not_db),
            'name_mismatch': len(name_mismatch),
            'page_fix_needed': len(page_fix),
            'field_diff_count': field_diff_count,  # real total of diffs
            'field_missing_db': field_missing,     # DB blank but PDF has value
        },
        'samples': {
            'in_db_not_pdf': in_db_not_pdf[:50],
            'in_pdf_not_db': in_pdf_not_db[:50],
            'name_mismatch': name_mismatch[:50],
            'field_diff': field_diff_samples,
        },
    }

    if apply_pagini and page_fix:
        affected = apply_pagini_fix(db_path, page_fix)
        report['page_fix_applied'] = affected
        print(f'[{familie}] Applied {affected} page fixes to DB', file=sys.stderr)

    if apply_all and full_field_updates:
        affected = apply_all_fields(db_path, full_field_updates)
        report['all_fields_applied'] = affected
        print(f'[{familie}] Applied {affected} full-field updates to DB', file=sys.stderr)

    if delete_orphans and in_db_not_pdf:
        ids = [r['id'] for r in in_db_not_pdf]
        affected = apply_delete_orphans(db_path, ids)
        report['orphans_deleted'] = affected
        print(f'[{familie}] Deleted {affected} orphan rows from DB', file=sys.stderr)

    if insert_new and in_pdf_not_db:
        new_pairs = [(item['code'], pdf_params[item['code']]) for item in in_pdf_not_db
                     if item['code'] in pdf_params]
        affected = apply_insert_new(db_path, familie, new_pairs)
        report['new_params_inserted'] = affected
        print(f'[{familie}] Inserted {affected} new params from PDF', file=sys.stderr)

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('producator', nargs='?', help='ABB, Danfoss, Lenze, Siemens')
    ap.add_argument('familie',    nargs='?', help='Specific familie (e.g. ACS580). Omit for all of producator.')
    ap.add_argument('--all', action='store_true', help='Audit ALL families')
    ap.add_argument('--apply-pagini', action='store_true', help='Update DB with real page numbers from PDF')
    ap.add_argument('--apply-all', action='store_true',
                    help='Update DB with ALL fields from PDF (description, type, default, min/max, unit, page)')
    ap.add_argument('--delete-orphans', action='store_true',
                    help='Delete rows in DB that are not in PDF (in_db_not_pdf). USE WITH CAUTION.')
    ap.add_argument('--insert-new', action='store_true',
                    help='Bulk INSERT params present in PDF but missing from DB.')
    ap.add_argument('--reextract', action='store_true',
                    help='Wipe descriere + pdf_extra columns then repopulate from PDF '
                         '(equivalent to UPDATE SET descriere=NULL, pdf_extra=NULL before --apply-all).')
    ap.add_argument('--db', default=str(DB_PATH), help='Path to SQLite DB')
    args = ap.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.all:
        families_to_run = list(FAMILIE_PDF_MAP.keys())
    elif args.producator and args.familie:
        families_to_run = [args.familie]
    elif args.producator:
        # Map producator -> familii (mirrors app.py PRODUCATOR_FAMILII)
        prod_map = {
            'ABB':     ['ACS580', 'ACS880'],
            'Danfoss': ['Danfoss_VLT_FC302'],
            'Lenze':   ['Lenze_i550', 'Lenze_i950'],
            'Siemens': ['SINAMICS_G120', 'SINAMICS_G130_G150', 'SINAMICS_S120_S150'],
        }
        families_to_run = prod_map.get(args.producator, [])
        if not families_to_run:
            print(f'Unknown producator: {args.producator}', file=sys.stderr)
            sys.exit(1)
    else:
        ap.print_help()
        sys.exit(0)

    # --reextract: wipe descriere + pdf_extra columns first (for the families in scope)
    if args.reextract:
        conn = sqlite3.connect(args.db)
        cur = conn.cursor()
        placeholders = ','.join('?' * len(families_to_run))
        cur.execute(
            f"UPDATE parametri_master SET descriere = NULL, pdf_extra = NULL "
            f"WHERE familie IN ({placeholders})",
            families_to_run
        )
        wiped = cur.rowcount
        conn.commit()
        conn.close()
        print(f'[reextract] Wiped descriere+pdf_extra on {wiped} rows '
              f'across {len(families_to_run)} families', file=sys.stderr)
        # Force --apply-all so the audit re-populates them
        args.apply_all = True

    summary = []
    for fam in families_to_run:
        rep = audit_familie(args.producator or '?', fam, args.db,
                             apply_pagini=args.apply_pagini, apply_all=args.apply_all,
                             delete_orphans=args.delete_orphans, insert_new=args.insert_new)
        out_file = REPORTS_DIR / f'audit_{fam}.json'
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
        summary.append({'familie': fam, 'output': str(out_file), 'totals': rep.get('totals', {}), 'error': rep.get('error')})

    print(json.dumps({'summary': summary}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

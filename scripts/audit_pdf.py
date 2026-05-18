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

    doc = fitz.open(pdf_path)
    try:
        for pno in range(doc.page_count):
            page = doc.load_page(pno)
            words = page.get_text("words")  # (x0,y0,x1,y1,word,block,line,word_no)
            if not words:
                continue
            # Group by y-row (tolerance 3 px)
            rows = {}
            for w in words:
                x0, y0, _, _, txt, *_ = w
                key = round(y0 / 3) * 3
                rows.setdefault(key, []).append((x0, txt))
            sorted_keys = sorted(rows.keys())

            # Auto-detect column boundaries from the page header "No. | Name | Description | Def/Type"
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

            for ri, ykey in enumerate(sorted_keys):
                row = sorted(rows[ykey], key=lambda t: t[0])
                if not row:
                    continue
                first_x, first_tok = row[0]
                if first_x >= x_name or not code_re.match(first_tok):
                    continue
                code = first_tok
                if code in out:
                    continue

                # Slice tokens by x column using detected boundaries
                name_toks = [t for x, t in row if x_name <= x < x_desc]
                desc_toks = [t for x, t in row if x_desc <= x < x_deftype]
                deftype_toks = [t for x, t in row if x >= x_deftype]

                name = ' '.join(name_toks).strip()
                description = ' '.join(desc_toks).strip()
                deftype = ' '.join(deftype_toks).strip()

                # default + type extraction from right col: usually "VAL [;VAL] unit / type"
                default_val = ''
                data_type = ''
                unit = ''
                if deftype:
                    # type token is typically the last alphabetic word matching enum/uint16/etc.
                    parts = deftype.replace('/', ' ').split()
                    for tok in reversed(parts):
                        if type_token_re.match(tok):
                            data_type = tok
                            break
                    # Reconstruct without type token for default/unit
                    rest = ' '.join(p for p in parts if not type_token_re.match(p)).strip()
                    # Unit is usually last alphabetic token after the numeric value
                    rm = re.match(r'^(.+?)\s+([A-Za-z°%/]+)$', rest)
                    if rm:
                        default_val = rm.group(1).strip()
                        unit = rm.group(2)
                    else:
                        default_val = rest

                # Range row: look at next row groups for "MIN ... MAX UNIT" at x ~ Name col
                min_val = max_val = ''
                for rj in range(ri + 1, min(ri + 8, len(sorted_keys))):
                    sub = sorted(rows[sorted_keys[rj]], key=lambda t: t[0])
                    if sub and code_re.match(sub[0][1]) and sub[0][0] < x_name:
                        break
                    range_toks = [t for x, t in sub if x_name - 10 <= x < x_deftype]
                    if not range_toks:
                        continue
                    rstr = ' '.join(range_toks)
                    rm = range_re.search(rstr)
                    if rm:
                        min_val = rm.group(1)
                        max_val = rm.group(2)
                        if not unit and rm.group(3):
                            unit = rm.group(3)
                        break

                if len(name) < 3:
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
                }
    finally:
        doc.close()
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
                            'min': '', 'max': '', 'unit': '',
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

                if code not in out:
                    out[code] = {
                        'name': name,
                        'page': pno,
                        'description': description,
                        'access': '',
                        'data_type': ptype,  # Range or Option
                        'default': default_val,
                        'min': min_val,
                        'max': max_val,
                        'unit': unit,
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
                    'min': '', 'max': '', 'unit': '',
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
    field_break_re = re.compile(
        r'^\s*(?:Dependency|Notice|Note|Recommend\.|Recommendation|Caution|WARNING|Refer to|Bit field|Value|P-Group|Calculated|Can be changed|Scaling|Dyn\. index|Units group|Unit selection|Func\. diagram|Expert list|Not for motor)\s*:',
        re.IGNORECASE
    )
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

        # Description: capture from "Description:" until next field-break or next param header
        description = ''
        for j in range(access_idx, min(access_idx + 30, n)):
            dm = desc_re.match(all_pages[j][1])
            if dm:
                parts = [dm.group(1).strip()]
                for k in range(j + 1, min(j + 20, n)):
                    nxt = all_pages[k][1]
                    if code_re.match(nxt):  # next param header
                        break
                    if field_break_re.match(nxt):  # next field section
                        break
                    if min_max_header_re.match(nxt):
                        break
                    if nxt.strip():
                        parts.append(nxt.strip())
                description = ' '.join(parts).strip()
                break

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
            }
        i = access_idx + 1
    return out


PARSERS = {'abb': parse_abb, 'danfoss': parse_danfoss, 'lenze': parse_lenze, 'siemens': parse_siemens}


# ---------- DB ----------

DB_FIELDS = ['descriere_scurta', 'descriere', 'acces', 'tip_date',
             'valoare_default_str', 'min', 'max', 'unitate', 'pagina']

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


def apply_all_fields(db_path, updates):
    """updates: list of (id, dict_of_pdf_fields) — overwrite all non-empty PDF-derived fields.
    Only updates DB columns where the PDF value is non-empty (avoid clobbering with blanks).
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    affected = 0
    for row_id, fields in updates:
        set_parts = []
        params = []
        for pdf_key, db_col in PDF_TO_DB.items():
            v = fields.get(pdf_key)
            if v in (None, ''):
                continue
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

def audit_familie(producator, familie, db_path, apply_pagini=False, apply_all=False):
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
    field_diffs = {f: [] for f in ['descriere', 'acces', 'tip_date',
                                    'valoare_default_str', 'min', 'max', 'unitate']}
    field_missing = {f: 0 for f in field_diffs}  # DB lipsește dar PDF are
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
            pdf_val = (pdfp.get(pdf_key) or '').strip() if isinstance(pdfp.get(pdf_key), str) else pdfp.get(pdf_key)
            if not pdf_val:
                continue
            db_val = dbp.get(db_col)
            if db_val is None or str(db_val).strip() == '':
                field_missing[db_col] += 1
                continue
            if normalize(str(db_val)) != normalize(str(pdf_val)):
                if len(field_diffs[db_col]) < 50:
                    field_diffs[db_col].append({
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
            'field_diff_count': {k: len(v) for k, v in field_diffs.items()},
            'field_missing_db': field_missing,  # DB blank but PDF has value
        },
        'samples': {
            'in_db_not_pdf': in_db_not_pdf[:50],
            'in_pdf_not_db': in_pdf_not_db[:50],
            'name_mismatch': name_mismatch[:50],
            'field_diff': field_diffs,
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

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('producator', nargs='?', help='ABB, Danfoss, Lenze, Siemens')
    ap.add_argument('familie',    nargs='?', help='Specific familie (e.g. ACS580). Omit for all of producator.')
    ap.add_argument('--all', action='store_true', help='Audit ALL families')
    ap.add_argument('--apply-pagini', action='store_true', help='Update DB with real page numbers from PDF')
    ap.add_argument('--apply-all', action='store_true',
                    help='Update DB with ALL fields from PDF (description, type, default, min/max, unit, page)')
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

    summary = []
    for fam in families_to_run:
        rep = audit_familie(args.producator or '?', fam, args.db,
                             apply_pagini=args.apply_pagini, apply_all=args.apply_all)
        out_file = REPORTS_DIR / f'audit_{fam}.json'
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
        summary.append({'familie': fam, 'output': str(out_file), 'totals': rep.get('totals', {}), 'error': rep.get('error')})

    print(json.dumps({'summary': summary}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

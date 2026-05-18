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
    ABB ACS580/ACS880 manuals: parameters appear as `NN.NN   Name`.
    Common pattern: ' 01.01 Motor speed used   text.'
    Returns dict: {code: {'name': str, 'page': int}}
    """
    try:
        import pdfplumber
    except ImportError:
        sys.stderr.write("ERROR: pdfplumber not installed. Run: pip install pdfplumber\n")
        sys.exit(2)

    out = {}
    pat = re.compile(r'^\s*(\d{1,3}\.\d{1,3}(?:\.\d{1,3})?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                m = pat.match(line)
                if m:
                    code = m.group(1)
                    name = m.group(2).strip()
                    # Skip lines that look like value enumerations (single short words)
                    if len(name) < 4:
                        continue
                    # Keep first occurrence (parameter definition appears once at intro)
                    if code not in out:
                        out[code] = {'name': name, 'page': pno}
    return out


def parse_danfoss(pdf_path):
    """
    Danfoss FC302: parameters as `NN-NN ParamName` (uses hyphen not dot).
    Returns dict keyed by `NN-NN`.
    """
    try:
        import pdfplumber
    except ImportError:
        sys.stderr.write("ERROR: pdfplumber not installed.\n")
        sys.exit(2)

    out = {}
    pat = re.compile(r'^\s*(\d{1,3}-\d{1,3})\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                m = pat.match(line)
                if m:
                    code = m.group(1)
                    name = m.group(2).strip()
                    if len(name) < 4:
                        continue
                    if code not in out:
                        out[code] = {'name': name, 'page': pno}
    return out


def parse_lenze(pdf_path):
    """
    Lenze i550/i950: parameters as `0xXXXXX:YY` or `0xXXXX` plus a name on the line.
    """
    try:
        import pdfplumber
    except ImportError:
        sys.stderr.write("ERROR: pdfplumber not installed.\n")
        sys.exit(2)

    out = {}
    pat = re.compile(r'^\s*(0x[0-9A-F]{4,5}(?::\d+)?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})', re.IGNORECASE)

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                m = pat.match(line)
                if m:
                    code = m.group(1).upper().replace('0X', '0x')
                    name = m.group(2).strip()
                    if len(name) < 4:
                        continue
                    if code not in out:
                        out[code] = {'name': name, 'page': pno}
    return out


def parse_siemens(pdf_path):
    """
    SINAMICS list manuals: each parameter block starts with `pNNNNN[idx] Name / Abbrev`
    and the immediately following line contains "Access level:" (sometimes preceded by
    a hardware tag like CU240E-2 or PM240). That structural follow-line is unique to
    real parameter definitions, so use it as a confirmation gate.
    """
    try:
        import pdfplumber
    except ImportError:
        sys.stderr.write("ERROR: pdfplumber not installed.\n")
        sys.exit(2)

    out = {}
    # Code can carry array notation [0...n] or bit-range .0...14 — both stripped from key
    code_re = re.compile(r'^\s*([pr]\d{4,5})(?:\[[^\]]+\])?(?:\.\d+(?:\.{2,3}\d+)?)?\s+([^\n]+?)\s*$')
    access_re = re.compile(r'Access\s*level\s*:', re.IGNORECASE)
    prefix_re = re.compile(r'^(?:[CB][IO](?:/[CB][IO])?\s*:\s*)+')
    abbrev_re = re.compile(r'\s*/\s*\S+\s*$')

    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            lines = text.split('\n')
            for i, line in enumerate(lines):
                m = code_re.match(line)
                if not m:
                    continue
                # Confirm: one of next 4 lines contains "Access level:"
                lookahead = ' '.join(lines[i + 1:i + 5])
                if not access_re.search(lookahead):
                    continue
                code = m.group(1)
                name = m.group(2).strip()
                name = prefix_re.sub('', name)
                name = abbrev_re.sub('', name)
                name = name.strip()
                if len(name) < 3:
                    continue
                if code not in out:
                    out[code] = {'name': name, 'page': pno}
    return out


PARSERS = {'abb': parse_abb, 'danfoss': parse_danfoss, 'lenze': parse_lenze, 'siemens': parse_siemens}


# ---------- DB ----------

def fetch_db_params(db_path, familie):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        'SELECT id, parametru, descriere_scurta, pagina FROM parametri_master WHERE familie = ?',
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


# ---------- Audit logic ----------

def audit_familie(producator, familie, db_path, apply=False):
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

    in_db_not_pdf = []  # parametri în DB care NU apar în PDF
    name_mismatch = []
    page_fix = []      # parametri unde pagina trebuie actualizată

    for code, dbp in db_codes.items():
        pdfp = pdf_params.get(code)
        if not pdfp:
            in_db_not_pdf.append({'id': dbp['id'], 'code': code, 'descriere': dbp.get('descriere_scurta')})
            continue
        # Name comparison
        db_name = normalize(dbp.get('descriere_scurta') or '')
        pdf_name = normalize(pdfp['name'])
        if db_name and pdf_name and db_name not in pdf_name and pdf_name not in db_name:
            name_mismatch.append({
                'id': dbp['id'], 'code': code,
                'db_name': dbp.get('descriere_scurta'),
                'pdf_name': pdfp['name']
            })
        # Page fix
        if dbp.get('pagina') != pdfp['page']:
            page_fix.append((dbp['id'], pdfp['page']))

    in_pdf_not_db = []
    for code, pdfp in pdf_params.items():
        if code not in db_codes:
            in_pdf_not_db.append({'code': code, 'name': pdfp['name'], 'page': pdfp['page']})

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
        },
        'samples': {
            'in_db_not_pdf': in_db_not_pdf[:50],
            'in_pdf_not_db': in_pdf_not_db[:50],
            'name_mismatch': name_mismatch[:50],
        },
    }

    if apply and page_fix:
        affected = apply_pagini_fix(db_path, page_fix)
        report['page_fix_applied'] = affected
        print(f'[{familie}] Applied {affected} page fixes to DB', file=sys.stderr)

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('producator', nargs='?', help='ABB, Danfoss, Lenze, Siemens')
    ap.add_argument('familie',    nargs='?', help='Specific familie (e.g. ACS580). Omit for all of producator.')
    ap.add_argument('--all', action='store_true', help='Audit ALL families')
    ap.add_argument('--apply-pagini', action='store_true', help='Update DB with real page numbers from PDF')
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
        rep = audit_familie(args.producator or '?', fam, args.db, apply=args.apply_pagini)
        out_file = REPORTS_DIR / f'audit_{fam}.json'
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(rep, f, indent=2, ensure_ascii=False)
        summary.append({'familie': fam, 'output': str(out_file), 'totals': rep.get('totals', {}), 'error': rep.get('error')})

    print(json.dumps({'summary': summary}, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()

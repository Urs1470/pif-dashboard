#!/usr/bin/env python3
"""Inspect the fault / alarm / warning sections of every drive manual PDF.

Goal: locate each manual's fault-code section, report its page range, and dump
representative sample pages so we can see the exact structure (columns, fields)
before designing a parser + DB schema.

Output: scripts/fault_codes_inspection.txt  (detailed page dumps)
        + a compact summary on the console.
"""
import re
from pathlib import Path
import fitz  # pymupdf

ROOT = Path(__file__).resolve().parent.parent
MANUALS_DIR = ROOT / 'manuals'
OUT = ROOT / 'scripts' / 'fault_codes_inspection.txt'

PDFS = [
    ('ABB ACS580',                 'ACS580_Firmware_Manual.pdf'),
    ('ABB ACS880',                 'ACS880_Primary_Firmware_Manual.pdf'),
    ('Danfoss VLT FC302',          'Danfoss_VLT_FC302_Programming_Guide.pdf'),
    ('Lenze i550',                 'Lenze_i550_Manual.pdf'),
    ('Lenze i950',                 'Lenze_i950_Manual.pdf'),
    ('Siemens SINAMICS G120',      'SINAMICS_G120_List_Manual.pdf'),
    ('Siemens SINAMICS G130/G150', 'SINAMICS_G130_G150_List_Manual.pdf'),
    ('Siemens SINAMICS S120/S150', 'SINAMICS_S120_S150_List_Manual.pdf'),
]

HEADING_KEYWORDS = [
    'fault tracing', 'warning and fault', 'fault and warning',
    'warning messages', 'fault messages', 'faults and warnings',
    'faults and alarms', 'list of faults and alarms', 'list of faults',
    'list of warnings', 'warnings and alarms', 'error messages',
    'error codes', 'troubleshooting', 'trouble shooting',
    'diagnostics and fault', 'fault and alarm', 'error list',
]

# Fault-code-like token patterns to find the dense list pages.
RE_FCODE = re.compile(r'\bF\d{4,6}\b')              # Siemens faults  F30001
RE_ACODE = re.compile(r'\bA\d{4,6}\b')              # Siemens alarms  A07910
RE_DANF = re.compile(r'(?:WARNING|ALARM)', re.I)    # Danfoss WARNING/ALARM
RE_HEX4 = re.compile(r'^[0-9A-Fa-f]{4}\b')          # ABB hex code at line start
RE_LENZE = re.compile(r'\b\d{4,5}\b')               # Lenze decimal error codes


def page_signal(txt):
    """Per-page fault-code signal counts."""
    f = len(RE_FCODE.findall(txt))
    a = len(RE_ACODE.findall(txt))
    danf = len(RE_DANF.findall(txt))
    hex4 = sum(1 for ln in txt.splitlines() if RE_HEX4.match(ln.strip()))
    return {'F': f, 'A': a, 'WARN/ALARM': danf, 'hex4line': hex4,
            'score': f + a + danf + hex4 * 2}


def inspect(label, fname, fh):
    path = MANUALS_DIR / fname
    sep = '=' * 100
    fh.write(f"\n{sep}\n{label}  --  {fname}\n{sep}\n")
    if not path.exists():
        fh.write("  MISSING\n")
        return f"{label:<28} MISSING"

    doc = fitz.open(path)
    n = doc.page_count
    pages = []
    for i in range(n):
        try:
            pages.append(doc.load_page(i).get_text())
        except Exception:
            pages.append('')

    fh.write(f"Pages: {n}\n\n")

    # --- heading keyword hits ---
    fh.write("-- Heading-keyword hits (page is 0-indexed; +1 = PDF page label) --\n")
    heading_pages = []
    for i, txt in enumerate(pages):
        low = txt.lower()
        for kw in HEADING_KEYWORDS:
            idx = low.find(kw)
            if idx != -1:
                snippet = ' '.join(txt[max(0, idx - 30):idx + 90].split())
                fh.write(f"  p{i:>4} | {kw:<22} | {snippet}\n")
                heading_pages.append(i)
    if not heading_pages:
        fh.write("  (none)\n")

    # --- per-page signal ---
    sig = [page_signal(t) for t in pages]
    scored = [(i, s) for i, s in enumerate(sig) if s['score'] > 0]
    scored.sort(key=lambda x: -x[1]['score'])
    fh.write("\n-- Top 12 pages by fault-code signal --\n")
    for i, s in scored[:12]:
        fh.write(f"  p{i:>4} | score={s['score']:>4} | F={s['F']:>3} A={s['A']:>3} "
                 f"WARN/ALARM={s['WARN/ALARM']:>3} hex4line={s['hex4line']:>3}\n")

    # --- find the densest contiguous run (the actual fault list) ---
    hi = {i for i, s in enumerate(sig) if s['score'] >= 8}
    runs = []
    if hi:
        cur = [min(hi)]
        for i in sorted(hi)[1:]:
            if i - cur[-1] <= 3:
                cur.append(i)
            else:
                runs.append((cur[0], cur[-1]))
                cur = [i]
        runs.append((cur[0], cur[-1]))
    runs.sort(key=lambda r: -(r[1] - r[0]))
    fh.write("\n-- Contiguous high-signal runs (likely the fault list), longest first --\n")
    for a, b in runs[:5]:
        tot = sum(sig[i]['score'] for i in range(a, b + 1))
        fh.write(f"  pages {a}..{b}  ({b - a + 1} pp, total score {tot})\n")
    if not runs:
        fh.write("  (none >= threshold)\n")

    # --- dump sample pages: start of the biggest run + a mid page ---
    dump_pages = []
    if runs:
        a, b = runs[0]
        dump_pages = [a, a + 1, (a + b) // 2]
    elif scored:
        top = scored[0][0]
        dump_pages = [top, top + 1]
    dump_pages = sorted(set(p for p in dump_pages if 0 <= p < n))

    for p in dump_pages:
        fh.write(f"\n----- RAW TEXT  p{p} (label ~{p + 1})  score={sig[p]['score']} -----\n")
        txt = pages[p]
        fh.write(txt[:4500])
        if len(txt) > 4500:
            fh.write(f"\n...[truncated, page has {len(txt)} chars]...\n")

    doc.close()
    summary_runs = ', '.join(f"{a}-{b}" for a, b in runs[:3]) or '-'
    return f"{label:<28} {n:>4}pp  runs: {summary_runs}"


def main():
    summaries = []
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write("FAULT-CODE SECTION INSPECTION\n")
        for label, fname in PDFS:
            print(f"  inspecting {label} ...")
            summaries.append(inspect(label, fname, fh))
    print("\n=== SUMMARY ===")
    for s in summaries:
        print(s)
    print(f"\nDetailed dumps -> {OUT}")


if __name__ == '__main__':
    main()

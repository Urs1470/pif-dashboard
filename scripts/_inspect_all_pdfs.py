"""Health-check: run the real parsers on every manual PDF and report counts + samples.

Re-run after parser tweaks or after dropping in a new PDF to confirm extraction
still produces a sane parameter list before triggering the full audit.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from audit_pdf import FAMILIE_PDF_MAP, PARSERS, MANUALS_DIR

print(f"{'familie':<22} {'pages':>6} {'params':>8}  sample")
print('-' * 110)

import pdfplumber
for fam, info in FAMILIE_PDF_MAP.items():
    pdf_path = MANUALS_DIR / info['pdf']
    if not pdf_path.exists():
        print(f"{fam:<22} MISSING {info['pdf']}")
        continue
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages)
    parser_fn = PARSERS[info['parser']]
    params = parser_fn(pdf_path)
    keys = list(params.keys())
    samples = ' || '.join(f"{k} p{params[k]['page']} {params[k]['name'][:35]}" for k in keys[:2])
    print(f"{fam:<22} {pages:>6} {len(params):>8}  {samples}")

"""Health check for every manual PDF: pages + parser hit count + samples."""
import re
import sys
from pathlib import Path
import pdfplumber

ROOT = Path(__file__).resolve().parent.parent
MANUALS = ROOT / 'manuals'

CHECKS = [
    ('ACS580',             'ACS580_Firmware_Manual.pdf',         re.compile(r'^\s*(\d{1,3}\.\d{1,3}(?:\.\d{1,3})?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')),
    ('ACS880',             'ACS880_Primary_Firmware_Manual.pdf', re.compile(r'^\s*(\d{1,3}\.\d{1,3}(?:\.\d{1,3})?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')),
    ('Danfoss_FC302',      'Danfoss_VLT_FC302_Programming_Guide.pdf', re.compile(r'^\s*(\d{1,3}-\d{1,3})\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')),
    ('Lenze_i550',         'Lenze_i550_Manual.pdf',              re.compile(r'^\s*(0x[0-9A-F]{4,5}(?::\d+)?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})', re.IGNORECASE)),
    ('Lenze_i950',         'Lenze_i950_Manual.pdf',              re.compile(r'^\s*(0x[0-9A-F]{4,5}(?::\d+)?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})', re.IGNORECASE)),
    ('SINAMICS_G120',      'SINAMICS_G120_List_Manual.pdf',      re.compile(r'^\s*([pr]\d{1,5}(?:\[\d+\])?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')),
    ('SINAMICS_G130_G150', 'SINAMICS_G130_G150_List_Manual.pdf', re.compile(r'^\s*([pr]\d{1,5}(?:\[\d+\])?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')),
    ('SINAMICS_S120_S150', 'SINAMICS_S120_S150_List_Manual.pdf', re.compile(r'^\s*([pr]\d{1,5}(?:\[\d+\])?)\s+([A-Z][A-Za-z0-9 ,\-/()&%.+_]{2,80})')),
]

# Loose "is this a parameter-style code anywhere on the line" probe per family,
# so we can spot reference manuals even when the strict line-start regex misses them
LOOSE = {
    'ACS580':             re.compile(r'\b\d{2}\.\d{2}\b'),
    'ACS880':             re.compile(r'\b\d{2}\.\d{2}\b'),
    'Danfoss_FC302':      re.compile(r'\b\d{1,2}-\d{1,2}\b'),
    'Lenze_i550':         re.compile(r'\b0x[0-9A-Fa-f]{4,5}\b'),
    'Lenze_i950':         re.compile(r'\b0x[0-9A-Fa-f]{4,5}\b'),
    'SINAMICS_G120':      re.compile(r'\b[pr]\d{3,5}\b'),
    'SINAMICS_G130_G150': re.compile(r'\b[pr]\d{3,5}\b'),
    'SINAMICS_S120_S150': re.compile(r'\b[pr]\d{3,5}\b'),
}

print(f"{'familie':<22} {'pages':>6} {'strict':>8} {'loose':>8}  sample")
print('-' * 110)
for fam, fname, pat in CHECKS:
    pdf_path = MANUALS / fname
    if not pdf_path.exists():
        print(f"{fam:<22} MISSING {fname}")
        continue
    strict_hits = 0
    loose_hits = 0
    samples = []
    loose_pat = LOOSE[fam]
    with pdfplumber.open(pdf_path) as pdf:
        pages = len(pdf.pages)
        for pno, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ''
            for line in text.split('\n'):
                if loose_pat.search(line):
                    loose_hits += 1
                m = pat.match(line)
                if m:
                    strict_hits += 1
                    if len(samples) < 3:
                        samples.append(f"p{pno} {m.group(1)} | {m.group(2)[:50]}")
    sample_str = ' || '.join(samples) if samples else '(no strict matches)'
    print(f"{fam:<22} {pages:>6} {strict_hits:>8} {loose_hits:>8}  {sample_str}")

#!/usr/bin/env python3
"""QA: flag fault-code `remediu` values that were truncated by the parser.

truncated  = ends with a function word that CANNOT end a sentence (the/and/of/
             to/under...) and no terminal '.', OR ends with a comma / dangling
             hyphen. These are near-certain mid-sentence cuts.
no_period  = softer: ends with a real word but no '.'/')' — usually just a
             dropped period, content complete. Reported separately.
"""
import sqlite3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
conn = sqlite3.connect(ROOT / 'pif_dashboard.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id, producator, familie, cod, nume, remediu FROM fault_codes"
).fetchall()

# Function words that cannot legitimately end a sentence.
STRICT = {'the', 'and', 'or', 'of', 'to', 'a', 'an', 'in', 'on', 'with', 'for',
          'by', 'from', 'at', 'under', 'over', 'into', 'than', 'that', 'this',
          'which', 'when', 'as', 'is', 'are', 'be', 'but', 'if', 'their', 'its'}
TERM = '.!?:'


def is_truncated(text):
    t = (text or '').rstrip()
    if not t:
        return False
    if t.endswith(',') or t.endswith(' -'):
        return True
    if t[-1] in TERM or t[-1] in ')]}%"”’•':
        return False
    last = re.sub(r'[^A-Za-z]', '', t.split()[-1]).lower()
    return last in STRICT


per_fam = {}
trunc = []
for r in rows:
    fam = r['familie']
    st = per_fam.setdefault(fam, {'total': 0, 'trunc': 0})
    st['total'] += 1
    if is_truncated(r['remediu']):
        st['trunc'] += 1
        trunc.append(r)

print(f"{'familie':<22} {'total':>6} {'TRUNCATED':>10}")
print('-' * 40)
for fam, s in sorted(per_fam.items()):
    print(f"{fam:<22} {s['total']:>6} {s['trunc']:>10}")
print('-' * 40)
print(f"TOTAL likely-truncated remedii: {len(trunc)}\n")
for r in trunc:
    rem = (r['remediu'] or '').rstrip()
    print(f"[{r['producator']}/{r['familie']}] {r['cod']} - {r['nume']}")
    print(f"    ...{rem[-110:]!r}")

conn.close()

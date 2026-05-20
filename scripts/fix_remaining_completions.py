import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

EXTRA_MAP = {'sel': 'selection', 'fil': 'filter'}
FRAG_RE = re.compile(r'^(.*?)\b(sel|fil)$', re.IGNORECASE)

def complete(name):
    m = FRAG_RE.match(name.strip())
    if m:
        return m.group(1) + EXTRA_MAP[m.group(2).lower()]
    return name

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

cur.execute("SELECT id, parametru, descriere_scurta FROM parametri_master WHERE descriere_scurta IS NOT NULL")
rows = cur.fetchall()
fixed = 0
for param_id, param, name in rows:
    new = complete(name)
    if new != name:
        cur.execute("UPDATE parametri_master SET descriere_scurta=? WHERE id=?", (new, param_id))
        fixed += 1
        print(f"  {param:<10} [{name}] -> [{new}]")

conn.commit()
conn.close()
print(f"Fixed: {fixed}")

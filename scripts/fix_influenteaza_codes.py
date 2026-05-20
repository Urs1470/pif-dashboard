"""Fix leading-zero codes in influenteaza field for ACS580."""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

# Pattern for ABB leading-zero codes in influenteaza
# e.g. '01.61, 07.25' -> '1.61, 7.25'
LEADING_ZERO_RE = re.compile(r'\b0+(\d+\.\d+)\b')

def fix_influenteaza(text):
    if not text:
        return text
    return LEADING_ZERO_RE.sub(r'\1', text)

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

cur.execute("""
    SELECT id, parametru, influenteaza FROM parametri_master
    WHERE familie='ACS580' AND influenteaza IS NOT NULL AND influenteaza != ''
""")
rows = cur.fetchall()

fixed = 0
for param_id, param, inf in rows:
    new_inf = fix_influenteaza(inf)
    if new_inf != inf:
        cur.execute("UPDATE parametri_master SET influenteaza=? WHERE id=?", (new_inf, param_id))
        fixed += 1
        print(f"  {param}: [{inf}] -> [{new_inf}]")

print(f"\nFixed influenteaza: {fixed} ACS580 params")

conn.commit()
conn.close()

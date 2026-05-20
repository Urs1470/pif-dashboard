"""
Fix ACS880 descriere_scurta: strip trailing hyphen artifact from truncated PDF names.
'AI supervision func-' -> 'AI supervision func'
'Motor speed estim-' -> 'Motor speed estim'

Also verify descriere hyphenation is clean.
"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# Verify descriere state
cur.execute("SELECT descriere FROM parametri_master WHERE familie='ACS880' AND descriere IS NOT NULL AND descriere != ''")
rows = cur.fetchall()
hyph_count = sum(1 for r in rows if re.search(r'\w+- +[a-z]', r[0]))
print(f"descriere hyphenation artifacts in DB: {hyph_count}")

# Fix descriere_scurta: strip trailing '-'
cur.execute(
    "SELECT id, parametru, descriere_scurta FROM parametri_master "
    "WHERE familie='ACS880' AND descriere_scurta LIKE '%-'"
)
rows = cur.fetchall()
print(f"\ndescriefe_scurta ending with '-': {len(rows)}")

fixed = 0
for param_id, parametru, desc_scurta in rows:
    # Strip trailing hyphen
    new_name = desc_scurta.rstrip('-').rstrip()
    if new_name != desc_scurta:
        cur.execute(
            "UPDATE parametri_master SET descriere_scurta=? WHERE id=?",
            (new_name, param_id)
        )
        fixed += 1

conn.commit()

# Verify
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS880' AND descriere_scurta LIKE '%-'")
remaining = cur.fetchone()[0]

conn.close()
print(f"Fixed: {fixed} names")
print(f"Remaining with '-' at end: {remaining}")

# Show sample
print("\nSample fixed names:")
for _, p, name in rows[:8]:
    print(f"  {p}: [{name}] -> [{name.rstrip('-').rstrip()}]")

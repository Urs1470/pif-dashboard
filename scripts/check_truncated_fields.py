"""Check all PDF-derived fields for truncation artifacts."""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# Check valoare_default_str with trailing '-'
cur.execute("""
    SELECT familie, COUNT(*) FROM parametri_master
    WHERE valoare_default_str LIKE '%-'
    GROUP BY familie ORDER BY familie
""")
rows = cur.fetchall()
print("valoare_default_str ending with '-':")
for fam, cnt in rows:
    print(f"  {fam}: {cnt}")

print()
cur.execute("""
    SELECT parametru, descriere_scurta, valoare_default_str
    FROM parametri_master
    WHERE familie='ACS880' AND valoare_default_str LIKE '%-'
    ORDER BY parametru LIMIT 20
""")
for p, ds, vd in cur.fetchall():
    print(f"  {p}: name=[{ds}] default=[{vd}]")

# Also check descriere_scurta that look truncated (short last word)
print("\ndescriefe_scurta ACS880 group 99.x:")
cur.execute("""
    SELECT parametru, descriere_scurta, valoare_default_str
    FROM parametri_master
    WHERE familie='ACS880' AND parametru LIKE '99.%'
    ORDER BY CAST(SUBSTR(parametru, 4) AS REAL)
""")
for p, ds, vd in cur.fetchall():
    print(f"  {p}: [{ds}] | default=[{vd}]")

conn.close()

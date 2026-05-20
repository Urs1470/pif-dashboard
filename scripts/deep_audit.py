"""Deep audit: find params where descriere_scurta = parametru code, dot-only values, etc."""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

print("=== 1. descriere_scurta == parametru (no real name) ===")
cur.execute("""
    SELECT familie, COUNT(*) FROM parametri_master
    WHERE TRIM(descriere_scurta) = TRIM(parametru)
    GROUP BY familie ORDER BY familie
""")
for fam, cnt in cur.fetchall():
    print(f"  {fam}: {cnt}")

cur.execute("""
    SELECT familie, parametru, descriere_scurta FROM parametri_master
    WHERE TRIM(descriere_scurta) = TRIM(parametru)
    ORDER BY familie, parametru LIMIT 30
""")
print("\n  Sample:")
for fam, p, ds in cur.fetchall():
    print(f"    {fam} {p}: [{ds}]")

print("\n=== 2. descriere_scurta empty/null ===")
cur.execute("""
    SELECT familie, COUNT(*) FROM parametri_master
    WHERE descriere_scurta IS NULL OR TRIM(descriere_scurta) = ''
    GROUP BY familie ORDER BY familie
""")
for fam, cnt in cur.fetchall():
    print(f"  {fam}: {cnt}")

print("\n=== 3. max/min = '.' (dot artifact) ===")
cur.execute("""
    SELECT familie, COUNT(*) FROM parametri_master
    WHERE CAST(max AS TEXT) = '.' OR CAST(min AS TEXT) = '.'
    GROUP BY familie ORDER BY familie
""")
for fam, cnt in cur.fetchall():
    print(f"  {fam}: {cnt}")

cur.execute("""
    SELECT familie, parametru, descriere_scurta, min, max FROM parametri_master
    WHERE CAST(max AS TEXT) = '.' OR CAST(min AS TEXT) = '.'
    LIMIT 10
""")
print("  Sample dot values:")
for fam, p, ds, mn, mx in cur.fetchall():
    print(f"    {fam} {p}: [{ds}] min={mn} max={mx}")

print("\n=== 4. valoare_default_str = parametru code ===")
cur.execute("""
    SELECT COUNT(*) FROM parametri_master
    WHERE TRIM(valoare_default_str) = TRIM(parametru)
""")
print(f"  Count: {cur.fetchone()[0]}")

print("\n=== 5. descriere_scurta looks like code (starts with digit-dot or 0x) ===")
cur.execute("""
    SELECT familie, COUNT(*) FROM parametri_master
    WHERE descriere_scurta REGEXP '^\d+\.\d+' OR descriere_scurta REGEXP '^0x'
    GROUP BY familie ORDER BY familie
""")
try:
    for fam, cnt in cur.fetchall():
        print(f"  {fam}: {cnt}")
except:
    # SQLite may not have REGEXP, do it in Python
    pass

# Python-side check
cur.execute("SELECT familie, parametru, descriere_scurta FROM parametri_master WHERE descriere_scurta IS NOT NULL")
rows = cur.fetchall()
code_like = [(f, p, ds) for f, p, ds in rows if re.match(r'^\d+\.\d+|^0x[0-9A-Fa-f]', ds or '')]
from collections import Counter
fam_counts = Counter(f for f, p, ds in code_like)
print("\n  descriere_scurta that look like param codes:")
for fam, cnt in sorted(fam_counts.items()):
    print(f"    {fam}: {cnt}")
if code_like:
    print("  Sample:")
    for f, p, ds in code_like[:15]:
        print(f"    {f} {p}: [{ds}]")

conn.close()

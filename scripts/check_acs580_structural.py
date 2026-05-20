import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# ACS580: same parser, same potential issues
print("ACS580 structural issues:")
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS580' AND CAST(max AS TEXT)='.'")
print(f"  max='.': {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS580' AND TRIM(descriere_scurta)=TRIM(parametru)")
print(f"  descriere_scurta = parametru: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS580' AND parametru LIKE '0%'")
print(f"  parametru with leading zero: {cur.fetchone()[0]}")

cur.execute("SELECT parametru, descriere_scurta FROM parametri_master WHERE familie='ACS580' AND parametru LIKE '0%'")
for p, ds in cur.fetchall():
    print(f"    [{p}]: [{ds}]")

# Check all families for leading zero issue
print("\nLeading zero parametru across ALL families:")
cur.execute("""
    SELECT familie, COUNT(*) FROM parametri_master
    WHERE parametru REGEXP '^0[^x]'
    GROUP BY familie
""")
# SQLite no REGEXP, do in Python
cur.execute("SELECT familie, parametru, descriere_scurta FROM parametri_master WHERE descriere_scurta IS NOT NULL")
rows = cur.fetchall()
import re
leading_zero = [(f, p, ds) for f, p, ds in rows if re.match(r'^0[^x]', p)]
from collections import Counter
counts = Counter(f for f, p, ds in leading_zero)
for fam, cnt in sorted(counts.items()):
    print(f"  {fam}: {cnt}")
if leading_zero:
    print("  Sample:")
    for f, p, ds in leading_zero[:10]:
        print(f"    {f} [{p}]: [{ds}]")

conn.close()

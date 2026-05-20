"""Fix structural DB issues:
1. ACS880 param 06.18 - leading zero code and descriere_scurta = code
2. max = '.' artifacts (133 ACS880 params)
"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# --- 1. Investigate 06.18 ---
print("=== 06.18 investigation ===")
cur.execute("SELECT * FROM parametri_master WHERE parametru='06.18' AND familie='ACS880'")
cols = [d[0] for d in cur.description]
row = cur.fetchone()
if row:
    for col, val in zip(cols, row):
        if val not in (None, ''):
            print(f"  {col}: {str(val)[:120]}")

# Check if there's a canonical 6.18 without leading zero
cur.execute("SELECT id, parametru, descriere_scurta FROM parametri_master WHERE familie='ACS880' AND parametru IN ('6.18','06.18')")
print("\nAll entries for 6.18 / 06.18:")
for row in cur.fetchall():
    print(f"  id={row[0]} parametru=[{row[1]}] desc=[{row[2]}]")

# Check other params with leading zeros
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS880' AND parametru LIKE '0%'")
print(f"\nACS880 params with leading zero: {cur.fetchone()[0]}")
cur.execute("SELECT parametru, descriere_scurta FROM parametri_master WHERE familie='ACS880' AND parametru LIKE '0%'")
for p, ds in cur.fetchall():
    print(f"  [{p}]: [{ds}]")

# --- 2. max = '.' investigation ---
print("\n=== max='.' investigation ===")
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS880' AND CAST(max AS TEXT)='.'")
print(f"ACS880 params with max='.': {cur.fetchone()[0]}")

# What should the max be? Check what the PDF says
cur.execute("""
    SELECT parametru, descriere_scurta, min, max, unitate, valoare_default_str
    FROM parametri_master
    WHERE familie='ACS880' AND CAST(max AS TEXT)='.'
    LIMIT 20
""")
print("\nSample params with max='.':")
for p, ds, mn, mx, u, vd in cur.fetchall():
    print(f"  {p}: [{ds}] min={mn} max={mx} unit={u} default={vd}")

# --- Fix 1: 06.18 - fix leading zero in parametru ---
# First check if 6.18 already exists
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS880' AND parametru='6.18'")
exists_6_18 = cur.fetchone()[0]
print(f"\n6.18 exists in DB: {exists_6_18}")

if not exists_6_18:
    # Rename 06.18 -> 6.18 and clear the bad descriere_scurta
    cur.execute("""
        UPDATE parametri_master
        SET parametru='6.18', descriere_scurta=''
        WHERE familie='ACS880' AND parametru='06.18'
    """)
    print(f"Fixed: renamed 06.18 -> 6.18, cleared descriere_scurta")
else:
    print("6.18 already exists - 06.18 is a duplicate, need to investigate")

# --- Fix 2: max = '.' -> NULL ---
cur.execute("""
    UPDATE parametri_master SET max=NULL
    WHERE CAST(max AS TEXT)='.'
""")
print(f"\nFixed max='.': {cur.rowcount} params set to NULL")

# Also check min = '.'
cur.execute("UPDATE parametri_master SET min=NULL WHERE CAST(min AS TEXT)='.'")
print(f"Fixed min='.': {cur.rowcount} params set to NULL")

conn.commit()
conn.close()
print("\nDone.")

"""
Fix PDF truncation in valoare_default_str and do targeted fix of known
ACS880 group 99 descriere_scurta truncated names.
"""
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

# Known correct names for ACS880 group 99 (from official ABB documentation)
ACS880_99_NAMES = {
    '99.6':  'Motor nominal current',
    '99.7':  'Motor nominal voltage',
    '99.8':  'Motor nominal frequency',
    '99.9':  'Motor nominal speed',
    '99.10': 'Motor nominal power',
    '99.11': 'Motor nominal cos phi',
    '99.12': 'Motor nominal torque',
    '99.14': 'Last ID run performed',
    '99.15': 'Motor pole pairs calculated',
    '99.18': 'Sine filter inductance',
    '99.19': 'Sine filter capacitance',
}

# Known correct valoare_default_str for ACS880 group 99
ACS880_99_DEFAULTS = {
    '99.3': 'Asynchronous motor',
}

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# 1) Fix valoare_default_str with trailing '-' (NOT single '-' which is a valid indicator)
cur.execute("""
    SELECT id, familie, parametru, valoare_default_str
    FROM parametri_master
    WHERE valoare_default_str LIKE '%-'
      AND LENGTH(valoare_default_str) > 1
""")
rows = cur.fetchall()
print(f"valoare_default_str ending with '-' (multi-char): {len(rows)}")

fixed_vd = 0
for param_id, fam, param, vd in rows:
    new_vd = vd.rstrip('-').rstrip()
    if new_vd and new_vd != vd:
        cur.execute("UPDATE parametri_master SET valoare_default_str=? WHERE id=?", (new_vd, param_id))
        fixed_vd += 1

print(f"Fixed valoare_default_str: {fixed_vd} params")

# Apply known ACS880 99.x default override
for param_code, correct_default in ACS880_99_DEFAULTS.items():
    cur.execute("""
        UPDATE parametri_master SET valoare_default_str=?
        WHERE familie='ACS880' AND parametru=?
    """, (correct_default, param_code))
    if cur.rowcount:
        print(f"  Set default {param_code} -> [{correct_default}]")

# 2) Fix known truncated ACS880 group 99 descriere_scurta
fixed_names = 0
for param_code, correct_name in ACS880_99_NAMES.items():
    cur.execute("""
        UPDATE parametri_master SET descriere_scurta=?
        WHERE familie='ACS880' AND parametru=?
          AND (descriere_scurta IS NULL OR descriere_scurta != ?)
    """, (correct_name, param_code, correct_name))
    if cur.rowcount:
        fixed_names += 1
        print(f"  Fixed name {param_code}: [{correct_name}]")

print(f"Fixed ACS880 group 99 names: {fixed_names}")

# 3) Also do ACS580 if it has similar issues
cur.execute("""
    SELECT COUNT(*) FROM parametri_master
    WHERE familie='ACS580' AND valoare_default_str LIKE '%-' AND LENGTH(valoare_default_str) > 1
""")
print(f"\nACS580 valoare_default_str still truncated: {cur.fetchone()[0]}")

conn.commit()
conn.close()
print("\nDone.")

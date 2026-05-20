"""Delete ghost/duplicate parameter entries."""
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# Verify before delete
print("=== Before delete ===")
cur.execute("""
    SELECT id, parametru, descriere_scurta, descriere
    FROM parametri_master
    WHERE familie='ACS880' AND parametru IN ('6.18','06.18')
    ORDER BY parametru
""")
for row in cur.fetchall():
    print(f"  id={row[0]} param=[{row[1]}] desc=[{row[2]}] | descriere={str(row[3])[:80]}")

# Delete the ghost: 06.18 with garbage data
cur.execute("""
    DELETE FROM parametri_master
    WHERE familie='ACS880' AND parametru='06.18'
      AND descriere_scurta='06.18'
""")
deleted = cur.rowcount
print(f"\nDeleted ghost entries: {deleted}")

# Also check for other params where descriere_scurta = parametru (might be other ghosts)
cur.execute("""
    SELECT id, familie, parametru, descriere_scurta, descriere
    FROM parametri_master
    WHERE TRIM(descriere_scurta) = TRIM(parametru)
""")
remaining = cur.fetchall()
if remaining:
    print(f"\nRemaining params with descriere_scurta = parametru:")
    for row in remaining:
        print(f"  id={row[0]} {row[1]} [{row[2]}] descriere={str(row[4])[:80]}")
else:
    print("\nNo more params with descriere_scurta = parametru")

# Verify total count
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS880'")
print(f"\nACS880 total after delete: {cur.fetchone()[0]}")

# Also verify max='.' is truly gone
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE CAST(max AS TEXT)='.'")
print(f"Params with max='.': {cur.fetchone()[0]}")

conn.commit()
conn.close()
print("Done.")

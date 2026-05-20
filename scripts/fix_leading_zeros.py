"""
Fix ABB (ACS580 + ACS880) params where group number has leading zero:
'01.61' -> '1.61', '07.25' -> '7.25' etc.

Strategy:
- If normalized code (without leading zero) doesn't exist: RENAME
- If normalized code already exists: the leading-zero entry is a DUPLICATE -> DELETE
"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

def normalize_abb_code(code):
    """'01.61' -> '1.61', '6.18' -> '6.18' (no change)."""
    m = re.match(r'^0+(\d+\.\d+.*)$', code)
    return m.group(1) if m else code

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

for familie in ('ACS580', 'ACS880'):
    cur.execute("""
        SELECT id, parametru, descriere_scurta, explicatie
        FROM parametri_master
        WHERE familie=? AND parametru LIKE '0%' AND parametru NOT LIKE '0x%'
        ORDER BY parametru
    """, (familie,))
    leading_zero_rows = cur.fetchall()

    if not leading_zero_rows:
        print(f"{familie}: no leading-zero params")
        continue

    print(f"\n{familie}: {len(leading_zero_rows)} params with leading zeros")

    renamed = 0
    deleted = 0

    for row_id, param, desc, expl in leading_zero_rows:
        norm = normalize_abb_code(param)
        if norm == param:
            continue  # no change needed

        # Check if normalized code already exists
        cur.execute(
            "SELECT id, descriere_scurta, explicatie FROM parametri_master WHERE familie=? AND parametru=?",
            (familie, norm)
        )
        existing = cur.fetchone()

        if existing is None:
            # Rename: leading-zero -> normalized
            cur.execute(
                "UPDATE parametri_master SET parametru=? WHERE id=?",
                (norm, row_id)
            )
            renamed += 1
            # print(f"  RENAME {param} -> {norm}: [{desc}]")
        else:
            # Duplicate: leading-zero is extra entry
            # Keep the better one (prefer the one with more data)
            existing_id, existing_desc, existing_expl = existing

            # If the leading-zero entry has richer data, merge before deleting
            # For now: if existing has no explicatie but this one does, update it
            if not existing_expl and expl:
                cur.execute(
                    "UPDATE parametri_master SET explicatie=? WHERE id=?",
                    (expl, existing_id)
                )
            if not existing_desc and desc:
                cur.execute(
                    "UPDATE parametri_master SET descriere_scurta=? WHERE id=?",
                    (desc, existing_id)
                )

            # Delete the leading-zero duplicate
            cur.execute("DELETE FROM parametri_master WHERE id=?", (row_id,))
            deleted += 1
            print(f"  DELETE duplicate {param} (kept {norm}): [{desc}]")

    print(f"  -> renamed: {renamed}, deleted (duplicates): {deleted}")

conn.commit()

# Final counts
print("\nFinal counts:")
for fam in ('ACS580', 'ACS880'):
    cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie=?", (fam,))
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie=? AND explicatie IS NOT NULL AND explicatie!=''", (fam,))
    cu_expl = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie=? AND parametru LIKE '0%' AND parametru NOT LIKE '0x%'", (fam,))
    still_lz = cur.fetchone()[0]
    print(f"  {fam}: total={total}, explicatie={cu_expl}, leading-zero remaining={still_lz}")

conn.close()
print("Done.")

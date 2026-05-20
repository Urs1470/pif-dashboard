"""Find remaining obviously truncated descriere_scurta in ACS880."""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# Find names where last word is very short and looks like a fragment
# (< 4 chars but not a known abbreviation like 'of', 'in', 'DC', 'AC', 'PID')
# Also find names where last word was previously hyphenated (common fragments)
KNOWN_FRAGMENTS = re.compile(
    r'\b(cur|fre|nom|pow|vol|spe|acc|dec|des|der|fil|ind|cap|sat|est|ref|sel|con|func|per|selec|refer|deriva|temper|potent)\s*$',
    re.IGNORECASE
)

cur.execute("SELECT parametru, descriere_scurta FROM parametri_master WHERE familie='ACS880' ORDER BY parametru")
rows = cur.fetchall()

truncated = [(p, ds) for p, ds in rows if ds and KNOWN_FRAGMENTS.search(ds)]
print(f"ACS880 likely truncated descriere_scurta: {len(truncated)}")
for p, ds in truncated[:30]:
    print(f"  {p:<8} [{ds}]")

# Also valoare_default_str check
cur.execute("""
    SELECT COUNT(*) FROM parametri_master
    WHERE valoare_default_str LIKE '%-' AND LENGTH(valoare_default_str) > 1
""")
print(f"\nAll families valoare_default_str still truncated: {cur.fetchone()[0]}")

conn.close()

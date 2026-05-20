import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# Count current issues
cur.execute("SELECT COUNT(*) FROM parametri_master WHERE familie='ACS880' AND descriere_scurta LIKE '%-'")
print("descriere_scurta ending with -:", cur.fetchone()[0])

cur.execute("SELECT id, parametru, descriere_scurta FROM parametri_master WHERE familie='ACS880' AND descriere_scurta LIKE '%-' LIMIT 10")
print("\nSample truncated descriere_scurta:")
for row in cur.fetchall():
    print(f"  {row[1]}: [{row[2]}]")

# Count descriere with word- word pattern
cur.execute("SELECT descriere FROM parametri_master WHERE familie='ACS880' AND descriere IS NOT NULL AND descriere != ''")
rows = cur.fetchall()
count_hyph = sum(1 for r in rows if re.search(r'\w+- +[a-z]', r[0]))
print(f"\ndescriere with 'word- word' hyphenation: {count_hyph}")

# Sample
cur.execute("SELECT parametru, descriere FROM parametri_master WHERE familie='ACS880' AND descriere IS NOT NULL AND descriere != '' LIMIT 2000")
rows = cur.fetchall()
bad = [(p, d) for p, d in rows if re.search(r'\w+- +[a-z]', d)][:5]
print("\nSample bad descriere:")
for p, d in bad:
    matches = re.findall(r'\w+- +[a-z]\w*', d)
    print(f"  {p}: {matches[:3]}")

conn.close()

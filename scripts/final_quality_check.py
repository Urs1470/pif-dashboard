"""Final quality check across all 8 families."""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

CATEGORII = {"Motor", "Limite", "Rampe", "I/O", "Comunicatii", "Protectii", "Diagnostic", "Altul"}
DIACRITICS = re.compile(r'[âăîțșÂĂÎȚȘ]')
HTML_TAG   = re.compile(r'<[^>]+>')
HYPH_DESC  = re.compile(r'\w+- +[a-z]')

print("=== COVERAGE EXPLICATIE ===")
cur.execute("""
    SELECT familie, COUNT(*) total,
           SUM(CASE WHEN explicatie IS NOT NULL AND explicatie!='' THEN 1 ELSE 0 END) cu
    FROM parametri_master GROUP BY familie ORDER BY familie
""")
for fam, tot, cu in cur.fetchall():
    cu = cu or 0
    pct = cu * 100 // tot if tot else 0
    flag = "" if pct == 100 else " <<<< INCOMPLETE"
    print(f"  {fam:<30} {cu}/{tot} ({pct}%){flag}")

print("\n=== QUALITY ISSUES PER FAMILY ===")
cur.execute("SELECT id, familie, parametru, explicatie, categorie, descriere, descriere_scurta FROM parametri_master")
rows = cur.fetchall()

fam_stats = {}
for row_id, fam, param, expl, categ, desc, desc_scurta in rows:
    s = fam_stats.setdefault(fam, {
        'html': 0, 'diacritics': 0, 'bad_categ': 0, 'desc_hyph': 0, 'desc_scurta_hyph': 0
    })
    if expl:
        if HTML_TAG.search(expl): s['html'] += 1
        if DIACRITICS.search(expl): s['diacritics'] += 1
    if categ and categ not in CATEGORII:
        s['bad_categ'] += 1
    if desc and HYPH_DESC.search(desc):
        s['desc_hyph'] += 1
    if desc_scurta and desc_scurta.endswith('-'):
        s['desc_scurta_hyph'] += 1

for fam, s in sorted(fam_stats.items()):
    issues = [f"{k}={v}" for k, v in s.items() if v > 0]
    print(f"  {fam:<30} {', '.join(issues) if issues else 'OK'}")

print("\n=== TOTAL PARAMS ===")
cur.execute("SELECT COUNT(*) FROM parametri_master")
print(f"  Total: {cur.fetchone()[0]}")

conn.close()

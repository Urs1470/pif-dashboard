"""
Fix PDF hyphenation artifacts in descriere and descriere_scurta for ALL families.
Also strips HTML from explicatie where found.
"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

HYPH_PATTERN  = re.compile(r'(\w+)-\s+([a-z]\w*)')
HTML_TAG      = re.compile(r'<[^>]+>')
EMOJI_PATTERN = re.compile(r'[\U0001F300-\U0001FFFF⚠✅❌✔✖]')

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# 1) Fix descriere hyphenation for ALL families
cur.execute("SELECT id, descriere FROM parametri_master WHERE descriere IS NOT NULL AND descriere != ''")
rows = cur.fetchall()
fixed_desc = 0
for param_id, descriere in rows:
    new_desc = HYPH_PATTERN.sub(r'\1\2', descriere)
    if new_desc != descriere:
        cur.execute("UPDATE parametri_master SET descriere=? WHERE id=?", (new_desc, param_id))
        fixed_desc += 1
print(f"Fixed descriere hyphenation: {fixed_desc} params")

# 2) Fix descriere_scurta trailing '-' for ALL families
cur.execute("SELECT id, descriere_scurta FROM parametri_master WHERE descriere_scurta LIKE '%-'")
rows = cur.fetchall()
fixed_scurta = 0
for param_id, desc_scurta in rows:
    new_name = desc_scurta.rstrip('-').rstrip()
    if new_name != desc_scurta:
        cur.execute("UPDATE parametri_master SET descriere_scurta=? WHERE id=?", (new_name, param_id))
        fixed_scurta += 1
print(f"Fixed descriere_scurta trailing '-': {fixed_scurta} params")

# 3) Strip HTML from explicatie for ALL families
cur.execute("SELECT id, familie, parametru, explicatie FROM parametri_master WHERE explicatie IS NOT NULL AND explicatie != ''")
rows = cur.fetchall()
fixed_html = 0
for param_id, fam, param, expl in rows:
    if HTML_TAG.search(expl):
        # Strip HTML tags
        clean = HTML_TAG.sub(' ', expl)
        clean = EMOJI_PATTERN.sub('', clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        cur.execute("UPDATE parametri_master SET explicatie=? WHERE id=?", (clean, param_id))
        fixed_html += 1
        print(f"  HTML stripped: {fam} {param}: [{expl[:80]}]")
print(f"Fixed explicatie HTML: {fixed_html} params")

conn.commit()
conn.close()
print("\nDone.")

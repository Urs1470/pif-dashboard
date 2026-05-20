"""Fix PDF hyphenation artifacts in ACS880 descriere field.

Joins split words like 'intern- ally' -> 'internally', 'para- meter' -> 'parameter'.
Pattern: word_chars + '- ' + lowercase_letter + word_chars

Does NOT touch: intentional hyphens (e.g., '0-10V', 'read-only', 'ACS880-xx')
which are either mid-word without space or followed by digits/uppercase.
"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

PATTERN = re.compile(r'(\w+)-\s+([a-z]\w*)')

def fix_hyph(text):
    if not text:
        return text
    return PATTERN.sub(r'\1\2', text)

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

cur.execute(
    "SELECT id, parametru, descriere FROM parametri_master "
    "WHERE familie='ACS880' AND descriere IS NOT NULL AND descriere != ''"
)
rows = cur.fetchall()

fixed = 0
for param_id, parametru, descriere in rows:
    new_desc = fix_hyph(descriere)
    if new_desc != descriere:
        cur.execute("UPDATE parametri_master SET descriere=? WHERE id=?", (new_desc, param_id))
        fixed += 1

conn.commit()
conn.close()
print(f"Fixed descriere hyphenation for {fixed} ACS880 params.")

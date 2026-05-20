"""
Complete truncated ACS880 descriere_scurta using known ABB naming conventions.
Only applies high-confidence suffix completions.
"""
import sqlite3, re, sys
sys.stdout.reconfigure(encoding='utf-8')

# Suffix → completion mapping (ABB ACS880 naming conventions)
# Only unambiguous suffixes
SUFFIX_MAP = {
    'cur':    'current',
    'fre':    'frequency',
    'selec':  'selection',
    'func':   'function',
    'refer':  'reference',
    'ref':    'reference',
    'deriva': 'derivative',
    'potent': 'potentiometer',
    'temper': 'temperature',
    'con':    'control',
    'ind':    'inductance',
    'cap':    'capacitance',
    'est':    'estimation',
    'per':    'performed',
    'vol':    'voltage',
    'pow':    'power',
}

# Regex: last word is a known fragment
FRAG_RE = re.compile(
    r'^(.*?)\b(' + '|'.join(re.escape(k) for k in SUFFIX_MAP) + r')$',
    re.IGNORECASE
)

def complete_name(name):
    m = FRAG_RE.match(name.strip())
    if m:
        prefix = m.group(1)
        frag = m.group(2).lower()
        completion = SUFFIX_MAP[frag]
        # Keep original capitalisation of fragment
        if m.group(2)[0].isupper():
            completion = completion.capitalize()
        return prefix + completion
    return name

conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

cur.execute("""
    SELECT id, parametru, descriere_scurta
    FROM parametri_master
    WHERE familie='ACS880'
      AND descriere_scurta IS NOT NULL AND descriere_scurta != ''
    ORDER BY parametru
""")
rows = cur.fetchall()

fixed = 0
for param_id, parametru, name in rows:
    new_name = complete_name(name)
    if new_name != name:
        cur.execute("UPDATE parametri_master SET descriere_scurta=? WHERE id=?", (new_name, param_id))
        fixed += 1
        print(f"  {parametru:<10} [{name}] -> [{new_name}]")

conn.commit()
conn.close()
print(f"\nFixed: {fixed} ACS880 param names")

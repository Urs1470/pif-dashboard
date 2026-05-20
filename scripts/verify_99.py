import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()
cur.execute("""
    SELECT parametru, descriere_scurta, valoare_default_str
    FROM parametri_master
    WHERE familie='ACS880' AND parametru LIKE '99.%'
    ORDER BY CAST(SUBSTR(parametru, 4) AS REAL)
""")
for p, ds, vd in cur.fetchall():
    print(f"  {p:<8} [{ds}] | default=[{vd}]")
conn.close()

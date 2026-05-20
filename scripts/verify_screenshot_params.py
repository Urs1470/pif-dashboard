import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()

# Check the exact params from the screenshot
params_to_check = ['99.3', '99.4', '99.6', '99.7', '99.8', '99.9']
cur.execute("""
    SELECT parametru, descriere_scurta, valoare_default_str
    FROM parametri_master
    WHERE familie='ACS880' AND parametru IN ('99.3','99.4','99.6','99.7','99.8','99.9')
    ORDER BY CAST(SUBSTR(parametru, 4) AS REAL)
""")
print("ACS880 group 99 (from screenshot):")
for p, ds, vd in cur.fetchall():
    print(f"  {p:<8} name=[{ds}]  default=[{vd}]")

conn.close()

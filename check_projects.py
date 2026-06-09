import sqlite3

conn = sqlite3.connect('pif_dashboard.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT id, nume, client, status, created_at FROM proiecte ORDER BY created_at DESC').fetchall()
print(f'Total proiecte in DB: {len(rows)}')
for r in rows:
    status = r['status'] or '?'
    nume = (r['nume'] or '')[:50]
    client = (r['client'] or '')[:30]
    print(f'  {status:12} | {nume:50} | {client}')
conn.close()

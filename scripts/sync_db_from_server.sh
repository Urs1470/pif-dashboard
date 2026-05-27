#!/usr/bin/env bash
# Sincronizeaza DB-ul local Windows cu cel de pe server (dupa ce Hermes a rulat enrichment).
# Foloseste /api/admin/db-dump (hot backup SQLite, safe vs scrieri concurente).
#
# Usage:  bash scripts/sync_db_from_server.sh
set -euo pipefail

cd "$(dirname "$0")/.."

SERVER="${PIF_SERVER:-https://pif.iupif.org}"
PIN="${PIF_DASHBOARD_PIN:?PIF_DASHBOARD_PIN env var is required}"
COOKIES="$(mktemp)"
TS="$(date +%Y%m%d_%H%M%S)"

echo "1/4 Login..."
curl -s -c "$COOKIES" -X POST "$SERVER/login" \
  -H "Content-Type: application/json" -d "{\"pin\":\"$PIN\"}" | grep -q '"success":true' \
  && echo "    OK" || { echo "    LOGIN ESUAT"; exit 1; }

echo "2/4 Backup DB local -> pif_dashboard.db.before-sync-$TS"
cp pif_dashboard.db "pif_dashboard.db.before-sync-$TS"

echo "3/4 Download DB de pe server..."
curl -s -b "$COOKIES" "$SERVER/api/admin/db-dump" --max-time 300 -o pif_dashboard.db.fromserver

# Validare: header SQLite
if [ "$(head -c 15 pif_dashboard.db.fromserver)" != "SQLite format 3" ]; then
  echo "    FISIER INVALID (nu e SQLite). Anulat."
  rm -f pif_dashboard.db.fromserver
  exit 1
fi

echo "4/4 Inlocuire DB local"
mv pif_dashboard.db.fromserver pif_dashboard.db
rm -f "$COOKIES"

echo ""
echo "GATA. DB local sincronizat cu serverul."
python - <<'EOF'
import sqlite3
conn = sqlite3.connect('pif_dashboard.db')
cur = conn.cursor()
cur.execute("SELECT familie, COUNT(*), SUM(CASE WHEN explicatie IS NOT NULL AND explicatie!='' THEN 1 ELSE 0 END) FROM parametri_master GROUP BY familie ORDER BY familie")
for fam, tot, cu in cur.fetchall():
    cu = cu or 0
    print(f"  {fam:<25} {cu}/{tot}  ({cu*100//tot if tot else 0}%)")
conn.close()
EOF

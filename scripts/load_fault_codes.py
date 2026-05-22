#!/usr/bin/env python3
"""Load parsed fault-code JSON files into the fault_codes table.

Reads scripts/fault_codes_<familie>.json (produced by the parse_faults_*.py
scripts) and inserts the rows into the DB. Idempotent per familie: existing
rows for a (producator, familie) pair are deleted before re-insert, so the
script is safe to re-run after re-parsing one manual.

Touches ONLY the fault_codes table.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / 'pif_dashboard.db'
DATA_DIR = ROOT / 'data' / 'fault_codes'

COLS = ['producator', 'familie', 'cod', 'cod_secundar', 'tip', 'nume',
        'cauza', 'remediu', 'reactie', 'confirmare', 'extra_json', 'pagina', 'sursa']


def main():
    files = sorted(DATA_DIR.glob('fault_codes_*.json'))
    if not files:
        print('No fault_codes_*.json files found.')
        return

    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    total = 0
    for f in files:
        data = json.load(open(f, encoding='utf-8'))
        if not data:
            print(f'{f.name:42s} (empty, skipped)')
            continue
        producator = data[0]['producator']
        familie = data[0]['familie']
        cur.execute('DELETE FROM fault_codes WHERE producator = ? AND familie = ?',
                    (producator, familie))
        rows = []
        for d in data:
            extra = d.get('extra')
            extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
            rows.append((
                d['producator'], d['familie'], d['cod'],
                d.get('cod_secundar'), d.get('tip'), d.get('nume'),
                d.get('cauza'), d.get('remediu'), d.get('reactie'),
                d.get('confirmare'), extra_json, d.get('pagina'), d.get('sursa'),
            ))
        cur.executemany(
            f"INSERT INTO fault_codes ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})",
            rows)
        total += len(rows)
        print(f'{familie:24s} {len(rows):5d} rows  <- {f.name}')

    conn.commit()
    n = cur.execute('SELECT COUNT(*) FROM fault_codes').fetchone()[0]
    conn.close()
    print('-' * 50)
    print(f'Loaded {total} rows; fault_codes table now has {n} rows.')


if __name__ == '__main__':
    main()

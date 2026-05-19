"""Apply LLM-generated explicații from a JSON file to parametri_master.

Input format (matches scripts/sample_explicatii.json):
[
  {
    "id": 15333,
    "familie": "ACS580",
    "parametru": "26.08",
    "GENERATED": {
      "explicatie": "...",
      "influenteaza": "30.19, 99.12",
      "categorie": "Limite"
    }
  },
  ...
]

Updates only `explicatie`, `influenteaza`, `categorie` — never touches
PDF-derived fields (descriere, acces, tip_date, default, min/max, unitate, pagina).
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / 'pif_dashboard.db'


def apply(input_path: Path, db_path: Path, dry_run: bool):
    data = json.loads(input_path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        sys.exit("Input must be a JSON array")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    written = skipped_no_id = skipped_no_gen = errors = 0
    for rec in data:
        param_id = rec.get('id')
        gen = rec.get('GENERATED') or {}
        if not param_id:
            skipped_no_id += 1
            continue
        if not gen.get('explicatie'):
            skipped_no_gen += 1
            continue
        try:
            if dry_run:
                print(f"  [dry] id={param_id} {rec.get('parametru')}: "
                      f"explicatie={gen['explicatie'][:60]}...")
            else:
                cur.execute(
                    'UPDATE parametri_master SET '
                    '  explicatie = ?, '
                    '  influenteaza = ?, '
                    '  categorie = COALESCE(NULLIF(?, ""), categorie) '
                    'WHERE id = ?',
                    (gen.get('explicatie') or '',
                     gen.get('influenteaza') or '',
                     gen.get('categorie') or '',
                     param_id)
                )
            written += 1
        except Exception as e:
            errors += 1
            print(f"  ERROR id={param_id}: {e}")

    if not dry_run:
        conn.commit()
    conn.close()

    print(f"\nResult: written={written}, no_id={skipped_no_id}, "
          f"no_gen={skipped_no_gen}, errors={errors}")
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input', help='Input JSON file with LLM-generated explicații')
    ap.add_argument('--db', default=str(DEFAULT_DB), help='SQLite DB path')
    ap.add_argument('--dry-run', action='store_true', help='Preview without writing')
    args = ap.parse_args()
    n = apply(Path(args.input), Path(args.db), args.dry_run)
    if n == 0:
        sys.exit(1)


if __name__ == '__main__':
    main()

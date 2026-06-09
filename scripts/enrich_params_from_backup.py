#!/usr/bin/env python3
"""Enrich parametri_master from ABB .dcparamsbak backup files.

Reads ALL parameters (including signals and defaults) from a drive backup,
compares with the existing parametri_master DB entries for the specified
family, and reports/applies differences.

Usage:
    python scripts/enrich_params_from_backup.py path/to/file.dcparamsbak [--apply] [--family ACS880]

Options:
    --apply     Actually INSERT/UPDATE the database (default: dry-run report only)
    --family    Target family in parametri_master (default: auto-detect from backup)

Reports:
    - New parameters missing from DB
    - Parameters with missing unit/default that can be filled
    - Parameters with different defaults (informational, not auto-overwritten)
    - Enum labels available for storage
"""

import argparse
import json
import os
import sqlite3
import sys

# Allow running from project root or scripts/ directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from scripts.parse_params.abb import parse_full, read_drive_info

DATABASE_PATH = os.path.join(PROJECT_ROOT, 'pif_dashboard.db')


def _detect_family(info: dict) -> str:
    """Detect parametri_master family from drive info."""
    family = info.get('Family', '')
    model = info.get('DriveModel', '')
    if '880' in family or '880' in model:
        return 'ACS880'
    if '580' in family or '580' in model:
        return 'ACS580'
    # Default to ACS880 for unknown ABB
    return 'ACS880'


def _load_db_params(familie: str) -> dict:
    """Load existing parametri_master entries for a family.

    Returns {parametru: {descriere_scurta, unitate, valoare_default, min, max, enum_labels}}
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT parametru, descriere_scurta, unitate, valoare_default,
               valoare_default_str, min, max, enum_labels
        FROM parametri_master WHERE familie = ?
    ''', (familie,))
    result = {}
    for row in cursor.fetchall():
        result[row['parametru']] = {
            'descriere_scurta': row['descriere_scurta'] or '',
            'unitate': row['unitate'] or '',
            'valoare_default': row['valoare_default'],
            'valoare_default_str': row['valoare_default_str'] or '',
            'min': row['min'],
            'max': row['max'],
            'enum_labels': row['enum_labels'] or '',
        }
    conn.close()
    return result


def _generate_id():
    """Generate a UUID for new parametri_master rows."""
    import uuid
    return str(uuid.uuid4())


def enrich(backup_path: str, familie: str = '', apply: bool = False):
    """Main enrichment logic."""
    # Read backup
    with open(backup_path, 'rb') as f:
        raw = f.read()

    info = read_drive_info(raw)
    if not familie:
        familie = _detect_family(info)

    print(f"Drive info: {json.dumps(info, indent=2)}")
    print(f"Target family: {familie}")
    print()

    # Parse all params (including signals and at-default)
    all_params = parse_full(raw, backup_path)
    print(f"Total parameters in backup: {len(all_params)}")
    signals = [p for p in all_params if p['is_signal']]
    config = [p for p in all_params if not p['is_signal']]
    print(f"  Signals (read-only): {len(signals)}")
    print(f"  Config parameters: {len(config)}")
    print()

    # Load existing DB
    db_params = _load_db_params(familie)
    print(f"Existing in parametri_master ({familie}): {len(db_params)}")
    print()

    # Compare
    new_params = []
    fill_unit = []
    fill_default = []
    fill_min_max = []
    different_default = []
    enum_available = []

    for p in all_params:
        code = p['db_id']
        db = db_params.get(code)

        if p.get('value_names'):
            enum_available.append(p)

        if db is None:
            new_params.append(p)
            continue

        # Check fillable fields
        if not db['unitate'] and p['unit']:
            fill_unit.append((code, p['unit']))

        # Default comparison
        backup_default = p['default_value']
        db_default = str(db['valoare_default']) if db['valoare_default'] is not None else db['valoare_default_str']
        if backup_default and db_default:
            try:
                if abs(float(backup_default) - float(db_default)) > 1e-6:
                    different_default.append((code, db_default, backup_default))
            except (ValueError, TypeError):
                if backup_default != db_default:
                    different_default.append((code, db_default, backup_default))
        elif backup_default and not db_default:
            fill_default.append((code, backup_default))

        # Min/Max
        if (db['min'] is None or str(db['min']).strip() == '') and p['min']:
            fill_min_max.append((code, 'min', p['min']))
        if (db['max'] is None or str(db['max']).strip() == '') and p['max']:
            fill_min_max.append((code, 'max', p['max']))

    # Enum labels that can be stored (for params that exist in DB)
    enum_for_existing = [p for p in enum_available if p['db_id'] in db_params]
    enum_missing_in_db = [p for p in enum_for_existing
                          if not db_params[p['db_id']].get('enum_labels')]

    # Report
    print("=" * 60)
    print("ENRICHMENT REPORT")
    print("=" * 60)
    print()

    print(f"New parameters missing from DB: {len(new_params)}")
    if new_params:
        for p in new_params[:20]:
            sig = " [signal]" if p['is_signal'] else ""
            print(f"  {p['db_id']:>8} | {p['name'][:50]:<50} | {p['unit'] or '-':<10}{sig}")
        if len(new_params) > 20:
            print(f"  ... and {len(new_params) - 20} more")
    print()

    print(f"Parameters with missing unit (fillable): {len(fill_unit)}")
    if fill_unit:
        for code, unit in fill_unit[:10]:
            print(f"  {code:>8} -> unit: {unit}")
        if len(fill_unit) > 10:
            print(f"  ... and {len(fill_unit) - 10} more")
    print()

    print(f"Parameters with missing default (fillable): {len(fill_default)}")
    if fill_default:
        for code, default in fill_default[:10]:
            print(f"  {code:>8} -> default: {default}")
        if len(fill_default) > 10:
            print(f"  ... and {len(fill_default) - 10} more")
    print()

    print(f"Parameters with missing min/max (fillable): {len(fill_min_max)}")
    if fill_min_max:
        for code, field, val in fill_min_max[:10]:
            print(f"  {code:>8} -> {field}: {val}")
        if len(fill_min_max) > 10:
            print(f"  ... and {len(fill_min_max) - 10} more")
    print()

    print(f"Parameters with different default (informational): {len(different_default)}")
    if different_default:
        for code, db_val, bak_val in different_default[:10]:
            print(f"  {code:>8} | DB: {db_val:<20} | Backup: {bak_val}")
        if len(different_default) > 10:
            print(f"  ... and {len(different_default) - 10} more")
    print()

    print(f"Enum labels available: {len(enum_available)} total, {len(enum_missing_in_db)} not yet in DB")
    print()

    if not apply:
        print("DRY RUN — no changes made. Use --apply to write to DB.")
        return

    # Apply changes
    print("APPLYING changes...")
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 1. INSERT new parameters
    inserted = 0
    for p in new_params:
        if p['is_signal']:
            continue  # Skip signals — they're not configurable
        try:
            cursor.execute('''
                INSERT INTO parametri_master (id, familie, parametru, descriere_scurta,
                    unitate, valoare_default, min, max, enum_labels, creat_la)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ''', (
                _generate_id(),
                familie,
                p['db_id'],
                p['name'],
                p['unit'] or None,
                p['default_value'] or None,
                p['min'] or None,
                p['max'] or None,
                json.dumps(p['value_names']) if p.get('value_names') else None,
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # Duplicate — skip
    print(f"  Inserted {inserted} new parameters")

    # 2. UPDATE missing units
    for code, unit in fill_unit:
        cursor.execute(
            'UPDATE parametri_master SET unitate = ? WHERE familie = ? AND parametru = ? AND (unitate IS NULL OR unitate = "")',
            (unit, familie, code)
        )
    print(f"  Updated {len(fill_unit)} units")

    # 3. UPDATE missing defaults
    for code, default in fill_default:
        cursor.execute(
            'UPDATE parametri_master SET valoare_default = ? WHERE familie = ? AND parametru = ? AND valoare_default IS NULL',
            (default, familie, code)
        )
    print(f"  Updated {len(fill_default)} defaults")

    # 4. UPDATE missing min/max
    for code, field, val in fill_min_max:
        cursor.execute(
            f'UPDATE parametri_master SET {field} = ? WHERE familie = ? AND parametru = ? AND ({field} IS NULL OR {field} = "")',
            (val, familie, code)
        )
    print(f"  Updated {len(fill_min_max)} min/max values")

    # 5. Store enum labels
    stored_enums = 0
    for p in enum_missing_in_db:
        if p.get('value_names'):
            cursor.execute(
                'UPDATE parametri_master SET enum_labels = ? WHERE familie = ? AND parametru = ? AND (enum_labels IS NULL OR enum_labels = "")',
                (json.dumps(p['value_names']), familie, p['db_id'])
            )
            stored_enums += 1
    print(f"  Stored {stored_enums} enum labels")

    conn.commit()
    conn.close()
    print()
    print("Done! Changes committed to database.")


def main():
    parser = argparse.ArgumentParser(
        description='Enrich parametri_master from ABB .dcparamsbak backup files'
    )
    parser.add_argument('backup', help='Path to .dcparamsbak file')
    parser.add_argument('--apply', action='store_true',
                        help='Apply changes to DB (default: dry-run)')
    parser.add_argument('--family', default='',
                        help='Target family (default: auto-detect)')
    args = parser.parse_args()

    if not os.path.exists(args.backup):
        print(f"Error: file not found: {args.backup}")
        sys.exit(1)

    enrich(args.backup, args.family, args.apply)


if __name__ == '__main__':
    main()

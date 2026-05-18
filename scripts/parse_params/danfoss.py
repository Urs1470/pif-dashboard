"""Parser pentru export "Changed parameters" din MCT 10 Set-up Software (Danfoss).

Input: text plain tab-separated, structura:

    Drive Name: ...
    Drive Address: ...
    Field-bus: ...

    The following parameters have been changed from default values:

    ID	Name	Setup	Current value	Default value

    010	Active Set-up	Setup 1	Multi Set-up	Set-up 1
    ...

ID extern Danfoss este format "flat": ultimele 2 cifre = parametru, restul = grupa.
DB intern: "grupa-parametru" cu suffix optional ".N" pentru sub-index.

Exemple transformari:
    010    -> 0-10
    124    -> 1-24
    540.0  -> 5-40.0
    916.2  -> 9-16.2
    1415   -> 14-15
    3090   -> 30-90
"""
from __future__ import annotations

import re
from typing import Dict, List


def danfoss_id_to_db(raw_id: str) -> str:
    """Transforma ID Danfoss flat in format DB grupa-parametru[.subindex]."""
    raw_id = raw_id.strip()
    parts = raw_id.split('.')
    main = parts[0]
    suffix = '.' + parts[1] if len(parts) > 1 else ''
    if len(main) < 3:
        # ex: '99' -> '0-99' (improbabil dar safety)
        return f"0-{main.zfill(2)}{suffix}"
    param = main[-2:]
    grupa = str(int(main[:-2]))
    return f"{grupa}-{param}{suffix}"


_HEADER_LINE_RE = re.compile(r'^\s*ID\s+Name', re.IGNORECASE)
_DATA_LINE_RE = re.compile(r'^\s*\d+(?:\.\d+)?\s')


def _split_fields(line: str) -> List[str]:
    """Tab-separated cu padding -> lista fields strip-uite, fara empty."""
    return [f.strip() for f in line.split('\t') if f.strip()]


def _is_data_line(line: str) -> bool:
    return bool(_DATA_LINE_RE.match(line))


def parse(content: str) -> List[Dict]:
    """Parseaza continutul si returneaza lista de parametri unificati.

    Returneaza:
        [
          {
            'db_id': '0-10',
            'raw_id': '010',
            'name': 'Active Set-up',
            'value': 'Multi Set-up',     # daca valorile sunt uniforme pe toate Setup-urile
            'default': 'Set-up 1',
            'setups': [1, 2, 3, 4],
            'conflict': False,
            'per_setup': {1: 'Multi Set-up', ...}  # populat doar daca conflict
          },
          ...
        ]
    Ordonat dupa db_id (grupa, parametru, subindex).
    """
    # Grupeaza intrari brute dupa db_id
    grouped: Dict[str, Dict] = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line:
            continue
        if _HEADER_LINE_RE.match(line):
            continue
        if not _is_data_line(line):
            continue

        fields = _split_fields(line)
        if len(fields) < 5:
            # Linie malformata - skip silentios
            continue

        raw_id, name, setup_label, current, default = fields[0], fields[1], fields[2], fields[3], fields[4]

        # Nume truncat in export (terminate cu '...') - lasam asa, UI poate completa din parametri_master
        # Setup label format "Setup N"
        setup_match = re.search(r'Setup\s*(\d+)', setup_label, re.IGNORECASE)
        setup_num = int(setup_match.group(1)) if setup_match else 1

        db_id = danfoss_id_to_db(raw_id)

        entry = grouped.setdefault(db_id, {
            'db_id': db_id,
            'raw_id': raw_id,
            'name': name,
            'default': default,
            'per_setup': {},
        })
        entry['per_setup'][setup_num] = current
        # Pastreaza numele cel mai lung (cel netruncat daca exista)
        if len(name) > len(entry['name']):
            entry['name'] = name
        # Pastreaza default-ul cel mai lung
        if len(default) > len(entry['default']):
            entry['default'] = default

    # Construieste rezultate finale cu detectie conflict
    result = []
    for db_id, entry in grouped.items():
        per_setup = entry['per_setup']
        setups = sorted(per_setup.keys())
        unique_values = set(per_setup.values())
        conflict = len(unique_values) > 1

        if conflict:
            # Preferinta default: Setup 1 daca exista, altfel cel mai mic
            value = per_setup.get(1) or per_setup[setups[0]]
        else:
            value = next(iter(unique_values))

        result.append({
            'db_id': db_id,
            'raw_id': entry['raw_id'],
            'name': entry['name'],
            'value': value,
            'default': entry['default'],
            'setups': setups,
            'conflict': conflict,
            'per_setup': {str(k): v for k, v in per_setup.items()} if conflict else {},
        })

    # Sortare: grupa numerica, parametru numeric, subindex numeric
    def sort_key(p):
        s = p['db_id']
        try:
            main, sub = (s.split('.') + ['0'])[:2]
            grupa, param = main.split('-')
            return (int(grupa), int(param), int(sub))
        except Exception:
            return (999, 999, 999)

    result.sort(key=sort_key)
    return result


if __name__ == '__main__':
    import sys
    import json
    path = sys.argv[1] if len(sys.argv) > 1 else r'D:\Downloads\Changed parameters danfoss.txt'
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    parsed = parse(content)
    print(f"Total params: {len(parsed)}")
    conflicts = [p for p in parsed if p['conflict']]
    print(f"Conflicts (valori diferite per Setup): {len(conflicts)}")
    print()
    print(json.dumps(parsed[:10], indent=2, ensure_ascii=False))
    if conflicts:
        print("\n--- Conflicte ---")
        print(json.dumps(conflicts, indent=2, ensure_ascii=False))

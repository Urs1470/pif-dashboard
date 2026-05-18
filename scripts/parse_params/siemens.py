"""Parser pentru export PDF Siemens Starter (SINAMICS G120/G130/G150/S120/S150).

Format text extras (linii tipice):
    1 p10 Drive [0] Ready [1] Quick commissioning
    5 p304[0] M Rated motor 400 0 Vrms voltage
    7 p307[0] M Rated motor 7.50 0.00 kW power
    19 p573 Inhibit [1] Yes [0] No automatic reference value calculation
    22 p969 System runtime relative 257468927 0 ms

Structura per linie:
    INDEX  CODE  [DATA_SET]  NAME...  CURRENT  FACTORY  [UNIT]  [NAME_CONTINUATION]

Coloana 'name' wrap-uieste pe linii suplimentare care NU incep cu un index.
Valorile pot fi numerice (400, 7.50, 27.00) sau enum-uri ([0] Ready, [1] Quick commissioning).

Format DB Siemens: 'pNNNN' (sau 'rNNNN' pentru read-only).
Skip implicit pentru r-params (monitorizare, nu se modifica manual).
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, List


_CODE_RE = re.compile(r'^(p|r)(\d+)(?:\[(\d+)\])?$', re.IGNORECASE)

# Linie cu parametru nou: incepe cu un index (numar mic), apoi codul p/r
_LINE_START_RE = re.compile(
    r'^\s*\d+\s+'                              # index list (1, 2, 3, ...)
    r'((?:p|r)\d+(?:\[\d+\])?)\s+'             # code (group 1)
    r'(?:([A-Z])\s+)?'                          # optional data set letter (group 2)
    r'(.+)$',                                   # rest (group 3)
    re.IGNORECASE
)

# Token de valoare: enum '[N] Text' sau numar +/- decimal cu unit optional
_VALUE_TOKEN_RE = re.compile(
    r'\[-?\d+\][^[\d]*(?=\s|$|\[)'              # enum: [N] urmat de text pana la urmatorul [ sau spatiu+ceva
    r'|[+-]?\d[\d.,]*'                          # numar
)


def _normalize_id(raw: str) -> str:
    """'p304[0]' -> 'p304', 'p304[1]' -> 'p304[1]', 'r41' -> 'r41'."""
    m = _CODE_RE.match(raw.strip())
    if not m:
        return raw.strip()
    prefix, num, idx = m.groups()
    prefix = prefix.lower()
    if idx is None or idx == '0':
        return f"{prefix}{num}"
    return f"{prefix}{num}[{idx}]"


def _parse_rest(rest: str):
    """Extrage (name, current, factory, unit) din partea de dupa cod si ds.

    Strategie: gaseste primele 2 token-uri care arata ca valori.
    Prima valoare = current, a doua = factory. Inainte de prima = name.
    Dupa a doua, restul (pana la sfarsit) = unit + posibila continuare nume.
    """
    rest = rest.strip()
    # Cauta toate valorile - poate fi enum [N] Text sau numar
    # Pentru enum, "[N] Text..." se intinde pana la urmatorul "[" sau pana la sfarsit
    # Pentru a fi precisi, cautam pozitiile valorilor numerice si enum
    val_positions = []  # lista (start, end, value_str)

    # Pas 1: gaseste toate numerele simple (nu cele din interiorul de [N])
    for m in re.finditer(r'(?<!\[)[+-]?\d[\d.,]*\b', rest):
        # Asigura-te ca nu e in interiorul unui [...] enum index
        val_positions.append((m.start(), m.end(), m.group(0)))

    # Pas 2: gaseste enum-urile - "[N] Text" pana la urmatorul "[N]" sau sfarsit
    enum_matches = list(re.finditer(r'\[-?\d+\][^[]*?(?=\s*\[-?\d+\]|\s*$)', rest))

    for m in enum_matches:
        # Adauga doar daca nu se overlap cu un numar deja gasit
        s, e = m.start(), m.end()
        if not any(vs <= s < ve for vs, ve, _ in val_positions):
            val_positions.append((s, e, m.group(0).strip()))

    val_positions.sort()

    if len(val_positions) < 1:
        return rest, '', '', ''

    if len(val_positions) == 1:
        # Doar o valoare gasita - probabil e current; name e tot inainte
        s, e, v = val_positions[0]
        name = rest[:s].rstrip()
        tail = rest[e:].strip()
        return name, v, '', tail

    # 2+ valori: primele 2 sunt current si factory
    first = val_positions[0]
    second = val_positions[1]
    name = rest[:first[0]].rstrip()
    current = first[2].strip()
    factory = second[2].strip()
    tail = rest[second[1]:].strip()  # poate contine unit + name continuation
    # Heuristic: primul token din tail = unit (daca nu pare propozitie)
    unit = ''
    rest_after = tail
    if tail:
        parts = tail.split(None, 1)
        first_token = parts[0]
        # Unit are de obicei putine litere/symbol-uri, fara spatii
        if len(first_token) <= 10 and re.match(r'^[A-Za-z%°Ωµ²³/]+s?$', first_token):
            unit = first_token
            rest_after = parts[1] if len(parts) > 1 else ''

    # Daca name e gol (rare), folosim rest_after (continuare name) ca name
    if not name:
        name = rest_after.strip()
        rest_after = ''
    else:
        # Atasam continuarea numelui la name daca exista (apare pe acelasi rand text)
        if rest_after:
            name = (name + ' ' + rest_after).strip()

    return name, current, factory, unit


def parse(content, filename: str = '', skip_readonly: bool = True) -> List[Dict]:
    """Parseaza PDF-ul Siemens Starter si returneaza lista params."""
    try:
        import pdfplumber
    except ImportError:
        return []

    if isinstance(content, (bytes, bytearray)):
        pdf_source = BytesIO(content)
    else:
        pdf_source = content

    # Extract text si construieste linii logice (combina wrap-urile name)
    logical_lines = []
    with pdfplumber.open(pdf_source) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for raw in text.splitlines():
                ln = raw.rstrip()
                if not ln.strip():
                    continue
                # Skip linii de header/footer evident
                if re.match(r'^\s*[A-Z]\s*$', ln):  # markers de col layout (A, B, C, D, E, F)
                    continue
                if re.match(r'^\s*(L\d+_\w+|SINAMICS|Parameter|Date|Editor|Checked|State|Standard|Page \d+|Pg\.|\d{1,3}_\d+_\d+|\d{1,2}/\d{1,2}/\d{4})', ln):
                    continue

                m = _LINE_START_RE.match(ln)
                if m:
                    logical_lines.append(['line', m.group(1), m.group(2) or '', m.group(3)])
                else:
                    # Continuare nume / valoare - ataseaza la ultima linie
                    if logical_lines:
                        logical_lines[-1][3] += ' ' + ln.strip()

    # Proceseaza fiecare parametru
    by_code = {}
    for _, code, ds, rest in logical_lines:
        db_id = _normalize_id(code)
        if db_id in by_code:
            continue
        if skip_readonly and db_id.startswith('r'):
            continue

        name, current, factory, unit = _parse_rest(rest)
        name = re.sub(r'\s+', ' ', name).strip()
        if unit:
            value = f"{current} {unit}".strip() if current else current
            default = f"{factory} {unit}".strip() if factory else factory
        else:
            value = current
            default = factory

        by_code[db_id] = {
            'db_id': db_id,
            'raw_id': code,
            'p_code': '',
            'name': name,
            'value': value.strip(),
            'default': default.strip(),
            'setups': [],
            'conflict': False,
            'per_setup': {},
        }

    result = list(by_code.values())

    def sort_key(p):
        m = _CODE_RE.match(p['raw_id'])
        if m:
            return (0 if m.group(1).lower() == 'p' else 1, int(m.group(2)), int(m.group(3) or '0'))
        return (2, 9999999, 0)

    result.sort(key=sort_key)
    return result


if __name__ == '__main__':
    import sys
    import json
    path = sys.argv[1] if len(sys.argv) > 1 else r'D:\Downloads\exemplu starter.pdf'
    with open(path, 'rb') as f:
        raw = f.read()
    parsed = parse(raw, filename=path)
    print(f"Total params (p-only): {len(parsed)}")
    parsed_all = parse(raw, filename=path, skip_readonly=False)
    print(f"Total params (toate):  {len(parsed_all)}")
    print()
    print(json.dumps(parsed[:20], indent=2, ensure_ascii=False))

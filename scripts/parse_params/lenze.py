"""Parser pentru export PDF Lenze EASY Starter (i550 / i950).

Format linie tipica in PDF:
    0x2540:001 P208:001 Mains settings: Rated mains voltage 400 Veff [1]
    0x2381:005 PROFINET settings: Station name xd51u1f7c2
    0x2942:004 Current controller par.: d-axis gain 26.00 V/A
    0x2860:001 P201:001 Frequency control: Default setpoint source Network [5]

Structura:
- Cod hex obligatoriu: 0xXXXX sau 0xXXXX:NNN
- Cod P optional: P NNN sau P NNN:NNN (parametru din menu/HMI)
- Denumire param (frecvent cu ":" separator pentru subdetaliu)
- Valoare la sfarsit, posibil cu unit (V, Hz, A, ms, %, ...) si optional [N] enum index

Filtrare implicita: skip parametri "system" pe care Ion nu-i editeaza manual:
    - PROFINET / WLAN / I&M settings (network)
    - Generic RPDO / TPDO mapping (fieldbus internals)
    - Inverter characteristic (caracteristica calibrare)
    - V/f / f grid points user characteristic (look-up tables generate)

Ion poate dezactiva filtrul cu skip_internals=False.
"""
from __future__ import annotations

import re
from io import BytesIO
from typing import Dict, List


# Regex linie data: cod hex + opt P code + restul
_LINE_RE = re.compile(
    r'^(0x[0-9A-Fa-f]+(?::\d{1,3})?)\s+'      # cod hex (group 1)
    r'(?:(P\d+(?::\d{1,3})?)\s+)?'             # optional P code (group 2)
    r'(.+)$'                                    # rest (group 3)
)

# Heuristic pentru extragere valoare la sfarsit. Order matters: incercam in ordine
# de specificitate, alegem cel mai NATURAL match (preferand patterns mai specifice).
# Acopera: "26.00 V/A", "400 Veff [1]", "Network [5]", "Not connected [0]",
#          "Digital input 1 [11]", "Quadratic [1]", "1500.000", "192.168.0.216", "xd51u1f7c2"
_VALUE_PATTERNS = [
    # enum text cu indice obligatoriu: cuvant cu majuscula + pana la 2 cuvinte + [N]
    re.compile(r'\s([A-Z][\w./+-]*(?:\s+[\w./+-]+){0,2}\s*\[-?\d+\])\s*$'),
    # IP-like (4 octeti)
    re.compile(r'\s(\d+(?:\.\d+){3})\s*$'),
    # numar cu unit + optional [N] (unit poate fi orice non-space non-bracket - acopera Ω, V/A, kg cm², etc)
    re.compile(r'\s([+-]?\d[\d.,]*(?:\s+[^\s\[\]]+)?(?:\s*\[-?\d+\])?)\s*$'),
    # token alfanumeric (SSID, name, hex string) - min 4 caractere
    re.compile(r'\s([A-Za-z0-9_-]{4,})\s*$'),
]

# Patternuri "internal" - skip cand skip_internals=True
_SKIP_NAME_PATTERNS = [
    re.compile(r'(?i)PROFINET settings'),
    re.compile(r'(?i)WLAN settings'),
    re.compile(r'(?i)Generic [RT]PDO mapping'),
    re.compile(r'(?i)Inverter characteristic'),
    re.compile(r'(?i)^(V|f) grid points'),
    re.compile(r'(?i)Field controller settings'),
    re.compile(r'(?i)Field weakening controller'),
    re.compile(r'(?i)Current controller par'),
    re.compile(r'(?i)Speed controller settings'),
    re.compile(r'(?i)Inertia settings'),
    re.compile(r'(?i)I&M\d'),
]


def _is_internal(name: str) -> bool:
    return any(p.search(name) for p in _SKIP_NAME_PATTERNS)


def _split_name_value(rest: str):
    """Separa numele de valoare din restul liniei.

    Returneaza (name, value). Daca nu poate separa, value='' si name=rest.
    Incearca fiecare pattern in ordine de prioritate, ia primul match.
    """
    rest = rest.strip()
    for pat in _VALUE_PATTERNS:
        m = pat.search(rest)
        if m:
            value = m.group(1).strip()
            name = rest[:m.start(1)].rstrip().rstrip(':').rstrip()
            if not name:
                return rest, ''
            return name, value
    return rest, ''


def parse(content, filename: str = '', skip_internals: bool = True) -> List[Dict]:
    """Parseaza PDF-ul Lenze si returneaza lista params.

    Args:
        content: bytes ai PDF-ului sau cale catre PDF
        filename: nume original (informativ)
        skip_internals: daca True, filtreaza parametrii system (default True)
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    # Accept bytes sau path
    if isinstance(content, (bytes, bytearray)):
        pdf_source = BytesIO(content)
    else:
        pdf_source = content

    # Acumulator pentru continuari multi-line (linie noua care nu incepe cu 0x = continuare valoare)
    lines = []
    with pdfplumber.open(pdf_source) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for raw in text.splitlines():
                ln = raw.rstrip()
                if not ln:
                    continue
                if ln.startswith('0x') or ln.lstrip().lower().startswith('0x'):
                    lines.append(ln.lstrip())
                else:
                    # Continuare la linia precedenta (valoare lunga, ex SSID multi-line)
                    if lines:
                        lines[-1] = lines[-1] + ' ' + ln.strip()

    result = []
    seen = set()
    for ln in lines:
        m = _LINE_RE.match(ln)
        if not m:
            continue
        hex_code = m.group(1)
        p_code = m.group(2)
        rest = m.group(3) or ''

        name, value = _split_name_value(rest)

        # Normalizare hex code (lowercase 0x, uppercase digits)
        hc = hex_code[2:].upper()
        if ':' in hc:
            head, sub = hc.split(':', 1)
            db_id = f'0x{head}:{sub.zfill(3)}'
        else:
            db_id = f'0x{hc}'

        if db_id in seen:
            continue
        seen.add(db_id)

        if skip_internals and _is_internal(name):
            continue

        result.append({
            'db_id': db_id,
            'raw_id': hex_code,
            'p_code': p_code or '',
            'name': name,
            'value': value,
            'default': '',
            'setups': [],
            'conflict': False,
            'per_setup': {},
        })

    # Sortare numerica dupa hex value + subindex
    def sort_key(p):
        s = p['db_id'][2:]  # strip '0x'
        head, _, sub = s.partition(':')
        try:
            return (int(head, 16), int(sub or '0'))
        except Exception:
            return (0xFFFFFF, 0)

    result.sort(key=sort_key)
    return result


if __name__ == '__main__':
    import sys
    import json
    path = sys.argv[1] if len(sys.argv) > 1 else r'D:\Downloads\exemplu lenze.pdf'
    with open(path, 'rb') as f:
        raw = f.read()
    parsed = parse(raw, filename=path)
    print(f"Total params (filtrat): {len(parsed)}")
    parsed_all = parse(raw, filename=path, skip_internals=False)
    print(f"Total params (toate):   {len(parsed_all)}")
    print()
    print(json.dumps(parsed[:15], indent=2, ensure_ascii=False))

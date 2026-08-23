"""Parser pentru arhive de proiect Siemens STARTER / SCOUT (SINAMICS).

Un proiect STARTER exportat (folder `.s7p` arhivat ZIP) conține fișierul
`Project.mcp` care — surprinzător — este o bază de date **SQLite**. În interior,
tabela `STG_CONTENTS2` ține un arbore OLE structured-storage cu, pentru fiecare
drive (Control Unit), stream-urile:

    varval  -> tabela de valori instanță  (MM4ACXInstValueTableV1)
    const   -> pool-ul de valori (defaults + valorile referite de varval)

Format `varval` (ASCII, linii `\\r\\n`):
    22 MM4ACXInstValueTableV1 8106
    131072 471 0 65617
    <packed_id> <const_index> <ext> <flag>

unde `packed_id = (pnu << 16) | index`, `const_index` indexează în `const`, iar
`flag` cu bitul 0x10000 setat marchează un parametru cu valoare instanță proprie
(adică modificat față de fabrică). `flag == -1` => parametru la valoarea default.

Format `const` (ASCII):
    1191 0 0 1 11 1 998 2147483647        (header)
    <id> 0 1 <type> 1 <value> 2147483647

`type`: 14 = float, restul (2/11/12...) = întreg/enum.

Validat empiric pe un proiect cu 6 × SINAMICS G120 CU240E-2 DP:
    p304=400V, p305=3.35A, p307=1.5kW, p310=50Hz, p311=1430rpm.

Returnează o listă de drive-uri, fiecare cu numele, modelul, firmware-ul,
familia (pentru join cu parametri_master) și parametrii modificați.
"""
from __future__ import annotations

import io
import os
import re
import sqlite3
import tempfile
import zipfile
from typing import Dict, List, Optional


# Tipuri de date din `const` care reprezintă valori în virgulă mobilă.
_FLOAT_TYPES = {'14'}

# Bit din coloana `flag` a `varval` care marchează "valoare instanță" (modificat).
_MODIFIED_BIT = 0x10000

# Parametri de date-motor pe care SINAMICS ii AUTO-CALCULEAZA (la p0340, din curentul/
# tensiunea introduse) si ii stocheaza cu flag=-1 (= "nemodificat manual") DESI au o
# valoare reala. Daca filtram doar dupa bitul "modificat", se pierd putere/cos phi/inertie/
# Rs etc. (ex: comisionare pe baza de curent -> p0307 putere ramane flag=-1 cu valoarea reala).
# Pentru acest set le includem in preview chiar daca flag=-1 (valorile 0/nesetate sar oricum).
_NAMEPLATE_PNUS = {
    304, 305, 307, 308, 309, 310, 311, 314, 316, 320, 322,
    335, 340, 341, 345, 350, 352, 356, 360, 625,
}


def _clean_float(s: str) -> str:
    """'3.349999905' -> '3.35', '50' -> '50', '1.5' -> '1.5'.

    STARTER stochează float-uri ca repr binar single-precision; le rotunjim la
    6 zecimale și eliminăm zerourile/punctul redundant.
    """
    try:
        v = float(s)
    except (ValueError, TypeError):
        return s
    if v != v or v in (float('inf'), float('-inf')):  # NaN / inf
        return s
    r = round(v, 6)
    if r == int(r):
        return str(int(r))
    # strip trailing zeros
    return f'{r:.6f}'.rstrip('0').rstrip('.')


def _familie_from_typename(typename: str) -> str:
    """'[SSP Sinamics G120 V4.7.13]SINAMICS CU240E-2 DP' -> 'SINAMICS_G120'."""
    t = (typename or '').lower()
    if 's120' in t or 's150' in t:
        return 'SINAMICS_S120_S150'
    if 'g130' in t or 'g150' in t:
        return 'SINAMICS_G130_G150'
    if 'g120' in t or 'sinamics' in t or 'micromaster' in t:
        return 'SINAMICS_G120'
    return ''


def _parse_typename(display_type: str):
    """Desparte OBJECT_DISPLAY_TYPENAME în (model, firmware).

    Ex: '[SSP Sinamics G120 V4.7.13]SINAMICS CU240E-2 DP V4.7.13'
        -> ('SINAMICS CU240E-2 DP', 'V4.7.13')
    """
    if not display_type:
        return '', ''
    # taie prefixul [SSP ...]
    model = re.sub(r'^\[[^\]]*\]', '', display_type).strip()
    fw = ''
    m = re.search(r'V\d+\.\d+(?:\.\d+)?', model)
    if m:
        fw = m.group(0)
        model = model[:m.start()].strip()
    return model, fw


def _decode(x) -> str:
    if isinstance(x, (bytes, bytearray)):
        return x.decode('latin-1', errors='replace')
    return '' if x is None else str(x)


def _parse_const(blob: bytes) -> Dict[int, tuple]:
    """const stream -> {id: (type, raw_value)}."""
    out: Dict[int, tuple] = {}
    text = _decode(blob)
    for ln in text.split('\r\n')[1:]:  # skip header
        p = ln.split()
        if len(p) >= 7:
            try:
                out[int(p[0])] = (p[3], p[5])
            except (ValueError, IndexError):
                continue
    return out


def _parse_varval(blob: bytes):
    """varval stream -> listă de (pnu, index, const_idx, flag)."""
    out = []
    text = _decode(blob)
    for ln in text.split('\r\n')[1:]:  # skip header
        p = ln.split()
        if len(p) < 4:
            continue
        try:
            packed = int(p[0])
            if packed < 0:
                continue
            const_idx = int(p[1])
            flag = int(p[3])
        except ValueError:
            continue
        out.append((packed >> 16, packed & 0xFFFF, const_idx, flag))
    return out


def _resolve_value(const_idx: int, const_pool: Dict[int, tuple]) -> Optional[str]:
    entry = const_pool.get(const_idx)
    if entry is None:
        return None
    typ, raw = entry
    if typ in _FLOAT_TYPES:
        return _clean_float(raw)
    return raw


def _format_code(pnu: int, index: int) -> str:
    """Format Siemens canonic, cu zero-padding la minim 4 cifre: p15 -> p0015,
    p304 -> p0304, p1120 -> p1120, p20383 -> p20383. Indexul (>0) se păstrează:
    p0840[1]. Trebuie să se potrivească exact cu `parametru` din parametri_master
    (ex. p0003, p0010), altfel descrierile și default-urile nu se rezolvă.
    """
    base = f'p{pnu:04d}'
    return f'{base}[{index}]' if index else base


def _read_project_drives(db_path: str) -> List[Dict]:
    """Deschide un Project.mcp (SQLite) și extrage drive-urile + parametrii."""
    conn = sqlite3.connect(db_path)
    conn.text_factory = bytes  # citim totul ca bytes, decodăm controlat
    cur = conn.cursor()

    # Object table: id -> (name, display_type, super_id)
    obj: Dict[str, tuple] = {}
    cur.execute('SELECT OBJECT_ID, OBJECT_NAME, OBJECT_DISPLAY_TYPENAME, OBJECT_SUPER_SUBIDX FROM OBJECTTABLE')
    for oid, name, dtype, sup in cur.fetchall():
        oid = _decode(oid)
        # OBJECT_SUPER_SUBIDX = '{GUID} <idx>' -> luăm doar GUID-ul
        sup_guid = _decode(sup).split()[0] if sup else ''
        obj[oid] = (_decode(name), _decode(dtype), sup_guid)

    # STG tree: storage_id -> guid(name) ; și gruparea stream-urilor pe parent
    cur.execute('SELECT STG_ID, STG_STG_ID, STG_TYPE, STG_NAME, STG_DATA FROM STG_CONTENTS2')
    stg_guid: Dict[int, str] = {}
    streams: Dict[int, Dict[str, bytes]] = {}
    for sid, parent, typ, name, data in cur.fetchall():
        nm = _decode(name)
        if typ == 1:  # storage node
            stg_guid[sid] = nm
        elif data is not None:  # stream
            streams.setdefault(parent, {})[nm] = data
    conn.close()

    drives: List[Dict] = []
    for parent_id, group in streams.items():
        if 'varval' not in group or 'const' not in group:
            continue
        cu_guid = stg_guid.get(parent_id)
        cu = obj.get(cu_guid)
        if not cu:
            continue
        # Numele/modelul vizibil: obiectul-părinte (device, ex G120_..._U705)
        device = obj.get(cu[2])  # cu[2] = super GUID
        if device and device[0]:
            nume = device[0]
            display_type = device[1] or cu[1]
        else:
            nume = cu[0]
            display_type = cu[1]

        model, firmware = _parse_typename(display_type)
        familie = _familie_from_typename(display_type)

        const_pool = _parse_const(group['const'])
        modified: Dict[str, str] = {}
        nameplate: Dict[str, str] = {}
        total = 0
        for pnu, index, const_idx, flag in _parse_varval(group['varval']):
            total += 1
            val = _resolve_value(const_idx, const_pool)
            if val is None:
                continue
            if flag != -1 and (flag & _MODIFIED_BIT):
                modified[_format_code(pnu, index)] = val
            elif index == 0 and pnu in _NAMEPLATE_PNUS and val not in ('', '0', '0.0'):
                # date-motor auto-calculate (flag=-1) cu valoare reala -> le pastram
                nameplate.setdefault(_format_code(pnu, index), val)
        # completeaza placuta auto-calculata FARA a suprascrie valorile setate manual
        for code, val in nameplate.items():
            modified.setdefault(code, val)

        drives.append({
            'nume': nume,
            'producator': 'Siemens',
            'model': model,
            'familie': familie,
            'firmware': firmware,
            'serial_number': '',  # nu este disponibil în proiectele offline
            'params': modified,
            'modified_count': len(modified),
            'total_count': total,
        })

    # ordonare stabilă după nume (U705, U725, ...)
    drives.sort(key=lambda d: d['nume'])
    return drives


def _find_mcp_in_zip(zf: zipfile.ZipFile) -> List[str]:
    """Returnează numele intrărilor care par a fi Project.mcp (SQLite)."""
    candidates = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        base = os.path.basename(info.filename).lower()
        if base.endswith('.mcp') and not base.endswith('.tmp'):
            candidates.append(info.filename)
    # preferă 'project.mcp' explicit, apoi după dimensiune (cel mai mare)
    candidates.sort(key=lambda n: (os.path.basename(n).lower() != 'project.mcp',
                                   -zf.getinfo(n).file_size))
    return candidates


def parse_archive(zip_bytes: bytes) -> Dict:
    """Parsează o arhivă ZIP de proiect STARTER și extrage drive-urile.

    Returns:
        {
          'project_name': str,
          'drives': [ {nume, producator, model, familie, firmware,
                       serial_number, params: {code: value},
                       modified_count, total_count}, ... ],
          'count': int,
        }
    Raises:
        ValueError dacă arhiva nu conține un proiect STARTER valid.
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as e:
        raise ValueError(f'Arhivă ZIP invalidă: {e}')

    mcp_names = _find_mcp_in_zip(zf)
    if not mcp_names:
        raise ValueError('Arhiva nu conține un fișier proiect STARTER (.mcp).')

    project_name = ''
    # numele proiectului: din .s7p sau din folderul rădăcină
    for info in zf.infolist():
        if info.filename.lower().endswith('.s7p'):
            project_name = os.path.splitext(os.path.basename(info.filename))[0]
            break

    # Limită anti zip-bomb pe dimensiunea decomprimată a fișierului proiect.
    _MAX_MCP_BYTES = 300 * 1024 * 1024

    last_err = None
    for mcp_name in mcp_names:
        if zf.getinfo(mcp_name).file_size > _MAX_MCP_BYTES:
            last_err = ValueError('Fișier proiect prea mare')
            continue
        raw = zf.read(mcp_name)
        if raw[:16] != b'SQLite format 3\x00':
            continue
        # sqlite3 are nevoie de un fișier pe disc
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        try:
            drives = _read_project_drives(tmp_path)
        except sqlite3.DatabaseError as e:
            last_err = e
            continue
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        if drives:
            if not project_name:
                project_name = os.path.basename(os.path.dirname(mcp_name)) or 'Proiect STARTER'
            return {
                'project_name': project_name,
                'drives': drives,
                'count': len(drives),
            }

    if last_err:
        raise ValueError(f'Nu am putut citi proiectul STARTER: {last_err}')
    raise ValueError('Nu am găsit niciun drive cu parametri în arhivă.')


if __name__ == '__main__':
    import sys
    path = sys.argv[1]
    with open(path, 'rb') as f:
        data = f.read()
    result = parse_archive(data)
    print(f"Proiect: {result['project_name']}  |  drive-uri: {result['count']}")
    for d in result['drives']:
        print(f"  {d['nume']:28} {d['model']:24} fw={d['firmware']:8} "
              f"modificați={d['modified_count']}/{d['total_count']}")
    if result['drives']:
        sample = result['drives'][0]
        print('\nExemplu parametri (primul drive):')
        for k, v in list(sample['params'].items())[:25]:
            print(f"    {k:10} = {v}")

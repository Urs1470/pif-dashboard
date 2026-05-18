"""Routing parser per producator pentru exporturi de parametri modificati.

Fiecare parser primeste bytes raw + filename si returneaza lista de dict-uri:
    [
      {
        'db_id': str,            # cod DB (ex: '0-10', '0x2540:001', 'p304')
        'raw_id': str,           # cod asa cum apare in export
        'name': str,             # denumire din export
        'value': str,            # valoare
        'default': str,          # default daca exista
        'setups': [int],         # opt - Setup-uri Danfoss
        'conflict': bool,        # opt - valori diferite intre Setup-uri
        'per_setup': dict,       # opt - daca conflict
      },
      ...
    ]
"""
from .danfoss import parse as parse_danfoss
from .lenze import parse as parse_lenze
from .siemens import parse as parse_siemens


PARSERS = {
    'Danfoss': parse_danfoss,
    'Lenze': parse_lenze,
    'Siemens': parse_siemens,
}


def parse_for_producator(producator, raw_bytes, filename=''):
    """Detecteaza parser-ul potrivit pentru producator si il apeleaza.

    Args:
        producator: numele producatorului (Danfoss, Lenze, Siemens, ABB)
        raw_bytes: bytes raw ai fisierului uploadat
        filename: numele fisierului (folosit pentru hint la detectie)
    Returns:
        tuple (key, parsed_list) sau (None, None) daca producator nu e suportat
    """
    producator_norm = (producator or '').strip().lower()
    for key, fn in PARSERS.items():
        if key.lower() in producator_norm:
            return key, fn(raw_bytes, filename)
    return None, None

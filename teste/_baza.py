"""Ce au in comun testele unitare de backend: radacina in `sys.path` si o baza NOUA.

Testele de aici ruleaza IN PROCES, fara server si fara browser — secunde, nu minute.
Au luat locul verificarilor din `scripts/test_suite.py` care nu puteau pica (scanau
fisiere sterse din iunie sau copia locala a bazei) si al partii de notificari care nu
trecea prin HTTP, dar statea in spatele unui login si nu rula niciodata automat.

RULARE (din radacina proiectului):
    python -m unittest discover -s teste
sau, cu tot restul: `python scripts/verifica.py`.

Biblioteca standard (`unittest`), fara pytest: nimic nou de instalat, nici pe masina
de dezvoltare, nici pe server.
"""

import os
import shutil
import sys
import tempfile
import unittest

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (RADACINA, os.path.join(RADACINA, 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import banc  # noqa: E402


class Test(unittest.TestCase):
    """Baza testelor care n-au nevoie de baza de date. Importul ei e cel care pune
    radacina proiectului in `sys.path` — de aceea toate testele pornesc de aici."""


class CuBazaNoua(Test):
    """Fiecare clasa primeste o baza NOUA, cu schema scrisa de `init_db()`, iar
    `database.DATABASE_PATH` arata spre ea cat ruleaza clasa. Baza de lucru
    (`pif_dashboard.db`) nu se atinge niciodata — o proba care scrie in ea a fost
    exact ce a gasit auditul din 2026-09-28 in `test_suite`."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix='pif-unit-')
        cls.db = os.path.join(cls._tmp, 'unit.db')
        banc.schema_noua(cls.db)
        import database
        cls._inainte = database.DATABASE_PATH
        database.DATABASE_PATH = cls.db

    @classmethod
    def tearDownClass(cls):
        import database
        database.DATABASE_PATH = cls._inainte
        shutil.rmtree(cls._tmp, ignore_errors=True)

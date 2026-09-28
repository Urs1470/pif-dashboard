"""Schema pe o baza GOALA: ajunge la versiunea curenta si are toate tabelele.

De ce: `init_db()` si migrarile v1..vN rulau doar peste copii ale unei baze deja
migrate — `smoke_ui` porneste pe copia locala, care e de mult la zi — deci o migrare
care crapa pe o instalare noua (o restaurare, o masina noua) nu se vedea nicaieri.
Ia si locul lui `db_table_check` din `test_suite`, care cauta `VALID_TABLES` in copia
locala a bazei (gitignored, veche) in loc de schema pe care o scrie codul.
"""

import sqlite3
import unittest

from _baza import CuBazaNoua


def _schema(cale):
    c = sqlite3.connect(cale)
    try:
        return c.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' "
            "ORDER BY type, name").fetchall()
    finally:
        c.close()


class SchemaDeLaZero(CuBazaNoua):

    def test_versiunea_e_cea_curenta(self):
        import database
        c = sqlite3.connect(self.db)
        try:
            v = c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0]
        finally:
            c.close()
        self.assertEqual(v, database.SCHEMA_VERSION)

    def test_tabelele_permise_exista(self):
        from utils import VALID_TABLES
        tabele = {r[1] for r in _schema(self.db) if r[0] == 'table'}
        self.assertEqual(set(VALID_TABLES) - tabele, set(),
                         'tabele din VALID_TABLES pe care schema noua nu le creeaza')

    def test_a_doua_rulare_nu_schimba_schema(self):
        # Serverul ruleaza `init_db()` la fiecare pornire: pe o baza la zi n-are voie
        # sa adauge, sa stearga sau sa rescrie nimic.
        import database
        inainte = _schema(self.db)
        database.init_db()
        self.assertEqual(_schema(self.db), inainte)


if __name__ == '__main__':
    unittest.main()

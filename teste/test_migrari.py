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


class CheileFaraCodPleaca(CuBazaNoua):
    """v42 (Ion, 2026-10-03, „Fă cele 6 puncte"): din `app_settings` pleaca `push_*`,
    `plan_departament_url`, `ics_feed_key` si `fault_data_rev`; orice alta cheie ramane."""

    PLEACA = ('push_vapid_private', 'push_sub_telefon', 'plan_departament_url', 'ics_feed_key',
              'fault_data_rev')
    RAMAN = ('obsidian_vault_path', 'pushover', 'debrief_abc', 'push')

    def _chei(self):
        c = sqlite3.connect(self.db)
        try:
            return {r[0] for r in c.execute('SELECT key FROM app_settings')}
        finally:
            c.close()

    def test_se_sterg_doar_cheile_fara_cod(self):
        import database
        c = sqlite3.connect(self.db)
        try:
            c.executemany("INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
                          "VALUES (?, 'x', '')", [(k,) for k in self.PLEACA + self.RAMAN])
            c.commit()
        finally:
            c.close()
        database.migrate_v41_to_v42()
        chei = self._chei()
        self.assertEqual(chei & set(self.PLEACA), set())
        # `pushover` si `push` nu incep cu `push_`: LIKE-ul are `_` scapat, nu „orice caracter".
        self.assertTrue(set(self.RAMAN) <= chei, set(self.RAMAN) - chei)

    def test_a_doua_rulare_nu_strica_nimic(self):
        import database
        database.migrate_v41_to_v42()
        inainte = self._chei()
        database.migrate_v41_to_v42()
        self.assertEqual(self._chei(), inainte)


if __name__ == '__main__':
    unittest.main()

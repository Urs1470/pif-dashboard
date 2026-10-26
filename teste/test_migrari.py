"""Schema pe o baza GOALA: ajunge la versiunea curenta si are toate tabelele.

De ce: `init_db()` si migrarile v1..vN rulau doar peste copii ale unei baze deja
migrate — `smoke_ui` porneste pe copia locala, care e de mult la zi — deci o migrare
care crapa pe o instalare noua (o restaurare, o masina noua) nu se vedea nicaieri.
Ia si locul lui `db_table_check` din `test_suite`, care cauta `VALID_TABLES` in copia
locala a bazei (gitignored, veche) in loc de schema pe care o scrie codul.
"""

import os
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


def _forma(cale, tabela):
    """Coloanele si cheile straine ale unei tabele, fara ordinea coloanelor: o baza urcata din v43
    primeste coloanele noi la coada, una noua le are in locul din CREATE."""
    c = sqlite3.connect(cale)
    try:
        coloane = {(r[1], r[2], r[3], r[4], r[5]) for r in c.execute('PRAGMA table_info("%s")' % tabela)}
        chei = {(r[2], r[3], r[4], r[6]) for r in c.execute('PRAGMA foreign_key_list("%s")' % tabela)}
        return coloane, chei
    finally:
        c.close()


class MigrareaV44(CuBazaNoua):
    """v43 -> v44 (etapa 3 din Torqa): ancore, `recurenta_baza`, `sabloane`, `stari_proiect`."""

    NOI = {'tasks': ('implementare_id', 'decalaj_zile', 'recurenta_baza'), 'global_tasks': ('recurenta_baza',)}

    def _baza_v43(self):
        """O copie a bazei clasei coborata la forma v43: fara coloanele si tabelele noi, cu
        `schema_version` 43 si cateva randuri. Coborarea cu DROP COLUMN, fiindca v44 doar adauga."""
        import shutil
        import tempfile
        cale = os.path.join(tempfile.mkdtemp(prefix='pif-v43-'), 'v43.db')
        self.addCleanup(shutil.rmtree, os.path.dirname(cale), ignore_errors=True)
        shutil.copyfile(self.db, cale)
        c = sqlite3.connect(cale)
        try:
            for tabela, coloane in self.NOI.items():
                for coloana in coloane:
                    c.execute('ALTER TABLE %s DROP COLUMN %s' % (tabela, coloana))
            c.execute('DROP TABLE sabloane')
            c.execute('DROP TABLE stari_proiect')
            c.execute('ALTER TABLE proiecte DROP COLUMN nr_oferta')  # v45
            c.execute('UPDATE schema_version SET version = 43')
            c.execute("INSERT INTO proiecte (id, tip, nume, status) VALUES ('p1', 'PIF', 'Vechi', 'pregatire')")
            c.execute("INSERT INTO implementari (id, proiect_id, data_start) VALUES ('i1', 'p1', '2026-10-12')")
            c.execute("INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta, recurenta, created_at) "
                      "VALUES ('t1', 'p1', 'Vechi', 'to_do', '2026-10-14', 'zilnic', 'x')")
            c.execute("INSERT INTO global_tasks (id, titlu, data_scadenta, recurenta, sfera, ora) "
                      "VALUES ('g1', 'Global', '2026-10-15', 'lunar', 'personal', '07:30')")
            c.commit()
        finally:
            c.close()
        return cale

    def _ruleaza_pe(self, cale, functie):
        import database
        inainte = database.DATABASE_PATH
        database.DATABASE_PATH = cale
        try:
            functie()
        finally:
            database.DATABASE_PATH = inainte

    def test_baza_noua_are_tabelele_si_coloanele_v44(self):
        import database
        self.assertGreaterEqual(database.SCHEMA_VERSION, 44)
        c = sqlite3.connect(self.db)
        try:
            self.assertEqual(c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0],
                             database.SCHEMA_VERSION)
            tabele = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            indexuri = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        finally:
            c.close()
        self.assertTrue({'sabloane', 'stari_proiect'} <= tabele)
        self.assertIn('idx_stari_proiect_proiect_data', indexuri)
        for tabela, coloane in self.NOI.items():
            self.assertTrue(set(coloane) <= {col[0] for col in _forma(self.db, tabela)[0]}, tabela)

    def test_o_baza_v43_urca_la_zi_cu_datele_intacte(self):
        import database
        cale = self._baza_v43()
        self._ruleaza_pe(cale, database.run_migrations)

        c = sqlite3.connect(cale)
        c.row_factory = sqlite3.Row
        try:
            self.assertEqual(c.execute('SELECT MAX(version) FROM schema_version').fetchone()[0],
                             database.SCHEMA_VERSION)
            t = dict(c.execute("SELECT * FROM tasks WHERE id = 't1'").fetchone())
            g = dict(c.execute("SELECT * FROM global_tasks WHERE id = 'g1'").fetchone())
            self.assertEqual((t['titlu'], t['data_scadenta'], t['recurenta']), ('Vechi', '2026-10-14', 'zilnic'))
            self.assertEqual((t['implementare_id'], t['decalaj_zile'], t['recurenta_baza']), (None, None, 'scadenta'))
            self.assertEqual((g['titlu'], g['sfera'], g['ora'], g['recurenta_baza']),
                             ('Global', 'personal', '07:30', 'scadenta'))
            self.assertEqual(c.execute("SELECT data_start FROM implementari WHERE id = 'i1'").fetchone()[0],
                             '2026-10-12')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM sabloane').fetchone()[0], 0)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM stari_proiect').fetchone()[0], 0)
        finally:
            c.close()
        # Aceeasi forma ca pe o baza noua.
        for tabela in ('tasks', 'global_tasks', 'sabloane', 'stari_proiect'):
            self.assertEqual(_forma(cale, tabela), _forma(self.db, tabela), tabela)

    def test_migrarea_se_poate_repeta(self):
        import database
        cale = self._baza_v43()
        self._ruleaza_pe(cale, database.run_migrations)
        inainte = _schema(cale)
        self._ruleaza_pe(cale, database.migrate_v43_to_v44)
        self._ruleaza_pe(cale, database.init_db)
        self.assertEqual(_schema(cale), inainte)

    def test_self_heal_aduce_inapoi_ce_lipseste_chiar_cu_versiunea_44(self):
        # O restaurare de baza veche peste una la v44: versiunea spune 44, structura lipseste.
        import database
        cale = self._baza_v43()
        c = sqlite3.connect(cale)
        try:
            c.execute('UPDATE schema_version SET version = 44')
            c.commit()
        finally:
            c.close()
        self._ruleaza_pe(cale, database.run_migrations)
        for tabela in ('tasks', 'global_tasks', 'sabloane', 'stari_proiect'):
            self.assertEqual(_forma(cale, tabela), _forma(self.db, tabela), tabela)


class MigrareaV45(CuBazaNoua):
    """v44 -> v45: `proiecte.nr_oferta`, completata o data din primul `OF_..` din `nr_comanda`."""

    _ruleaza_pe = MigrareaV44._ruleaza_pe

    # Formele reale din productie (citite pe 2026-10-26), plus doua fara oferta.
    COMENZI = {
        'romkuvert': ('OF_26_23125 (ofertă semnată de client, 14.10.2026)', 'OF_26_23125'),
        'biochem': ('9RH1177 / OF_26_03018', 'OF_26_03018'),
        'duplex': ('OF_26_07123_R1 / PO 4504976437 (+ OF_26_14613 supliment contrapanou A12)', 'OF_26_07123_R1'),
        'tde': ('OF 250326E (ofertă)', None),
        'po': ('PO 4504978671', None),
        'gol': (None, None),
    }

    def _baza_v44(self, versiune=44):
        import shutil
        import tempfile
        cale = os.path.join(tempfile.mkdtemp(prefix='pif-v44-'), 'v44.db')
        self.addCleanup(shutil.rmtree, os.path.dirname(cale), ignore_errors=True)
        shutil.copyfile(self.db, cale)
        c = sqlite3.connect(cale)
        try:
            c.execute('ALTER TABLE proiecte DROP COLUMN nr_oferta')
            c.execute('UPDATE schema_version SET version = ?', (versiune,))
            for pid, (comanda, _) in self.COMENZI.items():
                c.execute("INSERT INTO proiecte (id, tip, nume, status, nr_comanda) VALUES (?, 'PIF', ?, 'pregatire', ?)",
                          (pid, pid, comanda))
            c.commit()
        finally:
            c.close()
        return cale

    def _oferte(self, cale):
        c = sqlite3.connect(cale)
        try:
            return {r[0]: (r[1], r[2]) for r in c.execute('SELECT id, nr_comanda, nr_oferta FROM proiecte')}
        finally:
            c.close()

    def test_baza_noua_are_coloana(self):
        self.assertIn('nr_oferta', {col[0] for col in _forma(self.db, 'proiecte')[0]})

    def test_o_baza_v44_primeste_oferta_si_comanda_ramane(self):
        import database
        cale = self._baza_v44()
        self._ruleaza_pe(cale, database.run_migrations)
        self.assertEqual(self._oferte(cale), {pid: (comanda, oferta) for pid, (comanda, oferta) in self.COMENZI.items()})
        self.assertEqual(_forma(cale, 'proiecte'), _forma(self.db, 'proiecte'))

    def test_a_doua_rulare_nu_suprascrie_ce_a_scris_ion(self):
        import database
        cale = self._baza_v44()
        self._ruleaza_pe(cale, database.run_migrations)
        c = sqlite3.connect(cale)
        try:
            c.execute("UPDATE proiecte SET nr_oferta = 'OF_26_14613' WHERE id = 'duplex'")
            c.execute("UPDATE proiecte SET nr_oferta = '' WHERE id = 'biochem'")
            c.commit()
        finally:
            c.close()
        self._ruleaza_pe(cale, database.migrate_v44_to_v45)
        self._ruleaza_pe(cale, database.run_migrations)
        oferte = self._oferte(cale)
        self.assertEqual(oferte['duplex'][1], 'OF_26_14613')
        self.assertEqual(oferte['biochem'][1], '')

    def test_self_heal_cu_versiunea_45_si_coloana_lipsa(self):
        # O restaurare de dinainte de v45 peste o baza la v45.
        import database
        cale = self._baza_v44(versiune=45)
        self._ruleaza_pe(cale, database.run_migrations)
        self.assertEqual(self._oferte(cale)['biochem'], ('9RH1177 / OF_26_03018', 'OF_26_03018'))
        self.assertEqual(_forma(cale, 'proiecte'), _forma(self.db, 'proiecte'))


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

"""Backup apoi restore: fiecare coloana a fiecarei tabele exportate trebuie sa se intoarca.

`/api/backup` exporta tabelele cu `SELECT *`, deci cu toate coloanele. Restaurarea avea INSERT-uri
scrise de mana, cu coloanele enumerate, iar o coloana adaugata dupa ele se pierdea in tacere:
`proiecte.data_finalizare`, `vault_folder` si `notify_on_complete`, `global_tasks.ora`,
`tasks.data_start` / `progres` / `is_milestone`. Auditul din 2026-10-03 a facut backup, restore si
le-a gasit goale. Acum restaurarea ia coloanele din schema (`admin._reinsereaza`).

Testul de dus-intors de aici nu enumera coloane. Ia fiecare tabela si fiecare coloana din
`PRAGMA table_info`, scrie in ea o valoare DIFERITA de cea implicita (altfel o coloana pierduta
ar reveni oricum pe implicit si nu s-ar vedea), face backup, restaureaza intr-o baza noua si
compara toate randurile, toate coloanele. O coloana viitoare intra singura in verificare; una
pierduta pica testul.
"""

import os
import shutil
import sqlite3

from _aplicatia import CuAplicatia      # primul: `_baza` pune radacina si scripts/ in sys.path
from blueprints.admin import TABELE_BACKUP
from utils import DATE_FIELDS


# --------------------------------------------------------------------- date de proba, din schema

def implicit(dflt):
    """Valoarea implicita a unei coloane, din `PRAGMA table_info.dflt_value` (un literal SQL)."""
    if dflt is None:
        return None
    s = str(dflt)
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    try:
        return int(s)
    except ValueError:
        return s


# Cheile straine (si „legaturile" fara cheie, ca `task_subtasks.task_id`): randul n arata spre
# randul n al parintelui, ca baza sa accepte inserarea.
LEGATURI = {
    ('tasks', 'proiect_id'): lambda n: 'proiecte-%d' % n,
    ('task_subtasks', 'task_id'): lambda n: 'tasks-%d' % n,
    ('implementari', 'proiect_id'): lambda n: 'proiecte-%d' % n,
}
RANDURI = 2


def valoare(tabela, coloana, tip, dflt, pk, n):
    """O valoare pentru randul `n`, DIFERITA de implicita (o verifica `genereaza`)."""
    if (tabela, coloana) in LEGATURI:
        return LEGATURI[(tabela, coloana)](n)
    if pk:
        return '%s-%d' % (tabela, n)
    if coloana in DATE_FIELDS:
        return '2026-09-%02d' % (10 + n)         # utils.norm_date lasa neatinse datele ISO
    if 'INT' in (tip or '').upper():
        d = implicit(dflt)
        return 0 if d == 1 else (d or 0) + 1      # 0 / NULL -> 1, 1 -> 0, k -> k + 1
    return '%s.%s#%d' % (tabela, coloana, n)


def schema(cale):
    """{tabela: [(nume, tip, dflt, pk), ...]} pentru tabelele din backup."""
    c = sqlite3.connect(cale)
    try:
        return {t: [(r[1], r[2], r[4], r[5]) for r in c.execute('PRAGMA table_info("%s")' % t)]
                for t in TABELE_BACKUP}
    finally:
        c.close()


def genereaza(cale):
    """Scrie `RANDURI` randuri in fiecare tabela din backup, cu TOATE coloanele pe valori
    non-implicite. Intoarce schema, ca testul sa o refoloseasca."""
    sch = schema(cale)
    c = sqlite3.connect(cale)
    c.execute('PRAGMA foreign_keys=ON')
    try:
        for tabela in TABELE_BACKUP:
            coloane = sch[tabela]
            for n in range(1, RANDURI + 1):
                rand = {}
                for nume, tip, dflt, pk in coloane:
                    v = valoare(tabela, nume, tip, dflt, pk, n)
                    assert v != implicit(dflt), (
                        '%s.%s: valoarea de proba %r e chiar cea implicita — o coloana pierduta la '
                        'restaurare ar trece neobservata' % (tabela, nume, v))
                    rand[nume] = v
                c.execute('INSERT INTO "%s" (%s) VALUES (%s)' % (
                    tabela, ', '.join('"%s"' % k for k in rand), ', '.join('?' * len(rand))),
                    list(rand.values()))
        c.commit()
    finally:
        c.close()
    return sch


def citeste(cale, tabela):
    """Toate randurile tabelei, ca dictionare, in ordinea cheii primare. `push_*` nu intra in
    compararea cu backup-ul: nu pleaca de pe masina."""
    c = sqlite3.connect(cale)
    c.row_factory = sqlite3.Row
    try:
        pk = [r['name'] for r in c.execute('PRAGMA table_info("%s")' % tabela) if r['pk']]
        randuri = [dict(r) for r in c.execute('SELECT * FROM "%s" ORDER BY %s' % (tabela, ', '.join(pk)))]
    finally:
        c.close()
    if tabela == 'app_settings':
        randuri = [r for r in randuri if not r['key'].startswith('push_')]
    return randuri


def scrie(cale, sql, *param):
    c = sqlite3.connect(cale)
    try:
        c.execute(sql, param)
        c.commit()
    finally:
        c.close()


# ---------------------------------------------------------------------------------------- teste

class BackupSiRestore(CuAplicatia):

    def setUp(self):
        super().setUp()
        import database
        self.database = database
        self.sursa = self._baza_noua('sursa.db')
        self.destinatie = self._baza_noua('destinatie.db')
        self.addCleanup(self.catre, self.db)           # `CuBazaNoua` asteapta baza clasei pe loc
        self.catre(self.sursa)

    def _baza_noua(self, nume):
        """O baza cu schema completa (init_db + toate migrarile, ~1 s): se copiaza baza clasei,
        pe care testele nu o ating niciodata."""
        cale = os.path.join(self.dir_temp(), nume)
        shutil.copyfile(self.db, cale)
        return cale

    def catre(self, cale):
        """Aplicatia lucreaza de acum pe `cale` (database.get_db citeste DATABASE_PATH la apel)."""
        self.database.DATABASE_PATH = cale

    def backup(self):
        r = self.client.get('/api/backup', headers=self.bearer())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def restaureaza(self, continut, cale=None):
        if cale:
            self.catre(cale)
        return self.client.post('/api/restore', json=continut, headers=self.bearer())

    # ------------------------------------------------------------------ dus-intors, toate coloanele

    def test_backup_apoi_restore_intoarce_toate_coloanele_tuturor_tabelelor(self):
        sch = genereaza(self.sursa)
        backup = self.backup()

        # Backup-ul trebuie sa fie complet: fiecare tabela, fiecare rand, fiecare coloana.
        self.assertEqual(set(backup), set(TABELE_BACKUP))
        for tabela, coloane in sch.items():
            self.assertEqual(len(backup[tabela]), RANDURI, tabela)
            self.assertEqual(set(backup[tabela][0]), {c[0] for c in coloane}, tabela)

        r = self.restaureaza(backup, self.destinatie)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

        for tabela in TABELE_BACKUP:
            inainte, dupa = citeste(self.sursa, tabela), citeste(self.destinatie, tabela)
            self.assertEqual(len(dupa), RANDURI, tabela)
            for a, b in zip(inainte, dupa):
                for coloana, v in a.items():
                    self.assertEqual(b.get(coloana), v, '%s.%s nu s-a restaurat' % (tabela, coloana))
            self.assertEqual(dupa, inainte, tabela)

    def test_o_coloana_adaugata_maine_se_restaureaza_fara_sa_atingi_restore_ul(self):
        # Nimic din cod nu o enumera: vine din schema. (Aici se adauga doar in cele doua baze de proba.)
        for cale in (self.sursa, self.destinatie):
            c = sqlite3.connect(cale)
            try:
                c.execute("ALTER TABLE proiecte ADD COLUMN zz_viitoare TEXT DEFAULT 'implicit'")
                c.execute("ALTER TABLE tasks ADD COLUMN zz_viitoare INTEGER")
                c.commit()
            finally:
                c.close()
        genereaza(self.sursa)
        backup = self.backup()
        self.assertEqual(backup['proiecte'][0]['zz_viitoare'], 'proiecte.zz_viitoare#1')
        self.assertEqual(self.restaureaza(backup, self.destinatie).status_code, 200)
        self.assertEqual([p['zz_viitoare'] for p in citeste(self.destinatie, 'proiecte')],
                         ['proiecte.zz_viitoare#1', 'proiecte.zz_viitoare#2'])
        self.assertEqual([x['zz_viitoare'] for x in citeste(self.destinatie, 'tasks')], [1, 1])
        for tabela in TABELE_BACKUP:
            self.assertEqual(citeste(self.destinatie, tabela), citeste(self.sursa, tabela), tabela)

    def test_coloanele_pierdute_pe_2_octombrie_se_intorc(self):
        # Coloanele care lipseau din INSERT-urile de mana, numite, ca cine citeste testul sa vada
        # ce s-a intamplat (testul generic de sus nu le enumera). `notify_on_complete` si cele trei
        # ale Ganttului (`tasks.data_start`, `progres`, `is_milestone`) au plecat din schema in v43.
        genereaza(self.sursa)
        r = self.restaureaza(self.backup(), self.destinatie)
        self.assertEqual(r.status_code, 200)
        p = citeste(self.destinatie, 'proiecte')[0]
        self.assertEqual((p['data_finalizare'], p['vault_folder']), ('2026-09-11', 'proiecte.vault_folder#1'))
        self.assertEqual(citeste(self.destinatie, 'global_tasks')[0]['ora'], 'global_tasks.ora#1')

    def test_secretele_push_nu_pleaca_in_backup_si_nu_se_pierd_la_restore(self):
        genereaza(self.sursa)
        scrie(self.sursa, "INSERT INTO app_settings (key, value, updated_at) VALUES ('push_vapid_private', 'SECRET', 'x')")
        backup = self.backup()
        self.assertNotIn('SECRET', str(backup))
        scrie(self.destinatie, "INSERT INTO app_settings (key, value, updated_at) VALUES ('push_vapid_private', 'AL-MASINII', 'y')")
        self.assertEqual(self.restaureaza(backup, self.destinatie).status_code, 200)
        c = sqlite3.connect(self.destinatie)
        try:
            push = c.execute("SELECT key, value FROM app_settings WHERE key LIKE 'push!_%' ESCAPE '!'").fetchall()
        finally:
            c.close()
        self.assertEqual(push, [('push_vapid_private', 'AL-MASINII')], 'starea per-masina ramane a masinii')

    def test_un_rand_push_dintr_un_fisier_editat_de_mana_nu_intra(self):
        backup = self.backup()
        backup['app_settings'] = [{'key': 'push_injectat', 'value': 'x', 'updated_at': ''},
                                  {'key': 'ramane', 'value': 'v', 'updated_at': ''}]
        self.assertEqual(self.restaureaza(backup, self.destinatie).status_code, 200)
        self.assertEqual([r['key'] for r in citeste(self.destinatie, 'app_settings')], ['ramane'])
        c = sqlite3.connect(self.destinatie)
        try:
            self.assertEqual(c.execute("SELECT COUNT(*) FROM app_settings WHERE key = 'push_injectat'").fetchone()[0], 0)
        finally:
            c.close()

    # ------------------------------------------------------------ backup-uri facute inainte de azi

    def test_un_backup_vechi_se_restaureaza_ca_inainte_cu_implicitele_coloanelor_noi(self):
        """Formatul backup-ului nu s-a schimbat. Un backup facut inainte de coloanele v35-v41 (sau cu
        coloane scoase intre timp) se restaureaza: ce lipseste din rand ia valoarea implicita a
        coloanei, ce nu mai exista in tabela se ignora, iar `data_planificata` (inainte de v33)
        devine termen acolo unde termenul lipseste."""
        vechi = {
            'proiecte': [{'id': 'p1', 'tip': 'PIF', 'nume': 'Vechi', 'client': 'ACME', 'status': 'in_lucru',
                          'deadline': '2025-01-01', 'pm': 'X', 'nr_contract': 'C1', 'data_incepere': '2025-01-02',
                          'confirmat_client': 1, 'created_at': '2025-01-01T00:00:00'}],
            'tasks': [{'id': 't1', 'proiect_id': 'p1', 'titlu': 'Vechi', 'status': 'in_lucru',
                       'prioritate': 'urgent', 'faza': 'x', 'data_planificata': '2025-02-03',
                       'data_scadenta': '', 'ordine': 2}],
            'task_subtasks': [{'id': 's1', 'task_id': 't1', 'titlu': 'Pas', 'done': 1}],
            'global_tasks': [{'id': 'g1', 'titlu': 'Zilnic', 'prioritate': 'normal',
                              'data_planificata': '2025-02-04', 'sfera': None}],
            'implementari': [{'id': 'i1', 'proiect_id': 'p1', 'data_start': '2025-03-01', 'locatie': '',
                              'faza': None, 'confirmata': True}],
            'app_settings': [{'key': 'obsidian_vault_path', 'value': '/x', 'updated_at': 'z'}],
            # tabele disparute din schema: backup-urile vechi le au, restore-ul nu le citeste
            'jurnal': [{'id': 'j1'}], 'checklist_pif': [{'id': 'k1'}], 'assistant_memory': [{'id': 'a1'}],
            'task_dependencies': [{'id': 'd1'}], 'calcule': [{'id': 'k1'}],
            'clienti': [{'id': 'c1', 'nume': 'ACME'}],
        }
        r = self.restaureaza(vechi, self.destinatie)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        p = citeste(self.destinatie, 'proiecte')[0]
        self.assertEqual((p['status'], p['confirmat_client'], p['client']), ('in_lucru', 1, 'ACME'))
        self.assertEqual((p['vault_folder'], p['data_finalizare']), (None, None),
                         'coloanele care nu erau in backup iau implicita')
        self.assertNotIn('notify_on_complete', p, 'coloana scoasa in v43 nu revine din backup')
        t = citeste(self.destinatie, 'tasks')[0]
        self.assertEqual((t['data_scadenta'], t['ordine'], t['status']), ('2025-02-03', 2, 'in_lucru'))
        self.assertFalse({'data_start', 'progres', 'is_milestone', 'ordine_agenda'} & set(t),
                         'coloanele Ganttului si ale agendei nu revin din backup')
        g = citeste(self.destinatie, 'global_tasks')[0]
        self.assertEqual((g['data_scadenta'], g['sfera'], g['ora'], g['categorie']), ('2025-02-04', 'munca', None, 'General'))
        i = citeste(self.destinatie, 'implementari')[0]
        self.assertEqual((i['locatie'], i['faza'], i['confirmata']), ('site', 'implementare', 1))
        self.assertEqual(citeste(self.destinatie, 'task_subtasks')[0]['done'], 1)
        self.assertEqual([r['key'] for r in citeste(self.destinatie, 'app_settings')], ['obsidian_vault_path'])
        c = sqlite3.connect(self.destinatie)
        try:
            tabele = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            c.close()
        self.assertFalse(tabele & {'jurnal', 'checklist_pif', 'assistant_memory', 'task_dependencies',
                                   'calcule', 'clienti'}, 'nu se creeaza tabele')

    def test_un_backup_fara_unele_tabele_le_goleste_pe_cele_lipsa(self):
        genereaza(self.sursa)
        # Restore peste o baza plina, cu un backup care are doar proiecte: restul se goleste (ca inainte).
        self.catre(self.destinatie)
        genereaza(self.destinatie)
        r = self.restaureaza({'proiecte': [{'id': 'unic', 'tip': 'PIF', 'nume': 'Doar eu'}]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual([p['id'] for p in citeste(self.destinatie, 'proiecte')], ['unic'])
        for tabela in TABELE_BACKUP:
            if tabela != 'proiecte':
                self.assertEqual(citeste(self.destinatie, tabela), [], tabela)

    # ------------------------------------------------------------------------ tranzactia

    def test_un_fisier_stricat_anuleaza_totul_si_baza_ramane_cum_era(self):
        genereaza(self.destinatie)
        inainte = {t: citeste(self.destinatie, t) for t in TABELE_BACKUP}
        stricat = {'proiecte': [{'id': 'bun', 'tip': 'PIF', 'nume': 'Bun'},
                                {'id': 'rau', 'tip': 'PIF'}]}               # `nume` NOT NULL lipseste
        with self.assertLogs('blueprints.admin', level='ERROR'):
            r = self.restaureaza(stricat, self.destinatie)
        self.assertEqual(r.status_code, 500)
        self.assertIn('anulate', r.get_json()['error'])
        for tabela in TABELE_BACKUP:
            self.assertEqual(citeste(self.destinatie, tabela), inainte[tabela], '%s ramane neatins' % tabela)

    def test_un_rand_fara_nicio_coloana_cunoscuta_anuleaza_totul(self):
        genereaza(self.destinatie)
        inainte = citeste(self.destinatie, 'proiecte')
        with self.assertLogs('blueprints.admin', level='ERROR'):
            r = self.restaureaza({'proiecte': [{'nimic_cunoscut': 1}]}, self.destinatie)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(citeste(self.destinatie, 'proiecte'), inainte)

    def test_dispozitivul_nu_poate_face_nici_backup_nici_restore(self):
        from _aplicatia import DEVICE
        self.assertEqual(self.client.get('/api/backup', headers=self.bearer(DEVICE)).status_code, 401)
        self.assertEqual(self.client.post('/api/restore', json={}, headers=self.bearer(DEVICE)).status_code, 401)


if __name__ == '__main__':
    import unittest
    unittest.main()

"""Statusurile impuse in baza (v48, E-015).

Pana in v48 vocabularul (`pregatire`|`finalizat` la proiecte, `to_do`|`done` la taskuri) era doar o
conventie a aplicatiei: un `UPDATE` direct, un client cu o cheie veche sau un restore dintr-un backup
vechi puteau scrie orice. Acum triggerele refuza orice alta valoare, migrarea strange ce era deja in
baza, iar rutele si restore-ul traduc cheile vechi in loc sa raspunda 500.
"""

import sqlite3
import unittest

from _aplicatia import CuAplicatia, DEVICE
from _baza import CuBazaNoua


class TriggerePeBazaNoua(CuBazaNoua):

    def conn(self):
        c = sqlite3.connect(self.db)
        c.execute('PRAGMA foreign_keys=ON')
        return c

    def test_baza_noua_are_cele_sase_triggere(self):
        with self.conn() as c:
            nume = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'status_%'")}
        self.assertEqual(nume, {'status_%s_%s' % (t, e) for t in ('proiecte', 'tasks', 'global_tasks')
                                for e in ('insert', 'update')})

    def test_update_direct_cu_status_necunoscut_e_refuzat(self):
        c = self.conn()
        c.execute("INSERT INTO proiecte (id, tip, nume) VALUES ('p1', 'PIF', 'T')")
        c.execute("INSERT INTO tasks (id, proiect_id, titlu) VALUES ('t1', 'p1', 'T')")
        c.execute("INSERT INTO global_tasks (id, titlu) VALUES ('g1', 'T')")
        c.commit()
        for sql in ("UPDATE proiecte SET status = 'in_lucru' WHERE id = 'p1'",
                    "UPDATE proiecte SET status = NULL WHERE id = 'p1'",
                    "UPDATE tasks SET status = 'finalizat' WHERE id = 't1'",
                    "UPDATE global_tasks SET status = 'blocat' WHERE id = 'g1'",
                    "INSERT INTO tasks (id, proiect_id, titlu, status) VALUES ('t2', 'p1', 'T', 'oricare')",
                    "INSERT INTO proiecte (id, tip, nume, status) VALUES ('p2', 'PIF', 'T', 'anulat')"):
            with self.subTest(sql=sql), self.assertRaisesRegex(sqlite3.IntegrityError, 'status invalid'):
                c.execute(sql)
        # Valorile permise si default-urile trec.
        c.execute("UPDATE proiecte SET status = 'finalizat' WHERE id = 'p1'")
        c.execute("UPDATE tasks SET status = 'done' WHERE id = 't1'")
        c.execute("UPDATE global_tasks SET status = 'done', titlu = 'X' WHERE id = 'g1'")
        c.execute("UPDATE tasks SET titlu = 'fara status' WHERE id = 't1'")
        c.commit()
        c.close()


class MigrareaStrangeRandurileVechi(CuBazaNoua):

    def test_impune_statusurile_strange_si_e_idempotenta(self):
        import database
        c = sqlite3.connect(self.db)
        for t in ('proiecte', 'tasks', 'global_tasks'):
            for e in ('insert', 'update'):
                c.execute('DROP TRIGGER status_%s_%s' % (t, e))
        c.executemany("INSERT INTO proiecte (id, tip, nume, status, data_finalizare) VALUES (?, 'PIF', 'T', ?, ?)",
                      [('a', 'in_lucru', '2026-01-01'), ('b', 'finalizat', '2026-02-02'), ('c', None, ''),
                       ('d', 'pregatire', '')])
        c.executemany("INSERT INTO tasks (id, proiect_id, titlu, status) VALUES (?, 'b', 'T', ?)",
                      [('t1', 'finalizat'), ('t2', 'blocat'), ('t3', 'done'), ('t4', None)])
        c.executemany("INSERT INTO global_tasks (id, titlu, status) VALUES (?, 'T', ?)",
                      [('g1', 'in_asteptare'), ('g2', 'to_do')])
        c.commit()
        self.assertEqual(database.impune_statusurile(c), {'proiecte': 2, 'tasks': 3, 'global_tasks': 1})
        c.commit()
        self.assertEqual(dict(c.execute('SELECT id, status || "|" || data_finalizare FROM proiecte')),
                         {'a': 'pregatire|', 'b': 'finalizat|2026-02-02', 'c': 'pregatire|', 'd': 'pregatire|'})
        self.assertEqual(dict(c.execute('SELECT id, status FROM tasks')),
                         {'t1': 'done', 't2': 'to_do', 't3': 'done', 't4': 'to_do'})
        self.assertEqual(dict(c.execute('SELECT id, status FROM global_tasks')), {'g1': 'to_do', 'g2': 'to_do'})
        self.assertEqual(database.impune_statusurile(c), {})
        with self.assertRaises(sqlite3.IntegrityError):
            c.execute("UPDATE tasks SET status = 'blocat' WHERE id = 't1'")
        c.close()


class RuteleTraducCheileVechi(CuAplicatia):

    def setUp(self):
        super().setUp()
        r = self.client.post('/api/proiecte', json={'id': 'p-st', 'nume': 'T', 'tip': 'PIF'},
                             headers=self.bearer(DEVICE))
        self.assertIn(r.status_code, (201, 409), r.get_data(as_text=True))

    def status_task(self, tid):
        c = sqlite3.connect(self.db)
        try:
            return c.execute('SELECT status FROM tasks WHERE id = ?', (tid,)).fetchone()[0]
        finally:
            c.close()

    def test_task_cu_status_necunoscut_da_400_nu_500(self):
        r = self.client.post('/api/proiecte/p-st/tasks', json={'titlu': 'X', 'status': 'oricare'},
                             headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        r = self.client.post('/api/global-tasks', json={'titlu': 'X', 'status': 'oricare'},
                             headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))

    def test_cheia_veche_se_traduce_si_status_null_ramane_to_do(self):
        r = self.client.post('/api/proiecte/p-st/tasks', json={'id': 't-null', 'titlu': 'X', 'status': None},
                             headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(self.status_task('t-null'), 'to_do')
        r = self.client.put('/api/tasks/t-null', json={'status': 'finalizat'}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.status_task('t-null'), 'done')
        r = self.client.put('/api/tasks/t-null', json={'status': 'blocat'}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.status_task('t-null'), 'to_do')

    def test_restore_cu_backup_vechi_strange_statusurile(self):
        backup = {
            'proiecte': [{'id': 'p-vechi', 'tip': 'PIF', 'nume': 'V', 'status': 'in_lucru',
                          'data_finalizare': '2026-01-01'}],
            'tasks': [{'id': 't-vechi', 'proiect_id': 'p-vechi', 'titlu': 'V', 'status': 'finalizat'}],
            'global_tasks': [{'id': 'g-vechi', 'titlu': 'V', 'status': 'blocat'}],
        }
        r = self.client.post('/api/restore', json=backup, headers=self.bearer())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        c = sqlite3.connect(self.db)
        try:
            self.assertEqual(c.execute("SELECT status, data_finalizare FROM proiecte WHERE id = 'p-vechi'").fetchone(),
                             ('pregatire', ''))
            self.assertEqual(c.execute("SELECT status FROM tasks WHERE id = 't-vechi'").fetchone(), ('done',))
            self.assertEqual(c.execute("SELECT status FROM global_tasks WHERE id = 'g-vechi'").fetchone(), ('to_do',))
        finally:
            c.close()


if __name__ == '__main__':
    unittest.main()

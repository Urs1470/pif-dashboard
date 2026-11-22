"""Lista ascunsa `sistem`: taskurile pe care le face sistemul (coada lui Claude, rezultatele, amanarile) nu ajung in Torqa.

Ion, 2026-11-22: „nu vreau sa-mi poluezi Today sau task-urile cu ceea ce e din system". Lista nu e un rand din `liste`
(constanta `database.LISTA_SISTEM`, fara schema noua): scripturile o scriu si o citesc cu `?sfera=sistem` sau `?sfera=toate`,
iar snapshot-ul pentru Torqa, `/api/liste` si calendarul n-o arata. Decizia: docs/decizii/2026-11-22-lista-sistem.md.
"""

import sqlite3
import unittest

from _aplicatia import CuAplicatia, DEVICE, FULL


class CuSistem(CuAplicatia):

    def setUp(self):
        super().setUp()
        c = sqlite3.connect(self.db)
        try:
            c.execute('DELETE FROM global_tasks')
            c.execute('DELETE FROM task_subtasks')
            c.execute('DELETE FROM liste WHERE fixa = 0')
            c.commit()
        finally:
            c.close()

    def h(self, token=FULL):
        return self.bearer(token)

    def task(self, titlu='T', token=FULL, **extra):
        r = self.client.post('/api/global-tasks', json={'titlu': titlu, **extra}, headers=self.h(token))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def titluri(self, cale, token=FULL):
        r = self.client.get(cale, headers=self.h(token))
        self.assertEqual(r.status_code, 200, (cale, r.get_data(as_text=True)))
        return sorted(t['titlu'] for t in r.get_json())

    def amestec(self):
        """Doua taskuri ale lui Ion si doua ale sistemului, cu termen azi si cu un subtask pe fiecare din cele de sistem."""
        self.task('Munca lui Ion', sfera='munca', data_scadenta='2026-11-23')
        self.task('Personal al lui Ion', sfera='personal')
        a = self.task('Claude lucrează: X', sfera='sistem', data_scadenta='2026-11-23')
        b = self.task('Revin: rezultatul lui Claude «X»', sfera='sistem', data_scadenta='2026-11-23')
        c = sqlite3.connect(self.db)
        try:
            for i, t in enumerate((a, b)):
                c.execute("INSERT INTO task_subtasks (id, task_id, titlu, done, ordine) VALUES (?, ?, 'pas', 0, 0)",
                          ('sub-%d' % i, t))
            c.commit()
        finally:
            c.close()
        return a, b


class SferaSistem(CuSistem):

    def test_un_task_se_creeaza_in_sistem_cu_oricare_token(self):
        for token in (FULL, DEVICE):
            tid = self.task('Claude: ceva', token=token, sfera='sistem')
            r = self.client.get('/api/global-tasks/%s' % tid, headers=self.h(token))
            self.assertEqual(r.get_json()['sfera'], 'sistem')

    def test_fara_token_401(self):
        r = self.client.post('/api/global-tasks', json={'titlu': 'x', 'sfera': 'sistem'})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.get('/api/global-tasks?sfera=sistem').status_code, 401)

    def test_lista_de_sistem_si_toate_le_dau_pe_cele_de_sistem_iar_restul_nu(self):
        self.amestec()
        self.assertEqual(self.titluri('/api/global-tasks?sfera=sistem'),
                         ['Claude lucrează: X', 'Revin: rezultatul lui Claude «X»'])
        self.assertEqual(len(self.titluri('/api/global-tasks?sfera=toate')), 4, 'scripturile gasesc tot prin `toate`')
        self.assertEqual(self.titluri('/api/global-tasks'), ['Munca lui Ion'], 'implicit doar munca')
        self.assertEqual(self.titluri('/api/global-tasks?sfera=munca'), ['Munca lui Ion'])
        self.assertEqual(self.titluri('/api/global-tasks?sfera=personal'), ['Personal al lui Ion'])

    def test_arhiva_sistemului_se_citeste_cu_arhiva_true(self):
        tid = self.task('Claude gata: X', sfera='sistem')
        self.client.put('/api/global-tasks/%s' % tid, json={'status': 'done'}, headers=self.h())
        self.assertEqual(self.titluri('/api/global-tasks?sfera=toate&arhiva=true'), ['Claude gata: X'])
        self.assertEqual(self.titluri('/api/global-tasks?sfera=sistem&arhiva=true'), ['Claude gata: X'])

    def test_sfera_necunoscuta_ramane_400_si_spune_si_sistem(self):
        r = self.client.get('/api/global-tasks?sfera=Sistem', headers=self.h())
        self.assertEqual(r.status_code, 400)
        self.assertIn("'sistem'", r.get_json()['error'])

    def test_un_task_muncit_se_muta_in_sistem_cu_acelasi_put_care_il_marcheaza(self):
        tid = self.task('Claude: ceva', sfera='munca')
        r = self.client.put('/api/global-tasks/%s' % tid, json={'titlu': 'Claude lucrează: ceva', 'sfera': 'sistem'},
                            headers=self.h())
        self.assertEqual(r.status_code, 200)
        g = self.client.get('/api/global-tasks/%s' % tid, headers=self.h()).get_json()
        self.assertEqual((g['titlu'], g['sfera']), ('Claude lucrează: ceva', 'sistem'))

    def test_un_task_de_sistem_nu_iese_din_sistem(self):
        tid = self.task('Claude gata: X', sfera='sistem')
        for token in (FULL, DEVICE):
            for sfera in ('munca', 'personal'):
                r = self.client.put('/api/global-tasks/%s' % tid, json={'sfera': sfera, 'titlu': 'Altceva'},
                                    headers=self.h(token))
                self.assertEqual(r.status_code, 409, (token, sfera))
                self.assertEqual(r.get_json()['sfera'], 'sistem')
        g = self.client.get('/api/global-tasks/%s' % tid, headers=self.h()).get_json()
        self.assertEqual((g['sfera'], g['titlu']), ('sistem', 'Claude gata: X'), 'cererea refuzata nu scrie nimic')

    def test_un_put_fara_sfera_sau_cu_sistem_pe_un_task_de_sistem_trece(self):
        tid = self.task('Claude lucrează: X', sfera='sistem')
        for corp in ({'status': 'done'}, {'sfera': 'sistem', 'descriere': 'rezultat'}, {'sfera': None, 'descriere': 'iar'}):
            r = self.client.put('/api/global-tasks/%s' % tid, json=corp, headers=self.h())
            self.assertEqual(r.status_code, 200, corp)
        self.assertEqual(self.client.get('/api/global-tasks/%s' % tid, headers=self.h()).get_json()['sfera'], 'sistem')

    def test_un_task_de_sistem_se_poate_sterge(self):
        tid = self.task('Claude: ceva', sfera='sistem')
        self.assertEqual(self.client.delete('/api/global-tasks/%s' % tid, headers=self.h()).status_code, 200)

    def test_bifarea_unui_task_recurent_de_sistem_naste_urmatoarea_aparitie_tot_in_sistem(self):
        tid = self.task('Claude: cron', sfera='sistem', recurenta='zilnic', data_scadenta='2026-11-22')
        r = self.client.put('/api/global-tasks/%s' % tid, json={'status': 'done'}, headers=self.h())
        nou = r.get_json()['recurring_spawned']
        self.assertEqual(self.client.get('/api/global-tasks/%s' % nou, headers=self.h()).get_json()['sfera'], 'sistem')


class SistemulNuIeseLaTorqa(CuSistem):

    def snapshot(self, token=DEVICE):
        r = self.client.get('/api/sync/snapshot', headers=self.h(token))
        self.assertEqual(r.status_code, 200)
        return r.get_json()

    def test_snapshot_nu_are_taskurile_de_sistem_nici_subtaskurile_lor_nici_lista(self):
        self.amestec()
        for token in (DEVICE, FULL):
            d = self.snapshot(token)
            self.assertEqual(sorted(g['titlu'] for g in d['global_tasks']), ['Munca lui Ion', 'Personal al lui Ion'], token)
            self.assertEqual(d['subtasks'], [], 'subtaskurile unui task de sistem pleaca odata cu el')
            self.assertEqual([l['id'] for l in d['liste']], ['munca', 'personal'], token)
            self.assertNotIn('sistem', {g['sfera'] for g in d['global_tasks']})

    def test_snapshot_pastreaza_subtaskurile_taskurilor_lui_Ion(self):
        ion = self.task('Munca lui Ion', sfera='munca')
        c = sqlite3.connect(self.db)
        try:
            c.execute("INSERT INTO task_subtasks (id, task_id, titlu, done, ordine) VALUES ('s-ion', ?, 'pas', 0, 0)", (ion,))
            c.commit()
        finally:
            c.close()
        self.amestec()
        self.assertEqual([s['id'] for s in self.snapshot()['subtasks']], ['s-ion'])

    def test_un_task_mutat_in_sistem_dispare_din_snapshot(self):
        tid = self.task('Claude: ceva', sfera='munca')
        self.assertEqual([g['id'] for g in self.snapshot()['global_tasks']], [tid])
        self.client.put('/api/global-tasks/%s' % tid, json={'sfera': 'sistem'}, headers=self.h())
        self.assertEqual(self.snapshot()['global_tasks'], [])

    def test_calendarul_nu_are_taskurile_de_sistem(self):
        self.amestec()
        r = self.client.get('/api/calendar?start=2026-11-23&zile=7', headers=self.h(FULL))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([t['titlu'] for t in r.get_json()['taskuri'] if t['tip'] == 'global'], ['Munca lui Ion'])

    def test_deschise_din_liste_nu_numara_sistemul(self):
        self.amestec()
        r = self.client.get('/api/liste', headers=self.h(DEVICE))
        self.assertEqual([(l['id'], l['deschise']) for l in r.get_json()], [('munca', 1), ('personal', 1)])


class ListaSistemNuEUnaDeLaIon(CuSistem):

    def test_get_liste_nu_o_arata_nici_cu_un_rand_ajuns_acolo_de_mana(self):
        c = sqlite3.connect(self.db)
        try:
            c.execute("INSERT INTO liste (id, nume, iconita, ordine, fixa) VALUES ('sistem', 'Sistem', 'x', 9, 0)")
            c.commit()
        finally:
            c.close()
        try:
            r = self.client.get('/api/liste', headers=self.h(DEVICE))
            self.assertEqual([l['id'] for l in r.get_json()], ['munca', 'personal'])
            snap = self.client.get('/api/sync/snapshot', headers=self.h(DEVICE)).get_json()
            self.assertEqual([l['id'] for l in snap['liste']], ['munca', 'personal'])
        finally:
            c = sqlite3.connect(self.db)
            c.execute("DELETE FROM liste WHERE id = 'sistem'")
            c.commit()
            c.close()

    def test_nu_se_creeaza_o_lista_cu_id_sistem(self):
        r = self.client.post('/api/liste', json={'id': 'sistem', 'nume': 'Sistem', 'iconita': 'x'}, headers=self.h(DEVICE))
        self.assertEqual(r.status_code, 400)

    def test_nu_se_modifica_nu_se_sterge_nu_se_ordoneaza(self):
        for token in (DEVICE, FULL):
            r = self.client.put('/api/liste/sistem', json={'iconita': 'x'}, headers=self.h(token))
            self.assertEqual(r.status_code, 403, token)
            r = self.client.delete('/api/liste/sistem', headers=self.h(token))
            self.assertEqual(r.status_code, 403, token)
            r = self.client.put('/api/liste/ordine', json={'ids': ['sistem', 'munca', 'personal']}, headers=self.h(token))
            self.assertEqual(r.status_code, 400, token)
        self.assertEqual([l['id'] for l in self.client.get('/api/liste', headers=self.h()).get_json()], ['munca', 'personal'])

    def test_fara_token_401_pe_rutele_listei_de_sistem(self):
        self.assertEqual(self.client.put('/api/liste/sistem', json={}).status_code, 401)
        self.assertEqual(self.client.delete('/api/liste/sistem').status_code, 401)


if __name__ == '__main__':
    unittest.main()

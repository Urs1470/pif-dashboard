"""Garzile rutei de proiecte: id-ul din cale (stergerea) si `status` (frontmatter-ul din vault).

Ruta e deschisa si tokenului de dispozitiv (Torqa o cheama), deci ce intra prin `id` si `status`
trebuie sa fie sigur pentru sistemul de fisiere si pentru README-ul care se comite in Knowledge.
"""

import os
import unittest
from unittest import mock

from _aplicatia import CuAplicatia, DEVICE, FULL
import blueprints.obsidian as obsidian_module
import blueprints.projects as projects_module


class StergereaProiectului(CuAplicatia):
    """`DELETE /api/proiecte/<id>` sterge si `uploads/<id>`. Id-ul vine din cale si, la creare, din
    corpul cererii (oricine are un token poate pune `..`), deci dosarul se alege dupa regula din
    `dosar_de_incarcari`, iar un proiect care nu exista da 404 inainte de orice stergere. Torqa
    cheama ruta cu tokenul de dispozitiv si tine 404 drept „sters deja" — ramane deschisa lui."""

    def setUp(self):
        super().setUp()
        self.radacina = self.dir_temp()
        self.uploads = os.path.join(self.radacina, 'uploads')
        for rel in ('uploads/app/x.apk', 'uploads/torqa-web/current', 'in-afara.txt'):
            cale = os.path.join(self.radacina, *rel.split('/'))
            os.makedirs(os.path.dirname(cale), exist_ok=True)
            with open(cale, 'w', encoding='utf-8') as f:
                f.write('x')
        self.patch(projects_module, 'UPLOAD_FOLDER', self.uploads)

    def fisiere(self):
        return sorted(os.path.relpath(os.path.join(d, f), self.radacina).replace('\\', '/')
                      for d, _s, fs in os.walk(self.radacina) for f in fs)

    def proiect(self, pid):
        r = self.client.post('/api/proiecte', json={'id': pid, 'nume': 'T'}, headers=self.bearer())
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))

    def exista(self, pid):
        import database
        conn = database.get_db()
        try:
            return conn.execute('SELECT 1 FROM proiecte WHERE id = ?', (pid,)).fetchone() is not None
        finally:
            conn.close()

    def test_dosarul_proiectului_se_sterge_si_nimic_altceva(self):
        self.proiect('proiect-uuid-1')
        os.makedirs(os.path.join(self.uploads, 'proiect-uuid-1', 'sub'))
        with open(os.path.join(self.uploads, 'proiect-uuid-1', 'sub', 'f.pdf'), 'w') as f:
            f.write('x')
        inainte = self.fisiere()
        r = self.client.delete('/api/proiecte/proiect-uuid-1', headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertFalse(self.exista('proiect-uuid-1'))
        self.assertEqual(self.fisiere(), [x for x in inainte if 'proiect-uuid-1' not in x])

    def test_proiectul_necunoscut_da_404_si_nu_sterge_nimic(self):
        os.makedirs(os.path.join(self.uploads, 'fantoma'))
        inainte = self.fisiere()
        for token in (FULL, DEVICE):
            r = self.client.delete('/api/proiecte/fantoma', headers=self.bearer(token))
            self.assertEqual(r.status_code, 404, token)
        self.assertEqual(self.fisiere(), inainte)
        self.assertTrue(os.path.isdir(os.path.join(self.uploads, 'fantoma')))

    def test_dosarele_aplicatiei_nu_se_sterg_nici_cu_un_proiect_cu_numele_lor(self):
        inainte = self.fisiere()
        for pid in ('app', 'torqa-web', 'APP', 'Torqa-Web'):
            self.proiect(pid)
            r = self.client.delete('/api/proiecte/' + pid, headers=self.bearer(DEVICE))
            self.assertEqual(r.status_code, 200, pid)
            self.assertFalse(self.exista(pid), 'randul din baza se sterge oricum')
            self.assertEqual(self.fisiere(), inainte, pid)

    def test_id_cu_puncte_nu_ajunge_la_sistemul_de_fisiere(self):
        inainte = self.fisiere()
        for codat in ('%2e%2e', '%2e', '..', '.'):
            self.proiect(codat.replace('%2e', '.'))
            r = self.client.delete('/api/proiecte/' + codat, headers=self.bearer(DEVICE))
            self.assertIn(r.status_code, (200, 404), codat)
            self.assertEqual(self.fisiere(), inainte, codat)
        self.assertTrue(os.path.isdir(self.radacina))

    def test_regula_dosarului(self):
        baza = os.path.realpath(self.uploads)
        for bun in ('x', 'proiect-uuid-1', '3f2b8c1e-aaaa-bbbb-cccc-000000000001', 'A_b-9', 'a' * 64):
            self.assertEqual(projects_module.dosar_de_incarcari(bun), os.path.join(baza, bun), bun)
        for rau in ('', '.', '..', '...', '../x', 'a/b', 'a\\b', '/etc', 'C:\\x', 'a b', 'a\n',
                    'x\x00y', 'app', 'APP', 'torqa-web', 'a' * 65, None, 5, ['x']):
            self.assertIsNone(projects_module.dosar_de_incarcari(rau), repr(rau))


class StatusulProiectului(CuAplicatia):
    """`status` din corp ajunge in baza si, prin `sync_project_frontmatter`, in README-ul din vault
    (care se comite si se impinge in Knowledge). Ruta il accepta si cu tokenul de dispozitiv, deci
    primeste doar cele doua valori ale invariantului 2 (cheile vechi din `labels.py` se strang in
    `pregatire`); orice altceva e 400 si nu atinge baza."""

    RAU = ['x\n---\ninjectat: da', 'finalizat\nvault_folder: x', 'bogus', '', ' ', 123, True, ['finalizat'],
           {'a': 1}, 'PREGATIRE', 'final\u0131zat']

    def proiect(self, **camp):
        r = self.client.post('/api/proiecte', json={'nume': 'T', **camp}, headers=self.bearer())
        return r

    def status_in_baza(self, pid):
        import database
        conn = database.get_db()
        try:
            return conn.execute('SELECT status FROM proiecte WHERE id = ?', (pid,)).fetchone()['status']
        finally:
            conn.close()

    def test_put_cu_status_necunoscut_da_400_si_nu_schimba_nimic(self):
        pid = self.proiect().get_json()['id']
        for token in (FULL, DEVICE):
            for rau in self.RAU:
                r = self.client.put('/api/proiecte/' + pid, json={'status': rau}, headers=self.bearer(token))
                self.assertEqual(r.status_code, 400, repr(rau))
                self.assertIn('error', r.get_json())
        self.assertEqual(self.status_in_baza(pid), 'pregatire')

    def test_put_cu_statusurile_cunoscute(self):
        pid = self.proiect().get_json()['id']
        r = self.client.put('/api/proiecte/' + pid, json={'status': 'finalizat'}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.status_in_baza(pid), 'finalizat')
        r = self.client.put('/api/proiecte/' + pid, json={'status': 'in_lucru'}, headers=self.bearer())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.status_in_baza(pid), 'pregatire', 'cheia veche se strange in pregatire')
        r = self.client.put('/api/proiecte/' + pid, json={'status': ' pregatire '}, headers=self.bearer())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.status_in_baza(pid), 'pregatire')

    def test_put_fara_status_nu_cere_status(self):
        pid = self.proiect().get_json()['id']
        r = self.client.put('/api/proiecte/' + pid, json={'nume': 'Nou'}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200)
        r = self.client.put('/api/proiecte/' + pid, json={'nume': 'Nou', 'status': None}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, 'null = nu schimba statusul, ca pana acum')

    def test_post_cu_status_necunoscut_da_400(self):
        for rau in self.RAU + [None]:
            self.assertEqual(self.proiect(status=rau).status_code, 400, repr(rau))

    def test_post_cu_statusurile_cunoscute(self):
        self.assertEqual(self.status_in_baza(self.proiect().get_json()['id']), 'pregatire')
        r = self.proiect(status='finalizat')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.status_in_baza(r.get_json()['id']), 'finalizat')
        r = self.proiect(status='in_lucru')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.status_in_baza(r.get_json()['id']), 'pregatire')

    def test_frontmatter_ul_nu_primeste_linii_in_plus(self):
        # Plasa a doua, pentru o valoare care ar ajunge totusi acolo (un rand vechi din baza).
        vault = self.dir_temp()
        os.makedirs(os.path.join(vault, 'p'))
        readme = os.path.join(vault, 'p', 'README.md')
        with open(readme, 'w', encoding='utf-8', newline='\n') as f:
            f.write('---\nstatus: pregatire\nnume: T\n---\n# T\n')
        import database
        conn = database.get_db()
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?)",
                     (obsidian_module.OBSIDIAN_SETTING_KEY, vault))
        conn.commit()
        conn.close()

        class Sincron:
            def __init__(self, target=None, **_k):
                self.target = target

            def start(self):
                self.target()

        with mock.patch.object(obsidian_module.threading, 'Thread', Sincron):
            obsidian_module.sync_project_frontmatter(
                'p', {'status': 'finalizat\n---\nvault_folder: wiki/personal\r\nx:\u2028y'})
        with open(readme, encoding='utf-8') as f:
            rez = f.read()
        self.assertEqual(rez.split('\n')[:4], ['---', 'status: finalizat --- vault_folder: wiki/personal x: y',
                                               'nume: T', '---'])
        self.assertEqual(rez.count('---'), 3, rez)


if __name__ == '__main__':
    unittest.main()

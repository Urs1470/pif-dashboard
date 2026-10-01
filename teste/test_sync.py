"""Imaginea pentru Torqa (/api/sync/snapshot) si tokenul de dispozitiv.

Doua lucruri pazite aici, amandoua tacute daca se strica:
  - imaginea e INTREAGA: ce lipseste din ea, Torqa sterge local. Un task scapat din
    imagine dispare de pe telefon fara nicio eroare.
  - tokenul de dispozitiv NU deschide restore, backup, admin, deploy, upload de APK si
    cheia vault-ului. Un telefon pierdut nu trebuie sa poata inlocui sau descarca baza.
"""

import os

from _baza import CuBazaNoua

FULL = 'token-masina-test'
DEVICE = 'token-dispozitiv-test'


class ImagineaSiTokenul(CuBazaNoua):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._env = {k: os.environ.get(k) for k in ('PIF_API_TOKEN', 'PIF_DEVICE_TOKEN', 'PIF_RATE_LIMIT')}
        os.environ['PIF_API_TOKEN'] = FULL
        os.environ['PIF_DEVICE_TOKEN'] = DEVICE
        import app as app_module
        # Schema o scrie deja CuBazaNoua; primul request ar porni si planificatorul de
        # notificari (thread), care n-are ce cauta intr-un test.
        app_module._startup_initialized = True
        cls.client = app_module.app.test_client()

        import database
        conn = database.get_db()
        c = conn.cursor()
        c.execute("INSERT INTO proiecte (id, tip, nume, status) VALUES ('p-des', 'PIF', 'Deschis', 'pregatire')")
        c.execute("INSERT INTO proiecte (id, tip, nume, status, data_finalizare) "
                  "VALUES ('p-inc', 'PIF', 'Inchis', 'finalizat', '2026-09-01')")
        c.execute("INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta, recurenta, created_at) "
                  "VALUES ('t1', 'p-des', 'Parametrizare', 'to_do', '2026-10-02', 'saptamanal', '2026-09-30')")
        c.execute("INSERT INTO tasks (id, proiect_id, titlu, status, created_at) "
                  "VALUES ('t2', 'p-inc', 'Vechi', 'done', '2026-08-01')")
        c.execute("INSERT INTO tasks (id, proiect_id, titlu, status, created_at) "
                  "VALUES ('t3', 'p-inc', 'Dupa inchidere', 'to_do', '2026-09-30')")
        c.execute("INSERT INTO task_subtasks (id, task_id, titlu, done, ordine) VALUES ('s1', 't1', 'Rampe', 1, 0)")
        c.execute("INSERT INTO global_tasks (id, titlu, status, sfera, ora) VALUES ('g1', 'Raport', 'to_do', 'munca', '')")
        c.execute("INSERT INTO global_tasks (id, titlu, status, sfera, ora) VALUES ('g2', 'Sala', 'done', 'personal', '07:30')")
        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDownClass()

    def get(self, path, token=None):
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        return self.client.get(path, headers=headers)

    def post(self, path, token=None):
        headers = {'Authorization': f'Bearer {token}'} if token else {}
        return self.client.post(path, headers=headers)

    def test_fara_token_401(self):
        self.assertEqual(self.get('/api/sync/snapshot').status_code, 401)
        self.assertEqual(self.get('/api/sync/snapshot', token='gresit').status_code, 401)

    def test_imaginea_e_intreaga(self):
        r = self.get('/api/sync/snapshot', token=DEVICE)
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual({p['id'] for p in d['proiecte']}, {'p-des', 'p-inc'})
        # Toate taskurile, si cele facute (orfani nu exista: cheia straina e activa).
        self.assertEqual({t['id'] for t in d['tasks']}, {'t1', 't2', 't3'})
        self.assertEqual([s['id'] for s in d['subtasks']], ['s1'])
        self.assertEqual({g['id'] for g in d['global_tasks']}, {'g1', 'g2'}, 'si cele facute, din ambele sfere')
        self.assertTrue(d['server_time'])

    def test_campurile_de_care_are_nevoie_torqa(self):
        d = self.get('/api/sync/snapshot', token=DEVICE).get_json()
        t1 = next(t for t in d['tasks'] if t['id'] == 't1')
        for camp in ('proiect_id', 'titlu', 'descriere', 'status', 'data_scadenta', 'recurenta',
                     'ordine', 'ordine_agenda', 'updated_at', 'viu'):
            self.assertIn(camp, t1)
        self.assertEqual(t1['recurenta'], 'saptamanal')
        g2 = next(g for g in d['global_tasks'] if g['id'] == 'g2')
        self.assertEqual((g2['sfera'], g2['ora']), ('personal', '07:30'))

    def test_viu_urmeaza_regula_din_astazi(self):
        d = self.get('/api/sync/snapshot', token=DEVICE).get_json()
        viu = {t['id']: t['viu'] for t in d['tasks']}
        self.assertEqual(viu['t1'], 1, 'proiect deschis')
        self.assertEqual(viu['t2'], 0, 'proiect inchis, task de dinainte')
        self.assertEqual(viu['t3'], 1, 'nascut dupa inchidere')

    def test_tokenul_de_masina_merge_si_el(self):
        self.assertEqual(self.get('/api/sync/snapshot', token=FULL).status_code, 200)

    def test_tokenul_de_dispozitiv_deschide_rutele_de_lucru(self):
        self.assertEqual(self.get('/api/global-tasks?sfera=toate', token=DEVICE).status_code, 200)
        self.assertEqual(self.get('/api/proiecte/p-des/tasks', token=DEVICE).status_code, 200)

    def test_tokenul_de_dispozitiv_nu_atinge_baza_codul_sau_apk_ul(self):
        # Pe functia de verificare, nu pe rute: daca garda ar fi stricata, /api/deploy ar
        # rula `git reset --hard` chiar pe clona din care ruleaza testul.
        import app as app_module
        from utils import _check_api_token
        for metoda, ruta in [('GET', '/api/backup'), ('POST', '/api/restore'),
                             ('GET', '/api/admin/db-dump'), ('POST', '/api/admin/db-upload'),
                             ('GET', '/admin/db-upload'), ('POST', '/api/deploy'),
                             ('POST', '/api/app/upload'), ('POST', '/api/obsidian/vault-key'),
                             ('POST', '/api/obsidian/vault-sync')]:
            for token, asteptat in ((DEVICE, False), (FULL, True)):
                with app_module.app.test_request_context(
                        ruta, method=metoda, headers={'Authorization': f'Bearer {token}'}):
                    self.assertIs(_check_api_token(), asteptat, f'{metoda} {ruta} cu {token}')

    def test_rutele_de_citire_a_bazei_raspund_401_dispozitivului(self):
        # Doar rute care citesc: daca garda ar ceda, raspunsul ar fi baza, nu o actiune.
        for ruta in ('/api/backup', '/api/admin/db-dump'):
            self.assertEqual(self.get(ruta, token=DEVICE).status_code, 401, ruta)

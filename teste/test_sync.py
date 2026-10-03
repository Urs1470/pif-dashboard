"""Imaginea pentru Torqa (/api/sync/snapshot) si tokenul de dispozitiv.

Trei lucruri pazite aici, toate tacute daca se strica:
  - imaginea e INTREAGA: ce lipseste din ea, Torqa sterge local. Un task scapat din
    imagine dispare de pe telefon fara nicio eroare.
  - tokenul de dispozitiv NU deschide restore, backup, admin, deploy, upload de APK si
    cheia vault-ului. Un telefon pierdut nu trebuie sa poata inlocui sau descarca baza.
  - nici vault-ul: dispozitivul citeste doar notele din `vault_folder` al unui proiect (ce
    citeste butonul Wiki din Torqa) si nu scrie nicio nota. Restul vault-ului tine nota cu
    tokenul de masina si PIN-ul, iar PUT-ul impinge in repo-ul Knowledge cu cheia de scriere.
"""

import os

from _aplicatia import CuAplicatia
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
        # Schema o scrie deja CuBazaNoua; primul request n-are de ce s-o refaca (init_db) si
        # sa logheze o pornire a aplicatiei.
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
        # Si taskurile globale au subtaskuri (pe server, 2026-10-01: 7, pe doua globale).
        c.execute("INSERT INTO task_subtasks (id, task_id, titlu, done, ordine) VALUES ('s2', 'g1', 'Anexa', 0, 0)")
        c.execute("INSERT INTO task_subtasks (id, task_id, titlu, done, ordine) VALUES ('s3', 'nimeni', 'Orfan', 0, 0)")
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
        self.assertEqual({s['id'] for s in d['subtasks']}, {'s1', 's2'}, 'si ale globalelor, fara orfani')
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
                             ('POST', '/api/obsidian/vault-sync'),
                             # Nota din vault se SCRIE doar cu tokenul de masina (sau PIN): regula
                             # depinde de metoda, nu doar de cale.
                             ('PUT', '/api/obsidian/note'), ('POST', '/api/obsidian/note'),
                             ('DELETE', '/api/obsidian/note'), ('PATCH', '/api/obsidian/note')]:
            for token, asteptat in ((DEVICE, False), (FULL, True)):
                with app_module.app.test_request_context(
                        ruta, method=metoda, headers={'Authorization': f'Bearer {token}'}):
                    self.assertIs(_check_api_token(), asteptat, f'{metoda} {ruta} cu {token}')

    def test_dispozitivul_citeste_notele_dar_nu_le_scrie(self):
        # Garda de token lasa citirea sa treaca; ce nota se poate citi hotaraste ruta
        # (`NoteleDinVaultSiDispozitivul`). Doar PUT si celelalte scrieri sunt oprite aici.
        import app as app_module
        from utils import _check_api_token, device_token_denied
        for metoda in ('GET', 'HEAD', 'OPTIONS'):
            with app_module.app.test_request_context(
                    '/api/obsidian/note?path=a.md', method=metoda,
                    headers={'Authorization': f'Bearer {DEVICE}'}):
                self.assertIs(_check_api_token(), True, metoda)
        for metoda in ('PUT', 'POST', 'DELETE', 'PATCH'):
            self.assertTrue(device_token_denied(metoda, '/api/obsidian/note'), metoda)
        self.assertFalse(device_token_denied('GET', '/api/obsidian/note'))
        # Lista notelor unui proiect si restul API-ului de lucru nu sunt atinse de regula.
        for metoda, ruta in (('GET', '/api/proiecte/p-des/wiki'), ('PUT', '/api/proiecte/p-des'),
                             ('PUT', '/api/tasks/t1')):
            self.assertFalse(device_token_denied(metoda, ruta), f'{metoda} {ruta}')

    def test_rutele_de_citire_a_bazei_raspund_401_dispozitivului(self):
        # Doar rute care citesc: daca garda ar ceda, raspunsul ar fi baza, nu o actiune.
        for ruta in ('/api/backup', '/api/admin/db-dump'):
            self.assertEqual(self.get(ruta, token=DEVICE).status_code, 401, ruta)


class CreareaCuIdDeLaDispozitiv(CuBazaNoua):
    """Torqa creeaza cu id-ul facut pe dispozitiv. Daca raspunsul se pierde pe drum, cererea
    se repeta: a doua trebuie sa spuna „exista deja" (409), nu sa dubleze si nici sa cada cu
    500 din cheia primara, altfel taskul ramane nesincronizat pentru totdeauna."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._env = {k: os.environ.get(k) for k in ('PIF_API_TOKEN', 'PIF_DEVICE_TOKEN')}
        os.environ['PIF_API_TOKEN'] = FULL
        os.environ['PIF_DEVICE_TOKEN'] = DEVICE
        import app as app_module
        app_module._startup_initialized = True
        cls.client = app_module.app.test_client()
        import database
        conn = database.get_db()
        conn.execute("INSERT INTO proiecte (id, tip, nume, status) VALUES ('p1', 'PIF', 'Deschis', 'pregatire')")
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

    def post(self, path, body):
        return self.client.post(path, json=body, headers={'Authorization': f'Bearer {DEVICE}'})

    def imagine(self):
        return self.client.get('/api/sync/snapshot', headers={'Authorization': f'Bearer {DEVICE}'}).get_json()

    def test_task_de_proiect_a_doua_oara_409(self):
        r = self.post('/api/proiecte/p1/tasks', {'id': 'tx', 'titlu': 'Primul'})
        self.assertEqual((r.status_code, r.get_json()['id']), (201, 'tx'))
        r = self.post('/api/proiecte/p1/tasks', {'id': 'tx', 'titlu': 'Repetat'})
        self.assertEqual((r.status_code, r.get_json()['id']), (409, 'tx'))
        titluri = [t['titlu'] for t in self.imagine()['tasks'] if t['id'] == 'tx']
        self.assertEqual(titluri, ['Primul'], 'nici dublat, nici suprascris')

    def test_task_in_proiect_inexistent_404(self):
        r = self.post('/api/proiecte/sters/tasks', {'id': 'ty', 'titlu': 'Orfan'})
        self.assertEqual(r.status_code, 404)

    def test_global_a_doua_oara_409(self):
        self.assertEqual(self.post('/api/global-tasks', {'id': 'gx', 'titlu': 'Raport'}).status_code, 201)
        r = self.post('/api/global-tasks', {'id': 'gx', 'titlu': 'Raport'})
        self.assertEqual((r.status_code, r.get_json()['id']), (409, 'gx'))
        self.assertEqual(sum(1 for g in self.imagine()['global_tasks'] if g['id'] == 'gx'), 1)

    def test_subtask_primeste_id_si_parinte_global(self):
        self.assertEqual(self.post('/api/global-tasks', {'id': 'gp', 'titlu': 'Cu pasi'}).status_code, 201)
        r = self.post('/api/tasks/gp/subtasks', {'id': 'sx', 'titlu': 'Pas'})
        self.assertEqual((r.status_code, r.get_json()['id']), (201, 'sx'))
        r = self.post('/api/tasks/gp/subtasks', {'id': 'sx', 'titlu': 'Pas'})
        self.assertEqual((r.status_code, r.get_json()['id']), (409, 'sx'))
        self.assertEqual([s['task_id'] for s in self.imagine()['subtasks'] if s['id'] == 'sx'], ['gp'])

    def test_subtask_fara_id_merge_ca_inainte(self):
        self.assertEqual(self.post('/api/proiecte/p1/tasks', {'id': 'tz', 'titlu': 'Parinte'}).status_code, 201)
        r = self.post('/api/tasks/tz/subtasks', {'titlu': 'Din SPA'})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.get_json()['id'])

    def test_subtask_cu_parinte_inexistent_404(self):
        self.assertEqual(self.post('/api/tasks/nimeni/subtasks', {'id': 'so', 'titlu': 'Orfan'}).status_code, 404)

    # Torqa creeaza si proiecte si perioade (2026-10-02): aceeasi regula, acelasi raspuns.
    def test_proiect_a_doua_oara_409(self):
        r = self.post('/api/proiecte', {'id': 'px', 'nume': 'Primul', 'tip': 'PIF'})
        self.assertEqual((r.status_code, r.get_json()['id']), (201, 'px'))
        r = self.post('/api/proiecte', {'id': 'px', 'nume': 'Repetat', 'tip': 'PIF'})
        self.assertEqual((r.status_code, r.get_json()['id']), (409, 'px'))
        nume = [p['nume'] for p in self.imagine()['proiecte'] if p['id'] == 'px']
        self.assertEqual(nume, ['Primul'], 'nici dublat, nici suprascris')

    def test_proiect_fara_id_merge_ca_inainte(self):
        r = self.post('/api/proiecte', {'nume': 'Din SPA', 'tip': 'Service'})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.get_json()['id'])

    def test_perioada_a_doua_oara_409(self):
        corp = {'id': 'ix', 'data_start': '2026-10-05', 'data_sfarsit': '2026-10-07', 'faza': 'implementare'}
        r = self.post('/api/proiecte/p1/implementari', corp)
        self.assertEqual((r.status_code, r.get_json()['id']), (201, 'ix'))
        r = self.post('/api/proiecte/p1/implementari', dict(corp, data_start='2026-10-06'))
        self.assertEqual((r.status_code, r.get_json()['id']), (409, 'ix'))
        perioade = self.client.get('/api/proiecte/p1/implementari',
                                   headers={'Authorization': f'Bearer {DEVICE}'}).get_json()
        self.assertEqual([p['data_start'] for p in perioade if p['id'] == 'ix'], ['2026-10-05'])

    def test_perioada_in_proiect_inexistent_404(self):
        r = self.post('/api/proiecte/sters/implementari', {'id': 'iy', 'data_start': '2026-10-05'})
        self.assertEqual(r.status_code, 404)


# ====================================================== notele din vault si dispozitivul

# Vault-ul de proba. Dosarul `pompa` e al proiectului `p-pompa`; restul nu apartine niciunui
# proiect. `Secrete.md` e stand-in pentru nota care tine tokenul de masina si PIN-ul.
NOTE_VAULT = {
    'wiki/job/projects/acme/pompa/README.md': 'Pompa: README',
    'wiki/job/projects/acme/pompa/sub/pas.md': 'Pompa: un pas',
    'wiki/job/projects/acme/pompa/.trash/sterse.md': 'Pompa: stearsa',
    'wiki/job/projects/acme/pompa-vecina/README.md': 'Alt dosar, acelasi prefix',
    'wiki/job/projects/acme/fara-proiect/README.md': 'Dosar fara proiect',
    'wiki/job/projects/acme/dos-win/n.md': 'Dosar scris cu backslash',
    'wiki/personal/Tehnologie/Secrete.md': 'token-masina-inchipuit si PIN-inchipuit',
    'README.md': 'Radacina vault-ului',
}
PROIECTE_VAULT = (
    ('p-pompa', 'wiki/job/projects/acme/pompa'),
    ('p-fara', ''),                                          # fara dosar de vault
    ('p-radacina', '.'),                                     # arata spre radacina: nu deschide nimic
    ('p-lipsa', 'wiki/job/projects/acme/nu-exista'),         # dosar absent din copia asta a vault-ului
    ('p-win', 'wiki\\job\\projects\\acme\\dos-win\\'),       # backslash si slash la coada
)
INAUNTRU = 'wiki/job/projects/acme/pompa/README.md'
AFARA = 'wiki/personal/Tehnologie/Secrete.md'


class NoteleDinVaultSiDispozitivul(CuAplicatia):
    """`GET /api/obsidian/note` cu tokenul de dispozitiv: doar notele dintr-un `vault_folder` de
    proiect, adica exact ce deschide butonul Wiki din Torqa (lista vine de la
    `/api/proiecte/<id>/wiki`). Orice altceva da 403 — la fel pentru o nota care exista si pentru
    una care nu, ca dispozitivul sa nu poata deduce ce fisiere are vault-ul. `PUT` e refuzat
    dispozitivului (401, ca restul listei); tokenul de masina si sesiunea cu PIN raman netinute
    in loc."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import database
        conn = database.get_db()
        for pid, folder in PROIECTE_VAULT:
            conn.execute("INSERT INTO proiecte (id, tip, nume, status, vault_folder) "
                         "VALUES (?, 'PIF', ?, 'pregatire', ?)", (pid, pid, folder))
        conn.commit()
        conn.close()

    def setUp(self):
        super().setUp()
        self.vault = os.path.join(self.dir_temp(), 'vault')
        for rel, continut in NOTE_VAULT.items():
            cale = os.path.join(self.vault, *rel.split('/'))
            os.makedirs(os.path.dirname(cale), exist_ok=True)
            with open(cale, 'w', encoding='utf-8', newline='') as fh:
                fh.write(continut)
        from utils import set_app_setting
        set_app_setting('obsidian_vault_path', self.vault)

    def nota(self, path, token=DEVICE):
        return self.client.get('/api/obsidian/note', query_string={'path': path}, headers=self.bearer(token))

    def scrie(self, path, continut='SCRIS', token=DEVICE):
        return self.client.put('/api/obsidian/note', json={'path': path, 'content': continut},
                               headers=self.bearer(token))

    def pe_disc(self, rel):
        with open(os.path.join(self.vault, *rel.split('/')), encoding='utf-8', newline='') as fh:
            return fh.read()

    # ------------------------------------------------------------- citirea, dispozitiv

    def test_nota_din_dosarul_unui_proiect_se_citeste(self):
        r = self.nota(INAUNTRU)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        corp = r.get_json()
        self.assertEqual((corp['path'], corp['title'], corp['content']), (INAUNTRU, 'README', 'Pompa: README'))
        self.assertEqual(self.nota('wiki/job/projects/acme/pompa/sub/pas.md').get_json()['content'], 'Pompa: un pas')

    def test_forma_caii_nu_conteaza_cat_timp_nota_e_inauntru(self):
        for forma in ('/' + INAUNTRU, INAUNTRU.replace('/', '\\'),
                      'wiki/job/projects/acme/pompa/sub/../README.md',
                      'wiki/job/projects/acme/./pompa/README.md'):
            with self.subTest(cale=forma):
                self.assertEqual(self.nota(forma).status_code, 200)

    def test_dosarul_din_proiect_scris_cu_backslash_se_potriveste(self):
        self.assertEqual(self.nota('wiki/job/projects/acme/dos-win/n.md').status_code, 200)

    def test_orice_alta_nota_din_vault_da_403(self):
        for path in (AFARA, 'README.md', 'wiki/job/projects/acme/fara-proiect/README.md'):
            with self.subTest(cale=path):
                r = self.nota(path)
                self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
                self.assertNotIn('inchipuit', r.get_data(as_text=True), 'corpul 403 nu poarta nota')

    def test_un_dosar_frate_cu_acelasi_prefix_nu_trece(self):
        # `pompa-vecina` incepe cu `pompa`: o comparatie pe text ar lasa-o sa treaca.
        self.assertEqual(self.nota('wiki/job/projects/acme/pompa-vecina/README.md').status_code, 403)

    def test_iesirea_din_dosar_prin_puncte_nu_trece(self):
        for path in ('wiki/job/projects/acme/pompa/../../../../personal/Tehnologie/Secrete.md',
                     'wiki\\job\\projects\\acme\\pompa\\..\\..\\..\\..\\personal\\Tehnologie\\Secrete.md',
                     'wiki/job/projects/acme/pompa/../pompa-vecina/README.md'):
            with self.subTest(cale=path):
                self.assertEqual(self.nota(path).status_code, 403)
        # In afara vault-ului nici macar nu e o nota: 404, ca pentru oricine.
        for path in ('../afara.md', 'wiki/../../afara.md', os.path.join(os.path.dirname(self.vault), 'afara.md')):
            with self.subTest(cale=path):
                self.assertEqual(self.nota(path).status_code, 404)

    def test_o_legatura_simbolica_din_dosar_spre_afara_nu_trece(self):
        legatura = os.path.join(self.vault, 'wiki', 'job', 'projects', 'acme', 'pompa', 'scapare.md')
        try:
            os.symlink(os.path.join(self.vault, *AFARA.split('/')), legatura)
        except (OSError, NotImplementedError):
            self.skipTest('legaturile simbolice cer drepturi pe masina asta')
        self.assertEqual(self.nota('wiki/job/projects/acme/pompa/scapare.md').status_code, 403)

    def test_dosarele_ascunse_din_proiect_nu_se_citesc(self):
        # Lista Wiki le sare (`project_wiki_notes`), deci nici citirea nu le da.
        self.assertEqual(self.nota('wiki/job/projects/acme/pompa/.trash/sterse.md').status_code, 403)

    def test_un_proiect_cu_vault_folder_pe_radacina_nu_deschide_vault_ul(self):
        # `p-radacina` are vault_folder='.': tot vault-ul ar parea „inauntru". Nu e un proiect.
        self.assertEqual(self.nota(AFARA).status_code, 403)
        self.assertEqual(self.nota('README.md').status_code, 403)

    def test_403_si_404_nu_arata_ce_fisiere_are_vault_ul(self):
        # In afara dosarelor de proiect raspunsul e acelasi, exista nota sau nu.
        self.assertEqual(self.nota('wiki/personal/Tehnologie/Nu-exista.md').status_code, 403)
        self.assertEqual(self.nota(AFARA).status_code, 403)
        # In dosar, o nota lipsa e 404 obisnuit.
        self.assertEqual(self.nota('wiki/job/projects/acme/pompa/nu-exista.md').status_code, 404)

    def test_ce_listeaza_butonul_wiki_se_si_citeste(self):
        r = self.client.get('/api/proiecte/p-pompa/wiki', headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200)
        note = r.get_json()['notes']
        self.assertEqual({n['path'] for n in note},
                         {INAUNTRU, 'wiki/job/projects/acme/pompa/sub/pas.md'}, 'lista sare folderul ascuns')
        for n in note:
            with self.subTest(nota=n['path']):
                self.assertEqual(self.nota(n['path']).status_code, 200)

    def test_vault_neconfigurat_ramane_400(self):
        from utils import set_app_setting
        set_app_setting('obsidian_vault_path', os.path.join(self.vault, 'nu-exista'))
        self.assertEqual(self.nota(INAUNTRU).status_code, 400)

    # ----------------------------------------------- tokenul de masina si sesiunea cu PIN

    def test_tokenul_de_masina_citeste_orice_nota(self):
        for path in (INAUNTRU, AFARA, 'README.md'):
            with self.subTest(cale=path):
                self.assertEqual(self.nota(path, token=FULL).status_code, 200)
        self.assertEqual(self.nota('wiki/personal/nu-exista.md', token=FULL).status_code, 404)

    def test_sesiunea_cu_pin_citeste_orice_nota(self):
        self.assertEqual(self.login().status_code, 200)
        for path in (INAUNTRU, AFARA, 'README.md'):
            with self.subTest(cale=path):
                r = self.client.get('/api/obsidian/note', query_string={'path': path})
                self.assertEqual(r.status_code, 200)

    # ---------------------------------------------------------------- scrierea (PUT)

    def test_dispozitivul_nu_scrie_nicio_nota(self):
        # In dosarul unui proiect, in afara lui, sau una care nu exista: tot 401, ca restul listei.
        for path in (INAUNTRU, AFARA, 'wiki/job/projects/acme/pompa/nu-exista.md'):
            with self.subTest(cale=path):
                r = self.scrie(path)
                self.assertEqual(r.status_code, 401, r.get_data(as_text=True))
                self.assertEqual(r.get_json(), {'error': 'Unauthorized'})
        self.assertEqual(self.pe_disc(INAUNTRU), 'Pompa: README', 'nimic nu s-a scris')
        self.assertEqual(self.pe_disc(AFARA), NOTE_VAULT[AFARA])
        self.assertFalse(os.path.exists(os.path.join(self.vault, 'wiki', 'job', 'projects', 'acme', 'pompa',
                                                     'nu-exista.md')))

    def test_dispozitivul_nu_scrie_nici_cu_alta_metoda(self):
        for metoda in ('post', 'delete', 'patch'):
            with self.subTest(metoda=metoda):
                r = getattr(self.client, metoda)('/api/obsidian/note', json={'path': INAUNTRU, 'content': 'x'},
                                                 headers=self.bearer(DEVICE))
                self.assertIn(r.status_code, (401, 405))
        self.assertEqual(self.pe_disc(INAUNTRU), 'Pompa: README')

    def test_tokenul_de_masina_scrie_nota(self):
        r = self.scrie(INAUNTRU, 'Pompa: editata', token=FULL)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertTrue(r.get_json()['saved'])
        self.assertEqual(self.pe_disc(INAUNTRU), 'Pompa: editata')
        # Si in afara dosarelor de proiect: restrictia e a dispozitivului, nu a rutei.
        self.assertEqual(self.scrie(AFARA, 'si asta', token=FULL).status_code, 200)
        self.assertEqual(self.pe_disc(AFARA), 'si asta')

    def test_sesiunea_cu_pin_scrie_nota(self):
        self.assertEqual(self.login().status_code, 200)
        self.client.get('/api/stats')                       # cookie-ul csrf apare pe un raspuns autentificat
        token = self.client.get_cookie('csrf_token').value
        r = self.client.put('/api/obsidian/note', json={'path': INAUNTRU, 'content': 'Pompa: din sesiune'},
                            headers={'X-CSRF-Token': token})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.pe_disc(INAUNTRU), 'Pompa: din sesiune')

    # ------------------------------------------ `vault_folder`: cheia regulii de mai sus

    def vault_folder(self, pid):
        import database
        conn = database.get_db()
        try:
            row = conn.execute('SELECT vault_folder FROM proiecte WHERE id = ?', (pid,)).fetchone()
            return row['vault_folder'] if row else None
        finally:
            conn.close()

    def test_dispozitivul_nu_muta_dosarul_unui_proiect_ca_sa_citeasca_altceva(self):
        # Ocolul gasit la curatenie: PUT pe proiect cu alt dosar, apoi GET pe o nota de acolo.
        r = self.client.put('/api/proiecte/p-pompa', json={'vault_folder': 'wiki/personal'},
                            headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        self.assertEqual(self.vault_folder('p-pompa'), 'wiki/job/projects/acme/pompa')
        self.assertEqual(self.nota(AFARA).status_code, 403)
        # Nici impreuna cu un camp permis: cererea se refuza intreaga, nu pe jumatate.
        r = self.client.put('/api/proiecte/p-fara', json={'nume': 'Alt nume', 'vault_folder': 'wiki'},
                            headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.vault_folder('p-fara'), '')

    def test_dispozitivul_nu_creeaza_proiect_cu_dosar_de_vault(self):
        r = self.client.post('/api/proiecte', json={'id': 'p-nou-dispozitiv', 'tip': 'PIF', 'nume': 'Nou',
                                                    'vault_folder': 'wiki/personal'},
                             headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))
        self.assertIsNone(self.vault_folder('p-nou-dispozitiv'), 'proiectul nu s-a creat')

    def test_dispozitivul_nu_importa_debrief_cu_dosar_de_vault(self):
        r = self.client.post('/api/import/debrief',
                             json={'proiect': {'nume': 'Debrief dispozitiv', 'vault_folder': 'wiki/personal'}},
                             headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 403, r.get_data(as_text=True))

    def test_dispozitivul_editeaza_proiectul_fara_dosar_ca_inainte(self):
        # Ce trimite Torqa (fara `vault_folder`) trece ca pana acum.
        r = self.client.put('/api/proiecte/p-lipsa', json={'locatie': 'Iasi'}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.vault_folder('p-lipsa'), 'wiki/job/projects/acme/nu-exista')

    def test_tokenul_de_masina_seteaza_dosarul_ca_inainte(self):
        # `pif-sync.py link` scrie `vault_folder` cu tokenul de masina; regula e a dispozitivului.
        try:
            r = self.client.put('/api/proiecte/p-fara', json={'vault_folder': 'wiki/job/projects/acme/dos-win'},
                                headers=self.bearer(FULL))
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self.assertEqual(self.vault_folder('p-fara'), 'wiki/job/projects/acme/dos-win')
        finally:
            import database
            conn = database.get_db()
            conn.execute("UPDATE proiecte SET vault_folder = '' WHERE id = 'p-fara'")
            conn.commit()
            conn.close()

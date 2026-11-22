"""Contractul `/api/asistent` v1: registrul, actiunile, firul si tokenurile push.

Ce se pazeste, tacut daca se strica:
  - registrul: un corp care iese din contract da 400 cu calea campului si NU atinge registrul curent;
    `generat` mai vechi da 409; aceeasi cerere de doua ori lasa acelasi fisier; niciun `.tmp` ramas;
  - `GET /api/asistent` arata doar itemii activi (nou, vazut, amanat cu termenul trecut); gata,
    ignorat, la_claude si amanat in viitor raman ascunse; fara registru: `generat = null`, `items = []`;
  - tokenul de DISPOZITIV primeste 403 pe cele sase rute ale asistentului (inclusiv `cine=asistent` pe
    `POST /fir`) si trece pe rutele Torqa; fara autentificare: 401;
  - actiunea: itemul trebuie sa existe (404), actiunea sa fie a lui (400), `nu_util` mereu permis, a doua
    actiune cat prima asteapta da 409, consumul: 404 necunoscut, 409 a doua oara; asteapta -> consumat;
  - firul: mesajul lui Ion intra `nou` (`cine` forțat `ion`), a 31-a pe ora da 429, ciclul nou ->
    preluat -> gata|eroare si tranzitiile interzise (409), 404 necunoscut, aceeasi stare = 200 fara rescriere;
  - push: fara cheie `fcm_neconfigurat`, fara tokenuri `fara_tokenuri`, o eroare FCM (si o exceptie) nu da 5xx,
    ci `erori`; `UNREGISTERED` scoate tokenul din `push.json`; fara `push` in cerere nu se trimite nimic;
  - plafoane: 500 de randuri in fir si in actiuni (cad intai cele terminate; actiunile in asteptare nu cad),
    20 de tokenuri.
Directorul datelor e unul temporar: un test nu scrie niciodata in `uploads/` din proiect. Nicio proba nu atinge
reteaua: `fcm.trimite_date` sau `fcm._http_post` sunt inlocuite.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import asistent, fcm

ACUM = datetime(2026, 11, 22, 8, 0, 0, tzinfo=timezone.utc)
TOKEN_FCM = 'fcm-token-' + 'a' * 60
APLICATIE = 'org.iupif.torqa'
OPENSSL = shutil.which('openssl')
TRIMITE_REAL = fcm.trimite_date
unittest_skip_openssl = unittest.skipUnless(OPENSSL, 'openssl lipseste: nu se poate genera o cheie de proba')


def item(id_='torqa:task-9', **camp):
    base = {'id': id_, 'sursa': 'torqa', 'titlu': 'Task restant ' + id_, 'de_ce': 'Termen depasit cu 3 zile.',
            'gravitate': 'urgent', 'termen': '2026-11-19', 'prima_data': '2026-11-19T06:00:00Z', 'stare': 'nou',
            'amanat_pana': None, 'incredere': 'proprie', 'actiuni': ['gata', 'amana', 'ignora', 'claude']}
    base.update(camp)
    return base


def registru(*items, generat='2026-11-22T07:35:00Z', **camp):
    r = {'v': 1, 'generat': generat, 'items': list(items),
         'surse': {'torqa': {'ok': True}, 'mail': {'ok': False, 'eroare': 'Outlook nu raspunde'}},
         'veghe': {'generat': '2026-11-22T07:30:00Z', 'total': 46, 'ok': 45,
                   'picate': [{'nume': 'backup-vault', 'detaliu': 'ultima rulare acum 3 zile'}]}}
    r.update(camp)
    return r


class Baza(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'asistent')
        self.patch(asistent, 'DIR_ASISTENT', self.dir)
        self.acum = ACUM
        self.patch(asistent, '_acum', lambda: self.acum)
        self.env = mock.patch.dict(os.environ)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop('FCM_SERVICE_ACCOUNT_FILE', None)
        self.patch(self.app_module, 'RATE_LIMIT', 100000)           # limita de 60/min per IP nu e subiectul acestor teste
        fcm._CONT.update(cale=None, mtime=None, val=None)

    def h(self, token=FULL):
        return self.bearer(token) if token else {}

    def pune(self, cuprins, token=FULL):
        return self.client.put('/api/asistent/registru', json=cuprins, headers=self.h(token))

    def pune_ok(self, *items, **camp):
        r = self.pune(registru(*items, **camp))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def vedere(self, token=DEVICE):
        r = self.client.get('/api/asistent', headers=self.h(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def fisier(self, nume):
        with open(os.path.join(self.dir, nume), 'rb') as fh:
            return fh.read()

    def randuri(self, nume):
        return [json.loads(l) for l in self.fisier(nume).decode('utf-8').split('\n') if l.strip()]

    def scrie_randuri(self, nume, randuri):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, nume), 'w', encoding='utf-8') as fh:
            for r in randuri:
                fh.write(json.dumps(r) + '\n')

    def actiune(self, item_id='torqa:task-9', actiune='gata', token=DEVICE, **camp):
        return self.client.post('/api/asistent/actiune', json={'item_id': item_id, 'actiune': actiune, **camp},
                                headers=self.h(token))

    def actiuni(self, token=FULL, stare=None):
        return self.client.get('/api/asistent/actiuni', headers=self.h(token),
                               query_string={'stare': stare} if stare else None)

    def consuma(self, uid, token=FULL, **corp):
        return self.client.post('/api/asistent/actiuni/%s/consumat' % uid, json=corp or {'rezultat': 'ok'},
                                headers=self.h(token))

    def scrie_ion(self, text='Fa-mi un rezumat', token=DEVICE, **camp):
        return self.client.post('/api/asistent/fir', json={'text': text, **camp}, headers=self.h(token))

    def scrie_asistent(self, token=FULL, **camp):
        corp = {'cine': 'asistent', 'tip': 'info', 'text': 'Salut'}
        corp.update(camp)
        return self.client.post('/api/asistent/fir', json=corp, headers=self.h(token))

    def noi(self, token=FULL):
        r = self.client.get('/api/asistent/fir/noi', headers=self.h(token))
        self.assertEqual(r.status_code, 200)
        return r.get_json()

    def stare(self, id_, stare, token=FULL, **camp):
        return self.client.post('/api/asistent/fir/%s/stare' % id_, json={'stare': stare, **camp}, headers=self.h(token))

    def token_push(self, token=TOKEN_FCM, auth=DEVICE, **camp):
        corp = {'token': token, 'platforma': 'android', 'aplicatie': APLICATIE, 'versiune': '1.0.0'}
        corp.update(camp)
        return self.client.post('/api/asistent/push/token', json=corp, headers=self.h(auth))

    def tokenuri(self):
        return json.loads(self.fisier('push.json'))['tokeni']


# --------------------------------------------------------------------------- registrul

class Registru(Baza):

    def test_put_valid_scrie_si_raspunde(self):
        r = self.pune(registru(item('a:1'), item('a:2', stare='gata')))
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'items': 2}))
        self.assertEqual(sorted(os.listdir(self.dir)), ['asistent.lock', 'registru.json'], 'niciun .tmp ramas')
        stocat = json.loads(self.fisier('registru.json'))
        self.assertEqual(stocat['generat'], '2026-11-22T07:35:00Z')
        self.assertEqual(stocat['items'][0]['link'], None, 'campurile optionale lipsa se completeaza cu null')

    def test_registru_gol_de_itemi_e_valid(self):
        r = self.pune(registru(surse={}, veghe=None))
        self.assertEqual(r.get_json(), {'ok': True, 'items': 0})

    def test_aceeasi_cerere_de_doua_ori_lasa_acelasi_fisier(self):
        c = registru(item())
        self.pune(c)
        prima = self.fisier('registru.json')
        self.assertEqual(self.pune(c).status_code, 200)
        self.assertEqual(self.fisier('registru.json'), prima)

    def test_generat_mai_vechi_da_409_si_nu_scrie(self):
        self.pune_ok(item())
        prima = self.fisier('registru.json')
        r = self.pune(registru(item('a:alt'), generat='2026-11-22T07:00:00Z'))
        self.assertEqual(r.status_code, 409)
        self.assertIn('2026-11-22T07:35:00Z', r.get_json()['error'])
        self.assertEqual(self.fisier('registru.json'), prima)
        self.assertEqual(self.pune(registru(item('a:alt'), generat='2026-11-22T07:36:00Z')).status_code, 200)

    def test_fus_orar_in_generat_se_compara_ca_moment(self):
        self.pune_ok(item(), generat='2026-11-22T09:00:00+02:00')              # = 07:00Z
        self.assertEqual(self.pune(registru(item(), generat='2026-11-22T06:59:00Z')).status_code, 409)

    BAD = (
        ('camp necunoscut sus', lambda r: r.update(extra=1), 'corpul.extra'),
        ('v gresit', lambda r: r.update(v=2), 'v:'),
        ('v bool', lambda r: r.update(v=True), 'v:'),
        ('generat fara fus', lambda r: r.update(generat='2026-11-22T07:35:00'), 'generat'),
        ('generat luna 13', lambda r: r.update(generat='2026-13-22T07:35:00Z'), 'generat'),
        ('generat lipsa', lambda r: r.pop('generat'), 'generat'),
        ('items nu e lista', lambda r: r.update(items={}), 'corpul.items'),
        ('items peste 300', lambda r: r.update(items=[item('a:%d' % i) for i in range(301)]), 'corpul.items'),
        ('item nu e obiect', lambda r: r.update(items=['x']), 'items[0]'),
        ('item camp necunoscut', lambda r: r['items'][0].update(nou=1), 'items[0].nou'),
        ('item id lipsa', lambda r: r['items'][0].pop('id'), 'items[0].id'),
        ('item id peste 120', lambda r: r['items'][0].update(id='x' * 121), 'items[0].id'),
        ('item id duplicat', lambda r: r['items'].append(item()), 'items[1].id'),
        ('sursa necunoscuta', lambda r: r['items'][0].update(sursa='whatsapp'), 'items[0].sursa'),
        ('titlu gol', lambda r: r['items'][0].update(titlu=' '), 'items[0].titlu'),
        ('titlu peste 140', lambda r: r['items'][0].update(titlu='t' * 141), 'items[0].titlu'),
        ('de_ce peste 200', lambda r: r['items'][0].update(de_ce='d' * 201), 'items[0].de_ce'),
        ('gravitate', lambda r: r['items'][0].update(gravitate='mare'), 'items[0].gravitate'),
        ('termen invalid', lambda r: r['items'][0].update(termen='2026-02-30'), 'items[0].termen'),
        ('termen cu ora', lambda r: r['items'][0].update(termen='2026-11-19T10:00:00Z'), 'items[0].termen'),
        ('prima_data invalida', lambda r: r['items'][0].update(prima_data='ieri'), 'items[0].prima_data'),
        ('stare necunoscuta', lambda r: r['items'][0].update(stare='sters'), 'items[0].stare'),
        ('amanat fara amanat_pana', lambda r: r['items'][0].update(stare='amanat', amanat_pana=None), 'items[0].amanat_pana'),
        ('incredere', lambda r: r['items'][0].update(incredere='poate'), 'items[0].incredere'),
        ('actiune necunoscuta', lambda r: r['items'][0].update(actiuni=['sterge']), 'items[0].actiuni[0]'),
        ('actiuni duplicate', lambda r: r['items'][0].update(actiuni=['gata', 'gata']), 'items[0].actiuni'),
        ('nu_util nu se declara', lambda r: r['items'][0].update(actiuni=['nu_util']), 'items[0].actiuni[0]'),
        ('link absolut', lambda r: r['items'][0].update(link='/etc/passwd'), 'items[0].link'),
        ('link cu ..', lambda r: r['items'][0].update(link='wiki/../../x.md'), 'items[0].link'),
        ('link javascript', lambda r: r['items'][0].update(link='javascript:alert(1)'), 'items[0].link'),
        ('link http', lambda r: r['items'][0].update(link='http://exemplu.ro/x'), 'items[0].link'),
        ('surse nu e obiect', lambda r: r.update(surse=[]), 'surse'),
        ('surse ok nu e bool', lambda r: r['surse']['torqa'].update(ok='da'), 'surse.torqa.ok'),
        ('surse camp necunoscut', lambda r: r['surse']['torqa'].update(x=1), 'surse.torqa.x'),
        ('surse eroare lunga', lambda r: r['surse']['mail'].update(eroare='e' * 201), 'surse.mail.eroare'),
        ('surse nume prost', lambda r: r['surse'].update({'Mail Server': {'ok': True}}), 'surse.Mail Server'),
        ('veghe camp necunoscut', lambda r: r['veghe'].update(x=1), 'veghe.x'),
        ('veghe ok peste total', lambda r: r['veghe'].update(ok=50), 'veghe.ok'),
        ('veghe total negativ', lambda r: r['veghe'].update(total=-1), 'veghe.total'),
        ('veghe picat fara nume', lambda r: r['veghe']['picate'][0].pop('nume'), 'veghe.picate[0].nume'),
        ('veghe detaliu lung', lambda r: r['veghe']['picate'][0].update(detaliu='d' * 201), 'veghe.picate[0].detaliu'),
        ('veghe categorii nu e obiect', lambda r: r['veghe'].update(categorii=[]), 'veghe.categorii'),
        ('veghe categorie necunoscuta', lambda r: r['veghe'].update(categorii={'ftp': {'total': 1, 'ok': 1}}),
         'veghe.categorii.ftp'),
        ('veghe categorie ok peste total', lambda r: r['veghe'].update(categorii={'http': {'total': 1, 'ok': 2}}),
         'veghe.categorii.http.ok'),
        ('veghe categorie camp necunoscut',
         lambda r: r['veghe'].update(categorii={'disc': {'total': 1, 'ok': 1, 'x': 0}}), 'veghe.categorii.disc.x'),
        ('veghe categorie fara total', lambda r: r['veghe'].update(categorii={'timer': {'ok': 1}}),
         'veghe.categorii.timer.total'),
    )

    def test_corp_invalid_da_400_cu_calea_campului_si_pastreaza_registrul(self):
        self.pune_ok(item('vechi:1'))
        prima = self.fisier('registru.json')
        for nume, strica, cale in self.BAD:
            with self.subTest(nume):
                r = registru(item())
                strica(r)
                raspuns = self.pune(r)
                self.assertEqual(raspuns.status_code, 400, raspuns.get_data(as_text=True))
                self.assertIn(cale, raspuns.get_json()['error'])
                self.assertEqual(self.fisier('registru.json'), prima)

    def test_json_invalid_si_corp_care_nu_e_obiect(self):
        for corp in (b'', b'{', b'[]', b'"x"', b'null'):
            with self.subTest(corp=corp):
                r = self.client.put('/api/asistent/registru', data=corp, headers=dict(self.h(), **{'Content-Type': 'application/json'}))
                self.assertEqual(r.status_code, 400)

    def test_corp_prea_mare_413(self):
        r = self.client.put('/api/asistent/registru', data=b' ' * (1024 * 1024 + 10),
                            headers=dict(self.h(), **{'Content-Type': 'application/json'}))
        self.assertEqual(r.status_code, 413)

    def test_300_de_itemi_trec(self):
        self.assertEqual(self.pune_ok(*[item('a:%d' % i) for i in range(300)])['items'], 300)

    def test_diacriticele_se_pastreaza(self):
        self.pune_ok(item(titlu='Verifică ștergerea în așteptare'))
        self.assertEqual(self.vedere()['registru']['items'][0]['titlu'], 'Verifică ștergerea în așteptare')

    def test_link_valid_relativ_si_https(self):
        for link in ('wiki/job/Foo bar.md', 'https://pif.iupif.org/torqa/'):
            with self.subTest(link=link):
                self.assertEqual(self.pune(registru(item(link=link), generat='2026-11-22T07:40:00Z')).status_code, 200)

    def test_registrul_stricat_pe_disc_nu_strica_get(self):
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, 'registru.json'), 'w') as fh:
            fh.write('{"v": 1')
        v = self.vedere()
        self.assertEqual((v['registru']['generat'], v['registru']['items']), (None, []))


# --------------------------------------------------------------------------- GET /api/asistent

class Vedere(Baza):

    def test_fara_registru_totul_e_gol(self):
        v = self.vedere()
        self.assertEqual(v, {'v': 1, 'acum': '2026-11-22T08:00:00Z',
                             'registru': {'generat': None, 'vechime_min': None, 'items': [], 'surse': {}},
                             'veghe': None, 'fir': [], 'actiuni_in_asteptare': [], 'push': {'configurat': False}})

    def test_registru_vechime_surse_si_veghe(self):
        self.pune_ok(item())
        v = self.vedere()
        self.assertEqual(v['registru']['generat'], '2026-11-22T07:35:00Z')
        self.assertEqual(v['registru']['vechime_min'], 25)
        self.assertEqual(v['registru']['surse']['mail'], {'ok': False, 'eroare': 'Outlook nu raspunde'})
        self.assertEqual(v['veghe']['total'], 46)
        self.assertEqual(v['veghe']['picate'][0]['nume'], 'backup-vault')
        self.assertNotIn('categorii', v['veghe'])

    def test_veghe_categorii_optionale_trec_in_vedere(self):
        cat = {'http': {'total': 9, 'ok': 9}, 'timer': {'total': 23, 'ok': 22}, 'docker': {'total': 10, 'ok': 10},
               'putere': {'total': 2, 'ok': 2}, 'disc': {'total': 1, 'ok': 1}, 'netdata': {'total': 1, 'ok': 1}}
        r = registru(item())
        r['veghe']['categorii'] = cat
        self.assertEqual(self.pune(r).status_code, 200)
        self.assertEqual(self.vedere()['veghe']['categorii'], cat)

    def test_filtrarea_itemilor_active(self):
        trecut, viitor = '2026-11-22T07:59:59Z', '2026-11-22T08:00:01Z'
        self.pune_ok(
            item('a:nou', stare='nou'), item('a:vazut', stare='vazut'),
            item('a:amanat-expirat', stare='amanat', amanat_pana=trecut),
            item('a:amanat-acum', stare='amanat', amanat_pana='2026-11-22T08:00:00Z'),
            item('a:amanat-viitor', stare='amanat', amanat_pana=viitor),
            item('a:gata', stare='gata'), item('a:ignorat', stare='ignorat'), item('a:claude', stare='la_claude'))
        ids = [it['id'] for it in self.vedere()['registru']['items']]
        self.assertEqual(ids, ['a:nou', 'a:vazut', 'a:amanat-expirat', 'a:amanat-acum'])

    def test_amanat_cu_fus_orar_se_compara_ca_moment(self):
        self.pune_ok(item('a:1', stare='amanat', amanat_pana='2026-11-22T10:00:00+02:00'),   # = 08:00Z
                     item('a:2', stare='amanat', amanat_pana='2026-11-22T10:30:00+02:00'))   # = 08:30Z
        self.assertEqual([it['id'] for it in self.vedere()['registru']['items']], ['a:1'])

    def test_fir_ultimele_100_cele_mai_vechi_intai(self):
        self.scrie_randuri('fir.jsonl', [{'id': 'm_%06x' % i, 'ts': '2026-11-22T07:00:00Z', 'cine': 'asistent',
                                          'tip': 'info', 'text': 'mesaj %d' % i} for i in range(130)])
        fir = self.vedere()['fir']
        self.assertEqual((len(fir), fir[0]['text'], fir[-1]['text']), (100, 'mesaj 30', 'mesaj 129'))
        self.assertEqual(set(fir[0]), {'id', 'ts', 'cine', 'tip', 'titlu', 'text', 'sursa', 'item_id', 'task_id',
                                        'link', 'butoane', 'raspuns_la', 'stare', 'stare_detaliu', 'via'})
        self.assertEqual(fir[0]['butoane'], [])

    def test_sesiunea_si_tokenul_de_masina_citesc_la_fel(self):
        self.pune_ok(item())
        self.assertEqual(self.vedere(FULL), self.vedere(DEVICE))
        self.login()
        r = self.client.get('/api/asistent')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.get_json()['registru']['items']), 1)

    def test_push_configurat_dupa_fisierul_de_cont(self):
        self.assertFalse(self.vedere()['push']['configurat'])
        with mock.patch.object(fcm, 'configurat', return_value=True):
            self.assertTrue(self.vedere()['push']['configurat'])


# --------------------------------------------------------------------------- acces

class Acces(Baza):

    RUTE_MASINA = (
        ('put', '/api/asistent/registru'), ('get', '/api/asistent/actiuni'),
        ('post', '/api/asistent/actiuni/0123456789ab/consumat'), ('get', '/api/asistent/fir/noi'),
        ('post', '/api/asistent/fir/m_ab12cd/stare'),
    )

    def test_dispozitivul_primeste_403_pe_rutele_asistentului(self):
        for metoda, cale in self.RUTE_MASINA:
            with self.subTest(cale=cale):
                r = getattr(self.client, metoda)(cale, json=registru() if metoda == 'put' else {}, headers=self.h(DEVICE))
                self.assertEqual(r.status_code, 403)
                self.assertIn('dispozitiv', r.get_json()['error'])

    def test_dispozitivul_nu_scrie_ca_asistent(self):
        r = self.scrie_asistent(token=DEVICE)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.client.get('/api/asistent', headers=self.h(DEVICE)).get_json()['fir'], [])

    def test_fara_autentificare_401_pe_toate(self):
        for metoda, cale in self.RUTE_MASINA + (('get', '/api/asistent'), ('post', '/api/asistent/actiune'),
                                                 ('post', '/api/asistent/fir'), ('post', '/api/asistent/push/token'),
                                                 ('delete', '/api/asistent/push/token')):
            with self.subTest(cale=cale, metoda=metoda):
                self.assertEqual(self.client.open(cale, method=metoda.upper(), json={}).status_code, 401)

    def test_token_gresit_401(self):
        self.assertEqual(self.client.get('/api/asistent', headers=self.h('gresit')).status_code, 401)

    def test_dispozitivul_trece_pe_rutele_torqa(self):
        self.pune_ok(item())
        self.assertEqual(self.client.get('/api/asistent', headers=self.h(DEVICE)).status_code, 200)
        self.assertEqual(self.actiune(token=DEVICE).status_code, 201)
        self.assertEqual(self.scrie_ion(token=DEVICE).status_code, 201)
        self.assertEqual(self.token_push(auth=DEVICE).status_code, 200)

    def test_sesiunea_scrie_ca_ion_cu_csrf(self):
        self.login()
        self.client.get('/api/asistent')
        csrf = {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}
        r = self.client.post('/api/asistent/fir', json={'text': 'din browser'}, headers=csrf)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        r = self.client.post('/api/asistent/fir', json={'cine': 'asistent', 'tip': 'info', 'text': 'x'}, headers=csrf)
        self.assertEqual(r.status_code, 403)
        self.assertEqual([m['cine'] for m in self.vedere()['fir']], ['ion'])


# --------------------------------------------------------------------------- actiuni

class Actiuni(Baza):

    def setUp(self):
        super().setUp()
        self.pune_ok(item(), item('mail:5', actiuni=['gata']), item('vault:2', actiuni=[]))

    def test_ciclul_asteapta_consumat(self):
        r = self.actiune('torqa:task-9', 'claude', din='notificare')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        uid = r.get_json()['uid']
        self.assertEqual(list(r.get_json()), ['uid'])
        self.assertRegex(uid, r'^[0-9a-f]{12}$')
        self.assertEqual([a['uid'] for a in self.actiuni(stare='asteapta').get_json()], [uid])
        self.assertEqual(self.vedere()['actiuni_in_asteptare'],
                         [{'uid': uid, 'item_id': 'torqa:task-9', 'actiune': 'claude'}])
        a = self.actiuni().get_json()[0]
        self.assertEqual(a, {'uid': uid, 'ts': '2026-11-22T08:00:00Z', 'item_id': 'torqa:task-9',
                             'actiune': 'claude', 'zile': None, 'din': 'notificare'})
        r = self.consuma(uid, rezultat='ok', mesaj='dat lui Claude')
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'uid': uid}))
        self.assertEqual(self.actiuni(stare='asteapta').get_json(), [])
        self.assertEqual(self.vedere()['actiuni_in_asteptare'], [])
        consumata = self.actiuni(stare='consumat').get_json()
        self.assertEqual([x['uid'] for x in consumata], [uid])
        rand = self.randuri('actiuni.jsonl')[0]
        self.assertEqual((rand['stare'], rand['rezultat'], rand['mesaj'], rand['consumat']),
                         ('consumat', 'ok', 'dat lui Claude', '2026-11-22T08:00:00Z'))

    def test_dupa_consum_itemul_poate_primi_alta_actiune(self):
        uid = self.actiune().get_json()['uid']
        self.assertEqual(self.actiune(actiune='ignora').status_code, 409)
        self.consuma(uid, rezultat='fail')
        self.assertEqual(self.actiune(actiune='ignora').status_code, 201)

    def test_a_doua_actiune_pe_acelasi_item_cat_prima_asteapta_409(self):
        self.assertEqual(self.actiune().status_code, 201)
        r = self.actiune(actiune='claude')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(len(self.randuri('actiuni.jsonl')), 1)
        self.assertEqual(self.actiune('mail:5').status_code, 201, 'alt item: nicio problema')

    def test_item_necunoscut_404_si_fara_registru_404(self):
        self.assertEqual(self.actiune('nu:exista').status_code, 404)
        shutil.rmtree(self.dir)
        self.assertEqual(self.actiune().status_code, 404)

    def test_actiunea_trebuie_sa_fie_a_itemului(self):
        self.assertEqual(self.actiune('mail:5', 'claude').status_code, 400)
        r = self.actiune('mail:5', 'amana')
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.actiune', r.get_json()['error'])
        self.assertEqual(self.actiune('mail:5', 'gata').status_code, 201)

    def test_nu_util_e_mereu_permis(self):
        self.assertEqual(self.actiune('vault:2', 'nu_util').status_code, 201)
        self.assertEqual(self.actiune('vault:2', 'gata').status_code, 400, 'itemul n-are `gata`')
        self.assertEqual(self.actiune('vault:2', 'nu_util').status_code, 409, 'prima asteapta inca')

    def test_zile_la_amana(self):
        r = self.actiune(actiune='amana', zile=3)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.actiuni().get_json()[0]['zile'], 3)

    def test_amana_fara_zile_inseamna_o_zi(self):
        self.actiune(actiune='amana')
        self.assertEqual(self.actiuni().get_json()[0]['zile'], 1)

    def test_validarea_corpului(self):
        for corp, cale in (({}, 'corpul.item_id'),
                           ({'item_id': 'torqa:task-9'}, 'corpul.actiune'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'sterge'}, 'corpul.actiune'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'amana', 'zile': 0}, 'corpul.zile'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'amana', 'zile': 32}, 'corpul.zile'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'amana', 'zile': '2'}, 'corpul.zile'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'amana', 'zile': True}, 'corpul.zile'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'gata', 'zile': 2}, 'corpul.zile'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'gata', 'din': 'sms'}, 'corpul.din'),
                           ({'item_id': 'torqa:task-9', 'actiune': 'gata', 'extra': 1}, 'corpul.extra'),
                           ({'item_id': 5, 'actiune': 'gata'}, 'corpul.item_id'),
                           ({'item_id': 'x' * 121, 'actiune': 'gata'}, 'corpul.item_id')):
            with self.subTest(corp=corp):
                r = self.client.post('/api/asistent/actiune', json=corp, headers=self.h(DEVICE))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'actiuni.jsonl')))

    def test_zile_31_trece(self):
        self.assertEqual(self.actiune(actiune='amana', zile=31).status_code, 201)

    def test_get_actiuni_cele_mai_vechi_intai_si_stare_invalida_400(self):
        self.actiune('mail:5', 'gata')
        self.acum = ACUM - timedelta(minutes=5)
        self.actiune('torqa:task-9', 'gata')
        self.assertEqual([a['item_id'] for a in self.actiuni().get_json()], ['torqa:task-9', 'mail:5'])
        self.assertEqual(self.actiuni(stare='toate').status_code, 400)

    def test_consum_validare_404_409(self):
        uid = self.actiune().get_json()['uid']
        for corp, cale in (({}, 'corpul.rezultat'), ({'rezultat': 'poate'}, 'corpul.rezultat'),
                           ({'rezultat': 'ok', 'mesaj': 'm' * 301}, 'corpul.mesaj'),
                           ({'rezultat': 'ok', 'x': 1}, 'corpul.x'), ({'rezultat': 'ok', 'mesaj': 5}, 'corpul.mesaj')):
            with self.subTest(corp=corp):
                r = self.client.post('/api/asistent/actiuni/%s/consumat' % uid, json=corp, headers=self.h())
                self.assertEqual(r.status_code, 400)
                self.assertIn(cale, r.get_json()['error'])
        self.assertEqual(self.consuma('0123456789ab').status_code, 404)
        self.assertEqual(self.consuma('nu-e-uid').status_code, 404)
        self.assertEqual(self.consuma(uid, rezultat='ok').status_code, 200)
        r = self.consuma(uid, rezultat='fail')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.randuri('actiuni.jsonl')[0]['rezultat'], 'ok', 'o retrimitere nu rescrie rezultatul')

    def test_plafon_500_cad_cele_consumate_nu_cele_in_asteptare(self):
        vechi = [{'uid': '%012x' % i, 'ts': '2026-11-21T00:00:00Z', 'item_id': 'x:%d' % i, 'actiune': 'gata',
                  'zile': None, 'din': 'pagina', 'stare': 'consumat'} for i in range(499)]
        asteapta = {'uid': 'a' * 12, 'ts': '2026-11-21T00:00:00Z', 'item_id': 'mail:5', 'actiune': 'gata',
                    'zile': None, 'din': 'pagina', 'stare': 'asteapta'}
        self.scrie_randuri('actiuni.jsonl', [asteapta] + vechi + [dict(vechi[0], uid='b' * 12, stare='consumat')])
        self.assertEqual(self.actiune().status_code, 201)
        randuri = self.randuri('actiuni.jsonl')
        self.assertEqual(len(randuri), 500)
        self.assertEqual(randuri[0]['uid'], 'a' * 12, 'cea in asteptare nu cade')
        self.assertEqual(randuri[-1]['item_id'], 'torqa:task-9')
        self.assertNotIn('%012x' % 0, [r['uid'] for r in randuri], 'cea mai veche consumata a cazut')

    def test_rand_stricat_in_fisier_se_ignora(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'actiuni.jsonl'), 'w') as fh:
            fh.write('nu e json\n[1]\n')
        self.assertEqual(self.actiuni().get_json(), [])
        self.assertEqual(self.actiune().status_code, 201)


# --------------------------------------------------------------------------- fir

class Fir(Baza):

    def test_mesajul_lui_ion_intra_nou(self):
        r = self.scrie_ion('Ce am azi?', sursa='dictat')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(list(r.get_json()), ['id'])
        id_ = r.get_json()['id']
        self.assertRegex(id_, r'^m_[0-9a-f]{6}$')
        m = self.noi()[0]
        self.assertEqual(m, {'id': id_, 'ts': '2026-11-22T08:00:00Z', 'cine': 'ion', 'tip': 'mesaj', 'titlu': None,
                             'text': 'Ce am azi?', 'sursa': 'dictat', 'item_id': None, 'task_id': None, 'link': None,
                             'butoane': [], 'raspuns_la': None, 'stare': 'nou', 'stare_detaliu': None,
                             'via': 'dispozitiv'})

    def test_sursa_implicita_scris_si_cine_ion_acceptat(self):
        self.scrie_ion(cine='ion')
        self.assertEqual(self.noi()[0]['sursa'], 'scris')

    def test_cine_nu_se_poate_schimba_cu_dispozitivul(self):
        r = self.scrie_ion(cine='altcineva')
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.cine', r.get_json()['error'])

    def test_validarea_mesajului_lui_ion(self):
        for corp, cale in (({}, 'corpul.text'), ({'text': ''}, 'corpul.text'), ({'text': '  \n '}, 'corpul.text'),
                           ({'text': 'x' * 2001}, 'corpul.text'), ({'text': 5}, 'corpul.text'),
                           ({'text': 'a\x00b'}, 'corpul.text'),
                           ({'text': 'x', 'sursa': 'vocal'}, 'corpul.sursa'),
                           ({'text': 'x', 'raspuns_la': 'abc'}, 'corpul.raspuns_la'),
                           ({'text': 'x', 'tip': 'alerta'}, 'corpul.tip'),
                           ({'text': 'x', 'stare': 'gata'}, 'corpul.stare')):
            with self.subTest(corp=corp):
                r = self.client.post('/api/asistent/fir', json=corp, headers=self.h(DEVICE))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))

    def test_2000_de_caractere_cu_rand_nou_si_diacritice_trec(self):
        self.assertEqual(self.scrie_ion('ă' * 1990 + '\nșț\n\tînț').status_code, 201)

    def test_corp_care_nu_e_obiect_400(self):
        for corp in ([], 'x', 5, None):
            r = self.client.post('/api/asistent/fir', json=corp, headers=self.h(DEVICE))
            self.assertEqual(r.status_code, 400, corp)

    def test_limita_de_30_pe_ora_31_da_429(self):
        for i in range(30):
            self.acum = ACUM + timedelta(seconds=i)
            self.assertEqual(self.scrie_ion('mesaj %d' % i).status_code, 201, i)
        self.acum = ACUM + timedelta(seconds=30)
        r = self.scrie_ion('al 31-lea')
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.headers['Retry-After'], '3571')                       # prima iese din fereastra la 08:00 + 1 h
        self.assertEqual(len(self.randuri('fir.jsonl')), 30)
        self.acum = ACUM + timedelta(hours=1, seconds=1)                           # a iesit prima
        self.assertEqual(self.scrie_ion('acum da').status_code, 201)             # in fereastra raman 28 + aceasta
        self.assertEqual(self.scrie_ion('inca unul').status_code, 201)           # a doua a iesit si ea (08:00:01)
        self.assertEqual(self.scrie_ion('peste').status_code, 429)

    def test_limita_nu_numara_mesajele_asistentului(self):
        for i in range(35):
            self.assertEqual(self.scrie_asistent(text='a %d' % i).status_code, 201)
        self.assertEqual(self.scrie_ion().status_code, 201)

    def test_ciclul_nou_preluat_gata(self):
        id_ = self.scrie_ion().get_json()['id']
        r = self.stare(id_, 'preluat')
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'id': id_, 'stare': 'preluat'}))
        self.assertEqual(self.noi(), [], 'preluat nu mai e nou')
        r = self.stare(id_, 'gata', task_id='T-77', mesaj='creat taskul')
        self.assertEqual(r.status_code, 200)
        m = next(m for m in self.vedere()['fir'] if m['id'] == id_)
        self.assertEqual((m['stare'], m['task_id'], m['stare_detaliu']), ('gata', 'T-77', 'creat taskul'))

    def test_tranzitiile_permise_si_interzise(self):
        permise = (('nou', 'preluat'), ('nou', 'gata'), ('nou', 'eroare'), ('preluat', 'gata'), ('preluat', 'eroare'))
        interzise = (('gata', 'preluat'), ('gata', 'eroare'), ('eroare', 'gata'), ('eroare', 'preluat'))
        for de_la, la in permise + interzise:
            with self.subTest(de_la=de_la, la=la):
                id_ = self.scrie_ion().get_json()['id']
                self.acum += timedelta(minutes=5)
                rand = next(r for r in self.randuri('fir.jsonl') if r['id'] == id_)
                if de_la != 'nou':
                    rand['stare'] = de_la
                    todos = [rand if r['id'] == id_ else r for r in self.randuri('fir.jsonl')]
                    self.scrie_randuri('fir.jsonl', todos)
                r = self.stare(id_, la)
                self.assertEqual(r.status_code, 200 if (de_la, la) in permise else 409, r.get_data(as_text=True))

    def test_aceeasi_stare_a_doua_oara_e_200_fara_rescriere(self):
        id_ = self.scrie_ion().get_json()['id']
        self.stare(id_, 'preluat', mesaj='prima')
        prima = self.fisier('fir.jsonl')
        r = self.stare(id_, 'preluat', mesaj='a doua')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.fisier('fir.jsonl'), prima)

    def test_stare_404_400_si_mesajul_asistentului_nu_are_stare(self):
        self.assertEqual(self.stare('m_ffffff', 'preluat').status_code, 404)
        self.assertEqual(self.stare('nu-e-id', 'preluat').status_code, 404)
        id_ = self.scrie_asistent().get_json()['id']
        self.assertEqual(self.stare(id_, 'preluat').status_code, 409)
        ion = self.scrie_ion().get_json()['id']
        for corp, cale in (({}, 'corpul.stare'), ({'stare': 'nou'}, 'corpul.stare'), ({'stare': 'dus'}, 'corpul.stare'),
                           ({'stare': 'gata', 'mesaj': 'm' * 301}, 'corpul.mesaj'),
                           ({'stare': 'gata', 'task_id': 7}, 'corpul.task_id'), ({'stare': 'gata', 'x': 1}, 'corpul.x')):
            with self.subTest(corp=corp):
                r = self.client.post('/api/asistent/fir/%s/stare' % ion, json=corp, headers=self.h())
                self.assertEqual(r.status_code, 400)
                self.assertIn(cale, r.get_json()['error'])

    def test_fir_noi_doar_ion_cu_stare_nou_cele_mai_vechi_intai(self):
        a = self.scrie_ion('primul').get_json()['id']
        self.acum += timedelta(minutes=1)
        self.scrie_asistent(text='raspuns')
        b = self.scrie_ion('al doilea').get_json()['id']
        self.acum += timedelta(minutes=1)
        c = self.scrie_ion('al treilea').get_json()['id']
        self.stare(b, 'preluat')
        self.assertEqual([m['id'] for m in self.noi()], [a, c])

    def test_asistentul_cu_cine_ion_scrie_mesaj_al_lui_ion(self):
        r = self.client.post('/api/asistent/fir', json={'cine': 'ion', 'text': 'prin masina'}, headers=self.h(FULL))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.noi()[0]['text'], 'prin masina')

    def test_masina_fara_cine_400(self):
        r = self.client.post('/api/asistent/fir', json={'text': 'x', 'tip': 'info'}, headers=self.h(FULL))
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.cine', r.get_json()['error'])

    def test_validarea_mesajului_asistentului(self):
        ok = {'cine': 'asistent', 'tip': 'alerta', 'text': 'x'}
        for modifica, cale in (
                ({'tip': 'mesaj'}, 'corpul.tip'), ({'tip': None}, 'corpul.tip'), ({'text': ''}, 'corpul.text'),
                ({'text': 't' * 2001}, 'corpul.text'), ({'titlu': 't' * 141}, 'corpul.titlu'), ({'titlu': ''}, 'corpul.titlu'),
                ({'item_id': 'i' * 121}, 'corpul.item_id'), ({'task_id': 't' * 81}, 'corpul.task_id'),
                ({'link': 'http://x.ro'}, 'corpul.link'), ({'link': '../x'}, 'corpul.link'), ({'link': 'file:///etc/passwd'}, 'corpul.link'),
                ({'butoane': 'claude'}, 'corpul.butoane'), ({'butoane': ['sterge']}, 'corpul.butoane[0]'),
                ({'butoane': ['gata', 'gata']}, 'corpul.butoane'), ({'butoane': ['claude'] * 6}, 'corpul.butoane'),
                ({'raspuns_la': 'abc'}, 'corpul.raspuns_la'), ({'push': 'da'}, 'corpul.push'), ({'push': {'x': 1}}, 'corpul.push.x'),
                ({'push': {'prioritate': 'mare'}}, 'corpul.push.prioritate'), ({'sursa': 'scris'}, 'corpul.sursa'),
                ({'stare': 'nou'}, 'corpul.stare')):
            with self.subTest(modifica=modifica):
                r = self.client.post('/api/asistent/fir', json=dict(ok, **modifica), headers=self.h(FULL))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))

    def test_mesajul_asistentului_complet_se_intoarce_in_fir(self):
        r = self.scrie_asistent(tip='alerta', titlu='Backup picat', text='Ultima copie e veche.', item_id='server:backup',
                                task_id='T-1', link='wiki/job/index.md', butoane=['claude', 'amana', 'deschide'],
                                raspuns_la='m_abcdef')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        m = self.vedere()['fir'][0]
        self.assertEqual((m['cine'], m['tip'], m['titlu'], m['item_id'], m['task_id'], m['link'], m['butoane'],
                          m['raspuns_la'], m['stare'], m['sursa']),
                         ('asistent', 'alerta', 'Backup picat', 'server:backup', 'T-1', 'wiki/job/index.md',
                          ['claude', 'amana', 'deschide'], 'm_abcdef', None, None))

    def test_retrimiterea_aceluiasi_mesaj_il_dubleaza(self):
        """Contractul n-are cheie de idempotenta: documentat, nu ascuns."""
        self.scrie_ion('acelasi')
        self.scrie_ion('acelasi')
        self.assertEqual(len(self.noi()), 2)

    def test_plafon_500_cad_intai_cele_terminate(self):
        self.scrie_randuri('fir.jsonl', [dict(id='m_%06x' % i, ts='2026-11-21T00:00:00Z', cine='ion', tip='mesaj',
                                              text='vechi %d' % i, sursa='scris', stare='nou' if i < 3 else 'gata')
                                         for i in range(500)])
        self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
        randuri = self.randuri('fir.jsonl')
        self.assertEqual(len(randuri), 500)
        self.assertEqual([r['id'] for r in randuri[:3]], ['m_000000', 'm_000001', 'm_000002'], 'cele nou nu cad')
        self.assertEqual(randuri[3]['id'], 'm_000004', 'a cazut cea mai veche terminata (m_000003)')
        self.assertEqual(randuri[-1]['text'], 'nou')

    def test_plafon_500_cu_toate_neprocesate_cade_cea_mai_veche(self):
        self.scrie_randuri('fir.jsonl', [dict(id='m_%06x' % i, ts='2026-11-21T00:00:00Z', cine='ion', tip='mesaj',
                                              text='vechi %d' % i, sursa='scris', stare='nou') for i in range(500)])
        self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
        randuri = self.randuri('fir.jsonl')
        self.assertEqual((len(randuri), randuri[0]['id'], randuri[-1]['text']), (500, 'm_000001', 'nou'))

    def test_niciun_tmp_ramas_dupa_scrieri(self):
        self.scrie_ion()
        self.scrie_asistent()
        self.assertEqual(sorted(os.listdir(self.dir)), ['asistent.lock', 'fir.jsonl'])


# --------------------------------------------------------------------------- push

class Push(Baza):

    def setUp(self):
        super().setUp()
        self.date = []

        def trimite(tokeni, date, prioritate, **kw):
            self.date.append((list(tokeni), date, prioritate))
            return self.iesire

        self.iesire = {'trimise': 1, 'erori': [], 'nregistrate': []}
        self.patch(fcm, 'trimite_date', trimite)
        self.configurat = mock.patch.object(fcm, 'configurat', return_value=True)
        self.configurat.start()
        self.addCleanup(self.configurat.stop)

    def cu_push(self, prioritate='urgent', **camp):
        return self.scrie_asistent(push={'prioritate': prioritate}, **camp)

    def test_fara_push_in_cerere_nu_se_trimite_nimic(self):
        self.token_push()
        r = self.scrie_asistent()
        self.assertEqual(r.get_json()['push'], {'incercat': False, 'trimise': 0, 'erori': [], 'motiv': None})
        self.assertEqual(self.date, [])

    def test_fara_cheie_fcm_neconfigurat(self):
        self.configurat.stop()
        self.token_push()
        r = self.cu_push()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['push'], {'incercat': False, 'trimise': 0, 'erori': [], 'motiv': 'fcm_neconfigurat'})
        self.assertEqual(self.date, [])
        self.configurat.start()

    def test_fara_tokenuri(self):
        r = self.cu_push()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['push'], {'incercat': False, 'trimise': 0, 'erori': [], 'motiv': 'fara_tokenuri'})
        self.assertEqual(self.date, [])

    def test_trimitere_cu_succes(self):
        self.token_push()
        r = self.cu_push('urgent', tip='alerta', titlu='Backup picat', text='Ultima copie e veche.', item_id='server:backup',
                         butoane=['claude', 'amana', 'deschide'])
        id_ = r.get_json()['id']
        self.assertEqual(r.get_json()['push'], {'incercat': True, 'trimise': 1, 'erori': [], 'motiv': None})
        tokeni, date, android = self.date[0]
        self.assertEqual((tokeni, android), ([TOKEN_FCM], 'HIGH'))
        self.assertEqual(date, {'v': '1', 'tip': 'alerta', 'msg_id': id_, 'titlu': 'Backup picat',
                                'text': 'Ultima copie e veche.', 'item_id': 'server:backup',
                                'butoane': 'claude,amana,deschide', 'prioritate': 'urgent',
                                'deschide': '/system?tab=asistent&msg=%s' % id_})
        self.assertTrue(all(isinstance(v, str) for v in date.values()), 'FCM data: doar string-uri')

    def test_prioritatea_normal_si_silent_pleaca_cu_NORMAL(self):
        self.token_push()
        for prioritate in ('normal', 'silent'):
            self.cu_push(prioritate)
        self.assertEqual([d[2] for d in self.date], ['NORMAL', 'NORMAL'])
        self.assertEqual([d[1]['prioritate'] for d in self.date], ['normal', 'silent'])

    def test_push_gol_inseamna_prioritate_normal(self):
        self.token_push()
        r = self.scrie_asistent(push={})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.date[0][1]['prioritate'], 'normal')

    def test_campurile_lipsa_devin_string_gol(self):
        self.token_push()
        self.cu_push()
        d = self.date[0][1]
        self.assertEqual((d['titlu'], d['item_id'], d['butoane']), ('', '', ''))

    def test_textul_lung_se_taie_in_octeti_nu_in_caractere(self):
        """`data` din FCM are 4096 de octeti: se taie la cel mai lung prefix care incape sub 4000, fara sa rupa
        un caracter, indiferent de cati octeti are fiecare (ASCII 1, ț 2, emoji 4)."""
        self.token_push()
        titlu, item_id = 'ă' * 140, 'i' * 120
        for text in ('ț' * 2000, '😀' * 1000, 'ab😀😀ț ' * 285):
            with self.subTest(text=text[:6]):
                self.date.clear()
                self.cu_push(text=text, titlu=titlu, item_id=item_id)
                date = self.date[0][1]
                octeti = len(json.dumps(date, ensure_ascii=False).encode('utf-8'))
                self.assertLessEqual(octeti, 4000)
                self.assertTrue(date['text'].endswith('…'))
                prefix = date['text'][:-1]
                self.assertTrue(text.startswith(prefix.rstrip()), 'e un prefix al textului')
                self.assertGreater(octeti, 4000 - 8, 'cel mai lung prefix: nu mai incape nici un caracter (max 4 octeti + spatiu)')
                date['text'].encode('utf-8')                                    # niciun surogat, niciun caracter rupt
        self.assertEqual(self.vedere()['fir'][-1]['text'], text, 'in fir ramane intreg')

    def test_text_scurt_nu_se_atinge(self):
        self.token_push()
        self.cu_push(text='ț' * 500)
        self.assertEqual(self.date[0][1]['text'], 'ț' * 500)

    def test_eroare_fcm_nu_da_5xx_ci_intra_in_erori(self):
        self.token_push()
        self.iesire = {'trimise': 0, 'erori': ['...aaaaaa: HTTP 503'], 'nregistrate': []}
        r = self.cu_push()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['push'], {'incercat': True, 'trimise': 0, 'erori': ['...aaaaaa: HTTP 503'], 'motiv': None})
        self.assertEqual(len(self.vedere()['fir']), 1, 'mesajul ramane in fir')

    def test_exceptie_in_transport_nu_da_5xx(self):
        self.token_push()
        self.patch(fcm, 'trimite_date', mock.Mock(side_effect=RuntimeError('bug')))
        r = self.cu_push()
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.get_json()['push']['trimise'], r.get_json()['push']['erori']), (0, ['eroare interna la trimitere']))
        self.assertEqual(len(self.vedere()['fir']), 1)

    def test_unregistered_scoate_tokenul_din_push_json(self):
        self.token_push()
        self.token_push('alt-token-' + 'b' * 40)
        self.iesire = {'trimise': 1, 'erori': ['...aaaaaa: UNREGISTERED'], 'nregistrate': [TOKEN_FCM]}
        r = self.cu_push()
        self.assertEqual((r.get_json()['push']['trimise'], r.get_json()['push']['incercat']), (1, True))
        self.assertEqual([t['token'] for t in self.tokenuri()], ['alt-token-' + 'b' * 40])

    def test_tokenul_dispare_chiar_si_cand_toate_sunt_respinse(self):
        self.token_push()
        self.iesire = {'trimise': 0, 'erori': ['x'], 'nregistrate': [TOKEN_FCM]}
        self.cu_push()
        self.assertEqual(self.tokenuri(), [])
        self.assertEqual(self.cu_push().get_json()['push']['motiv'], 'fara_tokenuri')

    def test_push_nu_tine_blocarea_fisierelor(self):
        """Transportul ruleaza cu blocarea eliberata: o scriere din interiorul lui nu se blocheaza."""
        self.token_push()

        def trimite(tokeni, date, prioritate, **kw):
            self.assertEqual(self.token_push('din-transport-' + 'c' * 40).status_code, 200)
            return self.iesire
        self.patch(fcm, 'trimite_date', trimite)
        self.assertEqual(self.cu_push().status_code, 201)

    @unittest_skip_openssl
    def test_cap_la_cap_cu_cheie_reala_si_retea_inlocuita(self):
        """`blueprints/asistent` + `blueprints/fcm` fara mock pe `trimite_date`: doar `_http_post` e fals."""
        self.configurat.stop()
        dir_cont = tempfile.mkdtemp(prefix='pif-fcm-cap-')
        self.addCleanup(shutil.rmtree, dir_cont, ignore_errors=True)
        cheie = subprocess.run([OPENSSL, 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048'],
                               capture_output=True, check=True).stdout.decode()
        cont = os.path.join(dir_cont, 'cont.json')
        with open(cont, 'w') as fh:
            json.dump({'project_id': 'p-test', 'client_email': 'c@p-test.iam', 'private_key': cheie}, fh)
        os.environ['FCM_SERVICE_ACCOUNT_FILE'] = cont
        fcm._TOKEN.update(valoare=None, expira=0.0)
        cereri = []

        def http(url, date, antete, timeout):
            cereri.append(url)
            if url == fcm.URL_TOKEN:
                return 200, b'{"access_token": "acces", "expires_in": 3600}'
            return (404, b'{}') if json.loads(date)['message']['token'].startswith('mort') else (200, b'{}')
        self.patch(fcm, '_http_post', http)
        self.patch(fcm, 'trimite_date', TRIMITE_REAL)                              # cel real (anuleaza mock-ul din setUp)
        self.token_push('viu-' + 'a' * 40)
        self.token_push('mort-' + 'b' * 40)
        self.assertTrue(self.vedere()['push']['configurat'])
        r = self.cu_push()
        push = r.get_json()['push']
        self.assertEqual((r.status_code, push['incercat'], push['trimise'], push['motiv']), (201, True, 1, None))
        self.assertEqual(len(push['erori']), 1)
        self.assertIn('UNREGISTERED', push['erori'][0])
        self.assertEqual([t['token'] for t in self.tokenuri()], ['viu-' + 'a' * 40])
        self.assertEqual(cereri, [fcm.URL_TOKEN] + [fcm.URL_SEND % 'p-test'] * 2)
        self.assertEqual(self.date, [], 'mock-ul din setUp n-a fost folosit')


# --------------------------------------------------------------------------- tokenurile push

class TokenuriPush(Baza):

    def test_inregistrarea_pastreaza_campurile_si_nu_le_arata_in_get(self):
        r = self.token_push()
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True}))
        t = self.tokenuri()[0]
        self.assertEqual((t['token'], t['platforma'], t['aplicatie'], t['versiune']), (TOKEN_FCM, 'android', APLICATIE, '1.0.0'))
        self.assertEqual((t['inregistrat'], t['ultima_vedere']), ('2026-11-22T08:00:00Z', '2026-11-22T08:00:00Z'))
        self.assertNotIn(TOKEN_FCM, json.dumps(self.vedere()), 'tokenurile nu ies prin GET')

    def test_upsert_pe_token_actualizeaza_ultima_vedere(self):
        self.token_push()
        self.acum = ACUM + timedelta(days=2)
        self.token_push(versiune='1.1.0')
        tokenuri = self.tokenuri()
        self.assertEqual(len(tokenuri), 1)
        self.assertEqual((tokenuri[0]['versiune'], tokenuri[0]['inregistrat'], tokenuri[0]['ultima_vedere']),
                         ('1.1.0', '2026-11-22T08:00:00Z', '2026-11-24T08:00:00Z'))

    def test_versiunea_e_optionala(self):
        r = self.client.post('/api/asistent/push/token', json={'token': TOKEN_FCM, 'platforma': 'android', 'aplicatie': APLICATIE},
                             headers=self.h(DEVICE))
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self.tokenuri()[0]['versiune'])

    def test_validarea(self):
        ok = {'token': TOKEN_FCM, 'platforma': 'android', 'aplicatie': APLICATIE}
        for modifica, cale in (({'token': ''}, 'corpul.token'), ({'token': 'a' * 4097}, 'corpul.token'),
                               ({'token': 5}, 'corpul.token'), ({'token': 'cu spatiu'}, 'corpul.token'),
                               ({'token': 'diacritică'}, 'corpul.token'),
                               ({'platforma': 'ios'}, 'corpul.platforma'), ({'platforma': None}, 'corpul.platforma'),
                               ({'aplicatie': 'nu un pachet'}, 'corpul.aplicatie'), ({'aplicatie': 'org'}, 'corpul.aplicatie'),
                               ({'aplicatie': 'a.' * 60}, 'corpul.aplicatie'), ({'aplicatie': ''}, 'corpul.aplicatie'),
                               ({'versiune': 'v' * 41}, 'corpul.versiune'), ({'versiune': 1}, 'corpul.versiune'),
                               ({'extra': 1}, 'corpul.extra')):
            with self.subTest(modifica=modifica):
                r = self.client.post('/api/asistent/push/token', json=dict(ok, **modifica), headers=self.h(DEVICE))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        for corp in ({k: v for k, v in ok.items() if k != c} for c in ok):
            r = self.client.post('/api/asistent/push/token', json=corp, headers=self.h(DEVICE))
            self.assertEqual(r.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'push.json')))

    def test_token_de_4096_trece(self):
        self.assertEqual(self.token_push('a' * 4096).status_code, 200)

    def test_plafon_20_de_tokenuri_raman_cele_mai_recente(self):
        for i in range(22):
            self.acum = ACUM + timedelta(minutes=i)
            self.token_push('tok%02d-' % i + 'x' * 30)
        tokeni = [t['token'] for t in self.tokenuri()]
        self.assertEqual(len(tokeni), 20)
        self.assertNotIn('tok00-' + 'x' * 30, tokeni)
        self.assertNotIn('tok01-' + 'x' * 30, tokeni)
        self.assertIn('tok21-' + 'x' * 30, tokeni)

    def test_stergerea_e_idempotenta(self):
        self.token_push()
        r = self.client.delete('/api/asistent/push/token', json={'token': TOKEN_FCM}, headers=self.h(DEVICE))
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'scos': True}))
        self.assertEqual(self.tokenuri(), [])
        r = self.client.delete('/api/asistent/push/token', json={'token': TOKEN_FCM}, headers=self.h(DEVICE))
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'scos': False}))

    def test_stergerea_valideaza(self):
        for corp, cale in (({}, 'corpul.token'), ({'token': 5}, 'corpul.token'), ({'token': 'x', 'platforma': 'android'}, 'corpul.platforma')):
            r = self.client.delete('/api/asistent/push/token', json=corp, headers=self.h(DEVICE))
            self.assertEqual(r.status_code, 400)
            self.assertIn(cale, r.get_json()['error'])

    def test_push_json_are_drepturi_600(self):
        self.token_push()
        mod = stat.S_IMODE(os.stat(os.path.join(self.dir, 'push.json')).st_mode)
        self.assertEqual(mod, 0o600)


# --------------------------------------------------------------------------- recenzia (2026-11-22)

class Surogate(Baza):
    """Un surogat izolat (`\\ud83d`) trece de `json.loads` si strica scrierea UTF-8 (500): se respinge cu 400."""

    def brut(self, metoda, cale, corp, token):
        return self.client.open(cale, method=metoda, data=corp, content_type='application/json', headers=self.h(token))

    def test_surogat_in_mesajul_lui_ion(self):
        r = self.brut('POST', '/api/asistent/fir', '{"text": "salut \\ud83d"}', DEVICE)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn('corpul.text', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))

    def test_surogat_in_registru_cu_calea_campului(self):
        r = self.brut('PUT', '/api/asistent/registru',
                      json.dumps(registru(item(titlu='x \ud83d'))), FULL)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn('items[0].titlu', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'registru.json')))

    def test_surogat_in_mesajul_asistentului_si_in_restul_corpurilor(self):
        for metoda, cale, corp, token in (
                ('POST', '/api/asistent/fir', '{"cine": "asistent", "tip": "info", "text": "a\\udc00"}', FULL),
                ('POST', '/api/asistent/fir', '{"cine": "asistent", "tip": "info", "text": "x", "butoane": ["\\ud800"]}', FULL),
                ('POST', '/api/asistent/actiune', '{"item_id": "\\ud83d", "actiune": "gata"}', DEVICE),
                ('POST', '/api/asistent/push/token', '{"token": "\\ud83d", "platforma": "android", "aplicatie": "a.b"}', DEVICE),
                ('POST', '/api/asistent/fir', '{"text": "x", "\\ud83d": 1}', DEVICE)):
            with self.subTest(corp=corp):
                r = self.brut(metoda, cale, corp, token)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('corpul', r.get_json()['error'])
        self.assertEqual(os.listdir(self.dir) if os.path.exists(self.dir) else [], [])

    def test_perechea_valida_de_surogate_e_emoji_si_trece(self):
        r = self.brut('POST', '/api/asistent/fir', '{"text": "salut \\ud83d\\ude00"}', DEVICE)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.noi()[0]['text'], 'salut 😀')


@unittest.skipIf(not hasattr(os, 'geteuid') or os.geteuid() == 0, 'chmod 0 nu opreste citirea pentru root / pe Windows')
class EroriDeCitire(Baza):
    """O eroare de citire (permisiuni) nu trebuie sa duca la rescrierea fisierului pornind de la nimic."""

    def fara_acces(self, nume):
        cale = os.path.join(self.dir, nume)
        os.chmod(cale, 0)
        self.addCleanup(os.chmod, cale, 0o600)
        return cale

    def test_fir_ilizibil_da_500_si_nu_pierde_mesajele(self):
        for t in ('unu', 'doi', 'trei'):
            self.assertEqual(self.scrie_ion(t).status_code, 201)
        prima = self.fisier('fir.jsonl')
        cale = self.fara_acces('fir.jsonl')
        for r in (self.scrie_ion('patru'), self.scrie_asistent(), self.stare('m_ffffff', 'preluat')):
            self.assertEqual(r.status_code, 500)
        os.chmod(cale, 0o600)
        self.assertEqual(self.fisier('fir.jsonl'), prima)
        self.assertEqual(len(self.randuri('fir.jsonl')), 3)

    def test_citirea_simpla_cu_fisier_ilizibil_nu_da_500(self):
        self.scrie_ion('unu')
        self.fara_acces('fir.jsonl')
        v = self.vedere()
        self.assertEqual(v['fir'], [])
        self.assertEqual(self.client.get('/api/asistent/fir/noi', headers=self.h(FULL)).get_json(), [])

    def test_actiuni_ilizibile_dau_500_fara_scriere(self):
        self.pune_ok(item())
        uid = self.actiune('torqa:task-9').get_json()['uid']
        prima = self.fisier('actiuni.jsonl')
        cale = self.fara_acces('actiuni.jsonl')
        self.assertEqual(self.actiune('torqa:task-9', 'claude').status_code, 500)
        self.assertEqual(self.consuma(uid).status_code, 500)
        os.chmod(cale, 0o600)
        self.assertEqual(self.fisier('actiuni.jsonl'), prima)

    def test_tokenuri_ilizibile_dau_500_si_raman(self):
        self.token_push('A' * 40)
        self.token_push('B' * 40)
        prima = self.fisier('push.json')
        cale = self.fara_acces('push.json')
        self.assertEqual(self.token_push('C' * 40).status_code, 500)
        r = self.client.delete('/api/asistent/push/token', json={'token': 'A' * 40}, headers=self.h(DEVICE))
        self.assertEqual(r.status_code, 500)
        os.chmod(cale, 0o600)
        self.assertEqual(self.fisier('push.json'), prima)
        self.assertEqual([t['token'][0] for t in self.tokenuri()], ['A', 'B'])

    def test_registru_ilizibil_da_500_la_put(self):
        self.pune_ok(item('vechi:1'))
        prima = self.fisier('registru.json')
        cale = self.fara_acces('registru.json')
        self.assertEqual(self.pune(registru(item('nou:1'), generat='2026-11-22T07:40:00Z')).status_code, 500)
        os.chmod(cale, 0o600)
        self.assertEqual(self.fisier('registru.json'), prima)


class DateStricate(Baza):
    """Ce nu se poate citi nu se arunca tacut la rescriere: merge in `<fisier>.corupt`, o singura data."""

    def corupt(self, nume):
        with open(os.path.join(self.dir, nume + '.corupt'), 'rb') as fh:
            return fh.read()

    def test_liniile_stricate_din_fir_se_pastreaza_in_corupt(self):
        self.scrie_ion('unu')
        with open(os.path.join(self.dir, 'fir.jsonl'), 'ab') as fh:
            fh.write(b'{"id": "m_zzzz\n\xff\xfe garbage\n[1]\n')
        self.assertEqual(self.scrie_ion('doi').status_code, 201)
        self.assertEqual([r['text'] for r in self.randuri('fir.jsonl')], ['unu', 'doi'])
        corupt = self.corupt('fir.jsonl')
        self.assertEqual(corupt.split(b'\n')[:-1], [b'{"id": "m_zzzz', b'\xff\xfe garbage', b'[1]'])
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.dir, 'fir.jsonl.corupt')).st_mode), 0o600)
        self.scrie_ion('trei')
        self.assertEqual(self.corupt('fir.jsonl'), corupt, 'a doua scriere nu dubleaza copia')

    def test_actiuni_stricate_se_pastreaza_in_corupt(self):
        self.pune_ok(item())
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'actiuni.jsonl'), 'w') as fh:
            fh.write('nu e json\n')
        self.assertEqual(self.actiune().status_code, 201)
        self.assertEqual(self.corupt('actiuni.jsonl'), b'nu e json\n')

    def test_push_json_stricat_se_pastreaza_si_se_reia_de_la_zero(self):
        self.token_push('A' * 40)
        with open(os.path.join(self.dir, 'push.json'), 'wb') as fh:
            fh.write(b'\x00\x00 nu e json')
        self.assertEqual(self.token_push('B' * 40).status_code, 200)
        self.assertEqual([t['token'][0] for t in self.tokenuri()], ['B'])
        self.assertEqual(self.corupt('push.json'), b'\x00\x00 nu e json\n')

    def test_intrari_de_token_cu_alta_forma_se_pastreaza(self):
        with open(os.path.join(self.dir if os.path.isdir(self.dir) else (os.makedirs(self.dir) or self.dir), 'push.json'), 'w') as fh:
            json.dump({'tokeni': [{'token': 'bun-' + 'a' * 20}, {'fara': 'token'}, 7]}, fh)
        self.token_push('B' * 40)
        self.assertEqual(sorted(t['token'][0] for t in self.tokenuri()), ['B', 'b'])
        self.assertEqual(self.corupt('push.json').split(b'\n')[:-1], [b'{"fara": "token"}', b'7'])

    def test_registru_stricat_e_inlocuit_la_put(self):
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, 'registru.json'), 'w') as fh:
            fh.write('{broken')
        self.assertEqual(self.pune(registru(item())).status_code, 200)

    def test_u2028_si_u0085_in_text_nu_rup_randul(self):
        """`splitlines` ar fi rupt randul la U+2028 / U+0085 (json.dumps nu le scapa): mesajul ar fi disparut."""
        text = 'a\u2028b\u0085c\u2029d'
        self.assertEqual(self.scrie_ion(text).status_code, 201)
        self.assertEqual(self.scrie_asistent(text='x\u2028y').status_code, 201)
        self.assertEqual(len(self.randuri('fir.jsonl')), 2)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl.corupt')))
        fir = self.vedere()['fir']
        self.assertEqual([m['text'] for m in fir], [text, 'x\u2028y'])


class ItemiAscunsi(Baza):
    """Actiunea se accepta doar pe itemi activi: a doua apasare pe butonul din notificare, dupa ce asistentul a
    preluat-o pe prima, nu face al doilea task."""

    def test_stari_neactive_dau_409_pentru_orice_actiune(self):
        self.pune_ok(item('a:claude', stare='la_claude'), item('a:gata', stare='gata'), item('a:ign', stare='ignorat'),
                     item('a:viitor', stare='amanat', amanat_pana='2026-11-22T08:00:01Z'))
        for id_ in ('a:claude', 'a:gata', 'a:ign', 'a:viitor'):
            for actiune in ('claude', 'gata', 'nu_util'):
                with self.subTest(item=id_, actiune=actiune):
                    r = self.actiune(id_, actiune)
                    self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
                    self.assertIn('nu e activ', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'actiuni.jsonl')))

    def test_stari_active_trec(self):
        self.pune_ok(item('a:nou', stare='nou'), item('a:vazut', stare='vazut'),
                     item('a:expirat', stare='amanat', amanat_pana='2026-11-22T07:59:59Z'))
        for id_ in ('a:nou', 'a:vazut', 'a:expirat'):
            self.assertEqual(self.actiune(id_, 'claude').status_code, 201, id_)

    def test_a_doua_apasare_dupa_ce_asistentul_a_preluat_prima(self):
        self.pune_ok(item('a:1'))
        uid = self.actiune('a:1', 'claude', din='notificare').get_json()['uid']
        self.assertEqual(self.actiune('a:1', 'claude', din='notificare').status_code, 409, 'cat asteapta')
        self.consuma(uid)
        self.pune(registru(item('a:1', stare='la_claude'), generat='2026-11-22T07:40:00Z'))
        self.assertEqual(self.actiune('a:1', 'claude', din='notificare').status_code, 409, 'dupa ce itemul a trecut la_claude')
        self.assertEqual(len(self.randuri('actiuni.jsonl')), 1)

    def test_itemul_necunoscut_ramane_404(self):
        self.pune_ok(item('a:1', stare='gata'))
        self.assertEqual(self.actiune('nu:exista').status_code, 404)


class Via(Baza):
    """`via` il pune serverul pe mesajul lui Ion: asistentul afla de unde vine."""

    def mesaj_nou(self):
        return self.noi()[-1]

    def test_dispozitiv(self):
        self.scrie_ion(token=DEVICE)
        self.assertEqual(self.mesaj_nou()['via'], 'dispozitiv')

    def test_masina(self):
        r = self.client.post('/api/asistent/fir', json={'cine': 'ion', 'text': 'prin masina'}, headers=self.h(FULL))
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.mesaj_nou()['via'], 'masina')

    def test_sesiune(self):
        self.login()
        self.client.get('/api/asistent')
        csrf = {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}
        self.assertEqual(self.client.post('/api/asistent/fir', json={'text': 'din browser'}, headers=csrf).status_code, 201)
        self.assertEqual(self.mesaj_nou()['via'], 'sesiune')

    def test_mesajul_asistentului_nu_are_via(self):
        self.scrie_asistent()
        self.assertIsNone(self.vedere()['fir'][-1]['via'])

    def test_clientul_nu_poate_pune_via(self):
        for token in (DEVICE, FULL):
            r = self.client.post('/api/asistent/fir', json={'cine': 'ion', 'text': 'x', 'via': 'masina'}, headers=self.h(token))
            self.assertEqual(r.status_code, 400)
            self.assertIn('corpul.via', r.get_json()['error'])

    def test_via_apare_si_in_get_asistent(self):
        self.scrie_ion(token=DEVICE)
        self.assertEqual(self.vedere()['fir'][0]['via'], 'dispozitiv')


class Linkuri(Baza):
    """`link` ajunge in notificari si in aplicatie: fara cai care ies din vault, fara https care ascunde host-ul."""

    OK = ('wiki/job/Foo bar.md', 'wiki/a%20b.md', 'x.md', './x', 'wiki/job/a..b.md', 'https://pif.iupif.org/torqa/?a=1&b=%2F',
          'https://exemplu.ro:8443/x#y')
    REFUZATE = (
        ('https:// fara host', 'https://'), ('https:/// fara host', 'https:///x'), ('https cu cale doar', 'https:///etc/passwd'),
        ('https port gol', 'https://:443/x'), ('userinfo', 'https://u:p@evil.example/x'), ('userinfo simplu', 'https://ion@evil.example/'),
        ('https cu spatiu', 'https://exemplu.ro/a b'), ('https cu backslash', 'https://exemplu.ro\\@evil.example/'),
        ('https port gresit', 'https://exemplu.ro:99999/x'),
        ('%2e%2e', '%2e%2e/x'), ('%2E%2E majuscule', 'wiki/%2E%2E/x'), ('%2f', 'wiki%2f..%2fx'), ('%5c', 'wiki%5cx'), ('%00', 'x%00.md'),
        ('..', 'a/../b'), ('doar ..', '..'), ('absolut', '/etc/passwd'), ('backslash', 'a\\b'), ('schema', 'javascript:alert(1)'),
        ('schema data', 'data:text/html,x'), ('cu doua puncte', 'wiki/a:b.md'), ('//host', '//evil.example/x'),
        ('RLO', 'wiki/\u202emd.xe'), ('LRI', 'wiki/\u2066x'), ('PDI', 'wiki/x\u2069'), ('LRE', 'a\u202ab'), ('PDF', 'a\u202cb'),
        ('LRM', 'a\u200eb'), ('ALM', 'a\u061cb'), ('bidi in https', 'https://exemplu.ro/\u202ex'),
        ('control', 'a\x01b'), ('tab', 'a\tb'), ('newline', 'a\nb'), ('DEL', 'a\x7fb'), ('C1', 'a\x85b'), ('NUL', 'a\x00b'),
        ('U+2028', 'a\u2028b'),
    )

    def test_acceptate(self):
        for link in self.OK:
            with self.subTest(link=link):
                r = self.scrie_asistent(link=link)
                self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
                self.assertEqual(self.vedere()['fir'][-1]['link'], link)

    def test_refuzate_in_fir_si_in_registru(self):
        for nume, link in self.REFUZATE:
            with self.subTest(nume):
                r = self.scrie_asistent(link=link)
                self.assertEqual(r.status_code, 400, (link, r.get_data(as_text=True)))
                self.assertIn('corpul.link', r.get_json()['error'])
                r = self.pune(registru(item(link=link)))
                self.assertEqual(r.status_code, 400, (link, r.get_data(as_text=True)))
                self.assertIn('items[0].link', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'registru.json')))

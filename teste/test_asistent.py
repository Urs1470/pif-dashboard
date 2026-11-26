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
    un item referit de un mesaj al asistentului din fir e actionabil si fara registru (clasa `ActiuniDinFir`);
  - firul: mesajul lui Ion intra `nou` (`cine` forțat `ion`), a 31-a pe ora da 429, ciclul nou ->
    preluat -> gata|eroare si tranzitiile interzise (409), 404 necunoscut, aceeasi stare = 200 fara rescriere;
  - push: fara cheie `fcm_neconfigurat`, fara tokenuri `fara_tokenuri`, o eroare FCM (si o exceptie) nu da 5xx,
    ci `erori`; `UNREGISTERED` scoate tokenul din `push.json`; fara `push` in cerere nu se trimite nimic;
  - plafoane: 500 de randuri in fir si in actiuni (cad intai cele terminate; actiunile in asteptare nu cad),
    20 de tokenuri.
v1.1 (clasele `RefTintaAlegere`, `MesajAsistentV11`, `RaspunsLaIntrebare`, `Prezenta`):
  - `ref`, `tinta`, `alegere` pe mesajul lui Ion: validare strict, `mod: raspuns` doar la `decizie`, `alegere` doar
    cu `raspuns_la`, se intorc in `fir/noi` si in GET;
  - `intrebare`/`asteapta` cer 1-4 `optiuni` (id <= 40, eticheta <= 60, id-uri unice), alte tipuri nu le primesc;
    `masina` si `ref` pe mesajul asistentului;
  - raspunsul la o intrebare: 404 / 409 (nu e intrebare, deja raspuns) / 400 (optiune straina); `raspuns` pe
    intrebare si mesajul lui Ion apar impreuna (un singur `fir.jsonl`), niciodata una fara cealalta;
  - prezenta: PUT cu token de masina (dispozitiv 403, masina necunoscuta 404, corp strict), `masini` in GET cu
    pragurile de 180 s si 900 s la limita (ceas inlocuit), ordine fixa, nicio raportare = offline cu `ultima: null`.
v1.2 (clasa `Detalii`):
  - `detalii` pe mesajul asistentului (POST) si `PUT/GET /api/asistent/fir/<id>/detalii`: 1-65 536 de caractere dupa strip,
    fara surogate, `null` = lipsa / sterge; 404 / 409 / 403 / 401; id-ul nu poate iesi din `detalii/`;
  - fisierul `detalii/<id>.md` (atomic, nu intra in `fir.jsonl`) cade cu mesajul la plafonul de 500, iar cursa dintre
    PUT si scrierea firului nu lasa fisier orfan; `are_detalii` pe fiecare mesaj, false pe cele vechi.
v1.3 (clasa `Live`):
  - `PUT /api/asistent/fir/<id>/live` (token de masina; dispozitiv 403, fara token 401, sesiune cu CSRF): doar pe un mesaj al lui
    Ion (404 altfel, 400 la id invalid), corp strict (`text` 0-65 536 dupa strip, `unealta` <= 80 sau null, `gata` bool), `seq`
    creste cu 1, 409 dupa `gata`, fisierul `live/<id>.json` atomic; fiecare PUT matura fisierele de peste 15 minute;
  - `GET .../live`: 404 / 200 / 204 cu `?dupa=<seq>` (400 la valoare gresita), si cu dispozitivul sau sesiunea;
  - `GET .../live/flux` (SSE): antete, `retry`, un eveniment pe seq nou, inchidere la `gata`, ping la 15 s, plafon 60 s,
    `gol` dupa 20 s fara fisier, `Last-Event-ID`, 204 la reconectare dupa `gata`; ceasul e de proba, nimic nu asteapta.
Directorul datelor e unul temporar: un test nu scrie niciodata in `uploads/` din proiect. Nicio proba nu atinge
reteaua: `fcm.trimite_date` sau `fcm._http_post` sunt inlocuite.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
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
                             'veghe': None, 'fir': [], 'actiuni_in_asteptare': [], 'push': {'configurat': False},
                             'masini': [{'id': i, 'nume': n, 'stare': 'offline', 'ultima': None, 'idle_min': None}
                                        for i, n in (('server', 'Server'), ('pc-job', 'PC job'), ('ionpc', 'IONPC'))]})

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
                                        'link', 'butoane', 'raspuns_la', 'stare', 'stare_detaliu', 'via',
                                        'ref', 'tinta', 'alegere', 'optiuni', 'masina', 'raspuns', 'are_detalii'})
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
        ('post', '/api/asistent/fir/m_ab12cd/stare'), ('put', '/api/asistent/fir/m_ab12cd/detalii'),
        ('put', '/api/asistent/fir/m_ab12cd/live'),
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
                                                 ('get', '/api/asistent/fir/m_ab12cd/detalii'),
                                                 ('get', '/api/asistent/fir/m_ab12cd/live'),
                                                 ('get', '/api/asistent/fir/m_ab12cd/live/flux'),
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
                             'via': 'dispozitiv', 'ref': None, 'tinta': 'auto', 'alegere': None, 'optiuni': [],
                             'masina': None, 'raspuns': None, 'are_detalii': False})

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

    def test_masina_fara_cine_e_mesajul_lui_ion(self):
        # Torqa cu tokenul de masina nu trimite `cine` (2026-11-22: „Fa” respins cu 400 de pe telefon).
        ref = {'tip': 'decizie', 'id': 'executor:A-021', 'titlu': 'Actualizeaza Sure', 'sursa': 'Do', 'masina': 'server',
               'mod': 'raspuns'}
        r = self.client.post('/api/asistent/fir', json={'text': 'Fa', 'ref': ref}, headers=self.h(FULL))
        self.assertEqual(r.status_code, 201)
        m = self.noi()[0]
        self.assertEqual((m['cine'], m['text'], m['ref']['id']), ('ion', 'Fa', 'executor:A-021'))

    def test_masina_fara_cine_nu_devine_mesaj_al_asistentului(self):
        r = self.client.post('/api/asistent/fir', json={'text': 'x', 'tip': 'info'}, headers=self.h(FULL))
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.tip', r.get_json()['error'])
        r = self.client.post('/api/asistent/fir', json={'text': 'x', 'cine': 'altcineva'}, headers=self.h(FULL))
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.cine', r.get_json()['error'])
        self.assertEqual(self.noi(), [])

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


class ActiuniDinFir(Baza):
    """Un rezultat Claude ramane in fir cu butoanele lui dupa ce taskul Torqa s-a inchis si itemul a iesit din registru:
    Done, Tomorrow si Ignore nu mai dau 404 (jurnalul din 2026-11-22: 10 x 404 pe `claude:<task>`). Un item necunoscut
    si in registru, si in fir ramane 404."""

    ID = 'claude:09ce6bf2-1be3-4bd9-9d57-3c9b2024667d'

    def setUp(self):
        super().setUp()
        self.pune_ok(item('torqa:t1'))
        self.mesaj = self.scrie_asistent(tip='rezultat', item_id=self.ID, butoane=['gata', 'amana', 'ignora', 'deschide']).get_json()['id']

    def test_item_din_fir_fara_registru_primeste_actiunile_din_butoane(self):
        for actiune, extra in (('gata', {}), ('amana', {'zile': 2}), ('ignora', {}), ('nu_util', {})):
            with self.subTest(actiune=actiune):
                r = self.actiune(self.ID, actiune, din='pagina', **extra)
                self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
                self.consuma(r.get_json()['uid'])
        self.assertEqual([a['actiune'] for a in self.randuri('actiuni.jsonl')], ['gata', 'amana', 'ignora', 'nu_util'])

    def test_actiunea_trebuie_sa_fie_printre_butoanele_mesajului(self):
        self.scrie_asistent(tip='rezultat', item_id='claude:esuat', butoane=['gata', 'amana', 'deschide'])
        self.assertEqual(self.actiune('claude:esuat', 'amana').status_code, 201)
        r = self.actiune('claude:esuat', 'ignora')
        self.assertEqual(r.status_code, 400)
        self.assertIn('permise: gata, amana', r.get_json()['error'])
        r = self.actiune('claude:esuat', 'claude')
        self.assertEqual(r.status_code, 400, '`claude` nu e printre butoanele rezultatului')
        self.assertEqual(self.actiune('claude:esuat', 'deschide').status_code, 400, '`deschide` nu e actiune')

    def test_mesaj_fara_butoane_actiune_primeste_doar_nu_util(self):
        self.scrie_asistent(tip='info', item_id='x:fara', butoane=['deschide'])
        self.assertEqual(self.actiune('x:fara', 'gata').status_code, 400)
        self.assertEqual(self.actiune('x:fara', 'nu_util').status_code, 201)

    def test_item_necunoscut_nici_in_registru_nici_in_fir_ramane_404(self):
        r = self.actiune('claude:nu-exista', 'gata')
        self.assertEqual(r.status_code, 404)
        self.assertIn('fir', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'actiuni.jsonl')))
        # un mesaj al lui Ion cu acelasi text nu face itemul cunoscut: doar mesajele asistentului il poarta
        self.scrie_ion('claude:nu-exista')
        self.assertEqual(self.actiune('claude:nu-exista', 'gata').status_code, 404)

    def test_aceeasi_cerere_de_doua_ori_cat_prima_asteapta_da_409_apoi_se_accepta_din_nou(self):
        uid = self.actiune(self.ID, 'gata').get_json()['uid']
        self.assertEqual(self.actiune(self.ID, 'gata').status_code, 409)
        self.assertEqual(len(self.randuri('actiuni.jsonl')), 1)
        self.consuma(uid)
        self.assertEqual(self.actiune(self.ID, 'gata').status_code, 201, 'dublu-tap dupa consum: asistentul o aplica idempotent')

    def test_item_in_registru_are_prioritate_si_isi_pastreaza_regulile(self):
        # acelasi id si in registru (cu `gata` doar), si in fir (cu `amana`): registrul decide
        self.pune_ok(item('torqa:t1'), item(self.ID, sursa='claude', actiuni=['gata']))
        self.assertEqual(self.actiune(self.ID, 'amana').status_code, 400)
        self.assertEqual(self.actiune(self.ID, 'gata').status_code, 201)

    def test_repetarea_unei_actiuni_terminale_pe_item_din_fir_nu_da_409(self):
        self.pune_ok(item('torqa:t1'), item(self.ID, sursa='claude', actiuni=['gata', 'amana', 'ignora'], stare='gata'))
        self.assertEqual(self.actiune(self.ID, 'gata').status_code, 201, 'Done apasat a doua oara')
        self.pune_ok(item('torqa:t1'), item(self.ID, sursa='claude', actiuni=['gata', 'amana', 'ignora'], stare='ignorat'),
                     generat='2026-11-22T07:40:00Z')
        uid = self.randuri('actiuni.jsonl')[0]['uid']
        self.consuma(uid)
        self.assertEqual(self.actiune(self.ID, 'ignora').status_code, 201)
        # alta actiune pe un item inchis ramane 409, ca pana acum
        self.consuma(self.randuri('actiuni.jsonl')[1]['uid'])
        self.assertEqual(self.actiune(self.ID, 'amana').status_code, 409)

    def test_itemul_inchis_fara_mesaj_in_fir_ramane_409_si_nu_se_accepta_repetarea(self):
        self.pune_ok(item('a:gata', stare='gata'))
        self.assertEqual(self.actiune('a:gata', 'gata').status_code, 409)

    def test_fara_registru_deloc_itemul_din_fir_merge(self):
        os.remove(os.path.join(self.dir, 'registru.json'))
        self.assertEqual(self.actiune(self.ID, 'gata').status_code, 201)

    def test_fara_token_401_si_dispozitivul_cu_token_bun_trece(self):
        self.assertEqual(self.client.post('/api/asistent/actiune', json={'item_id': self.ID, 'actiune': 'gata'}).status_code, 401)
        self.assertEqual(self.actiune(self.ID, 'gata', token=DEVICE).status_code, 201)

    def test_corpul_se_valideaza_la_fel_pe_calea_din_fir(self):
        for corp, camp in (({'item_id': self.ID}, 'corpul.actiune'),
                           ({'item_id': self.ID, 'actiune': 'gata', 'zile': 2}, 'corpul.zile'),
                           ({'item_id': self.ID, 'actiune': 'amana', 'zile': 32}, 'corpul.zile'),
                           ({'item_id': self.ID, 'actiune': 'gata', 'extra': 1}, 'corpul.extra')):
            with self.subTest(corp=corp):
                r = self.client.post('/api/asistent/actiune', json=corp, headers=self.h(DEVICE))
                self.assertEqual(r.status_code, 400)
                self.assertIn(camp, r.get_json()['error'])


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


# --------------------------------------------------------------------------- v1.1: ref, tinta, alegere

REF = {'tip': 'decizie', 'id': 'pc-job:dec-7', 'titlu': 'Reinstalare Windows?', 'sursa': 'pc-job',
       'masina': 'pc-job', 'mod': 'raspuns'}
OPTIUNI = [{'id': 'pc-job', 'eticheta': 'PC job'}, {'id': 'ionpc', 'eticheta': 'IONPC'}]


class RefTintaAlegere(Baza):

    def test_ref_si_tinta_se_stocheaza_si_se_intorc(self):
        r = self.scrie_ion('Amana pe diseara', ref=REF, tinta='pc-job')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        m = self.noi()[0]
        self.assertEqual((m['ref'], m['tinta'], m['alegere']), (REF, 'pc-job', None))
        self.assertEqual(self.vedere()['fir'][0]['ref'], REF)
        self.assertEqual(self.randuri('fir.jsonl')[0]['ref'], REF)

    def test_fara_ref_si_tinta_ref_e_null_si_tinta_auto(self):
        self.scrie_ion('simplu')
        m = self.noi()[0]
        self.assertEqual((m['ref'], m['tinta'], m['alegere']), (None, 'auto', None))

    def test_ref_minim_primeste_valorile_implicite(self):
        self.scrie_ion('x', ref={'tip': 'item', 'id': 'torqa:task-9', 'titlu': 'Task'})
        self.assertEqual(self.noi()[0]['ref'], {'tip': 'item', 'id': 'torqa:task-9', 'titlu': 'Task', 'sursa': None,
                                                'masina': None, 'mod': 'discuta'})

    def test_toate_tipurile_de_ref_si_toate_tintele(self):
        for tip in ('item', 'decizie', 'verificare', 'job', 'istoric'):
            with self.subTest(tip=tip):
                r = self.scrie_ion('x', ref={'tip': tip, 'id': 'a', 'titlu': 'b', 'mod': 'discuta'})
                self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
                self.acum += timedelta(minutes=2)
        for tinta in ('auto', 'server', 'pc-job', 'ionpc'):
            with self.subTest(tinta=tinta):
                self.assertEqual(self.scrie_ion('x', tinta=tinta).status_code, 201)
                self.acum += timedelta(minutes=2)

    def test_limitele_de_lungime_trec(self):
        ref = {'tip': 'istoric', 'id': 'i' * 160, 'titlu': 't' * 140, 'sursa': 's' * 40}
        self.assertEqual(self.scrie_ion('x', ref=ref).status_code, 201)

    def test_mod_raspuns_doar_la_decizie(self):
        for tip in ('item', 'verificare', 'job', 'istoric'):
            with self.subTest(tip=tip):
                r = self.scrie_ion('x', ref=dict(REF, tip=tip))
                self.assertEqual(r.status_code, 400)
                self.assertIn('corpul.ref.mod', r.get_json()['error'])
        self.assertEqual(self.scrie_ion('x', ref=dict(REF, tip='item', mod='discuta')).status_code, 201)
        self.assertEqual(self.scrie_ion('x', ref=REF).status_code, 201)

    def test_validarea_ref_si_tinta_cu_calea_campului(self):
        ok = {'tip': 'item', 'id': 'a', 'titlu': 'b'}
        for corp, cale in (
                ({'ref': 'x'}, 'corpul.ref'), ({'ref': []}, 'corpul.ref'),
                ({'ref': dict(ok, x=1)}, 'corpul.ref.x'),
                ({'ref': {k: v for k, v in ok.items() if k != 'tip'}}, 'corpul.ref.tip'),
                ({'ref': {k: v for k, v in ok.items() if k != 'id'}}, 'corpul.ref.id'),
                ({'ref': {k: v for k, v in ok.items() if k != 'titlu'}}, 'corpul.ref.titlu'),
                ({'ref': dict(ok, tip='altceva')}, 'corpul.ref.tip'), ({'ref': dict(ok, tip=3)}, 'corpul.ref.tip'),
                ({'ref': dict(ok, id='')}, 'corpul.ref.id'), ({'ref': dict(ok, id=7)}, 'corpul.ref.id'),
                ({'ref': dict(ok, id='i' * 161)}, 'corpul.ref.id'), ({'ref': dict(ok, id='a\nb')}, 'corpul.ref.id'),
                ({'ref': dict(ok, titlu='')}, 'corpul.ref.titlu'), ({'ref': dict(ok, titlu='t' * 141)}, 'corpul.ref.titlu'),
                ({'ref': dict(ok, sursa='s' * 41)}, 'corpul.ref.sursa'), ({'ref': dict(ok, sursa=3)}, 'corpul.ref.sursa'),
                ({'ref': dict(ok, sursa='')}, 'corpul.ref.sursa'), ({'ref': dict(ok, masina=3)}, 'corpul.ref.masina'),
                ({'ref': dict(ok, mod=3)}, 'corpul.ref.mod'), ({'ref': dict(ok, tip=None)}, 'corpul.ref.tip'),
                ({'ref': dict(ok, masina='laptop')}, 'corpul.ref.masina'), ({'ref': dict(ok, masina='auto')}, 'corpul.ref.masina'),
                ({'ref': dict(ok, mod='altul')}, 'corpul.ref.mod'),
                ({'tinta': 'laptop'}, 'corpul.tinta'), ({'tinta': 5}, 'corpul.tinta'),
                ({'alegere': 'pc-job'}, 'corpul.alegere'),
                ({'alegere': 'pc-job', 'raspuns_la': None}, 'corpul.raspuns_la')):
            with self.subTest(corp=corp):
                r = self.client.post('/api/asistent/fir', json=dict({'text': 'x'}, **corp), headers=self.h(DEVICE))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))

    def test_alegere_cu_tip_gresit_si_prea_lunga_da_400(self):
        for alegere in (5, '', 'a' * 41):
            with self.subTest(alegere=alegere):
                r = self.scrie_ion('x', alegere=alegere, raspuns_la='m_abcdef')
                self.assertEqual(r.status_code, 400)
                self.assertIn('corpul.alegere', r.get_json()['error'])

    def test_fara_token_401_si_masina_cu_cine_ion_poate_trimite_ref(self):
        r = self.client.post('/api/asistent/fir', json={'text': 'x', 'ref': REF, 'tinta': 'ionpc'})
        self.assertEqual(r.status_code, 401)
        r = self.client.post('/api/asistent/fir', json={'cine': 'ion', 'text': 'x', 'ref': REF, 'tinta': 'ionpc'},
                             headers=self.h(FULL))
        self.assertEqual(r.status_code, 201)
        self.assertEqual((self.noi()[0]['ref'], self.noi()[0]['tinta']), (REF, 'ionpc'))

    def test_ref_intors_de_server_se_poate_retrimite_neschimbat(self):
        """Serverul intoarce `ref` cu sursa/masina null si `mod` pus; asistentul il repeta pe raspuns (fir/noi ->
        POST), iar Torqa il retrimite din GET: ambele trebuie sa treaca."""
        self.assertEqual(self.scrie_ion('x', ref={'tip': 'item', 'id': 'torqa:t-1', 'titlu': 'Task'}).status_code, 201)
        ref = self.noi()[0]['ref']
        self.assertEqual(ref, {'tip': 'item', 'id': 'torqa:t-1', 'titlu': 'Task', 'sursa': None, 'masina': None,
                               'mod': 'discuta'})
        r = self.scrie_asistent(tip='rezultat', ref=ref)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        r = self.scrie_ion('din GET', ref=self.vedere()['fir'][0]['ref'])
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        fir = self.vedere()['fir']
        self.assertEqual([m['ref'] for m in fir], [ref] * 3, 'acelasi ref, nealterat, dupa doua tururi')

    def test_ref_plin_se_retrimite_si_el(self):
        self.scrie_ion('x', ref=REF)
        ref = self.noi()[0]['ref']
        self.assertEqual(ref, REF)
        self.assertEqual(self.scrie_asistent(tip='rezultat', ref=ref).status_code, 201)
        self.assertEqual(self.scrie_ion('din GET', ref=ref).status_code, 201)

    def test_null_in_ref_ca_lipsa(self):
        ok = {'tip': 'decizie', 'id': 'a', 'titlu': 'b'}
        for extra in ({'sursa': None}, {'masina': None}, {'mod': None}, {'sursa': None, 'masina': None, 'mod': None}):
            with self.subTest(extra=extra):
                self.assertEqual(self.scrie_ion('x', ref=dict(ok, **extra)).status_code, 201)
                self.acum += timedelta(minutes=2)
        for m in self.noi():
            self.assertEqual(m['ref'], {'tip': 'decizie', 'id': 'a', 'titlu': 'b', 'sursa': None, 'masina': None, 'mod': 'discuta'})

    def test_mod_null_nu_ocoleste_regula_raspuns_doar_la_decizie(self):
        r = self.scrie_ion('x', ref={'tip': 'item', 'id': 'a', 'titlu': 'b', 'mod': 'raspuns', 'sursa': None})
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.ref.mod', r.get_json()['error'])

    def test_null_pe_campurile_optionale_ale_lui_ion_ca_lipsa(self):
        r = self.scrie_ion('x', ref=None, tinta=None, alegere=None)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        m = self.noi()[0]
        self.assertEqual((m['ref'], m['tinta'], m['alegere']), (None, 'auto', None))
        r = self.scrie_ion('x', alegere=None, raspuns_la='m_abcdef')
        self.assertEqual(r.status_code, 201, 'alegere null = reply obisnuit, fara verificarea intrebarii')

    def test_alegere_nenula_fara_raspuns_la_ramane_400_si_cu_null_pe_raspuns_la_la_fel(self):
        for corp in ({'alegere': 'pc-job'}, {'alegere': 'pc-job', 'raspuns_la': None}):
            with self.subTest(corp=corp):
                self.assertEqual(self.scrie_ion('x', **corp).status_code, 400)

    def test_mesajele_vechi_fara_campurile_noi_se_citesc(self):
        self.scrie_randuri('fir.jsonl', [{'id': 'm_000001', 'ts': '2026-11-22T07:00:00Z', 'cine': 'ion', 'tip': 'mesaj',
                                          'text': 'vechi', 'sursa': 'scris', 'stare': 'nou'},
                                         {'id': 'm_000002', 'ts': '2026-11-22T07:00:00Z', 'cine': 'asistent', 'tip': 'info',
                                          'text': 'vechi'}])
        ion, asistent = self.vedere()['fir']
        self.assertEqual((ion['ref'], ion['tinta'], ion['optiuni'], ion['raspuns']), (None, 'auto', [], None))
        self.assertEqual((asistent['ref'], asistent['tinta'], asistent['masina']), (None, None, None))


# --------------------------------------------------------------------------- v1.1: mesajul asistentului

class MesajAsistentV11(Baza):

    def test_intrebare_cu_optiuni_masina_si_ref_se_intorc(self):
        r = self.scrie_asistent(tip='intrebare', text='Unde sa rulez?', optiuni=OPTIUNI, ref=REF)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        m = self.vedere()['fir'][0]
        self.assertEqual((m['tip'], m['optiuni'], m['ref'], m['raspuns'], m['masina'], m['tinta']),
                         ('intrebare', OPTIUNI, REF, None, None, None))

    def test_asteapta_cu_server_si_anuleaza(self):
        optiuni = [{'id': 'server', 'eticheta': 'Run on Server instead'}, {'id': 'anuleaza', 'eticheta': 'Cancel'}]
        r = self.scrie_asistent(tip='asteapta', text='PC job e oprit', optiuni=optiuni, masina='pc-job')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        m = self.vedere()['fir'][0]
        self.assertEqual((m['tip'], m['optiuni'], m['masina']), ('asteapta', optiuni, 'pc-job'))

    def test_masina_si_ref_pe_lucreaza_si_rezultat(self):
        for tip in ('lucreaza', 'rezultat'):
            with self.subTest(tip=tip):
                r = self.scrie_asistent(tip=tip, masina='ionpc', ref=dict(REF, mod='discuta'))
                self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        fir = self.vedere()['fir']
        self.assertEqual([(m['masina'], m['ref']['mod']) for m in fir], [('ionpc', 'discuta')] * 2)

    def test_campurile_noi_null_sunt_ca_lipsa(self):
        r = self.scrie_asistent(tip='info', optiuni=None, masina=None, ref=None)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        m = self.vedere()['fir'][0]
        self.assertEqual((m['optiuni'], m['masina'], m['ref']), ([], None, None))

    def test_optiuni_la_limite_trec(self):
        patru = [{'id': 'o%d' % i, 'eticheta': 'e'} for i in range(4)]
        self.assertEqual(self.scrie_asistent(tip='intrebare', optiuni=patru).status_code, 201)
        limite = [{'id': 'i' * 40, 'eticheta': 'e' * 60}]
        self.assertEqual(self.scrie_asistent(tip='asteapta', optiuni=limite).status_code, 201)

    def test_validarea_optiunilor_masinii_si_ref(self):
        o = {'id': 'pc-job', 'eticheta': 'PC job'}
        for modifica, cale in (
                ({}, 'corpul.optiuni'), ({'optiuni': None}, 'corpul.optiuni'), ({'optiuni': []}, 'corpul.optiuni'),
                ({'optiuni': 'pc-job'}, 'corpul.optiuni'), ({'optiuni': [o] * 2}, 'corpul.optiuni[1].id'),
                ({'optiuni': [dict(o, id='x%d' % i) for i in range(5)]}, 'corpul.optiuni'),
                ({'optiuni': ['pc-job']}, 'corpul.optiuni[0]'), ({'optiuni': [dict(o, x=1)]}, 'corpul.optiuni[0].x'),
                ({'optiuni': [{'eticheta': 'e'}]}, 'corpul.optiuni[0].id'),
                ({'optiuni': [{'id': 'a'}]}, 'corpul.optiuni[0].eticheta'),
                ({'optiuni': [dict(o, id='')]}, 'corpul.optiuni[0].id'), ({'optiuni': [dict(o, id=3)]}, 'corpul.optiuni[0].id'),
                ({'optiuni': [dict(o, id='i' * 41)]}, 'corpul.optiuni[0].id'),
                ({'optiuni': [dict(o, eticheta='')]}, 'corpul.optiuni[0].eticheta'),
                ({'optiuni': [dict(o, eticheta='e' * 61)]}, 'corpul.optiuni[0].eticheta'),
                ({'optiuni': [dict(o, eticheta='a\nb')]}, 'corpul.optiuni[0].eticheta'),
                ({'optiuni': [o], 'masina': 'laptop'}, 'corpul.masina'), ({'optiuni': [o], 'masina': 3}, 'corpul.masina'),
                ({'optiuni': [o], 'ref': 'x'}, 'corpul.ref'), ({'optiuni': [o], 'ref': dict(REF, tip='item')}, 'corpul.ref.mod'),
                ({'optiuni': [o], 'ref': dict(REF, x=1)}, 'corpul.ref.x')):
            with self.subTest(modifica=modifica):
                r = self.client.post('/api/asistent/fir', json=dict({'cine': 'asistent', 'tip': 'intrebare', 'text': 'x'},
                                                                    **modifica), headers=self.h(FULL))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))

    def test_optiuni_nu_trec_la_alte_tipuri(self):
        for tip in ('brief', 'alerta', 'raspuns', 'lucreaza', 'rezultat', 'info'):
            with self.subTest(tip=tip):
                r = self.scrie_asistent(tip=tip, optiuni=OPTIUNI)
                self.assertEqual(r.status_code, 400)
                self.assertIn('corpul.optiuni', r.get_json()['error'])

    def test_dispozitivul_nu_scrie_intrebari(self):
        r = self.client.post('/api/asistent/fir', json={'cine': 'asistent', 'tip': 'intrebare', 'text': 'x',
                                                         'optiuni': OPTIUNI}, headers=self.h(DEVICE))
        self.assertEqual(r.status_code, 403)

    def test_push_la_intrebare_pleaca_cu_tipul_nou(self):
        os.environ['FCM_SERVICE_ACCOUNT_FILE'] = 'x'
        self.token_push()
        with mock.patch.object(fcm, 'configurat', return_value=True), \
                mock.patch.object(fcm, 'trimite_date', return_value={'trimise': 1, 'erori': [], 'nregistrate': []}) as t:
            r = self.scrie_asistent(tip='intrebare', optiuni=OPTIUNI, push={'prioritate': 'urgent'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(t.call_args[0][1]['tip'], 'intrebare')


# --------------------------------------------------------------------------- v1.1: raspunsul la intrebare

class RaspunsLaIntrebare(Baza):

    def intreaba(self, tip='intrebare', optiuni=OPTIUNI, **camp):
        r = self.scrie_asistent(tip=tip, text='Unde sa rulez?', optiuni=optiuni, **camp)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def raspunde(self, q, alegere='pc-job', text='PC job', token=DEVICE, **camp):
        return self.client.post('/api/asistent/fir', json=dict({'text': text, 'raspuns_la': q, 'alegere': alegere}, **camp),
                                headers=self.h(token))

    def mesaj(self, id_):
        return next(m for m in self.vedere()['fir'] if m['id'] == id_)

    def test_raspunsul_se_pune_pe_intrebare_si_mesajul_intra_in_coada(self):
        q = self.intreaba()
        self.acum += timedelta(seconds=30)
        r = self.raspunde(q)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(list(r.get_json()), ['id'])
        self.assertEqual(self.mesaj(q)['raspuns'], {'optiune': 'pc-job', 'ts': '2026-11-22T08:00:30Z'})
        ion = self.noi()
        self.assertEqual(len(ion), 1)
        self.assertEqual((ion[0]['id'], ion[0]['text'], ion[0]['stare'], ion[0]['raspuns_la'], ion[0]['alegere']),
                         (r.get_json()['id'], 'PC job', 'nou', q, 'pc-job'))
        self.assertEqual(ion[0]['ts'], self.mesaj(q)['raspuns']['ts'], 'aceeasi scriere, acelasi moment')

    def test_a_doua_alegere_da_409_si_nu_schimba_nimic(self):
        q = self.intreaba()
        self.assertEqual(self.raspunde(q).status_code, 201)
        inainte = self.fisier('fir.jsonl')
        for alegere in ('pc-job', 'ionpc'):
            with self.subTest(alegere=alegere):
                r = self.raspunde(q, alegere)
                self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertEqual(self.fisier('fir.jsonl'), inainte, 'nici raspunsul, nici mesajul al doilea nu s-au scris')
        self.assertEqual(len(self.noi()), 1)

    def test_asteapta_se_raspunde_la_fel(self):
        q = self.intreaba('asteapta', [{'id': 'server', 'eticheta': 'Run on Server instead'},
                                       {'id': 'anuleaza', 'eticheta': 'Cancel'}])
        self.assertEqual(self.raspunde(q, 'anuleaza', 'Cancel').status_code, 201)
        self.assertEqual(self.mesaj(q)['raspuns']['optiune'], 'anuleaza')

    def test_alegere_straina_de_optiuni_da_400_si_intrebarea_ramane_deschisa(self):
        q = self.intreaba()
        inainte = self.fisier('fir.jsonl')
        r = self.raspunde(q, 'server')
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.alegere', r.get_json()['error'])
        self.assertEqual(self.fisier('fir.jsonl'), inainte)
        self.assertEqual(self.raspunde(q).status_code, 201, 'dupa o alegere gresita se poate raspunde bine')

    def test_intrebare_necunoscuta_404(self):
        self.assertEqual(self.raspunde('m_ffffff').status_code, 404)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))

    def test_mesaj_care_nu_e_intrebare_da_409(self):
        info = self.scrie_asistent(tip='info').get_json()['id']
        ion = self.scrie_ion('un mesaj').get_json()['id']
        for tinta in (info, ion):
            with self.subTest(tinta=tinta):
                self.assertEqual(self.raspunde(tinta).status_code, 409)
        self.assertEqual(len(self.randuri('fir.jsonl')), 2)

    def test_un_mesaj_al_lui_ion_cu_optiuni_stocate_nu_devine_intrebare(self):
        self.scrie_randuri('fir.jsonl', [{'id': 'm_000001', 'ts': '2026-11-22T07:00:00Z', 'cine': 'ion', 'tip': 'intrebare',
                                          'text': 'x', 'optiuni': OPTIUNI, 'stare': 'nou'}])
        self.assertEqual(self.raspunde('m_000001').status_code, 409)

    def test_raspuns_la_fara_alegere_ramane_un_reply_obisnuit(self):
        q = self.intreaba()
        r = self.scrie_ion('Altceva', raspuns_la=q)
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(self.mesaj(q)['raspuns'], 'fara `alegere` intrebarea ramane deschisa')

    def test_aceleasi_campuri_ref_si_tinta_merg_si_la_raspuns(self):
        q = self.intreaba()
        self.assertEqual(self.raspunde(q, ref=REF, tinta='pc-job').status_code, 201)
        m = self.noi()[0]
        self.assertEqual((m['ref'], m['tinta'], m['alegere']), (REF, 'pc-job', 'pc-job'))

    def test_limita_de_30_pe_ora_nu_scrie_nici_raspunsul_pe_intrebare(self):
        q = self.intreaba()
        for i in range(30):
            self.acum = ACUM + timedelta(seconds=i)
            self.assertEqual(self.scrie_ion('mesaj %d' % i).status_code, 201)
        self.acum = ACUM + timedelta(seconds=30)
        r = self.raspunde(q)
        self.assertEqual(r.status_code, 429)
        self.assertIsNone(self.mesaj(q)['raspuns'], 'un 429 nu lasa raspunsul pe jumatate scris')
        self.acum = ACUM + timedelta(hours=1, seconds=1)
        self.assertEqual(self.raspunde(q).status_code, 201)

    def test_o_scriere_esuata_nu_lasa_raspunsul_pe_jumatate(self):
        """Mesajul lui Ion si `raspuns` sunt in acelasi fisier si intr-o singura `_scrie_fir`: daca scrierea pica,
        niciuna nu exista; daca reuseste, exista amandoua."""
        q = self.intreaba()
        inainte = self.fisier('fir.jsonl')
        with mock.patch.object(asistent, '_scrie_atomic', side_effect=OSError('disc plin')) as scrie:
            r = self.raspunde(q)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(scrie.call_count, 1)
        self.assertEqual(self.fisier('fir.jsonl'), inainte)
        self.assertEqual(self.noi(), [])
        self.assertEqual(self.raspunde(q).status_code, 201)
        randuri = self.randuri('fir.jsonl')
        self.assertEqual(sum(1 for r in randuri if r.get('raspuns')), 1)
        self.assertEqual(sum(1 for r in randuri if r.get('alegere') == 'pc-job'), 1)

    def test_o_singura_scriere_pe_raspuns(self):
        q = self.intreaba()
        with mock.patch.object(asistent, '_scrie_atomic', wraps=asistent._scrie_atomic) as scrie:
            self.assertEqual(self.raspunde(q).status_code, 201)
        self.assertEqual([c[0][0] for c in scrie.call_args_list], ['fir.jsonl'])

    def umple(self, n, deschise=()):
        """Fir cu `n` mesaje ale asistentului, terminate; primele sunt `deschise` (randuri deja facute)."""
        randuri = list(deschise)
        randuri += [{'id': 'm_%06x' % (i + 100), 'ts': '2026-11-21T07:00:00Z', 'cine': 'asistent', 'tip': 'info',
                     'text': 'x', 'stare': None} for i in range(n - len(randuri))]
        self.scrie_randuri('fir.jsonl', randuri)

    def intrebare_veche(self, id_='m_000001', **camp):
        return dict({'id': id_, 'ts': '2026-11-21T06:00:00Z', 'cine': 'asistent', 'tip': 'intrebare', 'text': 'Unde?',
                     'optiuni': OPTIUNI, 'stare': None}, **camp)

    def test_la_plafon_intrebarea_fara_raspuns_nu_cade(self):
        for tip in ('intrebare', 'asteapta'):
            with self.subTest(tip=tip):
                self.umple(500, [self.intrebare_veche(tip=tip)])
                self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
                randuri = self.randuri('fir.jsonl')
                self.assertEqual(len(randuri), 500)
                self.assertEqual(randuri[0]['id'], 'm_000001', 'intrebarea deschisa a ramas prima')
                self.assertNotIn('m_000064', [r['id'] for r in randuri], 'a cazut cel mai vechi mesaj terminat')

    def test_la_plafon_intrebarea_cu_raspuns_cade_ca_orice_mesaj_terminat(self):
        self.umple(500, [self.intrebare_veche(raspuns={'optiune': 'pc-job', 'ts': '2026-11-21T06:01:00Z'})])
        self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
        self.assertNotIn('m_000001', [r['id'] for r in self.randuri('fir.jsonl')])

    def test_la_plafon_raspunsul_gaseste_intrebarea_si_o_pastreaza(self):
        """Raspunsul la o intrebare veche, cu firul plin, nu da 404 si nu scoate intrebarea din fir in aceeasi scriere."""
        self.umple(500, [self.intrebare_veche()])
        r = self.raspunde('m_000001')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        randuri = self.randuri('fir.jsonl')
        self.assertEqual(len(randuri), 500)
        self.assertEqual(randuri[0]['id'], 'm_000001')
        self.assertEqual(randuri[0]['raspuns']['optiune'], 'pc-job')
        self.assertEqual(randuri[-1]['alegere'], 'pc-job')
        self.assertEqual(self.raspunde('m_000001').status_code, 409, 'a doua oara 409, nu 404')

    def test_la_plafon_doar_cu_intrebari_deschise_cade_cea_mai_veche(self):
        self.umple(500, [self.intrebare_veche('m_%06x' % i) for i in range(1, 501)])
        self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
        randuri = self.randuri('fir.jsonl')
        self.assertEqual((len(randuri), randuri[0]['id'], randuri[-1]['text']), (500, 'm_000002', 'nou'))

    def test_doua_raspunsuri_deodata_unul_castiga(self):
        """Doua cereri simultane (doi workeri sau un dublu-tap): exact una trece, cealalta 409."""
        import threading
        q = self.intreaba()
        coduri = []

        def trimite(alegere):
            with self.app_module.app.test_client() as c:
                r = c.post('/api/asistent/fir', json={'text': alegere, 'raspuns_la': q, 'alegere': alegere},
                           headers=self.h(DEVICE))
                coduri.append(r.status_code)
        fire = [threading.Thread(target=trimite, args=(a,)) for a in ('pc-job', 'ionpc')]
        for f in fire:
            f.start()
        for f in fire:
            f.join()
        self.assertEqual(sorted(coduri), [201, 409])
        self.assertEqual(len(self.noi()), 1)
        self.assertEqual(self.noi()[0]['alegere'], self.mesaj(q)['raspuns']['optiune'])


# --------------------------------------------------------------------------- v1.1: prezenta

class Prezenta(Baza):

    def raporteaza(self, masina='pc-job', token=FULL, **corp):
        corp = dict({'activ': True, 'idle_s': 30}, **corp)
        return self.client.put('/api/asistent/prezenta/%s' % masina, json=corp, headers=self.h(token))

    def masini(self):
        return {m['id']: m for m in self.vedere()['masini']}

    def test_raportarea_se_scrie_atomic_cu_ultima_pusa_de_server(self):
        r = self.raporteaza('pc-job', versiune='1.2.3')
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'masina': 'pc-job'}))
        self.assertEqual(json.loads(self.fisier('prezenta.json')),
                         {'masini': {'pc-job': {'ultima': '2026-11-22T08:00:00Z', 'activ': True, 'idle_s': 30,
                                                'versiune': '1.2.3'}}})
        self.assertEqual(sorted(os.listdir(self.dir)), ['asistent.lock', 'prezenta.json'], 'niciun .tmp ramas')

    def test_o_raportare_nu_o_sterge_pe_a_celorlalte(self):
        self.raporteaza('server')
        self.raporteaza('ionpc')
        self.assertEqual(sorted(json.loads(self.fisier('prezenta.json'))['masini']), ['ionpc', 'server'])

    def test_aceeasi_cerere_de_doua_ori_lasa_aceeasi_stare(self):
        self.raporteaza()
        prima = self.fisier('prezenta.json')
        self.assertEqual(self.raporteaza().status_code, 200)
        self.assertEqual(self.fisier('prezenta.json'), prima)
        self.acum += timedelta(seconds=60)
        self.raporteaza()
        self.assertEqual(json.loads(self.fisier('prezenta.json'))['masini']['pc-job']['ultima'], '2026-11-22T08:01:00Z')

    def test_dispozitivul_403_masina_necunoscuta_404_fara_token_401(self):
        r = self.raporteaza(token=DEVICE)
        self.assertEqual(r.status_code, 403)
        self.assertIn('dispozitiv', r.get_json()['error'])
        r = self.client.put('/api/asistent/prezenta/pc-job', json={'activ': True, 'idle_s': 0})
        self.assertEqual(r.status_code, 401)
        r = self.client.put('/api/asistent/prezenta/pc-job', json={'activ': True, 'idle_s': 0}, headers=self.h('gresit'))
        self.assertEqual(r.status_code, 401)
        for masina in ('laptop', 'PC-JOB', 'auto', 'intreaba', '0'):
            with self.subTest(masina=masina):
                self.assertEqual(self.raporteaza(masina).status_code, 404)
        self.assertEqual(self.raporteaza('laptop', token=DEVICE).status_code, 403, 'tokenul de dispozitiv e refuzat inainte')
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'prezenta.json')))

    def test_sesiunea_poate_raporta(self):
        self.login()
        csrf = {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}
        r = self.client.put('/api/asistent/prezenta/ionpc', json={'activ': False, 'idle_s': 5}, headers=csrf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def test_validarea_corpului_cu_calea_campului(self):
        for corp, cale in (
                ({}, 'corpul.activ'), ({'idle_s': 1}, 'corpul.activ'), ({'activ': 'da', 'idle_s': 1}, 'corpul.activ'),
                ({'activ': 1, 'idle_s': 1}, 'corpul.activ'), ({'activ': None, 'idle_s': 1}, 'corpul.activ'),
                ({'activ': True}, 'corpul.idle_s'), ({'activ': True, 'idle_s': -1}, 'corpul.idle_s'),
                ({'activ': True, 'idle_s': -0.5}, 'corpul.idle_s'), ({'activ': True, 'idle_s': '5'}, 'corpul.idle_s'),
                ({'activ': True, 'idle_s': 1e30}, 'corpul.idle_s'), ({'activ': True, 'idle_s': [1]}, 'corpul.idle_s'),
                ({'activ': True, 'idle_s': True}, 'corpul.idle_s'), ({'activ': True, 'idle_s': None}, 'corpul.idle_s'),
                ({'activ': True, 'idle_s': 10 ** 9 + 1}, 'corpul.idle_s'),
                ({'activ': True, 'idle_s': 1, 'versiune': 'v' * 41}, 'corpul.versiune'),
                ({'activ': True, 'idle_s': 1, 'versiune': ''}, 'corpul.versiune'),
                ({'activ': True, 'idle_s': 1, 'versiune': 3}, 'corpul.versiune'),
                ({'activ': True, 'idle_s': 1, 'versiune': '  '}, 'corpul.versiune'),
                ({'activ': True, 'idle_s': 1, 'x': 1}, 'corpul.x'), ({'activ': True, 'idle_s': 1, 'ultima': 'x'}, 'corpul.ultima')):
            with self.subTest(corp=corp):
                r = self.client.put('/api/asistent/prezenta/server', json=corp, headers=self.h())
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        for corp in ([], 'x', None, 5):
            with self.subTest(corp=corp):
                self.assertEqual(self.client.put('/api/asistent/prezenta/server', json=corp, headers=self.h()).status_code, 400)
        r = self.client.put('/api/asistent/prezenta/server', data='nu e json', headers=self.h())
        self.assertEqual(r.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'prezenta.json')))

    def test_idle_s_float_se_rotunjeste_in_jos(self):
        for trimis, stocat, idle_min in ((0.0, 0, 0), (0.9, 0, 0), (59.999, 59, 0), (119.5, 119, 1), (900.0, 900, 15),
                                         (900.4, 900, 15), (901.0, 901, 15), (1e9, 10 ** 9, 16666666)):
            with self.subTest(idle_s=trimis):
                r = self.raporteaza('ionpc', idle_s=trimis)
                self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
                rand = json.loads(self.fisier('prezenta.json'))['masini']['ionpc']
                self.assertEqual((rand['idle_s'], type(rand['idle_s'])), (stocat, int))
                self.assertEqual(self.masini()['ionpc']['idle_min'], idle_min)
        self.raporteaza('ionpc', idle_s=900.9)
        self.assertEqual(self.masini()['ionpc']['stare'], 'activ', '900.9 -> 900, inca activ')
        self.raporteaza('ionpc', idle_s=901.0)
        self.assertEqual(self.masini()['ionpc']['stare'], 'online')

    def test_idle_s_nan_si_infinit_dau_400(self):
        for literal in ('NaN', 'Infinity', '-Infinity', '-0.5', '-1', '1e400'):
            with self.subTest(literal=literal):
                r = self.client.put('/api/asistent/prezenta/server', data='{"activ": true, "idle_s": %s}' % literal,
                                    headers=dict(self.h(), **{'Content-Type': 'application/json'}))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'prezenta.json')))

    def test_versiune_null_ca_lipsa(self):
        self.assertEqual(self.raporteaza('server', versiune=None).status_code, 200)
        self.assertIsNone(json.loads(self.fisier('prezenta.json'))['masini']['server']['versiune'])

    def test_valorile_la_limita_trec(self):
        self.assertEqual(self.raporteaza(idle_s=0, versiune='v' * 40).status_code, 200)
        self.assertEqual(self.raporteaza(idle_s=10 ** 9, activ=False).status_code, 200)

    def test_corp_prea_mare_413(self):
        r = self.client.put('/api/asistent/prezenta/server', data=b'{"activ": true, "idle_s": 1, "versiune": "' + b'a' * 40000 + b'"}',
                            headers=dict(self.h(), **{'Content-Type': 'application/json'}))
        self.assertEqual(r.status_code, 413)

    def test_fara_nicio_raportare_toate_trei_sunt_offline_in_ordine_fixa(self):
        m = self.vedere()['masini']
        self.assertEqual([(x['id'], x['nume'], x['stare'], x['ultima'], x['idle_min']) for x in m],
                         [('server', 'Server', 'offline', None, None), ('pc-job', 'PC job', 'offline', None, None),
                          ('ionpc', 'IONPC', 'offline', None, None)])

    def test_ordinea_nu_depinde_de_ordinea_raportarilor(self):
        for masina in ('ionpc', 'server', 'pc-job'):
            self.raporteaza(masina)
        self.assertEqual([m['id'] for m in self.vedere()['masini']], ['server', 'pc-job', 'ionpc'])

    def test_activ_cand_a_raportat_acum_cu_activ_true_si_idle_mic(self):
        self.raporteaza('pc-job', activ=True, idle_s=119)
        self.assertEqual(self.masini()['pc-job'], {'id': 'pc-job', 'nume': 'PC job', 'stare': 'activ',
                                                   'ultima': '2026-11-22T08:00:00Z', 'idle_min': 1})
        self.assertEqual(self.masini()['server']['stare'], 'offline', 'celelalte nu se schimba')

    def test_pragul_de_180_s_online_pana_la_180_inclusiv(self):
        self.raporteaza('server', activ=False, idle_s=10)
        for secunde, stare in ((0, 'online'), (179, 'online'), (180, 'online'), (181, 'offline'), (3600, 'offline')):
            with self.subTest(secunde=secunde):
                self.acum = ACUM + timedelta(seconds=secunde)
                m = self.masini()['server']
                self.assertEqual(m['stare'], stare)
                self.assertEqual(m['ultima'], '2026-11-22T08:00:00Z', 'ultima ramane si cand e offline')

    def test_pragul_de_180_s_se_aplica_si_cand_e_activ(self):
        self.raporteaza('server', activ=True, idle_s=0)
        self.acum = ACUM + timedelta(seconds=180)
        self.assertEqual(self.masini()['server']['stare'], 'activ')
        self.acum = ACUM + timedelta(seconds=181)
        self.assertEqual(self.masini()['server']['stare'], 'offline')

    def test_pragul_de_900_s_de_inactivitate(self):
        for idle_s, stare in ((899, 'activ'), (900, 'activ'), (901, 'online'), (5000, 'online')):
            with self.subTest(idle_s=idle_s):
                self.raporteaza('ionpc', activ=True, idle_s=idle_s)
                self.assertEqual(self.masini()['ionpc']['stare'], stare)

    def test_activ_fals_e_online_oricat_de_mic_ar_fi_idle(self):
        self.raporteaza('ionpc', activ=False, idle_s=0)
        self.assertEqual(self.masini()['ionpc']['stare'], 'online')

    def test_idle_min_se_rotunjeste_in_jos_si_e_null_cand_e_offline(self):
        self.raporteaza('pc-job', activ=True, idle_s=3599)
        self.assertEqual(self.masini()['pc-job']['idle_min'], 59)
        self.raporteaza('pc-job', activ=True, idle_s=59)
        self.assertEqual(self.masini()['pc-job']['idle_min'], 0)
        self.acum = ACUM + timedelta(seconds=181)
        self.assertIsNone(self.masini()['pc-job']['idle_min'])

    def test_masina_revine_dupa_ce_a_fost_offline(self):
        self.raporteaza('pc-job')
        self.acum = ACUM + timedelta(hours=2)
        self.assertEqual(self.masini()['pc-job']['stare'], 'offline')
        self.raporteaza('pc-job')
        self.assertEqual(self.masini()['pc-job']['stare'], 'activ')

    def test_ceasul_serverului_in_urma_nu_da_offline(self):
        """O raportare cu `ultima` in viitor fata de `acum` (ceas dat inapoi) nu o scoate din online."""
        self.raporteaza('server')
        self.acum = ACUM - timedelta(seconds=30)
        self.assertEqual(self.masini()['server']['stare'], 'activ')

    def test_fisierul_de_prezenta_stricat_nu_da_500_si_se_reia(self):
        os.makedirs(self.dir, exist_ok=True)
        for continut in (b'nu e json', b'[]', b'{"masini": []}', b'\xff\xfe'):
            with self.subTest(continut=continut):
                with open(os.path.join(self.dir, 'prezenta.json'), 'wb') as fh:
                    fh.write(continut)
                self.assertEqual([m['stare'] for m in self.vedere()['masini']], ['offline'] * 3)
                self.assertEqual(self.raporteaza('server').status_code, 200)
                self.assertEqual(self.masini()['server']['stare'], 'activ')

    def test_intrari_cu_alta_forma_se_ignora(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'prezenta.json'), 'w', encoding='utf-8') as fh:
            json.dump({'masini': {'server': 'x', 'pc-job': {'ultima': 'ieri', 'activ': True, 'idle_s': 1},
                                  'ionpc': {'ultima': '2026-11-22T08:00:00Z', 'activ': True, 'idle_s': 'mult'},
                                  'altceva': {'ultima': '2026-11-22T08:00:00Z', 'activ': True, 'idle_s': 1}}}, fh)
        m = self.masini()
        self.assertEqual((m['server']['stare'], m['pc-job']['stare']), ('offline', 'offline'))
        self.assertEqual((m['ionpc']['stare'], m['ionpc']['idle_min']), ('online', None))
        self.assertEqual(len(self.vedere()['masini']), 3)

    def test_fisier_ilizibil_la_scriere_da_500_si_nu_rescrie(self):
        self.raporteaza('server')
        inainte = self.fisier('prezenta.json')
        with mock.patch.object(asistent, '_citeste_prezenta', side_effect=OSError('permisiuni')):
            self.assertEqual(self.raporteaza('ionpc').status_code, 500)
        self.assertEqual(self.fisier('prezenta.json'), inainte)

    def test_get_nu_arata_versiunea_si_toti_cititorii_vad_masinile(self):
        self.raporteaza('server', versiune='9.9')
        for token in (FULL, DEVICE):
            m = self.vedere(token)['masini'][0]
            self.assertEqual(set(m), {'id', 'nume', 'stare', 'ultima', 'idle_min'})


class PrezentaClaude(Baza):
    """v1.3: `claude` optional in prezenta = loginul Claude CLI al masinii (`claude auth status`). Compatibil in ambele sensuri: un client care
    nu-l trimite nu schimba nimic (cheia lipseste din GET), iar cel care il trimite e validat strict."""

    def raporteaza(self, masina='pc-job', token=FULL, **corp):
        corp = dict({'activ': True, 'idle_s': 30}, **corp)
        return self.client.put('/api/asistent/prezenta/%s' % masina, json=corp, headers=self.h(token))

    def masini(self):
        return {m['id']: m for m in self.vedere()['masini']}

    CL = {'logat': False, 'expira': None, 'verificat': '2026-11-22T08:00:00Z'}

    def test_claude_se_stocheaza_si_apare_in_get_doar_la_masina_care_l_a_raportat(self):
        r = self.raporteaza('ionpc', claude=dict(self.CL, expira='2026-12-01T00:00:00Z', logat=True))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.raporteaza('server')
        rand = json.loads(self.fisier('prezenta.json'))['masini']
        self.assertEqual(rand['ionpc']['claude'], {'logat': True, 'expira': '2026-12-01T00:00:00Z', 'verificat': '2026-11-22T08:00:00Z'})
        self.assertNotIn('claude', rand['server'], 'un client vechi: fisierul ramane cum era')
        m = self.masini()
        self.assertEqual(m['ionpc']['claude'], {'logat': True, 'expira': '2026-12-01T00:00:00Z', 'verificat': '2026-11-22T08:00:00Z'})
        self.assertNotIn('claude', m['server'])
        self.assertNotIn('claude', m['pc-job'], 'nereportata niciodata: nici cheia')
        self.assertEqual(set(m['server']), {'id', 'nume', 'stare', 'ultima', 'idle_min'}, 'forma veche, neschimbata')

    def test_claude_delogat_si_campurile_optionale_lipsa_se_intorc_ca_null(self):
        self.assertEqual(self.raporteaza('ionpc', claude={'logat': False}).status_code, 200)
        self.assertEqual(self.masini()['ionpc']['claude'], {'logat': False, 'expira': None, 'verificat': None})
        self.assertEqual(self.raporteaza('ionpc', claude=None).status_code, 200, 'null = lipsa')
        self.assertNotIn('claude', self.masini()['ionpc'])

    def test_claude_idempotent_si_ultima_raportare_inlocuieste_pe_cea_veche(self):
        self.raporteaza('pc-job', claude=self.CL)
        prima = self.fisier('prezenta.json')
        self.assertEqual(self.raporteaza('pc-job', claude=self.CL).status_code, 200)
        self.assertEqual(self.fisier('prezenta.json'), prima)
        self.raporteaza('pc-job', claude=dict(self.CL, logat=True))
        self.assertTrue(self.masini()['pc-job']['claude']['logat'], 'raportarea de acum a inlocuit-o pe cea de dinainte')

    def test_claude_invalid_da_400_cu_calea_si_nu_atinge_fisierul(self):
        for claude, cale in (({}, 'corpul.claude.logat'), ({'logat': 'da'}, 'corpul.claude.logat'), ({'logat': 1}, 'corpul.claude.logat'),
                             ({'logat': True, 'x': 1}, 'corpul.claude.x'), ({'logat': True, 'expira': 'maine'}, 'corpul.claude.expira'),
                             ({'logat': True, 'verificat': 5}, 'corpul.claude.verificat'), ('logat', 'corpul.claude'), ([True], 'corpul.claude'),
                             ({'logat': True, 'expira': '2026-12-01'}, 'corpul.claude.expira')):
            with self.subTest(claude=claude):
                r = self.raporteaza('ionpc', claude=claude)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(cale, r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'prezenta.json')))

    def test_un_rand_stocat_cu_claude_stricat_nu_strica_get(self):
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, 'prezenta.json'), 'w', encoding='utf-8') as fh:
            json.dump({'masini': {'ionpc': {'ultima': '2026-11-22T08:00:00Z', 'activ': True, 'idle_s': 1, 'versiune': None, 'claude': 'x'},
                                  'server': {'ultima': '2026-11-22T08:00:00Z', 'activ': True, 'idle_s': 1, 'versiune': None,
                                             'claude': {'logat': 'da'}}}}, fh)
        m = self.masini()
        self.assertNotIn('claude', m['ionpc'])
        self.assertNotIn('claude', m['server'])


# --------------------------------------------------------------------------- v1.2: detaliile unui mesaj

class Detalii(Baza):

    MD = '# Raport\n\nAm facut **ceva**.\n\n- unu\n- doi\n'

    def mesaj_asistent(self, **camp):
        r = self.scrie_asistent(tip='rezultat', text='Gata, am facut ceva', **camp)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def pune_detalii(self, id_, detalii, token=FULL):
        return self.client.put('/api/asistent/fir/%s/detalii' % id_, json={'detalii': detalii}, headers=self.h(token))

    def citeste(self, id_, token=DEVICE):
        return self.client.get('/api/asistent/fir/%s/detalii' % id_, headers=self.h(token))

    def pe_disc(self):
        d = os.path.join(self.dir, 'detalii')
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    def are(self, id_):
        return next(m for m in self.vedere()['fir'] if m['id'] == id_)['are_detalii']

    def umple(self, n):
        """Fir cu `n` mesaje terminate ale asistentului, id-uri m_000064, m_000065, ..."""
        self.scrie_randuri('fir.jsonl', [{'id': 'm_%06x' % (i + 100), 'ts': '2026-11-21T07:00:00Z', 'cine': 'asistent',
                                          'tip': 'info', 'text': 'x', 'stare': None} for i in range(n)])

    # ----- la POST

    def test_post_cu_detalii_scrie_fisierul_si_nu_il_pune_in_fir(self):
        r = self.scrie_asistent(tip='rezultat', text='Gata', detalii='  \n' + self.MD + '\n  ')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.assertEqual(sorted(r.get_json()), ['id', 'push'])
        id_ = r.get_json()['id']
        self.assertEqual(self.pe_disc(), [id_ + '.md'])
        self.assertEqual(self.fisier('detalii/%s.md' % id_).decode('utf-8'), self.MD.strip(), 'se stocheaza dupa strip')
        self.assertNotIn('detalii', self.randuri('fir.jsonl')[0])
        self.assertNotIn(b'Raport', self.fisier('fir.jsonl'))
        m = next(m for m in self.vedere()['fir'] if m['id'] == id_)
        self.assertTrue(m['are_detalii'])
        self.assertNotIn('detalii', m, 'GET-ul ramane mic: doar are_detalii')
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(self.dir, 'detalii', id_ + '.md')).st_mode), 0o600)

    def test_post_cu_detalii_null_sau_fara_ele_nu_scrie_nimic(self):
        a = self.mesaj_asistent(detalii=None)
        b = self.mesaj_asistent()
        self.assertEqual(self.pe_disc(), [])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'detalii')), 'directorul se creeaza doar la nevoie')
        self.assertEqual((self.are(a), self.are(b)), (False, False))

    def test_post_cu_detalii_valide_la_limita(self):
        for nume, detalii, asteptat in (('exact 65536', 'a' * 65536, 65536), ('cu spatii la capete', ' \n' + 'b' * 65536 + '\t ', 65536),
                                        ('un caracter', 'x', 1), ('diacritice si emoji', 'ț ă î ș \U0001F600' * 3000, None)):
            with self.subTest(nume):
                id_ = self.mesaj_asistent(detalii=detalii)
                continut = self.fisier('detalii/%s.md' % id_).decode('utf-8')
                self.assertEqual(continut, detalii.strip())
                if asteptat:
                    self.assertEqual(len(continut), asteptat)

    def test_post_cu_detalii_invalide_da_400_cu_calea_si_nu_scrie_nimic(self):
        cazuri = (('numar', 5), ('lista', ['a']), ('obiect', {'a': 1}), ('bool', True), ('gol', ''),
                  ('numai spatii', ' \n\t '), ('65537', 'a' * 65537), ('65537 cu spatii', ' ' + 'a' * 65537),
                  ('surogat', 'ok \ud83d rau'))
        for nume, detalii in cazuri:
            with self.subTest(nume):
                r = self.client.post('/api/asistent/fir', headers=self.h(FULL),
                                     data=json.dumps({'cine': 'asistent', 'tip': 'rezultat', 'text': 'x', 'detalii': detalii}),
                                     content_type='application/json')
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('corpul.detalii', r.get_json()['error'])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')), 'niciun mesaj scris')
        self.assertEqual(self.pe_disc(), [])

    def test_detalii_pe_mesajul_lui_ion_da_400(self):
        for token, extra in ((DEVICE, {}), (FULL, {'cine': 'ion'})):
            with self.subTest(token=token):
                r = self.client.post('/api/asistent/fir', json=dict({'text': 'salut', 'detalii': 'x'}, **extra), headers=self.h(token))
                self.assertEqual(r.status_code, 400)
                self.assertIn('corpul.detalii', r.get_json()['error'])
        self.assertEqual(self.pe_disc(), [])

    def test_corpul_cel_mare_trece_doar_la_mesajul_asistentului(self):
        mare = '\U0001F600' * 65536                              # 65 536 de caractere = ~786 KB scapate in JSON
        id_ = self.mesaj_asistent(detalii=mare)
        self.assertEqual(self.citeste(id_).get_json()['detalii'], mare)
        self.assertEqual(self.scrie_ion('x' * 40000).status_code, 413, 'mesajul lui Ion are tot plafonul de 32 KB')
        r = self.client.post('/api/asistent/fir', data=b'{"cine":"asistent","tip":"info","text":"' + b'a' * (1024 * 1024) + b'"}',
                             content_type='application/json', headers=self.h(FULL))
        self.assertEqual(r.status_code, 413)

    def test_cererea_trimisa_de_doua_ori_dubleaza_mesajul_si_fisierul(self):
        a, b = (self.mesaj_asistent(detalii=self.MD) for _ in range(2))
        self.assertNotEqual(a, b)
        self.assertEqual(self.pe_disc(), sorted([a + '.md', b + '.md']))

    def test_scrierea_firului_care_pica_nu_lasa_fisier(self):
        inainte = self.mesaj_asistent()
        fir = self.fisier('fir.jsonl')
        with mock.patch.object(asistent, '_scrie_fir', side_effect=OSError('disc plin')):
            r = self.scrie_asistent(tip='rezultat', text='x', detalii=self.MD)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(self.pe_disc(), [])
        self.assertEqual(self.fisier('fir.jsonl'), fir)
        self.assertTrue(inainte)

    def test_scrierea_fisierului_care_pica_da_500_fara_mesaj(self):
        with mock.patch.object(asistent, '_scrie_detalii', side_effect=OSError('permisiuni')):
            r = self.scrie_asistent(tip='rezultat', text='x', detalii=self.MD)
        self.assertEqual(r.status_code, 500)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'fir.jsonl')))

    # ----- PUT

    def test_put_pune_inlocuieste_si_sterge(self):
        id_ = self.mesaj_asistent()
        self.assertFalse(self.are(id_))
        r = self.pune_detalii(id_, '\n' + self.MD)
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'id': id_, 'are_detalii': True}))
        self.assertTrue(self.are(id_))
        self.assertEqual(self.fisier('detalii/%s.md' % id_).decode('utf-8'), self.MD.strip())
        self.assertEqual(self.pune_detalii(id_, 'Nou').get_json()['are_detalii'], True)
        self.assertEqual(self.fisier('detalii/%s.md' % id_), b'Nou')
        r = self.pune_detalii(id_, None)
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'id': id_, 'are_detalii': False}))
        self.assertEqual(self.pe_disc(), [])
        self.assertFalse(self.are(id_))
        self.assertEqual(self.pune_detalii(id_, None).status_code, 200, 'null pe un mesaj fara detalii e tot 200')
        self.assertEqual(self.citeste(id_).status_code, 404)

    def test_put_aceeasi_cerere_de_doua_ori_lasa_acelasi_fisier(self):
        id_ = self.mesaj_asistent()
        self.pune_detalii(id_, self.MD)
        prima = self.fisier('detalii/%s.md' % id_)
        self.acum += timedelta(seconds=90)
        self.assertEqual(self.pune_detalii(id_, self.MD).status_code, 200)
        self.assertEqual(self.fisier('detalii/%s.md' % id_), prima)
        self.assertEqual(self.pe_disc(), [id_ + '.md'], 'niciun .tmp ramas')
        self.assertEqual(self.citeste(id_).get_json()['ts'], '2026-11-22T08:01:30Z', 'doar ts avanseaza')

    def test_put_nu_atinge_firul(self):
        id_ = self.mesaj_asistent()
        fir = self.fisier('fir.jsonl')
        self.pune_detalii(id_, self.MD)
        self.assertEqual(self.fisier('fir.jsonl'), fir)

    def test_put_mesaj_necunoscut_404_si_mesajul_lui_ion_409(self):
        self.mesaj_asistent()
        ion = self.scrie_ion().get_json()['id']
        for id_, status in (('m_abcdef', 404), (ion, 409)):
            with self.subTest(id_=id_):
                r = self.pune_detalii(id_, 'x')
                self.assertEqual(r.status_code, status, r.get_data(as_text=True))
                self.assertEqual(self.pune_detalii(id_, None).status_code, status, 'si null verifica mesajul')
        self.assertEqual(self.pe_disc(), [])

    def test_put_acces(self):
        id_ = self.mesaj_asistent()
        self.assertEqual(self.pune_detalii(id_, 'x', token=DEVICE).status_code, 403)
        self.assertEqual(self.pune_detalii(id_, 'x', token=None).status_code, 401)
        self.assertEqual(self.pune_detalii(id_, 'x', token='gresit').status_code, 401)
        self.assertEqual(self.pe_disc(), [])

    def test_put_cu_sesiune_trece(self):
        id_ = self.mesaj_asistent()
        self.login()
        self.client.get('/api/asistent')
        csrf = {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}
        r = self.client.put('/api/asistent/fir/%s/detalii' % id_, json={'detalii': 'din sesiune'}, headers=csrf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.client.get('/api/asistent/fir/%s/detalii' % id_).get_json()['detalii'], 'din sesiune')

    def test_put_corp_invalid_da_400_si_lasa_fisierul_vechi(self):
        id_ = self.mesaj_asistent(detalii='vechi')
        cazuri = (('lipsa cheii', {}), ('camp necunoscut', {'detalii': 'x', 'alt': 1}), ('numar', {'detalii': 7}),
                  ('lista', {'detalii': []}), ('gol', {'detalii': ''}), ('spatii', {'detalii': '  \n'}),
                  ('65537', {'detalii': 'a' * 65537}), ('lista in loc de obiect', ['x']))
        for nume, corp in cazuri:
            with self.subTest(nume):
                r = self.client.put('/api/asistent/fir/%s/detalii' % id_, json=corp, headers=self.h(FULL))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('corpul', r.get_json()['error'])
        r = self.client.put('/api/asistent/fir/%s/detalii' % id_, headers=self.h(FULL),
                            data='{"detalii": "a\\ud83db"}', content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.detalii', r.get_json()['error'])
        self.assertEqual(self.client.put('/api/asistent/fir/%s/detalii' % id_, headers=self.h(FULL), data='nu e json',
                                         content_type='application/json').status_code, 400)
        self.assertEqual(self.fisier('detalii/%s.md' % id_), b'vechi')

    def test_put_la_limita_si_peste_ea(self):
        id_ = self.mesaj_asistent()
        self.assertEqual(self.pune_detalii(id_, 'a' * 65536).status_code, 200)
        self.assertEqual(self.pune_detalii(id_, 'a' * 65536 + ' \n').status_code, 200)
        self.assertEqual(self.pune_detalii(id_, 'a' * 65537).status_code, 400)
        r = self.client.put('/api/asistent/fir/%s/detalii' % id_, headers=self.h(FULL), content_type='application/json',
                            data=b'{"detalii": "' + b'a' * (1024 * 1024) + b'"}')
        self.assertEqual(r.status_code, 413)
        self.assertEqual(len(self.fisier('detalii/%s.md' % id_)), 65536)

    def test_put_eroare_de_disc_da_500_si_pastreaza_ce_era(self):
        id_ = self.mesaj_asistent(detalii='vechi')
        with mock.patch.object(asistent, '_scrie_atomic', side_effect=OSError('disc plin')):
            r = self.pune_detalii(id_, 'nou')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(self.fisier('detalii/%s.md' % id_), b'vechi')

    def test_put_cu_firul_ilizibil_da_500_fara_scriere(self):
        id_ = self.mesaj_asistent()
        with mock.patch.object(asistent, '_citeste_fir', side_effect=OSError('permisiuni')):
            self.assertEqual(self.pune_detalii(id_, 'x').status_code, 500)
        self.assertEqual(self.pe_disc(), [])

    # ----- id-ul nu poate iesi din detalii/

    ID_RELE = ('..', '.', '..%2f..%2fregistru', '%2e%2e', 'm_abcdef%2f..%2f..%2fregistru', 'm_abcdef%5c..', 'm_abcdef%00',
               'm_abcdef%0a', 'm_abcde', 'm_' + 'a' * 17, 'M_ABCDEF', 'm_abcdeg', 'm_abcdef.md', ' m_abcdef', 'registru.json',
               'm_abcdef/..', 'm_abcdef/../../registru')

    def test_id_cu_traversare_de_cale_da_404_si_nu_scrie_nimic(self):
        self.mesaj_asistent()
        lista = sorted(os.listdir(self.dir))
        radacina = sorted(os.listdir(os.path.dirname(self.dir)))
        for id_ in self.ID_RELE:
            for metoda, token, corp in (('put', FULL, {'detalii': 'x'}), ('put', FULL, {'detalii': None}), ('get', DEVICE, None),
                                        ('get', FULL, None)):
                with self.subTest(id_=id_, metoda=metoda, token=token):
                    r = self.client.open('/api/asistent/fir/%s/detalii' % id_, method=metoda.upper(), json=corp, headers=self.h(token))
                    self.assertEqual(r.status_code, 404, r.get_data(as_text=True))
        self.assertEqual(sorted(os.listdir(self.dir)), lista, 'nimic nou in directorul asistentului')
        self.assertEqual(sorted(os.listdir(os.path.dirname(self.dir))), radacina, 'nimic in afara lui')

    def test_functiile_de_disc_refuza_singure_un_id_rau(self):
        for id_ in ('..', '../x', 'm_abcdef/../x', 'm_abc', 'm_abcdef\n', '', None, 5, 'm_abcdef.md'):
            with self.subTest(id_=id_):
                for f in (asistent._nume_detalii, asistent._citeste_detalii, asistent._sterge_detalii):
                    with self.assertRaises(ValueError):
                        f(id_)
                with self.assertRaises(ValueError):
                    asistent._scrie_detalii(id_, 'x')
        self.assertEqual(asistent._nume_detalii('m_abcdef'), os.path.join('detalii', 'm_abcdef.md'))

    def test_un_fisier_strain_din_director_nu_se_numara_ca_detalii(self):
        id_ = self.mesaj_asistent()
        os.makedirs(os.path.join(self.dir, 'detalii'))
        for nume in (id_ + '.txt', id_ + '.md.abc123.tmp', 'x.md', id_ + '.md.bak'):
            with open(os.path.join(self.dir, 'detalii', nume), 'w') as fh:
                fh.write('x')
        self.assertFalse(self.are(id_))
        self.assertEqual(self.citeste(id_).status_code, 404)

    # ----- GET

    def test_get_intoarce_id_detalii_si_ts_la_toate_felurile_de_acces(self):
        id_ = self.mesaj_asistent()
        self.pune_detalii(id_, self.MD)
        asteptat = {'id': id_, 'detalii': self.MD.strip(), 'ts': '2026-11-22T08:00:00Z'}
        for token in (DEVICE, FULL):
            with self.subTest(token=token):
                r = self.citeste(id_, token)
                self.assertEqual((r.status_code, r.get_json()), (200, asteptat))
        self.login()
        self.assertEqual(self.client.get('/api/asistent/fir/%s/detalii' % id_).get_json(), asteptat)

    def test_get_ts_e_momentul_scrierii(self):
        id_ = self.mesaj_asistent()
        self.acum = ACUM + timedelta(hours=3, minutes=7, seconds=9)
        self.pune_detalii(id_, 'x')
        self.assertEqual(self.citeste(id_).get_json()['ts'], '2026-11-22T11:07:09Z')

    def test_get_diacritice_emoji_si_sfarsituri_de_linie_se_intorc_intacte(self):
        text = 'Titlu ăîșțâ \U0001F600\r\n\r\n```py\nprint(1)\n```\n\ttab\n\u2028 sep'
        id_ = self.mesaj_asistent()
        self.pune_detalii(id_, text)
        self.assertEqual(self.citeste(id_).get_json()['detalii'], text.strip())

    def test_get_404_mesaj_necunoscut_fara_detalii_sau_al_lui_ion(self):
        fara = self.mesaj_asistent()
        ion = self.scrie_ion().get_json()['id']
        for id_, motiv in (('m_abcdef', 'necunoscut'), (fara, 'nu are detalii'), (ion, 'nu are detalii')):
            with self.subTest(id_=id_):
                r = self.citeste(id_)
                self.assertEqual(r.status_code, 404)
                self.assertIn(motiv, r.get_json()['error'])

    def test_get_fisier_fara_mesaj_in_fir_da_404(self):
        os.makedirs(os.path.join(self.dir, 'detalii'))
        with open(os.path.join(self.dir, 'detalii', 'm_abcdef.md'), 'w') as fh:
            fh.write('orfan')
        self.assertEqual(self.citeste('m_abcdef').status_code, 404)

    def test_get_fisier_stricat_da_500(self):
        id_ = self.mesaj_asistent(detalii='x')
        with open(os.path.join(self.dir, 'detalii', id_ + '.md'), 'wb') as fh:
            fh.write(b'\xff\xfe')
        self.assertEqual(self.citeste(id_).status_code, 500)

    # ----- are_detalii

    def test_are_detalii_e_false_pe_mesajele_vechi_si_pe_cele_ale_lui_ion(self):
        self.scrie_randuri('fir.jsonl', [
            {'id': 'm_000001', 'ts': '2026-11-20T07:00:00Z', 'cine': 'asistent', 'tip': 'rezultat', 'text': 'vechi',
             'link': 'inbox/claude/2026-11-20_x.md', 'stare': None},
            {'id': 'm_000002', 'ts': '2026-11-20T07:01:00Z', 'cine': 'ion', 'tip': 'mesaj', 'text': 'bun', 'stare': 'nou'}])
        self.assertEqual([m['are_detalii'] for m in self.vedere()['fir']], [False, False])
        self.assertEqual([m['are_detalii'] for m in self.noi()], [False])
        self.assertEqual(self.vedere(FULL)['fir'][0]['are_detalii'], False)

    def test_are_detalii_pe_get_si_pe_fir_noi(self):
        a = self.mesaj_asistent()
        b = self.mesaj_asistent()
        self.pune_detalii(b, 'x')
        self.assertEqual([m['are_detalii'] for m in self.vedere()['fir']], [False, True])
        self.assertEqual(a != b, True)
        self.assertEqual(self.noi(), [])
        self.scrie_ion()
        self.assertEqual([m['are_detalii'] for m in self.noi()], [False])

    def test_directorul_de_detalii_ilizibil_nu_strica_get_ul(self):
        self.mesaj_asistent()
        with mock.patch.object(asistent.os, 'listdir', side_effect=PermissionError('x')):
            self.assertEqual([m['are_detalii'] for m in self.vedere()['fir']], [False])

    # ----- plafonul de 500 si cursa

    def test_la_plafon_mesajul_scos_isi_pierde_fisierul(self):
        self.umple(500)
        for id_ in ('m_000064', 'm_000065', 'm_000200'):
            self.assertEqual(self.pune_detalii(id_, 'detalii ' + id_).status_code, 200)
        self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
        randuri = self.randuri('fir.jsonl')
        self.assertEqual((len(randuri), randuri[0]['id']), (500, 'm_000065'))
        self.assertEqual(self.pe_disc(), ['m_000065.md', 'm_000200.md'])
        self.assertEqual(self.citeste('m_000064').status_code, 404)
        self.assertEqual(self.pune_detalii('m_000064', 'tarziu').status_code, 404)
        self.assertEqual(self.pe_disc(), ['m_000065.md', 'm_000200.md'], 'PUT-ul pe un mesaj scos nu lasa orfan')
        self.assertEqual(self.citeste('m_000065').get_json()['detalii'], 'detalii m_000065')

    def test_la_plafon_mesajul_lui_ion_scoate_si_el_fisierul(self):
        self.umple(500)
        self.pune_detalii('m_000064', 'x')
        self.assertEqual(self.scrie_ion().status_code, 201)
        self.assertEqual(self.pe_disc(), [])

    def test_la_plafon_cu_toate_deschise_cade_cea_mai_veche_cu_fisierul_ei(self):
        self.scrie_randuri('fir.jsonl', [{'id': 'm_%06x' % i, 'ts': '2026-11-21T06:00:00Z', 'cine': 'asistent', 'tip': 'intrebare',
                                          'text': 'Unde?', 'optiuni': [{'id': 'server', 'eticheta': 'Server'}], 'stare': None}
                                         for i in range(1, 501)])
        self.pune_detalii('m_000001', 'a')
        self.pune_detalii('m_000002', 'b')
        self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
        self.assertEqual(self.pe_disc(), ['m_000002.md'])

    def test_la_plafon_mesajele_pastrate_isi_tin_fisierul(self):
        """Intrebarea deschisa nu cade la plafon si nici fisierul ei."""
        self.scrie_randuri('fir.jsonl', [{'id': 'm_000001', 'ts': '2026-11-21T06:00:00Z', 'cine': 'asistent', 'tip': 'intrebare',
                                          'text': 'Unde?', 'optiuni': [{'id': 'server', 'eticheta': 'Server'}], 'stare': None}]
                          + [{'id': 'm_%06x' % (i + 100), 'ts': '2026-11-21T07:00:00Z', 'cine': 'asistent', 'tip': 'info',
                              'text': 'x', 'stare': None} for i in range(499)])
        self.pune_detalii('m_000001', 'ramane')
        self.pune_detalii('m_000064', 'cade')
        self.scrie_asistent(text='nou')
        self.assertEqual(self.pe_disc(), ['m_000001.md'])

    def test_fisierele_fara_mesaj_se_matura_la_urmatoarea_scriere_a_firului(self):
        id_ = self.mesaj_asistent(detalii='ramane')
        d = os.path.join(self.dir, 'detalii')
        for nume in ('m_ffffff.md', 'm_0123456789abcdef.md'):
            with open(os.path.join(d, nume), 'w') as fh:
                fh.write('orfan')
        for nume in ('README.txt', 'm_ffffff.md.a1b2c3.tmp'):
            with open(os.path.join(d, nume), 'w') as fh:
                fh.write('nu e fisier de detalii')
        self.scrie_ion()
        self.assertEqual(self.pe_disc(), sorted([id_ + '.md', 'README.txt', 'm_ffffff.md.a1b2c3.tmp']))

    def test_o_stergere_care_pica_nu_strica_scrierea_firului(self):
        self.umple(500)
        self.pune_detalii('m_000064', 'x')
        with mock.patch.object(asistent, '_sterge_detalii', side_effect=PermissionError('x')):
            self.assertEqual(self.scrie_asistent(text='nou').status_code, 201)
        self.assertEqual(self.pe_disc(), ['m_000064.md'], 'ramas orfan, dar cererea a trecut')
        self.assertEqual(self.scrie_asistent(text='inca unul').status_code, 201)
        self.assertEqual(self.pe_disc(), [], 'urmatoarea scriere a firului il matura')

    def test_put_pe_un_mesaj_care_iese_din_fir_chiar_atunci_nu_lasa_orfan(self):
        """Intercalarea cea rea, fortata: PUT-ul a gasit mesajul in fir, iar chiar inainte sa scrie fisierul porneste alta
        cerere care scoate mesajul la plafon. Cu blocarea, a doua cerere asteapta sfarsitul PUT-ului si apoi matura fisierul;
        fara ea, ar matura inaintea scrierii si fisierul ar ramane fara mesaj."""
        import threading
        self.umple(500)

        def scoate():
            with self.app_module.app.test_client() as c:
                c.post('/api/asistent/fir', json={'cine': 'asistent', 'tip': 'info', 'text': 'nou'}, headers=self.h(FULL))
        concurent = threading.Thread(target=scoate)
        scriere_reala = asistent._scrie_detalii

        def intercalat(id_, text):
            concurent.start()
            concurent.join(0.3)
            scriere_reala(id_, text)
        with mock.patch.object(asistent, '_scrie_detalii', intercalat):
            self.assertEqual(self.pune_detalii('m_000064', 'x').status_code, 200)
        concurent.join()
        self.assertEqual(self.randuri('fir.jsonl')[0]['id'], 'm_000065', 'mesajul a iesit din fir')
        self.assertEqual(self.pe_disc(), [])

    def test_cursa_dintre_put_si_scrierea_firului_nu_lasa_orfani(self):
        """PUT-uri pe cele mai vechi 30 de mesaje, in paralel cu 40 de mesaje noi la plafon (care le scot): la sfarsit nu
        ramane niciun fisier cu mesajul scos, oricum s-ar fi intercalat cererile."""
        import threading
        self.umple(500)
        vechi = ['m_%06x' % (i + 100) for i in range(30)]
        statusuri = []

        def pune():
            with self.app_module.app.test_client() as c:
                for _ in range(4):
                    for id_ in vechi:
                        statusuri.append(c.put('/api/asistent/fir/%s/detalii' % id_, json={'detalii': 'x' * 50},
                                               headers=self.h(FULL)).status_code)

        def scrie():
            with self.app_module.app.test_client() as c:
                for i in range(40):
                    statusuri.append(c.post('/api/asistent/fir', json={'cine': 'asistent', 'tip': 'info', 'text': 'nou %d' % i},
                                            headers=self.h(FULL)).status_code)
        fire = [threading.Thread(target=pune), threading.Thread(target=scrie)]
        for f in fire:
            f.start()
        for f in fire:
            f.join()
        self.assertEqual(set(statusuri) - {200, 201, 404}, set())
        self.assertEqual(len(self.randuri('fir.jsonl')), 500)
        ramase = {r['id'] for r in self.randuri('fir.jsonl')}
        self.assertEqual([f for f in self.pe_disc() if f[:-3] not in ramase], [], 'fisier fara mesaj in fir')
        self.assertEqual(self.pe_disc(), [], 'toate cele 30 au fost scoase de cele 40 de mesaje noi')

    # ----- corectii dupa recenzie

    def test_linia_stricata_a_unui_mesaj_nu_ia_cu_ea_detaliile(self):
        """O linie ilizibila din fir.jsonl merge in .corupt la urmatoarea scriere: detaliile mesajului ei raman, in scrierea
        aceea si in cele de dupa ea, ca sa le gaseasca cine repara linia. Un fisier fara nicio urma in .corupt tot se matura."""
        self.umple(3)
        self.pune_detalii('m_000064', 'ale mesajului cu linia stricata')
        self.pune_detalii('m_000065', 'ale unui mesaj sanatos')
        os.makedirs(os.path.join(self.dir, 'detalii'), exist_ok=True)
        with open(os.path.join(self.dir, 'detalii', 'm_ffffff.md'), 'w') as fh:
            fh.write('orfan adevarat')
        randuri = self.randuri('fir.jsonl')
        with open(os.path.join(self.dir, 'fir.jsonl'), 'w', encoding='utf-8') as fh:
            fh.write('{"id": "m_000064", "ts": "2026-11-21T07:00\n')              # linie taiata la mijloc
            for r in randuri[1:]:
                fh.write(json.dumps(r) + '\n')
        with self.assertLogs('pif_dashboard', 'WARNING') as jurnal:
            self.assertEqual(self.scrie_asistent(text='unu').status_code, 201)
        self.assertTrue(any('nu se matura' in l for l in jurnal.output), jurnal.output)
        self.assertIn(b'm_000064', self.fisier('fir.jsonl.corupt'))
        self.assertEqual(self.pe_disc(), ['m_000064.md', 'm_000065.md', 'm_ffffff.md'], 'scrierea cu linii stricate nu matura')
        self.assertEqual(self.scrie_asistent(text='doi').status_code, 201)                # fara linii stricate acum
        self.assertEqual(self.pe_disc(), ['m_000064.md', 'm_000065.md'], 'protejat de .corupt; orfanul fara urma a plecat')
        self.assertEqual(self.fisier('detalii/m_000064.md'), b'ale mesajului cu linia stricata')

    def test_corupt_ilizibil_lasa_fisierele_fara_mesaj_pe_loc(self):
        self.umple(2)
        os.makedirs(os.path.join(self.dir, 'detalii'))
        with open(os.path.join(self.dir, 'detalii', 'm_ffffff.md'), 'w') as fh:
            fh.write('x')
        os.mkdir(os.path.join(self.dir, 'fir.jsonl.corupt'))                               # open() da IsADirectoryError
        self.assertEqual(self.scrie_asistent(text='unu').status_code, 201)
        self.assertEqual(self.pe_disc(), ['m_ffffff.md'])

    def test_masina_cu_mesaj_al_lui_ion_peste_32_kb_da_413(self):
        corp = lambda **c: json.dumps(dict({'text': 'a' * 2000}, **c))                      # noqa: E731
        post = lambda data, **kw: self.client.post('/api/asistent/fir', data=data, content_type='application/json',  # noqa: E731
                                                   headers=self.h(FULL), **kw)
        gunoi = {'gunoi': 'x' * 40000}
        for nume, data in (('cine=ion', corp(cine='ion', **gunoi)), ('fara cine', corp(**gunoi)), ('cine ciudat', corp(cine='x', **gunoi)),
                           ('lista', json.dumps(['x' * 40000]))):
            with self.subTest(nume):
                r = post(data)
                self.assertEqual(r.status_code, 413, r.get_data(as_text=True))
                self.assertIn('32 KB', r.get_json()['error'])
        r = post(corp(cine='ion'))
        self.assertEqual(r.status_code, 201, 'sub 32 KB mesajul lui Ion trece si cu token de masina')
        self.assertEqual(self.noi()[0]['via'], 'masina')
        self.assertEqual(self.scrie_asistent(tip='rezultat', text='x', detalii='d' * 40000).status_code, 201,
                         'mesajul asistentului are 1 MiB')
        self.assertEqual(self.scrie_ion('x' * 40000).status_code, 413, 'dispozitivul: neschimbat')
        self.assertEqual(len(self.randuri('fir.jsonl')), 2)

    def test_masina_cu_corp_fara_content_length_aceleasi_plafoane(self):
        import io
        corp = lambda **c: json.dumps(dict({'text': 'a' * 2000, 'gunoi': 'x' * 40000}, **c)).encode()   # noqa: E731
        for cine, status in (('ion', 413), ('asistent', 400)):                             # asistentul: trece de 413, cade la campul `gunoi`
            with self.subTest(cine=cine):
                r = self.client.post('/api/asistent/fir', input_stream=io.BytesIO(corp(cine=cine, tip='info')),
                                     content_type='application/json', headers=self.h(FULL))
                self.assertEqual(r.status_code, status, r.get_data(as_text=True))
        r = self.client.post('/api/asistent/fir', input_stream=io.BytesIO(b'{"cine":"asistent","x":"' + b'a' * (1024 * 1024) + b'"}'),
                             content_type='application/json', headers=self.h(FULL))
        self.assertEqual(r.status_code, 413)

    def test_masina_corp_invalid_sau_cu_surogat_ramane_400(self):
        for data in ('nu e json', '{"cine": "asistent", "text": "a\\ud83db"}'):
            with self.subTest(data=data):
                r = self.client.post('/api/asistent/fir', data=data, content_type='application/json', headers=self.h(FULL))
                self.assertEqual(r.status_code, 400)

    def test_tmp_vechi_de_la_o_oprire_se_matura_cele_proaspete_si_straine_raman(self):
        id_ = self.mesaj_asistent(detalii='x')
        d = os.path.join(self.dir, 'detalii')
        vechi = ['m_ffffff.md.a1b2c3.tmp', id_ + '.md.0f0f0f.tmp', 'm_0123456789abcdef.md.abcdef.tmp']
        proaspete = ['m_eeeeee.md.a1b2c3.tmp']
        straine = ['m_ffffff.md.xyz.tmp', 'x.md.a1b2c3.tmp', 'm_ffffff.tmp', 'm_ffffff.md.a1b2c3.tmp.bak', id_ + '.txt']
        vechime = time.time() - 3600
        for nume in vechi + proaspete + straine:
            with open(os.path.join(d, nume), 'w') as fh:
                fh.write('x')
            if nume in vechi + straine:
                os.utime(os.path.join(d, nume), (vechime, vechime))
        self.assertEqual(self.pe_disc(), sorted([id_ + '.md'] + vechi + proaspete + straine), 'fara scriere nu se sterge nimic')
        self.assertEqual(self.scrie_ion().status_code, 201)
        self.assertEqual(self.pe_disc(), sorted([id_ + '.md'] + proaspete + straine))
        self.assertEqual(self.citeste(id_).get_json()['detalii'], 'x')

    def test_un_tmp_care_nu_se_poate_sterge_nu_strica_scrierea_firului(self):
        self.mesaj_asistent(detalii='x')
        nume = os.path.join(self.dir, 'detalii', 'm_ffffff.md.a1b2c3.tmp')
        with open(nume, 'w') as fh:
            fh.write('x')
        os.utime(nume, (time.time() - 3600,) * 2)
        with mock.patch.object(asistent, '_sterge_tmp', side_effect=PermissionError('x')):
            self.assertEqual(self.scrie_ion().status_code, 201)
        self.assertTrue(os.path.exists(nume))
        self.assertEqual(self.scrie_ion().status_code, 201)
        self.assertFalse(os.path.exists(nume))


# --------------------------------------------------------------------------- v1.3: textul live al raspunsului

class Live(Baza):
    """`PUT/GET /api/asistent/fir/<id>/live` si fluxul SSE `.../live/flux`. Ceasul fluxului (`_monoton`, `_somn`) e inlocuit
    cu unul de proba: `self.t` avanseaza doar cand fluxul „doarme”, iar `self.la(t, fn)` ruleaza `fn` cand ceasul trece de `t`
    (asa se simuleaza un PUT al asistentului in mijlocul fluxului); niciun test nu asteapta in realitate."""

    def setUp(self):
        super().setUp()
        self.t = 0.0
        self.somnuri = 0
        self.programate = []
        self.patch(asistent, '_monoton', lambda: self.t)
        self.patch(asistent, '_somn', self.somn)
        self.masina = self.app_module.app.test_client()          # al doilea client: PUT-urile din mijlocul fluxului

    def somn(self, secunde):
        self.t += secunde
        self.somnuri += 1
        gata = [p for p in self.programate if p[0] <= self.t]
        self.programate = [p for p in self.programate if p[0] > self.t]
        for _, fn in gata:
            fn()

    def la(self, t, fn):
        self.programate.append((t, fn))

    def mesaj_ion(self):
        r = self.scrie_ion()
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def pune_live(self, id_, text='Salut', token=FULL, client=None, **camp):
        corp = {'text': text, 'gata': False}
        corp.update(camp)
        return (client or self.client).put('/api/asistent/fir/%s/live' % id_, json=corp, headers=self.h(token))

    def pune_ok(self, id_, text='Salut', **camp):
        r = self.pune_live(id_, text, **camp)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()['seq']

    def citeste(self, id_, token=DEVICE, **query):
        return self.client.get('/api/asistent/fir/%s/live' % id_, headers=self.h(token), query_string=query or None)

    def flux(self, id_, token=DEVICE, ultim=None):
        antete = self.h(token)
        if ultim is not None:
            antete['Last-Event-ID'] = str(ultim)
        return self.client.get('/api/asistent/fir/%s/live/flux' % id_, headers=antete)

    def pe_disc(self):
        d = os.path.join(self.dir, 'live')
        return sorted(os.listdir(d)) if os.path.isdir(d) else []

    @staticmethod
    def blocuri(r):
        """Blocurile unui flux (separate de o linie goala), ca liste de linii."""
        return [b.split('\n') for b in r.get_data(as_text=True).split('\n\n') if b]

    @staticmethod
    def data(bloc):
        return json.loads(next(l for l in bloc if l.startswith('data: '))[len('data: '):])

    # ----- PUT

    def test_put_scrie_fisierul_cu_seq_crescator(self):
        id_ = self.mesaj_ion()
        self.assertEqual(self.pe_disc(), [], 'directorul se creeaza doar la nevoie')
        self.assertEqual(self.pune_live(id_, 'Incep', unealta='stare').get_json(), {'seq': 1})
        self.assertEqual(json.loads(self.fisier('live/%s.json' % id_)),
                         {'id': id_, 'text': 'Incep', 'unealta': 'stare', 'gata': False, 'seq': 1, 'la': '2026-11-22T08:00:00Z'})
        self.assertEqual(self.pune_live(id_, 'Incep si continui').get_json(), {'seq': 2})
        self.assertEqual(self.pune_live(id_, 'Incep si continui', gata=True).get_json(), {'seq': 3})
        scris = json.loads(self.fisier('live/%s.json' % id_))
        self.assertEqual((scris['seq'], scris['text'], scris['unealta'], scris['gata']), (3, 'Incep si continui', None, True))
        self.assertEqual(self.pe_disc(), [id_ + '.json'], 'niciun .tmp ramas')
        self.assertNotIn(b'Incep', self.fisier('fir.jsonl'), 'textul live nu intra in fir.jsonl')

    def test_o_retrimitere_inainte_de_gata_da_acelasi_text_cu_seq_mai_mare(self):
        id_ = self.mesaj_ion()
        self.assertEqual([self.pune_ok(id_, 'la fel') for _ in range(2)], [1, 2])
        self.assertEqual(self.citeste(id_).get_json()['text'], 'la fel')

    def test_text_cu_strip_gol_si_la_limita(self):
        id_ = self.mesaj_ion()
        for nume, text, asteptat in (('strip', '  \n Salut \t ', 'Salut'), ('gol', '', ''), ('doar spatii', ' \n ', ''),
                                     ('exact 65536', 'a' * 65536, 'a' * 65536),
                                     ('65536 cu spatii la capete', ' \n' + 'b' * 65536 + '\t ', 'b' * 65536)):
            with self.subTest(nume):
                self.pune_ok(id_, text)
                self.assertEqual(json.loads(self.fisier('live/%s.json' % id_))['text'], asteptat)

    def test_unealta_lipsa_null_si_goala_dau_null(self):
        id_ = self.mesaj_ion()
        for camp in ({}, {'unealta': None}, {'unealta': '  '}):
            with self.subTest(camp=camp):
                self.pune_ok(id_, **camp)
                self.assertIsNone(json.loads(self.fisier('live/%s.json' % id_))['unealta'])
        self.pune_ok(id_, unealta='x' * 80)
        self.assertEqual(json.loads(self.fisier('live/%s.json' % id_))['unealta'], 'x' * 80)

    def test_put_fara_token_401_cu_dispozitiv_403(self):
        id_ = self.mesaj_ion()
        self.assertEqual(self.pune_live(id_, token=None).status_code, 401)
        self.assertEqual(self.pune_live(id_, token='gresit').status_code, 401)
        r = self.pune_live(id_, token=DEVICE)
        self.assertEqual(r.status_code, 403)
        self.assertIn('dispozitiv', r.get_json()['error'])
        self.assertEqual(self.pe_disc(), [], 'nimic scris fara token de masina')

    def test_put_cu_sesiune_cere_csrf(self):
        id_ = self.mesaj_ion()
        self.login()
        r = self.client.put('/api/asistent/fir/%s/live' % id_, json={'text': 'x', 'gata': False})
        self.assertEqual(r.status_code, 403)
        csrf = {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}
        r = self.client.put('/api/asistent/fir/%s/live' % id_, json={'text': 'x', 'gata': False}, headers=csrf)
        self.assertEqual((r.status_code, r.get_json()), (200, {'seq': 1}))

    def test_put_pe_mesaj_inexistent_sau_al_asistentului_da_404(self):
        asistent_id = self.scrie_asistent().get_json()['id']
        for nume, id_ in (('inexistent', 'm_abcdef'), ('al asistentului', asistent_id)):
            with self.subTest(nume):
                r = self.pune_live(id_)
                self.assertEqual(r.status_code, 404)
                self.assertIn('error', r.get_json())
        self.assertEqual(self.pe_disc(), [])

    def test_put_cu_id_invalid_da_400(self):
        for id_ in ('m_zz', 'abc', 'm_12345', 'm_' + 'a' * 17, 'M_ABCDEF', 'm_abcdef.json'):
            with self.subTest(id_=id_):
                r = self.pune_live(id_)
                self.assertEqual(r.status_code, 400)
                self.assertIn('error', r.get_json())
        self.assertEqual(self.pe_disc(), [])

    def test_put_cu_corp_invalid_da_400_si_nu_atinge_fisierul(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'bun')
        bun = self.fisier('live/%s.json' % id_)
        cazuri = (
            ('camp necunoscut', {'text': 'x', 'gata': False, 'extra': 1}, 'corpul.extra'),
            ('text lipseste', {'gata': False}, 'corpul.text'),
            ('text numar', {'text': 5, 'gata': False}, 'corpul.text'),
            ('text null', {'text': None, 'gata': False}, 'corpul.text'),
            ('text prea lung', {'text': 'a' * 65537, 'gata': False}, 'corpul.text'),
            ('unealta numar', {'text': 'x', 'gata': False, 'unealta': 7}, 'corpul.unealta'),
            ('unealta 81', {'text': 'x', 'gata': False, 'unealta': 'x' * 81}, 'corpul.unealta'),
            ('unealta cu control', {'text': 'x', 'gata': False, 'unealta': 'a\nb'}, 'corpul.unealta'),
            ('gata lipseste', {'text': 'x'}, 'corpul.gata'),
            ('gata text', {'text': 'x', 'gata': 'true'}, 'corpul.gata'),
            ('gata numar', {'text': 'x', 'gata': 1}, 'corpul.gata'),
            ('gata null', {'text': 'x', 'gata': None}, 'corpul.gata'),
            ('corp lista', ['x'], 'corpul'),
        )
        for nume, corp, camp in cazuri:
            with self.subTest(nume):
                r = self.client.put('/api/asistent/fir/%s/live' % id_, json=corp, headers=self.h(FULL))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(camp, r.get_json()['error'])
        for nume, brut in (('nu e JSON', b'{'), ('surogat izolat', b'{"text": "\\ud83d", "gata": false}'), ('gol', b'')):
            with self.subTest(nume):
                r = self.client.put('/api/asistent/fir/%s/live' % id_, data=brut, content_type='application/json',
                                    headers=self.h(FULL))
                self.assertEqual(r.status_code, 400)
        self.assertEqual(self.fisier('live/%s.json' % id_), bun)

    def test_dupa_gata_orice_put_da_409_si_fisierul_ramane(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Gata', gata=True)
        final = self.fisier('live/%s.json' % id_)
        for gata in (True, False):
            with self.subTest(gata=gata):
                r = self.pune_live(id_, 'altceva', gata=gata)
                self.assertEqual(r.status_code, 409)
                self.assertIn('error', r.get_json())
        self.assertEqual(self.fisier('live/%s.json' % id_), final)

    def test_put_cu_eroare_de_disc_da_500_si_seq_ramane(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'unu')
        with mock.patch.object(asistent, '_scrie_atomic', side_effect=OSError('disc')):
            r = self.pune_live(id_, 'doi')
        self.assertEqual(r.status_code, 500)
        self.assertEqual(self.pune_live(id_, 'doi').get_json(), {'seq': 2})

    def test_fisier_live_stricat_se_comporta_ca_lipsa(self):
        id_ = self.mesaj_ion()
        os.makedirs(os.path.join(self.dir, 'live'))
        for continut in (b'{', b'[]', b'{"seq": "3", "gata": false}', b'{"seq": 3, "gata": "nu"}', b'\xff\xfe'):
            with self.subTest(continut=continut):
                with open(os.path.join(self.dir, 'live', id_ + '.json'), 'wb') as fh:
                    fh.write(continut)
                self.assertEqual(self.citeste(id_).status_code, 404)
        self.assertEqual(self.pune_live(id_).get_json(), {'seq': 1})

    # ----- matura

    def test_matura_sterge_fisierele_vechi_de_15_minute_la_fiecare_put(self):
        a, b = self.mesaj_ion(), self.mesaj_ion()
        os.makedirs(os.path.join(self.dir, 'live'))
        limita = ACUM.timestamp() - 900
        fisiere = {'m_0000a1.json': limita - 1,              # vechi: se sterge
                   'm_0000a2.json': limita,                  # exact 15 minute: ramane
                   'm_0000a3.json': limita + 1,              # proaspat: ramane
                   'm_0000a4.json.a1b2c3.tmp': limita - 1,   # .tmp vechi de la un proces mort: se sterge
                   'm_0000a5.json.a1b2c3.tmp': limita + 1,   # .tmp proaspat: ramane
                   'straina.json': limita - 3600,            # nu e al nostru: nu se atinge
                   'm_0000a6.json.bak': limita - 3600}
        for nume, mtime in fisiere.items():
            with open(os.path.join(self.dir, 'live', nume), 'w') as fh:
                fh.write('{}')
            os.utime(os.path.join(self.dir, 'live', nume), (mtime, mtime))
        self.pune_ok(a)
        self.assertEqual(self.pe_disc(), sorted(set(fisiere) - {'m_0000a1.json', 'm_0000a4.json.a1b2c3.tmp'} | {a + '.json'}))
        self.acum = ACUM + timedelta(seconds=901)
        self.pune_ok(b)
        self.assertEqual(self.pe_disc(), sorted(['straina.json', 'm_0000a6.json.bak', b + '.json']),
                         'la ACUM+901 s toate fisierele noastre mai vechi de ACUM+1 s cad, si cel al lui `a`; straine raman')

    def test_un_raspuns_vechi_inchis_nu_mai_blocheaza_cu_409_dupa_matura(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Gata', gata=True)
        self.assertEqual(self.pune_live(id_).status_code, 409)
        self.acum = ACUM + timedelta(seconds=901)
        self.assertEqual(self.pune_live(id_, 'din nou').get_json(), {'seq': 1})

    def test_matura_care_nu_poate_sterge_nu_strica_put_ul(self):
        a, b = self.mesaj_ion(), self.mesaj_ion()
        self.pune_ok(a)
        self.acum = ACUM + timedelta(seconds=901)
        with mock.patch.object(os, 'remove', side_effect=PermissionError('x')):
            self.assertEqual(self.pune_live(b).status_code, 200)
        self.assertEqual(self.pe_disc(), sorted([a + '.json', b + '.json']))
        self.assertEqual(self.pune_live(b).status_code, 200)
        self.assertEqual(self.pe_disc(), [b + '.json'])

    # ----- GET (polling)

    def test_get_404_200_si_204_cu_dupa(self):
        id_ = self.mesaj_ion()
        r = self.citeste(id_)
        self.assertEqual(r.status_code, 404)
        self.assertIn('error', r.get_json())
        self.pune_ok(id_, 'Salut', unealta='stare')
        self.pune_ok(id_, 'Salut din nou')
        r = self.citeste(id_)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {'id': id_, 'text': 'Salut din nou', 'unealta': None, 'gata': False, 'seq': 2,
                                        'la': '2026-11-22T08:00:00Z'})
        self.assertEqual(r.headers['Cache-Control'], 'no-store')
        for dupa, status in ((0, 200), (1, 200), (2, 204), (3, 204), (999999, 204)):
            with self.subTest(dupa=dupa):
                r = self.citeste(id_, dupa=dupa)
                self.assertEqual(r.status_code, status)
                if status == 204:
                    self.assertEqual(r.get_data(), b'')
                else:
                    self.assertEqual(r.get_json()['seq'], 2)
        self.pune_ok(id_, 'Salut din nou si inca', gata=True)
        self.assertEqual(self.citeste(id_, dupa=2).get_json()['seq'], 3)
        self.assertTrue(self.citeste(id_, dupa=2).get_json()['gata'])

    def test_get_cu_dupa_invalid_da_400_iar_dupa_fara_fisier_404(self):
        id_ = self.mesaj_ion()
        self.assertEqual(self.citeste(id_, dupa=5).status_code, 404)
        self.pune_ok(id_)
        for dupa in ('abc', '-1', '1.5', '', '1' * 10):
            with self.subTest(dupa=dupa):
                self.assertEqual(self.citeste(id_, dupa=dupa).status_code, 400)

    def test_get_cu_id_invalid_404_si_acces(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_)
        self.assertEqual(self.citeste('m_zz').status_code, 404)
        self.assertEqual(self.citeste(id_, token=None).status_code, 401)
        self.assertEqual(self.citeste(id_, token='gresit').status_code, 401)
        for token in (DEVICE, FULL):
            self.assertEqual(self.citeste(id_, token=token).status_code, 200)
        self.login()
        self.assertEqual(self.citeste(id_, token=None).status_code, 200, 'si cu sesiune')

    # ----- SSE

    def test_flux_antete_retry_si_evenimentele_pana_la_gata(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Incep', unealta='stare')
        self.la(1.0, lambda: self.pune_live(id_, 'Incep si continui', client=self.masina))
        self.la(2.0, lambda: self.pune_live(id_, 'Incep si continui pana la capat', gata=True, client=self.masina))
        r = self.flux(id_)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Content-Type'], 'text/event-stream; charset=utf-8')
        self.assertEqual(r.headers['Cache-Control'], 'no-cache')
        self.assertEqual(r.headers['X-Accel-Buffering'], 'no')
        blocuri = self.blocuri(r)
        self.assertEqual(blocuri[0], ['retry: 2000'])
        self.assertEqual(len(blocuri), 4, blocuri)
        self.assertEqual([b[:2] for b in blocuri[1:]], [['id: 1', 'event: live'], ['id: 2', 'event: live'], ['id: 3', 'event: live']])
        self.assertEqual([self.data(b)['seq'] for b in blocuri[1:]], [1, 2, 3])
        self.assertEqual([self.data(b)['gata'] for b in blocuri[1:]], [False, False, True])
        self.assertEqual(self.data(blocuri[1]), {'id': id_, 'text': 'Incep', 'unealta': 'stare', 'gata': False, 'seq': 1,
                                                 'la': '2026-11-22T08:00:00Z'})
        self.assertEqual(self.data(blocuri[3])['text'], 'Incep si continui pana la capat')
        self.assertIn('data: {"id":"%s","text":"Incep","unealta":"stare"' % id_, r.get_data(as_text=True), 'JSON compact')
        self.assertLess(self.t, 3.0, 'se inchide la gata, nu la plafon')
        self.assertEqual(self.programate, [])

    def test_al_doilea_flux_deodata_primeste_ocupat_si_nu_tine_workerul(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Scriu')
        loc = asistent._ia_locul_fluxului()                      # un flux deschis in alt worker
        self.assertIsNotNone(loc)
        try:
            r = self.flux(id_)
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.get_data(as_text=True), 'retry: 2000\n\nevent: ocupat\ndata: {}\n\n')
            self.assertEqual(self.somnuri, 0, 'se inchide pe loc, nu tine workerul')
        finally:
            asistent._lasa_locul_fluxului(loc)
        self.pune_ok(id_, 'Scriu tot', gata=True)
        self.assertEqual([b[0] for b in self.blocuri(self.flux(id_))], ['retry: 2000', 'id: 2'], 'locul s-a eliberat')

    def test_fluxul_terminat_isi_elibereaza_locul(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Gata', gata=True)
        for _ in range(3):
            self.assertEqual([b[0] for b in self.blocuri(self.flux(id_))], ['retry: 2000', 'id: 1'])
        loc = asistent._ia_locul_fluxului()
        self.assertIsNotNone(loc, 'dupa trei fluxuri inchise, locul e liber')
        asistent._lasa_locul_fluxului(loc)

    def test_fluxul_abandonat_de_client_elibereaza_locul(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Scriu')
        gen = asistent._flux_live(id_, 0)
        self.assertEqual(next(gen), 'retry: 2000\n\n')
        self.assertIsNone(asistent._ia_locul_fluxului(), 'cat ruleaza, locul e luat')
        gen.close()                                               # serverul inchide iteratorul cand clientul a plecat
        loc = asistent._ia_locul_fluxului()
        self.assertIsNotNone(loc)
        asistent._lasa_locul_fluxului(loc)

    def test_get_fara_fisier_404_fara_rand_de_log(self):
        id_ = self.mesaj_ion()
        with self.assertNoLogs('pif_dashboard', 'WARNING'):
            r = self.citeste(id_, dupa=0)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.headers['Cache-Control'], 'no-store')

    def test_flux_cu_text_pe_mai_multe_randuri_ramane_un_singur_rand_data(self):
        id_ = self.mesaj_ion()
        text = 'rand 1\nrand 2\r\nrand 3   ă ș \U0001F600'
        self.pune_ok(id_, text, gata=True)
        bloc = self.blocuri(self.flux(id_))[1]
        self.assertEqual(len(bloc), 3, bloc)
        self.assertEqual(self.data(bloc)['text'], text)

    def test_flux_cu_fisier_deja_gata_trimite_evenimentul_si_se_inchide_fara_sa_doarma(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Totul', gata=True)
        blocuri = self.blocuri(self.flux(id_))
        self.assertEqual([b[0] for b in blocuri], ['retry: 2000', 'id: 1'])
        self.assertEqual(self.somnuri, 0)

    def test_flux_fara_fisier_trimite_gol_dupa_20_s(self):
        id_ = self.mesaj_ion()
        r = self.flux(id_)
        self.assertEqual(r.get_data(as_text=True), 'retry: 2000\n\n: ping\n\nevent: gol\ndata: {}\n\n',
                         'un ping la 15 s, apoi gol')
        self.assertGreaterEqual(self.t, 20.0)
        self.assertLess(self.t, 20.5)

    def test_flux_fara_fisier_dar_cu_fisier_aparut_la_timp_nu_trimite_gol(self):
        id_ = self.mesaj_ion()
        self.la(19.0, lambda: self.pune_live(id_, 'Tarziu', gata=True, client=self.masina))
        blocuri = self.blocuri(self.flux(id_))
        self.assertEqual([b[0] for b in blocuri], ['retry: 2000', ': ping', 'id: 1'])
        self.assertNotIn('gol', json.dumps(blocuri))

    def test_flux_cu_fisier_neinchis_trimite_ping_la_15_s_si_se_opreste_la_60_s(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Scriu')
        r = self.flux(id_)
        self.assertEqual(r.get_data(as_text=True).count(': ping\n\n'), 3, 'la 15, 30 si 45 s; la 60 s se inchide')
        self.assertEqual([b[0] for b in self.blocuri(r) if not b[0].startswith(':')], ['retry: 2000', 'id: 1'])
        self.assertGreaterEqual(self.t, 60.0)
        self.assertLess(self.t, 60.5)

    def test_un_eveniment_reseteaza_numaratoarea_pingului(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Scriu')
        self.la(10.0, lambda: self.pune_live(id_, 'Scriu mai mult', client=self.masina))
        self.la(25.0, lambda: self.pune_live(id_, 'Scriu si mai mult', gata=True, client=self.masina))
        blocuri = self.blocuri(self.flux(id_))
        self.assertEqual([b[0] for b in blocuri], ['retry: 2000', 'id: 1', 'id: 2', 'id: 3'],
                         'ultimul eveniment la 10 s, urmatorul la 25 s: sub 15 s intre ele, deci niciun ping')

    def test_last_event_id_nu_retrimite_ce_stie_clientul(self):
        id_ = self.mesaj_ion()
        for text in ('unu', 'doi', 'trei'):
            self.pune_ok(id_, text)
        for ultim in (None, 0, 2, 'abc', '-1', ''):
            with self.subTest(ultim=ultim):
                self.t = 0.0
                ids = [self.data(b)['seq'] for b in self.blocuri(self.flux(id_, ultim=ultim)) if b[0].startswith('id: ')]
                self.assertEqual(ids, [3], 'un Last-Event-ID care nu e intreg nu se ia in seama')
        self.t = 0.0
        r = self.flux(id_, ultim=3)
        self.assertEqual([b[0] for b in self.blocuri(r)], ['retry: 2000'] + [': ping'] * 3, 'clientul are deja seq 3')
        self.assertGreaterEqual(self.t, 60.0, 'raspunsul nu e gata, deci fluxul asteapta pana la plafon')

    def test_last_event_id_si_un_seq_nou_in_timpul_fluxului(self):
        id_ = self.mesaj_ion()
        for text in ('unu', 'doi', 'trei'):
            self.pune_ok(id_, text)
        self.la(1.0, lambda: self.pune_live(id_, 'patru', gata=True, client=self.masina))
        blocuri = self.blocuri(self.flux(id_, ultim=3))
        self.assertEqual([b[0] for b in blocuri], ['retry: 2000', 'id: 4'])
        self.assertEqual(self.data(blocuri[1])['text'], 'patru')

    def test_reconectare_dupa_gata_primit_da_204_care_opreste_reconectarea(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'unu')
        self.pune_ok(id_, 'doi', gata=True)
        for ultim in (2, 3, 99):
            with self.subTest(ultim=ultim):
                r = self.flux(id_, ultim=ultim)
                self.assertEqual((r.status_code, r.get_data()), (204, b''))
        r = self.flux(id_, ultim=1)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([b[0] for b in self.blocuri(r)], ['retry: 2000', 'id: 2'])

    def test_flux_cu_sesiune_fara_bearer(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Salut', gata=True)
        self.assertEqual(self.flux(id_, token=None).status_code, 401)
        self.login()
        r = self.flux(id_, token=None)
        self.assertEqual(r.status_code, 200)
        self.assertEqual([b[0] for b in self.blocuri(r)], ['retry: 2000', 'id: 1'])

    def test_flux_acces_si_id_invalid(self):
        id_ = self.mesaj_ion()
        self.assertEqual(self.flux(id_, token='gresit').status_code, 401)
        r = self.flux(id_, token=FULL)
        self.assertEqual((r.status_code, r.get_data(as_text=True)), (200, 'retry: 2000\n\n: ping\n\nevent: gol\ndata: {}\n\n'))
        r = self.flux('m_zz')
        self.assertEqual(r.status_code, 404)
        self.assertIn('error', r.get_json())

    def test_flux_citeste_fisierul_la_250_ms(self):
        id_ = self.mesaj_ion()
        self.flux(id_).get_data()
        self.assertEqual(self.somnuri, 80, '20 s / 0,25 s')

    def test_o_eroare_de_citire_in_flux_nu_il_opreste(self):
        id_ = self.mesaj_ion()
        self.pune_ok(id_, 'Salut', gata=True)
        citeste = asistent._citeste_live
        apeluri = []

        def capricios(i):
            apeluri.append(i)
            if len(apeluri) == 2:                          # primul apel e cel din ruta, al doilea (primul din generator) cade
                raise PermissionError('os.replace in curs')
            return citeste(i)
        with mock.patch.object(asistent, '_citeste_live', capricios):
            blocuri = self.blocuri(self.flux(id_))
        self.assertEqual([b[0] for b in blocuri], ['retry: 2000', 'id: 1'])
        self.assertEqual(self.somnuri, 1, 'un singur ciclu a esuat; apoi fisierul se citeste si fluxul se inchide la gata')

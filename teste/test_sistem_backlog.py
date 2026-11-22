"""Tab-ul Backlog din System (contractul `/api/sistem` v1.3, aditiv): blocul `backlog` din snapshot-ul sursei `server` si
inchiderea unui item prin `POST /api/sistem/decizie`.

Ce se pazeste, tacut daca se strica:
  - blocul `backlog` se accepta doar de la `server` (alta sursa: 400), cu campurile exacte, id `E-NNN`, `masina` din enum,
    maximum 300 de itemi cu id-uri unice, `total` cel putin cat lista (poate fi mai mare: lista se taie), un camp in plus sau
    un tip gresit da 400 cu calea campului si snapshot-ul curent ramane neatins; fara bloc, snapshot-ul vechi ramane valid;
  - `GET /api/sistem` da `backlog` la nivelul de sus (blocul serverului, `null` fara el);
  - o decizie `backlog:E-NNN` cu optiunile fixe `inchide-implementat|inchide-respins|inchide-duplicat` se accepta doar pentru un
    item din backlog-ul stocat; id gresit, optiune necunoscuta sau nota peste 400 de caractere dau 400, itemul absent 409;
  - cat decizia e in asteptare (sau preluata), itemul nu mai apare in `GET /api/sistem` si `total`/`asteapta_ion` scad cu el;
    anulata sau consumata cu `fail`, reapare; consumata cu `ok`, iese cu urmatorul snapshot;
  - istoricul tine eticheta optiunii si titlul cu id-ul itemului; retrimiterea inlocuieste decizia in asteptare;
  - 300 de itemi cu cele mai lungi texte incap in limita corpului PUT; tokenul lipsa da 401, cel de dispozitiv poate decide dar
    nu poate trimite blocul.
"""

import json
import os
from datetime import datetime, timezone

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import sistem
from test_sistem import corp

ACUM = datetime(2026, 11, 22, 8, 12, 0, tzinfo=timezone.utc)


def it(n=264, **camp):
    base = {'id': 'E-%d' % n, 'zona': 'dashboard', 'titlu': 'Titlu %d' % n, 'descriere': 'Descriere %d.' % n,
            'creat': '2026-10-05', 'varsta_zile': 48, 'etichete': ['loc: PC (torqa-sp)'], 'asteapta_ion': False,
            'masina': 'ionpc', 'repo': 'torqa-sp'}
    base.update(camp)
    return base


def bloc(*itemi, **camp):
    itemi = list(itemi) or [it(264), it(328, asteapta_ion=True, etichete=['Ion'], masina=None, repo=None, varsta_zile=39)]
    b = {'generat': '2026-11-22T08:00:00Z', 'total': len(itemi), 'asteapta_ion': sum(1 for i in itemi if i['asteapta_ion']),
         'cel_mai_vechi_zile': max(i['varsta_zile'] or 0 for i in itemi), 'itemi': itemi}
    b.update(camp)
    return b


def server(**camp):
    return corp('server', backlog=bloc(), **camp)


class SistemBacklog(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'sistem')
        self.patch(sistem, 'DIR_SISTEM', self.dir)
        self.patch(sistem, '_acum', lambda: ACUM)

    def pune(self, cuprins, sursa='server', token=FULL):
        return self.client.put('/api/sistem/sursa/' + sursa, json=cuprins, headers=self.bearer(token) if token else {})

    def pune_ok(self, cuprins, sursa='server'):
        r = self.pune(cuprins, sursa)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))

    def citeste(self, token=FULL):
        r = self.client.get('/api/sistem', headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def decide(self, id_, optiune, token=FULL, **camp):
        return self.client.post('/api/sistem/decizie', json={'id': id_, 'optiune': optiune, **camp},
                                headers=self.bearer(token) if token else {})

    def consuma(self, uid, rezultat='closed in the ledger', **camp):
        return self.client.post('/api/sistem/decizii/%s/consumat' % uid, json={'rezultat': rezultat, **camp},
                                headers=self.bearer(FULL))

    def ids(self, vedere=None):
        b = (vedere or self.citeste())['backlog']
        return [i['id'] for i in b['itemi']]

    # ----------------------------------------------------------------------- snapshot

    def test_blocul_se_pastreaza_si_iese_la_nivelul_de_sus(self):
        self.pune_ok(server())
        b = self.citeste()['backlog']
        self.assertEqual(b, bloc())
        self.assertEqual(b['itemi'][0]['repo'], 'torqa-sp')
        self.assertIsNone(b['itemi'][1]['masina'])

    def test_fara_bloc_backlog_e_null_si_snapshot_vechi_ramane_valid(self):
        self.assertIsNone(self.citeste()['backlog'])
        self.pune_ok(corp('server'))
        self.assertIsNone(self.citeste()['backlog'])
        self.pune_ok(corp('pc-job'), 'pc-job')
        self.assertIsNone(self.citeste()['backlog'])

    def test_backlog_vine_doar_de_la_server(self):
        for sursa in ('pc-job', 'ionpc'):
            r = self.pune(corp(sursa, backlog=bloc()), sursa)
            self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
            self.assertIn('backlog', r.get_json()['error'])
        self.assertIsNone(self.citeste()['backlog'])

    def test_backlog_de_la_alt_server_nu_acopera_blocul_serverului(self):
        self.pune_ok(server())
        self.pune_ok(corp('pc-job'), 'pc-job')
        self.assertEqual(self.ids(), ['E-264', 'E-328'])

    def test_blocul_in_afara_contractului_400_si_snapshotul_ramane(self):
        self.pune_ok(server())
        bun = bloc()
        rele = {
            'null': None,
            'nu-i obiect': [],
            'camp in plus': dict(bun, x=1),
            'lipseste total': {k: v for k, v in bun.items() if k != 'total'},
            'generat cu offset': dict(bun, generat='2026-11-22T08:00:00+00:00'),
            'total text': dict(bun, total='2'),
            'total bool': dict(bun, total=True),
            'total negativ': dict(bun, total=-1),
            'total sub lista': dict(bun, total=1),
            'asteapta peste total': dict(bun, asteapta_ion=3),
            'vechime float': dict(bun, cel_mai_vechi_zile=1.5),
            'itemi nu-i lista': dict(bun, itemi='x'),
            'item gol': dict(bun, itemi=[{}]),
            'item camp in plus': dict(bun, itemi=[it(1, x=1)]),
            'id fara E-': dict(bun, itemi=[it(1, id='B-1')]),
            'id 6 cifre': dict(bun, itemi=[it(1, id='E-123456')]),
            'id cu spatiu': dict(bun, itemi=[it(1, id='E-1 ')]),
            'id duplicat': dict(bun, total=2, itemi=[it(1), it(1)]),
            'zona goala': dict(bun, itemi=[it(1, zona='')]),
            'zona 41': dict(bun, itemi=[it(1, zona='z' * 41)]),
            'titlu 201': dict(bun, itemi=[it(1, titlu='t' * 201)]),
            'titlu gol': dict(bun, itemi=[it(1, titlu='  ')]),
            'descriere 401': dict(bun, itemi=[it(1, descriere='d' * 401)]),
            'descriere null': dict(bun, itemi=[it(1, descriere=None)]),
            'creat prost': dict(bun, itemi=[it(1, creat='22.11.2026')]),
            'creat 30 feb': dict(bun, itemi=[it(1, creat='2026-02-30')]),
            'varsta negativa': dict(bun, itemi=[it(1, varsta_zile=-1)]),
            'varsta text': dict(bun, itemi=[it(1, varsta_zile='48')]),
            'etichete 9': dict(bun, itemi=[it(1, etichete=['e%d' % n for n in range(9)])]),
            'eticheta 41': dict(bun, itemi=[it(1, etichete=['e' * 41])]),
            'eticheta goala': dict(bun, itemi=[it(1, etichete=[' '])]),
            'asteapta_ion 1': dict(bun, itemi=[it(1, asteapta_ion=1)]),
            'masina necunoscuta': dict(bun, itemi=[it(1, masina='vm')]),
            'repo necunoscut': dict(bun, itemi=[it(1, repo='altul')]),
            'lipseste masina': dict(bun, itemi=[{k: v for k, v in it(1).items() if k != 'masina'}]),
            'lipseste repo': dict(bun, itemi=[{k: v for k, v in it(1).items() if k != 'repo'}]),
            '301 itemi': dict(bun, total=301, itemi=[it(n) for n in range(1, 302)]),
        }
        for nume, rau in rele.items():
            with self.subTest(nume):
                r = self.pune(corp('server', backlog=rau))
                self.assertEqual(r.status_code, 400, (nume, r.get_data(as_text=True)))
                self.assertIn('backlog', r.get_json()['error'])
        self.assertEqual(self.ids(), ['E-264', 'E-328'], 'snapshot-ul bun a ramas')

    def test_nulabile_si_limitele_se_accepta(self):
        i = it(99999, creat=None, varsta_zile=None, masina=None, repo=None, descriere='', zona='z' * 40, titlu='t' * 200,
               etichete=['e' * 40] * 8)
        self.pune_ok(corp('server', backlog=bloc(i, total=5000)))
        b = self.citeste()['backlog']
        self.assertEqual(b['total'], 5000, 'total poate depasi lista: lista se taie la 300, totalul ramane real')
        self.assertEqual(b['itemi'], [i])

    def test_300_de_itemi_cu_texte_maxime_incap_in_limita_corpului(self):
        # cel mai rau caz: caractere de 3 octeti in toate campurile text, 8 etichete de 40
        itemi = [it(n, zona='ă' * 40, titlu='€' * 200, descriere='€' * 400, etichete=['€' * 40] * 8) for n in range(1, 301)]
        corp_mare = corp('server', backlog=bloc(*itemi))
        octeti = len(json.dumps(corp_mare, ensure_ascii=False).encode('utf-8'))
        self.assertLess(octeti, sistem.MAX_CORP, octeti)
        r = self.pune(corp_mare)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:200])
        self.assertEqual(len(self.citeste()['backlog']['itemi']), 300)

    # ----------------------------------------------------------------------- decizia de inchidere

    def test_inchiderea_se_inregistreaza_cu_optiunile_fixe(self):
        self.pune_ok(server())
        for optiune, label in (('inchide-implementat', 'Close as done'), ('inchide-respins', 'Close as not needed'),
                               ('inchide-duplicat', 'Close as duplicate')):
            with self.subTest(optiune):
                r = self.decide('backlog:E-264', optiune, text='nota lui Ion')
                self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
                rand = [x for x in self.client.get('/api/sistem/decizii', headers=self.bearer(FULL)).get_json()['decizii']
                        if x['uid'] == r.get_json()['uid']][0]
                self.assertEqual((rand['id'], rand['optiune'], rand['label'], rand['text'], rand['sursa']),
                                 ('backlog:E-264', optiune, label, 'nota lui Ion', 'server'))
                self.assertEqual(rand['titlu'], 'E-264 · Titlu 264')

    def test_nota_e_optionala_si_are_cel_mult_400_de_caractere(self):
        self.pune_ok(server())
        r = self.decide('backlog:E-264', 'inchide-respins')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.decide('backlog:E-328', 'inchide-respins', text='n' * 400).status_code, 201)
        r = self.decide('backlog:E-264', 'inchide-respins', text='n' * 401)
        self.assertEqual(r.status_code, 400)
        self.assertIn('corpul.text', r.get_json()['error'])

    def test_orice_altceva_pe_un_id_backlog_da_400_sau_409(self):
        self.pune_ok(server())
        for id_, optiune in (('backlog:E-264', 'aprob'), ('backlog:E-264', 'claude'), ('backlog:E-264', ''),
                             ('backlog:', 'inchide-respins'), ('backlog:264', 'inchide-respins'),
                             ('backlog:e-264', 'inchide-respins'), ('backlog:A-001', 'inchide-respins'),
                             ('backlog:E-264 ', 'inchide-respins'), ('backlog:E-1234567', 'inchide-respins'),
                             ('backlog:backlog:E-264', 'inchide-respins')):
            with self.subTest(id_=id_, optiune=optiune):
                self.assertEqual(self.decide(id_, optiune).status_code, 400)
        self.assertEqual(self.client.get('/api/sistem/decizii', headers=self.bearer(FULL)).get_json()['decizii'], [])

    def test_itemul_absent_din_backlog_da_409(self):
        self.assertEqual(self.decide('backlog:E-264', 'inchide-respins').status_code, 409, 'fara snapshot')
        self.pune_ok(corp('server'))
        self.assertEqual(self.decide('backlog:E-264', 'inchide-respins').status_code, 409, 'snapshot fara bloc')
        self.pune_ok(server(generat='2026-11-22T08:01:00Z'))
        r = self.decide('backlog:E-999', 'inchide-respins')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.decide('backlog:E-264', 'inchide-respins').status_code, 201)

    def test_un_id_backlog_nu_trece_prin_itemii_obisnuiti(self):
        """`backlog:E-264` nu e un item din `itemi`; un item obisnuit cu acelasi id nu da optiunile backlog-ului."""
        self.pune_ok(corp('pc-job', {'id': 'backlog:E-264', 'grup': 'review', 'titlu': 't', 'motiv': '', 'etichete': [],
                                     'optiuni': [{'id': 'aprob', 'label': 'Approve', 'stil': 'filled'}]}), 'pc-job')
        self.assertEqual(self.decide('backlog:E-264', 'aprob').status_code, 400)

    def test_fara_token_401_iar_dispozitivul_poate_decide_dar_nu_trimite_blocul(self):
        self.pune_ok(server())
        self.assertEqual(self.decide('backlog:E-264', 'inchide-respins', token=None).status_code, 401)
        self.assertEqual(self.decide('backlog:E-264', 'inchide-respins', token='gresit').status_code, 401)
        self.assertEqual(self.decide('backlog:E-264', 'inchide-respins', token=DEVICE).status_code, 201)
        self.assertEqual(self.pune(server(), token=DEVICE).status_code, 401)
        self.assertEqual(self.pune(server(), token=None).status_code, 401)
        self.assertEqual(self.client.get('/api/sistem').status_code, 401)
        self.assertIn('backlog', self.citeste(token=DEVICE))

    def test_retrimiterea_inlocuieste_decizia_in_asteptare(self):
        self.pune_ok(server())
        uid1 = self.decide('backlog:E-264', 'inchide-respins').get_json()['uid']
        uid2 = self.decide('backlog:E-264', 'inchide-implementat', text='gata').get_json()['uid']
        self.assertNotEqual(uid1, uid2)
        dec = self.client.get('/api/sistem/decizii', headers=self.bearer(FULL)).get_json()['decizii']
        self.assertEqual([(d['uid'], d['optiune']) for d in dec], [(uid2, 'inchide-implementat')])
        self.assertEqual(self.ids(), ['E-328'], 'inca ascuns, o singura data')

    # ----------------------------------------------------------------------- ciclul de viata

    def test_itemul_cu_decizie_in_asteptare_nu_mai_apare_si_numerele_scad(self):
        self.pune_ok(server())
        uid = self.decide('backlog:E-328', 'inchide-implementat').get_json()['uid']
        b = self.citeste()['backlog']
        self.assertEqual([i['id'] for i in b['itemi']], ['E-264'])
        self.assertEqual((b['total'], b['asteapta_ion'], b['cel_mai_vechi_zile']), (1, 0, 48))
        self.assertEqual(self.client.post('/api/sistem/decizii/%s/preluat' % uid, json={}, headers=self.bearer(FULL)).status_code, 200)
        self.assertEqual(self.ids(), ['E-264'], 'preluata: tot ascuns')
        # snapshot-ul stocat ramane intreg: al doilea clic gaseste itemul
        self.assertEqual(self.decide('backlog:E-328', 'inchide-respins').status_code, 409, 'preluata: nu se mai schimba')

    def test_anulata_sau_esuata_reapare(self):
        self.pune_ok(server())
        uid = self.decide('backlog:E-264', 'inchide-respins').get_json()['uid']
        self.assertEqual(self.ids(), ['E-328'])
        r = self.client.post('/api/sistem/decizie/%s/anulare' % uid, headers=self.bearer(FULL))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.ids(), ['E-264', 'E-328'], 'anulata: reapare')
        uid = self.decide('backlog:E-264', 'inchide-respins').get_json()['uid']
        self.assertEqual(self.consuma(uid, 'evolve.py close a iesit cu 2', stare='fail').status_code, 200)
        v = self.citeste()
        self.assertEqual(self.ids(v), ['E-264', 'E-328'], 'consumata cu fail: reapare')
        self.assertEqual(v['backlog']['total'], 2)
        h = v['istoric'][0]
        self.assertEqual((h['id'], h['optiune'], h['label'], h['stare']), ('backlog:E-264', 'inchide-respins', 'Close as not needed', 'fail'))

    def test_consumata_ok_iese_cu_urmatorul_snapshot_si_apare_in_istoric(self):
        self.pune_ok(server())
        uid = self.decide('backlog:E-264', 'inchide-implementat', text='am rulat testele').get_json()['uid']
        self.assertEqual(self.consuma(uid, 'closed in the ledger (implementat)', stare='ok').status_code, 200)
        # ledger-ul a iesit din snapshot la fold + PUT
        self.pune_ok(corp('server', backlog=bloc(it(328, asteapta_ion=True, etichete=['Ion'], masina=None, repo=None)),
                          generat='2026-11-22T08:05:00Z'))
        v = self.citeste()
        self.assertEqual(self.ids(v), ['E-328'])
        h = v['istoric'][0]
        self.assertEqual((h['id'], h['titlu'], h['label'], h['text'], h['stare'], h['rezultat']),
                         ('backlog:E-264', 'E-264 · Titlu 264', 'Close as done', 'am rulat testele', 'ok',
                          'closed in the ledger (implementat)'))
        self.assertEqual(self.decide('backlog:E-264', 'inchide-respins').status_code, 409, 'iesit din backlog')

    def test_cel_mai_vechi_ramane_cand_lista_e_taiata(self):
        """Cu `total` peste lista (taiata la 300) nu se poate reface vechimea din ce a ramas: ramane cea a serverului."""
        self.pune_ok(corp('server', backlog=bloc(it(1, varsta_zile=10), it(2, varsta_zile=5), total=400, cel_mai_vechi_zile=900)))
        self.decide('backlog:E-1', 'inchide-respins')
        b = self.citeste()['backlog']
        self.assertEqual((b['total'], b['cel_mai_vechi_zile']), (399, 900))

    def test_clientul_nu_poate_trimite_comenzi_prin_backlog(self):
        """Nota e text: ajunge in rand ca text, nu schimba optiunea sau verdictul si nu iese din campul `text`."""
        self.pune_ok(server())
        r = self.decide('backlog:E-264', 'inchide-respins', text='--verdict implementat; rm -rf ~')
        self.assertEqual(r.status_code, 201)
        dec = self.client.get('/api/sistem/decizii', headers=self.bearer(FULL)).get_json()['decizii'][0]
        self.assertEqual(dec['optiune'], 'inchide-respins')
        self.assertEqual(dec['text'], '--verdict implementat; rm -rf ~')
        r = self.client.post('/api/sistem/decizie', json={'id': 'backlog:E-264', 'optiune': 'inchide-respins', 'verdict': 'x'},
                             headers=self.bearer(FULL))
        self.assertEqual(r.status_code, 400)


class RefulBacklogInFirul(CuAplicatia):
    """`Discuss` si `Give to Claude` trimit un mesaj normal la `POST /api/asistent/fir` cu `ref: {tip: item, id: backlog:E-NNN}`:
    forma trece validarea ref-ului din `blueprints/asistent.py`, cu limitele ei (id <= 160, titlu <= 140, sursa <= 40)."""

    def test_forma_din_contract_trece(self):
        from blueprints.asistent import _ref
        for masina in ('server', 'ionpc', 'pc-job', None):
            ref = _ref({'tip': 'item', 'id': 'backlog:E-264', 'titlu': 'Titlu', 'sursa': 'Backlog · dashboard',
                        'masina': masina}, 'corpul.ref')
            self.assertEqual((ref['tip'], ref['id'], ref['masina'], ref['mod']), ('item', 'backlog:E-264', masina, 'discuta'))

    def test_limitele_titlului_si_sursei(self):
        from blueprints.asistent import EroareCorp, _ref
        bun = {'tip': 'item', 'id': 'backlog:E-264', 'titlu': 't' * 140, 'sursa': 's' * 40, 'masina': 'ionpc'}
        _ref(bun, 'corpul.ref')
        for camp, rau in (('titlu', 't' * 141), ('sursa', 's' * 41), ('masina', 'vm'), ('id', 'i' * 161)):
            with self.assertRaises(EroareCorp, msg=camp):
                _ref(dict(bun, **{camp: rau}), 'corpul.ref')

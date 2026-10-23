"""Calendarul Outlook: `PUT /api/outlook/calendar` si cheia `outlook` din `GET /api/calendar`.

Ce se pazeste, tacut daca se strica:
  - un corp care iese din contract da 400 (cu campul si indexul evenimentului) si NU atinge
    snapshot-ul vechi: Torqa continua sa vada ultimul calendar bun;
  - scrierea e atomica (fisier temporar + `os.replace`): nu ramane niciun `.tmp`;
  - `/api/calendar` intoarce doar evenimentele care ating fereastra, pe data locala din string;
  - fara snapshot sau cu fisierul corupt, `outlook` e `null` si raspunsul ramane 200;
  - doar tokenul de masina (sau sesiunea) scrie; dispozitivul citeste cheia, dar nu scrie;
  - restul raspunsului `/api/calendar` are aceleasi chei ca inainte (APK-ul instalat ignora cheia noua).
Directorul snapshot-ului e unul temporar: un test nu scrie niciodata in `uploads/` din proiect.
"""

import copy
import json
import os

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import outlook

CHEI_VECHI = {'start', 'zile', 'today', 'perioade', 'taskuri', 'de_decis', 'neplanificate', 'probleme'}


def ev(id_, start, end, toata_ziua=False, **camp):
    return {'id': id_, 'title': 'Titlu ' + id_, 'allDay': toata_ziua, 'start': start, 'end': end,
            'location': '', 'busy': 'busy', 'isPrivate': False, **camp}


def corp(*evenimente):
    return {'generatedAt': '2026-10-19T14:05:00+03:00', 'source': 'outlook',
            'windowStart': '2026-10-12', 'windowEnd': '2026-12-18', 'events': list(evenimente)}


# Fereastra cererilor din teste: start=2026-10-12, zile=42 -> [2026-10-12, 2026-11-23).
IN_FEREASTRA = [
    ev('zi-in', '2026-10-20', '2026-10-21', True),
    ev('ora-in', '2026-10-20T09:00:00+03:00', '2026-10-20T10:00:00+03:00'),
    ev('zi-peste-inceput', '2026-10-11', '2026-10-13', True),            # incepe inainte, se termina in fereastra
    ev('ora-peste-inceput', '2026-10-11T22:00:00+03:00', '2026-10-12T01:00:00+03:00'),
    ev('ora-ultima-zi', '2026-11-22T23:00:00+02:00', '2026-11-23T01:00:00+02:00'),   # incepe in ultima zi
]
IN_AFARA = [
    ev('zi-inainte', '2026-10-10', '2026-10-12', True),                  # end exclusiv = inceputul ferestrei
    ev('ora-inainte', '2026-10-11T09:00:00+03:00', '2026-10-11T10:00:00+03:00'),
    ev('zi-peste-capat', '2026-11-23', '2026-11-24', True),              # incepe in prima zi de dupa fereastra
    ev('ora-peste-capat', '2026-11-23T09:00:00+02:00', '2026-11-23T10:00:00+02:00'),
    ev('ora-mult-dupa', '2026-12-01T09:00:00+02:00', '2026-12-01T10:00:00+02:00'),
]


class CalendarulOutlook(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'outlook')
        self.patch(outlook, 'DIR_OUTLOOK', self.dir)
        self.fisier = os.path.join(self.dir, 'calendar.json')

    def pune(self, cuprins, token=FULL, **kw):
        return self.client.put('/api/outlook/calendar', json=cuprins,
                               headers=self.bearer(token) if token else {}, **kw)

    def calendar(self, token=FULL, extra=''):
        r = self.client.get('/api/calendar?start=2026-10-12&zile=42' + extra, headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def octeti(self):
        with open(self.fisier, 'rb') as fh:
            return fh.read()

    # ----------------------------------------------------------------------- PUT valid

    def test_put_valid_scrie_fisierul_si_numara(self):
        r = self.pune(corp(*IN_FEREASTRA, *IN_AFARA))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json(), {'ok': True, 'count': 10})
        self.assertTrue(os.path.isfile(self.fisier))
        scris = json.loads(self.octeti().decode('utf-8'))
        self.assertEqual(len(scris['events']), 10)
        self.assertEqual(scris['generatedAt'], '2026-10-19T14:05:00+03:00')
        self.assertEqual(os.listdir(self.dir), ['calendar.json'], 'niciun .tmp ramas')

    def test_snapshot_gol_e_valid(self):
        r = self.pune(corp())
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'count': 0}))

    def test_a_doua_urcare_inlocuieste_prima_si_repetarea_e_inofensiva(self):
        self.pune(corp(ev('vechi', '2026-10-20', '2026-10-21', True)))
        nou = corp(ev('nou', '2026-10-22', '2026-10-23', True))
        self.assertEqual(self.pune(nou).get_json()['count'], 1)
        dupa_prima = self.octeti()
        self.assertEqual(self.pune(nou).status_code, 200)         # cerere repetata dupa raspuns pierdut
        self.assertEqual(self.octeti(), dupa_prima)
        self.assertEqual([e['id'] for e in json.loads(dupa_prima.decode('utf-8'))['events']], ['nou'])

    def test_titlul_cu_diacritice_se_pastreaza(self):
        self.pune(corp(ev('d', '2026-10-20', '2026-10-21', True, title='Ședință ofertare — țevi', location='Cluj-Napoca')))
        e = self.calendar()['outlook']['events'][0]
        self.assertEqual((e['title'], e['location']), ('Ședință ofertare — țevi', 'Cluj-Napoca'))

    def test_campurile_in_plus_se_ignora_si_nu_se_scriu(self):
        c = corp(ev('x', '2026-10-20', '2026-10-21', True, extra='nu'))
        c['altceva'] = 1
        self.assertEqual(self.pune(c).status_code, 200)
        scris = json.loads(self.octeti().decode('utf-8'))
        self.assertNotIn('altceva', scris)
        self.assertNotIn('extra', scris['events'][0])

    def test_entryid_se_pastreaza_si_ajunge_in_calendar(self):
        eid = '000000002EF00F88527AB540B4BCAD953BEDD3BD0700'
        self.assertEqual(self.pune(corp(ev('cu', '2026-10-20', '2026-10-21', True, entryId=eid),
                                        ev('fara', '2026-10-22', '2026-10-23', True))).status_code, 200)
        evenimente = {e['id']: e for e in self.calendar()['outlook']['events']}
        self.assertEqual(evenimente['cu']['entryId'], eid)
        self.assertNotIn('entryId', evenimente['fara'])          # snapshot de la un script mai vechi

    def test_entryid_gol_sau_null_e_ca_lipsa(self):
        for gol in ('', None):
            self.assertEqual(self.pune(corp(ev('x', '2026-10-20', '2026-10-21', True, entryId=gol))).status_code, 200)
            self.assertNotIn('entryId', json.loads(self.octeti().decode('utf-8'))['events'][0])

    def test_entryid_invalid_da_400_si_nu_atinge_snapshot_ul(self):
        self.pune(corp(ev('bun', '2026-10-20', '2026-10-21', True)))
        inainte = self.octeti()
        for rau in ('outlook:0000000000000000000000', 'ABC', 'zz' * 20, 'A' * 1025, 123, ['00' * 20]):
            r = self.pune(corp(ev('x', '2026-10-20', '2026-10-21', True, entryId=rau)))
            self.assertEqual(r.status_code, 400, repr(rau))
            self.assertIn('events[0].entryId', r.get_json()['error'])
        self.assertEqual(self.octeti(), inainte)

    def test_formele_de_ora_acceptate(self):
        for start, end in (('2026-10-20T09:00:00Z', '2026-10-20T10:00:00Z'),
                           ('2026-10-20T09:00+03:00', '2026-10-20T09:00+03:00'),
                           ('2026-10-20T09:00:00.123+03:00', '2026-10-20T09:00:00.456+03:00'),
                           ('2026-10-20T09:00:00-05:00', '2026-10-20T20:00:00+03:00')):
            r = self.pune(corp(ev('t', start, end)))
            self.assertEqual(r.status_code, 200, (start, end, r.get_data(as_text=True)))

    def test_toata_ziua_cu_capete_egale_e_valida(self):
        self.assertEqual(self.pune(corp(ev('e', '2026-10-20', '2026-10-20', True))).status_code, 200)

    # ----------------------------------------------------------------------- GET /api/calendar

    def test_fara_snapshot_outlook_e_null(self):
        j = self.calendar()
        self.assertIn('outlook', j)
        self.assertIsNone(j['outlook'])
        self.assertTrue(CHEI_VECHI <= set(j))

    def test_restul_raspunsului_ramane_la_fel(self):
        fara = self.calendar()
        self.pune(corp(*IN_FEREASTRA))
        cu = self.calendar()
        self.assertEqual(set(cu) - {'outlook'}, CHEI_VECHI)
        self.assertEqual({k: v for k, v in cu.items() if k != 'outlook'},
                         {k: v for k, v in fara.items() if k != 'outlook'})

    def test_doar_evenimentele_din_fereastra(self):
        self.pune(corp(*IN_AFARA, *IN_FEREASTRA))
        o = self.calendar()['outlook']
        self.assertEqual(set(o), {'generatedAt', 'events'})
        self.assertEqual(o['generatedAt'], '2026-10-19T14:05:00+03:00')
        self.assertEqual(sorted(e['id'] for e in o['events']), sorted(e['id'] for e in IN_FEREASTRA))
        # Evenimentul intors e cel urcat, camp cu camp.
        iesit = {e['id']: e for e in o['events']}
        for e in IN_FEREASTRA:
            self.assertEqual(iesit[e['id']], e)

    def test_fereastra_cererii_hotaraste(self):
        self.pune(corp(*IN_AFARA, *IN_FEREASTRA))
        r = self.client.get('/api/calendar?start=2026-11-23&zile=7', headers=self.bearer())
        ids = sorted(e['id'] for e in r.get_json()['outlook']['events'])
        self.assertEqual(ids, ['ora-peste-capat', 'ora-ultima-zi', 'zi-peste-capat'])

    def test_fisier_corupt_da_null_si_200(self):
        os.makedirs(self.dir)
        for continut in (b'{"events": [', b'\xff\xfe\x00 nu e json', b'[]', b'{"events": 3, "generatedAt": "x"}', b''):
            with open(self.fisier, 'wb') as fh:
                fh.write(continut)
            self.assertIsNone(self.calendar()['outlook'], continut)

    def test_un_eveniment_stricat_in_fisier_nu_strica_restul(self):
        os.makedirs(self.dir)
        bun = ev('bun', '2026-10-20', '2026-10-21', True)
        with open(self.fisier, 'w', encoding='utf-8') as fh:
            json.dump({'generatedAt': '2026-10-19T14:05:00+03:00',
                       'events': [7, {'id': 'fara-campuri'}, bun]}, fh)
        self.assertEqual([e['id'] for e in self.calendar()['outlook']['events']], ['bun'])

    # ----------------------------------------------------------------------- corpuri invalide

    def test_corpuri_invalide_dau_400_cu_campul_si_nu_ating_snapshot_ul(self):
        self.pune(corp(ev('vechi', '2026-10-20', '2026-10-21', True)))
        inainte = self.octeti()

        def cu(mut):
            c = copy.deepcopy(corp(ev('a', '2026-10-20T09:00:00+03:00', '2026-10-20T10:00:00+03:00'),
                                   ev('b', '2026-10-22', '2026-10-23', True)))
            mut(c)
            return c

        def e1(**camp):                       # schimba evenimentul de la indexul 1
            return lambda c: c['events'][1].update(camp)

        def fara1(camp):
            return lambda c: c['events'][1].pop(camp)

        cazuri = [
            ('events[1].id: duplicat', lambda c: c['events'][1].update(id='a')),
            ('events[1].id', e1(id='are spatiu')),
            ('events[1].id', e1(id='x' * 65)),
            ('events[1].id', e1(id='')),
            ('events[1].id', e1(id='a\n')),
            ('events[1].id', e1(id=5)),
            ('events[1].id', fara1('id')),
            ('events[1].end: nu poate fi inainte', e1(start='2026-10-23', end='2026-10-22')),
            ('events[0].end: nu poate fi inainte', lambda c: c['events'][0].update(end='2026-10-20T08:59:00+03:00')),
            ('events[0].end: nu poate fi inainte', lambda c: c['events'][0].update(end='2026-10-20T09:30:00+05:00')),
            ('events[1].busy', e1(busy='ocupat')),
            ('events[1].busy', e1(busy=1)),
            ('events[1].busy', fara1('busy')),
            ('events[1].title', e1(title=5)),
            ('events[1].title', e1(title='t' * 501)),
            ('events[1].title', fara1('title')),
            ('events[1].location', e1(location=None)),
            ('events[1].location', e1(location='l' * 501)),
            ('events[1].allDay', e1(allDay='false')),
            ('events[1].allDay', e1(allDay=0)),
            ('events[1].isPrivate', e1(isPrivate='nu')),
            ('events[1].isPrivate', fara1('isPrivate')),
            ('events[1].start', e1(start='2026-10-22T09:00:00+03:00')),      # allDay cere doar data
            ('events[1].start', e1(start='2026-02-30')),
            ('events[1].start', e1(start=20261022)),
            ('events[1].end', e1(end='22.10.2026')),
            ('events[0].start', lambda c: c['events'][0].update(start='2026-10-20')),   # cu ora cere ora
            ('events[0].start', lambda c: c['events'][0].update(start='2026-10-20T09:00:00')),   # fara offset
            ('events[0].end', lambda c: c['events'][0].update(end='2026-10-20T10:00:00+25:00')),
            ('events[0].end', lambda c: c['events'][0].update(end='2026-13-20T10:00:00+03:00')),
            ('events[0].start', lambda c: c['events'][0].update(start=None)),
            ('events[0]', lambda c: c['events'].__setitem__(0, 'nu e obiect')),
            ('generatedAt', lambda c: c.update(generatedAt='2026-10-19T14:05:00')),
            ('generatedAt', lambda c: c.update(generatedAt=1760875500)),
            ('generatedAt', lambda c: c.pop('generatedAt')),
            ('source', lambda c: c.update(source='google')),
            ('source', lambda c: c.pop('source')),
            ('windowStart', lambda c: c.update(windowStart='12.10.2026')),
            ('windowEnd', lambda c: c.update(windowEnd=None)),
            ('windowEnd: nu poate fi inainte', lambda c: c.update(windowEnd='2026-10-01')),
            ('events', lambda c: c.update(events={'a': 1})),
            ('events', lambda c: c.pop('events')),
        ]
        for asteptat, mut in cazuri:
            r = self.pune(cu(mut))
            self.assertEqual(r.status_code, 400, (asteptat, r.get_data(as_text=True)))
            self.assertIn(asteptat, r.get_json()['error'])
            self.assertEqual(self.octeti(), inainte, 'snapshot-ul vechi trebuie sa ramana neatins: ' + asteptat)
        self.assertEqual(os.listdir(self.dir), ['calendar.json'])

    def test_mai_mult_de_2000_de_evenimente_da_400(self):
        self.pune(corp(ev('vechi', '2026-10-20', '2026-10-21', True)))
        inainte = self.octeti()
        mic = [{'id': 'e%d' % i, 'title': '', 'allDay': True, 'start': '2026-10-20', 'end': '2026-10-21',
                'location': '', 'busy': 'free', 'isPrivate': False} for i in range(2001)]
        r = self.pune(corp(*mic))
        self.assertEqual(r.status_code, 400)
        self.assertIn('events', r.get_json()['error'])
        self.assertEqual(self.octeti(), inainte)
        # Exact 2000 trece.
        self.assertEqual(self.pune(corp(*mic[:2000])).get_json(), {'ok': True, 'count': 2000})

    def test_corp_care_nu_e_json_obiect_da_400(self):
        self.pune(corp(ev('vechi', '2026-10-20', '2026-10-21', True)))
        inainte = self.octeti()
        for brut in (b'', b'nu e json', b'[]', b'"text"', b'null', b'\xff\xfe', b'[' * 5000):
            r = self.client.put('/api/outlook/calendar', data=brut, headers=self.bearer(),
                                content_type='application/json')
            self.assertEqual(r.status_code, 400, brut)
            self.assertIn('error', r.get_json())
        self.assertEqual(self.octeti(), inainte)

    def test_peste_1_mb_da_413_si_nu_atinge_snapshot_ul(self):
        self.pune(corp(ev('vechi', '2026-10-20', '2026-10-21', True)))
        inainte = self.octeti()
        mare = corp(*[ev('e%d' % i, '2026-10-20', '2026-10-21', True, title='t' * 500) for i in range(2000)])
        brut = json.dumps(mare).encode('utf-8')
        self.assertGreater(len(brut), 1024 * 1024)
        r = self.client.put('/api/outlook/calendar', data=brut, headers=self.bearer(),
                            content_type='application/json')
        self.assertEqual(r.status_code, 413)
        self.assertIn('error', r.get_json())
        self.assertEqual(self.octeti(), inainte)

    # ----------------------------------------------------------------------- acces

    def test_fara_token_nu_scrie(self):
        r = self.pune(corp(), token=None)
        self.assertEqual(r.status_code, 401)
        self.assertFalse(os.path.exists(self.fisier))
        self.assertEqual(self.pune(corp(), token='gresit').status_code, 401)
        self.assertFalse(os.path.exists(self.fisier))

    def test_tokenul_de_dispozitiv_nu_scrie_dar_citeste_cheia(self):
        # Acelasi raspuns ca la celelalte rute refuzate dispozitivului (401, nu 403): garda e in
        # `_check_api_token`, iar `login_required` nu stie de ce a fost refuzat tokenul.
        r = self.pune(corp(ev('x', '2026-10-20', '2026-10-21', True)), token=DEVICE)
        self.assertEqual(r.status_code, 401)
        self.assertFalse(os.path.exists(self.fisier))
        self.pune(corp(ev('x', '2026-10-20', '2026-10-21', True)))
        j = self.calendar(token=DEVICE)
        self.assertEqual([e['id'] for e in j['outlook']['events']], ['x'])

    def test_garda_dispozitivului_acopera_orice_metoda_pe_prefix(self):
        from utils import device_token_denied
        for metoda in ('GET', 'PUT', 'POST', 'DELETE'):
            self.assertTrue(device_token_denied(metoda, '/api/outlook/calendar'), metoda)
        self.assertFalse(device_token_denied('GET', '/api/calendar'))

    def test_scrierea_nu_atinge_baza_de_date(self):
        import sqlite3
        def numar():
            c = sqlite3.connect(self.db)
            try:
                return [c.execute('SELECT COUNT(*) FROM %s' % t).fetchone()[0]
                        for t in ('proiecte', 'tasks', 'implementari', 'app_settings')]
            finally:
                c.close()
        inainte = numar()
        self.pune(corp(ev('x', '2026-10-20', '2026-10-21', True)))
        self.assertEqual(numar(), inainte)

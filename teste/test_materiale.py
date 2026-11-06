"""Centralizatorul de materiale: `PUT /api/materiale` (colectorul) si `GET /api/materiale` (Torqa).

Ce se pazeste, tacut daca se strica:
  - un corp care iese din contract da 400 cu calea campului si NU atinge snapshot-ul curent;
  - campurile in plus se pastreaza (colectorul inca evolueaza), sectiunile lipsa devin [];
  - rotatia: snapshot-ul curent devine „anterior" doar cand cel nou e din alta zi; o rulare
    repetata in aceeasi zi nu sterge marcajele; un snapshot mai vechi decat cel curent da 409;
  - marcajele de la GET: nou, mutat (cu termenul vechi), cantitate, stare LM, disparute; fara
    proiect in snapshot-ul anterior, niciun marcaj (altfel totul ar fi „nou");
  - termenele 1900-01-01 si 2030-12-31 raman brute si primesc `termen_neregulat`;
  - `vechi` dupa o zi lucratoare (vineri ramane proaspata pana luni);
  - fara snapshot sau cu fisierul stricat, GET da 200 cu `generat` null;
  - doar tokenul de masina (sau sesiunea) scrie; dispozitivul citeste, dar nu scrie.
Directorul snapshot-urilor e unul temporar: un test nu scrie niciodata in `uploads/` din proiect.
"""

import copy
import json
import os
from datetime import datetime, timezone

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import materiale

PID = 'p-26-337'
PID2 = 'p-26-088'


def termen(ct, art, data, cant=-1, rez='COC1', **camp):
    return {'cod_proiect_bc': '26_088 - Spoting LM:3', 'lm': 3, 'ct': ct, 'cod_articol': art,
            'descriere': 'Articol ' + art, 'termen_confirmat': data, 'cantitate_restanta': cant,
            'um': 'BUC', 'furnizor': 'Furnizor', 'rezervat_din': rez, **camp}


def proiect(pid=PID, cod='26_337', **sectiuni):
    return {'proiect_id': pid, 'cod_proiect': cod, **sectiuni}


def corp(*proiecte, generat='2026-11-06T08:02:11+02:00'):
    return {'generat': generat, 'sursa': {'bc': 'EGBROAPP01\\E100/BC_Data_EGB', 'mail': 'Outlook'},
            'proiecte': list(proiecte)}


NECOMANDAT = {'cod_proiect_bc': '26_337, urmeaza LM, de alocat', 'lm': None, 'ct': 'CT26003872',
              'data_creare_ct': '2026-11-06', 'cod_articol': 'WIK^57510615', 'descriere': 'TRADUCTOR PRESIUNE',
              'cantitate_necomandata': 1, 'um': 'BUC', 'achizitor': 'Oana Giuglea'}
MAIL = {'data': '2026-11-04T10:12', 'de_la': 'Ion Ursu', 'subiect': 'Comanda traductor 26_337',
        'tip': 'comanda_mail', 'ct': [], 'lm': None, 'entry_id': '000000002EF00F88527AB540B4BCAD953BEDD3BD0700'}
ALERTA = {'tip': 'comanda_fara_lm', 'text': 'Comanda pe mail, fara LM in E100', 'din': '2026-11-04',
          'ref': MAIL['entry_id']}


class Materiale(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'materiale')
        self.patch(materiale, 'DIR_MATERIALE', self.dir)
        # „Acum" fix: vineri 6 nov. 2026, 10:00 ora Romaniei.
        self.patch(materiale, '_acum', lambda: datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc))

    def pune(self, cuprins, token=FULL):
        return self.client.put('/api/materiale', json=cuprins, headers=self.bearer(token) if token else {})

    def citeste(self, token=FULL):
        r = self.client.get('/api/materiale', headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def fisier(self, nume):
        with open(os.path.join(self.dir, nume), 'rb') as fh:
            return fh.read()

    def proiect_in(self, j, pid=PID):
        return next(p for p in j['proiecte'] if p['proiect_id'] == pid)

    # ----------------------------------------------------------------------- PUT valid

    def test_put_valid_scrie_si_raspunde(self):
        r = self.pune(corp(proiect(necomandate=[NECOMANDAT], mailuri=[MAIL], alerte=[ALERTA])))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json(), {'ok': True, 'proiecte': 1, 'rotit': False})
        self.assertEqual(os.listdir(self.dir), ['snapshot.json'], 'niciun .tmp ramas, niciun anterior')

    def test_sectiunile_lipsa_devin_liste_goale_si_campurile_in_plus_raman(self):
        p = proiect(necomandate=[dict(NECOMANDAT, camp_nou='x')])
        p['extra_proiect'] = {'a': 1}
        self.assertEqual(self.pune(corp(p)).status_code, 200)
        scris = json.loads(self.fisier('snapshot.json').decode('utf-8'))['proiecte'][0]
        self.assertEqual((scris['lm'], scris['termene'], scris['mailuri'], scris['alerte']), ([], [], [], []))
        self.assertEqual(scris['necomandate'][0]['camp_nou'], 'x')
        self.assertEqual(scris['extra_proiect'], {'a': 1})

    def test_diacriticele_se_pastreaza(self):
        self.pune(corp(proiect(lm=[{'nr': 1, 'stare': 'Trimitere spre aprobare'}],
                               alerte=[dict(ALERTA, text='Comandă pe mail, fără LM în E100')])))
        p = self.proiect_in(self.citeste())
        self.assertEqual(p['alerte'][0]['text'], 'Comandă pe mail, fără LM în E100')

    def test_repetarea_aceleiasi_cereri_lasa_acelasi_fisier(self):
        c = corp(proiect(necomandate=[NECOMANDAT]))
        self.pune(c)
        prima = self.fisier('snapshot.json')
        self.assertEqual(self.pune(c).get_json()['rotit'], False)
        self.assertEqual(self.fisier('snapshot.json'), prima)
        self.assertEqual(sorted(os.listdir(self.dir)), ['snapshot.json'])

    # ----------------------------------------------------------------------- PUT respins

    def test_corp_gresit_da_400_cu_calea_si_nu_atinge_snapshotul(self):
        self.pune(corp(proiect(necomandate=[NECOMANDAT])))
        inainte = self.fisier('snapshot.json')
        cazuri = [
            ({'proiecte': []}, 'generat'),
            (dict(corp(), generat='2026-11-06T08:02:11'), 'generat'),                 # fara offset
            (dict(corp(), proiecte={}), 'proiecte'),
            (corp(proiect(pid='')), 'proiecte[0].proiect_id'),
            (corp(proiect(), proiect()), 'proiecte[1].proiect_id: duplicat'),
            (corp(proiect(cod='')), 'proiecte[0].cod_proiect'),
            (corp(proiect(termene=[termen('CT1', 'A', '12.11.2026')])), 'proiecte[0].termene[0].termen_confirmat'),
            (corp(proiect(termene=[termen('', 'A', None)])), 'proiecte[0].termene[0].ct'),
            (corp(proiect(termene=[termen('CT1', 'A', None, cant='3')])), 'proiecte[0].termene[0].cantitate_restanta'),
            (corp(proiect(termene=[termen('CT1', 'A', None, cant=True)])), 'proiecte[0].termene[0].cantitate_restanta'),
            (corp(proiect(necomandate=[dict(NECOMANDAT, cantitate_necomandata=None)])),
             'proiecte[0].necomandate[0].cantitate_necomandata'),
            (corp(proiect(lm=[{'nr': -1}])), 'proiecte[0].lm[0].nr'),
            (corp(proiect(lm=[{'nr': 1, 'data_stare': '5 nov'}])), 'proiecte[0].lm[0].data_stare'),
            (corp(proiect(mailuri=[dict(MAIL, tip='altceva')])), 'proiecte[0].mailuri[0].tip'),
            (corp(proiect(mailuri=[dict(MAIL, data='2026-11-04')])), 'proiecte[0].mailuri[0].data'),
            (corp(proiect(mailuri=[dict(MAIL, entry_id='nu-hex')])), 'proiecte[0].mailuri[0].entry_id'),
            (corp(proiect(mailuri=[dict(MAIL, ct='CT1')])), 'proiecte[0].mailuri[0].ct'),
            (corp(proiect(alerte=[dict(ALERTA, tip='Comanda')])), 'proiecte[0].alerte[0].tip'),
            (corp(proiect(alerte=[dict(ALERTA, text='')])), 'proiecte[0].alerte[0].text'),
            (corp(proiect(termene='x')), 'proiecte[0].termene: trebuie sa fie o lista'),
            (corp(proiect(termene=['x'])), 'proiecte[0].termene[0]: trebuie sa fie obiect'),
        ]
        for cuprins, mesaj in cazuri:
            with self.subTest(mesaj=mesaj):
                r = self.pune(cuprins)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn(mesaj, r.get_json()['error'])
        self.assertEqual(self.fisier('snapshot.json'), inainte)

    def test_json_invalid_da_400(self):
        r = self.client.put('/api/materiale', data=b'{nu', headers=dict(self.bearer(), **{'Content-Type': 'application/json'}))
        self.assertEqual(r.status_code, 400)

    def test_corp_prea_mare_da_413(self):
        self.patch(materiale, 'MAX_CORP', 1000)
        r = self.pune(corp(proiect(mailuri=[dict(MAIL, subiect='x' * 900), MAIL])))
        self.assertEqual(r.status_code, 413)

    def test_snapshot_mai_vechi_decat_cel_curent_da_409(self):
        self.pune(corp(proiect(), generat='2026-11-06T08:02:11+02:00'))
        r = self.pune(corp(proiect(), generat='2026-11-05T08:02:11+02:00'))
        self.assertEqual(r.status_code, 409)
        self.assertIn('2026-11-06T08:02:11+02:00', r.get_json()['error'])

    # ----------------------------------------------------------------------- autentificarea

    def test_fara_token_sau_cu_token_gresit_401(self):
        self.assertEqual(self.pune(corp(), token=None).status_code, 401)
        self.assertEqual(self.pune(corp(), token='gresit').status_code, 401)
        self.assertEqual(self.client.get('/api/materiale').status_code, 401)

    def test_dispozitivul_citeste_dar_nu_scrie(self):
        self.assertEqual(self.pune(corp(proiect()), token=DEVICE).status_code, 401)
        self.assertFalse(os.path.exists(self.dir))
        self.pune(corp(proiect()))
        self.assertEqual(len(self.citeste(token=DEVICE)['proiecte']), 1)
        from utils import device_token_denied
        for metoda in ('PUT', 'POST', 'DELETE'):
            self.assertTrue(device_token_denied(metoda, '/api/materiale'), metoda)
        self.assertFalse(device_token_denied('GET', '/api/materiale'))

    # ----------------------------------------------------------------------- GET si rotatia

    def test_fara_snapshot_sau_cu_fisier_stricat_get_da_200_gol(self):
        gol = {'generat': None, 'comparat_cu': None, 'vechi': True, 'sursa': {}, 'proiecte': []}
        self.assertEqual(self.citeste(), gol)
        os.makedirs(self.dir)
        with open(os.path.join(self.dir, 'snapshot.json'), 'w', encoding='utf-8') as fh:
            fh.write('{stricat')
        with self.assertLogs('pif_dashboard', level='WARNING'):
            self.assertEqual(self.citeste(), gol)

    def test_prima_colectare_nu_are_marcaje(self):
        self.pune(corp(proiect(PID2, '26_088', termene=[termen('CT1', 'A', '2026-11-10')],
                               lm=[{'nr': 3, 'stare': 'Aprobata'}], mailuri=[MAIL])))
        j = self.citeste()
        self.assertIsNone(j['comparat_cu'])
        p = self.proiect_in(j, PID2)
        self.assertIsNone(p['termene'][0]['schimbare'])
        self.assertIsNone(p['lm'][0]['schimbare'])
        self.assertIsNone(p['mailuri'][0]['schimbare'])
        self.assertEqual(p['disparute'], {'lm': [], 'termene': [], 'necomandate': []})

    def test_rotatia_doar_la_zi_noua(self):
        self.pune(corp(proiect(), generat='2026-11-05T08:01:00+02:00'))
        r = self.pune(corp(proiect(), generat='2026-11-06T08:02:11+02:00'))
        self.assertTrue(r.get_json()['rotit'])
        self.assertEqual(sorted(os.listdir(self.dir)), ['snapshot.json', 'snapshot.prev.json'])
        # A doua rulare in aceeasi zi: anteriorul ramane cel de ieri.
        r = self.pune(corp(proiect(), generat='2026-11-06T11:30:00+02:00'))
        self.assertFalse(r.get_json()['rotit'])
        j = self.citeste()
        self.assertEqual((j['generat'], j['comparat_cu']), ('2026-11-06T11:30:00+02:00', '2026-11-05T08:01:00+02:00'))

    def test_marcajele_fata_de_ziua_anterioara(self):
        ieri = proiect(PID2, '26_088',
                       termene=[termen('CT1', 'MUTAT', '2026-11-10'), termen('CT1', 'LA_FEL', '2026-11-10'),
                                termen('CT1', 'CANT', '2026-11-12', cant=-6), termen('CT2', 'PLECAT', '2026-11-08')],
                       necomandate=[dict(NECOMANDAT, ct='CT9', cantitate_necomandata=2)],
                       lm=[{'nr': 3, 'stare': 'Trimitere spre aprobare'}, {'nr': 4, 'stare': 'Redactare'}],
                       mailuri=[MAIL], alerte=[ALERTA])
        azi = proiect(PID2, '26_088',
                      termene=[termen('CT1', 'MUTAT', '2026-11-12'), termen('CT1', 'LA_FEL', '2026-11-10'),
                               termen('CT1', 'CANT', '2026-11-12', cant=-2), termen('CT3', 'NOU', '2026-11-18')],
                      necomandate=[dict(NECOMANDAT, ct='CT9', cantitate_necomandata=1)],
                      lm=[{'nr': 3, 'stare': 'Aprobata'}, {'nr': 5, 'stare': 'Redactare'}],
                      mailuri=[MAIL, dict(MAIL, subiect='RE: Comanda', entry_id='00AA' * 6)],
                      alerte=[ALERTA, dict(ALERTA, tip='alta', ref='CT3')])
        self.pune(corp(ieri, generat='2026-11-05T08:01:00+02:00'))
        self.pune(corp(azi, generat='2026-11-06T08:02:11+02:00'))
        p = self.proiect_in(self.citeste(), PID2)
        t = {r['cod_articol']: r for r in p['termene']}
        self.assertEqual((t['MUTAT']['schimbare'], t['MUTAT']['termen_anterior']), ('mutat', '2026-11-10'))
        self.assertIsNone(t['LA_FEL']['schimbare'])
        self.assertEqual((t['CANT']['schimbare'], t['CANT']['cantitate_anterioara']), ('cantitate', -6))
        self.assertEqual(t['NOU']['schimbare'], 'nou')
        self.assertEqual([r['cod_articol'] for r in p['disparute']['termene']], ['PLECAT'])
        self.assertEqual((p['necomandate'][0]['schimbare'], p['necomandate'][0]['cantitate_anterioara']),
                         ('cantitate', 2))
        lm = {r['nr']: r for r in p['lm']}
        self.assertEqual((lm[3]['schimbare'], lm[3]['stare_anterioara']), ('stare', 'Trimitere spre aprobare'))
        self.assertEqual(lm[5]['schimbare'], 'nou')
        self.assertEqual([r['nr'] for r in p['disparute']['lm']], [4])
        self.assertEqual([m['schimbare'] for m in p['mailuri']], [None, 'nou'])
        self.assertEqual([a['schimbare'] for a in p['alerte']], [None, 'nou'])

    def test_acelasi_articol_de_mai_multe_ori_pe_acelasi_ct(self):
        # Cazul real CT26003799: aceeasi clema de trei ori, cu cantitati diferite.
        ieri = proiect(termene=[termen('CT1', 'CLEMA', None, -10), termen('CT1', 'CLEMA', None, -1),
                                termen('CT1', 'CLEMA', None, -1)])
        azi = proiect(termene=[termen('CT1', 'CLEMA', None, -1), termen('CT1', 'CLEMA', '2026-11-12', -10),
                               termen('CT1', 'CLEMA', None, -1)])
        self.pune(corp(ieri, generat='2026-11-05T08:01:00+02:00'))
        self.pune(corp(azi, generat='2026-11-06T08:02:11+02:00'))
        p = self.proiect_in(self.citeste())
        marcaje = sorted((r['cantitate_restanta'], r['schimbare']) for r in p['termene'])
        self.assertEqual(marcaje, [(-10, 'mutat'), (-1, None), (-1, None)])
        self.assertEqual(p['disparute']['termene'], [])

    def test_proiect_nou_fata_de_ziua_anterioara_nu_are_marcaje(self):
        self.pune(corp(proiect(PID2, '26_088'), generat='2026-11-05T08:01:00+02:00'))
        self.pune(corp(proiect(PID2, '26_088'), proiect(termene=[termen('CT1', 'A', None)]),
                       generat='2026-11-06T08:02:11+02:00'))
        self.assertIsNone(self.proiect_in(self.citeste())['termene'][0]['schimbare'])

    def test_termenele_neregulate_raman_brute_si_sunt_semnalate(self):
        self.pune(corp(proiect(termene=[termen('CT1', 'A', '2030-12-31'), termen('CT1', 'B', '1900-01-01'),
                                        termen('CT1', 'C', '2026-11-12'), termen('CT1', 'D', None)])))
        t = {r['cod_articol']: r for r in self.proiect_in(self.citeste())['termene']}
        self.assertEqual(t['A']['termen_confirmat'], '2030-12-31')
        self.assertEqual({k: v['termen_neregulat'] for k, v in t.items()},
                         {'A': True, 'B': True, 'C': False, 'D': False})

    def test_numele_proiectului_vine_din_baza(self):
        r = self.client.post('/api/proiecte', json={'id': PID, 'nume': 'Service traductor', 'tip': 'PIF',
                                                    'client': 'ROMKUVERT IND SRL'}, headers=self.bearer())
        self.assertIn(r.status_code, (200, 201), r.get_data(as_text=True))
        self.pune(corp(proiect(), proiect('p-sters', '26_000')))
        j = self.citeste()
        self.assertEqual(self.proiect_in(j)['proiect']['nume'], 'Service traductor')
        self.assertEqual(self.proiect_in(j)['proiect']['client'], 'ROMKUVERT IND SRL')
        self.assertIsNone(self.proiect_in(j, 'p-sters')['proiect'])

    def test_snapshotul_de_pe_disc_nu_primeste_marcajele(self):
        self.pune(corp(proiect(termene=[termen('CT1', 'A', '2030-12-31')])))
        self.citeste()
        scris = json.loads(self.fisier('snapshot.json').decode('utf-8'))
        self.assertNotIn('termen_neregulat', scris['proiecte'][0]['termene'][0])
        self.assertNotIn('disparute', scris['proiecte'][0])

    # ----------------------------------------------------------------------- vechimea

    def test_vechi_dupa_o_zi_lucratoare(self):
        utc = timezone.utc
        cazuri = [
            ('2026-11-05T08:02:00+02:00', datetime(2026, 11, 6, 8, 0, tzinfo=utc), False),   # joi -> vineri
            ('2026-11-05T08:02:00+02:00', datetime(2026, 11, 6, 9, 0, tzinfo=utc), True),    # dupa marja
            ('2026-11-06T08:02:00+02:00', datetime(2026, 11, 9, 7, 30, tzinfo=utc), False),  # vineri -> luni
            ('2026-11-06T08:02:00+02:00', datetime(2026, 11, 10, 7, 0, tzinfo=utc), True),   # vineri -> marti
        ]
        for generat, acum, asteptat in cazuri:
            with self.subTest(generat=generat, acum=acum):
                self.assertEqual(materiale.e_vechi(generat, acum), asteptat)

    def test_get_spune_vechi(self):
        self.pune(corp(proiect(), generat='2026-11-03T08:00:00+02:00'))
        self.assertTrue(self.citeste()['vechi'])
        self.pune(corp(proiect(), generat='2026-11-06T08:02:11+02:00'))
        self.assertFalse(self.citeste()['vechi'])

    # ----------------------------------------------------------------------- copie

    def test_get_nu_modifica_snapshotul_intre_cereri(self):
        self.pune(corp(proiect(termene=[termen('CT1', 'A', None)])))
        prima = self.citeste()
        self.assertEqual(self.citeste(), prima)
        self.assertEqual(copy.deepcopy(prima), prima)

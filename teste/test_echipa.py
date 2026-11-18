"""Planul echipei din Gantt: `PUT/GET /api/echipa/sursa`, `GET /api/echipa` si cheia `echipa` din
`GET /api/calendar`.

Ce se pazeste, tacut daca se strica:
  - secretul planului nu iese NICIODATA: nici in raspunsuri, nici in log, nici in mesajele de eroare;
  - sursa se schimba doar dupa o citire de proba reusita; un PUT respins lasa sursa veche;
  - dispozitivul nu scrie sursa (401), dar citeste planul;
  - snapshot-ul e normalizat (fara email-uri, entraId, hash-uri), cu capatul de interval INCLUSIV;
  - cache-ul e de 15 minute; un Gantt cazut lasa snapshot-ul vechi cu `stale: true` si nu e
    reincercat in fiecare cerere;
  - cele trei avertizari (perioada_diferita, lipseste_in_dashboard, lipseste_in_srp) si cazul fara;
  - `/api/calendar` are aceleasi chei ca inainte, plus `echipa` (aditiv).
Toate datele sunt sintetice; reteaua e inlocuita (`echipa._descarca`), iar directorul snapshot-ului
e unul temporar: un test nu scrie niciodata in `uploads/` din proiect.
"""

import contextlib
import json
import logging
import os
import sqlite3
import time
import urllib.error
from datetime import datetime, timedelta, timezone
from unittest import mock

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import echipa

CHEI_VECHI = {'start', 'zile', 'today', 'perioade', 'taskuri', 'de_decis', 'neplanificate', 'probleme'}

PLAN_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
SECRET = '11111111-2222-3333-4444-555555555555'
EMAIL = 'eu@exemplu.test'
_REALA = echipa._descarca          # `_descarca` adevarata; setUp o inlocuieste cu un mock
AZI = '2026-11-18'
T0 = datetime(2026, 11, 18, 10, 0, 0, tzinfo=timezone.utc)

RESURSE = [
    {'displayName': 'Eu Sintetic', 'fullName': 'Eu Test Sintetic', 'email': EMAIL, 'entraId': 'entra-secret-1', 'id': 'r1'},
    {'displayName': 'Coleg Unu', 'fullName': 'Coleg Test', 'email': 'coleg@exemplu.test', 'entraId': 'entra-secret-2', 'id': 'r2'},
]


def act(id_, text, parent, start, end, resource=None, **extra):
    """O activitate ca in Gantt: `start` si `end` ca stringurile lui (cu ora)."""
    a = {'id': id_, 'parent': parent, 'text': text, 'start_date': start, 'end_date': end, 'duration': 1,
         'progress': 0, 'type': 'task', 'color': '#123456', 'open': True, 'description': '', 'render': '',
         'rollup': False, 'unscheduled': False}
    if resource is not None:
        a['resource'] = resource
    a.update(extra)
    return a


def zi(luna_zi, final=False):
    """'11-18' -> '2026-11-18 00:00' (inceput) sau '2026-11-18 23:59' (sfarsit, ca in Gantt)."""
    return '2026-%s %s' % (luna_zi, '23:59' if final else '00:00')


def gantt(activitati, resurse=None):
    """Raspunsul brut al Gantt-ului: `plan` si `resources` sunt STRINGURI JSON, plus campuri pe care
    snapshot-ul nu trebuie sa le pastreze."""
    return {
        'planId': PLAN_ID, 'secret': SECRET, 'writePassHash': 'hash-scriere-secret',
        'lockedByEmail': 'cineva@exemplu.test', 'ownerEmail': 'owner@exemplu.test', 'ownerEntraId': 'entra-owner',
        'plan': json.dumps({'data': activitati, 'links': [], 'baselines': None}),
        'displaySettings': '{}', 'resources': json.dumps(RESURSE if resurse is None else resurse),
        'encryptedResources': None, 'projectStatus': 'x', 'license': 'x', 'timestamp': 1,
    }


def plan_echipa():
    """Planul sintetic al testelor de avertizari (azi = 2026-11-18)."""
    return [
        act(1001, 'C26_287_Proiect Sintetic Unu', 0, zi('11-16'), zi('11-20', True), resource=[]),
        act(1002, 'E1_PIF', '1001', zi('11-18'), zi('11-19', True), resource=['r1']),         # parent STRING
        act(1003, 'E2_PIF', 1001, zi('11-16'), zi('11-17', True), resource=['r2']),           # a colegului, si trecuta
        act(2001, '26_088_Proiect Doi', 0, zi('11-09'), zi('11-22', True)),
        act(2002, 'E1_PIF', 2001, zi('11-09'), zi('11-22', True), resource=['r1']),
        act(3001, '800_Mentenanta Sintetica', 0, zi('11-01'), zi('12-31', True), resource=['r1']),   # fara cod, fara etape
        act(4001, 'C26_555_Doar Coleg', 0, zi('11-20'), zi('11-27', True)),
        act(4002, 'E1_PIF', 4001, zi('11-20'), zi('11-27', True), resource=['r2']),
    ]


class Gantt:
    """Un `_descarca` de test: numara apelurile si intoarce (sau ridica) ce i se spune."""

    def __init__(self, raspuns=None):
        self.raspuns = raspuns
        self.apeluri = []

    def __call__(self, plan_id, secret):
        self.apeluri.append((plan_id, secret))
        if isinstance(self.raspuns, Exception):
            raise self.raspuns
        return self.raspuns


class CuEchipa(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'echipa')
        self.patch(echipa, 'DIR_ECHIPA', self.dir)
        self.ceas = [T0]
        self.patch(echipa, '_acum', lambda: self.ceas[0])
        self.patch(echipa, '_azi', lambda: AZI)
        self.gantt = Gantt(gantt(plan_echipa()))
        self.patch(echipa, '_descarca', self.gantt)
        self._goleste_dashboard()

    # ----------------------------------------------------------------------- ajutoare

    def _goleste_dashboard(self):
        con = sqlite3.connect(self.db)
        con.execute('DELETE FROM implementari')
        con.execute('DELETE FROM proiecte')
        con.commit()
        con.close()

    def dashboard(self, *proiecte):
        """(id, cod, status, [(start, end), ...]) -> randuri in `proiecte` si `implementari`."""
        con = sqlite3.connect(self.db)
        for pid, cod, status, perioade in proiecte:
            con.execute("INSERT INTO proiecte (id, tip, nume, cod_proiect, status) VALUES (?, 'pif', ?, ?, ?)",
                        (pid, 'Proiect ' + pid, cod, status))
            for ix, (s, e) in enumerate(perioade):
                con.execute('INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit) VALUES (?, ?, ?, ?)',
                            ('%s-i%d' % (pid, ix), pid, s, e))
        con.commit()
        con.close()

    def pune_sursa(self, token=FULL, **corp):
        c = {'planId': PLAN_ID, 'secret': SECRET, 'email': EMAIL}
        c.update(corp)
        return self.client.put('/api/echipa/sursa', json=c, headers=self.bearer(token) if token else {})

    def configureaza(self):
        r = self.pune_sursa()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r

    def echipa(self, token=FULL):
        r = self.client.get('/api/echipa', headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def calendar(self, extra=''):
        r = self.client.get('/api/calendar?start=2026-11-16&zile=14' + extra, headers=self.bearer())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def fisier(self, nume):
        with open(os.path.join(self.dir, nume), 'rb') as fh:
            return fh.read()

    def avertizari(self):
        return self.echipa()['avertizari']


# =============================================================================== normalizare

class Normalizare(CuEchipa):

    def norm(self, activitati, resurse=None):
        return echipa.normalizeaza(gantt(activitati, resurse), EMAIL, acum=T0)

    def test_capatul_e_inclusiv_pentru_23_59_01_00_si_00_00(self):
        s = self.norm([
            act(1, 'A', 0, '2026-11-18 00:00', '2026-11-19 23:59'),
            act(2, 'B', 0, '2026-11-18 00:00', '2026-11-19 01:00'),
            act(3, 'C', 0, '2026-11-18 00:00', '2026-11-20 00:00'),     # 00:00 = ziua dinainte
            act(4, 'D', 0, '2026-11-18 00:00', '2026-11-18 00:00'),     # nu poate iesi inaintea inceputului
        ])
        end = {a['id']: (a['start'], a['end']) for a in s['activitati']}
        self.assertEqual(end['1'], ('2026-11-18', '2026-11-19'))
        self.assertEqual(end['2'], ('2026-11-18', '2026-11-19'))
        self.assertEqual(end['3'], ('2026-11-18', '2026-11-19'))
        self.assertEqual(end['4'], ('2026-11-18', '2026-11-18'))

    def test_parinte_int_sau_string_da_acelasi_proiect(self):
        s = self.norm([
            act(1768390299382, 'C26_287_Sintetic', 0, zi('11-16'), zi('11-20', True)),
            act(10, 'E1', '1768390299382', zi('11-16'), zi('11-17', True)),
            act(11, 'E2', 1768390299382, zi('11-18'), zi('11-19', True)),
        ])
        a = {x['id']: x for x in s['activitati']}
        self.assertIsNone(a['1768390299382']['parinte_id'])
        self.assertEqual(a['10']['parinte_id'], '1768390299382')
        self.assertEqual(a['11']['parinte_id'], '1768390299382')
        for i in ('10', '11', '1768390299382'):
            self.assertEqual(a[i]['proiect_text'], 'C26_287_Sintetic')
            self.assertEqual(a[i]['cod'], '26_287')               # etapele mostenesc codul de la radacina
        self.assertTrue(all(isinstance(x['id'], str) for x in s['activitati']))

    def test_resursele_lipsa_goale_sau_necunoscute_si_ale_mele(self):
        s = self.norm([
            act(1, 'fara cheie', 0, zi('11-18'), zi('11-18', True)),
            act(2, 'goala', 0, zi('11-18'), zi('11-18', True), resource=[]),
            act(3, 'nula', 0, zi('11-18'), zi('11-18', True), resource=None),
            act(4, 'a mea', 0, zi('11-18'), zi('11-18', True), resource=['r1', 'r2']),
            act(5, 'a altuia', 0, zi('11-18'), zi('11-18', True), resource=['r2']),
        ])
        a = {x['id']: x for x in s['activitati']}
        self.assertEqual([a[i]['resurse'] for i in '12345'], [[], [], [], ['r1', 'r2'], ['r2']])
        self.assertEqual([a[i]['ale_mele'] for i in '12345'], [False, False, False, True, False])
        self.assertEqual(s['eu'], 'r1')

    def test_snapshot_nu_pastreaza_email_entraid_hash_sau_secret(self):
        s = self.norm(plan_echipa())
        text = json.dumps(s)
        for interzis in ('exemplu.test', 'entra-', 'hash-scriere', SECRET, PLAN_ID, 'writePassHash', 'ownerEmail'):
            self.assertNotIn(interzis, text)
        self.assertEqual(s['resurse'], [{'id': 'r1', 'nume': 'Eu Sintetic'}, {'id': 'r2', 'nume': 'Coleg Unu'}])
        self.assertEqual(set(s), {'generatedAt', 'eu', 'resurse', 'activitati'})
        self.assertEqual(s['generatedAt'], '2026-11-18T10:00:00Z')
        self.assertEqual(set(s['activitati'][0]), {'id', 'parinte_id', 'text', 'proiect_text', 'start', 'end', 'stare',
                                                   'progres', 'resurse', 'ale_mele', 'cod', 'proiect_id'})

    def test_stare_si_progres(self):
        s = self.norm([act(1, 'A', 0, zi('11-18'), zi('11-18', True), state='problem', progress=0.4),
                       act(2, 'B', 0, zi('11-18'), zi('11-18', True), progress=7)])
        a = {x['id']: x for x in s['activitati']}
        self.assertEqual((a['1']['stare'], a['1']['progres']), ('problem', 0.4))
        self.assertEqual((a['2']['stare'], a['2']['progres']), (None, 1.0))

    def test_email_necunoscut_da_eu_null_si_activitate_cu_data_stricata_se_omite(self):
        s = self.norm([act(1, 'A', 0, zi('11-18'), zi('11-18', True), resource=['r1']),
                       act(2, 'B', 0, 'nu e data', zi('11-18', True))], resurse=[RESURSE[1]])
        self.assertIsNone(s['eu'])
        self.assertEqual([a['id'] for a in s['activitati']], ['1'])
        self.assertFalse(s['activitati'][0]['ale_mele'])

    def test_forma_neasteptata_ridica_eroare_fara_sa_citeze_continutul(self):
        for raw in ({'plan': 'nu e json', 'resources': '[]'}, {'plan': '{"data": 3}', 'resources': '[]'},
                    {'plan': '{"data": []}', 'resources': '{"x": 1}'}, {}):
            with self.assertRaises(echipa.EroareGantt):
                echipa.normalizeaza(raw, EMAIL)


# =============================================================================== coduri

class Coduri(CuEchipa):

    def cod(self, text):
        return echipa.cod_text(echipa.analiza_cod(text))

    def test_formele_din_gantt(self):
        for text, asteptat in (
                ('C26_287_VLG_Retro-fit Actionare de CC', '26_287'),
                ('26_088_SPOTING_Linie', '26_088'),
                ('C25_020_An FEED', '25_020'),
                ('250826E_C1_ABB-Linie', '250826E_C1'),
                ('230728_C1_Sitline', '230728_C1'),
                ('250656E_Carmeuse Sintetic', '250656E'),
                ('800_Mentenanta', None),
                ('E1_PIF', None), ('', None), (None, None), ('Proiect 26_287', None),
                ('26_2870_prea lung', None), ('2508261_prea lung', None)):
            self.assertEqual(self.cod(text), asteptat, text)

    def test_potrivirea_cu_codurile_din_dashboard(self):
        def p(gantt_text, dashboard):
            return echipa.coduri_potrivite(echipa.analiza_cod(gantt_text), echipa.analiza_cod(dashboard))
        self.assertTrue(p('C26_287_VLG', '26_287'))
        self.assertTrue(p('26_088_SPOTING', '26_088'))
        self.assertTrue(p('C25_020_An', '25_020'))
        self.assertTrue(p('250826E_C1_ABB', '250826E_C1'))
        self.assertTrue(p('230728_C1_Sitline', '230728E_C1'))       # E lipseste in Gantt
        self.assertTrue(p('250656E_Carmeuse', '250656E'))
        self.assertTrue(p('250656E_Carmeuse', '250656E_C2'))        # sufix doar pe o parte: nu conteaza
        self.assertFalse(p('250826E_C1_ABB', '250826E_C2'))         # sufix pe ambele parti, diferit
        self.assertFalse(p('26_287_x', '26_288'))
        self.assertFalse(p('26_287_x', '262870'))
        self.assertFalse(p('800_Mentenanta', '800'))
        self.assertFalse(p('26_287_x', 'TBD'))
        self.assertFalse(p('26_287_x', ''))
        self.assertFalse(p('26_287_x', None))

    def test_proiect_id_pe_activitati_si_codurile_nepotrivite_raman_null(self):
        self.dashboard(('p1', '26_287', 'pregatire', []), ('p2', 'TBD', 'pregatire', []), ('p3', '', 'pregatire', []),
                       ('p4', None, 'pregatire', []))
        self.configureaza()
        a = {x['id']: x for x in self.echipa()['activitati']}
        self.assertEqual((a['1001']['proiect_id'], a['1002']['proiect_id'], a['1003']['proiect_id']), ('p1', 'p1', 'p1'))
        self.assertIsNone(a['2002']['proiect_id'])
        self.assertIsNone(a['3001']['proiect_id'])

    def test_la_doua_proiecte_cu_acelasi_cod_castiga_cel_activ(self):
        self.dashboard(('a-vechi', '26_287', 'finalizat', []), ('b-activ', '26_287', 'pregatire', []))
        self.configureaza()
        self.assertEqual({a['proiect_id'] for a in self.echipa()['activitati'] if a['cod'] == '26_287'}, {'b-activ'})


# =============================================================================== avertizari

class Avertizari(CuEchipa):

    def test_exemplele_reale_de_azi_cu_date_sintetice(self):
        self.dashboard(
            ('p1', '26_287', 'pregatire', [('2026-11-18', '2026-11-19')]),   # = etapa din Gantt: fara avertizare
            ('p2', '26_088', 'pregatire', [('2026-11-30', '2026-12-01')]),   # Gantt 09-22.11: perioada_diferita
            ('p3', '26_337', 'pregatire', [('2026-11-28', '2026-11-29')]),   # absent din Gantt: lipseste_in_srp
            ('p4', 'TBD', 'pregatire', [('2026-11-20', '2026-11-21')]),      # fara cod: nu se poate compara
            ('p6', '26_555', 'pregatire', [('2026-11-25', '2026-11-25')]),   # in Gantt doar la un coleg
        )
        self.configureaza()
        av = self.avertizari()
        pe_tip = {}
        for a in av:
            pe_tip.setdefault(a['tip'], []).append(a)
        self.assertEqual(sorted(pe_tip), ['lipseste_in_dashboard', 'lipseste_in_srp', 'perioada_diferita'])
        self.assertEqual(len(av), 4, av)
        self.assertEqual(pe_tip['perioada_diferita'], [{
            'tip': 'perioada_diferita', 'proiect_id': 'p2', 'cod': '26_088', 'proiect_nume': 'Proiect p2',
            'srp': {'activitate_id': '2002', 'text': 'E1_PIF', 'start': '2026-11-09', 'end': '2026-11-22'},
            'dashboard': {'implementare_id': 'p2-i0', 'start': '2026-11-30', 'end': '2026-12-01'}}])
        self.assertEqual(sorted(a['proiect_id'] for a in pe_tip['lipseste_in_srp']), ['p3', 'p6'])
        srp = [a for a in pe_tip['lipseste_in_srp'] if a['proiect_id'] == 'p3'][0]
        self.assertEqual(srp, {'tip': 'lipseste_in_srp', 'proiect_id': 'p3', 'cod': '26_337', 'proiect_nume': 'Proiect p3',
                               'srp': None, 'dashboard': {'implementare_id': 'p3-i0', 'start': '2026-11-28', 'end': '2026-11-29'}})
        self.assertEqual(pe_tip['lipseste_in_dashboard'], [{
            'tip': 'lipseste_in_dashboard', 'proiect_id': None, 'cod': None, 'proiect_nume': '800_Mentenanta Sintetica',
            'srp': {'activitate_id': '3001', 'text': '800_Mentenanta Sintetica', 'start': '2026-11-01', 'end': '2026-12-31'},
            'dashboard': None}])

    def test_fara_avertizari_cand_planurile_se_potrivesc(self):
        self.gantt.raspuns = gantt([
            act(1001, 'C26_287_Proiect Sintetic Unu', 0, zi('11-16'), zi('11-20', True)),
            act(1002, 'E1_PIF', '1001', zi('11-18'), zi('11-19', True), resource=['r1']),
            act(1003, 'E2_PIF', 1001, zi('11-16'), zi('11-17', True), resource=['r2'])])
        self.dashboard(('p1', '26_287', 'pregatire', [('2026-11-18', '2026-11-19')]))
        self.configureaza()
        self.assertEqual(self.avertizari(), [])

    def test_perioada_fara_sfarsit_e_o_zi(self):
        self.gantt.raspuns = gantt([act(1, '26_287_x', 0, zi('11-20'), zi('11-20', True), resource=['r1'])])
        self.dashboard(('p1', '26_287', 'pregatire', [('2026-11-20', '')]))
        self.configureaza()
        self.assertEqual(self.avertizari(), [])

    def test_intervale_perechi_dupa_suprapunere_apoi_dupa_data_cea_mai_apropiata(self):
        self.gantt.raspuns = gantt([
            act(1, '26_100_Sintetic', 0, zi('11-01'), zi('02-01', True)) | {'start_date': '2026-11-01 00:00', 'end_date': '2027-02-01 23:59'},
            act(2, 'A exact', 1, zi('11-20'), zi('11-21', True), resource=['r1']),
            act(3, 'B suprapus', 1, zi('11-25'), zi('11-26', True), resource=['r1']),
            act(4, 'C aproape', 1, zi('12-05'), zi('12-06', True), resource=['r1']),
            act(5, 'D singur', 1, '2027-01-10 00:00', '2027-01-11 23:59', resource=['r1']),
            act(6, 'E trecut', 1, zi('11-01'), zi('11-05', True), resource=['r1']),     # end < azi: nu conteaza
        ])
        self.dashboard(('p1', '26_100', 'pregatire', [
            ('2026-11-20', '2026-11-21'),        # = A
            ('2026-11-26', '2026-11-28'),        # se suprapune cu B
            ('2026-12-20', '2026-12-20'),        # cel mai apropiat liber de C
            ('2026-11-02', '2026-11-03'),        # trecut: nu conteaza
        ]))
        self.configureaza()
        av = self.avertizari()
        self.assertEqual([a['tip'] for a in av], ['perioada_diferita'] * 3, av)
        cuplu = [((a['srp'] or {}).get('text'), (a['dashboard'] or {}).get('start')) for a in av]
        self.assertEqual(sorted(cuplu, key=str), sorted([('B suprapus', '2026-11-26'), ('C aproape', '2026-12-20'),
                                                         ('D singur', None)], key=str))

    def test_interval_doar_in_dashboard_are_srp_null(self):
        self.gantt.raspuns = gantt([act(1, '26_100_x', 0, zi('11-20'), zi('11-21', True), resource=['r1'])])
        self.dashboard(('p1', '26_100', 'pregatire', [('2026-11-20', '2026-11-21'), ('2026-12-01', '2026-12-02')]))
        self.configureaza()
        av = self.avertizari()
        self.assertEqual(len(av), 1)
        self.assertEqual((av[0]['tip'], av[0]['srp'], av[0]['dashboard']['start']), ('perioada_diferita', None, '2026-12-01'))

    def test_pentru_activitatile_lui_ion_se_folosesc_frunzele(self):
        # Radacina e a lui Ion si acopera 18-30.11, dar ce conteaza sunt etapele (frunzele).
        self.gantt.raspuns = gantt([
            act(1, '26_100_x', 0, zi('11-18'), zi('11-30', True), resource=['r1']),
            act(2, 'E1', 1, zi('11-18'), zi('11-19', True), resource=['r1']),
            act(3, 'E2', 1, zi('11-25'), zi('11-26', True), resource=['r1'])])
        self.dashboard(('p1', '26_100', 'pregatire', [('2026-11-18', '2026-11-19'), ('2026-11-25', '2026-11-26')]))
        self.configureaza()
        self.assertEqual(self.avertizari(), [])

    def test_perioadele_trecute_nu_dau_avertizari(self):
        self.gantt.raspuns = gantt([act(1, '26_100_x', 0, zi('11-01'), zi('11-05', True), resource=['r1'])])
        self.dashboard(('p1', '26_100', 'pregatire', [('2026-11-02', '2026-11-03')]),
                       ('p2', '26_200', 'pregatire', [('2026-11-02', '2026-11-03')]))
        self.configureaza()
        self.assertEqual(self.avertizari(), [])

    def test_proiect_finalizat_nu_e_lipsa_din_srp_iar_dashboard_nu_se_scrie(self):
        self.dashboard(('p1', '26_777', 'finalizat', [('2026-11-25', '2026-11-26')]))
        self.configureaza()
        con = sqlite3.connect(self.db)
        inainte = con.execute('SELECT id, proiect_id, data_start, data_sfarsit, confirmata FROM implementari ORDER BY id').fetchall()
        con.close()
        self.assertEqual([a for a in self.avertizari() if a['proiect_id'] == 'p1'], [])
        con = sqlite3.connect(self.db)
        dupa = con.execute('SELECT id, proiect_id, data_start, data_sfarsit, confirmata FROM implementari ORDER BY id').fetchall()
        con.close()
        self.assertEqual(inainte, dupa)


# =============================================================================== citire

class Citire(CuEchipa):

    def test_fara_sursa_si_fara_snapshot_raspunsul_e_null(self):
        r = self.client.get('/api/echipa', headers=self.bearer())
        self.assertEqual((r.status_code, r.get_json()), (200, None))
        self.assertEqual(self.gantt.apeluri, [])
        self.assertIsNone(self.calendar()['echipa'])

    def test_get_echipa_contractul(self):
        self.dashboard(('p1', '26_287', 'pregatire', [('2026-11-18', '2026-11-19')]))
        self.configureaza()
        j = self.echipa()
        self.assertEqual(set(j), {'generatedAt', 'stale', 'eu', 'resurse', 'activitati', 'avertizari'})
        self.assertEqual((j['generatedAt'], j['stale'], j['eu']), ('2026-11-18T10:00:00Z', False, 'r1'))
        self.assertEqual(len(j['activitati']), 8)
        etapa = [a for a in j['activitati'] if a['id'] == '1002'][0]
        self.assertEqual(etapa, {'id': '1002', 'parinte_id': '1001', 'text': 'E1_PIF',
                                 'proiect_text': 'C26_287_Proiect Sintetic Unu', 'start': '2026-11-18', 'end': '2026-11-19',
                                 'stare': None, 'progres': 0.0, 'resurse': ['r1'], 'ale_mele': True,
                                 'cod': '26_287', 'proiect_id': 'p1'})

    def test_dispozitivul_citeste_planul(self):
        self.configureaza()
        self.assertEqual(self.echipa(DEVICE)['eu'], 'r1')

    def test_fara_token_401(self):
        self.assertEqual(self.client.get('/api/echipa').status_code, 401)
        self.assertEqual(self.client.get('/api/echipa/sursa').status_code, 401)

    def test_calendar_pastreaza_cheile_vechi_si_adauga_echipa(self):
        fara = self.calendar()
        self.configureaza()
        cu = self.calendar()
        self.assertEqual(set(cu) - {'echipa', 'outlook'}, CHEI_VECHI)
        self.assertIn('echipa', cu)
        self.assertEqual({k: v for k, v in cu.items() if k not in ('echipa', 'outlook')},
                         {k: v for k, v in fara.items() if k not in ('echipa', 'outlook')})
        self.assertEqual(set(cu['echipa']), {'generatedAt', 'stale', 'eu', 'resurse', 'activitati', 'avertizari'})

    def test_calendar_da_doar_activitatile_care_ating_fereastra(self):
        self.configureaza()
        ids = lambda j: sorted(a['id'] for a in j['echipa']['activitati'])
        # [2026-11-16, 2026-11-30): ating fereastra toate, in afara de nimic; 3001 (11-01..12-31) o traverseaza.
        self.assertEqual(ids(self.calendar()), ['1001', '1002', '1003', '2001', '2002', '3001', '4001', '4002'])
        # [2026-11-23, 2026-11-30): 1001..1003 (se termina 11-20) nu mai intra; 2002 se termina 11-22, inclusiv: nici el.
        j = self.client.get('/api/calendar?start=2026-11-23&zile=7', headers=self.bearer()).get_json()
        self.assertEqual(ids(j), ['3001', '4001', '4002'])
        # Capatul e inclusiv: o fereastra care incepe chiar in ziua 22 prinde activitatea care se termina pe 22.
        j = self.client.get('/api/calendar?start=2026-11-22&zile=7', headers=self.bearer()).get_json()
        self.assertEqual(ids(j), ['2001', '2002', '3001', '4001', '4002'])
        # Avertizarile nu se taie dupa fereastra.
        self.assertEqual(len(j['echipa']['avertizari']), len(self.avertizari()))

    def test_planul_nu_strica_calendarul_cand_ceva_se_rupe(self):
        self.configureaza()
        with mock.patch.object(echipa, '_incarca_dashboard', side_effect=RuntimeError('boom')):
            with self.assertLogs('pif_dashboard', 'ERROR'):
                j = self.calendar()
        self.assertIsNone(j['echipa'])
        self.assertTrue(CHEI_VECHI <= set(j))

    def test_snapshot_corupt_e_ignorat_fara_500(self):
        self.configureaza()
        self.gantt.raspuns = echipa.EroareGantt('Gantt-ul nu raspunde')
        with open(os.path.join(self.dir, 'plan.json'), 'wb') as fh:
            fh.write(b'{"activitati": [')
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.client.get('/api/echipa', headers=self.bearer())
        self.assertEqual((r.status_code, r.get_json()), (200, None))


# =============================================================================== cache

class Cache(CuEchipa):

    def test_nu_reciteste_in_15_minute_si_reciteste_dupa(self):
        self.configureaza()
        self.assertEqual(len(self.gantt.apeluri), 1)                       # citirea de proba din PUT
        self.ceas[0] = T0 + timedelta(minutes=14, seconds=59)
        self.assertFalse(self.echipa()['stale'])
        self.assertEqual(len(self.gantt.apeluri), 1)
        self.ceas[0] = T0 + timedelta(minutes=15, seconds=1)
        j = self.echipa()
        self.assertEqual(len(self.gantt.apeluri), 2)
        self.assertEqual((j['stale'], j['generatedAt']), (False, '2026-11-18T10:15:01Z'))
        self.assertEqual(self.gantt.apeluri[-1], (PLAN_ID, SECRET))
        self.echipa()
        self.assertEqual(len(self.gantt.apeluri), 2)                       # proaspat din nou
        self.assertEqual(os.listdir(self.dir).count('reimprospatare.lock'), 0)

    def test_gantt_cazut_pastreaza_snapshot_ul_vechi_cu_stale(self):
        self.configureaza()
        inainte = self.fisier('plan.json')
        self.ceas[0] = T0 + timedelta(minutes=20)
        self.gantt.raspuns = echipa.EroareGantt('Gantt-ul nu raspunde')
        with self.assertLogs('pif_dashboard', 'WARNING') as log:
            j = self.echipa()
        self.assertTrue(j['stale'])
        self.assertEqual(j['generatedAt'], '2026-11-18T10:00:00Z')
        self.assertEqual(len(j['activitati']), 8)
        self.assertEqual(self.fisier('plan.json'), inainte)
        self.assertIn('gantt_indisponibil', '\n'.join(log.output))
        self.assertTrue(self.calendar()['echipa']['stale'])

    def test_dupa_un_esec_nu_se_incearca_din_nou_in_fiecare_cerere(self):
        self.configureaza()
        self.ceas[0] = T0 + timedelta(minutes=20)
        self.gantt.raspuns = echipa.EroareGantt('Gantt-ul nu raspunde')
        with self.assertLogs('pif_dashboard', 'WARNING'):
            self.echipa()
        self.assertEqual(len(self.gantt.apeluri), 2)
        self.echipa()
        self.calendar()
        self.assertEqual(len(self.gantt.apeluri), 2, 'pauza dupa esec')
        lacat = os.path.join(self.dir, 'reimprospatare.lock')
        vechi = time.time() - echipa.PAUZA_DUPA_INCERCARE - 5
        os.utime(lacat, (vechi, vechi))
        self.gantt.raspuns = gantt(plan_echipa())
        j = self.echipa()
        self.assertEqual(len(self.gantt.apeluri), 3)
        self.assertFalse(j['stale'])

    def test_un_lacat_proaspat_al_celuilalt_worker_opreste_citirea_dubla(self):
        self.configureaza()
        self.ceas[0] = T0 + timedelta(minutes=30)
        with open(os.path.join(self.dir, 'reimprospatare.lock'), 'w'):
            pass
        j = self.echipa()
        self.assertEqual(len(self.gantt.apeluri), 1)
        self.assertTrue(j['stale'])

    def test_primul_acces_fara_snapshot_dar_cu_sursa_citeste_o_data(self):
        self.configureaza()
        os.remove(os.path.join(self.dir, 'plan.json'))
        j = self.echipa()
        self.assertEqual(len(self.gantt.apeluri), 2)
        self.assertEqual(len(j['activitati']), 8)

    def test_gantt_cazut_fara_snapshot_da_null(self):
        self.configureaza()
        os.remove(os.path.join(self.dir, 'plan.json'))
        self.gantt.raspuns = echipa.EroareGantt('Gantt-ul nu raspunde')
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.client.get('/api/echipa', headers=self.bearer())
        self.assertEqual((r.status_code, r.get_json()), (200, None))


# =============================================================================== sursa

class Sursa(CuEchipa):

    def test_put_valid_scrie_sursa_si_snapshot_si_raspunde_mascat(self):
        r = self.pune_sursa()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json(), {'ok': True, 'configurat': True, 'planId': '****eeee', 'eu': 'Eu Sintetic', 'activitati': 8})
        sursa = json.loads(self.fisier('sursa.json'))
        self.assertEqual(sursa, {'planId': PLAN_ID, 'secret': SECRET, 'email': EMAIL})
        self.assertEqual(json.loads(self.fisier('plan.json'))['eu'], 'r1')
        self.assertEqual(sorted(os.listdir(self.dir)), ['plan.json', 'sursa.json'], 'niciun .tmp ramas')

    def test_get_sursa(self):
        r = self.client.get('/api/echipa/sursa', headers=self.bearer())
        self.assertEqual((r.status_code, r.get_json()), (200, {'configurat': False, 'planId': None, 'eu': None}))
        self.configureaza()
        r = self.client.get('/api/echipa/sursa', headers=self.bearer())
        self.assertEqual(r.get_json(), {'configurat': True, 'planId': '****eeee', 'eu': 'Eu Sintetic'})

    def test_put_repetat_lasa_aceeasi_sursa(self):
        self.configureaza()
        prima = self.fisier('sursa.json')
        self.assertEqual(self.pune_sursa().status_code, 200)
        self.assertEqual(self.fisier('sursa.json'), prima)

    def test_uuid_cu_litere_mari_si_email_cu_spatii_se_normalizeaza(self):
        r = self.pune_sursa(planId=PLAN_ID.upper(), secret=SECRET.upper(), email='  EU@Exemplu.Test ')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.gantt.apeluri[-1], (PLAN_ID, SECRET))
        self.assertEqual(json.loads(self.fisier('sursa.json'))['email'], 'EU@Exemplu.Test')

    def test_corpuri_invalide_dau_400_si_nu_cheama_gantt(self):
        for corp, camp in (({'planId': 'nu-uuid'}, 'planId'), ({'planId': 5}, 'planId'), ({'planId': None}, 'planId'),
                           ({'secret': 'x'}, 'secret'), ({'secret': ''}, 'secret'),
                           ({'email': 'fara-arond'}, 'email'), ({'email': 'a@b'}, 'email'), ({'email': 'a b@c.test'}, 'email'),
                           ({'email': 7}, 'email'), ({'email': 'x' * 300 + '@exemplu.test'}, 'email')):
            r = self.pune_sursa(**corp)
            self.assertEqual(r.status_code, 400, corp)
            self.assertIn(camp, r.get_json()['error'])
        for brut in ('[]', '"x"', 'nu e json', ''):
            r = self.client.put('/api/echipa/sursa', data=brut, content_type='application/json', headers=self.bearer())
            self.assertEqual(r.status_code, 400, brut)
        self.assertEqual(self.gantt.apeluri, [])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'sursa.json')))

    def test_corp_prea_mare_413(self):
        r = self.client.put('/api/echipa/sursa', data=json.dumps({'planId': PLAN_ID, 'secret': SECRET, 'email': EMAIL,
                                                                  'x': 'a' * 5000}),
                            content_type='application/json', headers=self.bearer())
        self.assertEqual(r.status_code, 413)
        self.assertEqual(self.gantt.apeluri, [])

    def test_gantt_care_nu_raspunde_da_400_si_pastreaza_sursa_veche(self):
        self.configureaza()
        sursa, plan = self.fisier('sursa.json'), self.fisier('plan.json')
        self.gantt.raspuns = echipa.EroareGantt('Gantt-ul a raspuns cu codul 404')
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.pune_sursa(planId='99999999-bbbb-cccc-dddd-eeeeeeeeeeee', secret='99999999-2222-3333-4444-555555555555')
        self.assertEqual(r.status_code, 400)
        self.assertIn('codul 404', r.get_json()['error'])
        self.assertEqual((self.fisier('sursa.json'), self.fisier('plan.json')), (sursa, plan))

    def test_email_care_nu_e_printre_resurse_da_400_si_pastreaza_sursa_veche(self):
        self.configureaza()
        sursa, plan = self.fisier('sursa.json'), self.fisier('plan.json')
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.pune_sursa(email='altcineva@exemplu.test')
        self.assertEqual(r.status_code, 400)
        self.assertIn('email', r.get_json()['error'])
        self.assertEqual((self.fisier('sursa.json'), self.fisier('plan.json')), (sursa, plan))

    def test_raspuns_de_alta_forma_da_400(self):
        self.gantt.raspuns = {'plan': 'nu e json', 'resources': '[]'}
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.pune_sursa()
        self.assertEqual(r.status_code, 400)
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'sursa.json')))

    def test_dispozitivul_nu_scrie_sursa(self):
        r = self.pune_sursa(token=DEVICE)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(self.client.get('/api/echipa/sursa', headers=self.bearer(DEVICE)).status_code, 401)
        self.assertEqual(self.gantt.apeluri, [])
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'sursa.json')))

    def test_fara_token_nu_scrie_sursa(self):
        self.assertEqual(self.pune_sursa(token=None).status_code, 401)
        self.assertEqual(self.gantt.apeluri, [])

    def test_sesiunea_cu_pin_scrie_sursa(self):
        self.assertEqual(self.login().status_code, 200)
        self.client.get('/api/echipa/sursa')                 # cookie-ul csrf vine pe raspuns
        token = self.client.get_cookie('csrf_token').value
        r = self.client.put('/api/echipa/sursa', json={'planId': PLAN_ID, 'secret': SECRET, 'email': EMAIL},
                            headers={'X-CSRF-Token': token})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))


# =============================================================================== secretul nu iese

class SecretulNuIese(CuEchipa):

    @contextlib.contextmanager
    def capteaza_logul(self):
        """Tot ce scrie `pif_dashboard` (si pe nivel DEBUG), ca lista de linii; spre deosebire de
        `assertLogs`, nu pica cand nu s-a scris nimic."""
        linii = []

        class Colector(logging.Handler):
            def emit(self, record):
                linii.append(self.format(record))
        h, logger = Colector(), logging.getLogger('pif_dashboard')
        nivel = logger.level
        logger.addHandler(h)
        logger.setLevel(logging.DEBUG)
        try:
            yield linii
        finally:
            logger.removeHandler(h)
            logger.setLevel(nivel)

    def verifica_fara_secret(self, text, unde):
        self.assertNotIn(SECRET, text, unde)
        self.assertNotIn(PLAN_ID, text, unde)

    def test_raspunsuri(self):
        for r in (self.pune_sursa(),
                  self.client.get('/api/echipa/sursa', headers=self.bearer()),
                  self.client.get('/api/echipa', headers=self.bearer()),
                  self.client.get('/api/echipa', headers=self.bearer(DEVICE)),
                  self.client.get('/api/calendar?start=2026-11-16&zile=14', headers=self.bearer())):
            self.verifica_fara_secret(r.get_data(as_text=True), r.request.path)

    def test_erori_si_log_cand_gantt_pica_cu_urlerror_care_poarta_url_ul(self):
        """`urllib` pune uneori adresa in mesajul erorii: nimic din el nu trebuie sa ajunga in raspuns sau in log."""
        def cade(cerere, timeout=None):
            self.assertEqual(timeout, 5)
            raise urllib.error.URLError('nu merge: ' + cerere.full_url)
        self.patch(echipa, '_descarca', _REALA)
        with mock.patch('urllib.request.urlopen', side_effect=cade):
            with self.assertLogs('pif_dashboard', 'DEBUG') as log:
                r = self.pune_sursa()
        self.assertEqual(r.status_code, 400)
        self.verifica_fara_secret(r.get_data(as_text=True), 'raspuns')
        self.verifica_fara_secret('\n'.join(log.output), 'log')
        self.assertIn('Gantt-ul nu raspunde', r.get_json()['error'])

    def test_erori_si_log_la_reimprospatare_cu_http_error(self):
        self.configureaza()
        self.ceas[0] = T0 + timedelta(minutes=30)

        def cade(cerere, timeout=None):
            raise urllib.error.HTTPError(cerere.full_url, 503, 'Service Unavailable ' + cerere.full_url, {}, None)
        self.patch(echipa, '_descarca', _REALA)
        with mock.patch('urllib.request.urlopen', side_effect=cade):
            with self.assertLogs('pif_dashboard', 'DEBUG') as log:
                r = self.client.get('/api/echipa', headers=self.bearer())
        self.assertTrue(r.get_json()['stale'])
        self.verifica_fara_secret(r.get_data(as_text=True), 'raspuns')
        text = '\n'.join(log.output)
        self.verifica_fara_secret(text, 'log')
        self.assertIn('codul 503', text)

    def test_citirea_reala_cere_url_ul_cu_parametrii_si_nu_il_logheaza(self):
        class Raspuns:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return json.dumps(gantt(plan_echipa())).encode('utf-8')

        vazute = []

        def raspunde(cerere, timeout=None):
            vazute.append((cerere.full_url, timeout))
            return Raspuns()
        self.patch(echipa, '_descarca', _REALA)
        with mock.patch('urllib.request.urlopen', side_effect=raspunde):
            with self.capteaza_logul() as log:
                r = self.pune_sursa()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        url, timeout = vazute[0]
        self.assertTrue(url.startswith(echipa.URL_GANTT + '?'))
        self.assertIn('planId=' + PLAN_ID, url)
        self.assertIn('secret=' + SECRET, url)
        self.assertEqual(timeout, 5)
        self.verifica_fara_secret('\n'.join(log), 'log')
        self.verifica_fara_secret(r.get_data(as_text=True), 'raspuns')

    def test_raspuns_care_nu_e_json_si_raspuns_peste_plafon(self):
        class Raspuns:
            status = 200

            def __init__(self, brut):
                self.brut = brut

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self, n=-1):
                return self.brut[:n] if n >= 0 else self.brut
        self.patch(echipa, '_descarca', _REALA)
        for brut, mesaj in ((b'<html>nu e json</html>', 'nu e JSON'), (b'[1, 2]', 'alta forma'),
                            (b'x' * (echipa.MAX_RASPUNS_GANTT + 10), 'prea mare')):
            with mock.patch('urllib.request.urlopen', return_value=Raspuns(brut)):
                with self.assertLogs('pif_dashboard', 'WARNING'):
                    r = self.pune_sursa()
            self.assertEqual(r.status_code, 400)
            self.assertIn(mesaj, r.get_json()['error'])


if __name__ == '__main__':
    import unittest
    unittest.main()

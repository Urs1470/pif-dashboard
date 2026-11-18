"""Dashboard <-> Gantt, o data pe zi: jobul `POST /api/echipa/sincronizeaza`, `POST /api/echipa/trimite`
si coloanele v47 ale `implementari` (`blueprints/echipa.py`).

Ce se pazeste, tacut daca se strica:
  - citirea si scrierea in Gantt se fac DOAR din job (sau din „trimite", cererea explicita a lui Ion):
    salvarea unei perioade (POST / PUT / DELETE) nu mai suna Gantt-ul si nu mai are cheia `srp`;
  - sincronizarea in trei cai fata de BAZA (intervalul convenit la ultima rulare): doar Torqa mutat -> se
    scrie in SRP; doar SRP mutat -> `schimbat_in_srp`, dashboard-ul nu se atinge; amandoua -> `conflict`;
  - se scriu doar patru campuri (start_date, end_date, duration, constraint_date) ale unei etape in care
    Ion e resursa; restul obiectului brut ramane identic; fara Ion: `protejat`, zero POST;
  - un Gantt cazut inregistreaza rularea ca eroare (502), nu schimba nimic altceva si face `stale`;
  - a doua rulare imediata nu mai are ce trimite (idempotent);
  - secretul nu iese in raspuns, in log sau in erori;
  - coloanele `srp_activitate_id`, `srp_sincron_start`, `srp_sincron_end` fac dus-intors prin backup si restore.
Toate datele sunt sintetice; reteaua (`_descarca`, `_trimite_activitate`) e inlocuita de un Gantt viu in memorie.
"""

import copy
import io
import json
import os
import sqlite3
import time
import urllib.error
from unittest import mock

from _aplicatia import DEVICE, FULL
from blueprints import echipa
from test_echipa import PLAN_ID, SECRET, T0, CuEchipa, act, gantt, zi

_REALA_TRIMITE = echipa._trimite_activitate     # cea adevarata; setUp o inlocuieste cu Gantt-ul viu
CAMPURI_SCRISE = {'start_date', 'end_date', 'duration', 'constraint_date'}
BAZA = ('2026-11-18', '2026-11-19')             # intervalul etapei 1002 / al perioadei p1-i0 la inceput


class GanttViu:
    """Un Gantt in memorie: GET intoarce planul curent, POST inlocuieste (sau adauga) activitatea cu
    acelasi id, ca serverul real. Numara apelurile."""

    def __init__(self, activitati):
        self.activitati = copy.deepcopy(activitati)
        self.get_uri = 0
        self.posturi = []
        self.cade_get = False
        self.cade_post = False
        self.cade_dupa = None                  # int: dupa atatea POST-uri reusite, urmatoarele cad
        self.aplica = True                     # False: POST-ul „reuseste", dar planul nu se schimba

    def __call__(self, plan_id, secret):
        self.get_uri += 1
        if self.cade_get:
            raise echipa.EroareGantt('Gantt-ul nu raspunde')
        return gantt(copy.deepcopy(self.activitati))

    def trimite(self, plan_id, secret, activitate):
        if self.cade_post or (self.cade_dupa is not None and len(self.posturi) >= self.cade_dupa):
            raise echipa.EroareGantt('Gantt-ul nu raspunde la scriere')
        self.posturi.append(copy.deepcopy(activitate))
        if not self.aplica:
            return
        for ix, a in enumerate(self.activitati):
            if str(a['id']) == str(activitate['id']):
                self.activitati[ix] = copy.deepcopy(activitate)
                return
        self.activitati.append(copy.deepcopy(activitate))

    def activitate(self, id_):
        return next(a for a in self.activitati if str(a['id']) == str(id_))

    def muta(self, id_, start, end):
        a = self.activitate(id_)
        a['start_date'], a['end_date'] = zi(start), zi(end, True)


def plan_sync():
    """Proiectul 26_287: radacina pe care e si Ion, o etapa a lui Ion si una a unui coleg."""
    return [
        act(1001, 'C26_287_Proiect Sintetic Unu', 0, zi('11-16'), zi('11-30', True), resource=['r1'],
            constraint_type='asap', constraint_date='2026-11-16 00:00'),
        act(1002, 'E1_PIF', '1001', zi('11-18'), zi('11-19', True), resource=['r1'], duration=2,
            constraint_type='asap', constraint_date='2026-11-18 00:00', state='progress', progress=0.5,
            row_height=40, split_placement='x'),
        act(1003, 'E2_PIF', 1001, zi('11-16'), zi('11-17', True), resource=['r2'], duration=2,
            constraint_type='asap', constraint_date='2026-11-16 00:00'),
    ]


def doua_etape_ale_lui_ion():
    return plan_sync() + [act(1004, 'E3_PIF', '1001', zi('11-23'), zi('11-24', True), resource=['r1'], duration=2,
                              constraint_type='asap', constraint_date='2026-11-23 00:00')]


class CuGanttViu(CuEchipa):

    def setUp(self):
        super().setUp()
        self.viu = GanttViu(plan_sync())
        self.patch(echipa, '_descarca', self.viu)
        self.patch(echipa, '_trimite_activitate', self.viu.trimite)
        self.dashboard(('p1', '26_287', 'pregatire', [BAZA]))
        self.configureaza()
        self.viu.get_uri = 0                   # numaram doar ce face sincronizarea

    # ----------------------------------------------------------------------- ajutoare

    def api(self, metoda, cale, corp=None, token=FULL):
        return getattr(self.client, metoda)(cale, json=corp, headers=self.bearer(token) if token else {})

    def ruleaza(self, token=FULL):
        return self.api('post', '/api/echipa/sincronizeaza', {}, token=token)

    def sql(self, interogare, *param):
        con = sqlite3.connect(self.db)
        try:
            rez = con.execute(interogare, param).fetchall()
            con.commit()
            return rez
        finally:
            con.close()

    def leaga(self, impl_id='p1-i0', aid='1002', baza=BAZA):
        self.sql('UPDATE implementari SET srp_activitate_id = ?, srp_sincron_start = ?, srp_sincron_end = ? '
                 'WHERE id = ?', aid, baza[0] if baza else None, baza[1] if baza else None, impl_id)

    def perioada_legata(self, impl_id, start, end, aid, baza):
        self.sql('INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit, srp_activitate_id, '
                 'srp_sincron_start, srp_sincron_end) VALUES (?, ?, ?, ?, ?, ?, ?)',
                 impl_id, 'p1', start, end, aid, baza[0], baza[1])

    def legatura(self, impl_id='p1-i0'):
        return self.sql('SELECT srp_activitate_id, srp_sincron_start, srp_sincron_end FROM implementari WHERE id = ?',
                        impl_id)[0]

    def muta_in_torqa(self, impl_id, start, end):
        self.sql('UPDATE implementari SET data_start = ?, data_sfarsit = ? WHERE id = ?',
                 '2026-' + start, '2026-' + end, impl_id)

    def date_perioada(self, impl_id='p1-i0'):
        return self.sql('SELECT data_start, data_sfarsit FROM implementari WHERE id = ?', impl_id)[0]

    def assertFaraPost(self):
        self.assertEqual(self.viu.posturi, [])

    def avertizari_tip(self, tip):
        return [a for a in self.avertizari() if a['tip'] == tip]


# =============================================================================== jobul zilei

class Job(CuGanttViu):

    def test_prima_rulare_leaga_perioada_egala_cu_etapa_fara_nicio_scriere(self):
        r = self.ruleaza()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json(), {'ultima_rulare': '2026-11-18T10:00:00Z', 'rezultat': 'ok', 'trimise': 0,
                                        'create': 0, 'avertizari': 0, 'eroare': None})
        self.assertEqual(self.legatura(), ('1002', '2026-11-18', '2026-11-19'))
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (1, []))
        self.assertEqual(json.loads(self.fisier('sincronizare.json')), r.get_json())

    def test_a_doua_rulare_imediata_nu_mai_are_ce_trimite(self):
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        self.leaga()
        self.assertEqual(self.ruleaza().get_json()['trimise'], 1)
        self.viu.posturi.clear()
        r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['rezultat'], r.get_json()['trimise']), (200, 'ok', 0))
        self.assertFaraPost()

    def test_schimbat_in_torqa_se_scrie_in_srp_cu_exact_patru_campuri(self):
        self.leaga()
        original = copy.deepcopy(self.viu.activitate(1002))
        r = self.api('put', '/api/implementari/p1-i0', {'data_start': '2026-11-20', 'data_sfarsit': '2026-11-22'})
        self.assertEqual(r.get_json(), {'message': 'ok'})                       # salvarea nu suna Gantt-ul, nu are `srp`
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))
        j = self.echipa()                                                         # citirea nu face retea
        self.assertEqual(j['de_trimis'], [{'proiect_id': 'p1', 'implementare_id': 'p1-i0', 'start': '2026-11-20',
                                           'end': '2026-11-22', 'tip': 'modificata'}])
        self.assertEqual(j['avertizari'], [])
        self.assertEqual(self.viu.get_uri, 0)

        r = self.ruleaza()
        self.assertEqual(r.get_json()['trimise'], 1)
        self.assertEqual(len(self.viu.posturi), 1)
        trimis = self.viu.posturi[0]
        self.assertEqual({k for k in trimis if trimis[k] != original.get(k)}, CAMPURI_SCRISE)
        self.assertEqual(trimis, {**original, 'start_date': '2026-11-20 00:00', 'end_date': '2026-11-22 23:59',
                                  'duration': 3, 'constraint_date': '2026-11-20 00:00'})
        self.assertEqual((trimis['state'], trimis['progress'], trimis['row_height'], trimis['resource']),
                         ('progress', 0.5, 40, ['r1']))
        self.assertEqual(self.legatura(), ('1002', '2026-11-20', '2026-11-22'))             # baza = Torqa
        j = self.echipa()
        self.assertEqual((j['de_trimis'], j['avertizari']), ([], []))
        self.assertEqual({a['id']: (a['start'], a['end']) for a in j['activitati']}['1002'], ('2026-11-20', '2026-11-22'))

    def test_constraint_date_se_muta_doar_daca_era_egal_cu_vechiul_start(self):
        self.leaga()
        self.viu.activitate(1002)['constraint_date'] = '2026-11-01 00:00'
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        self.ruleaza()
        self.assertEqual(self.viu.posturi[0]['constraint_date'], '2026-11-01 00:00')

    def test_durata_e_in_zile_calendaristice_inclusiv(self):
        self.assertEqual(echipa._zile_inclusiv(('2026-04-24', '2026-06-08')), 46)
        self.assertEqual(echipa._zile_inclusiv(('2026-11-20', '2026-11-20')), 1)

    def test_perioada_fara_sfarsit_e_o_zi(self):
        self.leaga()
        self.sql("UPDATE implementari SET data_start = '2026-11-24', data_sfarsit = '' WHERE id = 'p1-i0'")
        self.ruleaza()
        self.assertEqual((self.viu.posturi[0]['start_date'], self.viu.posturi[0]['end_date'], self.viu.posturi[0]['duration']),
                         ('2026-11-24 00:00', '2026-11-24 23:59', 1))

    def test_schimbat_in_srp_nu_atinge_dashboard_ul(self):
        self.leaga()
        self.viu.muta(1002, '11-25', '11-26')
        r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['rezultat'], r.get_json()['avertizari']), (200, 'ok', 1))
        self.assertFaraPost()
        self.assertEqual(self.date_perioada(), BAZA)                                          # dashboard-ul ramane
        self.assertEqual(self.legatura(), ('1002',) + BAZA)                                    # baza ramane
        self.assertEqual(self.echipa()['avertizari'], [{
            'tip': 'schimbat_in_srp', 'proiect_id': 'p1', 'cod': '26_287', 'proiect_nume': 'Proiect p1',
            'srp': {'activitate_id': '1002', 'text': 'E1_PIF', 'start': '2026-11-25', 'end': '2026-11-26'},
            'dashboard': {'implementare_id': 'p1-i0', 'start': '2026-11-18', 'end': '2026-11-19'},
            'baza': {'start': '2026-11-18', 'end': '2026-11-19'}}])
        self.assertEqual(self.echipa()['de_trimis'], [])

    def test_conflict_cand_s_au_mutat_amandoua_nu_se_scrie_nimic(self):
        self.leaga()
        self.viu.muta(1002, '11-25', '11-26')
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        r = self.ruleaza()
        self.assertEqual(r.get_json()['avertizari'], 1)
        self.assertFaraPost()
        c = self.avertizari_tip('conflict')
        self.assertEqual(len(c), 1)
        self.assertEqual((c[0]['srp']['start'], c[0]['dashboard']['start'], c[0]['baza']),
                         ('2026-11-25', '2026-11-20', {'start': '2026-11-18', 'end': '2026-11-19'}))
        self.assertEqual(self.date_perioada(), ('2026-11-20', '2026-11-22'))
        self.assertEqual(self.legatura(), ('1002',) + BAZA)

    def test_amandoua_mutate_dar_la_aceleasi_date_e_sincron_si_baza_se_aduce_la_zi(self):
        self.leaga()
        self.viu.muta(1002, '11-25', '11-26')
        self.muta_in_torqa('p1-i0', '11-25', '11-26')
        r = self.ruleaza()
        self.assertEqual(r.get_json()['avertizari'], 0)
        self.assertFaraPost()
        self.assertEqual(self.legatura(), ('1002', '2026-11-25', '2026-11-26'))

    def test_fara_baza_si_date_diferite_e_perioada_diferita_fara_nicio_scriere(self):
        self.muta_in_torqa('p1-i0', '11-30', '12-01')
        r = self.ruleaza()
        self.assertEqual(r.get_json()['avertizari'], 1)
        self.assertFaraPost()
        self.assertEqual(self.legatura(), (None, None, None))
        a = self.avertizari_tip('perioada_diferita')
        self.assertEqual((a[0]['srp']['activitate_id'], a[0]['dashboard']['start']), ('1002', '2026-11-30'))
        self.assertEqual(self.echipa()['de_trimis'], [])

    def test_perioada_legata_fara_baza_si_date_diferite_e_perioada_diferita(self):
        self.leaga(baza=None)
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        self.ruleaza()
        self.assertFaraPost()
        self.assertEqual(len(self.avertizari_tip('perioada_diferita')), 1)

    def test_etapa_disparuta_din_plan_e_avertizare_si_legatura_ramane(self):
        self.leaga(aid='999999')
        r = self.ruleaza()
        # + etapa 1002 a lui Ion, acum fara nicio perioada: `perioada_diferita` cu dashboard null
        self.assertEqual(r.get_json()['avertizari'], 2)
        a = self.avertizari_tip('schimbat_in_srp')[0]
        self.assertEqual((a['motiv'], a['srp']), ('etapa_disparuta', None))
        self.assertEqual(self.legatura()[0], '999999')
        self.assertFaraPost()

    def test_perioada_noua_fara_pereche_creeaza_etapa_sub_radacina(self):
        r = self.api('post', '/api/proiecte/p1/implementari',
                     {'id': 'i-nou', 'data_start': '2026-11-24', 'data_sfarsit': '2026-11-25', 'eticheta': 'Montaj'})
        self.assertEqual((r.status_code, r.get_json()), (201, {'id': 'i-nou'}))      # fara `srp`
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))
        self.leaga()
        self.assertEqual(self.echipa()['de_trimis'], [{'proiect_id': 'p1', 'implementare_id': 'i-nou', 'start': '2026-11-24',
                                                       'end': '2026-11-25', 'tip': 'noua'}])
        r = self.ruleaza()
        self.assertEqual((r.get_json()['create'], r.get_json()['trimise'], r.get_json()['rezultat']), (1, 0, 'ok'))
        self.assertEqual(len(self.viu.posturi), 1)                  # in radacina (16-30.11): fara lungire
        nou = self.viu.posturi[0]
        self.assertIsInstance(nou['id'], int)
        self.assertNotIn(nou['id'], {1001, 1002, 1003})
        self.assertEqual((nou['parent'], nou['text'], nou['resource'], nou['type'], nou['progress'], nou['open']),
                         ('1001', 'Montaj', ['r1'], 'task', 0, True))
        self.assertEqual((nou['constraint_type'], nou['constraint_date'], nou['start_date'], nou['end_date'], nou['duration']),
                         ('asap', '2026-11-24 00:00', '2026-11-24 00:00', '2026-11-25 23:59', 2))
        self.assertNotIn('state', nou)
        self.assertEqual((nou['row_height'], nou['color']), (40, '#123456'))
        self.assertEqual(self.legatura('i-nou'), (str(nou['id']), '2026-11-24', '2026-11-25'))
        self.assertEqual(self.echipa()['de_trimis'], [])

    def test_eticheta_goala_da_textul_pif(self):
        self.leaga()
        self.api('post', '/api/proiecte/p1/implementari', {'data_start': '2026-11-24', 'data_sfarsit': '2026-11-25'})
        self.ruleaza()
        self.assertEqual(self.viu.posturi[0]['text'], 'PIF')

    def test_perioada_noua_in_afara_radacinii_o_lungeste_intai(self):
        self.leaga()
        self.api('post', '/api/proiecte/p1/implementari', {'data_start': '2026-12-07', 'data_sfarsit': '2026-12-09'})
        radacina = copy.deepcopy(self.viu.activitate(1001))
        self.ruleaza()
        self.assertEqual([p['id'] == 1001 for p in self.viu.posturi], [True, False])
        self.assertEqual(self.viu.posturi[0], {**radacina, 'end_date': '2026-12-09 23:59', 'duration': 24})

    def test_doua_scrieri_sub_aceeasi_radacina_o_lungesc_o_singura_data_la_uniune(self):
        self.viu.activitati = doua_etape_ale_lui_ion()
        self.leaga()
        self.perioada_legata('p1-i1', '2026-11-23', '2026-11-24', '1004', ('2026-11-23', '2026-11-24'))
        self.muta_in_torqa('p1-i0', '11-28', '12-03')
        self.muta_in_torqa('p1-i1', '12-05', '12-08')
        r = self.ruleaza()
        self.assertEqual((r.get_json()['trimise'], r.get_json()['rezultat']), (2, 'ok'))
        self.assertEqual([p['id'] for p in self.viu.posturi], [1001, 1002, 1004])
        self.assertEqual(self.viu.posturi[0]['end_date'], '2026-12-08 23:59')

    def test_radacina_nu_se_scurteaza_si_nu_se_atinge_cand_etapa_ramane_in_ea(self):
        self.leaga()
        self.muta_in_torqa('p1-i0', '11-17', '11-29')
        self.ruleaza()
        self.assertEqual([p['id'] for p in self.viu.posturi], [1002])

    def test_perioada_noua_fara_ion_pe_radacina_e_protejata(self):
        self.viu.activitate(1001)['resource'] = ['r2']
        self.leaga()
        self.api('post', '/api/proiecte/p1/implementari', {'id': 'i-nou', 'data_start': '2026-11-24', 'data_sfarsit': '2026-11-25'})
        r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['create'], r.get_json()['avertizari']), (200, 0, 1))
        self.assertFaraPost()
        a = self.avertizari_tip('protejat')
        self.assertEqual((a[0]['motiv'], a[0]['srp'], a[0]['dashboard']['implementare_id']),
                         ('ion_nu_e_pe_radacina', None, 'i-nou'))
        self.assertEqual(self.echipa()['de_trimis'], [])

    def test_radacina_fara_ion_nu_se_lungeste_dar_etapa_se_scrie(self):
        self.viu.activitate(1001)['resource'] = ['r2']
        self.leaga()
        self.muta_in_torqa('p1-i0', '11-28', '12-04')
        self.ruleaza()
        self.assertEqual([p['id'] for p in self.viu.posturi], [1002])

    def test_perioada_stearsa_in_torqa_nu_atinge_srp(self):
        self.leaga()
        r = self.api('delete', '/api/implementari/p1-i0')
        self.assertEqual(r.status_code, 200)
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))
        r = self.ruleaza()
        self.assertEqual((r.get_json()['rezultat'], r.get_json()['trimise']), ('ok', 0))
        self.assertFaraPost()
        self.assertEqual(self.viu.activitate(1002)['start_date'], '2026-11-18 00:00')       # etapa ramane

    def test_etapa_fara_ion_e_protejata_zero_post(self):
        self.leaga(aid='1003', baza=('2026-11-16', '2026-11-17'))                       # legatura spre etapa unui coleg
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        r = self.ruleaza()
        self.assertEqual((r.get_json()['rezultat'], r.get_json()['avertizari']), ('ok', 2))   # + 1002, fara perioada
        self.assertFaraPost()
        a = self.avertizari_tip('protejat')
        self.assertEqual((a[0]['motiv'], a[0]['srp']['activitate_id']), ('ion_nu_e_pe_etapa', '1003'))
        self.assertEqual(self.echipa()['de_trimis'], [])

    def test_ion_scos_de_pe_etapa_intre_timp_e_protejat(self):
        self.leaga()
        self.viu.activitate(1002)['resource'] = ['r2']
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        self.ruleaza()
        self.assertFaraPost()
        self.assertEqual(len(self.avertizari_tip('protejat')), 1)

    def test_proiect_finalizat_nu_se_sincronizeaza(self):
        self.leaga()
        self.sql("UPDATE proiecte SET status = 'finalizat' WHERE id = 'p1'")
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        self.ruleaza()
        self.assertFaraPost()

    def test_proiect_fara_cod_sau_fara_radacina_nu_se_atinge(self):
        self.dashboard(('p9', 'TBD', 'pregatire', [('2026-11-18', '2026-11-19')]),
                       ('p8', '26_999', 'pregatire', [('2026-11-18', '2026-11-19')]))
        self.ruleaza()
        self.assertFaraPost()
        self.assertEqual(self.legatura('p9-i0'), (None, None, None))
        self.assertEqual(self.legatura('p8-i0'), (None, None, None))

    def test_perioadele_trecute_nelegate_nu_se_leaga_si_nu_creeaza_etape(self):
        self.sql("INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit) VALUES ('vechi', 'p1', '2026-10-01', '2026-10-02')")
        self.leaga()
        self.ruleaza()
        self.assertFaraPost()
        self.assertEqual(self.legatura('vechi'), (None, None, None))

    def test_id_nou_nu_se_ciocneste_cu_unul_existent(self):
        ms = int(T0.timestamp() * 1000)
        self.viu.activitati.append(act(ms, 'Alta', '1001', zi('11-16'), zi('11-16', True), resource=['r2']))
        self.leaga()
        self.api('post', '/api/proiecte/p1/implementari', {'data_start': '2026-11-24', 'data_sfarsit': '2026-11-25'})
        self.ruleaza()
        self.assertEqual(self.viu.posturi[0]['id'], ms + 1)

    def test_doua_perioade_noi_primesc_id_uri_diferite(self):
        self.leaga()
        self.api('post', '/api/proiecte/p1/implementari', {'data_start': '2026-11-24', 'data_sfarsit': '2026-11-25'})
        self.api('post', '/api/proiecte/p1/implementari', {'data_start': '2026-11-26', 'data_sfarsit': '2026-11-27'})
        r = self.ruleaza()
        self.assertEqual(r.get_json()['create'], 2)
        ids = [p['id'] for p in self.viu.posturi]
        self.assertEqual(len(set(ids)), 2)

    def test_radacina_fara_nicio_etapa_da_un_sablon_minimal(self):
        self.viu.activitati = [act(1001, 'C26_287_Proiect', 0, zi('11-01'), zi('11-10', True), resource=['r1'])]
        self.api('post', '/api/proiecte/p1/implementari', {'data_start': '2026-11-24', 'data_sfarsit': '2026-11-25'})
        self.sql("UPDATE implementari SET data_start = '2026-11-26', data_sfarsit = '2026-11-27' WHERE id = 'p1-i0'")
        r = self.ruleaza()
        self.assertEqual((r.get_json()['create'], r.get_json()['rezultat']), (2, 'ok'))
        self.assertEqual([p['id'] == 1001 for p in self.viu.posturi], [True, False, False])    # radacina o data, la uniune
        self.assertEqual(self.viu.posturi[0]['end_date'], '2026-11-27 23:59')
        for nou in self.viu.posturi[1:]:
            self.assertEqual((nou['parent'], nou['resource'], nou['type'], nou['constraint_type']), ('1001', ['r1'], 'task', 'asap'))


# =============================================================================== erori ale jobului

class ErorileJobului(CuGanttViu):

    def setUp(self):
        super().setUp()
        self.leaga()
        self.muta_in_torqa('p1-i0', '11-20', '11-22')

    def test_gantt_cazut_la_citire_inregistreaza_eroarea_si_nu_schimba_nimic(self):
        plan = self.fisier('plan.json')
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.ruleaza()
        self.assertEqual(r.status_code, 502)
        self.assertEqual((r.get_json()['rezultat'], r.get_json()['eroare']), ('eroare', 'gantt_indisponibil'))
        self.assertEqual(json.loads(self.fisier('sincronizare.json'))['rezultat'], 'eroare')
        self.assertEqual(self.fisier('plan.json'), plan)
        self.assertEqual(self.date_perioada(), ('2026-11-20', '2026-11-22'))
        self.assertEqual(self.legatura(), ('1002',) + BAZA)
        self.assertEqual(self.viu.posturi, [])
        j = self.echipa()
        self.assertTrue(j['stale'])
        self.assertEqual(j['sincronizare']['rezultat'], 'eroare')

    def test_o_rulare_buna_dupa_una_esuata_scoate_stale(self):
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            self.ruleaza()
        self.viu.cade_get = False
        self.assertEqual(self.ruleaza().status_code, 200)
        self.assertFalse(self.echipa()['stale'])

    def test_scrierea_respinsa_de_gantt_e_502_si_baza_nu_se_misca(self):
        self.viu.cade_post = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['rezultat'], r.get_json()['trimise']), (502, 'eroare', 0))
        self.assertEqual(self.legatura(), ('1002',) + BAZA)
        self.assertEqual(self.date_perioada(), ('2026-11-20', '2026-11-22'))
        self.assertEqual(len(self.echipa()['de_trimis']), 1)                 # la urmatoarea rulare se reincearca

    def test_rezultat_partial_cand_doar_o_parte_din_scrieri_reuseste(self):
        self.viu.activitati = doua_etape_ale_lui_ion()
        self.perioada_legata('p1-i1', '2026-11-24', '2026-11-25', '1004', ('2026-11-23', '2026-11-24'))
        self.viu.cade_dupa = 1
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['rezultat'], r.get_json()['trimise']), (200, 'partial', 1))
        self.assertEqual(self.legatura(), ('1002', '2026-11-20', '2026-11-22'))
        self.assertEqual(self.legatura('p1-i1'), ('1004', '2026-11-23', '2026-11-24'))     # nescrisa: baza veche
        self.viu.cade_dupa = None
        r = self.ruleaza()                                                     # reincercarea o duce la capat
        self.assertEqual((r.get_json()['rezultat'], r.get_json()['trimise']), ('ok', 1))

    def test_verificarea_care_nu_vede_datele_noi_nu_muta_baza(self):
        self.viu.aplica = False
        r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['rezultat'], r.get_json()['trimise']), (502, 'eroare', 0))
        self.assertEqual(self.legatura(), ('1002',) + BAZA)
        self.assertEqual(len(self.viu.posturi), 1)                  # fara retry in aceeasi rulare

    def test_o_eroare_neasteptata_da_500_si_se_inregistreaza(self):
        with mock.patch.object(echipa, '_incarca_dashboard', side_effect=RuntimeError('boom')):
            with self.assertLogs('pif_dashboard', 'WARNING') as log:
                r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['eroare']), (500, 'eroare_interna'))
        self.assertIn('RuntimeError', '\n'.join(log.output))
        self.assertNotIn('scriere.lock', os.listdir(self.dir))

    def test_un_lacat_proaspat_de_scriere_opreste_rularea(self):
        with open(os.path.join(self.dir, 'scriere.lock'), 'w'):
            pass
        r = self.ruleaza()
        self.assertEqual((r.status_code, self.viu.get_uri), (409, 0))
        self.assertNotIn('sincronizare.json', os.listdir(self.dir))

    def test_un_lacat_vechi_nu_blocheaza_si_lacatul_se_elibereaza(self):
        lacat = os.path.join(self.dir, 'scriere.lock')
        with open(lacat, 'w'):
            pass
        vechi = time.time() - echipa.EXPIRARE_LACAT_SCRIERE - 5
        os.utime(lacat, (vechi, vechi))
        self.assertEqual(self.ruleaza().status_code, 200)
        self.assertNotIn('scriere.lock', os.listdir(self.dir))

    def test_fara_sursa_configurata_409_fara_retea(self):
        os.remove(os.path.join(self.dir, 'sursa.json'))
        r = self.ruleaza()
        self.assertEqual((r.status_code, self.viu.get_uri, self.viu.posturi), (409, 0, []))

    def test_dispozitivul_si_cererea_fara_token_primesc_401_fara_retea(self):
        for token in (DEVICE, None):
            r = self.ruleaza(token=token)
            self.assertEqual(r.status_code, 401)
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))

    def test_sesiunea_cu_pin_poate_porni_jobul(self):
        self.assertEqual(self.login().status_code, 200)
        self.client.get('/api/echipa')                                   # cookie-ul csrf vine pe raspuns
        token = self.client.get_cookie('csrf_token').value
        r = self.client.post('/api/echipa/sincronizeaza', json={}, headers={'X-CSRF-Token': token})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))


# =============================================================================== salvarea perioadelor nu mai suna Gantt-ul

class SalvareaFaraRetea(CuGanttViu):

    def test_post_put_delete_nu_fac_retea_si_nu_au_cheia_srp(self):
        r = self.api('post', '/api/proiecte/p1/implementari', {'id': 'i2', 'data_start': '2026-11-24'})
        self.assertEqual((r.status_code, r.get_json()), (201, {'id': 'i2'}))
        r = self.api('put', '/api/implementari/i2', {'data_start': '2026-11-25', 'data_sfarsit': '2026-11-26'})
        self.assertEqual((r.status_code, r.get_json()), (200, {'message': 'ok'}))
        r = self.api('delete', '/api/implementari/i2')
        self.assertEqual((r.status_code, r.get_json()), (200, {'message': 'ok'}))
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))
        self.assertEqual(self.api('put', '/api/implementari/nu-exista', {'data_start': '2026-11-25'}).status_code, 404)

    def test_gantt_cazut_nu_strica_salvarea(self):
        self.viu.cade_get = True
        r = self.api('put', '/api/implementari/p1-i0', {'data_start': '2026-11-20', 'data_sfarsit': '2026-11-22'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.date_perioada(), ('2026-11-20', '2026-11-22'))


# =============================================================================== /api/echipa/trimite

class Trimite(CuGanttViu):

    def trimite(self, token=FULL, **corp):
        return self.api('post', '/api/echipa/trimite', corp, token=token)

    def test_trimite_ignora_conflictul_si_aduce_baza_si_snapshot_la_zi(self):
        self.leaga()
        self.viu.muta(1002, '11-25', '11-26')                               # altcineva a mutat etapa
        self.muta_in_torqa('p1-i0', '11-20', '11-22')                       # si Ion a mutat perioada: conflict la job
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual((r.status_code, r.get_json()),
                         (200, {'srp': {'status': 'ok', 'motiv': 'sincronizat', 'activitate_id': '1002'}}))
        self.assertEqual(len(self.viu.posturi), 1)
        self.assertEqual((self.viu.posturi[0]['start_date'], self.viu.posturi[0]['end_date']),
                         ('2026-11-20 00:00', '2026-11-22 23:59'))
        self.assertEqual(self.viu.posturi[0]['constraint_date'], '2026-11-18 00:00')        # nu era egal cu startul din Gantt
        self.assertEqual(self.legatura(), ('1002', '2026-11-20', '2026-11-22'))             # baza = Torqa
        stare = {a['id']: (a['start'], a['end']) for a in self.echipa()['activitati']}
        self.assertEqual(stare['1002'], ('2026-11-20', '2026-11-22'))                        # snapshot reimprospatat
        self.assertEqual(self.echipa()['avertizari'], [])

    def test_trimite_pastreaza_protectia(self):
        self.leaga(aid='1003', baza=('2026-11-16', '2026-11-17'))
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.get_json()['srp'], {'status': 'protejat', 'motiv': 'ion_nu_e_pe_etapa', 'activitate_id': '1003'})
        self.assertFaraPost()
        self.assertEqual(self.legatura(), ('1003', '2026-11-16', '2026-11-17'))

    def test_trimite_cu_etapa_aleasa_a_unui_coleg_e_protejat(self):
        r = self.trimite(implementare_id='p1-i0', activitate_id='1003')
        self.assertEqual(r.get_json()['srp']['status'], 'protejat')
        self.assertFaraPost()

    def test_trimite_cu_etapa_inexistenta_e_protejat(self):
        r = self.trimite(implementare_id='p1-i0', activitate_id='999999')
        self.assertEqual(r.get_json()['srp'], {'status': 'protejat', 'motiv': 'etapa_necunoscuta', 'activitate_id': None})
        self.assertFaraPost()

    def test_trimite_cu_datele_deja_egale_nu_scrie_si_leaga(self):
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'deja_sincron', 'activitate_id': '1002'})
        self.assertFaraPost()
        self.assertEqual(self.legatura(), ('1002',) + BAZA)

    def test_trimite_fara_legatura_alege_cea_mai_apropiata_etapa_libera(self):
        self.muta_in_torqa('p1-i0', '11-25', '11-26')
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'sincronizat', 'activitate_id': '1002'})
        self.assertEqual(self.viu.activitate(1002)['start_date'], '2026-11-25 00:00')
        self.assertEqual(self.legatura(), ('1002', '2026-11-25', '2026-11-26'))

    def test_trimite_aceeasi_cerere_de_doua_ori_a_doua_nu_scrie(self):
        self.muta_in_torqa('p1-i0', '11-25', '11-26')
        self.trimite(implementare_id='p1-i0')
        self.viu.posturi.clear()
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'deja_sincron', 'activitate_id': '1002'})
        self.assertFaraPost()

    def test_trimite_fara_nicio_etapa_libera_creeaza_una(self):
        self.dashboard(('p1x', '26_287', 'pregatire', [('2026-12-01', '2026-12-02')]))
        self.leaga()                                                          # singura etapa a lui Ion e ocupata
        r = self.trimite(implementare_id='p1x-i0')
        self.assertEqual(r.get_json()['srp']['motiv'], 'etapa_noua')
        self.assertEqual([p['id'] == 1001 for p in self.viu.posturi], [True, False])
        self.assertEqual(self.legatura('p1x-i0')[1:], ('2026-12-01', '2026-12-02'))

    def test_dispozitivul_poate_trimite(self):
        self.muta_in_torqa('p1-i0', '11-25', '11-26')
        r = self.trimite(token=DEVICE, implementare_id='p1-i0')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json()['srp']['status'], 'ok')

    def test_fara_token_401(self):
        r = self.trimite(token=None, implementare_id='p1-i0')
        self.assertEqual(r.status_code, 401)
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))

    def test_intrari_invalide(self):
        self.assertEqual(self.trimite(implementare_id='nu-exista').status_code, 404)
        for corp in ({}, {'implementare_id': 5}, {'implementare_id': ''}, {'implementare_id': 'x' * 101},
                     {'implementare_id': 'p1-i0', 'activitate_id': 7}, {'implementare_id': 'p1-i0', 'activitate_id': ''}):
            self.assertEqual(self.trimite(**corp).status_code, 400, corp)
        r = self.client.post('/api/echipa/trimite', data='[1]', content_type='application/json', headers=self.bearer())
        self.assertEqual(r.status_code, 400)
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))

    def test_gantt_cazut_da_502_cu_srp_eroare_si_nu_muta_baza(self):
        self.leaga()
        self.muta_in_torqa('p1-i0', '11-20', '11-22')
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json()['srp']['status'], 'eroare')
        self.assertEqual(self.legatura(), ('1002',) + BAZA)

    def test_trimite_cu_alta_scriere_in_curs_da_409(self):
        with open(os.path.join(self.dir, 'scriere.lock'), 'w'):
            pass
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.status_code, 409)


# =============================================================================== alt plan, secretul, backup

class SursaNoua(CuGanttViu):

    def test_alt_plan_uita_legaturile_si_starea_rularii(self):
        self.ruleaza()
        self.assertEqual(self.legatura()[0], '1002')
        self.assertIn('sincronizare.json', os.listdir(self.dir))
        r = self.pune_sursa(planId='99999999-bbbb-cccc-dddd-eeeeeeeeeeee')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.legatura(), (None, None, None))
        self.assertNotIn('sincronizare.json', os.listdir(self.dir))
        self.assertEqual(self.date_perioada(), BAZA)                              # datele perioadei nu se ating

    def test_acelasi_plan_pastreaza_legaturile(self):
        self.ruleaza()
        self.assertEqual(self.pune_sursa().status_code, 200)
        self.assertEqual(self.legatura()[0], '1002')
        self.assertIn('sincronizare.json', os.listdir(self.dir))

    def test_un_put_respins_nu_atinge_legaturile(self):
        self.ruleaza()
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.pune_sursa(planId='99999999-bbbb-cccc-dddd-eeeeeeeeeeee')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.legatura()[0], '1002')


class SecretulNuIese(CuGanttViu):

    def verifica(self, text, unde):
        self.assertNotIn(SECRET, text, unde)
        self.assertNotIn(PLAN_ID, text, unde)

    def test_scenarii_de_succes_si_de_esec_fara_secret_in_log_si_in_raspuns(self):
        raspunsuri = []
        with self.capteaza_logul() as log:
            self.leaga()
            self.muta_in_torqa('p1-i0', '11-20', '11-22')
            raspunsuri.append(self.ruleaza())                                                   # succes
            self.api('post', '/api/proiecte/p1/implementari', {'id': 'i-nou', 'data_start': '2026-12-07', 'data_sfarsit': '2026-12-09'})
            raspunsuri.append(self.ruleaza())                                                   # etapa noua + radacina
            raspunsuri.append(self.api('post', '/api/echipa/trimite', {'implementare_id': 'p1-i0'}))
            self.leaga(aid='1003', baza=('2026-11-16', '2026-11-17'))
            raspunsuri.append(self.api('post', '/api/echipa/trimite', {'implementare_id': 'p1-i0'}))    # protejat
            self.viu.cade_get = True
            raspunsuri.append(self.ruleaza())                                                   # eroare
            raspunsuri.append(self.api('post', '/api/echipa/trimite', {'implementare_id': 'p1-i0'}))    # eroare
            raspunsuri += [self.client.get(c, headers=self.bearer(t)) for c, t in (
                ('/api/echipa', FULL), ('/api/echipa', DEVICE), ('/api/echipa/sursa', FULL),
                ('/api/calendar?start=2026-11-16&zile=14', FULL))]
        for r in raspunsuri:
            self.verifica(r.get_data(as_text=True), 'raspuns')
        self.verifica('\n'.join(log), 'log')
        self.assertTrue(any('cod=' in linie for linie in log))

    def test_trimiterea_reala_cere_url_ul_corect_si_nu_il_logheaza(self):
        class Raspuns:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        vazute = []

        def raspunde(cerere, timeout=None):
            vazute.append((cerere, timeout))
            return Raspuns()
        obiect = {'id': 1002, 'text': 'E1_PIF ș ț', 'start_date': '2026-11-20 00:00'}
        with mock.patch('urllib.request.urlopen', side_effect=raspunde):
            _REALA_TRIMITE(PLAN_ID, SECRET, obiect)
        cerere, timeout = vazute[0]
        self.assertEqual((cerere.get_method(), timeout), ('POST', 5))
        self.assertTrue(cerere.full_url.startswith(echipa.URL_ACTIVITATE + '?'))
        for parte in ('planId=' + PLAN_ID, 'secret=' + SECRET, 'writePassHash=&', 'taskId=1002'):
            self.assertIn(parte, cerere.full_url)
        self.assertNotIn('license', cerere.full_url)
        self.assertEqual(cerere.get_header('Content-type'), 'application/json; charset=utf-8')
        self.assertEqual(json.loads(cerere.data.decode('utf-8')), obiect)

    def test_trimiterea_reala_cazuta_nu_scoate_url_ul_in_erori(self):
        self.patch(echipa, '_trimite_activitate', _REALA_TRIMITE)
        self.leaga()
        self.muta_in_torqa('p1-i0', '11-20', '11-22')

        def cade(cerere, timeout=None):
            raise urllib.error.URLError('nu merge: ' + cerere.full_url)
        with mock.patch('urllib.request.urlopen', side_effect=cade):
            with self.capteaza_logul() as log:
                r = self.ruleaza()
        self.assertEqual((r.status_code, r.get_json()['rezultat']), (502, 'eroare'))
        self.verifica(r.get_data(as_text=True), 'raspuns')
        self.verifica('\n'.join(log), 'log')
        self.assertTrue(any('Gantt-ul nu raspunde la scriere' in linie for linie in log))

    def test_trimiterea_reala_cu_http_error_spune_doar_codul(self):
        self.patch(echipa, '_trimite_activitate', _REALA_TRIMITE)
        self.leaga()
        self.muta_in_torqa('p1-i0', '11-20', '11-22')

        def cade(cerere, timeout=None):
            raise urllib.error.HTTPError(cerere.full_url, 403, 'Forbidden ' + cerere.full_url, {}, io.BytesIO(b''))
        with mock.patch('urllib.request.urlopen', side_effect=cade):
            with self.capteaza_logul() as log:
                self.ruleaza()
        self.verifica('\n'.join(log), 'log')
        self.assertTrue(any('codul 403' in linie for linie in log))


class BackupSiRestore(CuGanttViu):

    def test_cele_trei_coloane_fac_dus_intors(self):
        self.leaga(aid='1768390299382', baza=('2026-11-18', '2026-11-19'))
        r = self.api('get', '/api/backup')
        self.assertEqual(r.status_code, 200)
        backup = r.get_json()
        self.assertEqual([(i['srp_activitate_id'], i['srp_sincron_start'], i['srp_sincron_end']) for i in backup['implementari']],
                         [('1768390299382', '2026-11-18', '2026-11-19')])
        self.leaga(aid=None, baza=None)                                          # baza se strica dupa backup
        self.assertEqual(self.legatura(), (None, None, None))
        rr = self.api('post', '/api/restore', backup)
        self.assertEqual(rr.status_code, 200, rr.get_data(as_text=True))
        self.assertEqual(self.legatura(), ('1768390299382', '2026-11-18', '2026-11-19'))

    def test_un_backup_de_dinainte_de_v47_se_restaureaza_cu_legatura_goala(self):
        backup = self.api('get', '/api/backup').get_json()
        for i in backup['implementari']:
            for c in coloane_srp():
                del i[c]
        rr = self.api('post', '/api/restore', backup)
        self.assertEqual(rr.status_code, 200, rr.get_data(as_text=True))
        self.assertEqual(self.legatura(), (None, None, None))

    def test_legatura_si_baza_nu_ies_in_api_ul_de_perioade(self):
        self.leaga()
        r = self.api('get', '/api/proiecte/p1/implementari')
        text = r.get_data(as_text=True)
        for c in coloane_srp():
            self.assertNotIn(c, text)


def coloane_srp():
    import database
    return database.COLOANE_SRP


if __name__ == '__main__':
    import unittest
    unittest.main()

"""Dashboard -> Gantt: sincronizarea perioadelor cu etapele lui Ion (`blueprints/echipa.py`, v47).

Ce se pazeste, tacut daca se strica:
  - dupa o perioada salvata (POST / PUT), serverul scrie in Gantt DOAR etapa lui Ion si DOAR patru
    campuri (start_date, end_date, duration, constraint_date); restul obiectului brut ramane identic;
  - o etapa fara Ion pe ea nu se atinge niciodata (`protejat`, zero POST);
  - o etapa mutata de altcineva in Gantt da `conflict` si nu se scrie; `/api/echipa/trimite` (decizia
    lui Ion) ignora conflictul, dar nu protectia;
  - perioada din dashboard ramane salvata oricum: Gantt cazut -> `srp.status = eroare`, nimic altceva;
  - nu se trimite nimic cand datele sunt deja egale (`deja_sincron`);
  - DELETE nu atinge Gantt-ul;
  - secretul nu iese in raspuns, in log sau in erori;
  - coloana `implementari.srp_activitate_id` face dus-intors prin backup si restore.
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


class GanttViu:
    """Un Gantt in memorie: GET intoarce planul curent, POST inlocuieste (sau adauga) activitatea cu
    acelasi id, ca serverul real. Numara apelurile."""

    def __init__(self, activitati):
        self.activitati = copy.deepcopy(activitati)
        self.get_uri = 0
        self.posturi = []
        self.cade_get = False
        self.cade_post = False
        self.aplica = True                     # False: POST-ul „reuseste", dar planul nu se schimba

    def __call__(self, plan_id, secret):
        self.get_uri += 1
        if self.cade_get:
            raise echipa.EroareGantt('Gantt-ul nu raspunde')
        return gantt(copy.deepcopy(self.activitati))

    def trimite(self, plan_id, secret, activitate):
        if self.cade_post:
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


class CuGanttViu(CuEchipa):

    def setUp(self):
        super().setUp()
        self.viu = GanttViu(plan_sync())
        self.patch(echipa, '_descarca', self.viu)
        self.patch(echipa, '_trimite_activitate', self.viu.trimite)
        self.dashboard(('p1', '26_287', 'pregatire', [('2026-11-18', '2026-11-19')]))
        self.configureaza()
        self.viu.get_uri = 0                   # numaram doar ce face sincronizarea

    # ----------------------------------------------------------------------- ajutoare

    def api(self, metoda, cale, corp=None, token=FULL):
        r = getattr(self.client, metoda)(cale, json=corp, headers=self.bearer(token) if token else {})
        return r

    def put_perioada(self, impl_id, **corp):
        return self.api('put', '/api/implementari/' + impl_id, corp)

    def post_perioada(self, proiect_id, **corp):
        return self.api('post', '/api/proiecte/%s/implementari' % proiect_id, corp)

    def legatura(self, impl_id):
        con = sqlite3.connect(self.db)
        try:
            return con.execute('SELECT srp_activitate_id FROM implementari WHERE id = ?', (impl_id,)).fetchone()[0]
        finally:
            con.close()

    def seteaza_legatura(self, impl_id, activitate_id):
        con = sqlite3.connect(self.db)
        con.execute('UPDATE implementari SET srp_activitate_id = ? WHERE id = ?', (activitate_id, impl_id))
        con.commit()
        con.close()

    def date_perioada(self, impl_id):
        con = sqlite3.connect(self.db)
        try:
            return con.execute('SELECT data_start, data_sfarsit FROM implementari WHERE id = ?', (impl_id,)).fetchone()
        finally:
            con.close()

    def srp(self, r, cod=None):
        self.assertIn(r.status_code, (200, 201) if cod is None else (cod,), r.get_data(as_text=True))
        return r.get_json()['srp']

    def assertFaraPost(self):
        self.assertEqual(self.viu.posturi, [])


# =============================================================================== PUT

class PutPerioada(CuGanttViu):

    def test_put_sincron_trimite_exact_campurile_schimbate(self):
        original = copy.deepcopy(self.viu.activitate(1002))
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['message'], 'ok')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'sincronizat', 'activitate_id': '1002'})
        self.assertEqual(len(self.viu.posturi), 1)
        trimis = self.viu.posturi[0]
        self.assertEqual({k for k in trimis if trimis[k] != original.get(k)}, CAMPURI_SCRISE)
        self.assertEqual(trimis, {**original, 'start_date': '2026-11-20 00:00', 'end_date': '2026-11-22 23:59',
                                  'duration': 3, 'constraint_date': '2026-11-20 00:00'})
        self.assertEqual((trimis['state'], trimis['progress'], trimis['row_height'], trimis['resource']),
                         ('progress', 0.5, 40, ['r1']))
        self.assertEqual(self.legatura('p1-i0'), '1002')
        self.assertEqual(self.date_perioada('p1-i0'), ('2026-11-20', '2026-11-22'))
        # Verificare: GET de proba si snapshot-ul reimprospatat.
        stare = {a['id']: a for a in self.echipa()['activitati']}
        self.assertEqual((stare['1002']['start'], stare['1002']['end']), ('2026-11-20', '2026-11-22'))

    def test_constraint_date_se_muta_doar_daca_era_egal_cu_vechiul_start(self):
        self.viu.activitate(1002)['constraint_date'] = '2026-11-01 00:00'
        self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(self.viu.posturi[0]['constraint_date'], '2026-11-01 00:00')
        self.viu.posturi.clear()
        self.viu.activitate(1002)['constraint_date'] = None
        self.put_perioada('p1-i0', data_start='2026-11-23', data_sfarsit='2026-11-23')
        self.assertIsNone(self.viu.posturi[0]['constraint_date'])
        self.assertEqual(self.viu.posturi[0]['duration'], 1)

    def test_durata_e_in_zile_calendaristice_inclusiv(self):
        self.assertEqual(echipa._zile_inclusiv(('2026-04-24', '2026-06-08')), 46)
        self.assertEqual(echipa._zile_inclusiv(('2026-11-20', '2026-11-20')), 1)

    def test_perioada_fara_sfarsit_e_o_zi(self):
        self.put_perioada('p1-i0', data_start='2026-11-24', data_sfarsit='')
        self.assertEqual((self.viu.posturi[0]['start_date'], self.viu.posturi[0]['end_date'], self.viu.posturi[0]['duration']),
                         ('2026-11-24 00:00', '2026-11-24 23:59', 1))

    def test_fara_schimbare_de_date_nu_se_atinge_gantt_ul(self):
        r = self.put_perioada('p1-i0', eticheta='Altă etichetă', confirmata=1)
        self.assertEqual(r.get_json()['srp'], {'status': 'ignorat', 'motiv': 'date_neschimbate', 'activitate_id': None})
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))

    def test_use_srp_dates_e_deja_sincron_si_nu_trimite_nimic(self):
        # Gantt-ul a fost mutat de altcineva; Torqa face PUT cu datele din SRP.
        a = self.viu.activitate(1002)
        a['start_date'], a['end_date'] = '2026-11-25 00:00', '2026-11-26 23:59'
        self.seteaza_legatura('p1-i0', '1002')
        r = self.put_perioada('p1-i0', data_start='2026-11-25', data_sfarsit='2026-11-26')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'deja_sincron', 'activitate_id': '1002'})
        self.assertFaraPost()

    def test_use_srp_dates_fara_legatura_gaseste_etapa_dupa_intervalul_nou(self):
        a = self.viu.activitate(1002)
        a['start_date'], a['end_date'] = '2026-11-25 00:00', '2026-11-26 23:59'
        r = self.put_perioada('p1-i0', data_start='2026-11-25', data_sfarsit='2026-11-26')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'deja_sincron', 'activitate_id': '1002'})
        self.assertFaraPost()
        self.assertEqual(self.legatura('p1-i0'), '1002')

    def test_a_doua_salvare_identica_nu_mai_scrie(self):
        self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.viu.posturi.clear()
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp']['status'], 'ignorat')
        self.assertFaraPost()

    def test_tinta_se_gaseste_dupa_intervalul_vechi_fara_legatura_salvata(self):
        self.assertIsNone(self.legatura('p1-i0'))
        self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-20')
        self.assertEqual([p['id'] for p in self.viu.posturi], [1002])

    def test_etapa_ocupata_de_alta_perioada_nu_e_tinta(self):
        self.dashboard(('p1b', '26_287', 'finalizat', [('2026-11-18', '2026-11-19')]))
        self.seteaza_legatura('p1b-i0', '1002')
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-20')
        # 1002 apartine altei perioade: aici se creeaza o etapa noua, iar 1002 ramane neatinsa.
        self.assertEqual(r.get_json()['srp']['motiv'], 'etapa_noua')
        self.assertNotIn(1002, [p['id'] for p in self.viu.posturi])

    def test_etapa_fara_ion_e_protejata_zero_post(self):
        self.seteaza_legatura('p1-i0', '1003')                       # legatura spre etapa unui coleg
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp'], {'status': 'protejat', 'motiv': 'ion_nu_e_pe_etapa', 'activitate_id': '1003'})
        self.assertFaraPost()
        self.assertEqual(self.date_perioada('p1-i0'), ('2026-11-20', '2026-11-22'))

    def test_ion_scos_de_pe_etapa_intre_timp_e_protejat(self):
        self.seteaza_legatura('p1-i0', '1002')
        self.viu.activitate(1002)['resource'] = ['r2']
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp']['status'], 'protejat')
        self.assertFaraPost()

    def test_etapa_mutata_in_gantt_da_conflict_zero_post(self):
        self.seteaza_legatura('p1-i0', '1002')
        a = self.viu.activitate(1002)
        a['start_date'], a['end_date'] = '2026-11-25 00:00', '2026-11-26 23:59'
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp'], {'status': 'conflict', 'motiv': 'etapa_mutata_in_gantt', 'activitate_id': '1002'})
        self.assertFaraPost()
        self.assertEqual(self.date_perioada('p1-i0'), ('2026-11-20', '2026-11-22'))     # dashboard-ul ramane salvat

    def test_lungeste_radacina_cand_etapa_iese_din_ea(self):
        radacina = copy.deepcopy(self.viu.activitate(1001))
        r = self.put_perioada('p1-i0', data_start='2026-11-28', data_sfarsit='2026-12-04')
        self.assertEqual(r.get_json()['srp']['status'], 'ok')
        self.assertEqual([p['id'] for p in self.viu.posturi], [1001, 1002])     # radacina intai
        self.assertEqual(self.viu.posturi[0], {**radacina, 'end_date': '2026-12-04 23:59', 'duration': 19})

    def test_radacina_nu_se_scurteaza_si_nu_se_atinge_cand_etapa_ramane_in_ea(self):
        self.put_perioada('p1-i0', data_start='2026-11-17', data_sfarsit='2026-11-29')
        self.assertEqual([p['id'] for p in self.viu.posturi], [1002])

    def test_radacina_fara_ion_nu_se_lungeste_dar_etapa_se_scrie(self):
        self.viu.activitate(1001)['resource'] = ['r2']
        self.put_perioada('p1-i0', data_start='2026-11-28', data_sfarsit='2026-12-04')
        self.assertEqual([p['id'] for p in self.viu.posturi], [1002])

    def test_proiect_fara_cod_sau_fara_radacina_e_ignorat_fara_scriere(self):
        self.dashboard(('p9', 'TBD', 'pregatire', [('2026-11-18', '2026-11-19')]),
                       ('p8', '26_999', 'pregatire', [('2026-11-18', '2026-11-19')]))
        r = self.put_perioada('p9-i0', data_start='2026-11-20')
        self.assertEqual(r.get_json()['srp'], {'status': 'ignorat', 'motiv': 'fara_cod', 'activitate_id': None})
        r = self.put_perioada('p8-i0', data_start='2026-11-20')
        self.assertEqual(r.get_json()['srp'], {'status': 'ignorat', 'motiv': 'fara_radacina', 'activitate_id': None})
        self.assertFaraPost()

    def test_fara_sursa_configurata_nu_se_face_nicio_cerere(self):
        os.remove(os.path.join(self.dir, 'sursa.json'))
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp'], {'status': 'ignorat', 'motiv': 'fara_sursa', 'activitate_id': None})
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))

    def test_perioada_inexistenta_ramane_404_fara_cheia_srp(self):
        r = self.put_perioada('nu-exista', data_start='2026-11-20')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn('srp', r.get_json())


# =============================================================================== POST (perioada noua)

class PerioadaNoua(CuGanttViu):

    def test_perioada_noua_cu_ion_pe_radacina_creeaza_etapa(self):
        r = self.post_perioada('p1', id='i-nou', data_start='2026-11-24', data_sfarsit='2026-11-25', eticheta='Montaj')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['id'], 'i-nou')
        srp = r.get_json()['srp']
        self.assertEqual((srp['status'], srp['motiv']), ('ok', 'etapa_noua'))
        self.assertEqual(len(self.viu.posturi), 1)                  # in radacina (16-30.11): fara lungire
        nou = self.viu.posturi[0]
        self.assertEqual(srp['activitate_id'], str(nou['id']))
        self.assertIsInstance(nou['id'], int)
        self.assertNotIn(nou['id'], {1001, 1002, 1003})
        self.assertEqual((nou['parent'], nou['text'], nou['resource'], nou['type'], nou['progress'], nou['open']),
                         ('1001', 'Montaj', ['r1'], 'task', 0, True))
        self.assertEqual((nou['constraint_type'], nou['constraint_date'], nou['start_date'], nou['end_date'], nou['duration']),
                         ('asap', '2026-11-24 00:00', '2026-11-24 00:00', '2026-11-25 23:59', 2))
        self.assertNotIn('state', nou)                              # nu mosteneste starea sablonului
        self.assertEqual((nou['row_height'], nou['color']), (40, '#123456'))   # restul dupa o etapa existenta
        self.assertEqual(self.legatura('i-nou'), str(nou['id']))
        self.assertEqual(self.date_perioada('i-nou'), ('2026-11-24', '2026-11-25'))

    def test_eticheta_goala_da_textul_pif(self):
        self.post_perioada('p1', data_start='2026-11-24', data_sfarsit='2026-11-25')
        self.assertEqual(self.viu.posturi[0]['text'], 'PIF')

    def test_perioada_noua_in_afara_radacinii_o_lungeste_si_apoi_creeaza_etapa(self):
        self.post_perioada('p1', data_start='2026-12-07', data_sfarsit='2026-12-09')
        self.assertEqual([p['id'] == 1001 for p in self.viu.posturi], [True, False])
        self.assertEqual(self.viu.posturi[0]['end_date'], '2026-12-09 23:59')

    def test_perioada_noua_cu_intervalul_unei_etape_a_lui_ion_o_adopta_fara_duplicat(self):
        r = self.post_perioada('p1', id='i-x', data_start='2026-11-18', data_sfarsit='2026-11-19')
        # 1002 e a perioadei p1-i0 (nelegata inca), deci e libera: se adopta, nu se creeaza o a doua.
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'deja_sincron', 'activitate_id': '1002'})
        self.assertFaraPost()

    def test_fara_ion_pe_radacina_perioada_noua_e_protejata(self):
        self.viu.activitate(1001)['resource'] = ['r2']
        r = self.post_perioada('p1', data_start='2026-11-24', data_sfarsit='2026-11-25')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['srp'], {'status': 'protejat', 'motiv': 'ion_nu_e_pe_radacina', 'activitate_id': None})
        self.assertFaraPost()

    def test_id_nou_nu_se_ciocneste_cu_unul_existent(self):
        ms = int(T0.timestamp() * 1000)
        self.viu.activitati.append(act(ms, 'Alta', '1001', zi('11-16'), zi('11-16', True), resource=['r2']))
        self.post_perioada('p1', data_start='2026-11-24', data_sfarsit='2026-11-25')
        self.assertEqual(self.viu.posturi[0]['id'], ms + 1)

    def test_radacina_fara_nicio_etapa_da_un_sablon_minimal(self):
        self.viu.activitati = [act(1001, 'C26_287_Proiect', 0, zi('11-16'), zi('11-30', True), resource=['r1'])]
        self.post_perioada('p1', data_start='2026-11-24', data_sfarsit='2026-11-25')
        nou = self.viu.posturi[0]
        self.assertEqual((nou['parent'], nou['resource'], nou['type'], nou['constraint_type']), ('1001', ['r1'], 'task', 'asap'))


# =============================================================================== erori

class Erori(CuGanttViu):

    def test_gantt_cazut_la_post_perioada_salvata_status_eroare(self):
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.post_perioada('p1', id='i-nou', data_start='2026-11-24', data_sfarsit='2026-11-25')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()['srp'], {'status': 'eroare', 'motiv': 'gantt_indisponibil', 'activitate_id': None})
        self.assertEqual(self.date_perioada('i-nou'), ('2026-11-24', '2026-11-25'))

    def test_gantt_cazut_la_put_perioada_salvata_status_eroare(self):
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['srp']['status'], 'eroare')
        self.assertEqual(self.date_perioada('p1-i0'), ('2026-11-20', '2026-11-22'))
        self.assertIsNone(self.legatura('p1-i0'))

    def test_scrierea_respinsa_de_gantt_e_eroare_si_perioada_ramane(self):
        self.viu.cade_post = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp'], {'status': 'eroare', 'motiv': 'gantt_indisponibil', 'activitate_id': None})
        self.assertEqual(self.date_perioada('p1-i0'), ('2026-11-20', '2026-11-22'))

    def test_verificarea_care_nu_vede_datele_noi_e_eroare_fara_legatura(self):
        self.viu.aplica = False
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp'], {'status': 'eroare', 'motiv': 'verificare_esuata', 'activitate_id': '1002'})
        self.assertIsNone(self.legatura('p1-i0'))
        self.assertEqual(len(self.viu.posturi), 1)                  # fara retry automat

    def test_o_eroare_neasteptata_nu_strica_raspunsul(self):
        with mock.patch.object(echipa, '_citeste_perioada', side_effect=RuntimeError('boom')):
            with self.assertLogs('pif_dashboard', 'WARNING') as log:
                r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()['srp'], {'status': 'eroare', 'motiv': 'eroare_interna', 'activitate_id': None})
        self.assertIn('RuntimeError', '\n'.join(log.output))

    def test_un_lacat_proaspat_de_scriere_opreste_sincronizarea(self):
        with open(os.path.join(self.dir, 'scriere.lock'), 'w'):
            pass
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp'], {'status': 'eroare', 'motiv': 'sincronizare_in_curs', 'activitate_id': None})
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))

    def test_lacatul_se_elibereaza_dupa_fiecare_sincronizare(self):
        self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertNotIn('scriere.lock', os.listdir(self.dir))
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            self.put_perioada('p1-i0', data_start='2026-11-23', data_sfarsit='2026-11-24')
        self.assertNotIn('scriere.lock', os.listdir(self.dir))

    def test_un_lacat_vechi_nu_blocheaza(self):
        lacat = os.path.join(self.dir, 'scriere.lock')
        with open(lacat, 'w'):
            pass
        vechi = time.time() - echipa.EXPIRARE_LACAT_SCRIERE - 5
        os.utime(lacat, (vechi, vechi))
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp']['status'], 'ok')

    def test_email_necunoscut_in_plan_e_protejat(self):
        con = open(os.path.join(self.dir, 'sursa.json'), encoding='utf-8')
        sursa = json.load(con)
        con.close()
        sursa['email'] = 'altcineva@exemplu.test'
        with open(os.path.join(self.dir, 'sursa.json'), 'w', encoding='utf-8') as fh:
            json.dump(sursa, fh)
        r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp']['motiv'], 'email_necunoscut')
        self.assertFaraPost()


# =============================================================================== DELETE

class Stergere(CuGanttViu):

    def test_delete_nu_atinge_gantt_ul(self):
        self.seteaza_legatura('p1-i0', '1002')
        r = self.api('delete', '/api/implementari/p1-i0')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('srp', r.get_json())
        self.assertEqual((self.viu.get_uri, self.viu.posturi), (0, []))
        self.assertEqual(self.viu.activitate(1002)['start_date'], '2026-11-18 00:00')      # etapa ramane


# =============================================================================== /api/echipa/trimite

class Trimite(CuGanttViu):

    def trimite(self, token=FULL, **corp):
        return self.api('post', '/api/echipa/trimite', corp, token=token)

    def test_trimite_ignora_conflictul(self):
        self.seteaza_legatura('p1-i0', '1002')
        a = self.viu.activitate(1002)
        a['start_date'], a['end_date'] = '2026-11-25 00:00', '2026-11-26 23:59'
        con = sqlite3.connect(self.db)
        con.execute("UPDATE implementari SET data_start = '2026-11-20', data_sfarsit = '2026-11-22' WHERE id = 'p1-i0'")
        con.commit()
        con.close()
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json(), {'srp': {'status': 'ok', 'motiv': 'sincronizat', 'activitate_id': '1002'}})
        self.assertEqual(len(self.viu.posturi), 1)
        self.assertEqual((self.viu.posturi[0]['start_date'], self.viu.posturi[0]['end_date']),
                         ('2026-11-20 00:00', '2026-11-22 23:59'))
        # constraint_date era 2026-11-18 (nu startul curent din Gantt, 25.11): ramane
        self.assertEqual(self.viu.posturi[0]['constraint_date'], '2026-11-18 00:00')

    def test_trimite_pastreaza_protectia(self):
        self.seteaza_legatura('p1-i0', '1003')
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.get_json()['srp'], {'status': 'protejat', 'motiv': 'ion_nu_e_pe_etapa', 'activitate_id': '1003'})
        self.assertFaraPost()

    def test_trimite_cu_etapa_aleasa_a_unui_coleg_e_protejat(self):
        r = self.trimite(implementare_id='p1-i0', activitate_id='1003')
        self.assertEqual(r.get_json()['srp']['status'], 'protejat')
        self.assertFaraPost()

    def test_trimite_cu_etapa_inexistenta_e_protejat(self):
        r = self.trimite(implementare_id='p1-i0', activitate_id='999999')
        self.assertEqual(r.get_json()['srp'], {'status': 'protejat', 'motiv': 'etapa_necunoscuta', 'activitate_id': None})
        self.assertFaraPost()

    def test_trimite_fara_legatura_alege_cea_mai_apropiata_etapa_libera(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE implementari SET data_start = '2026-11-25', data_sfarsit = '2026-11-26' WHERE id = 'p1-i0'")
        con.commit()
        con.close()
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'sincronizat', 'activitate_id': '1002'})
        self.assertEqual(self.viu.activitate(1002)['start_date'], '2026-11-25 00:00')
        self.assertEqual(self.legatura('p1-i0'), '1002')

    def test_trimite_aceeasi_cerere_de_doua_ori_a_doua_nu_scrie(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE implementari SET data_start = '2026-11-25', data_sfarsit = '2026-11-26' WHERE id = 'p1-i0'")
        con.commit()
        con.close()
        self.trimite(implementare_id='p1-i0')
        self.viu.posturi.clear()
        r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.get_json()['srp'], {'status': 'ok', 'motiv': 'deja_sincron', 'activitate_id': '1002'})
        self.assertFaraPost()

    def test_trimite_fara_nicio_etapa_libera_creeaza_una(self):
        self.dashboard(('p1x', '26_287', 'pregatire', [('2026-12-01', '2026-12-02')]))
        self.seteaza_legatura('p1-i0', '1002')                      # singura etapa a lui Ion e ocupata
        r = self.trimite(implementare_id='p1x-i0')
        self.assertEqual(r.get_json()['srp']['motiv'], 'etapa_noua')

    def test_dispozitivul_poate_trimite(self):
        con = sqlite3.connect(self.db)
        con.execute("UPDATE implementari SET data_start = '2026-11-25', data_sfarsit = '2026-11-26' WHERE id = 'p1-i0'")
        con.commit()
        con.close()
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

    def test_gantt_cazut_da_502_cu_srp_eroare(self):
        self.viu.cade_get = True
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.status_code, 502)
        self.assertEqual(r.get_json()['srp']['status'], 'eroare')

    def test_trimite_cu_perioada_blocata_de_alt_worker_da_409(self):
        with open(os.path.join(self.dir, 'scriere.lock'), 'w'):
            pass
        with self.assertLogs('pif_dashboard', 'WARNING'):
            r = self.trimite(implementare_id='p1-i0')
        self.assertEqual(r.status_code, 409)


# =============================================================================== secretul

class SecretulNuIese(CuGanttViu):

    def verifica(self, text, unde):
        self.assertNotIn(SECRET, text, unde)
        self.assertNotIn(PLAN_ID, text, unde)

    def test_scenarii_de_succes_si_de_esec_fara_secret_in_log_si_in_raspuns(self):
        with self.capteaza_logul() as log:
            raspunsuri = [
                self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22'),
                self.post_perioada('p1', data_start='2026-11-24', data_sfarsit='2026-11-25'),
                self.api('post', '/api/echipa/trimite', {'implementare_id': 'p1-i0'}),
            ]
            self.seteaza_legatura('p1-i0', '1003')
            raspunsuri.append(self.put_perioada('p1-i0', data_start='2026-11-26', data_sfarsit='2026-11-27'))     # protejat
            self.viu.cade_get = True
            raspunsuri.append(self.put_perioada('p1-i0', data_start='2026-11-28', data_sfarsit='2026-11-29'))     # eroare
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

        def cade(cerere, timeout=None):
            raise urllib.error.URLError('nu merge: ' + cerere.full_url)
        with mock.patch('urllib.request.urlopen', side_effect=cade):
            with self.capteaza_logul() as log:
                r = self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.assertEqual(r.get_json()['srp'], {'status': 'eroare', 'motiv': 'gantt_indisponibil', 'activitate_id': None})
        self.verifica(r.get_data(as_text=True), 'raspuns')
        self.verifica('\n'.join(log), 'log')
        self.assertTrue(any('Gantt-ul nu raspunde la scriere' in linie for linie in log))

    def test_trimiterea_reala_cu_http_error_spune_doar_codul(self):
        self.patch(echipa, '_trimite_activitate', _REALA_TRIMITE)

        def cade(cerere, timeout=None):
            raise urllib.error.HTTPError(cerere.full_url, 403, 'Forbidden ' + cerere.full_url, {}, io.BytesIO(b''))
        with mock.patch('urllib.request.urlopen', side_effect=cade):
            with self.capteaza_logul() as log:
                self.put_perioada('p1-i0', data_start='2026-11-20', data_sfarsit='2026-11-22')
        self.verifica('\n'.join(log), 'log')
        self.assertTrue(any('codul 403' in linie for linie in log))


# =============================================================================== backup / restore

class BackupSiRestore(CuGanttViu):

    def test_coloana_srp_activitate_id_face_dus_intors(self):
        self.seteaza_legatura('p1-i0', '1768390299382')
        r = self.api('get', '/api/backup')
        self.assertEqual(r.status_code, 200)
        backup = r.get_json()
        self.assertEqual([i['srp_activitate_id'] for i in backup['implementari']], ['1768390299382'])
        self.seteaza_legatura('p1-i0', None)                         # baza se strica dupa backup
        self.assertIsNone(self.legatura('p1-i0'))
        rr = self.api('post', '/api/restore', backup)
        self.assertEqual(rr.status_code, 200, rr.get_data(as_text=True))
        self.assertEqual(self.legatura('p1-i0'), '1768390299382')

    def test_un_backup_de_dinainte_de_v47_se_restaureaza_cu_legatura_goala(self):
        backup = self.api('get', '/api/backup').get_json()
        for i in backup['implementari']:
            del i['srp_activitate_id']
        rr = self.api('post', '/api/restore', backup)
        self.assertEqual(rr.status_code, 200, rr.get_data(as_text=True))
        self.assertIsNone(self.legatura('p1-i0'))

    def test_legatura_nu_iese_in_api_ul_de_perioade(self):
        self.seteaza_legatura('p1-i0', '1002')
        r = self.api('get', '/api/proiecte/p1/implementari')
        self.assertNotIn('srp_activitate_id', r.get_data(as_text=True))


if __name__ == '__main__':
    import unittest
    unittest.main()

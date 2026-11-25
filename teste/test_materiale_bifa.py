"""Bifa manuala pe materiale: `PUT /api/materiale/bifa` si cum o aplica `GET /api/materiale`.

Ion bifeaza in Torqa ca un articol „a ajuns la destinatie" sau e „livrat", peste ce spune colectorul. Ce se pazeste,
tacut daca se strica:
  - corpul gresit da 400 cu numele campului, fara snapshot curent sau cu un articol necunoscut da 409, si niciuna
    din ele nu scrie nimic;
  - null scoate bifa, aceeasi stare de doua ori nu schimba nimic (nici ora `la`), iar tokenul de dispozitiv scrie
    (ruta nu e in DEVICE_TOKEN_READ_ONLY, care e exact-match pe `/api/materiale`);
  - la citire, o bifa peste starea colectorului schimba `stare` (cu `stare_colector`), scoate `intarziat` si
    ajusteaza `rezumat`; colectorul deja la nivelul bifei ramane cum e, dar `bifa` apare;
  - bifa traieste in `app_settings` (intra in backup, restore o aduce inapoi), nu in snapshot: o colectare noua
    n-o sterge, iar snapshot-ul de pe disc ramane cu starile colectorului;
  - un articol bifat nu mai da alerta de livrare cand serverul calculeaza alertele.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import materiale
from utils import device_token_denied

PID = 'p-26-337'
PID2 = 'p-26-088'
LA = '2026-11-25T10:00:00Z'


def rand(cod, stare, termen=None, tip=None, intarziat=False, **camp):
    return {'cod_bc': cod, 'descriere': 'Articol ' + cod, 'stare': stare, 'termen': termen, 'termen_tip': tip,
            'intarziat': intarziat, **camp}


def materiale_standard():
    return [rand('A', 'confirmat', '2026-11-30', 'confirmat'),
            rand('B', 'confirmat', '2026-12-05', 'confirmat'),
            rand('C', 'in_tranzit', '2026-11-20', 'planificat', intarziat=True),
            rand('D', 'livrat', '2026-11-10', 'livrat'),
            rand('E', 'la_destinatie', '2026-11-12', 'primit')]


def rezumat_standard():
    return {'total': 5, 'pe_stare': {'confirmat': 2, 'in_tranzit': 1, 'livrat': 1, 'la_destinatie': 1}, 'intarziate': 1,
            'urmatoarea': {'data': '2026-11-30', 'tip': 'confirmat', 'stare': 'confirmat', 'descriere': 'Articol A',
                           'cod_bc': 'A'},
            'ultima_asteptata': '2026-12-05'}


def proiect(pid=PID, mat=None, rez=None, **camp):
    return {'proiect_id': pid, 'cod_proiect': '26_337',
            'materiale': materiale_standard() if mat is None else mat,
            'rezumat': rezumat_standard() if rez is None else rez, **camp}


def corp(*proiecte, generat='2026-11-25T08:02:11+02:00', **sursa):
    return {'generat': generat, 'sursa': {'bc': 'BC', **sursa}, 'proiecte': list(proiecte)}


class Baza(CuAplicatia):
    """Snapshot-uri intr-un director temporar, „acum" fix si cheia `materiale_bife` goala la fiecare test."""

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'materiale')
        self.patch(materiale, 'DIR_MATERIALE', self.dir)
        self.acum = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
        self.patch(materiale, '_acum', lambda: self.acum)
        self.sql("DELETE FROM app_settings WHERE key = 'materiale_bife'")

    def sql(self, text, *param):
        c = sqlite3.connect(self.db)
        try:
            r = c.execute(text, param).fetchall()
            c.commit()
            return r
        finally:
            c.close()

    def snapshot(self, *proiecte, token=FULL, **kw):
        r = self.client.put('/api/materiale', json=corp(*(proiecte or (proiect(),)), **kw), headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r

    def bifeaza(self, cod, stare, pid=PID, token=FULL):
        return self.client.put('/api/materiale/bifa', json={'proiect_id': pid, 'cod_bc': cod, 'stare': stare},
                               headers=self.bearer(token) if token else {})

    def citeste(self, token=FULL):
        r = self.client.get('/api/materiale', headers=self.bearer(token))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def proiect_in(self, j, pid=PID):
        return next(p for p in j['proiecte'] if p['proiect_id'] == pid)

    def rand_in(self, j, cod, pid=PID):
        return next(m for m in self.proiect_in(j, pid)['materiale'] if m['cod_bc'] == cod)

    def stocat(self):
        r = self.sql("SELECT value FROM app_settings WHERE key = 'materiale_bife'")
        return json.loads(r[0][0]) if r else None


class PutBifa(Baza):

    def test_bifa_ok_raspunde_cu_ora_utc_si_se_stocheaza_in_app_settings(self):
        self.snapshot()
        r = self.bifeaza('A', 'la_destinatie')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(r.get_json(), {'ok': True, 'bifa': {'stare': 'la_destinatie', 'la': LA}})
        self.assertEqual(self.stocat(), {PID: {'A': {'stare': 'la_destinatie', 'la': LA}}})

    def test_null_scoate_bifa_si_o_a_doua_scoatere_e_tot_200(self):
        self.snapshot()
        self.bifeaza('A', 'livrat')
        r = self.bifeaza('A', None)
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'bifa': None}))
        self.assertEqual(self.stocat(), {}, 'ultimul articol scos nu lasa proiectul gol in stocare')
        r = self.bifeaza('A', None)
        self.assertEqual((r.status_code, r.get_json()), (200, {'ok': True, 'bifa': None}))
        self.assertNotIn('bifa', self.rand_in(self.citeste(), 'A'))

    def test_aceeasi_stare_de_doua_ori_pastreaza_ora_prima_data(self):
        self.snapshot()
        prima = self.bifeaza('A', 'livrat').get_json()
        self.acum = datetime(2026, 11, 25, 15, 30, tzinfo=timezone.utc)       # reincercarea vine mai tarziu
        a_doua = self.bifeaza('A', 'livrat').get_json()
        self.assertEqual(a_doua, prima)
        self.assertEqual(a_doua['bifa']['la'], LA)

    def test_alta_stare_inlocuieste_bifa_cu_ora_noua(self):
        self.snapshot()
        self.bifeaza('A', 'la_destinatie')
        self.acum = datetime(2026, 11, 25, 15, 30, tzinfo=timezone.utc)
        r = self.bifeaza('A', 'livrat')
        self.assertEqual(r.get_json()['bifa'], {'stare': 'livrat', 'la': '2026-11-25T15:30:00Z'})
        self.assertEqual(list(self.stocat()[PID]), ['A'], 'o singura bifa pe articol')

    def test_bifele_a_doua_proiecte_si_a_doua_articole_se_pastreaza_laolalta(self):
        self.snapshot(proiect(), proiect(PID2))
        self.bifeaza('A', 'livrat')
        self.bifeaza('B', 'la_destinatie')
        self.bifeaza('A', 'la_destinatie', pid=PID2)
        self.assertEqual(self.stocat(), {PID: {'A': {'stare': 'livrat', 'la': LA}, 'B': {'stare': 'la_destinatie', 'la': LA}},
                                         PID2: {'A': {'stare': 'la_destinatie', 'la': LA}}})

    def test_corp_gresit_da_400_cu_numele_campului_si_nu_scrie(self):
        self.snapshot()
        bun = {'proiect_id': PID, 'cod_bc': 'A', 'stare': 'livrat'}
        cazuri = [
            (dict(bun, proiect_id=None), 'proiect_id'),
            (dict(bun, proiect_id=''), 'proiect_id'),
            (dict(bun, proiect_id='p 1; DROP'), 'proiect_id'),
            (dict(bun, proiect_id=7), 'proiect_id'),
            (dict(bun, cod_bc=None), 'cod_bc'),
            (dict(bun, cod_bc='   '), 'cod_bc'),
            (dict(bun, cod_bc=12), 'cod_bc'),
            (dict(bun, cod_bc='x' * 1001), 'cod_bc'),
            (dict(bun, stare='ajuns'), 'stare'),
            (dict(bun, stare='confirmat'), 'stare'),            # starile colectorului nu se bifeaza
            (dict(bun, stare=1), 'stare'),
            (dict(bun, stare=True), 'stare'),
            (dict(bun, stare=['livrat']), 'stare'),
            ({k: v for k, v in bun.items() if k != 'stare'}, 'stare'),   # lipsa campului nu e „scoate bifa"
        ]
        for corp_, camp in cazuri:
            with self.subTest(corp=corp_):
                r = self.client.put('/api/materiale/bifa', json=corp_, headers=self.bearer())
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertTrue(r.get_json()['error'].startswith(camp + ':'), r.get_json())
        for brut in ('nu e json', '[1, 2]', '"text"', 'null'):
            with self.subTest(brut=brut):
                r = self.client.put('/api/materiale/bifa', data=brut, headers=dict(self.bearer(), **{'Content-Type': 'application/json'}))
                self.assertEqual(r.status_code, 400)
                self.assertIn('error', r.get_json())
        self.assertIsNone(self.stocat(), 'nicio cerere respinsa nu scrie in app_settings')

    def test_corp_prea_mare_da_413(self):
        self.snapshot()
        r = self.client.put('/api/materiale/bifa', json={'proiect_id': PID, 'cod_bc': 'A' * 20000, 'stare': 'livrat'},
                            headers=self.bearer())
        self.assertEqual(r.status_code, 413)
        self.assertIsNone(self.stocat())

    def test_fara_snapshot_curent_da_409(self):
        r = self.bifeaza('A', 'livrat')
        self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
        self.assertIn('snapshot', r.get_json()['error'])
        self.assertIsNone(self.stocat())

    def test_proiect_sau_articol_necunoscut_da_409_chiar_si_la_scoatere(self):
        self.snapshot(proiect(), proiect(PID2, mat=[]))
        cazuri = [(PID, 'NU-EXISTA', 'cod_bc'), ('p-necunoscut', 'A', 'proiect_id'), (PID2, 'A', 'cod_bc')]
        for pid, cod, camp in cazuri:
            for stare in ('livrat', None):
                with self.subTest(pid=pid, cod=cod, stare=stare):
                    r = self.bifeaza(cod, stare, pid=pid)
                    self.assertEqual(r.status_code, 409, r.get_data(as_text=True))
                    self.assertIn(camp, r.get_json()['error'])
        self.assertIsNone(self.stocat())

    def test_proiect_fara_cheia_materiale_in_snapshot_da_409(self):
        p = proiect()
        del p['materiale']
        self.snapshot(p)
        self.assertEqual(self.bifeaza('A', 'livrat').status_code, 409)

    def test_cod_bc_se_potriveste_exact(self):
        self.snapshot(proiect(mat=[rand('Ab-1', 'confirmat', '2026-11-30', 'confirmat')]))
        self.assertEqual(self.bifeaza('ab-1', 'livrat').status_code, 409)
        self.assertEqual(self.bifeaza('Ab-1', 'livrat').status_code, 200)

    def test_fara_token_401_iar_masina_sesiunea_si_dispozitivul_scriu(self):
        self.snapshot()
        self.assertEqual(self.bifeaza('A', 'livrat', token=None).status_code, 401)
        self.assertEqual(self.bifeaza('A', 'livrat', token='gresit').status_code, 401)
        self.assertIsNone(self.stocat())
        self.assertEqual(self.bifeaza('A', 'livrat', token=DEVICE).status_code, 200)
        self.assertEqual(self.bifeaza('A', None, token=FULL).status_code, 200)

    def test_dispozitivul_scrie_bifa_dar_nu_snapshot_ul(self):
        self.assertFalse(device_token_denied('PUT', '/api/materiale/bifa'))
        self.assertTrue(device_token_denied('PUT', '/api/materiale'))
        r = self.client.put('/api/materiale', json=corp(proiect()), headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 401)

    def test_sesiunea_cu_csrf_scrie_iar_fara_csrf_nu(self):
        self.snapshot()
        self.assertEqual(self.login().status_code, 200)
        corp_ = {'proiect_id': PID, 'cod_bc': 'A', 'stare': 'livrat'}
        self.assertEqual(self.client.put('/api/materiale/bifa', json=corp_).status_code, 403)
        csrf = {'X-CSRF-Token': self.client.get_cookie('csrf_token').value}
        r = self.client.put('/api/materiale/bifa', json=corp_, headers=csrf)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.rand_in(self.citeste(), 'A')['stare'], 'livrat')

    def test_valoare_stricata_in_app_settings_nu_strica_nici_citirea_nici_o_bifa_noua(self):
        self.snapshot()
        self.sql("INSERT INTO app_settings (key, value, updated_at) VALUES ('materiale_bife', 'nu e json {', 'x')")
        self.assertNotIn('bifa', self.rand_in(self.citeste(), 'A'))
        self.assertEqual(self.bifeaza('A', 'livrat').status_code, 200)
        self.assertEqual(self.stocat(), {PID: {'A': {'stare': 'livrat', 'la': LA}}})


class GetCuBife(Baza):

    def test_bifa_peste_colector_schimba_starea_si_ajusteaza_rezumatul(self):
        self.snapshot()
        self.bifeaza('A', 'la_destinatie')
        j = self.citeste()
        a = self.rand_in(j, 'A')
        self.assertEqual((a['stare'], a['stare_colector'], a['intarziat']), ('la_destinatie', 'confirmat', False))
        self.assertEqual(a['bifa'], {'stare': 'la_destinatie', 'la': LA})
        rez = self.proiect_in(j)['rezumat']
        self.assertEqual(rez['pe_stare'], {'confirmat': 1, 'in_tranzit': 1, 'livrat': 1, 'la_destinatie': 2})
        self.assertEqual(rez['total'], 5)
        self.assertEqual(rez['intarziate'], 1)
        b = self.rand_in(j, 'B')
        self.assertEqual((b['stare'], b['intarziat']), ('confirmat', False))
        self.assertNotIn('bifa', b)
        self.assertNotIn('stare_colector', b)

    def test_urmatoarea_trece_la_urmatorul_rand_in_asteptare(self):
        self.snapshot()
        self.bifeaza('A', 'livrat')                  # A era „urmatoarea"
        rez = self.proiect_in(self.citeste())['rezumat']
        self.assertEqual(rez['urmatoarea'], {'data': '2026-12-05', 'tip': 'confirmat', 'stare': 'confirmat',
                                             'descriere': 'Articol B', 'cod_bc': 'B'})
        self.assertEqual(rez['ultima_asteptata'], '2026-12-05')
        self.bifeaza('B', 'la_destinatie')           # nu mai asteapta nimic
        rez = self.proiect_in(self.citeste())['rezumat']
        self.assertIsNone(rez['urmatoarea'])
        self.assertIsNone(rez['ultima_asteptata'])

    def test_urmatoarea_nu_se_schimba_cand_se_bifeaza_alt_rand(self):
        self.snapshot()
        self.bifeaza('B', 'livrat')
        rez = self.proiect_in(self.citeste())['rezumat']
        self.assertEqual(rez['urmatoarea']['cod_bc'], 'A')
        self.assertEqual(rez['ultima_asteptata'], '2026-11-30', 'ultimul rand in asteptare e acum A')

    def test_randul_intarziat_bifat_nu_mai_e_intarziat(self):
        self.snapshot()
        self.bifeaza('C', 'livrat')
        j = self.citeste()
        c = self.rand_in(j, 'C')
        self.assertEqual((c['stare'], c['stare_colector'], c['intarziat']), ('livrat', 'in_tranzit', False))
        rez = self.proiect_in(j)['rezumat']
        self.assertEqual(rez['intarziate'], 0)
        self.assertEqual(rez['pe_stare'], {'confirmat': 2, 'livrat': 2, 'la_destinatie': 1}, 'in_tranzit a ajuns la 0 si dispare')
        self.assertEqual(rez['urmatoarea']['cod_bc'], 'A')

    def test_colectorul_deja_la_nivelul_bifei_sau_peste_ramane_cum_e_dar_bifa_apare(self):
        self.snapshot()
        self.bifeaza('D', 'la_destinatie')           # colector: livrat (peste)
        self.bifeaza('E', 'la_destinatie')           # colector: la_destinatie (egal)
        j = self.citeste()
        for cod, stare in (('D', 'livrat'), ('E', 'la_destinatie')):
            r = self.rand_in(j, cod)
            self.assertEqual(r['stare'], stare)
            self.assertNotIn('stare_colector', r)
            self.assertEqual(r['bifa'], {'stare': 'la_destinatie', 'la': LA})
        self.assertEqual(self.proiect_in(j)['rezumat'], rezumat_standard(), 'rezumatul neatins')

    def test_la_destinatie_bifat_livrat_urca_un_nivel(self):
        self.snapshot()
        self.bifeaza('E', 'livrat')
        j = self.citeste()
        e = self.rand_in(j, 'E')
        self.assertEqual((e['stare'], e['stare_colector']), ('livrat', 'la_destinatie'))
        self.assertEqual(self.proiect_in(j)['rezumat']['pe_stare'],
                         {'confirmat': 2, 'in_tranzit': 1, 'livrat': 2})

    def test_scoaterea_bifei_aduce_inapoi_starea_colectorului(self):
        self.snapshot()
        inainte = self.citeste()
        self.bifeaza('A', 'livrat')
        self.bifeaza('C', 'la_destinatie')
        self.assertNotEqual(self.citeste(), inainte)
        self.bifeaza('A', None)
        self.bifeaza('C', None)
        self.assertEqual(self.citeste(), inainte)

    def test_o_stare_fara_nivel_se_ridica_la_bifa(self):
        # `partial`, `fara_ct`, `lm_in_lucru`: nu sunt in curs si nu sunt la destinatie; bifa le trece peste.
        self.snapshot(proiect(mat=[rand('P', 'partial'), rand('Q', 'fara_ct'), rand('R', None)],
                              rez={'total': 3, 'pe_stare': {'partial': 1, 'fara_ct': 1}, 'intarziate': 0, 'urmatoarea': None}))
        for cod in 'PQR':
            self.bifeaza(cod, 'la_destinatie')
        j = self.citeste()
        self.assertEqual([self.rand_in(j, c)['stare'] for c in 'PQR'], ['la_destinatie'] * 3)
        self.assertEqual([self.rand_in(j, c)['stare_colector'] for c in 'PQR'], ['partial', 'fara_ct', None])
        self.assertEqual(self.proiect_in(j)['rezumat']['pe_stare'], {'la_destinatie': 3})

    def test_fara_rezumat_randul_se_schimba_si_nimic_nu_pica(self):
        p = proiect()
        del p['rezumat']
        self.snapshot(p)
        self.bifeaza('A', 'livrat')
        j = self.citeste()
        self.assertEqual(self.rand_in(j, 'A')['stare'], 'livrat')
        self.assertNotIn('rezumat', self.proiect_in(j))

    def test_bifa_pe_un_proiect_nu_atinge_alt_proiect_cu_acelasi_cod(self):
        self.snapshot(proiect(), proiect(PID2))
        self.bifeaza('A', 'livrat')
        j = self.citeste()
        self.assertEqual(self.rand_in(j, 'A', PID2)['stare'], 'confirmat')
        self.assertNotIn('bifa', self.rand_in(j, 'A', PID2))

    def test_citirea_cu_tokenul_de_dispozitiv_vede_bifele(self):
        self.snapshot()
        self.bifeaza('A', 'livrat')
        self.assertEqual(self.rand_in(self.citeste(DEVICE), 'A')['stare'], 'livrat')

    def test_fara_snapshot_get_ramane_gol(self):
        j = self.citeste()
        self.assertEqual((j['generat'], j['proiecte']), (None, []))

    # ----------------------------------------------------------------- bifa si colectarea urmatoare

    def test_bifa_supravietuieste_unui_put_nou_al_colectorului(self):
        self.snapshot()
        self.bifeaza('A', 'la_destinatie')
        # Colectarea de dupa-amiaza: acelasi articol, cu alt termen; A tot „confirmat" la colector.
        mat = materiale_standard()
        mat[0]['termen'] = '2026-12-01'
        self.snapshot(proiect(mat=mat), generat='2026-11-25T13:02:11+02:00')
        a = self.rand_in(self.citeste(), 'A')
        self.assertEqual((a['stare'], a['stare_colector'], a['termen']), ('la_destinatie', 'confirmat', '2026-12-01'))
        self.assertEqual(a['bifa']['la'], LA)

    def test_snapshot_ul_de_pe_disc_ramane_cu_starile_colectorului(self):
        self.snapshot()
        self.bifeaza('A', 'livrat')
        self.snapshot(generat='2026-11-25T13:02:11+02:00')
        with open(os.path.join(self.dir, 'snapshot.json'), 'rb') as fh:
            scris = json.loads(fh.read().decode('utf-8'))
        a = next(m for m in scris['proiecte'][0]['materiale'] if m['cod_bc'] == 'A')
        self.assertEqual(a['stare'], 'confirmat')
        self.assertNotIn('bifa', a)
        self.assertEqual(scris['proiecte'][0]['rezumat'], rezumat_standard())

    def test_randul_iesit_din_snapshot_nu_se_arata_dar_bifa_ramane_stocata_si_revine_cu_el(self):
        self.snapshot()
        self.bifeaza('B', 'livrat')
        fara_b = [m for m in materiale_standard() if m['cod_bc'] != 'B']
        self.snapshot(proiect(mat=fara_b), generat='2026-11-25T13:02:11+02:00')
        j = self.citeste()
        self.assertEqual([m['cod_bc'] for m in self.proiect_in(j)['materiale']], ['A', 'C', 'D', 'E'])
        self.assertTrue(all('bifa' not in m for m in self.proiect_in(j)['materiale']))
        self.assertEqual(self.stocat(), {PID: {'B': {'stare': 'livrat', 'la': LA}}})
        self.snapshot(generat='2026-11-25T16:02:11+02:00')
        self.assertEqual(self.rand_in(self.citeste(), 'B')['stare'], 'livrat')

    def test_bifa_pentru_un_proiect_care_nu_mai_e_in_snapshot_nu_strica_nimic(self):
        self.snapshot(proiect(), proiect(PID2))
        self.bifeaza('A', 'livrat', pid=PID2)
        self.snapshot(generat='2026-11-25T13:02:11+02:00')       # doar PID
        j = self.citeste()
        self.assertEqual([p['proiect_id'] for p in j['proiecte']], [PID])
        self.assertEqual(self.rand_in(j, 'A')['stare'], 'confirmat')

    # ----------------------------------------------------------------- backup si restore

    def test_cheia_intra_in_backup_si_restore_o_aduce_inapoi(self):
        self.snapshot()
        self.bifeaza('A', 'livrat')
        r = self.client.get('/api/backup', headers=self.bearer())
        self.assertEqual(r.status_code, 200)
        backup = r.get_json()
        randuri = [s for s in backup['app_settings'] if s['key'] == 'materiale_bife']
        self.assertEqual([json.loads(s['value']) for s in randuri], [{PID: {'A': {'stare': 'livrat', 'la': LA}}}])
        self.bifeaza('A', None)                                    # bifa dispare, ca dupa un dezastru
        self.sql("DELETE FROM app_settings WHERE key = 'materiale_bife'")
        self.assertEqual(self.rand_in(self.citeste(), 'A')['stare'], 'confirmat')
        r = self.client.post('/api/restore', json=backup, headers=self.bearer())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.rand_in(self.citeste(), 'A')['stare'], 'livrat')
        self.assertEqual(self.stocat(), {PID: {'A': {'stare': 'livrat', 'la': LA}}})


class AlerteDeLivrare(Baza):
    """Cu `sursa.alerte = "server"`, un articol bifat nu mai da alerta de livrare fata de start."""

    def setUp(self):
        super().setUp()
        self.patch(materiale, '_acum', lambda: datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc))
        self.sql('DELETE FROM tasks')
        self.sql('DELETE FROM implementari')
        self.sql('DELETE FROM proiecte')
        self.sql("INSERT INTO proiecte (id, tip, nume, status) VALUES (?, 'PIF', 'VLG', 'pregatire')", PID)
        self.sql("INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit) VALUES ('in-curs', ?, '2026-11-16', '2026-11-18')", PID)

    def corp_server(self):
        mat = [rand('A', 'confirmat', '2026-11-20', 'confirmat', descriere='Vine dupa'),
               rand('B', 'confirmat', '2026-11-25', 'confirmat', descriere='Vine dupa si el')]
        return corp(proiect(mat=mat, rez={'total': 2, 'pe_stare': {'confirmat': 2}, 'intarziate': 0}),
                    generat='2026-11-17T08:02:11+02:00', alerte='server', utilizator='ion')

    def pune(self):
        r = self.client.put('/api/materiale', json=self.corp_server(), headers=self.bearer())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def alerte_livrare(self):
        p = self.proiect_in(self.citeste())
        return [a for a in p['alerte'] if a['tip'].startswith('livrare_')]

    def test_fara_bifa_ambele_articole_dau_alerta(self):
        self.assertEqual(self.pune()['alerte'], 1)
        self.assertEqual(self.alerte_livrare()[0]['n'], 2)

    def test_un_articol_bifat_iese_din_alerta_la_urmatoarea_colectare(self):
        self.pune()
        self.assertEqual(self.bifeaza('A', 'la_destinatie').status_code, 200)
        self.pune()                                                  # colectorul trimite din nou, A tot „confirmat"
        a = self.alerte_livrare()
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]['n'], 1)
        self.assertIn('Vine dupa si el', a[0]['text'])
        self.assertNotIn('Vine dupa (', a[0]['text'])
        j = self.citeste()
        self.assertEqual(self.rand_in(j, 'A')['fata_de_start'], None)
        self.assertEqual(self.rand_in(j, 'B')['fata_de_start'], 'dupa')
        self.assertEqual(self.proiect_in(j)['rezumat']['dupa_start'], 1)

    def test_toate_bifate_nu_mai_ramane_nicio_alerta_de_livrare(self):
        self.pune()
        self.bifeaza('A', 'livrat')
        self.bifeaza('B', 'la_destinatie')
        raspuns = self.pune()
        self.assertEqual(raspuns['alerte'], 0)
        self.assertEqual(self.alerte_livrare(), [])
        self.assertEqual(self.proiect_in(self.citeste())['rezumat']['dupa_start'], 0)

    def test_dupa_scoaterea_bifei_alerta_revine(self):
        self.pune()
        self.bifeaza('A', 'livrat')
        self.bifeaza('B', 'livrat')
        self.pune()
        self.bifeaza('A', None)
        self.pune()
        self.assertEqual(self.alerte_livrare()[0]['n'], 1)

    def test_get_dupa_bifa_arata_deja_randul_scos_din_marcajul_de_start(self):
        # Alerta din `alerte[]` se reface la colectarea urmatoare; marcajul de pe rand si numaratoarea, imediat.
        self.pune()
        self.bifeaza('A', 'livrat')
        j = self.citeste()
        self.assertIsNone(self.rand_in(j, 'A')['fata_de_start'])
        self.assertEqual(self.proiect_in(j)['rezumat']['dupa_start'], 1)

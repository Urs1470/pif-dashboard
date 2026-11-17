"""Alertele materialelor calculate pe server (`blueprints/materiale_alerte.py`, din 2026-11-17).

Ce se pazeste, tacut daca se strica:
  - regulile sunt cele ale colectorului (Knowledge `tools/materiale-colector.ps1`): comanda pe mail fara LM, CT fara
    LM, contract fara linii de pontaj, livrari dupa / aproape de startul perioadei; cu cazurile care le acopera;
  - zilele lucratoare sar weekendul; „azi" e ziua din `generat`, nu ceasul serverului;
  - id-ul taskului e cel al colectorului (SHA-1 pe nume, forma UUID), deci un task creat de PC nu se dubleaza;
  - la PUT: cu `sursa.alerte = "server"` serverul scrie alertele in snapshot si creeaza taskurile o singura data;
    fara flag, alertele trimise raman neatinse si nu se creeaza niciun task (colectorul vechi);
  - perioada vine din `implementari`: urmatoarea care n-a trecut, inclusiv una in curs.
"""

import os
import sqlite3
from datetime import date, datetime, timezone

from _aplicatia import FULL, CuAplicatia
from _baza import Test
from blueprints import materiale, materiale_alerte as ma

PID = 'p-26-287'
ME = 'ELECTROGLOBAL\\ion.ursu'
AZI = date(2026, 11, 17)                     # marti


def mail(data, fir, ct=(), comanda=True, entry='E' * 24, subiect=None):
    return {'data': data, 'de_la': 'Ion Ursu', 'subiect': subiect or fir, 'tip': 'comanda_mail', 'ct': list(ct),
            'lm': None, 'entry_id': entry, 'trimis_de_mine': True, 'comanda_mea': comanda, 'fir': fir}


def proiect(**sectiuni):
    p = {'proiect_id': PID, 'cod_proiect': '26_287', 'rezumat': {'total': 0}, 'materiale': [], 'lm': [], 'termene': [],
         'necomandate': [], 'mailuri': [], 'alerte': []}
    p.update(sectiuni)
    return p


def tipuri(alerte):
    return [a['tip'] for a in alerte]


class Reguli(Test):

    def test_zile_lucratoare_sar_weekendul(self):
        self.assertEqual(ma.zile_lucratoare_dupa(date(2026, 11, 13), date(2026, 11, 16)), 1)   # vineri -> luni
        self.assertEqual(ma.zile_lucratoare_dupa(date(2026, 11, 9), AZI), 6)
        self.assertEqual(ma.zile_lucratoare_dupa(AZI, AZI), 0)

    def test_id_stabil_e_cel_al_colectorului(self):
        # calculat cu New-StableId din materiale-colector.ps1 pe 2026-11-17
        nume = ('14f75451-f3f7-4319-b352-b30856fa859e|comanda_fara_lm|000000002EF00F88527AB540B4BCAD953BEDD3BD070085CD'
                'A8DC5B097842820E1274CC4C6849000000000109000085CDA8DC5B097842820E1274CC4C68490001313C9A0A0000')
        self.assertEqual(ma.id_stabil(nume), '4d481d15-eca8-57d3-ad49-da91ce25ae20')

    def test_comanda_fara_lm_dupa_doua_zile(self):
        p = proiect(mailuri=[mail('2026-11-09T10:12:00', 'Comanda 26_287', subiect='26_287 livrare')])
        a = ma.alerte_proiect(p, AZI, ME, None)
        self.assertEqual(tipuri(a), ['comanda_fara_lm'])
        self.assertEqual(a[0]['text'], 'Comanda pe mail din 09.11.2026 („26_287 livrare”) nu are LM în E100 după '
                                       '6 zile lucrătoare')
        self.assertEqual(a[0]['din'], '2026-11-09')

    def test_comanda_de_ieri_nu_e_inca_alerta(self):
        p = proiect(mailuri=[mail('2026-11-16T10:00:00', 'Comanda')])
        self.assertEqual(ma.alerte_proiect(p, AZI, ME, None), [])

    def test_comanda_acoperita_de_lm_creat_de_ion(self):
        lm = [{'nr': 3, 'creat': '2026-11-10', 'creat_de': 'electroglobal\\ION.URSU'}]
        p = proiect(mailuri=[mail('2026-11-09T10:00:00', 'Comanda')], lm=lm)
        self.assertEqual(ma.alerte_proiect(p, AZI, ME, None), [])
        lm_altcuiva = [{'nr': 3, 'creat': '2026-11-10', 'creat_de': 'ELECTROGLOBAL\\altcineva'}]
        self.assertEqual(tipuri(ma.alerte_proiect(proiect(mailuri=[mail('2026-11-09T10:00:00', 'Comanda')], lm=lm_altcuiva),
                                                  AZI, ME, None)), ['comanda_fara_lm'])
        lm_dinainte = [{'nr': 3, 'creat': '2026-11-06', 'creat_de': ME}]
        self.assertEqual(tipuri(ma.alerte_proiect(proiect(mailuri=[mail('2026-11-09T10:00:00', 'Comanda')], lm=lm_dinainte),
                                                  AZI, ME, None)), ['comanda_fara_lm'])

    def test_comanda_acoperita_de_ct_cu_lm_pe_fir(self):
        m1 = mail('2026-11-09T10:00:00', 'Comanda')
        m2 = mail('2026-11-10T09:00:00', 'Comanda', ct=['CT26000001'], comanda=False)
        termene = [{'ct': 'CT26000001', 'lm': 3}]
        self.assertEqual(ma.alerte_proiect(proiect(mailuri=[m1, m2], termene=termene), AZI, ME, None), [])
        fara_lm = [{'ct': 'CT26000001', 'lm': None}]
        a = ma.alerte_proiect(proiect(mailuri=[m1, m2], termene=fara_lm), AZI, ME, None)
        self.assertEqual(tipuri(a), ['comanda_fara_lm'], 'CT-ul firului fara LM nu acopera; nici ct_fara_lm separat')
        self.assertTrue(a[0]['text'].endswith('(pe fir: CT26000001)'))

    def test_comanda_cu_ct_iesit_din_bc_e_incheiata(self):
        m1 = mail('2026-11-09T10:00:00', 'Comanda', ct=['CT26000009'])
        self.assertEqual(ma.alerte_proiect(proiect(mailuri=[m1]), AZI, ME, None), [])

    def test_ct_fara_lm_cu_achizitor_si_dupa_doua_zile(self):
        nec = [{'ct': 'CT26003872', 'lm': None, 'data_creare_ct': '2026-11-06', 'achizitor': 'Oana Giuglea'},
               {'ct': 'CT26003872', 'lm': None, 'data_creare_ct': '2026-11-06', 'achizitor': 'Oana Giuglea'},
               {'ct': 'CT26009999', 'lm': None, 'data_creare_ct': '2026-11-16', 'achizitor': 'X'},
               {'ct': '(fara CT)', 'lm': None}]
        a = ma.alerte_proiect(proiect(necomandate=nec), AZI, ME, None)
        self.assertEqual([(x['tip'], x['ref']) for x in a], [('ct_fara_lm', 'CT26003872')])
        self.assertEqual(a[0]['text'], 'CT26003872 nu e alocat pe niciun LM în BC (creat 06.11.2026, achizitor Oana Giuglea)')

    def test_fara_linii_pontaj(self):
        p = proiect(contract_data='2026-11-12', linii_contract=0)
        a = ma.alerte_proiect(p, AZI, ME, None)
        self.assertEqual(tipuri(a), ['fara_linii_pontaj'])
        self.assertEqual(a[0]['text'], 'Proiectul 26_287 are contract în E100 din 12.11.2026, dar nicio linie de pontaj deschisă')
        self.assertEqual(ma.alerte_proiect(proiect(contract_data='2026-11-12', linii_contract=2), AZI, ME, None), [])
        self.assertEqual(ma.alerte_proiect(proiect(contract_data='2026-11-16', linii_contract=0), AZI, ME, None), [])
        self.assertEqual(ma.alerte_proiect(proiect(linii_contract=0), AZI, ME, None), [], 'fara contract, fara alerta')

    def test_livrari_fata_de_start_si_marcajele(self):
        mat = [{'cod_bc': 'A', 'descriere': 'Dupa', 'termen': '2026-11-30', 'termen_tip': 'confirmat'},
               {'cod_bc': 'B', 'descriere': 'Aproape', 'termen': '2026-11-25', 'termen_tip': 'planificat'},
               {'cod_bc': 'C', 'descriere': 'Devreme', 'termen': '2026-11-10', 'termen_tip': 'confirmat'},
               {'cod_bc': 'D', 'descriere': 'Livrat', 'termen': '2026-11-30', 'termen_tip': 'livrat'}]
        per = {'id': 'per1', 'data_start': '2026-11-28', 'data_sfarsit': '2026-11-29', 'faza': 'implementare'}
        p = proiect(materiale=mat)
        a = ma.alerte_proiect(p, AZI, ME, per)
        self.assertEqual(tipuri(a), ['livrare_dupa_start', 'livrare_aproape_start'])
        self.assertEqual(a[0]['text'], 'Perioada planificată începe pe 28.11, iar 1 materiale vin după start: Dupa (30.11 confirmat)')
        self.assertEqual(a[1]['ref'], 'perioada|per1|2026-11-28')
        self.assertEqual([m['fata_de_start'] for m in mat], ['dupa', 'aproape', None, None])
        self.assertEqual(p['rezumat']['perioada'], per)
        self.assertEqual((p['rezumat']['dupa_start'], p['rezumat']['aproape_start']), (1, 1))

    def test_fara_perioada_fara_marcaje(self):
        mat = [{'cod_bc': 'A', 'termen': '2026-11-30', 'termen_tip': 'confirmat'}]
        p = proiect(materiale=mat)
        self.assertEqual(ma.alerte_proiect(p, AZI, ME, None), [])
        self.assertNotIn('fata_de_start', mat[0])
        self.assertIsNone(p['rezumat']['perioada'])

    def test_lista_de_livrari_se_taie_la_cinci(self):
        mat = [{'cod_bc': str(i), 'descriere': 'M%d' % i, 'termen': '2026-12-%02d' % (i + 1), 'termen_tip': 'confirmat'}
               for i in range(7)]
        a = ma.alerte_proiect(proiect(materiale=mat), AZI, ME, {'id': 'x', 'data_start': '2026-11-28'})
        self.assertTrue(a[0]['text'].endswith('M4 (05.12 confirmat); încă 2'), a[0]['text'])

    def test_taskul_alertei(self):
        p = proiect()
        a = {'tip': 'livrare_aproape_start', 'din': '2026-11-20', 'ref': 'perioada|x|2026-11-20', 'text': 'T'}
        t = ma.task_pentru(p, a, AZI)
        self.assertEqual(t['titlu'], 'Materiale cu cel mult o săptămână înainte de startul din 20.11 (26_287)')
        self.assertEqual(t['data_scadenta'], '2026-11-17', 'scadenta: o saptamana inainte de start, dar nu in trecut')
        c = ma.task_pentru(p, {'tip': 'comanda_fara_lm', 'din': '2026-11-09', 'ref': 'E1', 'text': 'T', 'entry_id': 'ABCDEF' * 4,
                               'subiect': 'S'}, AZI)
        self.assertIn('Din mail: [„S”](outlook:' + 'ABCDEF' * 4 + ')', c['descriere'])
        self.assertIsNone(c['data_scadenta'])


class LaPut(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.patch(materiale, 'DIR_MATERIALE', os.path.join(self.dir_temp(), 'materiale'))
        self.patch(materiale, '_acum', lambda: datetime(2026, 11, 17, 8, 0, tzinfo=timezone.utc))
        with sqlite3.connect(self.db) as c:
            c.execute('DELETE FROM tasks')
            c.execute('DELETE FROM implementari')
            c.execute('DELETE FROM proiecte')
            c.execute("INSERT INTO proiecte (id, tip, nume, status) VALUES (?, 'PIF', 'VLG', 'pregatire')", (PID,))
            c.execute("INSERT INTO implementari (id, proiect_id, data_start, data_sfarsit) VALUES "
                      "('trecuta', ?, '2026-11-02', '2026-11-03'), ('in-curs', ?, '2026-11-16', '2026-11-18'), "
                      "('viitoare', ?, '2026-12-01', '')", (PID, PID, PID))

    def corp(self, server=True, **kw):
        sursa = {'bc': 'BC', 'mail': 'Outlook'}
        if server:
            sursa.update(alerte='server', utilizator=ME)
        mat = [{'cod_bc': 'A', 'descriere': 'Vine dupa', 'termen': '2026-11-20', 'termen_tip': 'confirmat'}]
        return {'generat': '2026-11-17T08:02:11+02:00', 'sursa': sursa,
                'proiecte': [proiect(mailuri=[mail('2026-11-09T10:00:00', 'Comanda')], materiale=mat, **kw)]}

    def pune(self, corp):
        return self.client.put('/api/materiale', json=corp, headers=self.bearer(FULL))

    def taskuri(self):
        with sqlite3.connect(self.db) as c:
            return c.execute('SELECT id, titlu, status, data_scadenta FROM tasks ORDER BY ordine').fetchall()

    def test_cu_flag_calculeaza_scrie_si_creeaza_taskurile_o_data(self):
        r = self.pune(self.corp())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        j = r.get_json()
        self.assertEqual(j['alerte'], 2)
        self.assertEqual(j['taskuri'], {'noi': 2, 'existente': 0, 'sarite': 0})
        t = self.taskuri()
        self.assertEqual([x[2] for x in t], ['to_do', 'to_do'])
        self.assertTrue(t[1][1].startswith('Materiale care vin după startul din 16.11'), t)
        p = self.client.get('/api/materiale', headers=self.bearer(FULL)).get_json()['proiecte'][0]
        self.assertEqual(tipuri(p['alerte']), ['comanda_fara_lm', 'livrare_dupa_start'])
        self.assertEqual(p['rezumat']['perioada']['id'], 'in-curs', 'perioada in curs, nu cea trecuta')
        self.assertEqual(p['materiale'][0]['fata_de_start'], 'dupa')
        r2 = self.pune(self.corp())
        self.assertEqual(r2.get_json()['taskuri'], {'noi': 0, 'existente': 2, 'sarite': 0})
        self.assertEqual(len(self.taskuri()), 2)

    def test_taskul_creat_inainte_de_colector_nu_se_dubleaza(self):
        tid = ma.id_stabil('%s|comanda_fara_lm|%s' % (PID, 'E' * 24))
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO tasks (id, proiect_id, titlu, status) VALUES (?, ?, 'creat de PC', 'done')", (tid, PID))
        j = self.pune(self.corp()).get_json()
        self.assertEqual(j['taskuri'], {'noi': 1, 'existente': 1, 'sarite': 0})
        self.assertIn((tid, 'creat de PC', 'done'), [x[:3] for x in self.taskuri()], 'bifat de Ion: ramane bifat')

    def test_fara_flag_pastreaza_alertele_trimise_si_nu_creeaza_taskuri(self):
        corp = self.corp(server=False, alerte=[{'tip': 'comanda_fara_lm', 'text': 'trimisa de PC', 'din': '2026-11-09', 'ref': 'E1'}])
        j = self.pune(corp).get_json()
        self.assertNotIn('taskuri', j)
        self.assertEqual(self.taskuri(), [])
        p = self.client.get('/api/materiale', headers=self.bearer(FULL)).get_json()['proiecte'][0]
        self.assertEqual([a['text'] for a in p['alerte']], ['trimisa de PC'])
        self.assertNotIn('fata_de_start', p['materiale'][0])

    def test_proiect_sters_se_sare(self):
        corp = self.corp()
        corp['proiecte'][0]['proiect_id'] = 'p-sters'
        j = self.pune(corp).get_json()
        # proiectul sters n-are perioade, deci doar comanda pe mail: o alerta, al carei task se sare
        self.assertEqual(j['taskuri'], {'noi': 0, 'existente': 0, 'sarite': 1})
        self.assertEqual(self.taskuri(), [])

    def test_azi_e_ziua_din_generat(self):
        corp = self.corp()
        corp['generat'] = '2026-11-10T08:00:00+02:00'          # o zi lucratoare dupa comanda din 09.11
        j = self.pune(corp).get_json()
        self.assertEqual(j['alerte'], 1, 'doar livrarea; comanda nu are inca 2 zile lucratoare')

"""Etapa 3 din Torqa (schema v44): taskuri ancorate de perioada, recurenta de la finalizare,
sabloane de lucrare si starea proiectului. Rutele, prin clientul de test.

Zilele de mai jos sunt fixe si verificate in calendar: 2026-10-12 si 2026-10-19 sunt luni,
2026-10-14 miercuri, 2026-10-16 vineri, 2026-10-17 sambata.
"""

import sqlite3
from datetime import date

from _aplicatia import CuAplicatia, DEVICE


class Baza(CuAplicatia):
    """Scurtaturi peste API; fiecare test isi face proiectul lui (baza e comuna clasei)."""

    def api(self, metoda, url, corp=None, token=None):
        r = getattr(self.client, metoda)(url, json=corp, headers=self.bearer(token) if token else self.bearer())
        return r

    def proiect(self, **extra):
        r = self.api('post', '/api/proiecte', {'nume': 'Proiect', 'tip': 'PIF', **extra})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def perioada(self, pid, start='2026-10-12', **extra):
        r = self.api('post', '/api/proiecte/%s/implementari' % pid, {'data_start': start, **extra})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def task(self, pid, **corp):
        r = self.api('post', '/api/proiecte/%s/tasks' % pid, {'titlu': 'T', **corp})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def taskuri(self, pid):
        r = self.api('get', '/api/proiecte/%s/tasks' % pid)
        return {t['id']: t for t in r.get_json()}

    def sql(self, interogare, *param):
        import database
        c = sqlite3.connect(database.DATABASE_PATH)
        try:
            return c.execute(interogare, param).fetchall()
        finally:
            c.close()


# ---------------------------------------------------------------------------------- L1: ancore

class Ancore(Baza):

    def test_mutarea_perioadei_muta_taskurile_ancorate_nefacute(self):
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        zero = self.task(pid, implementare_id=iid, decalaj_zile=0)
        plus_cinci = self.task(pid, implementare_id=iid, decalaj_zile=5)
        minus_doi = self.task(pid, implementare_id=iid, decalaj_zile=-2)
        facut = self.task(pid, implementare_id=iid, decalaj_zile=1)
        liber = self.task(pid, data_scadenta='2026-10-13')
        self.api('put', '/api/tasks/%s' % facut, {'status': 'done', 'implementare_id': iid, 'decalaj_zile': 1})
        inainte = self.taskuri(pid)
        self.assertEqual(inainte[plus_cinci]['data_scadenta'], '2026-10-17')

        r = self.api('put', '/api/implementari/%s' % iid, {'data_start': '2026-10-19'})
        self.assertEqual(r.status_code, 200)

        dupa = self.taskuri(pid)
        self.assertEqual(dupa[zero]['data_scadenta'], '2026-10-19')
        # Zile calendaristice, fara ajustare de weekend: 19 + 5 = sambata 24, 19 - 2 = sambata 17.
        self.assertEqual(dupa[plus_cinci]['data_scadenta'], '2026-10-24')
        self.assertEqual(dupa[minus_doi]['data_scadenta'], '2026-10-17')
        # Ancora ramane, cu acelasi decalaj.
        self.assertEqual((dupa[plus_cinci]['implementare_id'], dupa[plus_cinci]['decalaj_zile']), (iid, 5))
        # Nu se muta: taskul facut, cel neancorat.
        self.assertEqual(dupa[facut]['data_scadenta'], inainte[facut]['data_scadenta'])
        self.assertEqual(dupa[facut]['updated_at'], inainte[facut]['updated_at'])
        self.assertEqual(dupa[liber]['data_scadenta'], '2026-10-13')
        self.assertEqual(dupa[liber]['updated_at'], inainte[liber]['updated_at'])
        # Cele mutate au `updated_at` nou: Torqa le trage din imagine dupa el.
        for t in (zero, plus_cinci, minus_doi):
            self.assertGreater(dupa[t]['updated_at'], inainte[t]['updated_at'], t)

    def test_perioada_mutata_nu_atinge_taskurile_altei_perioade(self):
        pid = self.proiect()
        prima, a_doua = self.perioada(pid, '2026-10-12'), self.perioada(pid, '2026-11-02')
        t1 = self.task(pid, implementare_id=prima, decalaj_zile=1)
        t2 = self.task(pid, implementare_id=a_doua, decalaj_zile=1)
        self.api('put', '/api/implementari/%s' % prima, {'data_start': '2026-10-13'})
        taskuri = self.taskuri(pid)
        self.assertEqual((taskuri[t1]['data_scadenta'], taskuri[t2]['data_scadenta']),
                         ('2026-10-14', '2026-11-03'))

    def test_alte_campuri_ale_perioadei_nu_muta_nimic(self):
        pid = self.proiect()
        iid = self.perioada(pid)
        t = self.task(pid, implementare_id=iid, decalaj_zile=2)
        inainte = self.taskuri(pid)[t]
        self.api('put', '/api/implementari/%s' % iid, {'eticheta': 'Montaj', 'data_sfarsit': '2026-10-16'})
        self.assertEqual(self.taskuri(pid)[t], inainte)
        # Acelasi start trimis din nou: nici asta nu muta nimic.
        self.api('put', '/api/implementari/%s' % iid, {'data_start': '2026-10-12'})
        self.assertEqual(self.taskuri(pid)[t], inainte)

    def test_start_gol_nu_muta_taskuri(self):
        pid = self.proiect()
        iid = self.perioada(pid)
        t = self.task(pid, implementare_id=iid, decalaj_zile=2)
        inainte = self.taskuri(pid)[t]
        r = self.api('put', '/api/implementari/%s' % iid, {'data_start': ''})
        self.assertEqual(r.status_code, 200)
        # Comportamentul de dinainte ramane: '' suprascrie startul. Taskul nu se misca.
        self.assertEqual(self.sql('SELECT data_start FROM implementari WHERE id = ?', iid), [('',)])
        self.assertEqual(self.taskuri(pid)[t], inainte)

    def test_perioada_inexistenta_ramane_404(self):
        self.assertEqual(self.api('put', '/api/implementari/nu-exista', {'data_start': '2026-10-19'}).status_code, 404)

    def test_ancorare_la_creare_calculeaza_termenul_si_ignora_data_trimisa(self):
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        t = self.task(pid, implementare_id=iid, decalaj_zile=3, data_scadenta='2000-01-01')
        rand = self.taskuri(pid)[t]
        self.assertEqual((rand['data_scadenta'], rand['implementare_id'], rand['decalaj_zile']),
                         ('2026-10-15', iid, 3))

    def test_ancorare_explicita_prin_put(self):
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        t = self.task(pid, data_scadenta='2026-10-01')
        r = self.api('put', '/api/tasks/%s' % t, {'implementare_id': iid, 'decalaj_zile': -1,
                                                  'data_scadenta': '2000-01-01'})
        self.assertEqual(r.status_code, 200)
        rand = self.taskuri(pid)[t]
        self.assertEqual((rand['data_scadenta'], rand['implementare_id'], rand['decalaj_zile']),
                         ('2026-10-11', iid, -1))

    def test_perioada_din_alt_proiect_sau_inexistenta_da_400(self):
        pid, altul = self.proiect(), self.proiect()
        strain = self.perioada(altul)
        t = self.task(pid)
        for impl in (strain, 'nu-exista'):
            r = self.api('post', '/api/proiecte/%s/tasks' % pid,
                         {'titlu': 'X', 'implementare_id': impl, 'decalaj_zile': 0})
            self.assertEqual(r.status_code, 400, impl)
            r = self.api('put', '/api/tasks/%s' % t, {'implementare_id': impl, 'decalaj_zile': 0})
            self.assertEqual(r.status_code, 400, impl)
        rand = self.taskuri(pid)[t]
        self.assertEqual((rand['implementare_id'], rand['decalaj_zile']), (None, None))
        self.assertEqual(len(self.taskuri(pid)), 1, 'un 400 nu lasa un task pe jumatate')

    def test_ancora_fara_decalaj_intreg_sau_fara_start_da_400(self):
        pid = self.proiect()
        iid = self.perioada(pid)
        fara_start = self.perioada(pid, '')
        t = self.task(pid)
        for corp in ({'implementare_id': iid},
                     {'implementare_id': iid, 'decalaj_zile': '3'},
                     {'implementare_id': iid, 'decalaj_zile': 1.5},
                     {'implementare_id': iid, 'decalaj_zile': True},
                     {'implementare_id': iid, 'decalaj_zile': 10 ** 9},
                     {'implementare_id': fara_start, 'decalaj_zile': 1}):
            r = self.api('put', '/api/tasks/%s' % t, corp)
            self.assertEqual(r.status_code, 400, corp)

    def test_schimbarea_termenului_desprinde_ancora(self):
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        t = self.task(pid, implementare_id=iid, decalaj_zile=2)
        r = self.api('put', '/api/tasks/%s' % t, {'data_scadenta': '2026-10-30'})
        self.assertEqual(r.status_code, 200)
        rand = self.taskuri(pid)[t]
        self.assertEqual((rand['data_scadenta'], rand['implementare_id'], rand['decalaj_zile']),
                         ('2026-10-30', None, None))
        # Desprins, nu mai merge dupa perioada.
        self.api('put', '/api/implementari/%s' % iid, {'data_start': '2026-11-02'})
        self.assertEqual(self.taskuri(pid)[t]['data_scadenta'], '2026-10-30')

    def test_golirea_termenului_desprinde_si_ea(self):
        pid = self.proiect()
        iid = self.perioada(pid)
        t = self.task(pid, implementare_id=iid, decalaj_zile=2)
        self.api('put', '/api/tasks/%s' % t, {'data_scadenta': ''})
        rand = self.taskuri(pid)[t]
        self.assertEqual((rand['data_scadenta'], rand['implementare_id']), ('', None))

    def test_alte_schimbari_si_acelasi_termen_pastreaza_ancora(self):
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        t = self.task(pid, implementare_id=iid, decalaj_zile=2)
        # Torqa poate trimite tot taskul, cu termenul neschimbat: nu e o schimbare de termen.
        r = self.api('put', '/api/tasks/%s' % t, {'titlu': 'Nou', 'data_scadenta': '2026-10-14', 'descriere': 'd'})
        self.assertEqual(r.status_code, 200)
        rand = self.taskuri(pid)[t]
        self.assertEqual((rand['titlu'], rand['implementare_id'], rand['decalaj_zile']), ('Nou', iid, 2))

    def test_implementare_id_null_sau_gol_desprinde_fara_sa_atinga_termenul(self):
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        for gol in (None, ''):
            t = self.task(pid, implementare_id=iid, decalaj_zile=2)
            r = self.api('put', '/api/tasks/%s' % t, {'implementare_id': gol})
            self.assertEqual(r.status_code, 200)
            rand = self.taskuri(pid)[t]
            self.assertEqual((rand['data_scadenta'], rand['implementare_id'], rand['decalaj_zile']),
                             ('2026-10-14', None, None), repr(gol))

    def test_stergerea_perioadei_goleste_ancora_si_pastreaza_taskul(self):
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        t = self.task(pid, implementare_id=iid, decalaj_zile=2)
        self.assertEqual(self.api('delete', '/api/implementari/%s' % iid).status_code, 200)
        rand = self.taskuri(pid)[t]
        self.assertEqual((rand['data_scadenta'], rand['implementare_id'], rand['decalaj_zile']),
                         ('2026-10-14', None, None))

    def test_cheia_straina_goleste_implementare_id_si_la_o_stergere_directa(self):
        # Plasa de siguranta a cheii straine, fara ruta: `ON DELETE SET NULL`.
        import database
        pid = self.proiect()
        iid = self.perioada(pid)
        t = self.task(pid, implementare_id=iid, decalaj_zile=2)
        c = database.get_db()
        c.execute('DELETE FROM implementari WHERE id = ?', (iid,))
        c.commit()
        c.close()
        self.assertEqual(self.taskuri(pid)[t]['implementare_id'], None)

    def test_stergerea_proiectului_sterge_perioada_si_taskurile_ei(self):
        pid = self.proiect()
        iid = self.perioada(pid)
        self.task(pid, implementare_id=iid, decalaj_zile=2)
        self.assertEqual(self.api('delete', '/api/proiecte/%s' % pid).status_code, 200)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM tasks WHERE proiect_id = ?', pid), [(0,)])


# --------------------------------------------------------------------- L6: recurenta de la finalizare

class Recurenta(Baza):

    def azi(self, an, luna, zi):
        from blueprints import tasks
        self.patch(tasks, '_azi', lambda: date(an, luna, zi))

    def bifeaza(self, pid, tid):
        r = self.api('put', '/api/tasks/%s' % tid, {'status': 'done'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def test_de_la_finalizare_numara_de_azi_nu_de_la_termen(self):
        self.azi(2026, 10, 14)                      # miercuri
        pid = self.proiect()
        de_la_termen = self.task(pid, data_scadenta='2026-10-01', recurenta='zilnic')
        de_la_final = self.task(pid, data_scadenta='2026-10-01', recurenta='zilnic', recurenta_baza='finalizare')
        r1, r2 = self.bifeaza(pid, de_la_termen), self.bifeaza(pid, de_la_final)
        taskuri = self.taskuri(pid)
        self.assertEqual(r1['recurring_next'], '2026-10-02')
        self.assertEqual(taskuri[r1['recurring_spawned']]['data_scadenta'], '2026-10-02')
        self.assertEqual(r2['recurring_next'], '2026-10-15')
        self.assertEqual(taskuri[r2['recurring_spawned']]['data_scadenta'], '2026-10-15')

    def test_de_la_finalizare_sare_weekendul(self):
        self.azi(2026, 10, 16)                      # vineri: zilnic -> sambata -> luni
        pid = self.proiect()
        t = self.task(pid, data_scadenta='2026-10-01', recurenta='zilnic', recurenta_baza='finalizare')
        nou = self.bifeaza(pid, t)['recurring_spawned']
        self.assertEqual(self.taskuri(pid)[nou]['data_scadenta'], '2026-10-19')

    def test_de_la_finalizare_saptamanal_si_lunar(self):
        self.azi(2026, 10, 14)
        pid = self.proiect()
        sapt = self.task(pid, recurenta='saptamanal', recurenta_baza='finalizare')    # fara termen
        lunar = self.task(pid, data_scadenta='2026-01-31', recurenta='lunar', recurenta_baza='finalizare')
        sapt_nou = self.bifeaza(pid, sapt)['recurring_spawned']
        lunar_nou = self.bifeaza(pid, lunar)['recurring_spawned']
        taskuri = self.taskuri(pid)
        self.assertEqual(taskuri[sapt_nou]['data_scadenta'], '2026-10-21')
        self.assertEqual(taskuri[lunar_nou]['data_scadenta'], '2026-11-16')   # 14 nov e sambata -> luni 16

    def test_copia_pastreaza_baza_si_nu_mosteneste_ancora(self):
        self.azi(2026, 10, 14)
        pid = self.proiect()
        iid = self.perioada(pid, '2026-10-12')
        t = self.task(pid, implementare_id=iid, decalaj_zile=1, recurenta='zilnic', recurenta_baza='finalizare')
        nou_id = self.bifeaza(pid, t)['recurring_spawned']
        nou = self.taskuri(pid)[nou_id]
        self.assertEqual(nou['recurenta_baza'], 'finalizare')
        self.assertEqual(nou['recurenta'], 'zilnic')
        self.assertEqual((nou['implementare_id'], nou['decalaj_zile']), (None, None))
        # Originalul bifat isi pastreaza ancora (istoric), iar mutarea perioadei nu atinge copia.
        vechi = self.taskuri(pid)[t]
        self.assertEqual((vechi['implementare_id'], vechi['decalaj_zile']), (iid, 1))
        self.api('put', '/api/implementari/%s' % iid, {'data_start': '2026-11-02'})
        self.assertEqual(self.taskuri(pid)[nou['id']]['data_scadenta'], nou['data_scadenta'])

    def test_baza_implicita_e_scadenta_si_se_poate_schimba(self):
        pid = self.proiect()
        t = self.task(pid, recurenta='lunar')
        self.assertEqual(self.taskuri(pid)[t]['recurenta_baza'], 'scadenta')
        self.assertEqual(self.api('put', '/api/tasks/%s' % t, {'recurenta_baza': 'finalizare'}).status_code, 200)
        self.assertEqual(self.taskuri(pid)[t]['recurenta_baza'], 'finalizare')
        self.api('put', '/api/tasks/%s' % t, {'titlu': 'alt titlu'})
        self.assertEqual(self.taskuri(pid)[t]['recurenta_baza'], 'finalizare', 'un PUT fara cheie nu o atinge')

    def test_taskul_global_de_la_finalizare(self):
        self.azi(2026, 10, 14)
        r = self.api('post', '/api/global-tasks', {'titlu': 'G', 'data_scadenta': '2026-10-01', 'recurenta': 'zilnic',
                                                   'recurenta_baza': 'finalizare', 'sfera': 'personal',
                                                   'ora': '07:30'})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        gid = r.get_json()['id']
        r = self.api('put', '/api/global-tasks/%s' % gid, {'status': 'done'})
        self.assertEqual(r.get_json()['recurring_next'], '2026-10-15')
        nou = self.api('get', '/api/global-tasks/%s' % r.get_json()['recurring_spawned']).get_json()
        self.assertEqual((nou['data_scadenta'], nou['recurenta_baza'], nou['sfera'], nou['ora']),
                         ('2026-10-15', 'finalizare', 'personal', '07:30'))

    def test_taskul_global_de_la_scadenta_ramane_ca_inainte(self):
        r = self.api('post', '/api/global-tasks', {'titlu': 'G', 'data_scadenta': '2026-10-01', 'recurenta': 'zilnic'})
        gid = r.get_json()['id']
        self.assertEqual(self.api('get', '/api/global-tasks/%s' % gid).get_json()['recurenta_baza'], 'scadenta')
        self.assertEqual(self.api('put', '/api/global-tasks/%s' % gid, {'status': 'done'}).get_json()['recurring_next'],
                         '2026-10-02')

    def test_valori_necunoscute_dau_400_la_creare_si_la_actualizare(self):
        pid = self.proiect()
        t = self.task(pid, recurenta='zilnic')
        g = self.api('post', '/api/global-tasks', {'titlu': 'G'}).get_json()['id']
        for corp in ({'recurenta': 'anual'}, {'recurenta': 'Zilnic'}, {'recurenta': 5},
                     {'recurenta_baza': 'maine'}, {'recurenta_baza': ''}):
            self.assertEqual(self.api('post', '/api/proiecte/%s/tasks' % pid, {'titlu': 'X', **corp}).status_code,
                             400, ('task create', corp))
            self.assertEqual(self.api('put', '/api/tasks/%s' % t, corp).status_code, 400, ('task put', corp))
            self.assertEqual(self.api('post', '/api/global-tasks', {'titlu': 'X', **corp}).status_code,
                             400, ('global create', corp))
            self.assertEqual(self.api('put', '/api/global-tasks/%s' % g, corp).status_code, 400, ('global put', corp))
        self.assertEqual(len(self.taskuri(pid)), 1, 'un 400 nu creeaza nimic')
        self.assertEqual(self.taskuri(pid)[t]['recurenta'], 'zilnic')

    def test_valorile_cunoscute_trec_inclusiv_golul_care_opreste_recurenta(self):
        pid = self.proiect()
        for recurenta in ('', 'zilnic', 'saptamanal', 'lunar'):
            t = self.task(pid, recurenta=recurenta)
            self.assertEqual(self.api('put', '/api/tasks/%s' % t, {'recurenta': ''}).status_code, 200)
            self.assertEqual(self.taskuri(pid)[t]['recurenta'], '')
            self.assertEqual(self.api('put', '/api/tasks/%s' % t, {'recurenta': recurenta}).status_code, 200)
        g = self.api('post', '/api/global-tasks', {'titlu': 'G', 'recurenta': 'lunar'})
        self.assertEqual(g.status_code, 201)


# ------------------------------------------------------------------------------------- L2: sabloane

SABLON = {'sare_weekend': True, 'taskuri': [
    {'titlu': 'Comanda cablu', 'decalaj_zile': -14, 'subtaskuri': []},
    {'titlu': 'Parametrizare', 'descriere': 'Dupa montaj', 'decalaj_zile': 2, 'subtaskuri': ['Rampe', 'Test STO']},
]}


class Sabloane(Baza):

    def sablon(self, **extra):
        r = self.api('post', '/api/sabloane', {'nume': 'PIF drive', 'continut': SABLON, **extra})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        return r.get_json()['id']

    def test_creare_citire_actualizare_stergere(self):
        sid = self.sablon()
        lista = {s['id']: s for s in self.api('get', '/api/sabloane').get_json()}
        self.assertEqual(lista[sid]['nume'], 'PIF drive')
        self.assertEqual(lista[sid]['continut'], SABLON, 'continutul se intoarce ca obiect, nu ca text')
        self.assertTrue(lista[sid]['created_at'] and lista[sid]['updated_at'])

        nou = {'sare_weekend': False, 'taskuri': []}
        self.assertEqual(self.api('put', '/api/sabloane/%s' % sid, {'nume': 'Alt nume'}).status_code, 200)
        s = {x['id']: x for x in self.api('get', '/api/sabloane').get_json()}[sid]
        self.assertEqual((s['nume'], s['continut']), ('Alt nume', SABLON), 'PUT fara continut nu-l atinge')
        self.assertEqual(self.api('put', '/api/sabloane/%s' % sid, {'continut': nou}).status_code, 200)
        s = {x['id']: x for x in self.api('get', '/api/sabloane').get_json()}[sid]
        self.assertEqual((s['nume'], s['continut']), ('Alt nume', nou))

        self.assertEqual(self.api('delete', '/api/sabloane/%s' % sid).status_code, 200)
        self.assertNotIn(sid, {x['id'] for x in self.api('get', '/api/sabloane').get_json()})

    def test_id_dat_de_client_si_409_la_repetare(self):
        self.assertEqual(self.sablon(id='sablon-client'), 'sablon-client')
        r = self.api('post', '/api/sabloane', {'id': 'sablon-client', 'nume': 'X', 'continut': SABLON})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()['id'], 'sablon-client')

    def test_forma_continutului_se_valideaza(self):
        def gresit(continut, mesaj):
            r = self.api('post', '/api/sabloane', {'nume': 'X', 'continut': continut})
            self.assertEqual(r.status_code, 400, continut)
            self.assertIn(mesaj, r.get_json()['error'])

        gresit(None, 'obiect')
        gresit('{"sare_weekend": true, "taskuri": []}', 'obiect')
        gresit({'sare_weekend': 1, 'taskuri': []}, 'sare_weekend')
        gresit({'sare_weekend': True}, 'taskuri')
        gresit({'sare_weekend': True, 'taskuri': {}}, 'taskuri')
        gresit({'sare_weekend': True, 'taskuri': ['x']}, 'taskuri[0]')
        corect = {'titlu': 'T', 'decalaj_zile': 0, 'subtaskuri': []}
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'titlu': '  '}]}, 'titlu')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'titlu': 5}]}, 'titlu')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'descriere': 5}]}, 'descriere')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'decalaj_zile': '2'}]}, 'decalaj_zile')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'decalaj_zile': True}]}, 'decalaj_zile')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'decalaj_zile': 1.5}]}, 'decalaj_zile')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'subtaskuri': 'a'}]}, 'subtaskuri')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'subtaskuri': [1]}]}, 'subtaskuri')
        gresit({'sare_weekend': None, 'taskuri': []}, 'sare_weekend')
        gresit({'sare_weekend': 'false', 'taskuri': []}, 'sare_weekend')
        gresit({'sare_weekend': True, 'taskuri': [{**corect, 'subtaskuri': None}]}, 'subtaskuri')

    def test_cheile_omise_se_completeaza_la_scriere(self):
        # sare_weekend lipsa = false, subtaskuri lipsa = []; ambele ajung scrise in baza.
        sid = self.sablon(continut={'taskuri': [{'titlu': 'A', 'decalaj_zile': 0},
                                                {'titlu': 'B', 'decalaj_zile': 1, 'subtaskuri': ['x']}]})
        asteptat = {'sare_weekend': False, 'taskuri': [{'titlu': 'A', 'decalaj_zile': 0, 'subtaskuri': []},
                                                       {'titlu': 'B', 'decalaj_zile': 1, 'subtaskuri': ['x']}]}
        s = {x['id']: x for x in self.api('get', '/api/sabloane').get_json()}[sid]
        self.assertEqual(s['continut'], asteptat)
        import json
        text = self.sql('SELECT continut FROM sabloane WHERE id = ?', sid)[0][0]
        self.assertEqual(json.loads(text), asteptat, 'normalizat in baza, nu doar la citire')

        # Si la PUT; descrierea, cand e data, ramane.
        self.assertEqual(self.api('put', '/api/sabloane/%s' % sid, {'continut': {'taskuri': [
            {'titlu': 'C', 'descriere': 'd', 'decalaj_zile': 2}]}}).status_code, 200)
        s = {x['id']: x for x in self.api('get', '/api/sabloane').get_json()}[sid]
        self.assertEqual(s['continut'], {'sare_weekend': False, 'taskuri': [
            {'titlu': 'C', 'descriere': 'd', 'decalaj_zile': 2, 'subtaskuri': []}]})

    def test_cheile_optionale_gresite_ca_tip_dau_400_si_la_put(self):
        sid = self.sablon()
        for continut in ({'sare_weekend': 1, 'taskuri': []},
                         {'taskuri': [{'titlu': 'T', 'decalaj_zile': 0, 'subtaskuri': 'a'}]},
                         {'taskuri': [{'titlu': 'T', 'decalaj_zile': 0, 'subtaskuri': [1]}]}):
            self.assertEqual(self.api('put', '/api/sabloane/%s' % sid, {'continut': continut}).status_code, 400)
        s = {x['id']: x for x in self.api('get', '/api/sabloane').get_json()}[sid]
        self.assertEqual(s['continut'], SABLON, 'un 400 nu schimba nimic')

    def test_descrierea_e_optionala_iar_lista_goala_de_taskuri_trece(self):
        r = self.api('post', '/api/sabloane', {'nume': 'Gol', 'continut': {'sare_weekend': False, 'taskuri': []}})
        self.assertEqual(r.status_code, 201)

    def test_numele_nu_poate_lipsi(self):
        for corp in ({'continut': SABLON}, {'nume': '', 'continut': SABLON}, {'nume': '  ', 'continut': SABLON},
                     {'nume': 5, 'continut': SABLON}, {'nume': 'X'}):
            self.assertEqual(self.api('post', '/api/sabloane', corp).status_code, 400, corp)

    def test_put_valideaza_si_da_404(self):
        sid = self.sablon()
        self.assertEqual(self.api('put', '/api/sabloane/%s' % sid, {'nume': ''}).status_code, 400)
        self.assertEqual(self.api('put', '/api/sabloane/%s' % sid, {'continut': {'taskuri': {}}}).status_code, 400)
        self.assertEqual(self.api('put', '/api/sabloane/nu-exista', {'nume': 'X'}).status_code, 404)
        self.assertEqual(self.api('delete', '/api/sabloane/nu-exista').status_code, 404)
        # Un 400 nu schimba nimic.
        s = {x['id']: x for x in self.api('get', '/api/sabloane').get_json()}[sid]
        self.assertEqual((s['nume'], s['continut']), ('PIF drive', SABLON))

    def test_cere_login_iar_dispozitivul_le_poate_folosi(self):
        self.assertEqual(self.client.get('/api/sabloane').status_code, 401)
        self.assertEqual(self.client.post('/api/sabloane', json={'nume': 'X', 'continut': SABLON}).status_code, 401)
        r = self.api('post', '/api/sabloane', {'nume': 'De pe telefon', 'continut': SABLON}, token=DEVICE)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.api('get', '/api/sabloane', token=DEVICE).status_code, 200)
        self.assertEqual(self.api('delete', '/api/sabloane/%s' % r.get_json()['id'], token=DEVICE).status_code, 200)

    def test_continutul_cu_diacritice_se_pastreaza(self):
        continut = {'sare_weekend': True, 'taskuri': [{'titlu': 'Verificare ventilație', 'decalaj_zile': 0,
                                                       'subtaskuri': ['Pregătire']}]}
        sid = self.sablon(continut=continut)
        s = {x['id']: x for x in self.api('get', '/api/sabloane').get_json()}[sid]
        self.assertEqual(s['continut'], continut)


# ------------------------------------------------------------------------- L3: starea proiectului

class StariProiect(Baza):

    def stare(self, pid, **corp):
        return self.api('post', '/api/proiecte/%s/stari' % pid, {'stare': 'in_grafic', **corp})

    def test_adaugare_si_lista_desc_dupa_data(self):
        pid = self.proiect()
        for zi, st in (('2026-10-05', 'in_grafic'), ('2026-10-12', 'risc'), ('2026-10-08', 'blocat')):
            r = self.stare(pid, stare=st, data=zi, facut='Facut', blocaje='Bloc', urmator='Urm')
            self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        lista = self.api('get', '/api/proiecte/%s/stari' % pid).get_json()
        self.assertEqual([(s['data'], s['stare']) for s in lista],
                         [('2026-10-12', 'risc'), ('2026-10-08', 'blocat'), ('2026-10-05', 'in_grafic')])
        self.assertEqual((lista[0]['facut'], lista[0]['blocaje'], lista[0]['urmator'], lista[0]['proiect_id']),
                         ('Facut', 'Bloc', 'Urm', pid))
        self.assertTrue(lista[0]['created_at'])

    def test_in_aceeasi_zi_cea_scrisa_ultima_e_prima(self):
        pid = self.proiect()
        self.stare(pid, stare='in_grafic', data='2026-10-12')
        self.stare(pid, stare='risc', data='2026-10-12')
        lista = self.api('get', '/api/proiecte/%s/stari' % pid).get_json()
        self.assertEqual([s['stare'] for s in lista], ['risc', 'in_grafic'])
        self.assertEqual(self.api('get', '/api/proiecte/%s' % pid).get_json()['stare_curenta'], 'risc')

    def test_cele_patru_stari_trec_iar_restul_da_400(self):
        pid = self.proiect()
        for st in ('in_grafic', 'risc', 'blocat', 'asteptare'):
            self.assertEqual(self.stare(pid, stare=st, data='2026-10-12').status_code, 201, st)
        # „finalizat" e statusul proiectului (invariantul 2), nu o stare.
        for st in ('finalizat', 'pregatire', 'Risc', '', None, 5):
            self.assertEqual(self.stare(pid, stare=st).status_code, 400, repr(st))
        self.assertEqual(self.api('post', '/api/proiecte/%s/stari' % pid, {}).status_code, 400)

    def test_data_invalida_da_400_iar_data_romaneasca_se_normalizeaza(self):
        pid = self.proiect()
        for rau in ('maine', '2026-02-31', '31.02.2026', 20261012):
            self.assertEqual(self.stare(pid, data=rau).status_code, 400, rau)
        self.stare(pid, data='5.10.2026')
        self.assertEqual(self.api('get', '/api/proiecte/%s/stari' % pid).get_json()[0]['data'], '2026-10-05')

    def test_fara_data_se_pune_azi(self):
        pid = self.proiect()
        for corp in ({}, {'data': ''}, {'data': None}):
            r = self.stare(pid, **corp)
            self.assertEqual(r.status_code, 201, corp)
        for s in self.api('get', '/api/proiecte/%s/stari' % pid).get_json():
            self.assertRegex(s['data'], r'^\d{4}-\d{2}-\d{2}$')

    def test_proiect_inexistent_da_404(self):
        self.assertEqual(self.stare('nu-exista').status_code, 404)

    def test_perioada_trebuie_sa_fie_a_proiectului(self):
        pid, altul = self.proiect(), self.proiect()
        buna, straina = self.perioada(pid), self.perioada(altul)
        r = self.stare(pid, implementare_id=buna)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.stare(pid, implementare_id=straina).status_code, 400)
        self.assertEqual(self.stare(pid, implementare_id='nu-exista').status_code, 400)
        self.assertEqual(self.api('get', '/api/proiecte/%s/stari' % pid).get_json()[0]['implementare_id'], buna)

    def test_stergerea_perioadei_pastreaza_starea_fara_legatura(self):
        pid = self.proiect()
        iid = self.perioada(pid)
        sid = self.stare(pid, implementare_id=iid).get_json()['id']
        self.assertEqual(self.api('delete', '/api/implementari/%s' % iid).status_code, 200)
        rand = self.api('get', '/api/proiecte/%s/stari' % pid).get_json()
        self.assertEqual([(s['id'], s['implementare_id']) for s in rand], [(sid, None)])

    def test_id_dat_de_client_si_409(self):
        pid = self.proiect()
        self.assertEqual(self.stare(pid, id='stare-client').get_json()['id'], 'stare-client')
        r = self.stare(pid, id='stare-client')
        self.assertEqual((r.status_code, r.get_json()['id']), (409, 'stare-client'))

    def test_stergere_si_404(self):
        pid = self.proiect()
        sid = self.stare(pid).get_json()['id']
        self.assertEqual(self.api('delete', '/api/stari/%s' % sid).status_code, 200)
        self.assertEqual(self.api('get', '/api/proiecte/%s/stari' % pid).get_json(), [])
        self.assertEqual(self.api('delete', '/api/stari/%s' % sid).status_code, 404)

    def test_nu_exista_put(self):
        pid = self.proiect()
        sid = self.stare(pid).get_json()['id']
        self.assertEqual(self.api('put', '/api/stari/%s' % sid, {'stare': 'risc'}).status_code, 405)

    def test_proiectul_primeste_ultima_stare_in_lista_si_la_citire(self):
        fara = self.proiect(nume='Fara stare')
        cu = self.proiect(nume='Cu stare')
        self.stare(cu, stare='in_grafic', data='2026-10-05')
        self.stare(cu, stare='risc', data='2026-10-12')
        self.stare(cu, stare='blocat', data='2026-10-08')

        unul = self.api('get', '/api/proiecte/%s' % cu).get_json()
        self.assertEqual((unul['stare_curenta'], unul['stare_data']), ('risc', '2026-10-12'))
        self.assertEqual(unul['nume'], 'Cu stare', 'p.* ramane intreg')
        self.assertIn('urmatoarea', unul)
        gol = self.api('get', '/api/proiecte/%s' % fara).get_json()
        self.assertEqual((gol['stare_curenta'], gol['stare_data']), (None, None))

        lista = {p['id']: p for p in self.api('get', '/api/proiecte?limit=500').get_json()}
        self.assertEqual((lista[cu]['stare_curenta'], lista[cu]['stare_data']), ('risc', '2026-10-12'))
        self.assertEqual((lista[fara]['stare_curenta'], lista[fara]['stare_data']), (None, None))
        self.assertIn('urmatoarea_faza', lista[cu])

    def test_dupa_stergerea_ultimei_stari_curenta_e_cea_dinainte(self):
        pid = self.proiect()
        self.stare(pid, stare='in_grafic', data='2026-10-05')
        ultima = self.stare(pid, stare='risc', data='2026-10-12').get_json()['id']
        self.api('delete', '/api/stari/%s' % ultima)
        self.assertEqual(self.api('get', '/api/proiecte/%s' % pid).get_json()['stare_curenta'], 'in_grafic')

    def test_stergerea_proiectului_sterge_starile(self):
        pid, ramas = self.proiect(), self.proiect()
        self.stare(pid)
        self.stare(pid, stare='risc')
        self.stare(ramas)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM stari_proiect WHERE proiect_id = ?', pid), [(2,)])
        self.assertEqual(self.api('delete', '/api/proiecte/%s' % pid).status_code, 200)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM stari_proiect WHERE proiect_id = ?', pid), [(0,)])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM stari_proiect WHERE proiect_id = ?', ramas), [(1,)])

    def test_cere_login(self):
        self.assertEqual(self.client.get('/api/proiecte/x/stari').status_code, 401)
        self.assertEqual(self.client.post('/api/proiecte/x/stari', json={'stare': 'risc'}).status_code, 401)
        self.assertEqual(self.client.delete('/api/stari/x').status_code, 401)


if __name__ == '__main__':
    import unittest
    unittest.main()

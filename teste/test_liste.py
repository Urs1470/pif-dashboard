"""Listele proprii (v46): `/api/liste`, sfera taskurilor globale validata dupa tabela, snapshot, backup.

Torqa creeaza listele cu tokenul de dispozitiv si cu id facut pe telefon (are coada offline si retrimite),
deci tot ce se verifica aici trece prin acel token. Listele fixe (`munca`, `personal`) nu se sterg si nu-si
schimba numele; o lista cu taskuri nu se sterge.
"""

import sqlite3
import unittest

from _aplicatia import CuAplicatia, DEVICE, FULL


class CuListe(CuAplicatia):

    def setUp(self):
        super().setUp()
        # Baza clasei e comuna testelor ei: fiecare test porneste de la cele doua liste fixe, fara taskuri.
        c = sqlite3.connect(self.db)
        try:
            c.execute('DELETE FROM global_tasks')
            c.execute('DELETE FROM liste WHERE fixa = 0')
            c.execute("UPDATE liste SET iconita = 'work', culoare = NULL, ordine = 0 WHERE id = 'munca'")
            c.execute("UPDATE liste SET iconita = 'person', culoare = NULL, ordine = 1 WHERE id = 'personal'")
            c.commit()
        finally:
            c.close()

    def h(self, token=DEVICE):
        return self.bearer(token)

    def liste(self):
        r = self.client.get('/api/liste', headers=self.h())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def ids(self):
        return [l['id'] for l in self.liste()]

    def creeaza(self, **corp):
        corp.setdefault('nume', 'Casă')
        corp.setdefault('iconita', 'house')
        return self.client.post('/api/liste', json=corp, headers=self.h())

    def task(self, titlu='T', **extra):
        return self.client.post('/api/global-tasks', json={'titlu': titlu, **extra}, headers=self.h())


class RuteListe(CuListe):

    def test_tokenul_de_dispozitiv_are_voie(self):
        from utils import device_token_denied
        for metoda in ('GET', 'POST', 'PUT', 'DELETE'):
            self.assertFalse(device_token_denied(metoda, '/api/liste'), metoda)
            self.assertFalse(device_token_denied(metoda, '/api/liste/casa'), metoda)
            self.assertFalse(device_token_denied(metoda, '/api/liste/ordine'), metoda)

    def test_fara_token_401_pe_toate_rutele(self):
        for metoda, cale in (('get', '/api/liste'), ('post', '/api/liste'), ('put', '/api/liste/munca'),
                             ('put', '/api/liste/ordine'), ('delete', '/api/liste/munca')):
            r = getattr(self.client, metoda)(cale, json={}) if metoda != 'get' else self.client.get(cale)
            self.assertEqual(r.status_code, 401, (metoda, cale))
            r = getattr(self.client, metoda)(cale, headers=self.h('gresit'))
            self.assertEqual(r.status_code, 401, (metoda, cale, 'token gresit'))

    def test_lista_porneste_cu_cele_doua_fixe_in_ordine(self):
        liste = self.liste()
        self.assertEqual([(l['id'], l['nume'], l['iconita'], l['culoare'], l['ordine'], l['fixa'], l['deschise'])
                          for l in liste],
                         [('munca', 'Muncă', 'work', None, 0, 1, 0), ('personal', 'Personal', 'person', None, 1, 1, 0)])
        self.assertEqual(set(liste[0]), {'id', 'nume', 'iconita', 'culoare', 'ordine', 'fixa', 'created_at',
                                         'updated_at', 'deschise'})

    def test_deschise_numara_doar_taskurile_nefacute_din_lista(self):
        self.creeaza(id='casa')
        self.task('a', sfera='casa')
        self.task('b', sfera='casa')
        self.task('c', sfera='casa', status='done')
        self.task('d', sfera='personal')
        self.task('e')                                             # fara sfera = munca
        deschise = {l['id']: l['deschise'] for l in self.liste()}
        self.assertEqual(deschise, {'munca': 1, 'personal': 1, 'casa': 2})

    # ---------------------------------------------------------------------------------- creare

    def test_creare_cu_id_de_la_client(self):
        r = self.creeaza(id='casa', nume='  Casă ', iconita='house', culoare='#A1B2C3')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        corp = r.get_json()
        self.assertEqual((corp['id'], corp['nume'], corp['iconita'], corp['culoare'], corp['ordine'],
                          corp['fixa'], corp['deschise']), ('casa', 'Casă', 'house', '#a1b2c3', 2, 0, 0))
        self.assertTrue(corp['created_at'] and corp['updated_at'])
        self.assertEqual(self.ids(), ['munca', 'personal', 'casa'])

    def test_aceeasi_cerere_a_doua_oara_da_409_cu_id_si_nu_dubleaza(self):
        self.assertEqual(self.creeaza(id='casa').status_code, 201)
        r = self.creeaza(id='casa', nume='Alt nume')
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()['id'], 'casa')
        liste = self.liste()
        self.assertEqual([l['nume'] for l in liste if l['id'] == 'casa'], ['Casă'], 'prima ramane neatinsa')
        self.assertEqual(len(liste), 3)

    def test_fara_id_serverul_il_genereaza(self):
        a, b = self.creeaza().get_json(), self.creeaza().get_json()
        self.assertEqual(a['ordine'], 2)
        self.assertEqual(b['ordine'], 3)
        self.assertNotEqual(a['id'], b['id'])
        import re
        self.assertTrue(re.fullmatch(r'[a-z0-9_-]{1,40}', a['id']), a['id'])

    def test_ordine_e_maximul_plus_unu(self):
        self.creeaza(id='a')
        self.creeaza(id='b')
        self.client.delete('/api/liste/a', headers=self.h())        # a=2 pleaca, b=3 ramane
        self.assertEqual(self.creeaza(id='c').get_json()['ordine'], 4, 'maximul + 1, nu numarul de liste')

    def test_culoare_lipsa_sau_null_e_implicita(self):
        self.assertIsNone(self.creeaza(id='a').get_json()['culoare'])
        self.assertIsNone(self.creeaza(id='b', culoare=None).get_json()['culoare'])

    def test_corpuri_gresite_la_creare_dau_400(self):
        rele = [
            {'nume': ''}, {'nume': '   '}, {'nume': None}, {'nume': 5}, {'nume': 'x' * 61},
            {'iconita': ''}, {'iconita': ' '}, {'iconita': None}, {'iconita': 3}, {'iconita': 'i' * 41},
            {'culoare': 'rosu'}, {'culoare': '#fff'}, {'culoare': '#12345g'}, {'culoare': 'a1b2c3'},
            {'culoare': '#a1b2c3 '}, {'culoare': 7}, {'culoare': ''},
            {'id': 'Casa'}, {'id': 'cu spatiu'}, {'id': ''}, {'id': 'x' * 41}, {'id': 12}, {'id': ['a']},
            {'id': 'a\n'}, {'id': 'munca'}, {'id': 'personal'}, {'id': 'ordine'},
        ]
        for corp in rele:
            r = self.creeaza(**corp)
            self.assertEqual(r.status_code, 400, (corp, r.get_data(as_text=True)))
            self.assertIn('error', r.get_json())
        self.assertEqual(self.ids(), ['munca', 'personal'], 'nimic nu s-a scris')
        r = self.client.post('/api/liste', data='nu e json', headers=self.h())
        self.assertEqual(r.status_code, 400)

    def test_id_de_40_de_caractere_trece(self):
        self.assertEqual(self.creeaza(id='a' * 40).status_code, 201)

    # ------------------------------------------------------------------------------ modificare

    def test_put_partial_pastreaza_restul_si_misca_updated_at(self):
        self.creeaza(id='casa', iconita='house', culoare='#112233')
        inainte = self.liste()[-1]
        r = self.client.put('/api/liste/casa', json={'nume': 'Acasă'}, headers=self.h())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        dupa = r.get_json()
        self.assertEqual((dupa['nume'], dupa['iconita'], dupa['culoare'], dupa['ordine']),
                         ('Acasă', 'house', '#112233', inainte['ordine']))
        self.assertGreaterEqual(dupa['updated_at'], inainte['updated_at'])
        self.assertNotEqual(dupa['updated_at'], inainte['updated_at'])
        self.assertEqual(self.liste()[-1], dupa)

    def test_put_culoare_null_o_aduce_la_implicit(self):
        self.creeaza(id='casa', culoare='#112233')
        r = self.client.put('/api/liste/casa', json={'culoare': None}, headers=self.h())
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(r.get_json()['culoare'])
        r = self.client.put('/api/liste/casa', json={'culoare': '#ABCDEF', 'iconita': 'star'}, headers=self.h())
        self.assertEqual((r.get_json()['culoare'], r.get_json()['iconita']), ('#abcdef', 'star'))

    def test_put_fara_nimic_de_schimbat_intoarce_lista_neatinsa(self):
        self.creeaza(id='casa')
        inainte = self.liste()[-1]
        r = self.client.put('/api/liste/casa', json={}, headers=self.h())
        self.assertEqual((r.status_code, r.get_json()), (200, inainte))

    def test_put_cu_valori_gresite_da_400_si_nu_scrie(self):
        self.creeaza(id='casa', culoare='#112233')
        inainte = self.liste()[-1]
        for corp in ({'nume': ''}, {'nume': None}, {'iconita': ''}, {'iconita': None}, {'culoare': 'x'},
                     {'culoare': ''}, {'nume': 'Bun', 'culoare': 'x'}):
            r = self.client.put('/api/liste/casa', json=corp, headers=self.h())
            self.assertEqual(r.status_code, 400, corp)
        self.assertEqual(self.liste()[-1], inainte)

    def test_put_pe_lista_necunoscuta_da_404(self):
        r = self.client.put('/api/liste/nu-exista', json={'nume': 'X'}, headers=self.h())
        self.assertEqual(r.status_code, 404)

    def test_lista_fixa_isi_schimba_iconita_si_culoarea_dar_nu_numele(self):
        r = self.client.put('/api/liste/munca', json={'nume': 'Serviciu'}, headers=self.h())
        self.assertEqual(r.status_code, 400)
        self.assertIn('fixe', r.get_json()['error'])
        r = self.client.put('/api/liste/personal', json={'nume': 'Mine', 'iconita': 'star'}, headers=self.h())
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.liste()[1]['iconita'], 'person', 'cererea refuzata nu scrie nimic')

        r = self.client.put('/api/liste/munca', json={'iconita': 'engineering', 'culoare': '#00ff00'}, headers=self.h())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual((r.get_json()['iconita'], r.get_json()['culoare'], r.get_json()['nume']),
                         ('engineering', '#00ff00', 'Muncă'))
        # Numele neschimbat, trimis impreuna cu restul obiectului, nu e o schimbare.
        r = self.client.put('/api/liste/munca', json={'nume': 'Muncă', 'iconita': 'work'}, headers=self.h())
        self.assertEqual((r.status_code, r.get_json()['iconita']), (200, 'work'))

    # ---------------------------------------------------------------------------------- ordine

    def test_ordine_noua_se_vede_la_get(self):
        self.creeaza(id='casa')
        self.creeaza(id='masina')
        r = self.client.put('/api/liste/ordine', json={'ids': ['casa', 'personal', 'masina', 'munca']},
                            headers=self.h())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual([l['id'] for l in r.get_json()], ['casa', 'personal', 'masina', 'munca'])
        self.assertEqual(self.ids(), ['casa', 'personal', 'masina', 'munca'])
        self.assertEqual([l['ordine'] for l in self.liste()], [0, 1, 2, 3])
        # O lista noua vine dupa ultima.
        self.assertEqual(self.creeaza(id='nou').get_json()['ordine'], 4)

    def test_aceeasi_ordine_trimisa_iar_nu_schimba_nimic(self):
        inainte = self.liste()
        r = self.client.put('/api/liste/ordine', json={'ids': ['munca', 'personal']}, headers=self.h())
        self.assertEqual((r.status_code, self.liste()), (200, inainte))

    def test_ordine_cu_set_gresit_da_400_si_nu_scrie(self):
        self.creeaza(id='casa')
        inainte = self.liste()
        rele = [{'ids': ['munca', 'personal']},                        # lipseste casa
                {'ids': ['munca', 'personal', 'casa', 'altceva']},     # una necunoscuta
                {'ids': ['casa', 'personal', 'casa']},                 # dublura, lipseste munca
                {'ids': ['munca', 'munca', 'personal', 'casa']},       # dublura, acelasi numar de id-uri
                {'ids': []}, {'ids': 'munca'}, {'ids': [1, 2, 3]}, {'ids': None}, {}]
        for corp in rele:
            r = self.client.put('/api/liste/ordine', json=corp, headers=self.h())
            self.assertEqual(r.status_code, 400, (corp, r.get_data(as_text=True)))
        self.assertEqual(self.liste(), inainte)

    def test_ordine_nu_e_prinsa_ca_id(self):
        # Fara regula de rutare, PUT /api/liste/ordine ar fi cautat o lista cu id-ul „ordine" (404).
        r = self.client.put('/api/liste/ordine', json={'ids': ['munca', 'personal']}, headers=self.h())
        self.assertEqual(r.status_code, 200)

    # ----------------------------------------------------------------------------------- stergere

    def test_lista_fixa_nu_se_sterge(self):
        for fixa in ('munca', 'personal'):
            r = self.client.delete('/api/liste/%s' % fixa, headers=self.h())
            self.assertEqual(r.status_code, 403, fixa)
        self.assertEqual(self.ids(), ['munca', 'personal'])

    def test_lista_cu_taskuri_nu_se_sterge_si_spune_cate(self):
        self.creeaza(id='casa')
        self.task('a', sfera='casa')
        self.task('b', sfera='casa', status='done')                # orice status conteaza
        r = self.client.delete('/api/liste/casa', headers=self.h())
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()['taskuri'], 2)
        self.assertIn('casa', self.ids())

    def test_lista_goala_se_sterge_si_a_doua_oara_e_404(self):
        self.creeaza(id='casa')
        r = self.client.delete('/api/liste/casa', headers=self.h())
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertNotIn('casa', self.ids())
        self.assertEqual(self.client.delete('/api/liste/casa', headers=self.h()).status_code, 404)

    def test_dupa_ce_taskurile_pleaca_lista_se_poate_sterge(self):
        self.creeaza(id='casa')
        tid = self.task('a', sfera='casa').get_json()['id']
        self.assertEqual(self.client.delete('/api/liste/casa', headers=self.h()).status_code, 409)
        r = self.client.put('/api/global-tasks/%s' % tid, json={'sfera': 'munca'}, headers=self.h())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.delete('/api/liste/casa', headers=self.h()).status_code, 200)

    def test_lista_necunoscuta_la_stergere_da_404(self):
        self.assertEqual(self.client.delete('/api/liste/nu-exista', headers=self.h()).status_code, 404)

    def test_si_tokenul_de_masina_si_sesiunea_cu_pin_au_acces(self):
        self.assertEqual(self.client.get('/api/liste', headers=self.h(FULL)).status_code, 200)
        self.assertEqual(self.client.get('/api/liste').status_code, 401)
        self.login()
        self.assertEqual(self.client.get('/api/liste').status_code, 200)


class SferaDupaTabela(CuListe):
    """`global_tasks.sfera` accepta orice id din `liste`; restul e 400 (invariantul 7, extins)."""

    def test_sfera_necunoscuta_la_creare_da_400_si_spune_ce_se_accepta(self):
        r = self.task(sfera='casa')
        self.assertEqual(r.status_code, 400)
        eroare = r.get_json()['error']
        self.assertIn("'munca'", eroare)
        self.assertIn("'personal'", eroare)
        for rea in ('Munca', 'xyz', 7, ['munca'], {'a': 1}):
            self.assertEqual(self.task(sfera=rea).status_code, 400, rea)
        self.assertEqual(self.client.get('/api/global-tasks?sfera=toate', headers=self.h()).get_json(), [])

    def test_sfera_goala_sau_lipsa_ramane_munca(self):
        for corp in ({}, {'sfera': ''}, {'sfera': None}):
            tid = self.task(**corp).get_json()['id']
            self.assertEqual(self.client.get('/api/global-tasks/%s' % tid, headers=self.h()).get_json()['sfera'],
                             'munca', corp)

    def test_o_sfera_noua_e_primita_si_filtrata_corect(self):
        self.creeaza(id='casa')
        r = self.task('Gresie', sfera='casa')
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        self.task('Raport')
        self.task('Sala', sfera='personal')

        def titluri(sfera):
            r = self.client.get('/api/global-tasks?sfera=%s' % sfera, headers=self.h())
            self.assertEqual(r.status_code, 200, (sfera, r.get_data(as_text=True)))
            return sorted(t['titlu'] for t in r.get_json())

        self.assertEqual(titluri('casa'), ['Gresie'])
        self.assertEqual(titluri('munca'), ['Raport'])
        self.assertEqual(titluri('personal'), ['Sala'])
        self.assertEqual(titluri('toate'), ['Gresie', 'Raport', 'Sala'])
        lista_implicita = self.client.get('/api/global-tasks', headers=self.h()).get_json()
        self.assertEqual([t['titlu'] for t in lista_implicita], ['Raport'], 'implicit doar munca')

    def test_filtrul_cu_sfera_necunoscuta_da_400_cu_sferele_acceptate(self):
        self.creeaza(id='casa')
        r = self.client.get('/api/global-tasks?sfera=nu-exista', headers=self.h())
        self.assertEqual(r.status_code, 400)
        eroare = r.get_json()['error']
        for cuvant in ("'munca'", "'personal'", "'casa'", "'toate'"):
            self.assertIn(cuvant, eroare)

    def test_mutarea_unui_task_pe_o_lista_noua(self):
        self.creeaza(id='casa')
        tid = self.task('Gresie').get_json()['id']
        r = self.client.put('/api/global-tasks/%s' % tid, json={'sfera': 'casa'}, headers=self.h())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get('/api/global-tasks/%s' % tid, headers=self.h()).get_json()['sfera'], 'casa')
        r = self.client.put('/api/global-tasks/%s' % tid, json={'sfera': 'nu-exista'}, headers=self.h())
        self.assertEqual(r.status_code, 400)
        r = self.client.put('/api/global-tasks/%s' % tid, json={'titlu': 'Altul'}, headers=self.h())
        self.assertEqual(r.status_code, 200, 'un PUT fara sfera nu o atinge')
        self.assertEqual(self.client.get('/api/global-tasks/%s' % tid, headers=self.h()).get_json()['sfera'], 'casa')

    def test_o_lista_stearsa_nu_mai_e_sfera_valida(self):
        self.creeaza(id='casa')
        self.assertEqual(self.client.delete('/api/liste/casa', headers=self.h()).status_code, 200)
        self.assertEqual(self.task(sfera='casa').status_code, 400)

    def test_aparitia_urmatoare_a_unui_task_recurent_ramane_pe_lista_lui(self):
        self.creeaza(id='casa')
        tid = self.task('Udat', sfera='casa', data_scadenta='2026-10-26', recurenta='zilnic').get_json()['id']
        r = self.client.put('/api/global-tasks/%s' % tid, json={'status': 'done'}, headers=self.h())
        self.assertEqual(r.status_code, 200)
        toate = self.client.get('/api/global-tasks?sfera=casa', headers=self.h()).get_json()
        self.assertEqual([(t['titlu'], t['status']) for t in toate], [('Udat', 'to_do')])


class SnapshotSiBackup(CuListe):

    def test_snapshotul_are_listele_la_fel_ca_get(self):
        self.creeaza(id='casa', culoare='#123456')
        self.task('a', sfera='casa')
        r = self.client.get('/api/sync/snapshot', headers=self.h())
        self.assertEqual(r.status_code, 200)
        corp = r.get_json()
        self.assertEqual(corp['liste'], self.liste())
        self.assertEqual([l['id'] for l in corp['liste']], ['munca', 'personal', 'casa'])
        self.assertEqual(corp['liste'][2]['deschise'], 1)
        self.assertEqual([g['sfera'] for g in corp['global_tasks']], ['casa'])

    def test_backup_are_tabela_liste_si_restore_o_aduce_inapoi(self):
        self.creeaza(id='casa', nume='Casă', iconita='house', culoare='#123456')
        r = self.client.get('/api/backup', headers=self.h(FULL))
        self.assertEqual(r.status_code, 200)
        backup = r.get_json()
        self.assertEqual([l['id'] for l in backup['liste']], ['munca', 'personal', 'casa'])
        self.assertEqual(set(backup['liste'][2]),
                         {'id', 'nume', 'iconita', 'culoare', 'ordine', 'fixa', 'created_at', 'updated_at'})
        # Dupa ce lista dispare din baza, restore-ul o readuce cu toate coloanele.
        self.client.delete('/api/liste/casa', headers=self.h())
        self.assertEqual(self.ids(), ['munca', 'personal'])
        r = self.client.post('/api/restore', json=backup, headers=self.h(FULL))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.liste()[2]['culoare'], '#123456')
        self.assertEqual(self.ids(), ['munca', 'personal', 'casa'])

    def test_dispozitivul_nu_poate_face_backup(self):
        self.assertEqual(self.client.get('/api/backup', headers=self.h(DEVICE)).status_code, 401)


if __name__ == '__main__':
    unittest.main()

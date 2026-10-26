"""`proiecte.nr_oferta` (v45) pe rute: Torqa o scrie cu tokenul de dispozitiv si o citeste din lista.

Oferta dupa care s-a dat comanda sta separat de `nr_comanda` (PO); un PUT cu doar oferta nu atinge
comanda (PUT face merge partial), iar un proiect creat fara ea o are goala, nu NULL.
"""

import unittest

from _aplicatia import CuAplicatia, DEVICE


class NrOfertaPeRute(CuAplicatia):

    def proiect(self, pid, **extra):
        r = self.client.post('/api/proiecte', json={'id': pid, 'nume': 'T', 'tip': 'PIF', **extra},
                             headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))

    def citit(self, pid):
        r = self.client.get('/api/proiecte/%s' % pid, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def test_crearea_scrie_oferta_si_lista_o_intoarce(self):
        self.proiect('p-of', nr_comanda='PO 4504976437', nr_oferta='OF_26_07123_R1')
        self.assertEqual(self.citit('p-of')['nr_oferta'], 'OF_26_07123_R1')
        lista = self.client.get('/api/proiecte', headers=self.bearer(DEVICE)).get_json()
        self.assertEqual([p['nr_oferta'] for p in lista if p['id'] == 'p-of'], ['OF_26_07123_R1'])

    def test_fara_oferta_la_creare_e_sir_gol(self):
        self.proiect('p-gol')
        self.assertEqual(self.citit('p-gol')['nr_oferta'], '')

    def test_put_cu_oferta_nu_atinge_comanda(self):
        self.proiect('p-put', nr_comanda='9RH1177 / OF_26_03018')
        r = self.client.put('/api/proiecte/p-put', json={'nr_oferta': 'OF_26_03018'}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        p = self.citit('p-put')
        self.assertEqual((p['nr_comanda'], p['nr_oferta']), ('9RH1177 / OF_26_03018', 'OF_26_03018'))

    def test_put_fara_oferta_o_pastreaza(self):
        self.proiect('p-pastrat', nr_oferta='OF_26_23125')
        r = self.client.put('/api/proiecte/p-pastrat', json={'nume': 'Alt nume'}, headers=self.bearer(DEVICE))
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.citit('p-pastrat')['nr_oferta'], 'OF_26_23125')

    def test_oferta_se_poate_goli(self):
        self.proiect('p-golit', nr_oferta='OF_26_23125')
        self.client.put('/api/proiecte/p-golit', json={'nr_oferta': ''}, headers=self.bearer(DEVICE))
        self.assertEqual(self.citit('p-golit')['nr_oferta'], '')


if __name__ == '__main__':
    unittest.main()

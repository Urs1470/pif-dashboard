"""Loturile de mail ale Mail Tasks (`blueprints/mail_lot.py`, din 2026-11-17): PC-ul urca exportul, serverul il judeca.

Ce se pazeste, tacut daca se strica:
  - tokenul de dispozitiv (Torqa) nu citeste si nu scrie loturi: continutul mailurilor ramane al masinilor;
  - un export in afara formei da 400 si nu scrie nimic;
  - lista nu contine mailuri, doar id, momentul si marimea; loturile vin cele mai vechi intai;
  - `gata` sterge lotul; `ultima_rulare` se scrie doar la cod 0 (cu erori, fereastra urmatoare le reia);
  - un lot uitat mai mult de 7 zile se sterge la urmatorul PUT.
"""

import os
from datetime import datetime, timedelta

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import mail_lot

EXPORT = {'meta': {'generatedAt': '2026-11-17T08:00:05+02:00', 'folders': 'All'},
          'mails': [{'received': '2026-11-17 07:41', 'from': 'Viorel Șutu', 'subject': '26_287 livrare',
                     'body': 'Corpul mailului'}]}


class MailLot(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir = os.path.join(self.dir_temp(), 'mail-lot')
        self.patch(mail_lot, 'DIR_LOT', self.dir)

    def put(self, corp, token=FULL):
        return self.client.put('/api/mail/lot', json=corp, headers=self.bearer(token))

    def get(self, cale='/api/mail/lot', token=FULL):
        return self.client.get(cale, headers=self.bearer(token))

    def gata(self, lot_id, corp, token=FULL):
        return self.client.post('/api/mail/lot/%s/gata' % lot_id, json=corp, headers=self.bearer(token))

    def test_drumul_intreg(self):
        r = self.put(EXPORT)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        j = r.get_json()
        self.assertEqual((j['mailuri'], j['in_asteptare']), (1, 1))
        lista = self.get().get_json()
        self.assertEqual([x['id'] for x in lista['loturi']], [j['id']])
        self.assertNotIn('Corpul', str(lista), 'lista nu are continut de mail')
        self.assertEqual(lista['stare'], {'ultima_rulare': None, 'ultimul_lot': None})
        lot = self.get('/api/mail/lot/' + j['id']).get_json()
        self.assertEqual(lot['mails'][0]['body'], 'Corpul mailului')
        g = self.gata(j['id'], {'cod': 0, 'rezultat': '1 task nou', 'ultima_rulare': '2026-11-17T08:03:10'})
        self.assertEqual(g.status_code, 200, g.get_data(as_text=True))
        self.assertEqual(g.get_json()['stare']['ultima_rulare'], '2026-11-17T08:03:10')
        self.assertEqual(self.get().get_json()['loturi'], [])
        self.assertEqual(self.get('/api/mail/lot/' + j['id']).status_code, 404)
        self.assertEqual(self.gata(j['id'], {'cod': 0}).status_code, 404, 'a doua oara: lotul nu mai e')

    def test_cu_erori_fereastra_nu_avanseaza(self):
        a = self.put(EXPORT).get_json()['id']
        self.gata(a, {'cod': 0, 'ultima_rulare': '2026-11-17T08:03:10'})
        b = self.put(EXPORT).get_json()['id']
        s = self.gata(b, {'cod': 1, 'rezultat': 'Claude n-a raspuns', 'ultima_rulare': '2026-11-17T14:03:10'}).get_json()['stare']
        self.assertEqual(s['ultima_rulare'], '2026-11-17T08:03:10')
        self.assertEqual(s['ultimul_lot']['cod'], 1)

    def test_dispozitivul_nu_atinge_loturile(self):
        lot_id = self.put(EXPORT).get_json()['id']
        for r in (self.put(EXPORT, DEVICE), self.get(token=DEVICE), self.get('/api/mail/lot/' + lot_id, DEVICE),
                  self.gata(lot_id, {'cod': 0}, DEVICE)):
            self.assertEqual(r.status_code, 401, r.get_data(as_text=True))
        self.assertEqual(len(self.get().get_json()['loturi']), 1)

    def test_fara_token_401(self):
        self.assertEqual(self.client.get('/api/mail/lot').status_code, 401)

    def test_export_stricat_400_fara_scriere(self):
        for corp in ({'mails': []}, {'meta': {}, 'mails': {}}, {'meta': {}, 'mails': ['x']},
                     {'meta': {}, 'mails': [{'subject': 3}]}, [1, 2]):
            r = self.put(corp)
            self.assertEqual(r.status_code, 400, corp)
        self.assertEqual(self.get().get_json()['loturi'], [])

    def test_gata_cu_corp_gresit(self):
        lot_id = self.put(EXPORT).get_json()['id']
        for corp in ({}, {'cod': 'zero'}, {'cod': True}, {'cod': 0, 'ultima_rulare': 'ieri'}, {'cod': 0, 'rezultat': 'x' * 3000}):
            self.assertEqual(self.gata(lot_id, corp).status_code, 400, corp)
        self.assertEqual(self.gata('../stare', {'cod': 0}).status_code, 404)
        self.assertEqual(len(self.get().get_json()['loturi']), 1)

    def test_lotul_uitat_se_sterge(self):
        vechi = (datetime.now() - timedelta(days=8)).strftime('%Y%m%dT%H%M%S') + '-abcdef'
        os.makedirs(self.dir, exist_ok=True)
        with open(os.path.join(self.dir, vechi + '.json'), 'w', encoding='utf-8') as fh:
            fh.write('{"meta": {}, "mails": []}')
        self.put(EXPORT)
        ids = [x['id'] for x in self.get().get_json()['loturi']]
        self.assertNotIn(vechi, ids)
        self.assertEqual(len(ids), 1)

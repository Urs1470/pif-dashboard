"""Limita de incercari de PIN (`ratelimit.py`): comuna worker-ilor si pastrata peste redeploy.

Doi workeri Gunicorn sunt doua procese cu memorie separata; un redeploy e un proces nou. De
aceea testele de aici folosesc ori instante noi ale clasei pe acelasi fisier, ori procese
adevarate (`subprocess`), nu doar dictul din memorie care era problema.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from _aplicatia import CuAplicatia
from _baza import RADACINA, Test
from ratelimit import LimitaIncercari, cale_implicita

COD_WORKER = """
import sys
sys.path.insert(0, %r)
from ratelimit import LimitaIncercari
lim = LimitaIncercari(5, 300, cale=sys.argv[1])
print(sum(1 for _ in range(10) if lim.permite('203.0.113.9')))
""" % RADACINA


class LimitaPeFisier(Test):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='pif-rate-')
        self.addCleanup(__import__('shutil').rmtree, self.tmp, ignore_errors=True)
        self.cale = os.path.join(self.tmp, 'rate.db')

    def limita(self, limita=5, fereastra=300):
        return LimitaIncercari(limita, fereastra, cale=self.cale)

    def test_a_sasea_incercare_este_refuzata(self):
        lim = self.limita()
        self.assertEqual([lim.permite('198.51.100.1') for _ in range(7)], [True] * 5 + [False] * 2)

    def test_fiecare_ip_isi_are_numaratoarea(self):
        lim = self.limita()
        for _ in range(5):
            lim.permite('198.51.100.1')
        self.assertFalse(lim.permite('198.51.100.1'))
        self.assertTrue(lim.permite('198.51.100.2'))

    def test_doi_workeri_impart_numaratoarea(self):
        # Doua instante = doua procese cu memorie proprie, acelasi fisier. Inainte: 5 + 5.
        a, b = self.limita(), self.limita()
        rezultate = [a.permite('198.51.100.1') for _ in range(3)] + [b.permite('198.51.100.1') for _ in range(4)]
        self.assertEqual(rezultate, [True] * 5 + [False] * 2)

    def test_redeploy_nu_goleste_limita(self):
        vechi = self.limita()
        for _ in range(5):
            vechi.permite('198.51.100.1')
        del vechi                                  # procesul vechi dispare
        nou = self.limita()                        # procesul de dupa restart
        self.assertFalse(nou.permite('198.51.100.1'))

    def test_incercarile_expira_dupa_fereastra(self):
        lim = self.limita(fereastra=0.2)
        for _ in range(5):
            lim.permite('198.51.100.1')
        self.assertFalse(lim.permite('198.51.100.1'))
        import time
        time.sleep(0.3)
        self.assertTrue(lim.permite('198.51.100.1'))

    def test_o_incercare_refuzata_nu_prelungeste_blocarea(self):
        lim = self.limita()
        for _ in range(9):
            lim.permite('198.51.100.1')
        import sqlite3
        n = sqlite3.connect(self.cale).execute('SELECT COUNT(*) FROM incercari').fetchone()[0]
        self.assertEqual(n, 5)

    def test_doua_procese_adevarate_in_paralel_nu_trec_de_limita(self):
        procese = [subprocess.Popen([sys.executable, '-I', '-c', COD_WORKER, self.cale],
                                    stdout=subprocess.PIPE, text=True) for _ in range(4)]
        permise = sum(int(p.communicate()[0]) for p in procese)
        self.assertEqual([p.returncode for p in procese], [0] * 4)
        self.assertEqual(permise, 5, '4 procese x 10 incercari, aceeasi adresa: exact 5 trec')

    def test_fisierul_stricat_cade_pe_memorie_nu_pe_500(self):
        lim = LimitaIncercari(5, 300, cale=self.tmp)           # un director, nu un fisier SQLite
        with self.assertLogs('pif_dashboard', level='ERROR'):
            rezultate = [lim.permite('198.51.100.1') for _ in range(6)]
        self.assertEqual(rezultate, [True] * 5 + [False])

    def test_calea_implicita_sta_langa_baza_si_pif_rate_db_o_schimba(self):
        import database
        self.assertEqual(cale_implicita(), database.DATABASE_PATH + '.ratelimit')
        anterior = os.environ.get('PIF_RATE_DB')
        os.environ['PIF_RATE_DB'] = self.cale
        try:
            self.assertEqual(cale_implicita(), self.cale)
        finally:
            if anterior is None:
                del os.environ['PIF_RATE_DB']
            else:
                os.environ['PIF_RATE_DB'] = anterior


class LimitaPeLogin(CuAplicatia):
    """Prin ruta `/login`, cu PIN gresit (nu conteaza hash-ul)."""

    def setUp(self):
        super().setUp()
        self.patch(self.app_module, 'check_password_hash', lambda *_: False)

    def incearca(self):
        return self.client.post('/login', json={'pin': 'gresit'}).status_code

    def test_a_sasea_incercare_da_429_cu_retry_after(self):
        self.assertEqual([self.incearca() for _ in range(5)], [401] * 5)
        r = self.client.post('/login', json={'pin': 'gresit'})
        self.assertEqual(r.status_code, 429)
        self.assertEqual(r.headers['Retry-After'], '300')
        self.assertIn('error', r.get_json())

    def test_alt_worker_si_un_proces_nou_vad_aceleasi_incercari(self):
        for _ in range(3):
            self.incearca()
        # „Alt worker” / „dupa redeploy”: obiect nou pe acelasi fisier, memorie goala.
        self.patch(self.app_module, 'login_limit',
                   LimitaIncercari(self.app_module.LOGIN_LIMIT, self.app_module.LOGIN_WINDOW))
        self.assertEqual([self.incearca() for _ in range(3)], [401, 401, 429])

    def test_fisierul_limitei_nu_e_baza_aplicatiei(self):
        self.incearca()
        self.assertTrue(os.path.exists(self.db + '.ratelimit'))
        import sqlite3
        tabele = {r[0] for r in sqlite3.connect(self.db).execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertNotIn('incercari', tabele, 'schema bazei aplicatiei ramane neatinsa')


if __name__ == '__main__':
    unittest.main()

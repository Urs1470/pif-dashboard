"""Intoarcerea dupa login (`/login?next=`): doar o cale a ACESTUI site.

`/login?next=/torqa/` te duce inapoi la Torqa dupa PIN. Dar un `next` e o intrare pe care nu
o controlezi: daca ar duce oriunde, pagina de PIN ar deveni un redirect deschis — cineva
trimite un link cu `next=https://alt-site`, tu tastezi PIN-ul, si ajungi pe un site care arata
ca dashboardul. De aceea doar o cale relativa, cu o singura `/` la inceput; orice altceva
duce la `/`.

Regula exista in doua locuri, serverul (`utils.safe_next_url`) si pagina de login
(`destinatie()` din templates/login.html); unul din teste ruleaza amandoua pe aceleasi intrari.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from _aplicatia import PIN, CuAplicatia
from _baza import RADACINA, Test
from utils import safe_next_url

VALIDE = [
    '/', '/torqa/', '/torqa', '/torqa/?a=b', '/torqa/#/tag/azi', '/x/y/z.html', '/a%2Fb',
    '/@x', '/.', '/torqa/%2Fevil.com', '/api/me', '/%5Cevil.com', '/a?next=//evil.com',
    '/"><script>alert(1)</script>',                  # valid ca cale; se escapeaza la afisare
]

RELE = [
    None, '', 123, 1.5, True, [], ['/x'], {}, {'next': '/'},
    'torqa/', 'x', ' /torqa/', '/torqa/ ', '/ torqa', '/x y',
    '//evil.com', '///evil.com', '//', '////', '//evil.com/torqa/',
    '/\\evil.com', '\\evil.com', '\\\\evil.com', '\\/evil.com', '/\\/evil.com', '/a\\b',
    'https://evil.com', 'http://evil.com/torqa/', 'ftp://evil.com', 'javascript:alert(1)',
    'JaVaScRiPt:alert(1)', 'data:text/html,<script>alert(1)</script>', 'mailto:x@y.z',
    '/\t/evil.com', '/\n/evil.com', '/\r\nSet-Cookie: x=1', '/\x00x', '/\x7fx', '/\x1bx',
    '\t//evil.com', '\n//evil.com', '/' + chr(0x2028) + 'x', '/' + chr(0xa0) + 'x',
    '/caf' + chr(0xe9), '/' + chr(0x430) + chr(0x431) + chr(0x432),
    '/' + 'a' * 2048,                                 # 2049 de caractere
]


class SafeNextUrl(Test):

    def test_caile_ale_site_ului_trec_neschimbate(self):
        for v in VALIDE:
            with self.subTest(valoare=v):
                self.assertEqual(safe_next_url(v), v)

    def test_orice_altceva_duce_la_radacina(self):
        for v in RELE:
            with self.subTest(valoare=v):
                self.assertEqual(safe_next_url(v), '/')

    def test_valoarea_implicita(self):
        self.assertEqual(safe_next_url('//evil.com', default='/torqa/'), '/torqa/')
        self.assertEqual(safe_next_url(None, default='/x'), '/x')
        self.assertEqual(safe_next_url('/torqa/', default='/x'), '/torqa/')

    def test_limita_de_lungime(self):
        self.assertEqual(safe_next_url('/' + 'a' * 2047), '/' + 'a' * 2047)        # 2048
        self.assertEqual(safe_next_url('/' + 'a' * 2048), '/')                     # 2049


class DupaLogin(CuAplicatia):

    def pagina(self, next_=None):
        cale = '/login' if next_ is None else '/login?next=%s' % next_
        return self.client.get(cale)

    @staticmethod
    def data_next(r):
        m = re.search(r'<form id="login-form"[^>]*\bdata-next="([^"]*)"', r.get_data(as_text=True))
        assert m, 'formularul de login nu are data-next'
        return m.group(1)

    # ---- pagina de login poarta destinatia

    def test_pagina_de_login_poarta_destinatia_ceruta(self):
        r = self.pagina('/torqa/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.data_next(r), '/torqa/')

    def test_fara_next_destinatia_e_radacina(self):
        self.assertEqual(self.data_next(self.pagina()), '/')

    def test_un_next_primejdios_devine_radacina_in_pagina(self):
        for rau in ('//evil.com', 'https://evil.com', '/\\evil.com', 'javascript:alert(1)',
                    '/\t/evil.com', '%2F%2Fevil.com'):
            with self.subTest(next=rau):
                r = self.client.get('/login', query_string={'next': rau})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(self.data_next(r), '/')

    def test_un_next_cu_ghilimele_nu_iese_din_atribut(self):
        r = self.client.get('/login', query_string={'next': '/"><script>alert(1)</script>'})
        corp = r.get_data(as_text=True)
        self.assertNotIn('<script>alert(1)</script>', corp)
        self.assertIn('data-next="/&#34;&gt;&lt;script&gt;alert(1)&lt;/script&gt;"', corp)

    # ---- deja autentificat

    def test_deja_autentificat_redirect_la_destinatie(self):
        self.login()
        r = self.pagina('/torqa/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers['Location'], '/torqa/')

    def test_deja_autentificat_fara_next_sau_cu_next_rau_redirect_la_radacina(self):
        self.login()
        for next_ in (None, '//evil.com', 'https://evil.com', 'javascript:alert(1)', '/\\evil.com', ''):
            with self.subTest(next=next_):
                r = self.client.get('/login', query_string={} if next_ is None else {'next': next_})
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], '/')

    # ---- POST /login

    def test_pinul_bun_intoarce_destinatia_validata(self):
        for trimis, asteptat in (('/torqa/', '/torqa/'), ('/x/y', '/x/y'), (None, '/'), ('', '/'),
                                 ('//evil.com', '/'), ('https://evil.com', '/'),
                                 ('/\\evil.com', '/'), (5, '/'), (['/torqa/'], '/'), ({'a': 1}, '/')):
            with self.subTest(next=trimis):
                self.client = self.app_module.app.test_client()
                corp = {} if trimis is None else {'next': trimis}
                r = self.login(**corp)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.get_json(), {'success': True, 'next': asteptat})

    def test_fara_next_in_corp_raspunsul_ramane_compatibil(self):
        r = self.login()
        self.assertTrue(r.get_json()['success'])
        self.assertEqual(r.get_json()['next'], '/')

    def test_pinul_gresit_nu_autentifica_si_nu_da_destinatie(self):
        self.app_module._login_attempts.clear()
        r = self.client.post('/login', json={'pin': 'gresit', 'next': '/torqa/'})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json(), {'error': 'Invalid PIN'})
        self.assertEqual(self.client.get('/api/stats').status_code, 401, 'sesiunea nu s-a pus')
        self.assertEqual(self.client.get('/torqa/').status_code, 302)

    def test_pinul_bun_cu_next_torqa_te_pune_pe_sesiune(self):
        r = self.client.post('/login', json={'pin': PIN, 'next': '/torqa/'})
        self.assertEqual(r.get_json()['next'], '/torqa/')
        self.assertEqual(self.client.get('/api/stats').status_code, 200, 'sesiunea e pusa')

    # ---- aceeasi regula in browser

    @unittest.skipUnless(shutil.which('node'), 'node nu e in PATH')
    def test_regula_din_pagina_de_login_e_aceeasi_cu_a_serverului(self):
        with open(os.path.join(RADACINA, 'templates', 'login.html'), encoding='utf-8') as fh:
            sursa = fh.read()
        m = re.search(r'function destinatie\(valoare\) \{.*?\n        \}', sursa, re.S)
        self.assertIsNotNone(m, 'destinatie() lipseste din templates/login.html')
        intrari = [v for v in VALIDE + RELE if isinstance(v, str)] + [None, 5, True, [], {}]
        tmp = tempfile.mkdtemp(prefix='pif-login-js-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        cale = os.path.join(tmp, 'proba.js')
        with open(cale, 'w', encoding='utf-8') as fh:
            fh.write(m.group(0) + '\n'
                     'const intrari = %s;\n'
                     'process.stdout.write(JSON.stringify(intrari.map(destinatie)));\n'
                     % json.dumps(intrari))
        rez = subprocess.run([shutil.which('node'), cale], capture_output=True, timeout=60)
        self.assertEqual(rez.returncode, 0, rez.stderr.decode('utf-8', 'replace'))
        din_js = json.loads(rez.stdout.decode('utf-8'))
        for v, js in zip(intrari, din_js):
            with self.subTest(valoare=v):
                self.assertEqual(js, safe_next_url(v), 'pagina si serverul nu mai spun acelasi lucru')


if __name__ == '__main__':
    unittest.main()

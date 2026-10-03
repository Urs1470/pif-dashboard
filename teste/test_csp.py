"""Politica de continut a serverului, in afara de Torqa web (`/torqa/` si-o are pe a lui, `CSP_TORQA`).

Ce mai serveste serverul pe lângă Torqa: pagina de login, `/admin/db-upload`, raspunsurile JSON ale
API-ului, paginile de eroare si fisierele din `/static/`. Pana pe 2026-10-03 politica lor mai lista CDN-uri,
Google Fonts, `query1.finance.yahoo.com`, `img-src https:` si `'unsafe-inline'`, toate ramase de la SPA si
de la calculator. Acum: nimic din exterior, iar scripturile si stilurile inline cer nonce-ul cererii.

Testele de aici pazesc doua lucruri deodata. Politica: fara surse externe, fara `unsafe-*`. Si
paginile: o politica stricta strica in tacere o pagina care are inca un `onclick=` sau un
`style="..."` inline (butonul nu mai raspunde, iconita nu se mai ascunde), deci paginile se
scaneaza cu aceleasi reguli. Ca pagina de login chiar functioneaza sub ea s-a vazut intr-un
Chromium real (nicio incalcare, tema, PIN gresit, PIN bun) si o pazesc `teste/js/login.test.mjs`
(scriptul din pagina, cu formularul legat din script) si testele de aici (pagina fara nimic inline).
"""

import os
import re

from _aplicatia import CuAplicatia
from _baza import RADACINA


def directive(csp):
    return dict(d.strip().split(' ', 1) for d in csp.split(';') if d.strip())


def nonce_din(csp):
    m = re.search(r"'nonce-([A-Za-z0-9_\-]+)'", csp)
    return m.group(1) if m else None


def inline_fara_nonce(html):
    """Tot ce o politica fara `unsafe-inline` ar bloca intr-o pagina HTML."""
    probleme = []
    for m in re.finditer(r'<script\b([^>]*)>', html, re.I):
        if 'src=' not in m.group(1) and 'nonce=' not in m.group(1):
            probleme.append('script inline fara nonce: ' + m.group(0))
    for m in re.finditer(r'<style\b([^>]*)>', html, re.I):
        if 'nonce=' not in m.group(1):
            probleme.append('<style> fara nonce: ' + m.group(0))
    for m in re.finditer(r'<[a-zA-Z][^>]*?\s(on[a-z]+)\s*=', html):
        probleme.append('handler inline `%s`' % m.group(1))
    for m in re.finditer(r'<[a-zA-Z][^>]*?\sstyle\s*=', html):
        probleme.append('atribut `style` inline: ' + m.group(0)[:60])
    if re.search(r'(?:href|src|action)\s*=\s*["\']\s*javascript:', html, re.I):
        probleme.append('adresa javascript:')
    return probleme


class PoliticaImplicita(CuAplicatia):

    CAI = ('/login', '/login?next=/torqa/', '/', '/logout', '/api/healthz', '/api/stats', '/api/nu-exista',
           '/nu-exista', '/static/login.css', '/service-worker.js')

    def csp(self, cale, **kw):
        r = self.client.get(cale, **kw)
        r.close()                       # fisierele statice tin deschis fisierul pana la inchidere
        return r.headers['Content-Security-Policy']

    def test_nicio_sursa_externa_si_niciun_unsafe(self):
        for cale in self.CAI:
            with self.subTest(cale=cale):
                csp = self.csp(cale)
                self.assertNotRegex(csp, r'(\*|https?:|wss?:|blob:)', 'nicio sursa externa, nicio schema larga')
                self.assertNotIn("'unsafe-inline'", csp)
                self.assertNotIn("'unsafe-eval'", csp)
                for vechi in ('jsdelivr', 'cloudflare', 'unpkg', 'googleapis', 'gstatic', 'yahoo'):
                    self.assertNotIn(vechi, csp)

    def test_directivele(self):
        csp = self.csp('/login')
        d = directive(csp)
        nonce = nonce_din(csp)
        self.assertTrue(nonce and len(nonce) >= 16, 'nonce imprevizibil')
        self.assertEqual(d['default-src'], "'self'")
        self.assertEqual(set(d['script-src'].split()), {"'self'", "'nonce-%s'" % nonce})
        self.assertEqual(set(d['style-src'].split()), {"'self'", "'nonce-%s'" % nonce})
        self.assertEqual(set(d['img-src'].split()), {"'self'", 'data:'}, '`data:` = iconita paginii de login')
        self.assertEqual(d['font-src'], "'self'")
        self.assertEqual(d['connect-src'], "'self'")
        self.assertEqual(d['form-action'], "'self'")
        self.assertEqual(d['frame-ancestors'], "'none'")
        self.assertEqual(d['base-uri'], "'self'")
        # frame-src a plecat odata cu planul de departament (test_retragere); nu se intoarce.
        for lipsa in ('frame-src', 'worker-src', 'media-src', 'object-src', 'manifest-src'):
            self.assertNotIn(lipsa, d, lipsa)

    def test_nonce_nou_la_fiecare_cerere(self):
        nonce = {nonce_din(self.csp('/login')) for _ in range(5)}
        self.assertEqual(len(nonce), 5)
        self.assertNotIn(None, nonce)

    def test_nonce_din_antet_este_cel_din_pagina(self):
        r = self.client.get('/login')
        nonce = nonce_din(r.headers['Content-Security-Policy'])
        html = r.get_data(as_text=True)
        scripturi = re.findall(r'<script\b[^>]*>', html)
        self.assertEqual(len(scripturi), 2, 'bootstrap-ul temei si logica paginii')
        for tag in scripturi:
            self.assertIn('nonce="%s"' % nonce, tag)

    def test_pagina_de_login_nu_are_nimic_inline_fara_nonce(self):
        self.assertEqual(inline_fara_nonce(self.client.get('/login').get_data(as_text=True)), [])
        with open(os.path.join(RADACINA, 'templates', 'login.html'), encoding='utf-8') as fh:
            sablon = fh.read()
        # Sablonul are nonce-ul ca `{{ csp_nonce }}`; restul regulilor se aplica la fel.
        self.assertEqual(inline_fara_nonce(sablon), [])

    def test_pagina_de_login_isi_gaseste_clasa_iconitelor_in_css(self):
        # `style="display:none"` a fost inlocuit cu o clasa: daca clasa lipseste din CSS, toate cele
        # trei iconite de tema apar deodata.
        html = self.client.get('/login').get_data(as_text=True)
        with open(os.path.join(RADACINA, 'static', 'login.css'), encoding='utf-8') as fh:
            css = fh.read()
        for clasa in set(re.findall(r'class="(theme-icon-hidden)"', html)):
            self.assertRegex(css, r'\.%s\s*\{[^}]*display:\s*none' % clasa)

    def test_db_upload_poarta_nonce_si_nimic_inline_fara_el(self):
        self.assertEqual(self.login().status_code, 200)
        r = self.client.get('/admin/db-upload')
        self.assertEqual(r.status_code, 200)
        nonce = nonce_din(r.headers['Content-Security-Policy'])
        html = r.get_data(as_text=True)
        self.assertEqual(inline_fara_nonce(html), [])
        self.assertIn('<style nonce="%s">' % nonce, html)
        self.assertIn('<script nonce="%s">' % nonce, html)
        self.assertNotIn('__NONCE__', html, 'placeholder-ul a fost inlocuit')
        # Alta cerere, alt nonce: pagina nu tine unul vechi.
        r2 = self.client.get('/admin/db-upload')
        self.assertNotEqual(nonce_din(r2.headers['Content-Security-Policy']), nonce)

    def test_db_upload_trimite_tokenul_csrf_din_cookie(self):
        # Fara header, sesiunea de PIN primea 403 la urcare (csrf.py): pagina nu-l trimitea.
        self.assertEqual(self.login().status_code, 200)
        html = self.client.get('/admin/db-upload').get_data(as_text=True)
        self.assertIn('csrf_token=', html, 'scriptul citeste cookie-ul')
        self.assertIn("headers:{'X-CSRF-Token':csrf}", html, 'si il trimite la urcare')

    def test_urcarea_cu_sesiune_trece_de_csrf_doar_cu_header(self):
        # Fara fisier, ca nicio baza sa nu fie inlocuita: 400 = a trecut de CSRF, 403 = nu.
        self.assertEqual(self.login().status_code, 200)
        self.client.get('/admin/db-upload')                # cookie-ul csrf vine pe raspuns
        token = self.client.get_cookie('csrf_token').value
        self.assertEqual(self.client.post('/api/admin/db-upload').status_code, 403)
        r = self.client.post('/api/admin/db-upload', headers={'X-CSRF-Token': token})
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn("'db'", r.get_json()['error'])

    def test_db_upload_nu_se_deschide_cu_tokenul_de_dispozitiv_si_fara_sesiune(self):
        from _aplicatia import DEVICE
        self.assertEqual(self.client.get('/admin/db-upload', headers=self.bearer(DEVICE)).status_code, 302)
        self.assertEqual(self.client.get('/admin/db-upload').status_code, 302)

    def test_raspunsurile_date_inainte_de_nonce_au_politica_fara_el(self):
        # 429 de la limita de cereri: `before_request` se opreste inainte sa puna nonce-ul.
        self.patch(self.app_module, 'RATE_LIMIT', 1)
        self.client.get('/api/healthz')                      # healthz nu intra in limita
        self.client.get('/api/stats')
        r = self.client.get('/api/stats')
        self.assertEqual(r.status_code, 429)
        csp = r.headers['Content-Security-Policy']
        self.assertIsNone(nonce_din(csp))
        self.assertEqual(directive(csp)['script-src'], "'self'")
        # 403 de la CSRF: `_check_csrf` ruleaza inaintea lui `before_request_func`.
        self.patch(self.app_module, 'RATE_LIMIT', 1000)
        self.app_module.rate_limit_store.clear()
        self.assertEqual(self.login().status_code, 200)
        r = self.client.post('/api/global-tasks', json={'titlu': 'x'})
        self.assertEqual(r.status_code, 403)
        self.assertIn('Content-Security-Policy', r.headers)
        self.assertIsNone(nonce_din(r.headers['Content-Security-Policy']))

    def test_torqa_web_si_politica_lui_nu_sunt_atinse(self):
        from blueprints import torqa_web
        r = self.client.get('/torqa/')
        self.assertEqual(r.headers['Content-Security-Policy'], torqa_web.CSP_TORQA)


if __name__ == '__main__':
    import unittest
    unittest.main()

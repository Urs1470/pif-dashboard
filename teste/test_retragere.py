"""Ce a plecat odata cu interfata veche a dashboardului (2026-10-03) nu mai raspunde.

Serverul e doar backend-ul Torqa: API-ul, loginul cu PIN si Torqa web la `/torqa/`. Testele de
aici pazesc retragerea: o ruta, un fisier sau un blueprint adus inapoi din greseala (un
`git checkout` din eticheta `inainte-de-retragere`, un merge) apare ca test picat, nu ca o
suprafata veche care renaste in tacere. Ce NU s-a retras e acoperit de testele lui
(`test_torqa_web`, `test_sync`, `test_login_next`, `scripts/test_suite.py`).
"""

import os

from _aplicatia import CuAplicatia
from _baza import RADACINA


class NotificarilePushSiPlanulDeDepartament(CuAplicatia):
    """Rutele lor au plecat; randurile din `app_settings` raman (baza nu s-a atins)."""

    RUTE = (
        ('get', '/api/push/vapid-public'), ('post', '/api/push/subscribe'),
        ('post', '/api/push/unsubscribe'), ('post', '/api/push/tokens'),
        ('get', '/api/push/setari'), ('put', '/api/push/setari'), ('get', '/api/push/status'),
        ('post', '/api/push/test'), ('post', '/api/push/action'),
        ('get', '/api/settings/plan-departament'), ('put', '/api/settings/plan-departament'),
    )

    def test_rutele_dau_404_si_cu_token_de_masina(self):
        # Cu Bearer, fiindca o POST/PUT cu sesiune dar fara antet CSRF ar fi oprita de 403
        # inainte sa se afle ca ruta nu exista; aici vrem raspunsul de rutare.
        for metoda, cale in self.RUTE:
            with self.subTest(metoda=metoda, cale=cale):
                r = getattr(self.client, metoda)(cale, json={}, headers=self.bearer())
                self.assertEqual(r.status_code, 404)
                self.assertEqual(r.get_json(), {'error': 'Endpoint inexistent'})

    def test_nu_mai_exista_nicio_regula_pe_prefixele_plecate(self):
        reguli = [r.rule for r in self.app_module.app.url_map.iter_rules()]
        for prefix in ('/api/push/', '/api/settings/plan-departament'):
            self.assertEqual([r for r in reguli if r.startswith(prefix)], [], prefix)

    def test_politica_de_continut_implicita_nu_mai_deschide_cadre(self):
        # `frame-src` exista doar pentru planul de departament, incorporat in pagina /departament.
        csp = self.client.get('/login').headers['Content-Security-Policy']
        self.assertNotIn('frame-src', csp)
        self.assertNotIn('projectplan-powerpoint', csp)


class InterfataVeche(CuAplicatia):
    """SPA-ul Svelte, calculatorul public si tot ce le servea: radacina duce la Torqa web,
    restul dau 404. Raman: loginul, `/api/healthz`, `/service-worker.js` (retras)."""

    FISIERE_PLECATE = (
        '/calc', '/assets/index-abc123.js', '/favicon.svg', '/manifest.json', '/icon-192.png',
        '/icon-512.png', '/docs/abb-technical-guide.pdf', '/docs/standards/iec60034-1-extras.pdf',
        '/static/pdfjs/web/viewer.html', '/static/dist/index.html', '/api/me',
    )

    def test_radacina_duce_la_torqa_web_cu_sau_fara_sesiune(self):
        for autentificat in (False, True):
            if autentificat:
                self.assertEqual(self.login().status_code, 200)
            with self.subTest(autentificat=autentificat):
                r = self.client.get('/')
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], '/torqa/')

    def test_fisierele_si_paginile_interfetei_vechi_dau_404(self):
        self.login()
        for cale in self.FISIERE_PLECATE:
            with self.subTest(cale=cale):
                self.assertEqual(self.client.get(cale).status_code, 404)

    def test_nici_fara_sesiune_nu_se_serveste_nimic_din_ele(self):
        for cale in self.FISIERE_PLECATE:
            with self.subTest(cale=cale):
                self.assertEqual(self.client.get(cale).status_code, 404)

    def test_politica_speciala_pentru_pdfjs_a_plecat_si_ea(self):
        csp = self.client.get('/static/pdfjs/web/viewer.html').headers['Content-Security-Policy']
        self.assertNotIn('wasm-unsafe-eval', csp)

    def test_service_workerul_vechi_e_inlocuit_de_cel_care_se_retrage(self):
        # Fara sesiune: browserul il cere singur, in fundal, oricand.
        r = self.client.get('/service-worker.js')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers['Content-Type'].split(';')[0], 'application/javascript')
        self.assertEqual(r.headers['Service-Worker-Allowed'], '/')
        self.assertEqual(r.headers['Cache-Control'], 'no-cache', 'browserul trebuie sa-l reverifice mereu')
        corp = r.get_data(as_text=True)
        r.close()
        with open(os.path.join(RADACINA, 'static', 'service-worker.js'), encoding='utf-8', newline='') as fh:
            self.assertEqual(corp.replace('\r\n', '\n'), fh.read().replace('\r\n', '\n'))
        self.assertIn('registration.unregister()', corp)
        for ramas in ("addEventListener('fetch'", "addEventListener('push'", 'caches.open', 'cache.put'):
            self.assertNotIn(ramas, corp)

    def test_loginul_si_healthz_raman(self):
        self.assertEqual(self.client.get('/login').status_code, 200)
        self.assertEqual(self.client.get('/api/healthz').status_code, 200)
        self.assertEqual(self.login().status_code, 200)
        r = self.client.get('/login', query_string={'next': '/torqa/'})
        self.assertEqual((r.status_code, r.headers['Location']), (302, '/torqa/'))

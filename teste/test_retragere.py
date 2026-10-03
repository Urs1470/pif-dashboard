"""Ce a plecat odata cu interfata veche a dashboardului (2026-10-03) nu mai raspunde.

Serverul e doar backend-ul Torqa: API-ul, loginul cu PIN si Torqa web la `/torqa/`. Testele de
aici pazesc retragerea: o ruta, un fisier sau un blueprint adus inapoi din greseala (un
`git checkout` din eticheta `inainte-de-retragere`, un merge) apare ca test picat, nu ca o
suprafata veche care renaste in tacere. Ce NU s-a retras e acoperit de testele lui
(`test_torqa_web`, `test_sync`, `test_login_next`, `scripts/test_suite.py`).
"""

from _aplicatia import CuAplicatia


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

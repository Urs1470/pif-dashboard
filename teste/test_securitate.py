"""Gărzile: drumul prin vault, tabelele permise, secretele din iesirea git, CSRF.

Fiecare functie de aici sta intre o intrare pe care n-o controlezi si ceva ce nu vrei
atins: un fisier din afara vault-ului, o tabela oarecare intr-un SQL construit, un
token de acces scris intr-un log. Niciuna n-avea test pana pe 2026-09-28. (Tokenul de
actiune al notificarilor push a plecat odata cu push-ul, 2026-10-03.)
"""

import os
import shutil
import tempfile
import unittest

import csrf
from _aplicatia import CuAplicatia
from _baza import Test
from utils import safe_table
from blueprints.obsidian import _obsidian_safe_path, _obsidian_safe_dir, _scrub_secrets


class DrumulPrinVault(Test):

    def setUp(self):
        self.radacina = tempfile.mkdtemp(prefix='pif-vault-')
        self.vault = os.path.join(self.radacina, 'vault')
        os.makedirs(os.path.join(self.vault, 'sub'))
        for rel in ('a.md', 'sub/b.md', 'x.txt'):
            with open(os.path.join(self.vault, rel), 'w', encoding='utf-8') as f:
                f.write('x')
        with open(os.path.join(self.radacina, 'afara.md'), 'w', encoding='utf-8') as f:
            f.write('secret')

    def tearDown(self):
        shutil.rmtree(self.radacina, ignore_errors=True)

    def test_notele_din_vault_se_deschid(self):
        self.assertTrue(_obsidian_safe_path(self.vault, 'a.md'))
        self.assertTrue(_obsidian_safe_path(self.vault, 'sub/b.md'))
        self.assertTrue(_obsidian_safe_path(self.vault, '/a.md'), 'slash-ul din fata se ignora')
        self.assertTrue(_obsidian_safe_path(self.vault, 'sub\\b.md'), 'separatorul Windows')

    def test_nimic_din_afara_vault_ului(self):
        for rau in ['../afara.md', '..\\afara.md', 'sub/../../afara.md',
                    os.path.join(self.radacina, 'afara.md')]:
            self.assertIsNone(_obsidian_safe_path(self.vault, rau), rau)

    def test_doar_note_markdown(self):
        self.assertIsNone(_obsidian_safe_path(self.vault, 'x.txt'))
        self.assertIsNone(_obsidian_safe_path(self.vault, ''))
        self.assertIsNone(_obsidian_safe_path('', 'a.md'))

    def test_o_legatura_simbolica_spre_afara_nu_scapa(self):
        legatura = os.path.join(self.vault, 'scapare.md')
        try:
            os.symlink(os.path.join(self.radacina, 'afara.md'), legatura)
        except (OSError, NotImplementedError):
            self.skipTest('legaturile simbolice cer drepturi pe masina asta')
        self.assertIsNone(_obsidian_safe_path(self.vault, 'scapare.md'))

    def test_folderele(self):
        self.assertTrue(_obsidian_safe_dir(self.vault, 'sub'))
        for rau in ['..', '../', 'sub/../..', 'nu-exista', 'a.md', '']:
            self.assertIsNone(_obsidian_safe_dir(self.vault, rau), rau)


class TabelelePermise(Test):

    def test_doar_tabelele_din_lista(self):
        self.assertEqual(safe_table('proiecte'), 'proiecte')
        for rau in ['proiecte; DROP TABLE tasks', 'sqlite_master', 'Proiecte', '']:
            with self.assertRaises(ValueError, msg=rau):
                safe_table(rau)


class SecreteleDinGit(Test):

    def test_tokenul_din_url_nu_ajunge_in_iesire(self):
        self.assertEqual(_scrub_secrets('fatal: https://ion:ghp_abc123@github.com/x/vault.git'),
                         'fatal: https://github.com/x/vault.git')
        self.assertEqual(_scrub_secrets(None), '')
        self.assertEqual(_scrub_secrets('git@github.com:x/vault.git'), 'git@github.com:x/vault.git')


class ExceptiileCsrf(CuAplicatia):
    """Singura exceptie de la CSRF pe cale e `/webhook/` (HMAC). Exceptia pe endpoint pentru
    `push.push_action` a plecat odata cu notificarile push (2026-10-03): endpointul nu mai exista."""

    def test_nu_mai_exista_exceptie_pe_endpoint(self):
        self.assertFalse(hasattr(csrf, '_EXEMPT_ENDPOINTS'))
        self.assertEqual(csrf._EXEMPT_PREFIXES, ('/webhook/',))
        self.assertNotIn('push', ' '.join(self.app_module.app.view_functions))

    def test_scriere_cu_sesiune_fara_antet_da_403_si_cu_antet_trece(self):
        self.assertEqual(self.login().status_code, 200)
        self.client.get('/api/stats')                         # cookie-ul csrf apare pe un raspuns autentificat
        token = self.client.get_cookie('csrf_token').value
        self.assertEqual(self.client.post('/api/global-tasks', json={'titlu': 'x'}).status_code, 403)
        self.assertEqual(self.client.post('/api/global-tasks', json={'titlu': 'x'},
                                          headers={'X-CSRF-Token': 'gresit'}).status_code, 403)
        r = self.client.post('/api/global-tasks', json={'titlu': 'x'}, headers={'X-CSRF-Token': token})
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))

    def test_cererile_cu_bearer_nu_cer_antet_csrf(self):
        r = self.client.post('/api/global-tasks', json={'titlu': 'x'}, headers=self.bearer())
        self.assertEqual(r.status_code, 201)

    def test_webhook_ul_nu_e_oprit_de_csrf_nici_cu_sesiune(self):
        self.assertEqual(self.login().status_code, 200)
        r = self.client.post('/webhook/deploy', data=b'{}')
        # Raspunde handlerul lui (semnatura lipseste / secretul nu e configurat), nu pagina 403 de CSRF.
        self.assertIn(r.get_data(as_text=True), ('Invalid signature', 'Webhook not configured'))


if __name__ == '__main__':
    unittest.main()

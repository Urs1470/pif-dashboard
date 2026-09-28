"""Gărzile: drumul prin vault, tabelele permise, secretele din iesirea git, tokenul push.

Fiecare functie de aici sta intre o intrare pe care n-o controlezi si ceva ce nu vrei
atins: un fisier din afara vault-ului, o tabela oarecare intr-un SQL construit, un
token de acces scris intr-un log, o actiune pe un task facuta de oricine are un link.
Niciuna n-avea test pana pe 2026-09-28.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta

from _baza import Test
from utils import safe_table
from blueprints.obsidian import _obsidian_safe_path, _obsidian_safe_dir, _scrub_secrets
from blueprints import push


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


class TokenulDeActiune(Test):
    """Capabilitate pe UN task, din butoanele notificarii (fara sesiune, fara CSRF)."""

    def setUp(self):
        self._secret = push._secret
        push._secret = b'secret-de-test'

    def tearDown(self):
        push._secret = self._secret

    def test_tokenul_bun_intoarce_taskul(self):
        self.assertEqual(push.verifica_token(push.mint_token('t-1')), 't-1')

    def test_tokenul_alterat_se_respinge(self):
        tok = push.mint_token('t-1')
        self.assertIsNone(push.verifica_token(tok[:-2] + ('xx' if not tok.endswith('xx') else 'yy')))
        corp, sig = tok.split('.', 1)
        alt_corp = push.mint_token('t-2').split('.', 1)[0]
        self.assertIsNone(push.verifica_token(alt_corp + '.' + sig), 'semnatura altui task')

    def test_tokenul_expirat_se_respinge(self):
        vechi = push.mint_token('t-1', acum=datetime.now() - timedelta(hours=push.TOKEN_VALABIL_ORE + 1))
        self.assertIsNone(push.verifica_token(vechi))

    def test_alt_secret_nu_valideaza(self):
        tok = push.mint_token('t-1')
        push._secret = b'alt-secret'
        self.assertIsNone(push.verifica_token(tok))

    def test_gunoiul_nu_arunca(self):
        for rau in ['', None, 'gunoi', 'a.b', '....']:
            self.assertIsNone(push.verifica_token(rau), rau)


if __name__ == '__main__':
    unittest.main()

"""`POST /api/obsidian/vault-sync`: ce ajunge in linia de comanda a lui git."""

import os
import unittest

from _aplicatia import CuAplicatia, DEVICE, FULL
import blueprints.obsidian as obsidian_module


class SincronizareaVault(CuAplicatia):
    """`POST /api/obsidian/vault-sync` pune `branch` in `git fetch` / `git clone`: un `branch` care
    arata a optiune (`--upload-pack=<comanda>`) ar rula comenzi. Nimeni nu trimite corp (e doar
    „forteaza acum"), deci `repo_url` si `dest` ramasi pe valorile configurate, iar `branch` trece
    printr-o regula de nume de referinta git. Tokenul de dispozitiv nu ajunge la ruta (utils.py)."""

    def setUp(self):
        super().setUp()
        self.dest = os.path.join(self.dir_temp(), 'Knowledge')
        self.patch(obsidian_module, 'DEFAULT_VAULT_DEST', self.dest)
        self.apeluri = []

        def fals(args, cwd=None, timeout=90):
            self.apeluri.append(args)
            return 0, '', ''
        self.patch(obsidian_module, '_git', fals)

    def sync(self, corp=None, token=FULL):
        return self.client.post('/api/obsidian/vault-sync', json=corp, headers=self.bearer(token))

    def clona_existenta(self):
        os.makedirs(os.path.join(self.dest, '.git'))

    def test_branch_care_arata_a_optiune_nu_ajunge_la_git(self):
        for rau in ['--upload-pack=touch /tmp/pwn', '-x', '--', '-', 'a..b', 'a b', 'x;y', 'a/', '/a',
                    'a//b', 'x.lock', 'a\nb', 'a\x00b', '@{u}', 'a~1', 'a^', 'a:b', 'a*', 'a?', 'a[b', 'a\\b',
                    'x' * 101, 7, ['main'], {'a': 1}]:
            for clona in (False, True):
                if clona and not os.path.isdir(os.path.join(self.dest, '.git')):
                    self.clona_existenta()
                r = self.sync({'branch': rau})
                self.assertEqual(r.status_code, 400, repr(rau))
                self.assertFalse(r.get_json()['ok'])
        self.assertEqual(self.apeluri, [], 'git nu s-a atins')

    def test_repo_si_dest_doar_cele_configurate(self):
        for corp in ({'repo_url': 'https://evil.example/x.git'}, {'repo_url': '--upload-pack=x'},
                     {'repo_url': 'ext::sh -c id'}, {'repo_url': 5}, {'dest': os.path.dirname(self.dest)},
                     {'dest': '/etc'}, {'dest': '~/.ssh'}, {'dest': 5}, {'dest': ['x']}):
            r = self.sync(corp)
            self.assertEqual(r.status_code, 400, repr(corp))
        self.assertEqual(self.apeluri, [])

    def test_corp_care_nu_e_obiect_da_400(self):
        self.assertEqual(self.sync(['main']).status_code, 400)
        self.assertEqual(self.apeluri, [])

    def test_fara_corp_merge_ca_inainte_si_fetch_ul_are_separator(self):
        self.clona_existenta()
        for corp in (None, {}, {'branch': 'main'}, {'branch': 'release/1.2-x_y'},
                     {'repo_url': obsidian_module.DEFAULT_VAULT_REPO_HTTPS, 'dest': self.dest}):
            self.apeluri.clear()
            r = self.sync(corp)
            self.assertEqual(r.status_code, 200, f'{corp}: {r.get_data(as_text=True)}')
            fetch = [a for a in self.apeluri if a[0] == 'fetch']
            self.assertEqual(len(fetch), 1)
            f = fetch[0]
            self.assertEqual(f[f.index('--') + 1], 'origin', 'dupa `--` vin remote-ul si ref-ul, nu optiuni')
            self.assertEqual(f[-1], (corp or {}).get('branch', 'main'))

    def test_clonarea_are_separator_inainte_de_repo(self):
        r = self.sync({'branch': 'main'})
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        clona = [a for a in self.apeluri if a[0] == 'clone'][0]
        i = clona.index('--')
        self.assertEqual(clona[i + 2], self.dest)
        self.assertEqual(clona[clona.index('--branch') + 1], 'main')
        self.assertLess(clona.index('--branch'), i)

    def test_tokenul_de_dispozitiv_nu_ajunge_la_ruta(self):
        self.assertEqual(self.sync({}, token=DEVICE).status_code, 401)
        self.assertEqual(self.apeluri, [])


if __name__ == '__main__':
    unittest.main()

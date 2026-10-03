"""Adresa clientului (`app._client_ip`): antetele de proxy conteaza doar de la un proxy de incredere.

Limita de logare (5 incercari de PIN / 5 minute / adresa) si limita generala de cereri se tin pe
adresa asta. `CF-Connecting-IP` si `X-Forwarded-For` le scrie oricine ajunge direct la
gunicorn; daca s-ar crede de la oricine, fiecare incercare de PIN ar veni „de la o alta adresa"
si limita n-ar mai limita nimic. Pe server cererile vin prin `cloudflared`, de pe aceeasi masina
(loopback), care a primit deja de la Cloudflare adresa reala.

Testele trec prin `ProxyFix`, ca in productie: cererea de logare gresita lasa adresa folosita ca
cheie in `_login_attempts`.
"""

import os
from unittest import mock

from _aplicatia import CuAplicatia

CLIENT_A = '198.51.100.7'
CLIENT_B = '198.51.100.8'
PUBLIC = '203.0.113.9'       # un socket de pe internet, care ajunge direct la gunicorn
LAN = '192.168.0.50'         # alt calculator din retea


class AdresaClientului(CuAplicatia):

    def cerere(self, socket_, **antete):
        """O logare cu PIN gresit venita de la `socket_`; intoarce raspunsul."""
        return self.client.post('/login', json={'pin': 'gresit'}, headers=antete,
                                environ_base={'REMOTE_ADDR': socket_})

    def ip_folosit(self, socket_, **antete):
        """Adresa pe care a tinut-o aplicatia pentru o cerere de la `socket_` cu antetele date."""
        self.app_module._login_attempts.clear()
        self.assertEqual(self.cerere(socket_, **antete).status_code, 401)
        chei = list(self.app_module._login_attempts)
        self.assertEqual(len(chei), 1, chei)
        return chei[0]

    def cu_proxy(self, valoare):
        p = mock.patch.dict(os.environ, {'PIF_TRUSTED_PROXIES': valoare})
        p.start()
        self.addCleanup(p.stop)

    # ------------------------------------------------- de la proxy-ul local (cloudflared)

    def test_de_la_loopback_se_crede_cf_connecting_ip(self):
        for socket_ in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
            with self.subTest(socket=socket_):
                self.assertEqual(self.ip_folosit(socket_, **{'CF-Connecting-IP': CLIENT_A}), CLIENT_A)

    def test_adresa_ipv6_a_clientului_trece_intreaga(self):
        self.assertEqual(self.ip_folosit('127.0.0.1', **{'CF-Connecting-IP': '2001:db8::7'}), '2001:db8::7')

    def test_de_la_loopback_fara_cf_connecting_ip_se_foloseste_x_forwarded_for(self):
        # ProxyFix pune adresa din X-Forwarded-For (un hop) in `remote_addr`.
        self.assertEqual(self.ip_folosit('127.0.0.1', **{'X-Forwarded-For': CLIENT_B}), CLIENT_B)

    def test_de_la_loopback_fara_niciun_antet_e_loopback(self):
        self.assertEqual(self.ip_folosit('127.0.0.1'), '127.0.0.1')

    def test_un_cf_connecting_ip_care_nu_e_adresa_se_ignora(self):
        for rau in ('nu-e-ip', '1.2.3', '', '198.51.100.7, 10.0.0.1', '<script>'):
            with self.subTest(antet=rau):
                self.assertEqual(self.ip_folosit('127.0.0.1', **{'CF-Connecting-IP': rau}), '127.0.0.1')

    def test_gunicorn_pe_socket_unix_nu_are_adresa_de_peer_si_proxy_ul_e_local(self):
        # `--bind unix:...`: REMOTE_ADDR e gol (sau o cale). La un socket UNIX ajung doar procese de pe
        # masina, deci cloudflared e local; altfel toti clientii ar primi aceeasi adresa.
        for socket_ in ('', '/run/pif-dashboard.sock'):
            with self.subTest(socket=socket_):
                self.assertEqual(self.ip_folosit(socket_, **{'CF-Connecting-IP': CLIENT_A}), CLIENT_A)
                self.assertEqual(self.ip_folosit(socket_, **{'X-Forwarded-For': CLIENT_B}), CLIENT_B)
                self.assertEqual(self.ip_folosit(socket_), '127.0.0.1')

    def test_clientii_diferiti_prin_proxy_au_fiecare_limita_lui(self):
        # Calea de productie: un singur socket (cloudflared), mai multi clienti dupa antet.
        for n in range(8):
            r = self.cerere('127.0.0.1', **{'CF-Connecting-IP': '198.51.100.%d' % (10 + n)})
            self.assertEqual(r.status_code, 401, 'fiecare client are cele 5 incercari ale lui')

    def test_acelasi_client_prin_proxy_se_opreste_la_a_sasea_incercare(self):
        statusuri = [self.cerere('127.0.0.1', **{'CF-Connecting-IP': CLIENT_A}).status_code for _ in range(7)]
        self.assertEqual(statusuri, [401] * 5 + [429] * 2)
        # Alt client, prin acelasi proxy, nu e blocat.
        self.assertEqual(self.cerere('127.0.0.1', **{'CF-Connecting-IP': CLIENT_B}).status_code, 401)

    # ------------------------------------------- de la oricine altcineva: adresa socketului

    def test_de_la_un_socket_necunoscut_antetele_nu_conteaza(self):
        for socket_ in (PUBLIC, LAN, '2001:db8::99'):
            with self.subTest(socket=socket_):
                self.assertEqual(
                    self.ip_folosit(socket_, **{'CF-Connecting-IP': CLIENT_A, 'X-Forwarded-For': CLIENT_B}),
                    socket_)
                self.assertEqual(self.ip_folosit(socket_, **{'X-Forwarded-For': CLIENT_B}), socket_)
                self.assertEqual(self.ip_folosit(socket_), socket_)

    def test_adrese_inventate_nu_ocolesc_limita_de_logare(self):
        # Atacul: portul gunicorn ajuns direct, cu o „adresa" noua la fiecare incercare de PIN.
        statusuri = []
        for n in range(8):
            antete = {'CF-Connecting-IP': '198.51.100.%d' % (100 + n), 'X-Forwarded-For': '198.51.101.%d' % n}
            statusuri.append(self.cerere(PUBLIC, **antete).status_code)
        self.assertEqual(statusuri, [401] * 5 + [429] * 3, 'a sasea incercare de la acelasi socket e oprita')
        self.assertEqual(list(self.app_module._login_attempts), [PUBLIC])

    def test_adrese_inventate_nu_umplu_tabela_limitei_generale(self):
        for n in range(20):
            self.cerere(LAN, **{'CF-Connecting-IP': '198.51.100.%d' % (100 + n)})
        self.assertEqual(set(self.app_module.rate_limit_store), {LAN})

    # --------------------------------------------------------------- PIF_TRUSTED_PROXIES

    def test_un_proxy_adaugat_in_mediu_este_crezut(self):
        # cloudflared care ajunge la gunicorn pe adresa din LAN a masinii, nu pe loopback.
        self.cu_proxy('127.0.0.1,::1,192.168.0.107')
        self.assertEqual(self.ip_folosit('192.168.0.107', **{'CF-Connecting-IP': CLIENT_A}), CLIENT_A)
        self.assertEqual(self.ip_folosit(LAN, **{'CF-Connecting-IP': CLIENT_A}), LAN, 'celelalte adrese nu')
        self.assertEqual(self.ip_folosit('127.0.0.1', **{'CF-Connecting-IP': CLIENT_A}), CLIENT_A)

    def test_o_retea_CIDR_in_mediu(self):
        self.cu_proxy('10.1.0.0/16')
        self.assertEqual(self.ip_folosit('10.1.7.7', **{'CF-Connecting-IP': CLIENT_A}), CLIENT_A)
        self.assertEqual(self.ip_folosit('10.2.7.7', **{'CF-Connecting-IP': CLIENT_A}), '10.2.7.7')
        # Cand mediul inlocuieste lista, loopback-ul nu mai e de incredere decat daca e scris.
        self.assertEqual(self.ip_folosit('127.0.0.1', **{'CF-Connecting-IP': CLIENT_A}), '127.0.0.1')

    def test_mediu_gol_sau_gresit_nu_crede_pe_nimeni(self):
        for valoare in ('', 'nu-e-adresa', ' , '):
            with self.subTest(valoare=valoare):
                self.cu_proxy(valoare)
                self.assertEqual(self.ip_folosit('127.0.0.1', **{'CF-Connecting-IP': CLIENT_A}), '127.0.0.1')

    def test_o_intrare_gresita_nu_le_strica_pe_celelalte(self):
        self.cu_proxy('nu-e-adresa, 127.0.0.1')
        self.assertEqual(self.ip_folosit('127.0.0.1', **{'CF-Connecting-IP': CLIENT_A}), CLIENT_A)

    # ---------------------------------------------------------------------------- log

    def test_logul_arata_adresa_de_incredere_nu_cea_din_antet(self):
        with self.assertLogs('pif_dashboard', level='WARNING') as log:
            self.cerere('127.0.0.1', **{'CF-Connecting-IP': CLIENT_A})
            self.cerere(PUBLIC, **{'X-Forwarded-For': CLIENT_B})
        iesire = '\n'.join(log.output)
        self.assertIn('Login failed for IP: %s' % CLIENT_A, iesire)
        self.assertIn('Login failed for IP: %s' % PUBLIC, iesire)
        self.assertNotIn(CLIENT_B, iesire, 'X-Forwarded-For de la un socket necunoscut nu ajunge in log')


if __name__ == '__main__':
    import unittest
    unittest.main()

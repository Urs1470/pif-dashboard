"""Comparatiile de secrete: un antet cu caractere non-ASCII da 401/403, nu 500."""

import unittest
from unittest import mock

from _aplicatia import CuAplicatia


class TokenCuCaractereNonAscii(CuAplicatia):
    """`hmac.compare_digest` pe doua `str` cu caractere non-ASCII arunca TypeError: un antet
    `Authorization` cu un caracter ca „é" ar fi dat 500 in loc de 401."""

    def test_bearer_non_ascii_da_401_nu_500(self):
        for ruta in ('/api/stats', '/api/sync/snapshot'):
            r = self.client.get(ruta, headers={'Authorization': 'Bearer t\u00e9st'})
            self.assertEqual(r.status_code, 401, ruta)

    def test_semnatura_webhook_non_ascii_da_403_nu_500(self):
        with mock.patch.object(self.app_module, 'get_deploy_secret', return_value='s'):
            r = self.client.post('/webhook/deploy', data=b'{}',
                                 headers={'X-Hub-Signature-256': 'sha256=\u00e9\u00e9'})
        self.assertEqual(r.status_code, 403)

    def test_antetul_csrf_non_ascii_da_403_nu_500(self):
        self.assertEqual(self.login().status_code, 200)
        self.client.get('/api/stats')
        r = self.client.post('/api/global-tasks', json={'titlu': 'x'}, headers={'X-CSRF-Token': 'caf\u00e9'})
        self.assertEqual(r.status_code, 403)


if __name__ == '__main__':
    unittest.main()

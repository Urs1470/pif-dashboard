"""Notificarile de dimineata si lantul de trimitere — in proces, fara server si fara push real.

MUTATE DIN `scripts/test_suite.py` (2026-09-28). Partea asta nu trece prin HTTP: cheama
`check_and_send_daily` cu un expeditor injectat si `send_to_all` cu `webpush` inlocuit.
Statea totusi in spatele unui login pe un server de pe :5000, deci nu rula niciodata
automat — iar curatenia ei stergea TOATE cheile `push_*` din baza pe care o gasea,
inclusiv din `pif_dashboard.db`. Aici ruleaza pe o baza noua, de unica folosinta.

Doua buguri reale stau in spatele probelor de mai jos, amandoua cu suita verde:
cheia VAPID salvata ca PEM in loc de scalarul brut (semnarea crapa inainte de retea),
si `timeout=HTTP_TIMEOUT` nedefinit in `send_to_all` (fiecare trimitere murea cu
NameError, prins si numarat ca „esuat"). Nicio notificare n-a plecat, zile la rand.
"""

import base64
import json
import os
import sqlite3
import unittest
from datetime import datetime, timedelta

from _baza import CuBazaNoua
from blueprints import push

TID = 'proba-push-0001'


class DimineataZilnica(CuBazaNoua):

    def setUp(self):
        self._secret = push._secret
        push._secret = b'secret-de-test'
        self.c = sqlite3.connect(self.db)
        self.c.execute("DELETE FROM app_settings WHERE key = ?", (push.K_DAILY,))
        self.c.execute("DELETE FROM global_tasks")
        self.c.commit()
        self.azi8 = datetime.now().replace(hour=8, minute=5, second=0, microsecond=0)

    def tearDown(self):
        push._secret = self._secret
        self.c.close()

    def _task(self, zile_vechime, status='to_do'):
        cand = (datetime.now() - timedelta(days=zile_vechime)).isoformat()
        self.c.execute("INSERT OR REPLACE INTO global_tasks (id, titlu, status, sfera, data_scadenta, "
                       "created_at, updated_at) VALUES (?, ?, ?, 'personal', '', ?, ?)",
                       (TID, '__proba_push__', status, cand, cand))
        self.c.commit()

    def test_inainte_de_ora_nu_trimite_nimic(self):
        self._task(3)
        trimise = []
        r = push.check_and_send_daily(now=self.azi8.replace(hour=7), trimite=trimise.append)
        self.assertEqual((r, trimise), ('devreme', []))

    def test_la_ora_trimite_cate_o_notificare_per_task_si_o_singura_data(self):
        self._task(3)
        trimise = []
        self.assertEqual(push.check_and_send_daily(now=self.azi8, trimite=trimise.append), 'trimis')
        unul = [p for p in trimise if p.get('title') == '__proba_push__']
        self.assertEqual(len(unul), 1)
        self.assertEqual(unul[0]['tag'], 'pif-task-%s' % TID)
        self.assertIn('focus=global:%s' % TID, unul[0]['url'])
        self.assertIs(unul[0].get('actions'), True)
        self.assertEqual(push.verifica_token(unul[0]['token']), TID)
        # A doua rulare in aceeasi zi (al doilea worker, bucla de 5 minute): nimic.
        self.assertEqual(push.check_and_send_daily(now=self.azi8, trimite=trimise.append), 'claimed-gata')
        self.assertEqual(len(trimise), len(unul))

    def test_zi_fara_taskuri_consuma_ziua_fara_notificare(self):
        self._task(3, status='done')
        trimise = []
        self.assertEqual(push.check_and_send_daily(now=self.azi8, trimite=trimise.append), 'nimic')
        self.assertEqual(trimise, [])

    def test_taskul_de_o_zi_e_prea_proaspat(self):
        self._task(1)
        trimise = []
        self.assertEqual(push.check_and_send_daily(now=self.azi8, trimite=trimise.append), 'nimic')


@unittest.skipUnless(push._PUSH_OK, 'pywebpush lipseste pe masina asta — lantul real de trimitere nu se poate proba')
class LantulDeTrimitere(CuBazaNoua):

    def _abonament_valid(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        k = ec.generate_private_key(ec.SECP256R1())
        p256dh = base64.urlsafe_b64encode(k.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint)).decode().rstrip('=')
        auth = base64.urlsafe_b64encode(os.urandom(16)).decode().rstrip('=')
        return p256dh, auth

    def test_cheia_privata_e_scalarul_brut_citit_de_py_vapid(self):
        priv, _pub = push._chei_vapid()
        self.assertNotIn('-----BEGIN', priv)
        self.assertEqual(len(base64.urlsafe_b64decode(priv + '=' * (-len(priv) % 4))), 32)

    def test_criptarea_si_semnarea_merg_pana_la_retea(self):
        from pywebpush import webpush
        priv, _pub = push._chei_vapid()
        p256dh, auth = self._abonament_valid()
        try:
            webpush(subscription_info={'endpoint': 'https://fcm.googleapis.invalid:9/x',
                                       'keys': {'p256dh': p256dh, 'auth': auth}},
                    data=json.dumps({'title': 'proba'}), vapid_private_key=priv,
                    vapid_claims={'sub': push.PUSH_SUB}, timeout=3)
            self.fail('trimiterea spre un host mort n-avea cum sa reuseasca')
        except AssertionError:
            raise
        except Exception as e:
            t, m = type(e).__name__, str(e)
            retea = ('Connection' in t or 'Connection' in m or 'Max retries' in m
                     or 'resolve' in m.lower() or 'timed out' in m.lower())
            self.assertTrue(retea, 'trimiterea crapa INAINTE de retea: %s: %s' % (t, m[:120]))

    def test_send_to_all_cheama_webpush_cu_timeout_numeric(self):
        p256dh, auth = self._abonament_valid()
        apeluri = []
        original = push.webpush
        push.webpush = lambda **kw: apeluri.append(kw)
        try:
            push._salveaza_abonamente({'proba': {'endpoint': 'https://fcm.googleapis.invalid/proba',
                                                 'keys': {'p256dh': p256dh, 'auth': auth}}})
            trimise, esuate = push.send_to_all({'title': 'proba', 'body': 'x'})
        finally:
            push.webpush = original
        motiv = push.get_app_setting(push.K_LAST_ERROR, '') or ''
        self.assertEqual((trimise, esuate), (1, 0), motiv[:120])
        self.assertEqual(len(apeluri), 1)
        self.assertIsInstance(apeluri[0].get('timeout'), (int, float))
        self.assertGreater(apeluri[0]['timeout'], 0)


if __name__ == '__main__':
    unittest.main()

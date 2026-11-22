"""Transportul FCM (`blueprints/fcm.py`): semnatura RS256 fara biblioteca de criptografie, tokenul de
acces, trimiterea si ce face cu erorile. Nicio proba nu atinge reteaua: `fcm._http_post` e inlocuit.

Ce se pazeste, tacut daca se strica:
  - semnatura RS256 produsa de cod e IDENTICA cu cea a `openssl dgst -sha256 -sign` (PKCS#1 v1.5 e
    deterministic), pentru o cheie PKCS#8 (formatul Google) si pentru una PKCS#1;
  - JWT-ul are antet RS256, `iss`/`scope`/`aud`/`iat`/`exp` (o ora) si trei parti base64url fara `=`;
  - tokenul de acces se tine in memorie (a doua trimitere nu cere altul) si se arunca la 401;
  - 404 sau `UNREGISTERED` pun tokenul in `nregistrate`; 503, retea cazuta, timeout: in `erori`,
    fara exceptie; nicio eroare nu contine tokenul intreg, tokenul de acces sau cheia privata;
  - tot apelul are plafon de timp: nicio cerere nu primeste mai mult de TIMEOUT_CERERE, iar fara timp
    ramas nu pleaca nicio cerere;
  - fara `FCM_SERVICE_ACCOUNT_FILE` (sau cu un fisier stricat): `configurat()` e False si nu se ridica nimic.
"""

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock

from _baza import Test
from blueprints import fcm

OPENSSL = shutil.which('openssl')
TOKEN = 'dGVzdC10b2tlbi1mY20tMTIzNDU2Nzg5MC1hYmNkZWY'
ACCES = 'ya29.token-de-acces-secret'


def _ruleaza(*argv, intrare=None):
    return subprocess.run(argv, input=intrare, capture_output=True, check=True).stdout


class Chei:
    """O cheie RSA de proba, facuta o data pe proces (generarea dureaza ~0,3 s)."""
    pkcs8 = pkcs1 = pub = None
    dir = None

    @classmethod
    def pregateste(cls):
        if cls.pkcs8 is not None:
            return
        cls.dir = tempfile.mkdtemp(prefix='pif-fcm-')
        cls.pkcs8 = _ruleaza(OPENSSL, 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048').decode()
        cale = os.path.join(cls.dir, 'k8.pem')
        with open(cale, 'w') as fh:
            fh.write(cls.pkcs8)
        cls.pkcs1 = _ruleaza(OPENSSL, 'rsa', '-in', cale, '-traditional', '-outform', 'PEM').decode()
        cls.pub = os.path.join(cls.dir, 'pub.pem')
        with open(cls.pub, 'wb') as fh:
            fh.write(_ruleaza(OPENSSL, 'rsa', '-in', cale, '-pubout'))
        cls.cale8 = cale


@unittest.skipUnless(OPENSSL, 'openssl lipseste: nu se poate genera o cheie de proba')
class Semnatura(Test):

    @classmethod
    def setUpClass(cls):
        Chei.pregateste()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(Chei.dir, ignore_errors=True)
        Chei.pkcs8 = None

    def test_cele_doua_formate_de_cheie_dau_aceleasi_numere(self):
        self.assertTrue(Chei.pkcs8.startswith('-----BEGIN PRIVATE KEY-----'))
        self.assertTrue(Chei.pkcs1.startswith('-----BEGIN RSA PRIVATE KEY-----'))
        self.assertEqual(fcm.cheie_rsa(Chei.pkcs8), fcm.cheie_rsa(Chei.pkcs1))
        n, e, d = fcm.cheie_rsa(Chei.pkcs8)
        self.assertEqual((n.bit_length(), e), (2048, 65537))

    def test_semnatura_e_identica_cu_cea_din_openssl(self):
        mesaj = b'antet.corp de semnat'
        fisier = os.path.join(Chei.dir, 'mesaj.txt')
        with open(fisier, 'wb') as fh:
            fh.write(mesaj)
        asteptat = _ruleaza(OPENSSL, 'dgst', '-sha256', '-sign', Chei.cale8, fisier)
        self.assertEqual(fcm.semneaza_rs256(mesaj, *fcm.cheie_rsa(Chei.pkcs8)), asteptat)

    def test_jwt_are_forma_ceruta_de_google_si_se_verifica_cu_cheia_publica(self):
        n, e, d = fcm.cheie_rsa(Chei.pkcs8)
        jwt = fcm.jwt_rs256({'iss': 'cont@proiect.iam', 'scope': fcm.SCOPE, 'aud': fcm.URL_TOKEN,
                             'iat': 1000, 'exp': 4600}, n, e, d)
        antet, corp, semn = jwt.split('.')
        self.assertNotIn('=', jwt)

        def decodeaza(b):
            return base64.urlsafe_b64decode(b + '=' * (-len(b) % 4))
        self.assertEqual(json.loads(decodeaza(antet)), {'alg': 'RS256', 'typ': 'JWT'})
        self.assertEqual(json.loads(decodeaza(corp)), {'iss': 'cont@proiect.iam', 'scope': fcm.SCOPE,
                                                        'aud': fcm.URL_TOKEN, 'iat': 1000, 'exp': 4600})
        f_mesaj, f_semn = os.path.join(Chei.dir, 'jm.txt'), os.path.join(Chei.dir, 'js.bin')
        with open(f_mesaj, 'wb') as fh:
            fh.write(('%s.%s' % (antet, corp)).encode())
        with open(f_semn, 'wb') as fh:
            fh.write(decodeaza(semn))
        verificare = subprocess.run([OPENSSL, 'dgst', '-sha256', '-verify', Chei.pub, '-signature', f_semn, f_mesaj],
                                    capture_output=True)
        self.assertEqual(verificare.returncode, 0, verificare.stdout + verificare.stderr)

    def test_o_cheie_care_nu_se_potriveste_nu_semneaza(self):
        n, e, d = fcm.cheie_rsa(Chei.pkcs8)
        with self.assertRaises(ValueError):
            fcm.semneaza_rs256(b'x', n, e, d + 2)              # `d` stricat: verificarea cu `e` o prinde

    def test_chei_ilizibile_dau_valueerror(self):
        for pem in ('', 'nu e pem', '-----BEGIN PUBLIC KEY-----\nAAAA\n-----END PUBLIC KEY-----',
                    '-----BEGIN PRIVATE KEY-----\n!!!!\n-----END PRIVATE KEY-----',
                    '-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----',
                    '-----BEGIN ENCRYPTED PRIVATE KEY-----\nAAAA\n-----END ENCRYPTED PRIVATE KEY-----'):
            with self.subTest(pem=pem[:30]):
                with self.assertRaises(ValueError):
                    fcm.cheie_rsa(pem)


@unittest.skipUnless(OPENSSL, 'openssl lipseste: nu se poate genera o cheie de proba')
class Trimitere(Test):
    """`trimite_date` cu `_http_post` inlocuit: ce cereri pleaca si ce se intoarce."""

    @classmethod
    def setUpClass(cls):
        Chei.pregateste()
        cls.dir = tempfile.mkdtemp(prefix='pif-fcm-cont-')
        cls.cont = os.path.join(cls.dir, 'cont.json')
        with open(cls.cont, 'w') as fh:
            json.dump({'type': 'service_account', 'project_id': 'proiect-test', 'client_email': 'cont@proiect-test.iam',
                       'private_key': Chei.pkcs8}, fh)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)
        shutil.rmtree(Chei.dir, ignore_errors=True)
        Chei.pkcs8 = None

    def setUp(self):
        env = mock.patch.dict(os.environ, {'FCM_SERVICE_ACCOUNT_FILE': self.cont})
        env.start()
        self.addCleanup(env.stop)
        fcm._CONT.update(cale=None, mtime=None, val=None)
        fcm._TOKEN.update(valoare=None, expira=0.0)
        self.cereri = []
        self.raspunsuri = []                                   # (cod, corp) in ordinea cererilor

    def http(self, url, date, antete, timeout):
        self.cereri.append({'url': url, 'date': date, 'antete': antete, 'timeout': timeout})
        r = self.raspunsuri.pop(0) if self.raspunsuri else (200, b'{}')
        if isinstance(r, Exception):
            raise r
        return r

    def cu_http(self, *raspunsuri):
        self.raspunsuri = list(raspunsuri)
        p = mock.patch.object(fcm, '_http_post', self.http)
        p.start()
        self.addCleanup(p.stop)

    @staticmethod
    def acces(expira=3600):
        return (200, json.dumps({'access_token': ACCES, 'expires_in': expira}).encode())

    DATE = {'v': '1', 'tip': 'alerta', 'msg_id': 'm_ab12cd', 'titlu': 'T', 'text': 'x'}

    def test_trimitere_reusita_pune_tokenul_de_acces_si_mesajul_de_date(self):
        self.cu_http(self.acces(), (200, b'{"name":"projects/p/messages/1"}'))
        r = fcm.trimite_date([TOKEN], self.DATE, 'HIGH')
        self.assertEqual(r, {'trimise': 1, 'erori': [], 'nregistrate': []})
        oauth, send = self.cereri
        self.assertEqual(oauth['url'], 'https://oauth2.googleapis.com/token')
        self.assertIn(b'grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer', oauth['date'])
        self.assertEqual(send['url'], 'https://fcm.googleapis.com/v1/projects/proiect-test/messages:send')
        self.assertEqual(send['antete']['Authorization'], 'Bearer ' + ACCES)
        corp = json.loads(send['date'])
        self.assertEqual(corp, {'message': {'token': TOKEN, 'android': {'priority': 'HIGH', 'ttl': '86400s'},
                                            'data': self.DATE}})
        self.assertNotIn('notification', corp['message'], 'mesaj DOAR de date')

    def test_assertia_oauth_e_un_jwt_cu_iss_si_scope_ale_contului(self):
        self.cu_http(self.acces(), (200, b'{}'))
        fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        asertia = dict(p.split('=') for p in self.cereri[0]['date'].decode().split('&'))['assertion']
        corp = asertia.split('.')[1]
        claims = json.loads(base64.urlsafe_b64decode(corp + '=' * (-len(corp) % 4)))
        self.assertEqual((claims['iss'], claims['scope'], claims['aud']),
                         ('cont@proiect-test.iam', fcm.SCOPE, fcm.URL_TOKEN))
        self.assertEqual(claims['exp'] - claims['iat'], 3600)

    def test_tokenul_de_acces_se_reutilizeaza(self):
        self.cu_http(self.acces(), (200, b'{}'), (200, b'{}'))
        fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        self.assertEqual(r['trimise'], 1)
        self.assertEqual([c['url'] for c in self.cereri].count(fcm.URL_TOKEN), 1)

    def test_tokenul_de_acces_expirat_se_cere_din_nou(self):
        self.cu_http(self.acces(expira=30), (200, b'{}'), self.acces(), (200, b'{}'))   # 30 s < marja de 60 s
        fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        self.assertEqual([c['url'] for c in self.cereri].count(fcm.URL_TOKEN), 2)

    def test_401_arunca_tokenul_de_acces(self):
        self.cu_http(self.acces(), (401, b'{"error":{"status":"UNAUTHENTICATED"}}'), self.acces(), (200, b'{}'))
        r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        self.assertEqual((r['trimise'], r['nregistrate']), (0, []))
        self.assertIn('HTTP 401 UNAUTHENTICATED', r['erori'][0])
        self.assertEqual(fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')['trimise'], 1)
        self.assertEqual([c['url'] for c in self.cereri].count(fcm.URL_TOKEN), 2)

    def test_404_si_unregistered_scot_tokenul(self):
        unreg = json.dumps({'error': {'code': 404, 'status': 'NOT_FOUND', 'message': 'x', 'details': [
            {'@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError', 'errorCode': 'UNREGISTERED'}]}}).encode()
        for cod, corp in ((404, b'{}'), (404, unreg), (400, unreg)):
            with self.subTest(cod=cod):
                fcm._TOKEN.update(valoare=None, expira=0.0)
                self.cu_http(self.acces(), (cod, corp))
                r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
                self.assertEqual((r['trimise'], r['nregistrate']), (0, [TOKEN]))
                self.assertIn('UNREGISTERED', r['erori'][0])

    def test_un_token_bun_si_unul_mort_in_aceeasi_trimitere(self):
        self.cu_http(self.acces(), (200, b'{}'), (404, b'{}'))
        r = fcm.trimite_date([TOKEN, 'altul-' + TOKEN], self.DATE, 'NORMAL')
        self.assertEqual((r['trimise'], r['nregistrate'], len(r['erori'])), (1, ['altul-' + TOKEN], 1))

    def test_erorile_de_retea_si_de_server_intra_in_erori_fara_exceptie(self):
        for raspuns, cuvant in ((OSError('conexiune cazuta pe https://fcm.googleapis.com/x'), 'retea (OSError)'),
                                (TimeoutError('timed out'), 'retea (TimeoutError)'),
                                ((503, b'<html>'), 'HTTP 503'),
                                ((400, b'{"error":{"status":"INVALID_ARGUMENT"}}'), 'HTTP 400 INVALID_ARGUMENT')):
            with self.subTest(cuvant=cuvant):
                fcm._TOKEN.update(valoare=None, expira=0.0)
                self.cu_http(self.acces(), raspuns)
                r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
                self.assertEqual((r['trimise'], r['nregistrate']), (0, []))
                self.assertIn(cuvant, r['erori'][0])
                self.assertNotIn('googleapis', r['erori'][0], 'textul erorii de retea nu se copiaza')

    def test_nicio_eroare_nu_poarta_tokenul_intreg_nici_secretele(self):
        self.cu_http(self.acces(), (503, b'{}'))
        r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        text = json.dumps(r)
        self.assertNotIn(TOKEN, text)
        self.assertIn(TOKEN[-6:], text)
        self.assertNotIn(ACCES, text)
        self.assertNotIn('PRIVATE KEY', text)

    def test_eroarea_la_cererea_de_token_oauth(self):
        self.cu_http((400, b'{"error":"invalid_grant","error_description":"Invalid JWT Signature."}'))
        r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        self.assertEqual(r['trimise'], 0)
        self.assertEqual(r['erori'], ['token OAuth: HTTP 400 invalid_grant'])
        self.assertEqual(len(self.cereri), 1, 'fara token de acces nu se mai incearca trimiterea')

    def test_fiecare_cerere_are_timeout_si_nu_depaseste_plafonul(self):
        self.cu_http(self.acces(), (200, b'{}'), (200, b'{}'))
        fcm.trimite_date([TOKEN, TOKEN + 'x'], self.DATE, 'NORMAL')
        self.assertEqual(len(self.cereri), 3)
        for c in self.cereri:
            self.assertLessEqual(c['timeout'], fcm.TIMEOUT_CERERE)
            self.assertGreater(c['timeout'], 0)
        self.assertLessEqual(fcm.TIMEOUT_CERERE, fcm.TIMP_MAXIM)
        self.assertLessEqual(fcm.TIMP_MAXIM, 10)

    def test_fara_timp_ramas_nu_pleaca_nicio_cerere(self):
        self.cu_http(self.acces())
        r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL', timp_maxim=0)
        self.assertEqual(r['erori'], ['timp depasit'])
        self.assertEqual(self.cereri, [])

    def test_timpul_se_imparte_intre_cereri(self):
        """Dupa token, timpul ramas taie timeout-ul fiecarei trimiteri; cand se termina, restul nu pleaca."""
        ceas = iter([0.0, 0.0, 9.0, 9.9, 9.9])                  # limita 10; token la 0.0, trimiterea 1 la 9.0, trimiterea 2 la 9.9 (ramas 0.1)
        self.cu_http(self.acces(), (200, b'{}'), (200, b'{}'))
        with mock.patch.object(fcm.time, 'monotonic', lambda: next(ceas)):
            r = fcm.trimite_date([TOKEN, TOKEN + 'x', TOKEN + 'y'], self.DATE, 'NORMAL')
        self.assertEqual(r['trimise'], 1)
        self.assertIn('timp depasit', r['erori'][-1])
        self.assertAlmostEqual(self.cereri[1]['timeout'], 1.0, places=3)     # 10 - 9.0

    def test_plafonul_listei_de_erori(self):
        self.cu_http(self.acces(), *[(503, b'{}')] * 30)
        r = fcm.trimite_date(['t%02d' % i + TOKEN for i in range(30)], self.DATE, 'NORMAL')
        self.assertEqual(len(r['erori']), fcm.MAX_ERORI)


    # ------------------------------------------------------------------ recenzia 2026-11-22

    def test_details_cu_alta_forma_nu_ridica(self):
        """`details` care nu e lista (sau cu elemente care nu sunt obiecte) dadea TypeError din `trimite_date`."""
        for details in (5, 'x', {'a': 1}, [5, None, 'x'], [{'errorCode': 7, 'fieldViolations': 'nu'}], None):
            with self.subTest(details=details):
                fcm._TOKEN.update(valoare=None, expira=0.0)
                self.cu_http(self.acces(), (400, json.dumps({'error': {'status': 'INVALID_ARGUMENT', 'details': details}}).encode()))
                r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
                self.assertEqual((r['trimise'], r['nregistrate']), (0, []))
                self.assertIn('HTTP 400 INVALID_ARGUMENT', r['erori'][0])

    def test_corpuri_de_eroare_ciudate_nu_ridica(self):
        for corp in (b'', b'[]', b'null', b'{"error": 5}', b'{"error": {"details": [[]]}}', b'\xff\xfe', b'{"error": {"status": 7}}'):
            with self.subTest(corp=corp):
                fcm._TOKEN.update(valoare=None, expira=0.0)
                self.cu_http(self.acces(), (500, corp))
                r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
                self.assertEqual((r['trimise'], r['nregistrate'], len(r['erori'])), (0, [], 1))

    def test_invalid_argument_pe_campul_token_scoate_tokenul(self):
        corp = json.dumps({'error': {'code': 400, 'status': 'INVALID_ARGUMENT', 'message': 'x', 'details': [
            {'@type': 'type.googleapis.com/google.rpc.BadRequest',
             'fieldViolations': [{'field': 'message.token', 'description': 'The registration token is not a valid FCM registration token'}]}]}}).encode()
        self.cu_http(self.acces(), (400, corp))
        r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        self.assertEqual((r['trimise'], r['nregistrate']), (0, [TOKEN]))
        self.assertIn('INVALID_ARGUMENT (token)', r['erori'][0])

    def test_invalid_argument_pe_alt_camp_nu_scoate_tokenul(self):
        corp = json.dumps({'error': {'status': 'INVALID_ARGUMENT', 'details': [
            {'fieldViolations': [{'field': 'message.data', 'description': 'prea mare'}]}]}}).encode()
        self.cu_http(self.acces(), (400, corp))
        r = fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')
        self.assertEqual((r['trimise'], r['nregistrate']), (0, []), 'un mesaj prost nu e un token prost')

    def test_campul_token_fara_invalid_argument_sau_cu_alt_cod_nu_scoate_tokenul(self):
        for cod, stare in ((500, 'INVALID_ARGUMENT'), (400, 'FAILED_PRECONDITION')):
            fcm._TOKEN.update(valoare=None, expira=0.0)
            corp = json.dumps({'error': {'status': stare, 'details': [{'fieldViolations': [{'field': 'message.token'}]}]}}).encode()
            self.cu_http(self.acces(), (cod, corp))
            self.assertEqual(fcm.trimite_date([TOKEN], self.DATE, 'NORMAL')['nregistrate'], [], (cod, stare))


class ServerLocal:
    """Un server TCP de proba pe 127.0.0.1: `scenariu(conexiune)` ruleaza intr-un fir pe fiecare conexiune."""

    def __init__(self, scenariu):
        self.srv = socket.socket()
        self.srv.bind(('127.0.0.1', 0))
        self.srv.listen(8)
        self.port = self.srv.getsockname()[1]
        self.scenariu = scenariu
        self.inchis = False
        threading.Thread(target=self._serveste, daemon=True).start()

    def _serveste(self):
        while not self.inchis:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._una, args=(c,), daemon=True).start()

    def _una(self, c):
        try:
            c.settimeout(30)
            citit = b''
            while b'\r\n\r\n' not in citit:
                bucata = c.recv(65536)
                if not bucata:
                    return
                citit += bucata
            self.scenariu(c)
        except OSError:
            pass
        finally:
            c.close()

    @property
    def url(self):
        return 'http://127.0.0.1:%d/v1/projects/%%s/messages:send' % self.port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.inchis = True
        self.srv.close()


def _picatura(c, octeti, pauza, cati):
    for _ in range(cati):
        c.sendall(octeti)
        time.sleep(pauza)


class HttpPost(Test):
    """`_http_post` pe un server local: raspunsul real si, mai ales, plafonul de timp pe TOATA cererea."""

    def test_raspuns_normal_si_cod_de_eroare(self):
        def raspunde(c):
            c.sendall(b'HTTP/1.1 404 Not Found\r\nContent-Length: 13\r\nConnection: close\r\n\r\n{"a": "bine"}')
        with ServerLocal(raspunde) as srv:
            cod, corp = fcm._http_post(srv.url % 'p', b'{}', {'Content-Type': 'application/json'}, 5)
        self.assertEqual((cod, corp), (404, b'{"a": "bine"}'))

    def test_corpul_trimis_ajunge_intreg(self):
        def raspunde(c):
            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')
        with ServerLocal(raspunde) as srv:
            self.assertEqual(fcm._http_post(srv.url % 'p', b'x' * 100000, {}, 5), (200, b'{}'))

    def test_conexiune_refuzata_e_oserror(self):
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        port = s.getsockname()[1]
        s.close()
        with self.assertRaises(OSError):
            fcm._http_post('http://127.0.0.1:%d/x' % port, b'{}', {}, 5)

    def test_raspuns_taiat_la_jumatate_e_oserror_nu_httpexception(self):
        def taie(c):
            c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 40\r\n\r\nabc')
        with ServerLocal(taie) as srv:
            with self.assertRaises(OSError):
                fcm._http_post(srv.url % 'p', b'{}', {}, 5)

    def test_corpul_trimis_picatura_cu_picatura_se_opreste_la_plafon(self):
        """Fiecare octet vine inainte de timeout-ul unei operatii de socket: cu `urlopen(timeout=)` cererea
        dura 117 s. Plafonul e pe toata cererea."""
        with ServerLocal(lambda c: (c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 40\r\n\r\n'), _picatura(c, b'x', 0.2, 40))) as srv:
            t0 = time.monotonic()
            with self.assertRaises(TimeoutError):
                fcm._http_post(srv.url % 'p', b'{}', {}, 1.0)
            self.assertLess(time.monotonic() - t0, 2.0)

    def test_antetele_trimise_picatura_cu_picatura_se_opreste_la_plafon(self):
        with ServerLocal(lambda c: _picatura(c, b'H', 0.2, 40)) as srv:
            t0 = time.monotonic()
            with self.assertRaises(TimeoutError):
                fcm._http_post(srv.url % 'p', b'{}', {}, 1.0)
            self.assertLess(time.monotonic() - t0, 2.0)

    def test_server_care_tace_se_opreste_la_plafon(self):
        with ServerLocal(lambda c: time.sleep(5)) as srv:
            t0 = time.monotonic()
            with self.assertRaises(TimeoutError):
                fcm._http_post(srv.url % 'p', b'{}', {}, 0.5)
            self.assertLess(time.monotonic() - t0, 1.5)

    def test_cronometrul_nu_ramane_pornit(self):
        inainte = threading.active_count()
        with ServerLocal(lambda c: c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')) as srv:
            for _ in range(5):
                fcm._http_post(srv.url % 'p', b'{}', {}, 30)
            time.sleep(0.2)
        self.assertLessEqual(threading.active_count(), inainte + 1, 'niciun Timer de 30 s ramas')

    @unittest.skipUnless(OPENSSL, 'openssl lipseste')
    def test_tot_apelul_trimite_date_respecta_plafonul_cu_un_server_picatura(self):
        Chei.pregateste()
        dir_cont = tempfile.mkdtemp(prefix='pif-fcm-pic-')
        self.addCleanup(shutil.rmtree, dir_cont, ignore_errors=True)
        cont = os.path.join(dir_cont, 'cont.json')
        with open(cont, 'w') as fh:
            json.dump({'project_id': 'p', 'client_email': 'c@p.iam', 'private_key': Chei.pkcs8}, fh)
        env = mock.patch.dict(os.environ, {'FCM_SERVICE_ACCOUNT_FILE': cont})
        env.start()
        self.addCleanup(env.stop)
        fcm._CONT.update(cale=None, mtime=None, val=None)
        self.assertTrue(fcm.configurat())                         # incarca contul (si reseteaza tokenul de acces)
        fcm._TOKEN.update(valoare='acces', expira=time.time() + 3000)
        with ServerLocal(lambda c: (c.sendall(b'HTTP/1.1 200 OK\r\nContent-Length: 40\r\n\r\n'), _picatura(c, b'x', 0.3, 40))) as srv:
            with mock.patch.object(fcm, 'URL_SEND', srv.url):
                t0 = time.monotonic()
                r = fcm.trimite_date([TOKEN, TOKEN + 'x', TOKEN + 'y'], {'a': 'b'}, 'NORMAL', timp_maxim=1.5)
                durata = time.monotonic() - t0
        self.assertLess(durata, 3.0, 'plafon 1.5 s pe tot apelul, cu trei tokeni')
        self.assertEqual(r['trimise'], 0)
        self.assertIn('retea (TimeoutError)', r['erori'][0])
        self.assertIn('timp depasit', r['erori'][-1])


class FaraCont(Test):

    def setUp(self):
        fcm._CONT.update(cale=None, mtime=None, val=None)
        self.dir = tempfile.mkdtemp(prefix='pif-fcm-fara-')
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)

    def cu_env(self, valoare):
        env = mock.patch.dict(os.environ, {'FCM_SERVICE_ACCOUNT_FILE': valoare})
        env.start()
        self.addCleanup(env.stop)

    def test_fara_variabila_nu_e_configurat_si_nu_pleaca_nimic(self):
        with mock.patch.dict(os.environ):
            os.environ.pop('FCM_SERVICE_ACCOUNT_FILE', None)
            with mock.patch.object(fcm, '_http_post', side_effect=AssertionError('reteaua nu se atinge')):
                self.assertFalse(fcm.configurat())
                r = fcm.trimite_date([TOKEN], {}, 'NORMAL')
        self.assertEqual((r['trimise'], r['nregistrate']), (0, []))

    def test_fisier_lipsa_sau_stricat_nu_e_configurat(self):
        continuturi = {'lipsa': None, 'gol': '', 'nu_json': '{', 'lista': '[]', 'fara_campuri': '{"type": "service_account"}',
                       'cheie_proasta': json.dumps({'project_id': 'p', 'client_email': 'e@x', 'private_key': 'nu e pem'}),
                       'proiect_cu_slash': json.dumps({'project_id': 'a/b', 'client_email': 'e@x',
                                                       'private_key': '-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----'})}
        for nume, continut in continuturi.items():
            with self.subTest(nume):
                cale = os.path.join(self.dir, nume + '.json')
                if continut is not None:
                    with open(cale, 'w') as fh:
                        fh.write(continut)
                with mock.patch.dict(os.environ, {'FCM_SERVICE_ACCOUNT_FILE': cale}):
                    self.assertFalse(fcm.configurat())
                    self.assertEqual(fcm.trimite_date([TOKEN], {}, 'NORMAL')['trimise'], 0)


if __name__ == '__main__':
    unittest.main()

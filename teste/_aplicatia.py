"""Aplicatia Flask in proces, pentru testele care trec prin RUTE (APK, Torqa web, login).

Ce pune in mediu cat ruleaza o clasa (si pune la loc la sfarsit): tokenul de masina, cel
de dispozitiv si un PIN de test — niciunul nu e al lui Ion. Ce muta din aplicatie
(directoarele `uploads/app` si `uploads/torqa-web`) se muta intr-un director temporar:
un test nu scrie niciodata in `uploads/` din proiect, unde pe masina de dezvoltare pot
sta fisiere adevarate.

Modul `_baza` ramane al testelor fara aplicatie; asta se aseaza peste `CuBazaNoua`, fiindca
rutele de API cer baza.
"""

import io
import os
import shutil
import tempfile
import warnings
import zipfile
from unittest import mock

from _baza import CuBazaNoua

FULL = 'token-masina-test'
DEVICE = 'token-dispozitiv-test'
PIN = '135790'

# Un build minimal, cu aceleasi tipuri de fisiere ca al Angular (cel real: ~1200 de fisiere,
# vezi decizia 2026-10-01-torqa-web-si-canalul-apk.md): documentul, bundle-uri cu hash in
# nume, fisierele care se reverifica mereu, resurse nehash-uite sub `assets/`.
BUILD = {
    'index.html': '<!doctype html><html><head><base href="/torqa/"><title>Torqa</title></head>'
                  '<body><app-root></app-root></body></html>',
    'main-ABCDEFGH.js': 'console.log("main");',
    'chunk-QRSTUVWX.js': 'export const x = 1;',
    'styles-ABCDEFGH.css': 'body{margin:0}',
    'manifest.json': '{"name":"Torqa","start_url":"./index.html"}',
    'ngsw.json': '{"configVersion":1,"index":"/torqa/index.html"}',
    'ngsw-worker.js': '// ngsw',
    'favicon.ico': b'\x00\x00\x01\x00\x01\x00',
    'assets/icons/icon-72x72.png': b'\x89PNG\r\n\x1a\n',
    'assets/i18n/en.json': '{"hello":"hi"}',
    'media/open-sans-latin-400-normal-HCAVHEYW.woff2': b'wOF2\x00\x01\x00\x00',
}


def _octeti(continut):
    return continut if isinstance(continut, bytes) else continut.encode('utf-8')


def zip_cu(*intrari):
    """Un zip in memorie din perechi (nume sau ZipInfo, continut). Nu sanitizeaza numele:
    testele au nevoie de `../x`, de cai absolute si de nume duplicate."""
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')               # `Duplicate name`, cand testul il vrea
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for nume, continut in intrari:
                zf.writestr(nume, _octeti(continut))
    return buf.getvalue()


def zip_build(extra=None, fara=()):
    """Zip-ul lui BUILD, cu fisiere in plus sau cu continut schimbat (`extra`: {nume:
    continut}) si fara cateva (`fara`: nume)."""
    fisiere = dict(BUILD)
    fisiere.update(extra or {})
    for nume in fara:
        fisiere.pop(nume, None)
    return zip_cu(*fisiere.items())


class CuAplicatia(CuBazaNoua):
    """`self.client` (proaspat la fiecare test), `self.login()`, `self.dir_temp()`,
    `self.patch(obiect, nume, valoare)`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._env = {k: os.environ.get(k) for k in ('PIF_API_TOKEN', 'PIF_DEVICE_TOKEN', 'PIF_DASHBOARD_PIN')}
        os.environ['PIF_API_TOKEN'] = FULL
        os.environ['PIF_DEVICE_TOKEN'] = DEVICE
        os.environ['PIF_DASHBOARD_PIN'] = PIN
        import app as app_module
        # Schema o scrie deja CuBazaNoua; primul request n-are de ce s-o refaca (init_db) si
        # sa logheze o pornire a aplicatiei.
        app_module._startup_initialized = True
        cls.app_module = app_module
        # Hash-ul PIN-ului se tine minte la primul login si nu se mai recalculeaza: sa nu
        # mostenim unul facut cu alt PIN, nici sa-l lasam pe al nostru celorlalte teste.
        cls._hash_pin = getattr(app_module.get_hashed_pin, '_hash', None)
        if cls._hash_pin is not None:
            del app_module.get_hashed_pin._hash

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls.app_module.get_hashed_pin, '_hash'):
            del cls.app_module.get_hashed_pin._hash
        if cls._hash_pin is not None:
            cls.app_module.get_hashed_pin._hash = cls._hash_pin
        for k, v in cls._env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        super().tearDownClass()

    def setUp(self):
        # Limitele de cereri sunt in memoria procesului si se aduna intre teste.
        self.app_module.rate_limit_store.clear()
        self.app_module.login_limit.goleste()
        self.client = self.app_module.app.test_client()

    def login(self, **extra):
        self.app_module.login_limit.goleste()
        return self.client.post('/login', json={'pin': PIN, **extra})

    def dir_temp(self):
        d = tempfile.mkdtemp(prefix='pif-uploads-')
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        return d

    def patch(self, obiect, nume, valoare):
        p = mock.patch.object(obiect, nume, valoare)
        p.start()
        self.addCleanup(p.stop)

    @staticmethod
    def bearer(token=FULL):
        return {'Authorization': 'Bearer %s' % token}

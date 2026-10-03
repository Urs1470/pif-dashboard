"""Torqa web: urcarea build-ului, schimbarea atomica, servirea de la `/torqa/`, CSP, CSRF.

Ce se pazeste, in ordinea in care se strica mai greu de vazut:
  - un build respins (zip stricat, `../`, cale absoluta, legatura simbolica, fara
    index.html) NU atinge versiunea live si nu lasa nimic pe disc;
  - schimbarea versiunii e atomica (pointer rescris cu `os.replace`) si raman live + 2
    anterioare, nu mai multe, nu mai putine;
  - documentul (`/torqa/`, orice cale fara extensie) cere login, fisierele nu — si fisierele
    n-au Set-Cookie / Vary: Cookie, altfel browserul nu le tine niciodata in cache;
  - o cale nu iese niciodata din directorul versiunii;
  - `/torqa/` are politica de continut a lui, iar dashboardul isi pastreaza una a lui;
  - apelurile de API din Torqa merg pe sesiune + CSRF: cu antet reusesc, fara antet pica.

Tot ce se scrie pe disc se scrie intr-un director temporar, niciodata in `uploads/`.
"""

import io
import os
import stat
import subprocess
import time
import zipfile

from datetime import datetime, timedelta, timezone
from unittest import mock

from _aplicatia import BUILD, DEVICE, FULL, CuAplicatia, zip_build, zip_cu
from blueprints import torqa_web

IMUABIL = 'public, max-age=31536000, immutable'


class CuWeb(CuAplicatia):
    """Un `DIR_WEB` temporar si ajutoarele de urcare/citire."""

    def setUp(self):
        super().setUp()
        # `radacina` e a testului (nu TEMP-ul comun): ce ajunge „in afara” lui DIR_WEB ramane
        # vizibil aici, iar doua rulari in paralel nu se calca.
        self.radacina = self.dir_temp()
        self.dir_web = os.path.join(self.radacina, 'torqa-web')
        os.makedirs(self.dir_web)
        self.patch(torqa_web, 'DIR_WEB', self.dir_web)
        self.patch(torqa_web.logger, 'disabled', True)      # respingerile sunt asteptate, nu zgomot

    def get(self, cale, **kw):
        # `buffered`: send_file tine fisierul deschis pana se inchide raspunsul; un server WSGI
        # il inchide singur, clientul de test nu (ResourceWarning, iar pe Windows fisierul
        # deschis ar bloca stergerea directorului temporar).
        return self.client.get(cale, buffered=True, **kw)

    def urca(self, continut, token=FULL, camp='zip'):
        return self.client.post('/api/torqa/web/upload', headers=self.bearer(token) if token else {},
                                data={camp: (io.BytesIO(continut), 'torqa.zip')},
                                content_type='multipart/form-data')

    def instaleaza(self, continut=None):
        r = self.urca(zip_build() if continut is None else continut)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        return r.get_json()

    def versiuni_pe_disc(self):
        return sorted(n for n in os.listdir(self.dir_web) if torqa_web.ID_VERSIUNE.match(n))

    def citeste_live(self, rest):
        with open(os.path.join(self.dir_web, torqa_web.versiune_live(), rest), 'rb') as fh:
            return fh.read()


# ================================================================ urcare: acceptat

class UrcareaAcceptata(CuWeb):

    def test_un_build_bun_devine_live(self):
        zip_ = zip_build()
        corp = self.instaleaza(zip_)
        self.assertTrue(corp['ok'])
        self.assertRegex(corp['version'], torqa_web.ID_VERSIUNE)
        self.assertEqual(corp['files'], len(BUILD))
        self.assertEqual(corp['size'], sum(len(v if isinstance(v, bytes) else v.encode()) for v in BUILD.values()))
        self.assertEqual(corp['zip_size'], len(zip_))
        self.assertEqual(corp['kept'], [corp['version']])
        self.assertEqual(corp['warnings'], [], 'build-ul de proba are <base href="/torqa/">')
        self.assertEqual(torqa_web.versiune_live(), corp['version'])
        for nume, continut in BUILD.items():
            asteptat = continut if isinstance(continut, bytes) else continut.encode()
            self.assertEqual(self.citeste_live(nume), asteptat, nume)

    def test_numele_cu_backslash_si_cu_punct_se_normalizeaza(self):
        # Unele unelte Windows scriu `\` in numele din zip; `./` apare la zip-uri facute de mana.
        self.instaleaza(zip_cu(('index.html', '<html></html>'), ('./main-ABCDEFGH.js', 'm'),
                               ('assets\\i18n\\ro.json', '{}')))
        self.assertEqual(self.citeste_live('main-ABCDEFGH.js'), b'm')
        self.assertEqual(self.citeste_live('assets/i18n/ro.json'), b'{}')

    def test_intrarile_de_director_se_ignora(self):
        corp = self.instaleaza(zip_cu(('assets/', ''), ('assets/icons/', ''), ('index.html', 'x'),
                                      ('assets/icons/a.png', 'p')))
        self.assertEqual(corp['files'], 2, 'directoarele nu se numara ca fisiere')
        self.assertEqual(self.citeste_live('assets/icons/a.png'), b'p')

    def test_zip_stocat_fara_compresie_merge_si_el(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            zf.writestr('index.html', 'x')
        self.assertEqual(self.instaleaza(buf.getvalue())['files'], 1)


# ============================================== urcare: <base href> din index.html

class BazaPaginii(CuWeb):
    """Build-ul se face cu `--base-href /torqa/`. In Git Bash, argumentul `/torqa/` e rescris de
    MSYS intr-o cale de Windows, iar pagina iese alba fara nicio eroare la urcare: asta s-a
    intamplat la primul build de proba (2026-10-01). Un `<base>` gresit se respinge."""

    def cu_baza(self, html):
        return zip_build({'index.html': html})

    def test_baza_corecta_trece_in_oricare_forma_de_scriere(self):
        for html in ('<head><base href="/torqa/"></head>', "<head><BASE HREF='/torqa/'></head>",
                     '<head><base target="_top" href = "/torqa/" ></head>',
                     '<head><base\n   href="/torqa/"\n></head>',
                     '<meta charset="utf-8"><style>' + 'a{}' * 50000 + '</style><base href="/torqa/">'):
            with self.subTest(html=html[:50]):
                corp = self.instaleaza(self.cu_baza(html))
                self.assertEqual(corp['warnings'], [])

    def test_baza_gresita_se_respinge_cu_motivul_si_leacul(self):
        for gresit in ('C:/Users/ion.ursu/AppData/Local/Programs/Git/torqa/', '/', '/torqa', './', 'torqa/',
                       '/Torqa/', 'https://pif.iupif.org/torqa/', ''):
            with self.subTest(baza=gresit):
                r = self.urca(self.cu_baza('<head><base href="%s"></head>' % gresit))
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                eroare = r.get_json()['error']
                self.assertIn('--base-href /torqa/', eroare)
                self.assertIn('MSYS_NO_PATHCONV', eroare)
                self.assertIn(gresit, eroare)
        self.assertIsNone(torqa_web.versiune_live())
        self.assertEqual(os.listdir(self.dir_web), [], 'si nu lasa nimic pe disc')

    def test_baza_gresita_nu_atinge_versiunea_live(self):
        bun = self.instaleaza()
        r = self.urca(self.cu_baza('<base href="C:/x/torqa/">'))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(torqa_web.versiune_live(), bun['version'])
        self.assertEqual(self.versiuni_pe_disc(), [bun['version']])

    def test_fara_baza_trece_dar_cu_avertisment(self):
        corp = self.instaleaza(self.cu_baza('<!doctype html><title>fara baza</title>'))
        self.assertEqual(len(corp['warnings']), 1)
        self.assertIn('<base href="/torqa/">', corp['warnings'][0])
        self.assertEqual(torqa_web.versiune_live(), corp['version'])

    def test_primul_base_e_cel_care_conteaza(self):
        # Browserul foloseste primul <base> cu href: un al doilea, corect, nu repara primul.
        r = self.urca(self.cu_baza('<base href="/gresit/"><base href="/torqa/">'))
        self.assertEqual(r.status_code, 400)


# ============================================================== urcare: respins

class UrcareaRespinsa(CuWeb):

    def respinge(self, continut, cod=400, contine=None, **kw):
        r = self.urca(continut, **kw)
        self.assertEqual(r.status_code, cod, r.get_data(as_text=True))
        if contine:
            self.assertIn(contine, r.get_json()['error'])
        self.assertIsNone(torqa_web.versiune_live(), 'un build respins nu devine live')
        self.assertEqual(os.listdir(self.dir_web), [], 'si nu lasa nimic pe disc (temporare, versiuni)')
        return r

    # ---- autorizare

    def test_fara_token_401(self):
        self.respinge(zip_build(), 401, token=None)

    def test_token_gresit_401(self):
        self.respinge(zip_build(), 401, token='gresit')

    def test_tokenul_de_dispozitiv_e_refuzat(self):
        self.respinge(zip_build(), 401, token=DEVICE)

    def test_nici_sesiunea_nu_deschide_ruta(self):
        # Sesiune + CSRF valide, fara Bearer: ruta e masina-la-masina, nu o pagina.
        self.assertEqual(self.login().status_code, 200)
        token = self.client.get_cookie('csrf_token').value
        r = self.client.post('/api/torqa/web/upload', headers={'X-CSRF-Token': token},
                             data={'zip': (io.BytesIO(zip_build()), 'torqa.zip')},
                             content_type='multipart/form-data')
        self.assertEqual(r.status_code, 401)
        self.assertEqual(os.listdir(self.dir_web) if os.path.isdir(self.dir_web) else [], [])

    def test_garda_de_dispozitiv_acopera_prefixul_nu_doar_o_ruta(self):
        # Pe functia de verificare, nu pe ruta (ca in test_sync): lista de refuz e un prefix.
        from utils import _check_api_token
        for ruta in ('/api/torqa/web/upload', '/api/torqa/web/orice-alta-ruta-adaugata-mai-tarziu'):
            for token, asteptat in ((DEVICE, False), (FULL, True)):
                with self.app_module.app.test_request_context(
                        ruta, method='POST', headers={'Authorization': 'Bearer %s' % token}):
                    self.assertIs(_check_api_token(), asteptat, '%s cu %s' % (ruta, token))

    # ---- continut

    def test_lipseste_campul(self):
        r = self.client.post('/api/torqa/web/upload', headers=self.bearer(),
                             data={'altceva': (io.BytesIO(zip_build()), 'x.zip')},
                             content_type='multipart/form-data')
        self.assertEqual(r.status_code, 400)
        self.assertIn('zip', r.get_json()['error'])

    def test_nu_e_zip(self):
        # Semnatura se verifica INAINTE de a deschide arhiva: mesajul spune asta, nu „zip corupt".
        self.respinge(b'<html>nu e un zip</html>', contine='semnatura PK')
        self.respinge(b'', contine='semnatura PK')

    def test_zip_gol_are_alta_semnatura(self):
        self.respinge(zip_cu(), contine='semnatura PK')

    def test_semnatura_buna_continut_stricat(self):
        self.respinge(b'PK\x03\x04' + b'gunoi' * 40, contine='corupt')

    def test_prea_mare_dupa_salvare(self):
        # Fara Content-Length-ul de la poarta: marginea formularului e uriasa, deci verificarea
        # care pica e cea de pe fisierul salvat.
        self.patch(torqa_web, 'MARGINA_FORMULAR', 10 ** 9)
        self.patch(torqa_web, 'MAX_ZIP', 100)
        self.respinge(zip_build(), 413, contine='prea mare')

    def test_prea_mare_dupa_content_length_nu_se_citeste_corpul(self):
        self.patch(torqa_web, 'MARGINA_FORMULAR', 0)
        self.patch(torqa_web, 'MAX_ZIP', 100)
        with mock.patch.object(torqa_web, 'instaleaza') as instaleaza:
            r = self.urca(zip_build())
            self.assertEqual(r.status_code, 413)
            instaleaza.assert_not_called()

    def test_prea_multe_fisiere(self):
        self.patch(torqa_web, 'MAX_FISIERE', 3)
        self.respinge(zip_build(), contine='prea multe')

    def test_descomprimat_prea_mare(self):
        self.patch(torqa_web, 'MAX_DESCOMPRIMAT', 50)
        self.respinge(zip_cu(('index.html', 'x' * 200)), contine='descomprimat')

    def test_plafonul_descomprimat_se_verifica_in_doua_locuri(self):
        # Intai dupa dimensiunile din antet (valideaza_zip), apoi pe octetii scrisi
        # (_extrage): antetul unui zip facut de rau poate minti, deci a doua verificare
        # nu e redundanta. Fiecare se probeaza singura, fiindca prima o acopera pe a doua.
        zip_ = zip_cu(('index.html', 'x' * 200))
        self.patch(torqa_web, 'MAX_DESCOMPRIMAT', 50)
        with zipfile.ZipFile(io.BytesIO(zip_)) as zf:
            with self.assertRaisesRegex(ValueError, 'descomprimat'):
                torqa_web.valideaza_zip(zf)
            intrari = [(i, ['index.html']) for i in zf.infolist()]
            with self.assertRaisesRegex(ValueError, 'descomprimat'):
                torqa_web._extrage(zf, intrari, os.path.join(self.dir_web, 'tinta'))

    def test_fara_index_html(self):
        self.respinge(zip_build(fara=('index.html',)), contine='index.html')

    def test_index_html_doar_intr_un_folder(self):
        # Se zipuieste CONTINUTUL lui `browser`, nu folderul: mesajul spune asta.
        self.respinge(zip_cu(('browser/index.html', 'x'), ('browser/main-ABCDEFGH.js', 'm')),
                      contine='CONTINUTUL')

    def test_nume_duplicate(self):
        self.respinge(zip_cu(('index.html', 'a'), ('main.js', 'b'), ('main.js', 'c')), contine='duplicat')
        self.respinge(zip_cu(('index.html', 'a'), ('x/main.js', 'b'), ('x\\main.js', 'c')), contine='duplicat')

    def test_acelasi_nume_fisier_si_director(self):
        self.respinge(zip_cu(('index.html', 'a'), ('assets', 'fisier'), ('assets/x.png', 'p')),
                      contine='fisier')

    def test_zip_slip(self):
        for nume in ('../evil.txt', '../../evil.txt', 'a/../../evil.txt', 'assets/../../evil.txt',
                     '..\\evil.txt', 'a\\..\\..\\evil.txt', '..', 'a/..'):
            with self.subTest(nume=nume):
                self.respinge(zip_cu(('index.html', 'ok'), (nume, 'rau')), contine='..')
        # Nimic n-a ajuns in afara directorului tinta: niciun `evil.txt` nicaieri sub radacina testului.
        gasite = [os.path.join(d, f) for d, _, fisiere in os.walk(self.radacina) for f in fisiere if f == 'evil.txt']
        self.assertEqual(gasite, [])

    def test_cai_absolute(self):
        for nume in ('/etc/cron.d/evil', '/evil.txt', 'C:/Windows/evil.txt', 'C:\\evil.txt',
                     '\\evil.txt', '\\\\server\\share\\evil.txt', 'a/C:/evil.txt', 'flux:ascuns'):
            with self.subTest(nume=nume):
                self.respinge(zip_cu(('index.html', 'ok'), (nume, 'rau')))

    def test_legatura_simbolica(self):
        zi = zipfile.ZipInfo('assets/legatura.js')
        zi.create_system = 3
        zi.external_attr = (stat.S_IFLNK | 0o777) << 16
        self.respinge(zip_cu(('index.html', 'ok'), (zi, '/etc/passwd')), contine='legatura simbolica')

    def test_fisier_special(self):
        zi = zipfile.ZipInfo('assets/fifo')
        zi.create_system = 3
        zi.external_attr = (stat.S_IFIFO | 0o644) << 16
        self.respinge(zip_cu(('index.html', 'ok'), (zi, '')), contine='special')

    def test_intrare_criptata(self):
        brut = bytearray(zip_cu(('index.html', 'ok')))
        # Bitul 0 din „general purpose flag": antetul local (+6) si cel din directorul central (+8).
        for semnatura, deplasare in ((b'PK\x03\x04', 6), (b'PK\x01\x02', 8)):
            i = bytes(brut).find(semnatura)
            self.assertGreaterEqual(i, 0)
            brut[i + deplasare] |= 0x1
        self.respinge(bytes(brut), contine='criptata')

    def test_crc_gresit(self):
        brut = bytearray(zip_cu(('index.html', 'continut care se comprima'),
                                ('main-ABCDEFGH.js', 'altceva' * 40)))
        i = bytes(brut).rfind(b'altceva')
        if i < 0:                                   # comprimat: stricam un octet din mijloc
            i = len(brut) // 2
        brut[i] ^= 0xFF
        # Fie CRC, fie date comprimate stricate: oricum se respinge, si nu cu 500.
        r = self.urca(bytes(brut))
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertEqual(os.listdir(self.dir_web), [])

    def test_o_urcare_respinsa_nu_atinge_versiunea_live(self):
        bun = self.instaleaza()
        inainte = (torqa_web.versiune_live(), self.versiuni_pe_disc(), self.citeste_live('main-ABCDEFGH.js'))
        for rau in (b'nu e zip', zip_build(fara=('index.html',)), zip_cu(('index.html', 'x'), ('../x', 'y'))):
            self.assertEqual(self.urca(rau).status_code, 400)
            self.assertEqual((torqa_web.versiune_live(), self.versiuni_pe_disc(),
                              self.citeste_live('main-ABCDEFGH.js')), inainte)
        self.assertEqual(torqa_web.versiune_live(), bun['version'])
        self.assertEqual(sorted(os.listdir(self.dir_web)), sorted(inainte[1] + [torqa_web.NUME_POINTER]))


# ============================================ schimbarea atomica si retentia

class SchimbareaSiRetentia(CuWeb):

    def build_cu(self, n):
        return zip_build({'main-ABCDEFGH.js': 'versiunea %d' % n})

    def test_raman_live_si_doua_anterioare(self):
        urcate = []
        for n in range(1, 6):
            corp = self.instaleaza(self.build_cu(n))
            urcate.append(corp['version'])
            self.assertEqual(torqa_web.versiune_live(), corp['version'])
            self.assertEqual(self.citeste_live('main-ABCDEFGH.js'), ('versiunea %d' % n).encode())
            asteptate = sorted(urcate[-3:], reverse=True)
            self.assertEqual(self.versiuni_pe_disc(), sorted(asteptate), 'dupa urcarea %d' % n)
            self.assertEqual(corp['kept'], asteptate)
        self.assertEqual(len(set(urcate)), 5, 'ids distincte')
        self.assertEqual(urcate, sorted(urcate), 'ordinea lexicografica e cea cronologica')
        # Versiunile anterioare au continutul lor, neatins.
        for id_, n in zip(urcate[-3:], (3, 4, 5)):
            with open(os.path.join(self.dir_web, id_, 'main-ABCDEFGH.js'), 'rb') as fh:
                self.assertEqual(fh.read(), ('versiunea %d' % n).encode())

    def ceas(self, *momente):
        """Un `datetime` care intoarce pe rand `momente` (ultimul se repeta)."""
        coada = list(momente)

        class Ceas(datetime):
            @classmethod
            def now(cls, tz=None):
                return coada.pop(0) if len(coada) > 1 else coada[0]

        return Ceas

    def test_id_urile_sunt_stict_crescatoare_si_cand_ceasul_e_grosier_sau_da_inapoi(self):
        t = datetime(2026, 10, 1, 12, 0, 0, 500, tzinfo=timezone.utc)
        # Ceas care nu inainteaza deloc (rezolutie grosiera): trei urcari, acelasi „acum".
        with mock.patch.object(torqa_web, 'datetime', self.ceas(t)):
            ids = [self.instaleaza(self.build_cu(n))['version'] for n in (1, 2, 3)]
        self.assertEqual(len(set(ids)), 3, ids)
        self.assertEqual(ids, sorted(ids))
        # Ceas dat inapoi cu o zi (NTP, reglare de mana): noua versiune tot e cea mai noua.
        inapoi = t - timedelta(days=1)
        with mock.patch.object(torqa_web, 'datetime', self.ceas(inapoi)):
            nou = self.instaleaza(self.build_cu(4))['version']
        self.assertGreater(nou, ids[-1])
        self.assertEqual(torqa_web.versiune_live(), nou)
        self.assertEqual(self.versiuni_pe_disc(), sorted(ids[1:] + [nou]), 'se taie cea mai VECHE, nu cea „veche" dupa ceas')

    def test_un_rename_si_un_replace_blocate_o_clipa_se_reincearca(self):
        # Windows: un antivirus tine o clipa deschise fisierele abia scrise. De doua ori
        # PermissionError, a treia oara merge — la `rename` (director) si la `replace` (pointer).
        real_rename, real_replace = os.rename, os.replace
        apeluri = {'rename': 0, 'replace': 0}

        def rename(sursa, tinta):
            apeluri['rename'] += 1
            if apeluri['rename'] <= 2:
                raise PermissionError(5, 'Access is denied')
            return real_rename(sursa, tinta)

        def replace(sursa, tinta):
            apeluri['replace'] += 1
            if apeluri['replace'] <= 2:
                raise PermissionError(5, 'Access is denied')
            return real_replace(sursa, tinta)

        with mock.patch.object(torqa_web.os, 'rename', rename), \
                mock.patch.object(torqa_web.os, 'replace', replace), \
                mock.patch.object(torqa_web.time, 'sleep'):
            corp = self.instaleaza()
        self.assertEqual(apeluri, {'rename': 3, 'replace': 3})
        self.assertEqual(torqa_web.versiune_live(), corp['version'])

    def test_un_rename_blocat_pentru_totdeauna_da_500_si_nu_lasa_resturi(self):
        primul = self.instaleaza(self.build_cu(1))

        def rename(sursa, tinta):
            raise PermissionError(5, 'Access is denied')

        with mock.patch.object(torqa_web.os, 'rename', rename), mock.patch.object(torqa_web.time, 'sleep'):
            r = self.urca(self.build_cu(2))
        self.assertEqual(r.status_code, 500)
        self.assertEqual(torqa_web.versiune_live(), primul['version'])
        self.assertEqual(sorted(os.listdir(self.dir_web)), sorted([primul['version'], torqa_web.NUME_POINTER]))

    def test_un_director_care_arata_a_id_dar_nu_e_data_nu_strica_urcarea(self):
        os.makedirs(os.path.join(self.dir_web, '99999999T999999-999999'))     # luna 99
        os.makedirs(os.path.join(self.dir_web, '20000101T000000-000000'))
        corp = self.instaleaza()
        self.assertEqual(torqa_web.versiune_live(), corp['version'])
        self.assertGreater(corp['version'], '20000101T000000-000000')

    def test_doua_urcari_cu_acelasi_id_nu_se_calca(self):
        primul = self.instaleaza(self.build_cu(1))['version']
        # Simulam o urcare simultana care a luat deja id-ul urmator: primul `_id_nou` iese
        # ocupat, urmatoarea incercare ia altul.
        ocupat = self.dir_web + os.sep + '20990101T000000-000000'
        os.makedirs(ocupat)
        with open(os.path.join(ocupat, 'index.html'), 'w') as fh:
            fh.write('AL ALTEI URCARI')
        ids = iter(['20990101T000000-000000', '20990101T000000-000001'])
        with mock.patch.object(torqa_web, '_id_nou', lambda: next(ids)):
            corp = self.instaleaza(self.build_cu(2))
        self.assertEqual(corp['version'], '20990101T000000-000001')
        with open(os.path.join(ocupat, 'index.html')) as fh:
            self.assertEqual(fh.read(), 'AL ALTEI URCARI', 'directorul ocupat nu s-a atins')
        self.assertIn(primul, os.listdir(self.dir_web))

    def test_pointerul_se_rescrie_cu_os_replace_in_acelasi_director(self):
        real = os.replace
        apeluri = []

        def spion(sursa, tinta, *a, **k):
            apeluri.append((sursa, tinta))
            # In clipa mutarii, sursa e completa.
            with open(sursa, encoding='utf-8') as fh:
                apeluri[-1] += (fh.read(),)
            return real(sursa, tinta, *a, **k)

        with mock.patch.object(torqa_web.os, 'replace', spion):
            corp = self.instaleaza()
        pointer = [a for a in apeluri if a[1] == os.path.join(self.dir_web, torqa_web.NUME_POINTER)]
        self.assertEqual(len(pointer), 1, apeluri)
        self.assertEqual(os.path.dirname(pointer[0][0]), self.dir_web, 'acelasi sistem de fisiere')
        self.assertEqual(pointer[0][2].strip(), corp['version'])

    def test_pointerul_nu_se_atinge_pana_nu_e_gata_extragerea(self):
        primul = self.instaleaza(self.build_cu(1))
        # Extragerea pica la a doua urcare, dupa ce a scris o parte din fisiere.
        real = torqa_web._extrage

        def pica(zf, intrari, tinta):
            os.makedirs(tinta)
            with open(os.path.join(tinta, 'pe-jumatate.js'), 'w') as fh:
                fh.write('x')
            raise OSError('disc plin')

        with mock.patch.object(torqa_web, '_extrage', pica):
            r = self.urca(self.build_cu(2))
        self.assertIs(torqa_web._extrage, real)
        self.assertEqual(r.status_code, 500)
        self.assertEqual(torqa_web.versiune_live(), primul['version'])
        self.assertEqual(self.citeste_live('main-ABCDEFGH.js'), b'versiunea 1')
        self.assertEqual(sorted(os.listdir(self.dir_web)),
                         sorted([primul['version'], torqa_web.NUME_POINTER]), 'fara resturi')

    def test_pointer_care_nu_se_poate_scrie_nu_lasa_o_versiune_orfana(self):
        primul = self.instaleaza(self.build_cu(1))
        with mock.patch.object(torqa_web, '_scrie_pointer', side_effect=OSError('nu merge')):
            r = self.urca(self.build_cu(2))
        self.assertEqual(r.status_code, 500)
        self.assertEqual(torqa_web.versiune_live(), primul['version'])
        self.assertEqual(self.versiuni_pe_disc(), [primul['version']], 'directorul nou s-a sters')

    def test_intoarcerea_la_o_versiune_anterioara_prin_pointer(self):
        a = self.instaleaza(self.build_cu(1))['version']
        b = self.instaleaza(self.build_cu(2))['version']
        self.assertEqual(self.citeste_live('main-ABCDEFGH.js'), b'versiunea 2')
        # Procedura din decizie: `printf '<versiune>' > uploads/torqa-web/current`
        # (fara newline la sfarsit, sau cu — amandoua trebuie sa mearga).
        for continut in (a, a + '\n', a + '\r\n'):
            with open(os.path.join(self.dir_web, torqa_web.NUME_POINTER), 'w', newline='') as fh:
                fh.write(continut)
            self.assertEqual(torqa_web.versiune_live(), a)
            self.assertEqual(self.get('/torqa/main-ABCDEFGH.js').get_data(), b'versiunea 1')
        with open(os.path.join(self.dir_web, torqa_web.NUME_POINTER), 'w') as fh:
            fh.write(b)
        self.assertEqual(self.get('/torqa/main-ABCDEFGH.js').get_data(), b'versiunea 2')

    def test_dupa_o_intoarcere_urmatoarea_urcare_tine_minte_ce_e_live_acum(self):
        ids = [self.instaleaza(self.build_cu(n))['version'] for n in (1, 2, 3)]
        with open(os.path.join(self.dir_web, torqa_web.NUME_POINTER), 'w') as fh:
            fh.write(ids[0])
        nou = self.instaleaza(self.build_cu(4))['version']
        # Noua e live; raman ea + 2 anterioare (cele mai noi dupa ea).
        self.assertEqual(torqa_web.versiune_live(), nou)
        self.assertEqual(self.versiuni_pe_disc(), sorted([nou, ids[2], ids[1]]))

    def test_taierea_nu_atinge_decat_directoare_de_versiune(self):
        self.instaleaza(self.build_cu(1))
        os.makedirs(os.path.join(self.dir_web, 'ceva-al-cuiva'))
        with open(os.path.join(self.dir_web, 'notite.txt'), 'w') as fh:
            fh.write('x')
        for n in range(2, 7):
            self.instaleaza(self.build_cu(n))
        self.assertTrue(os.path.isdir(os.path.join(self.dir_web, 'ceva-al-cuiva')))
        self.assertTrue(os.path.isfile(os.path.join(self.dir_web, 'notite.txt')))
        self.assertEqual(len(self.versiuni_pe_disc()), 3)

    def test_resturile_vechi_ale_unei_urcari_cazute_se_sterg_pe_cele_proaspete_nu(self):
        os.makedirs(self.dir_web, exist_ok=True)
        vechi_dir = os.path.join(self.dir_web, '.tmp-vechi')
        vechi_zip = os.path.join(self.dir_web, '.up-vechi.zip')
        proaspat = os.path.join(self.dir_web, '.tmp-proaspat')
        os.makedirs(vechi_dir)
        os.makedirs(proaspat)
        with open(os.path.join(vechi_dir, 'x'), 'w') as fh:
            fh.write('x')
        with open(vechi_zip, 'wb') as fh:
            fh.write(b'PK')
        vechi = time.time() - torqa_web.VARSTA_RESTURI - 60
        os.utime(vechi_dir, (vechi, vechi))
        os.utime(vechi_zip, (vechi, vechi))
        self.instaleaza()
        self.assertFalse(os.path.exists(vechi_dir))
        self.assertFalse(os.path.exists(vechi_zip))
        self.assertTrue(os.path.exists(proaspat), 'o urcare in curs nu se atinge')


# ============================================================== servirea

class Servirea(CuWeb):

    # ---- nimic urcat

    def test_neinstalat_503_pe_document_si_pe_fisiere(self):
        self.login()
        for cale in ('/torqa/', '/torqa/index.html', '/torqa/ruta', '/torqa/main-ABCDEFGH.js'):
            with self.subTest(cale=cale):
                r = self.get(cale)
                self.assertEqual(r.status_code, 503)
                self.assertIn('nu este instalat', r.get_data(as_text=True))
                self.assertEqual(r.mimetype, 'text/html')
                self.assertEqual(r.headers['Cache-Control'], 'no-store')

    def test_neinstalat_documentul_cere_tot_login(self):
        r = self.get('/torqa/')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.headers['Location'], '/login?next=/torqa/')

    def test_pointer_stricat_inseamna_neinstalat(self):
        self.instaleaza()
        self.login()
        pointer = os.path.join(self.dir_web, torqa_web.NUME_POINTER)
        for rau in ('../../etc/passwd', '..', '', 'oricum', '20260101T000000-000000',   # dir care nu exista
                    '/etc', 'current'):
            with self.subTest(pointer=rau):
                with open(pointer, 'w') as fh:
                    fh.write(rau)
                self.assertIsNone(torqa_web.versiune_live())
                self.assertEqual(self.get('/torqa/').status_code, 503)
        os.remove(pointer)
        self.assertEqual(self.get('/torqa/').status_code, 503, 'fara pointer')

    def test_pointerul_nu_poate_arata_in_afara_lui_uploads_torqa_web(self):
        # Un pointer care duce spre un director REAL cu index.html din afara DIR_WEB ar servi
        # acel director sub /torqa/: regula „arata ca un id de versiune" il opreste, nu doar
        # verificarea ca exista index.html.
        self.instaleaza()
        afara = self.dir_temp()                  # un director REAL, cu index.html, in afara lui DIR_WEB
        with open(os.path.join(afara, 'index.html'), 'w') as fh:
            fh.write('DIN-AFARA')
        relativ = os.path.relpath(afara, self.dir_web).replace(os.sep, '/')       # ../pif-uploads-xxxx
        self.login()
        pointer = os.path.join(self.dir_web, torqa_web.NUME_POINTER)
        for rau in (relativ, relativ.replace('/', '\\'), os.path.abspath(afara), relativ + '/', './' + relativ):
            with self.subTest(pointer=rau):
                with open(pointer, 'w') as fh:
                    fh.write(rau)
                self.assertIsNone(torqa_web.versiune_live())
                r = self.get('/torqa/')
                self.assertEqual(r.status_code, 503)
                self.assertNotIn(b'DIN-AFARA', r.get_data())

    def test_versiune_fara_index_html_nu_e_live(self):
        corp = self.instaleaza()
        os.remove(os.path.join(self.dir_web, corp['version'], 'index.html'))
        self.assertIsNone(torqa_web.versiune_live())

    # ---- documentul cere sesiune

    def test_documentul_fara_sesiune_redirect_la_login(self):
        self.instaleaza()
        for cale in ('/torqa/', '/torqa/index.html', '/torqa/tasks', '/torqa/tag/azi/tasks',
                     '/torqa/assets/', '/torqa/ruta?x=1'):
            with self.subTest(cale=cale):
                r = self.get(cale)
                self.assertEqual(r.status_code, 302)
                self.assertEqual(r.headers['Location'], '/login?next=/torqa/')
                self.assertNotIn(b'app-root', r.get_data(), 'documentul nu se scurge')

    def test_slash_final_lipsa_duce_la_torqa_slash(self):
        r = self.get('/torqa')
        self.assertIn(r.status_code, (301, 308))
        self.assertEqual(r.headers['Location'], '/torqa/')

    def test_documentul_cu_sesiune(self):
        self.instaleaza()
        self.login()
        r = self.get('/torqa/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_data(), BUILD['index.html'].encode())
        self.assertEqual(r.mimetype, 'text/html')
        self.assertEqual(r.headers['Cache-Control'], 'no-cache')
        self.assertEqual(self.get('/torqa/index.html').get_data(), BUILD['index.html'].encode())

    def test_caile_aplicatiei_dau_documentul(self):
        self.instaleaza()
        self.login()
        for cale in ('/torqa/tasks', '/torqa/tag/azi/tasks', '/torqa/project/abc/settings', '/torqa/assets/'):
            with self.subTest(cale=cale):
                r = self.get(cale)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.get_data(), BUILD['index.html'].encode())

    def test_mai_multe_sesiuni_aceeasi_versiune_live(self):
        self.instaleaza()
        alt = self.app_module.app.test_client()
        self.login()
        self.assertEqual(self.get('/torqa/').status_code, 200)
        self.assertEqual(alt.get('/torqa/').status_code, 302, 'alt browser, fara login')

    # ---- fisierele nu cer sesiune

    def test_fisierele_se_dau_fara_login(self):
        self.instaleaza()
        for cale, continut in (('/torqa/main-ABCDEFGH.js', BUILD['main-ABCDEFGH.js']),
                               ('/torqa/styles-ABCDEFGH.css', BUILD['styles-ABCDEFGH.css']),
                               ('/torqa/ngsw.json', BUILD['ngsw.json']),
                               ('/torqa/ngsw-worker.js', BUILD['ngsw-worker.js']),
                               ('/torqa/manifest.json', BUILD['manifest.json']),
                               ('/torqa/assets/i18n/en.json', BUILD['assets/i18n/en.json'])):
            with self.subTest(cale=cale):
                r = self.get(cale)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.get_data(), continut.encode())

    def test_un_fisier_lipsa_e_404_nu_documentul(self):
        self.instaleaza()
        self.login()
        for cale in ('/torqa/chunk-ZZZZZZZZ.js', '/torqa/assets/lipsa.png', '/torqa/x/y/z.css',
                     '/torqa/index.htm'):
            with self.subTest(cale=cale):
                r = self.get(cale)
                self.assertEqual(r.status_code, 404)
                self.assertNotIn(b'app-root', r.get_data())

    def test_un_director_nu_se_serveste_ca_fisier(self):
        self.instaleaza()
        self.assertEqual(self.get('/torqa/assets.d').status_code, 404)

    def test_doar_get(self):
        self.instaleaza()
        self.login()
        token = self.client.get_cookie('csrf_token').value
        for metoda in ('post', 'put', 'delete', 'patch'):
            r = getattr(self.client, metoda)('/torqa/', headers={'X-CSRF-Token': token})
            self.assertEqual(r.status_code, 405, metoda)

    # ---- tipuri MIME

    def test_tipurile_mime(self):
        asteptate = {
            'a.js': 'text/javascript', 'b.mjs': 'text/javascript', 'c.css': 'text/css',
            'd.json': 'application/json', 'e.webmanifest': 'application/manifest+json',
            'f.svg': 'image/svg+xml', 'g.woff2': 'font/woff2', 'h.png': 'image/png',
            'i.ico': 'image/x-icon', 'j.woff': 'font/woff', 'k.js.map': 'application/json',
            'l.jpg': 'image/jpeg', 'm.mp3': 'audio/mpeg', 'n.txt': 'text/plain',
            'o.xyz': 'application/octet-stream', 'P.PNG': 'image/png',
        }
        self.instaleaza(zip_cu(('index.html', 'x'), *[(n, 'x') for n in asteptate]))
        for nume, tip in asteptate.items():
            with self.subTest(nume=nume):
                r = self.get('/torqa/%s' % nume)
                self.assertEqual(r.status_code, 200)
                self.assertEqual(r.mimetype, tip)
                self.assertEqual(r.headers['X-Content-Type-Options'], 'nosniff')
        # Scripturile au si charset, ca sa nu depinda de ce ghiceste browserul.
        self.assertEqual(self.get('/torqa/a.js').headers['Content-Type'], 'text/javascript; charset=utf-8')

    # ---- cache

    def test_documentul_si_fisierele_de_versiune_se_reverifica_mereu(self):
        self.instaleaza()
        self.login()
        for nume in ('index.html', 'ngsw.json', 'ngsw-worker.js', 'manifest.json'):
            with self.subTest(nume=nume):
                self.assertEqual(self.get('/torqa/%s' % nume).headers['Cache-Control'], 'no-cache')
        self.assertEqual(self.get('/torqa/').headers['Cache-Control'], 'no-cache')

    def test_bundle_urile_cu_hash_se_tin_un_an(self):
        self.instaleaza()
        for nume in ('main-ABCDEFGH.js', 'chunk-QRSTUVWX.js', 'styles-ABCDEFGH.css',
                     'media/open-sans-latin-400-normal-HCAVHEYW.woff2'):
            with self.subTest(nume=nume):
                self.assertEqual(self.get('/torqa/%s' % nume).headers['Cache-Control'], IMUABIL)

    def test_fisierele_fara_hash_se_reverifica(self):
        self.instaleaza(zip_build({'assets/logo-ABCDEFGH.png': 'p', 'altceva-abc.js': 'x', 'fara-hash.js': 'x'}))
        for nume in ('favicon.ico', 'assets/icons/icon-72x72.png', 'assets/i18n/en.json',
                     'assets/logo-ABCDEFGH.png',          # `assets/` nu e hash-uit de Angular, oricum ar arata
                     'altceva-abc.js', 'fara-hash.js'):
            with self.subTest(nume=nume):
                self.assertEqual(self.get('/torqa/%s' % nume).headers['Cache-Control'], 'no-cache')

    def test_cerere_conditionata_da_304(self):
        self.instaleaza()
        for nume in ('main-ABCDEFGH.js', 'ngsw.json', 'assets/i18n/en.json'):
            with self.subTest(nume=nume):
                r1 = self.get('/torqa/%s' % nume)
                etag = r1.headers['ETag']
                r2 = self.get('/torqa/%s' % nume, headers={'If-None-Match': etag})
                self.assertEqual(r2.status_code, 304)
                self.assertEqual(r2.get_data(), b'')

    def test_documentul_conditionat_cere_tot_sesiune(self):
        self.instaleaza()
        self.login()
        etag = self.get('/torqa/').headers['ETag']
        self.assertEqual(self.get('/torqa/', headers={'If-None-Match': etag}).status_code, 304)
        anonim = self.app_module.app.test_client()
        r = anonim.get('/torqa/', headers={'If-None-Match': etag}, buffered=True)
        self.assertEqual(r.status_code, 302, 'un ETag cunoscut nu ocoleste login-ul')

    # ---- fisierele nu ating sesiunea (altfel nu se pot tine in cache)

    def test_fisierele_nu_pun_cookie_si_nu_varieaza_dupa_cookie(self):
        self.instaleaza()
        for autentificat in (False, True):
            if autentificat:
                self.login()
            for cale in ('/torqa/main-ABCDEFGH.js', '/torqa/ngsw.json', '/torqa/assets/i18n/en.json',
                         '/torqa/lipsa.js'):
                with self.subTest(cale=cale, autentificat=autentificat):
                    r = self.get(cale)
                    self.assertEqual(r.headers.getlist('Set-Cookie'), [])
                    self.assertNotIn('cookie', r.headers.get('Vary', '').lower())

    def test_documentul_variaza_dupa_cookie_ca_sa_nu_se_amestece_raspunsurile(self):
        self.instaleaza()
        self.login()
        self.assertIn('cookie', self.get('/torqa/').headers.get('Vary', '').lower())

    def test_o_cerere_de_fisier_nu_strica_sesiunea(self):
        self.instaleaza()
        self.login()
        self.get('/torqa/main-ABCDEFGH.js')
        self.assertEqual(self.get('/torqa/').status_code, 200, 'inca autentificat')
        self.assertEqual(self.get('/api/stats').status_code, 200, 'sesiunea de API a ramas')

    def test_sesiunea_dashboardului_merge_ca_inainte(self):
        # Interfata de sesiune e inlocuita aplicatiei intregi: restul rutelor nu trebuie sa simta.
        self.assertEqual(self.get('/api/stats').status_code, 401, 'fara login, API-ul cere sesiune')
        r = self.login()
        self.assertEqual(r.status_code, 200)
        cookie_uri = ' '.join(r.headers.getlist('Set-Cookie'))
        self.assertIn('session=', cookie_uri)
        self.assertIn('csrf_token=', cookie_uri)
        self.assertEqual(self.get('/api/stats').status_code, 200)
        r = self.get('/')
        self.assertEqual((r.status_code, r.headers['Location']), (302, '/torqa/'))

    # ---- calea nu iese din versiune

    def test_nicio_cale_nu_iese_din_versiune(self):
        self.instaleaza()
        self.login()
        with open(os.path.join(self.dir_web, 'secret.txt'), 'w') as fh:
            fh.write('SECRET-DIN-DIR-WEB')
        with open(os.path.join(self.dir_web, torqa_web.versiune_live(), '..', '..', 'secret-sus.txt'), 'w') as fh:
            fh.write('SECRET-DIN-UPLOADS')
        anonim = self.app_module.app.test_client()
        incercari = ('/torqa/../secret.txt', '/torqa/%2e%2e/secret.txt', '/torqa/..%2fsecret.txt',
                     '/torqa/%2e%2e%2fsecret.txt', '/torqa/assets/../../secret.txt',
                     '/torqa/assets/%2e%2e/%2e%2e/secret.txt', '/torqa/..\\secret.txt',
                     '/torqa/%2e%2e%5csecret.txt', '/torqa/....//secret.txt', '/torqa//secret.txt',
                     '/torqa/../../secret-sus.txt', '/torqa/%2fetc%2fpasswd', '/torqa/%2Fsecret.txt',
                     '/torqa/C:/Windows/win.ini', '/torqa/..%00.js', '/torqa/index.html/../../secret.txt',
                     '/torqa/./../secret.txt', '/torqa/' + '../' * 20 + 'etc/passwd')
        for cale in incercari:
            for client in (self.client, anonim):
                with self.subTest(cale=cale):
                    r = client.get(cale, buffered=True)
                    corp = r.get_data()
                    self.assertNotIn(b'SECRET', corp)
                    self.assertNotIn(b'root:', corp)
                    self.assertNotIn(b'[fonts]', corp)
                    if r.status_code == 200:
                        # O cale fara extensie (`.../etc/passwd`) e o RUTA a aplicatiei, nu un fisier:
                        # autentificat, da documentul — niciodata fisierul cerut.
                        self.assertEqual(corp, BUILD['index.html'].encode(), cale)

    def test_o_legatura_simbolica_din_versiune_spre_afara_nu_scapa(self):
        self.instaleaza()
        with open(os.path.join(self.dir_web, 'secret.txt'), 'w') as fh:
            fh.write('SECRET')
        legatura = os.path.join(self.dir_web, torqa_web.versiune_live(), 'leak.txt')
        try:
            os.symlink(os.path.join(self.dir_web, 'secret.txt'), legatura)
        except (OSError, NotImplementedError):
            self.skipTest('legaturile simbolice cer drepturi pe masina asta')
        r = self.get('/torqa/leak.txt')
        self.assertEqual(r.status_code, 404)
        self.assertNotIn(b'SECRET', r.get_data())

    def test_o_jonctiune_din_versiune_spre_afara_nu_scapa(self):
        # Pe Windows o jonctiune (`mklink /J`) se face fara drepturi speciale, spre deosebire
        # de legatura simbolica de mai sus; `realpath` o rezolva la fel. Pe Linux, aceeasi
        # proba cu o legatura simbolica spre director.
        self.instaleaza()
        afara = os.path.join(self.dir_web, 'afara')
        os.makedirs(afara)
        with open(os.path.join(afara, 'secret.txt'), 'w') as fh:
            fh.write('SECRET-DIN-JONCTIUNE')
        link = os.path.join(self.dir_web, torqa_web.versiune_live(), 'jonctiune')
        if os.name == 'nt':
            rez = subprocess.run(['cmd', '/c', 'mklink', '/J', link, afara], capture_output=True)
            if rez.returncode != 0:
                self.skipTest('nu pot crea o jonctiune: %s' % rez.stdout.decode('utf-8', 'replace')[:80])
        else:
            try:
                os.symlink(afara, link, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('legaturile simbolice cer drepturi pe masina asta')
        self.assertTrue(os.path.isfile(os.path.join(link, 'secret.txt')), 'proba are sens: legatura merge')
        for cale in ('/torqa/jonctiune/secret.txt', '/torqa/jonctiune/../secret.txt'):
            with self.subTest(cale=cale):
                r = self.get(cale)
                self.assertNotEqual(r.status_code, 200)
                self.assertNotIn(b'SECRET', r.get_data())

    def test_cale_in_respinge_ce_iese_din_director(self):
        baza = os.path.join(self.dir_web, 'baza')
        os.makedirs(baza)
        with open(os.path.join(baza, 'ok.js'), 'w') as fh:
            fh.write('x')
        with open(os.path.join(self.dir_web, 'afara.js'), 'w') as fh:
            fh.write('x')
        self.assertEqual(os.path.normpath(torqa_web._cale_in(baza, 'ok.js')), os.path.join(baza, 'ok.js'))
        for rau in ('../afara.js', 'a/../../afara.js', '/etc/passwd', '..', '', 'lipsa.js'):
            self.assertIsNone(torqa_web._cale_in(baza, rau), rau)


# ============================================================ CSP pe /torqa/

class PoliticaDeContinut(CuWeb):

    def csp(self, cale):
        return self.get(cale).headers.get('Content-Security-Policy')

    def test_toate_raspunsurile_de_sub_torqa_poarta_politica_lui(self):
        self.instaleaza()
        self.login()
        for cale in ('/torqa', '/torqa/', '/torqa/index.html', '/torqa/ruta', '/torqa/main-ABCDEFGH.js',
                     '/torqa/ngsw.json', '/torqa/lipsa.js', '/torqa/../app.py'):
            with self.subTest(cale=cale):
                self.assertEqual(self.csp(cale), torqa_web.CSP_TORQA)

    def test_si_redirectul_la_login_si_pagina_de_neinstalat_o_poarta(self):
        self.assertEqual(self.csp('/torqa/'), torqa_web.CSP_TORQA, 'anonim, redirect')
        self.login()
        self.assertEqual(self.csp('/torqa/'), torqa_web.CSP_TORQA, 'neinstalat, 503')

    def test_restul_serverului_isi_pastreaza_politica_lui(self):
        self.instaleaza()
        self.login()
        for cale in ('/login', '/', '/api/stats', '/torqa-altceva', '/torqau/x'):
            with self.subTest(cale=cale):
                csp = self.csp(cale)
                self.assertNotEqual(csp, torqa_web.CSP_TORQA)
                self.assertNotIn("'unsafe-eval'", csp, 'unsafe-eval e doar al Torqa')
                self.assertIn('https://cdn.jsdelivr.net', csp)

    def test_politica_nu_deschide_nimic_in_exterior(self):
        csp = torqa_web.CSP_TORQA
        directive = dict(d.strip().split(' ', 1) for d in csp.split(';') if d.strip())
        self.assertNotRegex(csp, r'(\*|https?:|ws:|wss:)', 'nicio sursa externa, nicio schema larga')
        self.assertEqual(directive['default-src'], "'self'")
        # Ce nu e numit mai jos cade pe `default-src 'self'`: API-ul, fonturile, sunetele,
        # workerul de memento, manifestul — toate de pe acelasi domeniu. Iesirea pe retea
        # (`connect-src`) si cadrele (`frame-src`) n-au voie sa fie deschise explicit.
        for cade_pe_default in ('connect-src', 'font-src', 'media-src', 'worker-src', 'frame-src',
                                'manifest-src', 'child-src'):
            self.assertNotIn(cade_pe_default, directive, cade_pe_default)
        self.assertEqual(directive['object-src'], "'none'")
        self.assertEqual(directive['frame-ancestors'], "'none'")
        self.assertEqual(directive['base-uri'], "'self'")
        self.assertEqual(directive['form-action'], "'self'")
        # Cele trei `unsafe-*` cerute de aplicatie, si doar acolo unde le cere.
        self.assertEqual(set(directive['script-src'].split()), {"'self'", "'unsafe-inline'", "'unsafe-eval'"})
        self.assertEqual(set(directive['style-src'].split()), {"'self'", "'unsafe-inline'"})
        self.assertEqual(set(directive['img-src'].split()), {"'self'", 'data:', 'blob:'})
        for nume, valoare in directive.items():
            if nume != 'script-src':
                self.assertNotIn('unsafe-eval', valoare, nume)
            if nume not in ('script-src', 'style-src'):
                self.assertNotIn('unsafe-inline', valoare, nume)


# ======================================================= CSRF din Torqa web

class CsrfDinTorqa(CuWeb):
    """Apelurile de API ale paginii Torqa sunt aceleasi-origine, pe sesiunea dashboardului:
    cookie-ul `csrf_token` se trimite inapoi in antetul `X-CSRF-Token` (csrf.py)."""

    def setUp(self):
        super().setUp()
        self.instaleaza()
        self.assertEqual(self.login().status_code, 200)

    def antete(self, token):
        h = {'X-Torqa': '1', 'Referer': 'http://localhost/torqa/'}
        if token is not None:
            h['X-CSRF-Token'] = token
        return h

    def test_cookie_ul_csrf_apare_dupa_incarcarea_torqa(self):
        self.client.delete_cookie('csrf_token')
        self.assertIsNone(self.client.get_cookie('csrf_token'))
        r = self.get('/torqa/')
        self.assertEqual(r.status_code, 200)
        cookie = self.client.get_cookie('csrf_token')
        self.assertIsNotNone(cookie, 'documentul Torqa pune cookie-ul csrf')
        self.assertRegex(cookie.value, r'^[0-9a-f]{64}$')
        # Citibil din JavaScript (double submit): fara HttpOnly, pe tot site-ul.
        antet = [c for c in r.headers.getlist('Set-Cookie') if c.startswith('csrf_token=')][0]
        self.assertNotIn('HttpOnly', antet)
        self.assertIn('Path=/', antet)

    def test_cu_antet_scrierile_reusesc(self):
        self.get('/torqa/')
        h = self.antete(self.client.get_cookie('csrf_token').value)
        r = self.client.post('/api/global-tasks', json={'titlu': 'din Torqa web'}, headers=h)
        self.assertEqual(r.status_code, 201, r.get_data(as_text=True))
        id_ = r.get_json()['id']
        r = self.client.put('/api/global-tasks/%s' % id_, json={'titlu': 'schimbat din Torqa web'}, headers=h)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.get('/api/global-tasks/%s' % id_).get_json()['titlu'],
                         'schimbat din Torqa web')
        r = self.client.delete('/api/global-tasks/%s' % id_, headers=h)
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.get('/api/global-tasks/%s' % id_).status_code, 404)

    def test_fara_antet_scrierile_sunt_refuzate(self):
        self.get('/torqa/')
        h = self.antete(self.client.get_cookie('csrf_token').value)
        id_ = self.client.post('/api/global-tasks', json={'titlu': 'ramane'}, headers=h).get_json()['id']

        sans = self.antete(None)
        self.assertEqual(self.client.post('/api/global-tasks', json={'titlu': 'x'}, headers=sans).status_code, 403)
        self.assertEqual(self.client.put('/api/global-tasks/%s' % id_, json={'titlu': 'x'},
                                         headers=sans).status_code, 403)
        self.assertEqual(self.client.delete('/api/global-tasks/%s' % id_, headers=sans).status_code, 403)
        # Nimic nu s-a schimbat din cauza lor.
        self.assertEqual(self.get('/api/global-tasks/%s' % id_).get_json()['titlu'], 'ramane')

    def test_cu_antet_gresit_scrierile_sunt_refuzate(self):
        for gresit in ('', 'gresit', 'a' * 64):
            with self.subTest(antet=gresit):
                r = self.client.post('/api/global-tasks', json={'titlu': 'x'}, headers=self.antete(gresit))
                self.assertEqual(r.status_code, 403)

    def test_citirile_nu_cer_antet(self):
        self.assertEqual(self.get('/api/global-tasks?sfera=toate', headers=self.antete(None)).status_code, 200)

    def test_fara_sesiune_apelurile_de_api_din_torqa_sunt_401(self):
        anonim = self.app_module.app.test_client()
        self.assertEqual(anonim.get('/api/sync/snapshot', headers=self.antete(None)).status_code, 401)
        self.assertEqual(anonim.post('/api/global-tasks', json={'titlu': 'x'},
                                     headers=self.antete('orice')).status_code, 401)


if __name__ == '__main__':
    import unittest
    unittest.main()

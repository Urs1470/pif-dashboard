"""Canalele de actualizare Android (`/api/app/*`): `pif` (aplicatia veche) si `torqa`.

Patru lucruri pazite, toate tacute daca se strica:
  - CITIREA fara `canal` face exact ce facea inainte de canale: aceleasi fisiere, acelasi
    raspuns, acelasi nume la descarcare. Aplicatia veche (`org.iupif.pif`), inca instalata
    cateva zile, nu stie de canale si nu trebuie sa observe nimic;
  - URCAREA cere `canal`: fara el (ca si cu o valoare goala sau necunoscuta) da 400 si nu
    scrie nimic. O variabila nesetata in scriptul de build nu are voie sa cada pe `pif` si sa
    suprascrie aplicatia veche (sau pe oricare canal) cu alt APK;
  - `torqa` are fisierele lui si nu le atinge pe ale lui `pif`: un APK Torqa urcat peste
    cel vechi ar fi o actualizare pe care telefonul o refuza (alta semnatura/alt pachet);
  - doar tokenul de masina urca, pe ambele canale.
"""

import io
import json
import os

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import app_update

APK_PIF = b'PK\x03\x04' + b'apk-pif-' * 60
APK_TORQA = b'PK\x03\x04' + b'apk-torqa-' * 90


class CanaleApk(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir_app = self.dir_temp()
        self.patch(app_update, 'DIR_APP', self.dir_app)

    def urca(self, apk=APK_PIF, cod='100', nume='1.0.0', token=FULL, canal='pif', **camp):
        """`canal=None` = campul lipseste cu totul (nu e trimis)."""
        date = {'apk': (io.BytesIO(apk), 'x.apk'), 'versionCode': cod, 'versionName': nume, **camp}
        if canal is not None:
            date['canal'] = canal
        return self.client.post('/api/app/upload', headers=self.bearer(token) if token else {},
                                data=date, content_type='multipart/form-data')

    def get(self, cale, token=FULL):
        # `buffered`: send_file tine APK-ul deschis pana se inchide raspunsul (clientul de test
        # nu-l inchide singur), iar un fisier deschis blocheaza stergerea directorului temporar.
        return self.client.get(cale, headers=self.bearer(token), buffered=True)

    def fisiere(self):
        return sorted(os.listdir(self.dir_app))

    def citeste(self, nume):
        with open(os.path.join(self.dir_app, nume), 'rb') as fh:
            return fh.read()

    # ----------------------------------------------- `pif`: numele si formatul de dinainte

    def test_canalul_pif_scrie_exact_ca_inainte(self):
        r = self.urca()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        corp = r.get_json()
        self.assertEqual(set(corp), {'ok', 'versionCode', 'versionName', 'size', 'sha256', 'at', 'notes'},
                         'raspunsul nu primeste chei noi')
        self.assertEqual(self.fisiere(), ['meta.json', 'pif.apk'])
        self.assertEqual(self.citeste('pif.apk'), APK_PIF)
        # `meta.json`: aceleasi chei, in aceeasi ordine, cu aceeasi formatare (modul text
        # scrie CRLF pe Windows, LF pe server: nu asta se compara).
        asteptat = {k: corp[k] for k in ('versionCode', 'versionName', 'size', 'sha256', 'at', 'notes')}
        self.assertEqual(self.citeste('meta.json').decode('utf-8').replace('\r\n', '\n'),
                         json.dumps(asteptat, ensure_ascii=False, indent=2))
        self.assertEqual((corp['versionCode'], corp['versionName'], corp['size']), (100, '1.0.0', len(APK_PIF)))

    def test_versiunea_si_descarcarea_fara_canal(self):
        self.urca()
        v = self.get('/api/app/version')
        self.assertEqual(v.status_code, 200)
        corp = v.get_json()
        self.assertTrue(corp['disponibil'])
        self.assertEqual((corp['versionCode'], corp['versionName']), (100, '1.0.0'))
        d = self.get('/api/app/apk')
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d.get_data(), APK_PIF)
        self.assertEqual(d.mimetype, 'application/vnd.android.package-archive')
        self.assertIn('pif-1.0.0.apk', d.headers['Content-Disposition'])

    def test_canalul_pif_numit_explicit_e_cel_citit_fara_canal(self):
        self.assertEqual(self.urca(canal='pif').status_code, 200)
        self.assertEqual(self.fisiere(), ['meta.json', 'pif.apk'])
        self.assertEqual(self.get('/api/app/apk?canal=pif').get_data(), APK_PIF)
        self.assertEqual(self.get('/api/app/apk').get_data(), APK_PIF, 'fara canal, la citire, tot pif')
        self.assertEqual(self.get('/api/app/version').get_json(), self.get('/api/app/version?canal=pif').get_json())

    # ------------------------------------------------------ urcarea fara `canal` = 400

    def test_urcarea_fara_canal_da_400_si_nu_scrie_nimic(self):
        r = self.urca(canal=None)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn('Lipseste `canal`', r.get_json()['error'])
        self.assertIn('pif', r.get_json()['error'])
        self.assertIn('torqa', r.get_json()['error'])
        self.assertEqual(self.fisiere(), [], 'nimic nu se scrie')

    def test_urcarea_fara_canal_nu_suprascrie_aplicatia_veche_si_nici_pe_torqa(self):
        self.urca()
        self.urca(APK_TORQA, cod='200', nume='2.0.0', canal='torqa')
        inainte = {n: self.citeste(n) for n in self.fisiere()}
        for apk, cod, nume in ((APK_TORQA, '300', '3.0.0'), (APK_PIF, '301', '3.0.1')):
            with self.subTest(versiune=nume):
                self.assertEqual(self.urca(apk, cod=cod, nume=nume, canal=None).status_code, 400)
        self.assertEqual({n: self.citeste(n) for n in self.fisiere()}, inainte, 'niciun fisier atins')
        self.assertEqual(self.get('/api/app/version').get_json()['versionName'], '1.0.0')
        self.assertEqual(self.get('/api/app/version?canal=torqa').get_json()['versionName'], '2.0.0')

    def test_canalul_se_cere_dupa_token_si_inaintea_restului_validarilor(self):
        # Tokenul se verifica primul (401), apoi canalul (400), abia apoi fisierul si versiunea.
        self.assertEqual(self.urca(canal=None, token=None).status_code, 401)
        self.assertEqual(self.urca(canal=None, token=DEVICE).status_code, 401)
        r = self.urca(b'nu e apk', cod='abc', canal=None)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Lipseste `canal`', r.get_json()['error'])

    def test_numele_de_canal_se_normalizeaza(self):
        self.assertEqual(self.urca(APK_TORQA, canal=' Torqa ').status_code, 200)
        self.assertEqual(self.fisiere(), ['torqa-meta.json', 'torqa.apk'])
        self.assertTrue(self.get('/api/app/version?canal=TORQA').get_json()['disponibil'])

    # --------------------------------------------------------------- canalul torqa

    def test_torqa_are_fisierele_lui_si_nu_le_atinge_pe_ale_lui_pif(self):
        self.urca()
        inainte = {n: (self.citeste(n), os.stat(os.path.join(self.dir_app, n)).st_mtime_ns)
                   for n in ('pif.apk', 'meta.json')}
        r = self.urca(APK_TORQA, cod='200', nume='2.0.0', canal='torqa')
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        self.assertEqual(self.fisiere(), ['meta.json', 'pif.apk', 'torqa-meta.json', 'torqa.apk'])
        self.assertEqual(self.citeste('torqa.apk'), APK_TORQA)
        self.assertEqual(json.loads(self.citeste('torqa-meta.json'))['versionName'], '2.0.0')
        for n, (continut, mtime) in inainte.items():
            self.assertEqual(self.citeste(n), continut, n)
            self.assertEqual(os.stat(os.path.join(self.dir_app, n)).st_mtime_ns, mtime, '%s nu se rescrie' % n)

    def test_fiecare_canal_isi_citeste_versiunea_si_isi_da_apk_ul(self):
        self.urca()
        self.urca(APK_TORQA, cod='200', nume='2.0.0', canal='torqa')
        vp = self.get('/api/app/version').get_json()
        vt = self.get('/api/app/version?canal=torqa').get_json()
        self.assertEqual((vp['versionCode'], vp['versionName']), (100, '1.0.0'))
        self.assertEqual((vt['versionCode'], vt['versionName']), (200, '2.0.0'))
        dp = self.get('/api/app/apk')
        dt = self.get('/api/app/apk?canal=torqa')
        self.assertEqual((dp.get_data(), dt.get_data()), (APK_PIF, APK_TORQA))
        self.assertIn('pif-1.0.0.apk', dp.headers['Content-Disposition'])
        self.assertIn('torqa-2.0.0.apk', dt.headers['Content-Disposition'])

    def test_un_canal_nepublicat_nu_exista_si_nu_se_imprumuta_de_la_celalalt(self):
        self.assertEqual(self.get('/api/app/version?canal=torqa').get_json(), {'disponibil': False})
        self.assertEqual(self.get('/api/app/apk?canal=torqa').status_code, 404)
        self.urca()                                    # doar pif
        self.assertEqual(self.get('/api/app/version?canal=torqa').get_json(), {'disponibil': False})
        self.assertEqual(self.get('/api/app/apk?canal=torqa').status_code, 404)
        self.assertTrue(self.get('/api/app/version').get_json()['disponibil'])

    def test_dispozitivul_citeste_canalul_torqa(self):
        self.urca(APK_TORQA, cod='200', nume='2.0.0', canal='torqa')
        r = self.get('/api/app/version?canal=torqa', token=DEVICE)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()['disponibil'])
        self.assertEqual(self.get('/api/app/apk?canal=torqa', token=DEVICE).get_data(), APK_TORQA)

    # ------------------------------------------------------------- canal necunoscut

    def test_canal_necunoscut_sau_gol_da_400_si_nu_scrie_nimic(self):
        for rau in ('altceva', '', ' ', 'pif2', '../pif', 'torqa/x', 'torqa.apk'):
            with self.subTest(canal=rau):
                r = self.urca(canal=rau)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('Canal necunoscut', r.get_json()['error'])
                self.assertEqual(self.fisiere(), [], 'nimic nu se scrie')
                self.assertEqual(self.get('/api/app/version?canal=%s' % rau).status_code, 400)
                self.assertEqual(self.get('/api/app/apk?canal=%s' % rau).status_code, 400)

    # --------------------------------------------------------------- autorizare

    def test_urcarea_cere_tokenul_de_masina_pe_ambele_canale(self):
        for canal in ('pif', 'torqa'):
            with self.subTest(canal=canal):
                self.assertEqual(self.urca(token=None, canal=canal).status_code, 401, 'fara token')
                self.assertEqual(self.urca(token=DEVICE, canal=canal).status_code, 401,
                                 'tokenul de dispozitiv nu urca APK-uri')
                self.assertEqual(self.fisiere(), [])

    # ------------------------------------------------- validarile de dinainte raman

    def test_validarile_existente_se_aplica_si_canalului_torqa(self):
        for canal in ('pif', 'torqa'):
            with self.subTest(canal=canal):
                self.assertEqual(self.urca(b'nu e apk', canal=canal).status_code, 400, 'fara PK')
                self.assertEqual(self.urca(cod='abc', canal=canal).status_code, 400, 'versionCode')
                self.assertEqual(self.urca(nume='cu spatiu', canal=canal).status_code, 400, 'versionName')
                self.assertEqual(self.fisiere(), [], 'un APK respins nu lasa nimic')

    def test_un_apk_respins_nu_inlocuieste_pe_cel_publicat(self):
        self.urca(APK_TORQA, cod='200', nume='2.0.0', canal='torqa')
        self.assertEqual(self.urca(b'nu e apk', cod='201', nume='2.0.1', canal='torqa').status_code, 400)
        self.assertEqual(self.get('/api/app/apk?canal=torqa').get_data(), APK_TORQA)
        self.assertEqual(self.get('/api/app/version?canal=torqa').get_json()['versionName'], '2.0.0')


if __name__ == '__main__':
    import unittest
    unittest.main()

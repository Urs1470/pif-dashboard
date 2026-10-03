"""Actualizarea Android (`/api/app/*`): un singur canal, `torqa`.

Patru lucruri pazite, toate tacute daca se strica:
  - `canal` e obligatoriu si la URCARE si la CITIRE: fara el (ca si cu o valoare goala sau
    necunoscuta) da 400 si nu scrie nimic. Nu exista canal implicit: o variabila nesetata in
    scriptul de build nu are voie sa cada pe un canal ghicit;
  - canalul `pif` al aplicatiei vechi (`org.iupif.pif`) a plecat pe 2026-10-03: cerut pe nume da
    400, iar fisierele lui ramase in `uploads/app/` nu se mai servesc si nu se ating;
  - `torqa` isi scrie fisierele lui, cu formatul de pana acum;
  - doar tokenul de masina urca; dispozitivul citeste.
"""

import io
import json
import os

from _aplicatia import DEVICE, FULL, CuAplicatia
from blueprints import app_update

APK_TORQA = b'PK\x03\x04' + b'apk-torqa-' * 90
APK_VECHI = b'PK\x03\x04' + b'apk-pif-' * 60


class CanalulTorqa(CuAplicatia):

    def setUp(self):
        super().setUp()
        self.dir_app = self.dir_temp()
        self.patch(app_update, 'DIR_APP', self.dir_app)

    def urca(self, apk=APK_TORQA, cod='200', nume='2.0.0', token=FULL, canal='torqa', **camp):
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

    def pune_fisierele_vechi(self):
        """Ce a ramas pe server de la canalul `pif`: un APK si meta-ul lui."""
        with open(os.path.join(self.dir_app, 'pif.apk'), 'wb') as fh:
            fh.write(APK_VECHI)
        with open(os.path.join(self.dir_app, 'meta.json'), 'w', encoding='utf-8') as fh:
            json.dump({'versionCode': 1393013, 'versionName': '2026.08.25.1153'}, fh)

    # ------------------------------------------------------------------- torqa

    def test_torqa_scrie_fisierele_lui_cu_formatul_de_pana_acum(self):
        r = self.urca()
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        corp = r.get_json()
        self.assertEqual(set(corp), {'ok', 'versionCode', 'versionName', 'size', 'sha256', 'at', 'notes'})
        self.assertEqual(self.fisiere(), ['torqa-meta.json', 'torqa.apk'])
        self.assertEqual(self.citeste('torqa.apk'), APK_TORQA)
        asteptat = {k: corp[k] for k in ('versionCode', 'versionName', 'size', 'sha256', 'at', 'notes')}
        self.assertEqual(self.citeste('torqa-meta.json').decode('utf-8').replace('\r\n', '\n'),
                         json.dumps(asteptat, ensure_ascii=False, indent=2))
        self.assertEqual((corp['versionCode'], corp['versionName'], corp['size']), (200, '2.0.0', len(APK_TORQA)))

    def test_versiunea_si_descarcarea_cu_canal(self):
        self.urca()
        v = self.get('/api/app/version?canal=torqa').get_json()
        self.assertTrue(v['disponibil'])
        self.assertEqual((v['versionCode'], v['versionName']), (200, '2.0.0'))
        d = self.get('/api/app/apk?canal=torqa')
        self.assertEqual(d.status_code, 200)
        self.assertEqual(d.get_data(), APK_TORQA)
        self.assertEqual(d.mimetype, 'application/vnd.android.package-archive')
        self.assertIn('torqa-2.0.0.apk', d.headers['Content-Disposition'])

    def test_un_canal_nepublicat_raspunde_ca_nimic_disponibil(self):
        self.assertEqual(self.get('/api/app/version?canal=torqa').get_json(), {'disponibil': False})
        self.assertEqual(self.get('/api/app/apk?canal=torqa').status_code, 404)

    def test_numele_de_canal_se_normalizeaza(self):
        self.assertEqual(self.urca(canal=' Torqa ').status_code, 200)
        self.assertEqual(self.fisiere(), ['torqa-meta.json', 'torqa.apk'])
        self.assertTrue(self.get('/api/app/version?canal=TORQA').get_json()['disponibil'])

    def test_dispozitivul_citeste_canalul_torqa(self):
        self.urca()
        r = self.get('/api/app/version?canal=torqa', token=DEVICE)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()['disponibil'])
        self.assertEqual(self.get('/api/app/apk?canal=torqa', token=DEVICE).get_data(), APK_TORQA)

    # ------------------------------------------------------- fara canal = 400

    def test_urcarea_fara_canal_da_400_si_nu_scrie_nimic(self):
        r = self.urca(canal=None)
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn('Lipseste `canal`', r.get_json()['error'])
        self.assertIn('torqa', r.get_json()['error'])
        self.assertEqual(self.fisiere(), [], 'nimic nu se scrie')

    def test_citirea_fara_canal_da_400(self):
        self.urca()
        for cale in ('/api/app/version', '/api/app/apk'):
            with self.subTest(cale=cale):
                r = self.get(cale)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('Lipseste `canal`', r.get_json()['error'])

    def test_canalul_se_cere_dupa_token_si_inaintea_restului_validarilor(self):
        # Tokenul se verifica primul (401), apoi canalul (400), abia apoi fisierul si versiunea.
        self.assertEqual(self.urca(canal=None, token=None).status_code, 401)
        self.assertEqual(self.urca(canal=None, token=DEVICE).status_code, 401)
        r = self.urca(b'nu e apk', cod='abc', canal=None)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Lipseste `canal`', r.get_json()['error'])

    # -------------------------------------------------- canalul `pif` a plecat

    def test_canalul_pif_nu_mai_exista(self):
        r = self.urca(APK_VECHI, cod='100', nume='1.0.0', canal='pif')
        self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
        self.assertIn('Canal necunoscut', r.get_json()['error'])
        self.assertEqual(self.fisiere(), [], 'nimic nu se scrie')
        self.assertEqual(self.get('/api/app/version?canal=pif').status_code, 400)
        self.assertEqual(self.get('/api/app/apk?canal=pif').status_code, 400)

    def test_fisierele_ramase_de_la_pif_nu_se_servesc_si_nu_se_ating(self):
        self.pune_fisierele_vechi()
        inainte = {n: self.citeste(n) for n in self.fisiere()}
        self.assertEqual(self.get('/api/app/version').status_code, 400)
        self.assertEqual(self.get('/api/app/apk').status_code, 400)
        self.assertEqual(self.get('/api/app/version?canal=torqa').get_json(), {'disponibil': False},
                         'torqa nu imprumuta nimic de la canalul plecat')
        self.assertEqual(self.urca().status_code, 200)
        self.assertEqual(self.get('/api/app/apk?canal=torqa').get_data(), APK_TORQA)
        self.assertEqual({n: self.citeste(n) for n in ('pif.apk', 'meta.json')}, inainte,
                         'fisierele vechi raman cum erau; le sterge Ion, nu codul')

    def test_canal_necunoscut_sau_gol_da_400_si_nu_scrie_nimic(self):
        for rau in ('altceva', '', ' ', 'torqa2', '../torqa', 'torqa/x', 'torqa.apk'):
            with self.subTest(canal=rau):
                r = self.urca(canal=rau)
                self.assertEqual(r.status_code, 400, r.get_data(as_text=True))
                self.assertIn('Canal necunoscut', r.get_json()['error'])
                self.assertEqual(self.fisiere(), [], 'nimic nu se scrie')
                self.assertEqual(self.get('/api/app/version?canal=%s' % rau).status_code, 400)
                self.assertEqual(self.get('/api/app/apk?canal=%s' % rau).status_code, 400)

    # --------------------------------------------------------------- autorizare

    def test_urcarea_cere_tokenul_de_masina(self):
        self.assertEqual(self.urca(token=None).status_code, 401, 'fara token')
        self.assertEqual(self.urca(token=DEVICE).status_code, 401, 'tokenul de dispozitiv nu urca APK-uri')
        self.assertEqual(self.fisiere(), [])

    # ------------------------------------------------- validarile de dinainte raman

    def test_validarile_existente_se_aplica(self):
        self.assertEqual(self.urca(b'nu e apk').status_code, 400, 'fara PK')
        self.assertEqual(self.urca(cod='abc').status_code, 400, 'versionCode')
        self.assertEqual(self.urca(nume='cu spatiu').status_code, 400, 'versionName')
        self.assertEqual(self.fisiere(), [], 'un APK respins nu lasa nimic')

    def test_un_apk_respins_nu_inlocuieste_pe_cel_publicat(self):
        self.urca()
        self.assertEqual(self.urca(b'nu e apk', cod='201', nume='2.0.1').status_code, 400)
        self.assertEqual(self.get('/api/app/apk?canal=torqa').get_data(), APK_TORQA)
        self.assertEqual(self.get('/api/app/version?canal=torqa').get_json()['versionName'], '2.0.0')


if __name__ == '__main__':
    import unittest
    unittest.main()

"""`UPLOAD_FOLDER` vine din `PIF_UPLOAD_FOLDER`, cu `uploads/` de langa cod ca implicit (E-004)."""

import os
import subprocess
import sys
import tempfile
import shutil

from _baza import RADACINA, Test
import utils


class CaleUploads(Test):

    def test_fara_variabila_ramane_uploads_de_langa_cod(self):
        self.assertEqual(utils.cale_uploads({}), os.path.join(RADACINA, 'uploads'))
        self.assertEqual(utils.UPLOAD_IMPLICIT, os.path.join(RADACINA, 'uploads'))

    def test_valoare_goala_sau_cu_spatii_cade_pe_implicit(self):
        for brut in ('', '   ', '\t'):
            with self.subTest(brut=brut):
                self.assertEqual(utils.cale_uploads({'PIF_UPLOAD_FOLDER': brut}), utils.UPLOAD_IMPLICIT)

    def test_variabila_alege_directorul(self):
        tinta = os.path.join(tempfile.gettempdir(), 'pif-alt-uploads')
        self.assertEqual(utils.cale_uploads({'PIF_UPLOAD_FOLDER': ' %s ' % tinta}), tinta)

    def test_calea_relativa_se_face_absoluta(self):
        self.assertEqual(utils.cale_uploads({'PIF_UPLOAD_FOLDER': 'x/y'}), os.path.abspath('x/y'))

    def test_la_import_directorul_din_variabila_se_creeaza_si_ajunge_in_blueprinturi(self):
        tmp = tempfile.mkdtemp(prefix='pif-upl-')
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        tinta = os.path.join(tmp, 'ales')
        cod = ("import sys, os; sys.path.insert(0, %r);"
               "import utils; from blueprints import app_update, torqa_web;"
               "print(utils.UPLOAD_FOLDER); print(app_update.DIR_APP); print(torqa_web.DIR_WEB);"
               "print(os.path.isdir(utils.UPLOAD_FOLDER))" % RADACINA)
        env = dict(os.environ, PIF_UPLOAD_FOLDER=tinta)
        out = subprocess.run([sys.executable, '-I', '-c', cod], env=env, capture_output=True,
                             text=True, cwd=tmp, check=True).stdout.split('\n')
        self.assertEqual(out[:4], [tinta, os.path.join(tinta, 'app'), os.path.join(tinta, 'torqa-web'), 'True'])

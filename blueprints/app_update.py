# App Update Blueprint
# Distributia aplicatiei Android, de pe serverul propriu.
#
# DE CE EXISTA. Aplicatia nu vine dintr-un magazin, deci nimeni nu-i spune ca a
# aparut o versiune noua. Interfata se actualizeaza singura (WebView-ul incarca
# aplicatia live), dar CARCASA nativa — permisiuni, plugin-uri, versiune de
# Capacitor — nu. Fara ruta asta, singurul mecanism e „Ion isi aminteste sa
# intrebe", adica exact felul de intretinere care nu se face.
#
# Android NU permite unei aplicatii instalate lateral sa se actualizeze in
# tacere: dialogul de instalare il apesi tu. Ce se automatizeaza aici e tot
# restul — aflatul, descarcatul, si predarea fisierului catre instalator.
#
# UNDE STA APK-ul: in `uploads/app/`, adica in AFARA gitului (`uploads/` e
# gitignored). Nu prin repo: 5 MB per versiune ar ramane pentru totdeauna in
# istoric, iar deploy-ul (`git reset --hard`) le-ar tara pe toate la fiecare
# repornire. Build-ul il urca cu tokenul de masina, ca `/api/deploy`.
#
# SEMNATURA e contractul pe care se sprijine totul: Android accepta o
# actualizare doar daca e semnata cu ACEEASI cheie ca aplicatia instalata. De
# aceea cheia sta in afara repoului si nu se pierde — vezi
# `frontend/android/app/build.gradle`.

import hashlib
import json
import logging
import os
import re
from datetime import datetime

from flask import Blueprint, jsonify, request, send_file

from utils import login_required, _check_api_token, UPLOAD_FOLDER

logger = logging.getLogger(__name__)

app_update_bp = Blueprint('app_update', __name__)

DIR_APP = os.path.join(UPLOAD_FOLDER, 'app')
CALE_APK = os.path.join(DIR_APP, 'pif.apk')
CALE_META = os.path.join(DIR_APP, 'meta.json')

# Semnatura ZIP. Un APK E o arhiva zip; daca primele doua octete nu sunt „PK",
# fisierul nu e ce spune ca e si nu are rost sa ajunga pe telefon.
MAGIC_ZIP = b'PK'
MAX_APK = 100 * 1024 * 1024


def _meta():
    try:
        with open(CALE_META, encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


@app_update_bp.route('/api/app/upload', methods=['POST'])
def app_upload():
    """Urca un APK nou. Doar masina-la-masina (Bearer), ca `/api/deploy`.

    Deliberat FARA sesiune: singurul care urca e scriptul de build, iar o ruta
    care accepta si sesiune ar putea fi declansata dintr-o pagina deschisa.
    """
    if not _check_api_token():
        return jsonify({'error': 'Unauthorized'}), 401
    f = request.files.get('apk')
    if f is None:
        return jsonify({'error': 'Lipseste fisierul (camp `apk`).'}), 400

    cod = (request.form.get('versionCode') or '').strip()
    nume = (request.form.get('versionName') or '').strip()
    if not cod.isdigit():
        return jsonify({'error': 'versionCode trebuie sa fie un numar.'}), 400
    if not re.fullmatch(r'[0-9A-Za-z.\-_]{1,40}', nume or ''):
        return jsonify({'error': 'versionName invalid.'}), 400

    os.makedirs(DIR_APP, exist_ok=True)
    tmp = CALE_APK + '.nou'
    f.save(tmp)
    marime = os.path.getsize(tmp)
    try:
        with open(tmp, 'rb') as fh:
            if fh.read(2) != MAGIC_ZIP:
                raise ValueError('nu e un APK (lipseste semnatura zip)')
        if marime > MAX_APK:
            raise ValueError(f'prea mare ({marime // 1024 // 1024} MB)')
        h = hashlib.sha256()
        with open(tmp, 'rb') as fh:
            for bloc in iter(lambda: fh.read(1 << 20), b''):
                h.update(bloc)
    except ValueError as e:
        os.remove(tmp)
        return jsonify({'error': str(e)}), 400

    # Inlocuirea e ULTIMUL pas: pana aici, aplicatia veche ramane descarcabila.
    os.replace(tmp, CALE_APK)
    meta = {
        'versionCode': int(cod),
        'versionName': nume,
        'size': marime,
        'sha256': h.hexdigest(),
        'at': datetime.now().isoformat(timespec='seconds'),
        'notes': (request.form.get('notes') or '').strip()[:500],
    }
    with open(CALE_META, 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    logger.info('App update: urcat %s (%s), %d KB', nume, cod, marime // 1024)
    return jsonify({'ok': True, **meta})


@app_update_bp.route('/api/app/version', methods=['GET'])
@login_required
def app_version():
    """Ce versiune e disponibila. Aplicatia o compara cu a ei, la pornire."""
    m = _meta()
    if not m or not os.path.isfile(CALE_APK):
        return jsonify({'disponibil': False})
    return jsonify({'disponibil': True, **m})


@app_update_bp.route('/api/app/apk', methods=['GET'])
@login_required
def app_apk():
    """Fisierul propriu-zis. Numele include versiunea, ca sa se vada in
    descarcari CE s-a luat — un „pif.apk" peste altul nu spune nimic."""
    m = _meta() or {}
    if not os.path.isfile(CALE_APK):
        return jsonify({'error': 'Niciun APK urcat.'}), 404
    return send_file(
        CALE_APK,
        mimetype='application/vnd.android.package-archive',
        as_attachment=True,
        download_name='pif-%s.apk' % (m.get('versionName') or 'latest'),
        conditional=True,
    )

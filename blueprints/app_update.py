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
# aceea cheia de release a APK-urilor sta in afara depozitului si nu se pierde;
# acum o foloseste build-ul Torqa, din repo-ul Torqa (aici nu exista cod Android).
#
# CANALE. Doua aplicatii Android se actualizeaza de aici, fiecare cu semnatura ei:
#   `pif`   — aplicatia veche (`org.iupif.pif`, un WebView peste site), retrasa pe
#             2026-10-03 dar inca instalata cateva zile: se mai CITESTE (versiune,
#             APK), iar pe canalul ei se urca doar cu `canal=pif` scris.
#   `torqa` — Torqa nativ (`org.iupif.torqa`, build propriu din Super Productivity).
# Canalul se alege cu `canal=` (camp de formular la urcare, parametru de query la
# citire). Fiecare canal are fisierele lui, deci un APK nu il poate inlocui pe
# celalalt. La CITIRE un apel fara `canal` raspunde pe `pif` (aplicatia veche nu stie
# de canale). La URCARE `canal` e obligatoriu: lipsa lui, o valoare necunoscuta si una
# GOALA dau 400 — o variabila nesetata in scriptul de build nu are voie sa cada pe un
# canal implicit si sa suprascrie o aplicatie cu alta.

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

# Canalul la CITIRE cand `canal` lipseste (aplicatia veche nu stie de canale). Urcarea nu
# are canal implicit: vezi `app_upload`.
CANAL_IMPLICIT = 'pif'
# canal -> (fisierul APK, fisierul de meta, prefixul numelui la descarcare).
# `pif` pastreaza numele de dinainte de canale: serverul de productie are deja
# `uploads/app/pif.apk` + `meta.json`.
CANALE = {
    'pif': ('pif.apk', 'meta.json', 'pif'),
    'torqa': ('torqa.apk', 'torqa-meta.json', 'torqa'),
}

# Semnatura ZIP. Un APK E o arhiva zip; daca primele doua octete nu sunt „PK",
# fisierul nu e ce spune ca e si nu are rost sa ajunga pe telefon.
MAGIC_ZIP = b'PK'
MAX_APK = 100 * 1024 * 1024


def _canal(valoare):
    """Numele canalului pentru valoarea primita, sau None daca nu exista.

    `None` (parametru absent) = canalul implicit, `pif`: doar la CITIRE — urcarea refuza lipsa
    lui inainte sa ajunga aici (`app_upload`). Un sir gol NU e „absent": vezi comentariul de
    la CANALE.
    """
    if valoare is None:
        return CANAL_IMPLICIT
    nume = valoare.strip().lower()
    return nume if nume in CANALE else None


def _cai(canal):
    """(cale APK, cale meta) ale canalului. Citeste `DIR_APP` la apel, nu la import,
    ca testele sa-l poata muta intr-un director temporar."""
    apk, meta, _ = CANALE[canal]
    return os.path.join(DIR_APP, apk), os.path.join(DIR_APP, meta)


def _canal_necunoscut(valoare):
    return jsonify({'error': 'Canal necunoscut: %r (canale: %s).'
                             % (valoare, ', '.join(sorted(CANALE)))}), 400


def _canal_lipsa():
    return jsonify({'error': 'Lipseste `canal` (canale: %s). Urcarea nu are canal implicit.'
                             % ', '.join(sorted(CANALE))}), 400


def _meta(canal=CANAL_IMPLICIT):
    try:
        with open(_cai(canal)[1], encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


@app_update_bp.route('/api/app/upload', methods=['POST'])
def app_upload():
    """Urca un APK nou. Doar masina-la-masina (Bearer), ca `/api/deploy`.

    Deliberat FARA sesiune: singurul care urca e scriptul de build, iar o ruta
    care accepta si sesiune ar putea fi declansata dintr-o pagina deschisa.
    Campul `canal` alege aplicatia (`pif` sau `torqa`) si e OBLIGATORIU; vezi CANALE.
    """
    if not _check_api_token():
        return jsonify({'error': 'Unauthorized'}), 401
    brut = request.form.get('canal')
    if brut is None:
        return _canal_lipsa()
    canal = _canal(brut)
    if canal is None:
        return _canal_necunoscut(brut)
    cale_apk, cale_meta = _cai(canal)
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
    tmp = cale_apk + '.nou'
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
    os.replace(tmp, cale_apk)
    meta = {
        'versionCode': int(cod),
        'versionName': nume,
        'size': marime,
        'sha256': h.hexdigest(),
        'at': datetime.now().isoformat(timespec='seconds'),
        'notes': (request.form.get('notes') or '').strip()[:500],
    }
    with open(cale_meta, 'w', encoding='utf-8') as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
    logger.info('App update [%s]: urcat %s (%s), %d KB', canal, nume, cod, marime // 1024)
    return jsonify({'ok': True, **meta})


@app_update_bp.route('/api/app/version', methods=['GET'])
@login_required
def app_version():
    """Ce versiune e disponibila. Aplicatia o compara cu a ei, la pornire.
    `?canal=torqa` intreaba de Torqa nativ; fara parametru, raspunde pe `pif` (aplicatia veche)."""
    brut = request.args.get('canal')
    canal = _canal(brut)
    if canal is None:
        return _canal_necunoscut(brut)
    m = _meta(canal)
    if not m or not os.path.isfile(_cai(canal)[0]):
        return jsonify({'disponibil': False})
    return jsonify({'disponibil': True, **m})


@app_update_bp.route('/api/app/apk', methods=['GET'])
@login_required
def app_apk():
    """Fisierul propriu-zis. Numele include versiunea, ca sa se vada in
    descarcari CE s-a luat — un „pif.apk" peste altul nu spune nimic.
    `?canal=torqa` da APK-ul Torqa (`torqa-<versionName>.apk`); fara parametru, cel vechi (`pif`)."""
    brut = request.args.get('canal')
    canal = _canal(brut)
    if canal is None:
        return _canal_necunoscut(brut)
    cale_apk = _cai(canal)[0]
    m = _meta(canal) or {}
    if not os.path.isfile(cale_apk):
        return jsonify({'error': 'Niciun APK urcat.'}), 404
    return send_file(
        cale_apk,
        mimetype='application/vnd.android.package-archive',
        as_attachment=True,
        download_name='%s-%s.apk' % (CANALE[canal][2], m.get('versionName') or 'latest'),
        conditional=True,
    )

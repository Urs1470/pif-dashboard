# Loturile de mail pentru Mail Tasks: PC-ul de job exporta mailurile noi din Outlook, iar judecata (filtrul, Claude,
# taskurile) ruleaza pe laptop-server. Din 2026-11-17 (etapa 3 a centralizarii; Knowledge
# references/decizii/2026-11-17-runner-pc.md si docs/decizii/2026-11-17-mail-tasks-pe-server.md).
#
#   PC   `mail-tasks.py trimite`: GET /api/mail/lot (cat de departe exporta), apoi PUT /api/mail/lot cu exportul
#   srv  `mail-tasks.py server` (timer pe laptop): GET lista, GET /api/mail/lot/<id>, ruleaza, POST .../gata
#
# DE CE FISIERE SI NU O TABELA (tiparul `blueprints/materiale.py`): un lot traieste minute, pana il ia serverul, apoi
# se sterge; fara schema, fara migrare. Pe disc:
#   uploads/mail-lot/<id>.json   loturile in asteptare (exportul Outlook, cu corpul mailurilor)
#   uploads/mail-lot/stare.json  ultima rulare reusita si rezultatul ultimului lot (fara continut de mail)
# Un lot uitat mai mult de 7 zile se sterge la urmatorul PUT: continutul mailurilor nu ramane pe server.
#
# Doar tokenul de masina (si sesiunea cu PIN): tokenul de dispozitiv nu citeste mailuri (utils.DEVICE_TOKEN_DENIED).

import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from utils import login_required, UPLOAD_FOLDER

logger = logging.getLogger('pif_dashboard')

mail_lot_bp = Blueprint('mail_lot', __name__)

DIR_LOT = os.path.join(UPLOAD_FOLDER, 'mail-lot')
STARE = 'stare.json'
MAX_CORP = 12 * 1024 * 1024
MAX_MAILURI = 1000
MAX_REZULTAT = 2000
PASTRARE = timedelta(days=7)
_RE_ID = re.compile(r'\d{8}T\d{6}-[0-9a-f]{6}')


class EroareCorp(ValueError):
    pass


def _cale(nume):
    return os.path.join(DIR_LOT, nume)


def _scrie_atomic(nume, octeti):
    os.makedirs(DIR_LOT, exist_ok=True)
    cale = _cale(nume)
    tmp = '%s.%s.tmp' % (cale, secrets.token_hex(3))
    try:
        with open(tmp, 'wb') as fh:
            fh.write(octeti)
            fh.flush()
            os.fsync(fh.fileno())
        for incercare in range(5):               # Windows: un cititor deschis da PermissionError
            try:
                os.replace(tmp, cale)
                break
            except PermissionError:
                if incercare == 4:
                    raise
                time.sleep(0.1)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def _citeste_json(nume, implicit=None):
    try:
        with open(_cale(nume), encoding='utf-8') as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return implicit


def _loturi():
    """[(id, cale)] in asteptare, cele mai vechi intai."""
    if not os.path.isdir(DIR_LOT):
        return []
    ids = sorted(f[:-5] for f in os.listdir(DIR_LOT) if f.endswith('.json') and _RE_ID.fullmatch(f[:-5]))
    return [(i, _cale(i + '.json')) for i in ids]


def _primit(lot_id):
    return datetime.strptime(lot_id[:15], '%Y%m%dT%H%M%S')


def _curata(acum):
    """Sterge loturile mai vechi de PASTRARE; intoarce cate."""
    n = 0
    for i, cale in _loturi():
        if acum - _primit(i) > PASTRARE:
            try:
                os.remove(cale)
                n += 1
            except OSError:
                pass
    return n


def valideaza_export(corp):
    """Exportul lui export-outlook.ps1: {meta: {...}, mails: [...]}. Doar forma: continutul il judeca Mail Tasks."""
    if not isinstance(corp, dict):
        raise EroareCorp('corpul trebuie sa fie un obiect JSON')
    if not isinstance(corp.get('meta'), dict):
        raise EroareCorp('meta: obiectul exportului Outlook (generatedAt, ...)')
    mails = corp.get('mails')
    if not isinstance(mails, list):
        raise EroareCorp('mails: trebuie sa fie o lista')
    if len(mails) > MAX_MAILURI:
        raise EroareCorp('mails: maximum %d' % MAX_MAILURI)
    for ix, m in enumerate(mails):
        if not isinstance(m, dict):
            raise EroareCorp('mails[%d]: trebuie sa fie obiect' % ix)
        for camp in ('received', 'subject', 'from'):
            if m.get(camp) is not None and not isinstance(m[camp], str):
                raise EroareCorp('mails[%d].%s: text' % (ix, camp))
    return corp


def _stare_publica():
    s = _citeste_json(STARE, {}) or {}
    return {'ultima_rulare': s.get('ultima_rulare'), 'ultimul_lot': s.get('ultimul_lot')}


@mail_lot_bp.route('/api/mail/lot', methods=['PUT'])
@login_required
def put_lot():
    """Un export nou de la PC. Raspuns: {ok, id, mailuri, in_asteptare}."""
    if request.content_length is not None and request.content_length > MAX_CORP:
        return jsonify({'error': 'corp prea mare (maxim 12 MB)'}), 413
    brut = request.stream.read(MAX_CORP + 1)
    if len(brut) > MAX_CORP:
        return jsonify({'error': 'corp prea mare (maxim 12 MB)'}), 413
    try:
        corp = valideaza_export(json.loads(brut.decode('utf-8')))
    except (UnicodeDecodeError, ValueError, RecursionError) as e:
        mesaj = str(e) if isinstance(e, EroareCorp) else 'Body JSON invalid sau lipsa'
        return jsonify({'error': mesaj}), 400
    acum = datetime.now()
    _curata(acum)
    lot_id = '%s-%s' % (acum.strftime('%Y%m%dT%H%M%S'), secrets.token_hex(3))
    try:
        _scrie_atomic(lot_id + '.json', json.dumps(corp, ensure_ascii=False).encode('utf-8'))
    except OSError:
        logger.exception('Mail lot: scrierea a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea lotului.'}), 500
    return jsonify({'ok': True, 'id': lot_id, 'mailuri': len(corp['mails']), 'in_asteptare': len(_loturi())})


@mail_lot_bp.route('/api/mail/lot', methods=['GET'])
@login_required
def lista_loturi():
    """Starea (ultima rulare reusita, ultimul lot) si loturile in asteptare, fara continut."""
    loturi = []
    for i, cale in _loturi():
        try:
            marime = os.path.getsize(cale)
        except OSError:
            continue
        loturi.append({'id': i, 'primit': _primit(i).isoformat(), 'octeti': marime})
    return jsonify({'stare': _stare_publica(), 'loturi': loturi})


@mail_lot_bp.route('/api/mail/lot/<lot_id>', methods=['GET'])
@login_required
def get_lot(lot_id):
    if not _RE_ID.fullmatch(lot_id):
        return jsonify({'error': 'id invalid'}), 400
    corp = _citeste_json(lot_id + '.json')
    if corp is None:
        return jsonify({'error': 'lotul nu exista (deja procesat sau sters)'}), 404
    return jsonify(corp)


@mail_lot_bp.route('/api/mail/lot/<lot_id>/gata', methods=['POST'])
@login_required
def lot_gata(lot_id):
    """Serverul a terminat lotul: se sterge, iar starea retine rezultatul. Corp: {cod: int, rezultat: text,
    ultima_rulare: ISO sau null}. `ultima_rulare` se scrie doar la cod 0 (cu erori, fereastra urmatoare le reia)."""
    if not _RE_ID.fullmatch(lot_id):
        return jsonify({'error': 'id invalid'}), 400
    corp = request.get_json(silent=True)
    if not isinstance(corp, dict) or not isinstance(corp.get('cod'), int) or isinstance(corp.get('cod'), bool):
        return jsonify({'error': 'corp: {cod: intreg, rezultat: text, ultima_rulare: ISO|null}'}), 400
    rezultat = corp.get('rezultat') or ''
    if not isinstance(rezultat, str) or len(rezultat) > MAX_REZULTAT:
        return jsonify({'error': 'rezultat: text de cel mult %d caractere' % MAX_REZULTAT}), 400
    ultima = corp.get('ultima_rulare')
    if ultima is not None:
        try:
            datetime.fromisoformat(ultima)
        except (TypeError, ValueError):
            return jsonify({'error': 'ultima_rulare: data si ora ISO'}), 400
    cale = _cale(lot_id + '.json')
    if not os.path.exists(cale):
        return jsonify({'error': 'lotul nu exista (deja procesat sau sters)'}), 404
    stare = _citeste_json(STARE, {}) or {}
    if corp['cod'] == 0 and ultima:
        stare['ultima_rulare'] = ultima
    stare['ultimul_lot'] = {'id': lot_id, 'terminat': datetime.now().isoformat(timespec='seconds'),
                            'cod': corp['cod'], 'rezultat': rezultat}
    try:
        _scrie_atomic(STARE, json.dumps(stare, ensure_ascii=False).encode('utf-8'))
        os.remove(cale)
    except OSError:
        logger.exception('Mail lot: inchiderea lotului a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la inchiderea lotului.'}), 500
    return jsonify({'ok': True, 'stare': _stare_publica()})

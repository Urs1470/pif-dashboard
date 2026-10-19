# Outlook Blueprint
# Snapshot-ul calendarului Outlook al lui Ion, urcat de pe PC-ul de job si citit de Torqa prin
# `GET /api/calendar` (cheia `outlook`, vezi `admin.calendar_view`).
#
# DE CE UN FISIER SI NU O TABELA. Un script de pe PC-ul de job (COM, Outlook clasic) urca la 15
# de minute tot ce e in fereastra de ~10 saptamani: snapshot-ul se reface singur, deci nu are
# nevoie de schema, de migrare, de backup. `uploads/outlook/calendar.json` se rescrie intreg,
# atomic (fisier temporar + `os.replace`), asa ca o citire vede ori snapshot-ul vechi, ori pe
# cel nou, niciodata jumatati. Nu intra in backup si nu se atinge la restore: dupa o restaurare
# apare din nou in cel mult 15 minute. Decizia: docs/decizii/2026-10-19-calendarul-outlook.md.
#
# Contractul corpului e in `valideaza_snapshot`; orice abatere da 400 cu campul si indexul
# evenimentului, iar snapshot-ul existent ramane neatins.

import json
import logging
import os
import re
import secrets
import time
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from utils import login_required, UPLOAD_FOLDER

logger = logging.getLogger('pif_dashboard')

outlook_bp = Blueprint('outlook', __name__)

DIR_OUTLOOK = os.path.join(UPLOAD_FOLDER, 'outlook')
NUME_FISIER = 'calendar.json'

MAX_CORP = 1024 * 1024
MAX_EVENIMENTE = 2000
MAX_TEXT = 500
OCUPARE = ('free', 'tentative', 'busy', 'oof', 'elsewhere')

_RE_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
_RE_DATA = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_RE_DATA_ORA = re.compile(
    r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,9}))?)?'
    r'(Z|[+-]\d{2}:\d{2})')


class EroareCorp(ValueError):
    """Corpul nu respecta contractul; mesajul spune campul (si indexul evenimentului)."""


def _data(valoare):
    """`YYYY-MM-DD` -> date, sau None."""
    if not isinstance(valoare, str):
        return None
    m = _RE_DATA.fullmatch(valoare)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _data_ora(valoare):
    """ISO cu offset obligatoriu -> datetime cu fus, sau None. Scris de mana, nu cu
    `fromisoformat`: acceptarea lui (`Z`, fractiuni, data singura) difera de la o versiune de
    Python la alta, iar serverul si PC-ul de dezvoltare nu au neaparat aceeasi."""
    if not isinstance(valoare, str):
        return None
    m = _RE_DATA_ORA.fullmatch(valoare)
    if not m:
        return None
    an, luna, zi, ora, minut, sec, frac, fus = m.groups()
    try:
        if fus == 'Z':
            tz = timezone.utc
        else:
            ore, minute = int(fus[1:3]), int(fus[4:6])
            if ore > 23 or minute > 59:
                return None
            delta = timedelta(hours=ore, minutes=minute)
            tz = timezone(-delta if fus[0] == '-' else delta)
        micro = int((frac or '0')[:6].ljust(6, '0'))
        return datetime(int(an), int(luna), int(zi), int(ora), int(minut), int(sec or 0), micro, tzinfo=tz)
    except ValueError:
        return None


def _text(ev, camp, ix):
    valoare = ev.get(camp)
    if not isinstance(valoare, str):
        raise EroareCorp('events[%d].%s: trebuie sa fie text' % (ix, camp))
    if len(valoare) > MAX_TEXT:
        raise EroareCorp('events[%d].%s: maximum %d de caractere' % (ix, camp, MAX_TEXT))
    return valoare


def _bool(ev, camp, ix):
    valoare = ev.get(camp)
    if not isinstance(valoare, bool):
        raise EroareCorp('events[%d].%s: trebuie sa fie true sau false' % (ix, camp))
    return valoare


def _eveniment(ev, ix, ids):
    if not isinstance(ev, dict):
        raise EroareCorp('events[%d]: trebuie sa fie obiect' % ix)
    id_ = ev.get('id')
    if not isinstance(id_, str) or not _RE_ID.fullmatch(id_):
        raise EroareCorp('events[%d].id: 1-64 de caractere din A-Z a-z 0-9 _ -' % ix)
    if id_ in ids:
        raise EroareCorp('events[%d].id: duplicat in snapshot' % ix)
    ids.add(id_)
    titlu = _text(ev, 'title', ix)
    locatie = _text(ev, 'location', ix)
    toata_ziua = _bool(ev, 'allDay', ix)
    privat = _bool(ev, 'isPrivate', ix)
    ocupare = ev.get('busy')
    if not isinstance(ocupare, str) or ocupare not in OCUPARE:
        raise EroareCorp('events[%d].busy: una din %s' % (ix, '|'.join(OCUPARE)))
    if toata_ziua:
        start, sfarsit = _data(ev.get('start')), _data(ev.get('end'))
        tip = 'YYYY-MM-DD (allDay=true)'
    else:
        start, sfarsit = _data_ora(ev.get('start')), _data_ora(ev.get('end'))
        tip = 'data si ora ISO cu offset, ex. 2026-10-20T09:00:00+03:00 (allDay=false)'
    if start is None:
        raise EroareCorp('events[%d].start: trebuie sa fie %s' % (ix, tip))
    if sfarsit is None:
        raise EroareCorp('events[%d].end: trebuie sa fie %s' % (ix, tip))
    if sfarsit < start:
        raise EroareCorp('events[%d].end: nu poate fi inainte de start' % ix)
    # Se pastreaza stringurile primite (data locala din ele e cea pe care citeste GET-ul).
    return {
        'id': id_, 'title': titlu, 'allDay': toata_ziua,
        'start': ev['start'], 'end': ev['end'],
        'location': locatie, 'busy': ocupare, 'isPrivate': privat,
    }


def valideaza_snapshot(corp):
    """Corpul JSON -> snapshot normalizat (doar campurile din contract; ce e in plus se ignora),
    sau EroareCorp. Nu scrie nimic."""
    if not isinstance(corp, dict):
        raise EroareCorp('corpul trebuie sa fie un obiect JSON')
    if _data_ora(corp.get('generatedAt')) is None:
        raise EroareCorp('generatedAt: data si ora ISO cu offset, ex. 2026-10-19T14:05:00+03:00')
    if corp.get('source') != 'outlook':
        raise EroareCorp('source: trebuie sa fie "outlook"')
    inceput, sfarsit = _data(corp.get('windowStart')), _data(corp.get('windowEnd'))
    if inceput is None:
        raise EroareCorp('windowStart: trebuie sa fie YYYY-MM-DD')
    if sfarsit is None:
        raise EroareCorp('windowEnd: trebuie sa fie YYYY-MM-DD')
    if sfarsit < inceput:
        raise EroareCorp('windowEnd: nu poate fi inainte de windowStart')
    evenimente = corp.get('events')
    if not isinstance(evenimente, list):
        raise EroareCorp('events: trebuie sa fie o lista')
    if len(evenimente) > MAX_EVENIMENTE:
        raise EroareCorp('events: maximum %d de evenimente' % MAX_EVENIMENTE)
    ids = set()
    return {
        'generatedAt': corp['generatedAt'],
        'source': 'outlook',
        'windowStart': corp['windowStart'],
        'windowEnd': corp['windowEnd'],
        'events': [_eveniment(ev, ix, ids) for ix, ev in enumerate(evenimente)],
    }


def _cale():
    return os.path.join(DIR_OUTLOOK, NUME_FISIER)


def _scrie_atomic(snapshot):
    """Fisier alaturat, fsync, apoi `os.replace`: nu ramane niciodata un calendar.json taiat."""
    os.makedirs(DIR_OUTLOOK, exist_ok=True)
    cale = _cale()
    tmp = '%s.%s.tmp' % (cale, secrets.token_hex(3))
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(snapshot, fh, ensure_ascii=False)
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


def citeste_snapshot():
    """Snapshot-ul de pe disc, sau None daca nu exista ori nu se poate citi. Un fisier corupt
    nu strica `/api/calendar`: se logheaza si Torqa vede „fara Outlook" pana la urmatoarea
    urcare (cel mult 15 minute)."""
    try:
        with open(_cale(), 'r', encoding='utf-8') as fh:
            snapshot = json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):                # ValueError acopera JSONDecodeError si UnicodeDecodeError
        logger.warning('Outlook: calendar.json nu se poate citi; se ignora', exc_info=True)
        return None
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get('events'), list)
            or not isinstance(snapshot.get('generatedAt'), str)):
        logger.warning('Outlook: calendar.json are alta forma decat cea scrisa; se ignora')
        return None
    return snapshot


def evenimente_in_fereastra(snapshot, start, sfarsit):
    """Cheia `outlook` din `/api/calendar`: {generatedAt, events} cu evenimentele care se
    suprapun cu `[start, sfarsit)` (stringuri YYYY-MM-DD), sau None fara snapshot.

    Suprapunerea e pe data LOCALA din string (primele 10 caractere), fara conversie de fus:
    ziua unui eveniment e cea pe care o vede Outlook la Ion. Toata ziua: `end` e exclusiv.
    Cu ora: evenimentul care se termina in ziua ferestrei de inceput intra."""
    if snapshot is None:
        return None
    iesire = []
    for ev in snapshot['events']:
        try:
            s, e = ev['start'][:10], ev['end'][:10]
            if ev['allDay']:
                intra = s < sfarsit and e > start
            else:
                intra = s < sfarsit and e >= start
        except (TypeError, KeyError):
            continue                              # un rand stricat nu strica restul
        if intra:
            iesire.append(ev)
    return {'generatedAt': snapshot['generatedAt'], 'events': iesire}


@outlook_bp.route('/api/outlook/calendar', methods=['PUT'])
@login_required
def put_calendar():
    """Inlocuieste snapshot-ul calendarului Outlook. Sesiune sau Bearer `PIF_API_TOKEN`;
    tokenul de dispozitiv e refuzat (`DEVICE_TOKEN_DENIED`): un telefon pierdut nu scrie
    calendarul. Idempotent: aceeasi cerere de doua ori lasa acelasi fisier.
    Raspuns: {ok, count}."""
    if request.content_length is not None and request.content_length > MAX_CORP:
        return jsonify({'error': 'corp prea mare (maxim 1 MB)'}), 413
    brut = request.stream.read(MAX_CORP + 1)      # si fara Content-Length (chunked) plafonul ramane
    if len(brut) > MAX_CORP:
        return jsonify({'error': 'corp prea mare (maxim 1 MB)'}), 413
    try:
        corp = json.loads(brut.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return jsonify({'error': 'Body JSON invalid sau lipsa'}), 400
    try:
        snapshot = valideaza_snapshot(corp)
    except EroareCorp as e:
        logger.warning('Outlook: snapshot respins: %s', e)
        return jsonify({'error': str(e)}), 400
    try:
        _scrie_atomic(snapshot)
    except OSError:
        logger.exception('Outlook: scrierea snapshot-ului a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea snapshot-ului.'}), 500
    return jsonify({'ok': True, 'count': len(snapshot['events'])})

# System maintenance Blueprint
# Pagina „System maintenance" din Torqa: tot ce cere interventia lui Ion pentru mentinerea
# sistemului. Trei surse (laptop-server, PC-ul de job, IONPC) urca fiecare un snapshot JSON la
# `PUT /api/sistem/sursa/<sursa>`; Torqa citeste un singur `GET /api/sistem` si trimite deciziile
# la `POST /api/sistem/decizie`; serverul le consuma prin `GET /api/sistem/decizii` si
# `POST /api/sistem/decizii/<uid>/consumat`.
#
# DE CE FISIERE SI NU TABELE (tiparul `blueprints/outlook.py` si `blueprints/materiale.py`):
# fiecare rulare trimite snapshot-ul complet, care se reface singur; fara schema, fara migrare.
# Pe disc, sub `<uploads>/sistem/`:
#   <sursa>.json      ultimul snapshot al sursei, scris atomic
#   decizii.jsonl     deciziile din Torqa, un rand pe decizie, rescris atomic (max 500 de randuri)
#   amanari.json      {id item: pana cand e amanat}, scris atomic, cu amanarile expirate taiate
#   decizii.lock      doar pentru blocare: doi workeri nu rescriu deciziile deodata
#
# Contractul v1.1 (aditiv peste v1; Torqa 1171 citeste fara erori): o decizie are un ciclu de viata
# in asteptare -> preluata (de consumator) -> consumata, sau anulata de Ion cat nu e preluata;
# `istoric` in vedere, amanarea unui item si masinile asteptate care nu au raportat.
#
# Validarea e STRICTA (contractul v1): orice camp in plus sau lipsa, orice tip gresit da 400 cu
# calea campului, iar snapshot-ul existent ramane neatins.
#
# Serverul accepta ca decizie doar o optiune pusa de sursa in snapshot: clientul nu poate trimite
# comenzi (un telefon pierdut nu poate decat sa aleaga dintre butoanele existente).

import contextlib
import json
import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone

try:
    import fcntl
except ImportError:                               # Windows
    fcntl = None
    import msvcrt

from flask import Blueprint, g, jsonify, request, session

from blueprints.outlook import _data, _data_ora
from utils import login_required, UPLOAD_FOLDER

logger = logging.getLogger('pif_dashboard')

sistem_bp = Blueprint('sistem', __name__)

DIR_SISTEM = os.path.join(UPLOAD_FOLDER, 'sistem')
FISIER_DECIZII = 'decizii.jsonl'
FISIER_BLOCARE = 'decizii.lock'
FISIER_AMANARI = 'amanari.json'

MAX_CORP = 1024 * 1024
MAX_ITEMI = 200
MAX_URMEAZA = 50
MAX_AUTOMAT = 50
MAX_JOBURI = 50
MAX_RANDURI_DECIZII = 500
MAX_ISTORIC = 20
MAX_AMANARI = 200
MAX_AMANARE_ZILE = 31
VECHIME_WARN_ORE = 26
VECHIME_ZILE_ORE = 48

# Masinile care trebuie sa raporteze: una fara snapshot valid apare in vedere cu starea `fail`.
SURSE_ASTEPTATE = ('server', 'pc-job', 'ionpc')
# Numele de fisier `<nume>.json` din director care nu sunt snapshot-uri de sursa.
NUME_REZERVATE = frozenset(('amanari',))

STARI = ('ok', 'warn', 'fail')
GRUPURI = ('decide', 'review', 'do')
STILURI = ('filled', 'tinted', 'danger')

_RE_SURSA = re.compile(r'[a-z0-9][a-z0-9-]{1,19}')
_RE_OPTIUNE = re.compile(r'[a-z0-9-]{1,20}')
_RE_UID = re.compile(r'[0-9a-f]{12}')
_RE_GENERAT = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z')

CAMPURI_SNAPSHOT = frozenset(('v', 'sursa', 'masina', 'generat', 'sanatate', 'itemi', 'urmeaza', 'automat', 'joburi'))
# v1.2 (2026-11-17, aditiv): joburile programate ale masinii (runner-ul de pe PC-uri, timerele de utilizator de pe
# laptop), ca Torqa sa arate ce ruleaza unde. `ultima` si `urmatoarea` lipsesc cand nu se stiu (null nu se accepta).
CAMPURI_JOB = frozenset(('id', 'nume', 'stare', 'ultima', 'urmatoarea', 'detaliu'))
CAMPURI_SANATATE = frozenset(('stare', 'detaliu'))
CAMPURI_ITEM = frozenset(('id', 'grup', 'titlu', 'motiv', 'etichete', 'restant_zile', 'comanda', 'creat', 'optiuni'))
CAMPURI_OPTIUNE = frozenset(('id', 'label', 'stil'))
CAMPURI_URMEAZA = frozenset(('titlu', 'data'))
CAMPURI_AUTOMAT = frozenset(('ce', 'stare', 'detaliu'))
CAMPURI_DECIZIE = frozenset(('id', 'optiune', 'text'))
CAMPURI_CONSUMAT = frozenset(('rezultat', 'stare'))
CAMPURI_AMANARE = frozenset(('id', 'pana'))
CAMPURI_GOL = frozenset()                         # anulare si preluat: corp gol sau {}


class EroareCorp(ValueError):
    """Corpul nu respecta contractul; mesajul spune calea campului."""


# --------------------------------------------------------------------------- validarea

def _obiect(v, cale, permise):
    if not isinstance(v, dict):
        raise EroareCorp('%s: trebuie sa fie obiect' % cale)
    for camp in v:
        if camp not in permise:
            raise EroareCorp('%s.%s: camp necunoscut' % (cale, camp))
    return v


def _text(obj, camp, cale, maxim, nevid=False, optional=False):
    """Textul din `obj[camp]`. `optional`: campul poate lipsi (null nu e acceptat)."""
    if camp not in obj:
        if optional:
            return None
        raise EroareCorp('%s.%s: lipseste' % (cale, camp))
    v = obj[camp]
    if not isinstance(v, str):
        raise EroareCorp('%s.%s: trebuie sa fie text' % (cale, camp))
    if len(v) > maxim:
        raise EroareCorp('%s.%s: maximum %d de caractere' % (cale, camp, maxim))
    if nevid and not v.strip():
        raise EroareCorp('%s.%s: nu poate fi gol' % (cale, camp))
    return v


def _stare(obj, camp, cale):
    v = obj.get(camp)
    if not isinstance(v, str) or v not in STARI:
        raise EroareCorp('%s.%s: una din %s' % (cale, camp, '|'.join(STARI)))


def _lista(obj, camp, cale, maxim):
    if camp not in obj:
        raise EroareCorp('%s.%s: lipseste' % (cale, camp))
    v = obj[camp]
    if not isinstance(v, list):
        raise EroareCorp('%s.%s: trebuie sa fie o lista' % (cale, camp))
    if len(v) > maxim:
        raise EroareCorp('%s.%s: maximum %d de elemente' % (cale, camp, maxim))
    return v


def _generat(v, cale):
    """ISO 8601 UTC cu `Z`, cu secunde, fara fractiuni si fara offset. Intoarce datetime."""
    if not isinstance(v, str) or not _RE_GENERAT.fullmatch(v) or _data_ora(v) is None:
        raise EroareCorp('%s: data si ora UTC cu Z, ex. 2026-11-17T08:00:03Z' % cale)
    return _data_ora(v)


def _optiune(o, cale, vazute):
    _obiect(o, cale, CAMPURI_OPTIUNE)
    id_ = o.get('id')
    if not isinstance(id_, str) or not _RE_OPTIUNE.fullmatch(id_):
        raise EroareCorp('%s.id: 1-20 de caractere din a-z 0-9 -' % cale)
    if id_ in vazute:
        raise EroareCorp('%s.id: duplicat in item' % cale)
    vazute.add(id_)
    _text(o, 'label', cale, 40, nevid=True)
    if o.get('stil') not in STILURI:
        raise EroareCorp('%s.stil: una din %s' % (cale, '|'.join(STILURI)))


def _item(it, cale, ids):
    _obiect(it, cale, CAMPURI_ITEM)
    id_ = _text(it, 'id', cale, 80, nevid=True)
    if any(ord(c) < 32 for c in id_):
        raise EroareCorp('%s.id: fara caractere de control' % cale)
    if id_ in ids:
        raise EroareCorp('%s.id: duplicat in snapshot' % cale)
    ids.add(id_)
    if it.get('grup') not in GRUPURI:
        raise EroareCorp('%s.grup: una din %s' % (cale, '|'.join(GRUPURI)))
    _text(it, 'titlu', cale, 200, nevid=True)
    _text(it, 'motiv', cale, 600)
    etichete = _lista(it, 'etichete', cale, 5)
    for ix, e in enumerate(etichete):
        if not isinstance(e, str) or not e.strip() or len(e) > 40:
            raise EroareCorp('%s.etichete[%d]: text nevid, maximum 40 de caractere' % (cale, ix))
    if 'restant_zile' in it:
        r = it['restant_zile']
        if isinstance(r, bool) or not isinstance(r, int) or r < 0:
            raise EroareCorp('%s.restant_zile: intreg >= 0, sau lipsa' % cale)
    _text(it, 'comanda', cale, 400, optional=True)
    if 'creat' in it and _data(it['creat']) is None:
        raise EroareCorp('%s.creat: AAAA-LL-ZZ, sau lipsa' % cale)
    vazute = set()
    for ix, o in enumerate(_lista(it, 'optiuni', cale, 10)):
        _optiune(o, '%s.optiuni[%d]' % (cale, ix), vazute)


def valideaza_snapshot(corp, sursa_din_cale):
    """Corpul JSON -> snapshot de scris (exact campurile din contract), sau EroareCorp cu calea
    campului. Nu scrie nimic."""
    _obiect(corp, 'corpul', CAMPURI_SNAPSHOT)
    if corp.get('v') != 1 or isinstance(corp.get('v'), bool):
        raise EroareCorp('v: trebuie sa fie 1')
    if corp.get('sursa') != sursa_din_cale:
        raise EroareCorp('sursa: trebuie sa fie la fel cu cea din cale (%s)' % sursa_din_cale)
    _text(corp, 'masina', 'corpul', 80, nevid=True)
    _generat(corp.get('generat'), 'generat')
    sanatate = _obiect(corp.get('sanatate'), 'sanatate', CAMPURI_SANATATE)
    _stare(sanatate, 'stare', 'sanatate')
    _text(sanatate, 'detaliu', 'sanatate', 200)
    ids = set()
    for ix, it in enumerate(_lista(corp, 'itemi', 'corpul', MAX_ITEMI)):
        _item(it, 'itemi[%d]' % ix, ids)
    for ix, u in enumerate(_lista(corp, 'urmeaza', 'corpul', MAX_URMEAZA)):
        cale = 'urmeaza[%d]' % ix
        _obiect(u, cale, CAMPURI_URMEAZA)
        _text(u, 'titlu', cale, 200, nevid=True)
        if _data(u.get('data')) is None:
            raise EroareCorp('%s.data: AAAA-LL-ZZ' % cale)
    for ix, a in enumerate(_lista(corp, 'automat', 'corpul', MAX_AUTOMAT)):
        cale = 'automat[%d]' % ix
        _obiect(a, cale, CAMPURI_AUTOMAT)
        _text(a, 'ce', cale, 200, nevid=True)
        _stare(a, 'stare', cale)
        _text(a, 'detaliu', cale, 200)
    snap = {k: corp[k] for k in ('v', 'sursa', 'masina', 'generat', 'sanatate', 'itemi', 'urmeaza', 'automat')}
    if 'joburi' in corp:
        ids = set()
        for ix, j in enumerate(_lista(corp, 'joburi', 'corpul', MAX_JOBURI)):
            cale = 'joburi[%d]' % ix
            _obiect(j, cale, CAMPURI_JOB)
            id_ = _text(j, 'id', cale, 60, nevid=True)
            if id_ in ids:
                raise EroareCorp('%s.id: duplicat (%s)' % (cale, id_))
            ids.add(id_)
            _text(j, 'nume', cale, 80, nevid=True)
            _stare(j, 'stare', cale)
            for camp in ('ultima', 'urmatoarea'):
                if camp in j:
                    _generat(j[camp], '%s.%s' % (cale, camp))
            _text(j, 'detaliu', cale, 200)
        snap['joburi'] = corp['joburi']
    return snap


# --------------------------------------------------------------------------- discul

def _cale(nume):
    return os.path.join(DIR_SISTEM, nume)


def _acum():
    return datetime.now(timezone.utc)


def _z(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def _scrie_atomic(nume, octeti):
    """Fisier alaturat, fsync, apoi `os.replace`: un cititor vede ori fisierul vechi, ori pe cel nou.
    (Aceeasi tehnica ca `blueprints/materiale.py`; acolo directorul e fixat, de aceea copia.)"""
    os.makedirs(DIR_SISTEM, exist_ok=True)
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


_FIR = threading.Lock()


@contextlib.contextmanager
def _blocat():
    """Un singur scriitor pe `decizii.jsonl`: firul curent (threading) si celelalte procese
    (gunicorn are 2 workeri) printr-un fisier de blocare. Citirea nu se blocheaza: fisierul se
    inlocuieste atomic."""
    os.makedirs(DIR_SISTEM, exist_ok=True)
    with _FIR:
        with open(_cale(FISIER_BLOCARE), 'a+b') as fh:
            if fcntl is not None:
                fcntl.flock(fh, fcntl.LOCK_EX)
            else:                                 # pragma: no cover - doar Windows
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(fh, fcntl.LOCK_UN)
                else:                             # pragma: no cover
                    fh.seek(0)
                    msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)


def _citeste_snapshot(sursa):
    """Snapshot-ul sursei, sau None daca lipseste, nu se poate citi ori nu mai respecta
    contractul (un fisier stricat nu strica GET-ul: se logheaza si sursa dispare din vedere)."""
    try:
        with open(_cale(sursa + '.json'), 'rb') as fh:
            snapshot = json.loads(fh.read().decode('utf-8'))
        return valideaza_snapshot(snapshot, sursa)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, RecursionError) as e:   # EroareCorp, JSONDecodeError, UnicodeDecodeError
        logger.warning('Sistem: %s.json nu se poate citi (%s); se ignora', sursa, e)
        return None


def _surse():
    """[(sursa, snapshot)] pentru fisierele valide din director, in ordinea numelui."""
    try:
        nume = sorted(os.listdir(DIR_SISTEM))
    except FileNotFoundError:
        return []
    iesire = []
    for n in nume:
        if not n.endswith('.json') or not _RE_SURSA.fullmatch(n[:-5]) or n[:-5] in NUME_REZERVATE:
            continue
        snapshot = _citeste_snapshot(n[:-5])
        if snapshot is not None:
            iesire.append((n[:-5], snapshot))
    return iesire


def _citeste_decizii():
    """Randurile din decizii.jsonl, in ordinea din fisier. Un rand stricat se logheaza si se sare."""
    try:
        with open(_cale(FISIER_DECIZII), 'rb') as fh:
            brut = fh.read()
    except FileNotFoundError:
        return []
    except OSError:
        logger.warning('Sistem: %s nu se poate citi', FISIER_DECIZII, exc_info=True)
        return []
    randuri = []
    for nr, linie in enumerate(brut.decode('utf-8', errors='replace').splitlines(), 1):
        if not linie.strip():
            continue
        try:
            r = json.loads(linie)
        except ValueError:
            r = None
        if (not isinstance(r, dict) or not isinstance(r.get('uid'), str) or not isinstance(r.get('id'), str)
                or not isinstance(r.get('optiune'), str)):
            logger.warning('Sistem: %s, linia %d are alta forma; se ignora', FISIER_DECIZII, nr)
            continue
        randuri.append(r)
    return randuri


def _in_asteptare(r):
    """Decizia nu e nici consumata, nici anulata (inainte de v1.1: doar nu e consumata)."""
    return r.get('consumat') is None and r.get('anulat') is None


def _scrie_decizii(randuri):
    """Rescrie atomic decizii.jsonl, taind cele mai vechi randuri TERMINATE (consumate sau
    anulate) peste 500. Cele in asteptare nu se taie niciodata. Se cheama doar sub `_blocat()`."""
    exces = len(randuri) - MAX_RANDURI_DECIZII
    pastrate = []
    for r in randuri:
        if exces > 0 and not _in_asteptare(r):
            exces -= 1
            continue
        pastrate.append(r)
    continut = ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in pastrate)
    _scrie_atomic(FISIER_DECIZII, continut.encode('utf-8'))


def _citeste_amanari(acum):
    """{id item: pana} doar pentru amanarile din viitor. Fisierul lipsa sau stricat da {} (stricat:
    se logheaza); o intrare cu alta forma sau expirata se sare."""
    try:
        with open(_cale(FISIER_AMANARI), 'rb') as fh:
            brut = json.loads(fh.read().decode('utf-8'))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError, RecursionError):
        logger.warning('Sistem: %s nu se poate citi; se ignora', FISIER_AMANARI, exc_info=True)
        return {}
    if not isinstance(brut, dict):
        logger.warning('Sistem: %s are alta forma; se ignora', FISIER_AMANARI)
        return {}
    iesire = {}
    for id_, pana in brut.items():
        if not isinstance(pana, str) or not _RE_GENERAT.fullmatch(pana):
            continue
        moment = _data_ora(pana)
        if moment is not None and moment > acum:
            iesire[id_] = pana
    return iesire


# --------------------------------------------------------------------------- vederea combinata

def _cheie_item(it):
    restant, creat = it.get('restant_zile'), it.get('creat')
    return (GRUPURI.index(it['grup']),
            0 if restant is not None else 1, -(restant or 0),
            0 if creat else 1, creat or '',
            it['id'])


def _vechime_ore(generat, acum):
    return max(0.0, (acum - _data_ora(generat)).total_seconds() / 3600)


def _masina(sursa, snap, acum):
    ore = _vechime_ore(snap['generat'], acum)
    stare, detaliu = snap['sanatate']['stare'], snap['sanatate']['detaliu']
    if ore > VECHIME_WARN_ORE:
        if stare == 'ok':
            stare = 'warn'
        detaliu = 'last seen %d d' % (ore // 24) if ore > VECHIME_ZILE_ORE else 'last seen %d h' % int(ore)
    return {'sursa': sursa, 'masina': snap['masina'], 'ultima': snap['generat'],
            'vechime_ore': round(ore, 1), 'stare': stare, 'detaliu': detaliu, 'joburi': snap.get('joburi', [])}


def _masina_lipsa(sursa):
    """O sursa asteptata fara snapshot valid: `fail`, cu motivul in `detaliu`."""
    existent = os.path.exists(_cale(sursa + '.json'))
    return {'sursa': sursa, 'masina': '', 'ultima': None, 'vechime_ore': None, 'stare': 'fail',
            'detaliu': 'report unreadable' if existent else 'never reported', 'joburi': []}


def _masini(surse, acum):
    """Cate o intrare pe sursa, dupa numele sursei; sursele asteptate fara snapshot valid incluse."""
    masini = [_masina(sursa, snap, acum) for sursa, snap in surse]
    prezente = {sursa for sursa, _ in surse}
    masini.extend(_masina_lipsa(s) for s in SURSE_ASTEPTATE if s not in prezente)
    masini.sort(key=lambda m: m['sursa'])
    return masini


def _decizii_in_asteptare():
    """{id item: decizia in asteptare}. Cu doua pe acelasi id (fisier editat de mana) conteaza
    ultima din fisier."""
    return {r['id']: r for r in _citeste_decizii() if _in_asteptare(r)}


def _istoric(randuri):
    """Ultimele `MAX_ISTORIC` decizii terminate, cea mai recenta intai (dupa `consumat` sau
    `anulat`; la egal, cea scrisa mai tarziu in fisier). Randurile vechi n-au campurile noi:
    `titlu` lipsa -> id, `sursa` lipsa -> server, restul -> null."""
    terminate = [(str(r.get('consumat') or r.get('anulat')), ix, r)
                 for ix, r in enumerate(randuri) if not _in_asteptare(r)]
    terminate.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [{'uid': r['uid'], 'id': r['id'], 'titlu': r.get('titlu') or r['id'], 'optiune': r['optiune'],
             'label': r.get('label'), 'text': r.get('text'), 'ts': r.get('ts'),
             'sursa': r.get('sursa') or 'server', 'de_la': r.get('de_la'), 'rezultat': r.get('rezultat'),
             'stare': r.get('stare'), 'consumat': r.get('consumat'), 'anulat': r.get('anulat')}
            for _, _, r in terminate[:MAX_ISTORIC]]


def vedere(acum=None):
    acum = acum or _acum()
    surse = _surse()
    randuri = _citeste_decizii()
    in_asteptare = {r['id']: r for r in randuri if _in_asteptare(r)}
    amanari = _citeste_amanari(acum)
    # Cel mai nou snapshot intai: la acelasi id (sau titlu) ramane intrarea lui.
    pe_noutate = sorted(surse, key=lambda s: (_data_ora(s[1]['generat']), s[0]), reverse=True)
    itemi, vazute = [], set()
    for sursa, snap in pe_noutate:
        for it in snap['itemi']:
            if it['id'] in vazute:
                continue
            vazute.add(it['id'])
            d = in_asteptare.get(it['id'])
            decizie = None if d is None else {'uid': d['uid'], 'optiune': d['optiune'],
                                              'label': d.get('label'), 'ts': d.get('ts'),
                                              'preluat': d.get('preluat')}
            itemi.append(dict(it, sursa=sursa, decizie=decizie, amanat_pana=amanari.get(it['id'])))
    itemi.sort(key=_cheie_item)
    urmeaza, titluri = [], set()
    for _, snap in pe_noutate:
        for u in snap['urmeaza']:
            if u['titlu'] not in titluri:
                titluri.add(u['titlu'])
                urmeaza.append(dict(u))
    urmeaza.sort(key=lambda u: (u['data'], u['titlu']))
    automat = [dict(a, sursa=sursa) for sursa, snap in surse for a in snap['automat']]
    return {
        'generat': _z(acum),
        'numar': sum(1 for it in itemi if it['decizie'] is None),
        'masini': _masini(surse, acum),
        'itemi': itemi,
        'urmeaza': urmeaza,
        'automat': automat,
        'istoric': _istoric(randuri),
    }


# --------------------------------------------------------------------------- rutele

def _corp_json(maxim, gol_ok=False):
    """(corp, None) sau (None, raspuns de eroare). Citeste cel mult `maxim` octeti, si fara
    Content-Length (chunked). `gol_ok`: un corp absent da `{}` (rutele fara parametri in corp)."""
    if request.content_length is not None and request.content_length > maxim:
        return None, (jsonify({'error': 'corp prea mare (maxim %d KB)' % (maxim // 1024)}), 413)
    brut = request.stream.read(maxim + 1)
    if len(brut) > maxim:
        return None, (jsonify({'error': 'corp prea mare (maxim %d KB)' % (maxim // 1024)}), 413)
    if gol_ok and not brut.strip():
        return {}, None
    try:
        return json.loads(brut.decode('utf-8')), None
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None, (jsonify({'error': 'Body JSON invalid sau lipsa'}), 400)


@sistem_bp.route('/api/sistem/sursa/<sursa>', methods=['PUT'])
@login_required
def put_sursa(sursa):
    """Inlocuieste snapshot-ul unei surse. Sesiune sau Bearer `PIF_API_TOKEN`; tokenul de
    dispozitiv e refuzat (`DEVICE_TOKEN_DENIED`). Idempotent: aceeasi cerere de doua ori lasa
    acelasi fisier. Un snapshot cu `generat` mai vechi decat cel curent da 409 si nu se scrie.
    Raspuns: {ok, itemi}."""
    if not _RE_SURSA.fullmatch(sursa):
        return jsonify({'error': 'sursa: 2-20 de caractere din a-z 0-9 - (fara - la inceput)'}), 400
    if sursa in NUME_REZERVATE:                  # `amanari.json` nu e un snapshot: nu se acopera
        return jsonify({'error': 'sursa: numele %s e rezervat' % sursa}), 400
    corp, eroare = _corp_json(MAX_CORP)
    if eroare:
        return eroare
    try:
        snapshot = valideaza_snapshot(corp, sursa)
    except EroareCorp as e:
        logger.warning('Sistem: snapshot respins (%s): %s', sursa, e)
        return jsonify({'error': str(e)}), 400
    curent = _citeste_snapshot(sursa)
    if curent is not None and _data_ora(snapshot['generat']) < _data_ora(curent['generat']):
        return jsonify({'error': 'snapshot mai vechi decat cel curent (%s)' % curent['generat']}), 409
    try:
        _scrie_atomic(sursa + '.json', json.dumps(snapshot, ensure_ascii=False).encode('utf-8'))
    except OSError:
        logger.exception('Sistem: scrierea snapshot-ului %s a esuat pe disc', sursa)
        return jsonify({'error': 'Eroare pe disc la salvarea snapshot-ului.'}), 500
    return jsonify({'ok': True, 'itemi': len(snapshot['itemi'])})


@sistem_bp.route('/api/sistem', methods=['GET'])
@login_required
def get_sistem():
    """Vederea combinata a surselor, cu deciziile in asteptare, `istoric` (ultimele 20 terminate),
    `amanat_pana` pe item si masinile asteptate care n-au raportat. Sesiune sau oricare Bearer valid
    (Torqa pe telefon foloseste tokenul de dispozitiv). Fara surse: tot 200, cu cele trei masini
    asteptate in starea `fail`."""
    return jsonify(vedere())


def _de_la():
    if 'authenticated' in session:
        return 'sesiune'
    return 'dispozitiv' if getattr(g, 'api_token_scope', None) == 'device' else 'masina'


@sistem_bp.route('/api/sistem/decizie', methods=['POST'])
@login_required
def post_decizie():
    """Inregistreaza decizia lui Ion pentru un item. Sesiune, Bearer `PIF_API_TOKEN` sau tokenul
    de dispozitiv (butonul din Torqa). `id` trebuie sa existe acum in vedere, cu `optiune` printre
    optiunile puse de sursa; altfel 409. O decizie in asteptare (neconsumata si neanulata) pe
    acelasi `id` se inlocuieste (ultima castiga), deci o cerere retrimisa nu dubleaza nimic, doar
    schimba `uid`/`ts`; daca cea veche e deja preluata de consumator, 409 si nu se scrie nimic.
    Randul nou tine `titlu` si `sursa` ale itemului din vedere.
    Raspuns 201: {ok, uid}."""
    corp, eroare = _corp_json(16 * 1024)
    if eroare:
        return eroare
    try:
        _obiect(corp, 'corpul', CAMPURI_DECIZIE)
        id_ = _text(corp, 'id', 'corpul', 80, nevid=True)
        optiune = _text(corp, 'optiune', 'corpul', 20, nevid=True)
        if not _RE_OPTIUNE.fullmatch(optiune):
            raise EroareCorp('corpul.optiune: 1-20 de caractere din a-z 0-9 -')
        text = _text(corp, 'text', 'corpul', 500, optional=True) or ''
    except EroareCorp as e:
        logger.warning('Sistem: decizie respinsa: %s', e)
        return jsonify({'error': str(e)}), 400
    item = next((it for it in vedere()['itemi'] if it['id'] == id_), None)
    optiuni = {o['id']: o for o in item['optiuni']} if item else {}
    if optiune not in optiuni:
        return jsonify({'error': 'itemul sau opțiunea nu mai există'}), 409
    acum = _acum()
    rand = {'uid': secrets.token_hex(6), 'ts': _z(acum), 'id': id_, 'optiune': optiune,
            'label': optiuni[optiune]['label'], 'text': text, 'de_la': _de_la(),
            'consumat': None, 'rezultat': None,
            'titlu': item['titlu'], 'sursa': item['sursa'], 'preluat': None, 'anulat': None, 'stare': None}
    try:
        with _blocat():
            existente = _citeste_decizii()
            if any(r['id'] == id_ and _in_asteptare(r) and r.get('preluat') is not None for r in existente):
                return jsonify({'error': 'decizia anterioara se aplica deja'}), 409
            randuri = [r for r in existente if not (r['id'] == id_ and _in_asteptare(r))]
            randuri.append(rand)
            _scrie_decizii(randuri)
    except OSError:
        logger.exception('Sistem: scrierea deciziilor a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea deciziei.'}), 500
    return jsonify({'ok': True, 'uid': rand['uid']}), 201


@sistem_bp.route('/api/sistem/decizii', methods=['GET'])
@login_required
def get_decizii():
    """Deciziile in asteptare (neconsumate si neanulate), cele mai vechi intai, cu toate campurile
    randului (inclusiv `preluat`, `sursa`; randurile vechi nu le au). `?sursa=<s>` pastreaza doar
    randurile acelei surse (`sursa` lipsa = `server`); o sursa invalida da 400. Sesiune sau
    `PIF_API_TOKEN`; tokenul de dispozitiv e refuzat (`DEVICE_TOKEN_DENIED`): comenzile nu se
    citesc de pe telefon."""
    sursa = request.args.get('sursa')
    if sursa is not None and not _RE_SURSA.fullmatch(sursa):
        return jsonify({'error': 'sursa: 2-20 de caractere din a-z 0-9 - (fara - la inceput)'}), 400
    in_asteptare = [r for r in _citeste_decizii() if _in_asteptare(r)]
    if sursa is not None:
        in_asteptare = [r for r in in_asteptare if (r.get('sursa') or 'server') == sursa]
    in_asteptare.sort(key=lambda r: r.get('ts') or '')      # sortarea e stabila: la egal, ordinea din fisier
    return jsonify({'decizii': in_asteptare})


@sistem_bp.route('/api/sistem/decizii/<uid>/consumat', methods=['POST'])
@login_required
def post_consumat(uid):
    """Marcheaza decizia consumata, cu rezultatul si, optional, `stare` (ok|warn|fail). Aceeasi
    autentificare ca `GET /api/sistem/decizii`. 404 pentru un `uid` necunoscut, 409 pentru una deja
    consumata (o retrimitere nu rescrie rezultatul) sau anulata. Nu cere `preluat` inainte
    (consumatorul vechi nu-l trimite). Raspuns: {ok, uid}."""
    corp, eroare = _corp_json(16 * 1024)
    if eroare:
        return eroare
    try:
        _obiect(corp, 'corpul', CAMPURI_CONSUMAT)
        rezultat = _text(corp, 'rezultat', 'corpul', 300, nevid=True)
        if 'stare' in corp:
            _stare(corp, 'stare', 'corpul')
    except EroareCorp as e:
        logger.warning('Sistem: consum respins: %s', e)
        return jsonify({'error': str(e)}), 400
    if not _RE_UID.fullmatch(uid):
        return jsonify({'error': 'decizie necunoscuta'}), 404
    try:
        with _blocat():
            randuri = _citeste_decizii()
            rand = next((r for r in randuri if r['uid'] == uid), None)
            if rand is None:
                return jsonify({'error': 'decizie necunoscuta'}), 404
            if rand.get('anulat') is not None:
                return jsonify({'error': 'decizia a fost anulata'}), 409
            if rand.get('consumat') is not None:
                return jsonify({'error': 'decizia e deja consumata'}), 409
            rand['consumat'] = _z(_acum())
            rand['rezultat'] = rezultat
            rand['stare'] = corp.get('stare')
            _scrie_decizii(randuri)
    except OSError:
        logger.exception('Sistem: scrierea deciziilor a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea deciziei.'}), 500
    return jsonify({'ok': True, 'uid': uid})


def _corp_gol():
    """None daca corpul e absent sau `{}`; altfel raspunsul de eroare (400/413)."""
    corp, eroare = _corp_json(16 * 1024, gol_ok=True)
    if eroare:
        return eroare
    try:
        _obiect(corp, 'corpul', CAMPURI_GOL)
    except EroareCorp as e:
        logger.warning('Sistem: corp respins: %s', e)
        return jsonify({'error': str(e)}), 400
    return None


@sistem_bp.route('/api/sistem/decizii/<uid>/preluat', methods=['POST'])
@login_required
def post_preluat(uid):
    """Consumatorul anunta ca a luat decizia, INAINTE s-o aplice. Aceeasi autentificare ca
    `GET /api/sistem/decizii` (dispozitivul e refuzat de prefix). Corp gol sau `{}`. 404 uid
    necunoscut; 409 daca decizia e anulata sau consumata. Idempotent: deja preluata -> 200 cu
    momentul existent, fara rescriere (o reincercare a aceleiasi masini). Raspuns: {ok, uid, preluat}."""
    eroare = _corp_gol()
    if eroare:
        return eroare
    if not _RE_UID.fullmatch(uid):
        return jsonify({'error': 'decizie necunoscuta'}), 404
    try:
        with _blocat():
            randuri = _citeste_decizii()
            rand = next((r for r in randuri if r['uid'] == uid), None)
            if rand is None:
                return jsonify({'error': 'decizie necunoscuta'}), 404
            if rand.get('anulat') is not None:
                return jsonify({'error': 'decizia a fost anulata'}), 409
            if rand.get('consumat') is not None:
                return jsonify({'error': 'decizia e deja consumata'}), 409
            if rand.get('preluat') is None:
                rand['preluat'] = _z(_acum())
                _scrie_decizii(randuri)
            preluat = rand['preluat']
    except OSError:
        logger.exception('Sistem: scrierea deciziilor a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea deciziei.'}), 500
    return jsonify({'ok': True, 'uid': uid, 'preluat': preluat})


@sistem_bp.route('/api/sistem/decizie/<uid>/anulare', methods=['POST'])
@login_required
def post_anulare(uid):
    """Ion anuleaza o decizie cat n-a fost preluata. Sesiune, `PIF_API_TOKEN` sau tokenul de
    dispozitiv (prefixul `/api/sistem/decizii` nu prinde singularul `/api/sistem/decizie/`). Fara
    corp (sau `{}`). 404 uid necunoscut; 409 daca e preluata (se aplica deja) sau consumata. Deja
    anulata -> 200, fara rescriere (idempotent). Raspuns: {ok, uid}."""
    eroare = _corp_gol()
    if eroare:
        return eroare
    if not _RE_UID.fullmatch(uid):
        return jsonify({'error': 'decizie necunoscuta'}), 404
    try:
        with _blocat():
            randuri = _citeste_decizii()
            rand = next((r for r in randuri if r['uid'] == uid), None)
            if rand is None:
                return jsonify({'error': 'decizie necunoscuta'}), 404
            if rand.get('anulat') is None:
                if rand.get('consumat') is not None:
                    return jsonify({'error': 'decizia e deja consumata'}), 409
                if rand.get('preluat') is not None:
                    return jsonify({'error': 'se aplica deja'}), 409
                rand['anulat'] = _z(_acum())
                _scrie_decizii(randuri)
    except OSError:
        logger.exception('Sistem: scrierea deciziilor a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea deciziei.'}), 500
    return jsonify({'ok': True, 'uid': uid})


@sistem_bp.route('/api/sistem/amanare', methods=['POST'])
@login_required
def post_amanare():
    """Amana un item pana la `pana` (ISO Z, in viitor, cel mult 31 de zile) sau scoate amanarea
    (`pana: null`). Sesiune, `PIF_API_TOKEN` sau tokenul de dispozitiv. Cu `pana` nenul, itemul
    trebuie sa fie acum in vedere (409 altfel); maxim 200 de amanari (409 peste). `pana` in trecut sau
    peste 31 de zile: 400. Idempotent: aceeasi cerere de doua ori lasa acelasi fisier. Amanarile
    expirate se taie la fiecare scriere. Raspuns: {ok, id, pana}."""
    corp, eroare = _corp_json(16 * 1024)
    if eroare:
        return eroare
    acum = _acum()
    try:
        _obiect(corp, 'corpul', CAMPURI_AMANARE)
        id_ = _text(corp, 'id', 'corpul', 80, nevid=True)
        if 'pana' not in corp:
            raise EroareCorp('corpul.pana: lipseste')
        pana = corp['pana']
        if pana is not None:
            moment = _generat(pana, 'corpul.pana')
            if moment <= acum:
                raise EroareCorp('corpul.pana: trebuie sa fie in viitor')
            if moment > acum + timedelta(days=MAX_AMANARE_ZILE):
                raise EroareCorp('corpul.pana: cel mult %d de zile de acum' % MAX_AMANARE_ZILE)
    except EroareCorp as e:
        logger.warning('Sistem: amanare respinsa: %s', e)
        return jsonify({'error': str(e)}), 400
    if pana is not None and not any(it['id'] == id_ for it in vedere(acum)['itemi']):
        return jsonify({'error': 'itemul nu mai exista'}), 409
    try:
        with _blocat():
            vechi = _citeste_amanari(acum)                     # fara cele expirate
            noi = dict(vechi)
            if pana is None:
                noi.pop(id_, None)
            elif id_ in noi or len(noi) < MAX_AMANARI:
                noi[id_] = pana
            else:
                return jsonify({'error': 'prea multe amanari (maxim %d)' % MAX_AMANARI}), 409
            if noi != vechi or os.path.exists(_cale(FISIER_AMANARI)):
                _scrie_atomic(FISIER_AMANARI, json.dumps(noi, ensure_ascii=False).encode('utf-8'))
    except OSError:
        logger.exception('Sistem: scrierea amanarilor a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea amanarii.'}), 500
    return jsonify({'ok': True, 'id': id_, 'pana': pana})

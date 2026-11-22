# Asistentul din pagina System a Torqa Blueprint
# Contractul `/api/asistent` v1 (decizia 2026-11-22-asistent-in-torqa.md). pif-dashboard e doar
# DEPOZITUL si POSTA: tine registrul asistentului proactiv (tools/asistent/atentie.py din Knowledge),
# actiunile lui Ion pe itemi, firul de mesaje cu asistentul si tokenurile FCM, si trimite push-ul.
# Nu ruleaza niciun LLM si nu creeaza taskuri: mesajele lui Ion le preia asistentul de pe laptop.
#
# Trei parti, trei feluri de acces:
#   - asistentul (token de MASINA, sesiune): PUT registru, GET/POST actiuni, POST fir (cine=asistent),
#     GET fir/noi, POST fir/<id>/stare. Tokenul de DISPOZITIV primeste 403 pe ele.
#   - Torqa (sesiune sau token de dispozitiv): GET /api/asistent, POST actiune, POST fir (mesajul lui
#     Ion), push/token. Serviciul nativ Android foloseste acelasi token de dispozitiv.
#
# Fisiere, nu tabele (tiparul `blueprints/sistem.py`: fiecare rulare trimite starea completa, se reface
# singura; fara schema, fara migrare). Pe disc, sub `<uploads>/asistent/`:
#   registru.json    ultimul registru urcat de asistent, scris atomic
#   actiuni.jsonl    actiunile lui Ion (asteapta -> consumat), atomic, max 500 de randuri
#   fir.jsonl        mesajele firului, atomic, cu blocare, max 500
#   push.json        tokenurile FCM, atomic, drepturi 600
#   prezenta.json    ultima raportare a fiecarei masini (v1.1), atomic
#   asistent.lock    doar blocarea (fcntl): doi workeri nu rescriu deodata
#
# v1.1 (decizia 2026-11-22-asistent-in-torqa.md, sectiunea v1.1): `ref`, `tinta`, `alegere` pe mesajul lui Ion;
# `intrebare`/`asteapta` cu `optiuni`, `masina` si `ref` pe mesajul asistentului; raspunsul lui Ion la o intrebare
# (pus pe intrebare in ACEEASI scriere cu mesajul lui Ion); prezenta masinilor (`prezenta.json`, `masini` in GET).
#
# Validarea e STRICTA: camp necunoscut, lipsa sau tip gresit da 400 cu calea campului, iar starea
# veche ramane. Trimiterea FCM nu schimba niciodata statusul raspunsului: o eroare intra in `push.erori`.

import contextlib
import functools
import json
import logging
import os
import re
import secrets
import threading
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

try:
    import fcntl
except ImportError:                               # Windows
    fcntl = None
    import msvcrt

from flask import Blueprint, g, jsonify, request, session

from blueprints import fcm
from blueprints.sistem import EroareCorp, _corp_json as _corp_json_brut, _lista, _obiect, _text
from utils import login_required, UPLOAD_FOLDER

logger = logging.getLogger('pif_dashboard')

asistent_bp = Blueprint('asistent', __name__)

DIR_ASISTENT = os.path.join(UPLOAD_FOLDER, 'asistent')
F_REGISTRU = 'registru.json'
F_ACTIUNI = 'actiuni.jsonl'
F_FIR = 'fir.jsonl'
F_PUSH = 'push.json'
F_PREZENTA = 'prezenta.json'
F_BLOCARE = 'asistent.lock'

MAX_CORP_REGISTRU = 1024 * 1024
MAX_CORP = 32 * 1024
MAX_ITEMI = 300
MAX_SURSE = 30
MAX_PICATE = 100
MAX_RANDURI_ACTIUNI = 500
MAX_RANDURI_FIR = 500
MAX_TOKENURI = 20
FIR_IN_VEDERE = 100
MESAJE_PE_ORA = 30
MAX_ZILE = 31
MAX_IDLE_S = 10 ** 9                              # ~31 de ani: o garda de tip, nu o regula de produs
ONLINE_S = 180                                    # o masina e online daca a raportat in ultimele 180 s
ACTIV_IDLE_S = 900                                # activ = online, `activ: true` si ultima intrare acum cel mult 900 s
DATE_PUSH_OCTETI = 4000                           # `data` din mesajul FCM are 4096 de octeti pe tot; textul se taie sub asta

SURSE_ITEM = ('torqa', 'mail', 'sistem', 'server', 'netdata', 'vault', 'backlog', 'finante', 'ci', 'claude', 'pagina')
GRAVITATI = ('critic', 'urgent', 'azi', 'info')
STARI_ITEM = ('nou', 'vazut', 'amanat', 'gata', 'ignorat', 'la_claude')
STARI_ACTIVE = ('nou', 'vazut')
INCREDERI = ('proprie', 'straina')
ACTIUNI_ITEM = ('gata', 'amana', 'ignora', 'claude')
ACTIUNI_POST = ACTIUNI_ITEM + ('nu_util',)
DIN = ('pagina', 'notificare')
VIA = ('sesiune', 'dispozitiv', 'masina')
TIPURI_ASISTENT = ('brief', 'alerta', 'raspuns', 'lucreaza', 'rezultat', 'info', 'intrebare', 'asteapta')
TIPURI_CU_OPTIUNI = ('intrebare', 'asteapta')
MASINI = (('server', 'Server'), ('pc-job', 'PC job'), ('ionpc', 'IONPC'))   # ordinea din `masini`
IDS_MASINI = tuple(m for m, _ in MASINI)
TINTE = ('auto',) + IDS_MASINI
TIPURI_REF = ('item', 'decizie', 'verificare', 'job', 'istoric')
MODURI_REF = ('discuta', 'raspuns')
BUTOANE = ('claude', 'gata', 'amana', 'ignora', 'deschide')
PRIORITATI = ('urgent', 'normal', 'silent')
SURSE_MESAJ = ('scris', 'dictat')
STARI_MESAJ = ('preluat', 'gata', 'eroare')
TRANZITII = {'nou': ('preluat', 'gata', 'eroare'), 'preluat': ('gata', 'eroare')}

_RE_UID = re.compile(r'[0-9a-f]{12}')
_RE_MSG = re.compile(r'm_[0-9a-f]{6,16}')
_RE_SURSA_REG = re.compile(r'[a-z0-9][a-z0-9_-]{0,39}')
_RE_APLICATIE = re.compile(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+')
_RE_DATA = re.compile(r'(\d{4})-(\d{2})-(\d{2})')
_RE_MOMENT = re.compile(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})')

CAMPURI_REGISTRU = frozenset(('v', 'generat', 'items', 'surse', 'veghe'))
CAMPURI_ITEM = frozenset(('id', 'sursa', 'titlu', 'de_ce', 'gravitate', 'termen', 'prima_data', 'stare',
                          'amanat_pana', 'incredere', 'actiuni', 'link'))
CAMPURI_SURSA = frozenset(('ok', 'eroare'))
CAMPURI_VEGHE = frozenset(('generat', 'total', 'ok', 'picate', 'categorii'))
# Tipurile de verificari din veghe.py; `categorii` e optional (pagina Server arata un rand pe categorie).
CATEGORII_VEGHE = frozenset(('http', 'timer', 'docker', 'putere', 'disc', 'netdata'))
CAMPURI_CATEGORIE = frozenset(('total', 'ok'))
CAMPURI_PICAT = frozenset(('nume', 'detaliu'))
CAMPURI_ACTIUNE = frozenset(('item_id', 'actiune', 'zile', 'din'))
CAMPURI_CONSUMAT = frozenset(('rezultat', 'mesaj'))
CAMPURI_FIR_ASISTENT = frozenset(('cine', 'tip', 'text', 'titlu', 'item_id', 'task_id', 'link', 'butoane',
                                  'raspuns_la', 'push', 'optiuni', 'masina', 'ref'))
CAMPURI_FIR_ION = frozenset(('cine', 'text', 'sursa', 'raspuns_la', 'ref', 'tinta', 'alegere'))
CAMPURI_REF = frozenset(('tip', 'id', 'titlu', 'sursa', 'masina', 'mod'))
CAMPURI_OPTIUNE = frozenset(('id', 'eticheta'))
CAMPURI_PREZENTA = frozenset(('activ', 'idle_s', 'versiune'))
CAMPURI_PUSH = frozenset(('prioritate',))
CAMPURI_STARE = frozenset(('stare', 'task_id', 'mesaj'))
CAMPURI_TOKEN = frozenset(('token', 'platforma', 'aplicatie', 'versiune'))
CAMPURI_TOKEN_STERS = frozenset(('token',))


# --------------------------------------------------------------------------- corpul cererii

def _fara_surogate(v, cale):
    """Un surogat izolat (`\\ud83d`) trece de `json.loads`, dar nu se poate scrie ca UTF-8: ar da 500 la
    scriere. Se respinge aici, cu calea campului (si in chei)."""
    if isinstance(v, str):
        if any('\ud800' <= c <= '\udfff' for c in v):
            raise EroareCorp('%s: caractere Unicode invalide (surogat izolat)' % cale)
    elif isinstance(v, dict):
        for k, x in v.items():
            _fara_surogate(k, '%s.%s' % (cale, k.encode('ascii', 'backslashreplace').decode()))
            _fara_surogate(x, '%s.%s' % (cale, k) if cale else k)
    elif isinstance(v, list):
        for ix, x in enumerate(v):
            _fara_surogate(x, '%s[%d]' % (cale, ix))


def _corp_json(maxim, gol_ok=False):
    """Ca `sistem._corp_json`, plus 400 cu calea campului la surogate izolate."""
    corp, eroare = _corp_json_brut(maxim, gol_ok=gol_ok)
    if eroare:
        return corp, eroare
    try:
        _fara_surogate(corp, 'corpul')
    except EroareCorp as e:
        return None, _eroare(400, str(e))
    except RecursionError:
        return None, _eroare(400, 'Body JSON invalid sau lipsa')
    return corp, None


# --------------------------------------------------------------------------- erori si acces

def _eroare(status, mesaj, **extra):
    """Forma de eroare a depozitului: `{'error': text}`. Un rand de log pe cerere esuata, cu ruta si
    statusul (corpul cererii nu se logheaza)."""
    logger.warning('Asistent: %s %s -> %d: %s', request.method, request.path, status, mesaj)
    raspuns = jsonify({'error': mesaj})
    raspuns.status_code = status
    for k, v in extra.items():
        raspuns.headers[k] = str(v)
    return raspuns


def _este_dispozitiv():
    return 'authenticated' not in session and getattr(g, 'api_token_scope', None) == 'device'


def _doar_masina(f):
    """Rutele asistentului: tokenul de dispozitiv primeste 403 (sesiunea si tokenul de masina trec).
    Se pune SUB `login_required`, ca o cerere fara autentificare sa ramana 401."""
    @functools.wraps(f)
    def decorat(*args, **kwargs):
        if _este_dispozitiv():
            return _eroare(403, 'tokenul de dispozitiv nu are voie pe aceasta ruta')
        return f(*args, **kwargs)
    return decorat


# --------------------------------------------------------------------------- discul

def _cale(nume):
    return os.path.join(DIR_ASISTENT, nume)


def _acum():
    return datetime.now(timezone.utc)


def _z(moment):
    return moment.strftime('%Y-%m-%dT%H:%M:%SZ')


def _scrie_atomic(nume, octeti):
    """Fisier alaturat (drepturi 600), fsync, apoi `os.replace`: un cititor vede ori fisierul vechi,
    ori pe cel nou."""
    os.makedirs(DIR_ASISTENT, exist_ok=True)
    cale = _cale(nume)
    tmp = '%s.%s.tmp' % (cale, secrets.token_hex(3))
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as fh:
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


def _json_bytes(v):
    return json.dumps(v, ensure_ascii=False).encode('utf-8')


def _jsonl_bytes(randuri):
    return ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in randuri).encode('utf-8')


_FIR = threading.Lock()


@contextlib.contextmanager
def _blocat():
    """Un singur scriitor pe fisierele asistentului: firul curent (threading) si celelalte procese
    (gunicorn are 2 workeri) printr-un fisier de blocare. Citirea nu se blocheaza. Reteaua nu se
    atinge niciodata cu blocarea luata."""
    os.makedirs(DIR_ASISTENT, exist_ok=True)
    with _FIR:
        with open(_cale(F_BLOCARE), 'a+b') as fh:
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


def _salveaza_corupte(nume, bucati):
    """Ce nu se poate citi dintr-un fisier de date NU se pierde la rescriere: se adauga (o singura data
    fiecare bucata) in `<nume>.corupt`, cu drepturi 600, si se logheaza. OSError se ridica: fara copie, fara scriere."""
    if not bucati:
        return
    cale = _cale(nume + '.corupt')
    try:
        with open(cale, 'rb') as fh:
            deja = set(fh.read().split(b'\n'))
    except FileNotFoundError:
        deja = set()
    noi = [b for b in bucati if b not in deja]
    if noi:
        os.makedirs(DIR_ASISTENT, exist_ok=True)
        fd = os.open(cale, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'ab') as fh:
            for b in noi:
                fh.write(b.replace(b'\n', b' ') + b'\n')
        logger.warning('Asistent: %d bucati ilizibile din %s au fost puse in %s.corupt', len(noi), nume, nume)


def _citeste_jsonl(nume, cheie_text, strict=False):
    """Randurile unui .jsonl: obiecte cu `cheie_text` string. Liniile se despart DOAR la `\\n` (`splitlines`
    ar rupe un rand care contine U+2028 sau U+0085, pe care `json.dumps` nu le scapa).
    `strict=True` (citirea dinaintea unei scrieri, sub blocare): o eroare de citire (alta decat fisier lipsa)
    se ridica, ca sa nu se rescrie fisierul pornind de la nimic, iar liniile stricate merg in `<nume>.corupt`.
    `strict=False` (doar citire): eroarea se logheaza si dau []; liniile stricate se sar."""
    try:
        with open(_cale(nume), 'rb') as fh:
            brut = fh.read()
    except FileNotFoundError:
        return []
    except OSError:
        if strict:
            raise
        logger.warning('Asistent: %s nu se poate citi', nume, exc_info=True)
        return []
    randuri, rele = [], []
    for nr, linie in enumerate(brut.split(b'\n'), 1):
        if not linie.strip():
            continue
        try:
            r = json.loads(linie.decode('utf-8'))
        except (ValueError, RecursionError):                 # JSONDecodeError, UnicodeDecodeError
            r = None
        if not isinstance(r, dict) or not isinstance(r.get(cheie_text), str):
            logger.warning('Asistent: %s, linia %d are alta forma; se ignora', nume, nr)
            rele.append(linie)
            continue
        randuri.append(r)
    if strict:
        _salveaza_corupte(nume, rele)
    return randuri


# --------------------------------------------------------------------------- validarea registrului

def _moment(v, cale):
    """ISO 8601 cu secunde si fus (`Z` sau +HH:MM) -> datetime cu fus. Scris de mana (ca in
    `outlook._data_ora`): `fromisoformat` difera de la o versiune de Python la alta."""
    m = _RE_MOMENT.fullmatch(v) if isinstance(v, str) else None
    if m:
        an, luna, zi, ora, minut, sec = (int(x) for x in m.groups()[:6])
        fus = m.group(7)
        try:
            tz = timezone.utc if fus == 'Z' else timezone(
                (1 if fus[0] == '+' else -1) * timedelta(hours=int(fus[1:3]), minutes=int(fus[4:6])))
            return datetime(an, luna, zi, ora, minut, sec, tzinfo=tz)
        except ValueError:
            pass
    raise EroareCorp('%s: data si ora ISO cu fus, ex. 2026-11-22T07:35:00Z' % cale)


def _moment_sau_none(v):
    try:
        return _moment(v, 'ts')
    except EroareCorp:
        return None


def _nul_moment(obj, camp, cale):
    """Moment ISO, sau None cand campul lipseste ori e null."""
    if obj.get(camp) is None:
        return None
    return _moment(obj[camp], '%s.%s' % (cale, camp))


def _nul_text(obj, camp, cale, maxim):
    if obj.get(camp) is None:
        return None
    return _text(obj, camp, cale, maxim, nevid=True)


def _enum(obj, camp, cale, valori):
    v = obj.get(camp)
    if not isinstance(v, str) or v not in valori:
        raise EroareCorp('%s.%s: una din %s' % (cale, camp, '|'.join(valori)))
    return v


def _intreg(obj, camp, cale, minim, maxim):
    v = obj.get(camp)
    if isinstance(v, bool) or not isinstance(v, int) or not minim <= v <= maxim:
        raise EroareCorp('%s.%s: intreg intre %d si %d' % (cale, camp, minim, maxim))
    return v


def _fara_control(v, cale):
    if any(ord(c) < 32 or ord(c) == 127 for c in v):
        raise EroareCorp('%s: fara caractere de control' % cale)


def _ref(v, cale):
    """Randul despre care e mesajul (tras in chat sau „Discuss”): {tip, id, titlu, sursa?, masina?, mod?}.
    `mod` lipsa = `discuta`; `raspuns` (raspunsul liber la o decizie) doar la `tip: decizie`. Se stocheaza cu toate
    cheile (sursa si masina pot fi null). Campurile optionale lipsesc, nu sunt null."""
    _obiect(v, cale, CAMPURI_REF)
    tip = _enum(v, 'tip', cale, TIPURI_REF)
    id_ = _text(v, 'id', cale, 160, nevid=True)
    _fara_control(id_, '%s.id' % cale)
    titlu = _text(v, 'titlu', cale, 140, nevid=True)
    sursa = _text(v, 'sursa', cale, 40, nevid=True, optional=True)
    masina = _enum(v, 'masina', cale, IDS_MASINI) if 'masina' in v else None
    mod = _enum(v, 'mod', cale, MODURI_REF) if 'mod' in v else 'discuta'
    if mod == 'raspuns' and tip != 'decizie':
        raise EroareCorp('%s.mod: raspuns doar la tip decizie' % cale)
    return {'tip': tip, 'id': id_, 'titlu': titlu, 'sursa': sursa, 'masina': masina, 'mod': mod}


def _optiuni(corp, cale):
    """1-4 optiuni {id <=40, eticheta <=60}, cu id-uri unice (`alegere` se potriveste exact pe id)."""
    lista = _lista(corp, 'optiuni', cale, 4)
    if not lista:
        raise EroareCorp('%s.optiuni: minimum 1 optiune' % cale)
    optiuni, vazute = [], set()
    for ix, o in enumerate(lista):
        c = '%s.optiuni[%d]' % (cale, ix)
        _obiect(o, c, CAMPURI_OPTIUNE)
        id_ = _text(o, 'id', c, 40, nevid=True)
        _fara_control(id_, '%s.id' % c)
        eticheta = _text(o, 'eticheta', c, 60, nevid=True)
        _fara_control(eticheta, '%s.eticheta' % c)
        if id_ in vazute:
            raise EroareCorp('%s.id: duplicat' % c)
        vazute.add(id_)
        optiuni.append({'id': id_, 'eticheta': eticheta})
    return optiuni


# Caractere care nu au ce cauta intr-un link: de control (C0, DEL, C1), separatoare de linie si de paragraf,
# marcajele de directie (bidi) cu care un nume de fisier sau un host se poate rasturna la afisare.
_LINK_INTERZISE = frozenset(chr(c) for c in (*range(0, 32), *range(127, 160), 0x061C, 0x200E, 0x200F,
                                             *range(0x2028, 0x202F), *range(0x2066, 0x206A), 0xFEFF))
_RE_PROCENT_PERICULOS = re.compile(r'%(2e|2f|5c|00)', re.IGNORECASE)


def _link(obj, camp, cale):
    """Cale relativa din vault sau `https://host/...`. None cand lipseste.
    Relativa: fara `/` sau `\\` la inceput, fara `:` (nicio schema), fara segment `..`, fara `%2e`/`%2f`/`%5c`/`%00`
    (un `%2e%2e` decodat mai tarziu de un client ar iesi din vault). https: cu host, fara user:parola@,
    fara spatii. Oricare: fara caractere de control sau de directie."""
    if obj.get(camp) is None:
        return None
    v = _text(obj, camp, cale, 500, nevid=True)
    c = '%s.%s' % (cale, camp)
    if any(ch in _LINK_INTERZISE for ch in v):
        raise EroareCorp('%s: fara caractere de control sau de directie' % c)
    if v.startswith('https://'):
        try:
            parti = urllib.parse.urlsplit(v)
            host = parti.hostname
            parti.port                                         # ridica ValueError la un port invalid
        except ValueError:
            raise EroareCorp('%s: https:// cu host valid' % c)
        if not host or '@' in parti.netloc or any(ch.isspace() or ch == '\\' for ch in v):
            raise EroareCorp('%s: https:// cu host, fara user:parola@, fara spatii' % c)
        return v
    if (v.startswith(('/', '\\')) or ':' in v or '\\' in v or '..' in v.split('/')
            or _RE_PROCENT_PERICULOS.search(v)):
        raise EroareCorp('%s: cale relativa din vault sau https://' % c)
    return v


def _item(it, cale, ids):
    _obiect(it, cale, CAMPURI_ITEM)
    id_ = _text(it, 'id', cale, 120, nevid=True)
    _fara_control(id_, '%s.id' % cale)
    if id_ in ids:
        raise EroareCorp('%s.id: duplicat in registru' % cale)
    ids.add(id_)
    _enum(it, 'sursa', cale, SURSE_ITEM)
    _text(it, 'titlu', cale, 140, nevid=True)
    _text(it, 'de_ce', cale, 200)
    _enum(it, 'gravitate', cale, GRAVITATI)
    termen = it.get('termen')
    if termen is not None:
        m = _RE_DATA.fullmatch(termen) if isinstance(termen, str) else None
        try:
            if not m:
                raise ValueError
            datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            raise EroareCorp('%s.termen: AAAA-LL-ZZ sau null' % cale)
    _nul_moment(it, 'prima_data', cale)
    stare = _enum(it, 'stare', cale, STARI_ITEM)
    pana = _nul_moment(it, 'amanat_pana', cale)
    if stare == 'amanat' and pana is None:
        raise EroareCorp('%s.amanat_pana: obligatoriu cand stare e amanat' % cale)
    _enum(it, 'incredere', cale, INCREDERI)
    actiuni = _lista(it, 'actiuni', cale, len(ACTIUNI_ITEM))
    for ix, a in enumerate(actiuni):
        if not isinstance(a, str) or a not in ACTIUNI_ITEM:
            raise EroareCorp('%s.actiuni[%d]: una din %s' % (cale, ix, '|'.join(ACTIUNI_ITEM)))
    if len(set(actiuni)) != len(actiuni):
        raise EroareCorp('%s.actiuni: valori duplicate' % cale)
    link = _link(it, 'link', cale)
    return {'id': id_, 'sursa': it['sursa'], 'titlu': it['titlu'], 'de_ce': it['de_ce'],
            'gravitate': it['gravitate'], 'termen': termen, 'prima_data': it.get('prima_data'),
            'stare': stare, 'amanat_pana': it.get('amanat_pana'), 'incredere': it['incredere'],
            'actiuni': list(actiuni), 'link': link}


def _veghe(v, cale):
    _obiect(v, cale, CAMPURI_VEGHE)
    _moment(v.get('generat'), '%s.generat' % cale)
    total = _intreg(v, 'total', cale, 0, 10000)
    ok = _intreg(v, 'ok', cale, 0, 10000)
    if ok > total:
        raise EroareCorp('%s.ok: nu poate depasi total' % cale)
    picate = []
    for ix, p in enumerate(_lista(v, 'picate', cale, MAX_PICATE)):
        c = '%s.picate[%d]' % (cale, ix)
        _obiect(p, c, CAMPURI_PICAT)
        picate.append({'nume': _text(p, 'nume', c, 120, nevid=True), 'detaliu': _text(p, 'detaliu', c, 200)})
    rez = {'generat': v['generat'], 'total': total, 'ok': ok, 'picate': picate}
    if 'categorii' in v:
        cc = '%s.categorii' % cale
        _obiect(v['categorii'], cc, CATEGORII_VEGHE)
        categorii = {}
        for tip in sorted(v['categorii']):
            c = '%s.%s' % (cc, tip)
            _obiect(v['categorii'][tip], c, CAMPURI_CATEGORIE)
            t, k = _intreg(v['categorii'][tip], 'total', c, 0, 10000), _intreg(v['categorii'][tip], 'ok', c, 0, 10000)
            if k > t:
                raise EroareCorp('%s.ok: nu poate depasi total' % c)
            categorii[tip] = {'total': t, 'ok': k}
        rez['categorii'] = categorii
    return rez


def valideaza_registru(corp):
    """Corpul JSON -> registrul de scris (exact campurile din contract), sau EroareCorp cu calea
    campului. Nu scrie nimic."""
    _obiect(corp, 'corpul', CAMPURI_REGISTRU)
    if corp.get('v') != 1 or isinstance(corp.get('v'), bool):
        raise EroareCorp('v: trebuie sa fie 1')
    _moment(corp.get('generat'), 'generat')
    ids, items = set(), []
    for ix, it in enumerate(_lista(corp, 'items', 'corpul', MAX_ITEMI)):
        items.append(_item(it, 'items[%d]' % ix, ids))
    surse = corp.get('surse')
    if not isinstance(surse, dict):
        raise EroareCorp('surse: trebuie sa fie obiect')
    if len(surse) > MAX_SURSE:
        raise EroareCorp('surse: maximum %d de surse' % MAX_SURSE)
    surse_noi = {}
    for nume, s in surse.items():
        cale = 'surse.%s' % nume
        if not _RE_SURSA_REG.fullmatch(nume):
            raise EroareCorp('%s: nume de sursa 1-40 de caractere din a-z 0-9 _ -' % cale)
        _obiect(s, cale, CAMPURI_SURSA)
        if not isinstance(s.get('ok'), bool):
            raise EroareCorp('%s.ok: trebuie sa fie true sau false' % cale)
        surse_noi[nume] = {'ok': s['ok']}
        if 'eroare' in s:
            surse_noi[nume]['eroare'] = _text(s, 'eroare', cale, 200)
    registru = {'v': 1, 'generat': corp['generat'], 'items': items, 'surse': surse_noi, 'veghe': None}
    if corp.get('veghe') is not None:
        registru['veghe'] = _veghe(corp['veghe'], 'veghe')
    return registru


def _citeste_registru(strict=False):
    """Registrul stocat, sau None cand lipseste ori nu mai respecta contractul (se logheaza; un registru
    stricat e inlocuit la urmatorul PUT, fiindca asistentul retrimite starea completa). `strict`: o eroare
    de citire a fisierului (permisiuni, disc) se ridica in loc sa treaca drept „lipsa”."""
    try:
        with open(_cale(F_REGISTRU), 'rb') as fh:
            return valideaza_registru(json.loads(fh.read().decode('utf-8')))
    except FileNotFoundError:
        return None
    except OSError as e:
        if strict:
            raise
        logger.warning('Asistent: %s nu se poate citi (%s); se ignora', F_REGISTRU, e)
        return None
    except (ValueError, RecursionError) as e:            # EroareCorp, JSONDecodeError, UnicodeDecodeError
        logger.warning('Asistent: %s nu se poate citi (%s); se ignora', F_REGISTRU, e)
        return None


def _activ(it, acum):
    """Itemul se arata: stare nou|vazut, sau amanat cu `amanat_pana` trecut. Gata, ignorat si
    la_claude raman ascunse pana cand asistentul le schimba."""
    if it['stare'] in STARI_ACTIVE:
        return True
    return it['stare'] == 'amanat' and it['amanat_pana'] is not None and _moment(it['amanat_pana'], 'x') <= acum


# --------------------------------------------------------------------------- actiuni

def _scrie_actiuni(randuri):
    """Rescrie atomic actiuni.jsonl, taind cele mai vechi randuri CONSUMATE peste 500; cele in
    asteptare nu se taie niciodata (sunt cel mult cate un item din registru, deci cel mult 300)."""
    exces = len(randuri) - MAX_RANDURI_ACTIUNI
    pastrate = []
    for r in randuri:
        if exces > 0 and r.get('stare') == 'consumat':
            exces -= 1
            continue
        pastrate.append(r)
    _scrie_atomic(F_ACTIUNI, _jsonl_bytes(pastrate))


def _citeste_actiuni(strict=False):
    return _citeste_jsonl(F_ACTIUNI, 'uid', strict)


def _in_asteptare(r):
    return r.get('stare') == 'asteapta'


# --------------------------------------------------------------------------- fir

def _citeste_fir(strict=False):
    return _citeste_jsonl(F_FIR, 'id', strict)


def _scrie_fir(randuri):
    """Rescrie atomic fir.jsonl, max 500: intai cad cele mai vechi mesaje TERMINATE (ale asistentului
    si ale lui Ion deja gata/eroare), apoi, daca e nevoie, cele mai vechi oricare ar fi (doar cu 500 de
    mesaje ale lui Ion neprocesate, adica un asistent mort de zeci de ore)."""
    exces = len(randuri) - MAX_RANDURI_FIR
    if exces > 0:
        ultimul = len(randuri) - 1                             # mesajul abia adaugat nu cade niciodata
        pastrate = []
        for ix, r in enumerate(randuri):
            if exces > 0 and ix < ultimul and r.get('stare') not in ('nou', 'preluat'):
                exces -= 1
                continue
            pastrate.append(r)
        if exces > 0:
            logger.warning('Asistent: firul are %d mesaje neprocesate; cad cele mai vechi', exces + MAX_RANDURI_FIR)
            pastrate = pastrate[exces:]
        randuri = pastrate
    _scrie_atomic(F_FIR, _jsonl_bytes(randuri))


def _id_mesaj(existente):
    ids = {r['id'] for r in existente}
    while True:
        id_ = 'm_' + secrets.token_hex(3)
        if id_ not in ids:
            return id_


def _mesaj(r):
    """Randul din fisier -> forma din contract (campurile lipsa devin null)."""
    return {'id': r['id'], 'ts': r.get('ts'), 'cine': r.get('cine'), 'tip': r.get('tip'),
            'titlu': r.get('titlu'), 'text': r.get('text', ''), 'sursa': r.get('sursa'),
            'item_id': r.get('item_id'), 'task_id': r.get('task_id'), 'link': r.get('link'),
            'butoane': r.get('butoane') if isinstance(r.get('butoane'), list) else [],
            'raspuns_la': r.get('raspuns_la'), 'stare': r.get('stare'),
            'stare_detaliu': r.get('stare_detaliu'), 'via': r.get('via'),
            'ref': r.get('ref') if isinstance(r.get('ref'), dict) else None,
            'tinta': r.get('tinta') or ('auto' if r.get('cine') == 'ion' else None),
            'alegere': r.get('alegere'),
            'optiuni': r.get('optiuni') if isinstance(r.get('optiuni'), list) else [],
            'masina': r.get('masina'),
            'raspuns': r.get('raspuns') if isinstance(r.get('raspuns'), dict) else None}


# --------------------------------------------------------------------------- prezenta masinilor

def _citeste_prezenta(strict=False):
    """{id_masina: {ultima, activ, idle_s, versiune}} din `prezenta.json`. Lipsa sau continut care nu se
    poate citi = nicio masina n-a raportat (fiecare retrimite la un minut, deci nu are rost o copie `.corupt`).
    `strict` (sub blocare): o eroare de citire a fisierului (permisiuni, disc) se ridica, ca sa nu se rescrie
    fisierul cu o singura masina."""
    try:
        with open(_cale(F_PREZENTA), 'rb') as fh:
            octeti = fh.read()
    except FileNotFoundError:
        return {}
    except OSError:
        if strict:
            raise
        logger.warning('Asistent: %s nu se poate citi', F_PREZENTA, exc_info=True)
        return {}
    try:
        masini = json.loads(octeti.decode('utf-8')).get('masini')
        if not isinstance(masini, dict):
            raise ValueError('forma neasteptata')
    except (ValueError, AttributeError, RecursionError):
        logger.warning('Asistent: %s nu se poate citi; se ignora', F_PREZENTA)
        return {}
    return {k: v for k, v in masini.items() if k in IDS_MASINI and isinstance(v, dict)}


def _masini(acum):
    """Lista `masini` din GET, mereu in ordinea server, pc-job, ionpc. online = ultima raportare in ultimele
    ONLINE_S secunde; activ = online, `activ: true` si `idle_s` <= ACTIV_IDLE_S; altfel offline. O masina care n-a
    raportat niciodata e offline cu `ultima: null`. `idle_min` (minute intregi, rotunjite in jos) doar cand e online:
    la o masina offline valoarea raportata e veche, deci null."""
    prezenta = _citeste_prezenta()
    iesire = []
    for id_, nume in MASINI:
        r = prezenta.get(id_) or {}
        moment = _moment_sau_none(r.get('ultima'))
        stare, ultima, idle_min = 'offline', None, None
        if moment is not None:
            ultima = r['ultima']
            if (acum - moment).total_seconds() <= ONLINE_S:
                idle_s = r.get('idle_s')
                idle_ok = isinstance(idle_s, int) and not isinstance(idle_s, bool) and idle_s >= 0
                stare = 'activ' if r.get('activ') is True and idle_ok and idle_s <= ACTIV_IDLE_S else 'online'
                idle_min = idle_s // 60 if idle_ok else None
        iesire.append({'id': id_, 'nume': nume, 'stare': stare, 'ultima': ultima, 'idle_min': idle_min})
    return iesire


# --------------------------------------------------------------------------- push

def _citeste_tokenuri(strict=False):
    """Lista de tokenuri stocata ([{token, platforma, aplicatie, versiune, inregistrat, ultima_vedere}]).
    `strict` (citirea dinaintea unei scrieri, sub blocare): eroarea de citire se ridica (nu se rescrie de la
    zero), iar continutul care nu se poate citi merge in `push.json.corupt`."""
    try:
        with open(_cale(F_PUSH), 'rb') as fh:
            octeti = fh.read()
    except FileNotFoundError:
        return []
    except OSError:
        if strict:
            raise
        logger.warning('Asistent: %s nu se poate citi; se ignora', F_PUSH)
        return []
    try:
        brut = json.loads(octeti.decode('utf-8'))
        lista = brut.get('tokeni') if isinstance(brut, dict) else None
        if not isinstance(lista, list):
            raise ValueError('forma neasteptata')
    except (ValueError, RecursionError):
        logger.warning('Asistent: %s nu se poate citi; se ignora', F_PUSH)
        if strict:
            _salveaza_corupte(F_PUSH, [octeti])
        return []
    bune = [t for t in lista if isinstance(t, dict) and isinstance(t.get('token'), str) and t['token']]
    if strict and len(bune) != len(lista):
        _salveaza_corupte(F_PUSH, [json.dumps(t, ensure_ascii=True).encode('ascii') for t in lista if t not in bune])
    return bune


def _scrie_tokenuri(tokenuri):
    _scrie_atomic(F_PUSH, _json_bytes({'tokeni': tokenuri}))


def _octeti_date(date):
    return len(json.dumps(date, ensure_ascii=False).encode('utf-8'))


def _date_push(mesaj, prioritate):
    """Mesajul FCM DOAR de date: toate valorile string. `data` are 4096 de octeti pe tot (chei si valori):
    `text` se taie la cel mai lung prefix (pe caractere, deci niciun caracter UTF-8 rupt) cu care `data`,
    serializat JSON, ramane sub DATE_PUSH_OCTETI; mesajul intreg ramane in fir."""
    text = mesaj.get('text') or ''
    date = {'v': '1', 'tip': mesaj.get('tip') or 'info', 'msg_id': mesaj['id'],
            'titlu': mesaj.get('titlu') or '', 'text': text, 'item_id': mesaj.get('item_id') or '',
            'butoane': ','.join(mesaj.get('butoane') or []), 'prioritate': prioritate,
            'deschide': '/system?tab=asistent&msg=%s' % mesaj['id']}
    if _octeti_date(date) > DATE_PUSH_OCTETI:
        jos, sus = 0, len(text)                              # cel mai lung prefix care incape (cautare binara)
        while jos < sus:
            mijloc = (jos + sus + 1) // 2
            if _octeti_date(dict(date, text=text[:mijloc].rstrip() + '…')) <= DATE_PUSH_OCTETI:
                jos = mijloc
            else:
                sus = mijloc - 1
        date['text'] = text[:jos].rstrip() + '…'
    return date


def _trimite_push(mesaj, prioritate):
    """Trimite mesajul la toate dispozitivele; intoarce blocul `push` din raspuns. Nu ridica: orice
    eroare intra in `erori`, iar statusul raspunsului ramane 201."""
    rezultat = {'incercat': False, 'trimise': 0, 'erori': [], 'motiv': None}
    try:
        if not fcm.configurat():
            rezultat['motiv'] = 'fcm_neconfigurat'
            return rezultat
        tokeni = [t['token'] for t in _citeste_tokenuri()]
        if not tokeni:
            rezultat['motiv'] = 'fara_tokenuri'
            return rezultat
        rezultat['incercat'] = True
        iesire = fcm.trimite_date(tokeni, _date_push(mesaj, prioritate),
                                  'HIGH' if prioritate == 'urgent' else 'NORMAL')
        rezultat['trimise'] = iesire['trimise']
        rezultat['erori'] = iesire['erori']
        if iesire['nregistrate']:
            scoase = set(iesire['nregistrate'])
            with _blocat():
                _scrie_tokenuri([t for t in _citeste_tokenuri(True) if t['token'] not in scoase])
    except Exception:                                          # niciodata 5xx din cauza push-ului
        logger.exception('Asistent: trimiterea push a esuat neasteptat')
        rezultat['erori'].append('eroare interna la trimitere')
    if rezultat['erori']:
        logger.warning('Asistent: push %s: %d trimise, %d erori', mesaj['id'], rezultat['trimise'], len(rezultat['erori']))
    return rezultat


# --------------------------------------------------------------------------- rute: asistent -> backend

@asistent_bp.route('/api/asistent/registru', methods=['PUT'])
@login_required
@_doar_masina
def put_registru():
    """Inlocuieste registrul. Token de masina sau sesiune; dispozitivul primeste 403. Corp invalid: 400
    cu calea campului, registrul vechi ramane. `generat` mai vechi decat cel stocat: 409. Idempotent:
    aceeasi cerere de doua ori lasa acelasi fisier. Raspuns: {ok, items}."""
    corp, eroare = _corp_json(MAX_CORP_REGISTRU)
    if eroare:
        return eroare
    try:
        registru = valideaza_registru(corp)
    except EroareCorp as e:
        return _eroare(400, str(e))
    try:
        with _blocat():
            curent = _citeste_registru(True)
            if curent is not None and _moment(registru['generat'], 'generat') < _moment(curent['generat'], 'generat'):
                return _eroare(409, 'registru mai vechi decat cel curent (%s)' % curent['generat'])
            _scrie_atomic(F_REGISTRU, _json_bytes(registru))
    except OSError:
        logger.exception('Asistent: scrierea registrului a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea registrului.')
    return jsonify({'ok': True, 'items': len(registru['items'])})


@asistent_bp.route('/api/asistent/actiuni', methods=['GET'])
@login_required
@_doar_masina
def get_actiuni():
    """Actiunile lui Ion pe itemi, cele mai vechi intai. `?stare=asteapta` (implicit) sau `consumat`;
    alta valoare: 400. Raspuns: lista [{uid, ts, item_id, actiune, zile, din}]."""
    stare = request.args.get('stare', 'asteapta')
    if stare not in ('asteapta', 'consumat'):
        return _eroare(400, 'stare: asteapta sau consumat')
    randuri = [r for r in _citeste_actiuni() if r.get('stare') == stare]
    randuri.sort(key=lambda r: r.get('ts') or '')
    return jsonify([{'uid': r['uid'], 'ts': r.get('ts'), 'item_id': r.get('item_id'), 'actiune': r.get('actiune'),
                     'zile': r.get('zile'), 'din': r.get('din')} for r in randuri])


@asistent_bp.route('/api/asistent/actiuni/<uid>/consumat', methods=['POST'])
@login_required
@_doar_masina
def post_consumat(uid):
    """Asistentul marcheaza actiunea aplicata: {rezultat: ok|fail, mesaj?}. 404 uid necunoscut, 409
    deja consumata (o retrimitere nu rescrie rezultatul). Raspuns: {ok, uid}."""
    corp, eroare = _corp_json(MAX_CORP)
    if eroare:
        return eroare
    try:
        _obiect(corp, 'corpul', CAMPURI_CONSUMAT)
        rezultat = _enum(corp, 'rezultat', 'corpul', ('ok', 'fail'))
        mesaj = _text(corp, 'mesaj', 'corpul', 300, optional=True)
    except EroareCorp as e:
        return _eroare(400, str(e))
    if not _RE_UID.fullmatch(uid):
        return _eroare(404, 'actiune necunoscuta')
    try:
        with _blocat():
            randuri = _citeste_actiuni(True)
            rand = next((r for r in randuri if r['uid'] == uid), None)
            if rand is None:
                return _eroare(404, 'actiune necunoscuta')
            if rand.get('stare') == 'consumat':
                return _eroare(409, 'actiunea e deja consumata')
            rand.update(stare='consumat', consumat=_z(_acum()), rezultat=rezultat, mesaj=mesaj)
            _scrie_actiuni(randuri)
    except OSError:
        logger.exception('Asistent: scrierea actiunilor a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea actiunii.')
    return jsonify({'ok': True, 'uid': uid})


@asistent_bp.route('/api/asistent/fir/noi', methods=['GET'])
@login_required
@_doar_masina
def get_fir_noi():
    """Mesajele lui Ion cu stare `nou`, cele mai vechi intai (lista). Asistentul le preia cu
    `POST /api/asistent/fir/<id>/stare`."""
    return jsonify([_mesaj(r) for r in _citeste_fir() if r.get('cine') == 'ion' and r.get('stare') == 'nou'])


@asistent_bp.route('/api/asistent/fir/<id_>/stare', methods=['POST'])
@login_required
@_doar_masina
def post_stare(id_):
    """Asistentul schimba starea unui mesaj al lui Ion: nou->preluat, preluat->gata|eroare,
    nou->gata|eroare. Aceeasi stare a doua oara: 200 fara rescriere (o reincercare); orice alta
    tranzitie: 409. 404 mesaj necunoscut. Corp: {stare, task_id?, mesaj?}. Raspuns: {ok, id, stare}."""
    corp, eroare = _corp_json(MAX_CORP)
    if eroare:
        return eroare
    try:
        _obiect(corp, 'corpul', CAMPURI_STARE)
        stare = _enum(corp, 'stare', 'corpul', STARI_MESAJ)
        task_id = _text(corp, 'task_id', 'corpul', 80, nevid=True, optional=True)
        mesaj = _text(corp, 'mesaj', 'corpul', 300, optional=True)
    except EroareCorp as e:
        return _eroare(400, str(e))
    if not _RE_MSG.fullmatch(id_):
        return _eroare(404, 'mesaj necunoscut')
    try:
        with _blocat():
            randuri = _citeste_fir(True)
            rand = next((r for r in randuri if r['id'] == id_), None)
            if rand is None:
                return _eroare(404, 'mesaj necunoscut')
            curenta = rand.get('stare')
            if curenta is None:
                return _eroare(409, 'mesajul nu e al lui Ion: nu are stare')
            if curenta != stare:
                if stare not in TRANZITII.get(curenta, ()):
                    return _eroare(409, 'tranzitie nepermisa: %s -> %s' % (curenta, stare))
                rand['stare'] = stare
                if task_id is not None:
                    rand['task_id'] = task_id
                if mesaj is not None:
                    rand['stare_detaliu'] = mesaj
                _scrie_fir(randuri)
    except OSError:
        logger.exception('Asistent: scrierea firului a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea firului.')
    return jsonify({'ok': True, 'id': id_, 'stare': stare})


@asistent_bp.route('/api/asistent/prezenta/<masina>', methods=['PUT'])
@login_required
@_doar_masina
def put_prezenta(masina):
    """O masina spune ca e pornita: {activ: bool, idle_s: int >= 0, versiune?: <=40}. Token de masina sau sesiune;
    dispozitivul primeste 403; masina trebuie sa fie server, pc-job sau ionpc (404). `ultima` o pune serverul.
    Idempotent: aceeasi cerere de doua ori lasa aceeasi stare (doar `ultima` avanseaza). Raspuns: {ok, masina}."""
    if masina not in IDS_MASINI:
        return _eroare(404, 'masina necunoscuta (%s)' % '|'.join(IDS_MASINI))
    corp, eroare = _corp_json(MAX_CORP)
    if eroare:
        return eroare
    try:
        _obiect(corp, 'corpul', CAMPURI_PREZENTA)
        if not isinstance(corp.get('activ'), bool):
            raise EroareCorp('corpul.activ: trebuie sa fie true sau false')
        idle_s = _intreg(corp, 'idle_s', 'corpul', 0, MAX_IDLE_S)
        versiune = _text(corp, 'versiune', 'corpul', 40, nevid=True, optional=True)
    except EroareCorp as e:
        return _eroare(400, str(e))
    rand = {'ultima': _z(_acum()), 'activ': corp['activ'], 'idle_s': idle_s, 'versiune': versiune}
    try:
        with _blocat():
            prezenta = _citeste_prezenta(True)
            prezenta[masina] = rand
            _scrie_atomic(F_PREZENTA, _json_bytes({'masini': prezenta}))
    except OSError:
        logger.exception('Asistent: scrierea prezentei a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea prezentei.')
    return jsonify({'ok': True, 'masina': masina})


# --------------------------------------------------------------------------- rute: Torqa -> backend

@asistent_bp.route('/api/asistent', methods=['GET'])
@login_required
def get_asistent():
    """Vederea pentru pagina System: registrul (doar itemii activi), veghea, ultimele 100 de mesaje,
    actiunile in asteptare, starea push-ului si `masini` (prezenta, v1.1). Sesiune sau orice Bearer valid
    (inclusiv dispozitivul). Fara registru urcat: `registru.generat = null`, `items = []`, `veghe = null`."""
    acum = _acum()
    registru = _citeste_registru()
    if registru is None:
        vedere_registru, veghe = {'generat': None, 'vechime_min': None, 'items': [], 'surse': {}}, None
    else:
        vechime = int(max(0.0, (acum - _moment(registru['generat'], 'generat')).total_seconds()) // 60)
        vedere_registru = {'generat': registru['generat'], 'vechime_min': vechime,
                           'items': [it for it in registru['items'] if _activ(it, acum)],
                           'surse': registru['surse']}
        veghe = registru['veghe']
    return jsonify({
        'v': 1, 'acum': _z(acum),
        'registru': vedere_registru,
        'veghe': veghe,
        'fir': [_mesaj(r) for r in _citeste_fir()[-FIR_IN_VEDERE:]],
        'actiuni_in_asteptare': [{'uid': r['uid'], 'item_id': r.get('item_id'), 'actiune': r.get('actiune')}
                                 for r in _citeste_actiuni() if _in_asteptare(r)],
        'push': {'configurat': fcm.configurat()},
        'masini': _masini(acum),
    })


@asistent_bp.route('/api/asistent/actiune', methods=['POST'])
@login_required
def post_actiune():
    """Ion alege o actiune pe un item (din pagina sau din notificare). Itemul trebuie sa existe in
    registru (404 altfel), iar actiunea sa fie in `item.actiuni` (`nu_util` e mereu permis; altfel 400).
    `zile` (1-31, implicit 1) doar la `amana`. O a doua actiune pe acelasi item cat prima asteapta: 409,
    deci o cerere retrimisa nu dubleaza nimic. Raspuns 201: {uid}."""
    corp, eroare = _corp_json(MAX_CORP)
    if eroare:
        return eroare
    try:
        _obiect(corp, 'corpul', CAMPURI_ACTIUNE)
        item_id = _text(corp, 'item_id', 'corpul', 120, nevid=True)
        actiune = _enum(corp, 'actiune', 'corpul', ACTIUNI_POST)
        zile = None
        if 'zile' in corp:
            if actiune != 'amana':
                raise EroareCorp('corpul.zile: doar la actiunea amana')
            zile = _intreg(corp, 'zile', 'corpul', 1, MAX_ZILE)
        elif actiune == 'amana':
            zile = 1
        din = _enum(corp, 'din', 'corpul', DIN) if 'din' in corp else 'pagina'
    except EroareCorp as e:
        return _eroare(400, str(e))
    registru = _citeste_registru()
    item = next((it for it in registru['items'] if it['id'] == item_id), None) if registru else None
    if item is None:
        return _eroare(404, 'itemul nu exista in registru')
    if not _activ(item, _acum()):
        # Gata, ignorat, la_claude sau amanat in viitor: o a doua apasare pe butonul din notificare
        # (dupa ce asistentul a preluat prima actiune) nu trebuie sa creeze un al doilea task.
        return _eroare(409, 'itemul nu e activ (stare: %s)' % item['stare'])
    if actiune != 'nu_util' and actiune not in item['actiuni']:
        return _eroare(400, 'corpul.actiune: itemul nu permite %s (permise: %s)' % (actiune, ', '.join(item['actiuni']) or 'niciuna'))
    rand = {'uid': secrets.token_hex(6), 'ts': _z(_acum()), 'item_id': item_id, 'actiune': actiune,
            'zile': zile, 'din': din, 'stare': 'asteapta', 'consumat': None, 'rezultat': None, 'mesaj': None}
    try:
        with _blocat():
            randuri = _citeste_actiuni(True)
            if any(r.get('item_id') == item_id and _in_asteptare(r) for r in randuri):
                return _eroare(409, 'itemul are deja o actiune in asteptare')
            randuri.append(rand)
            _scrie_actiuni(randuri)
    except OSError:
        logger.exception('Asistent: scrierea actiunilor a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea actiunii.')
    return jsonify({'uid': rand['uid']}), 201


def _fir_ion(corp, via):
    """Mesajul lui Ion (sesiune, dispozitiv sau masina cu cine=ion). `via` il pune serverul, nu clientul:
    asistentul afla de unde vine mesajul. 201 {id} / 400 / 429."""
    try:
        _obiect(corp, 'corpul', CAMPURI_FIR_ION)
        if 'cine' in corp and corp['cine'] != 'ion':
            raise EroareCorp('corpul.cine: trebuie sa fie ion')
        text = _text(corp, 'text', 'corpul', 2000, nevid=True)
        _fara_control(text.replace('\n', ' ').replace('\t', ' ').replace('\r', ' '), 'corpul.text')
        sursa = _enum(corp, 'sursa', 'corpul', SURSE_MESAJ) if 'sursa' in corp else 'scris'
        raspuns_la = _text(corp, 'raspuns_la', 'corpul', 20, nevid=True, optional=True)
        if raspuns_la is not None and not _RE_MSG.fullmatch(raspuns_la):
            raise EroareCorp('corpul.raspuns_la: id de mesaj (m_...)')
        ref = _ref(corp['ref'], 'corpul.ref') if 'ref' in corp else None
        tinta = _enum(corp, 'tinta', 'corpul', TINTE) if 'tinta' in corp else 'auto'
        alegere = _text(corp, 'alegere', 'corpul', 40, nevid=True, optional=True)
        if alegere is not None and raspuns_la is None:
            raise EroareCorp('corpul.alegere: doar impreuna cu raspuns_la')
    except EroareCorp as e:
        return _eroare(400, str(e))
    acum = _acum()
    try:
        with _blocat():
            randuri = _citeste_fir(True)
            intrebare = None
            if alegere is not None:
                # Raspunsul la o intrebare: intrebarea si mesajul lui Ion se scriu impreuna, intr-un singur
                # `_scrie_fir`, sub aceeasi blocare; nu exista o stare in care una e scrisa fara cealalta.
                intrebare = next((r for r in randuri if r['id'] == raspuns_la), None)
                if intrebare is None:
                    return _eroare(404, 'intrebarea din raspuns_la nu exista')
                if intrebare.get('cine') != 'asistent' or intrebare.get('tip') not in TIPURI_CU_OPTIUNI:
                    return _eroare(409, 'mesajul din raspuns_la nu e o intrebare (intrebare sau asteapta)')
                if intrebare.get('raspuns'):
                    return _eroare(409, 'intrebarea a primit deja raspuns')
                ids = [o.get('id') for o in intrebare.get('optiuni') or [] if isinstance(o, dict)]
                if alegere not in ids:
                    return _eroare(400, 'corpul.alegere: una din %s' % '|'.join(map(str, ids)))
            recente = sorted(m for m in (_moment_sau_none(r.get('ts')) for r in randuri if r.get('cine') == 'ion')
                             if m is not None and m > acum - timedelta(hours=1))
            if len(recente) >= MESAJE_PE_ORA:
                # Se elibereaza un loc cand iese din fereastra al (len - 29)-lea cel mai vechi.
                asteapta = int((recente[len(recente) - MESAJE_PE_ORA] + timedelta(hours=1) - acum).total_seconds()) + 1
                return _eroare(429, 'prea multe mesaje (maxim %d pe ora)' % MESAJE_PE_ORA, **{'Retry-After': max(1, asteapta)})
            rand = {'id': _id_mesaj(randuri), 'ts': _z(acum), 'cine': 'ion', 'tip': 'mesaj', 'titlu': None,
                    'text': text, 'sursa': sursa, 'item_id': None, 'task_id': None, 'link': None,
                    'butoane': [], 'raspuns_la': raspuns_la, 'stare': 'nou', 'stare_detaliu': None, 'via': via,
                    'ref': ref, 'tinta': tinta, 'alegere': alegere}
            if intrebare is not None:
                intrebare['raspuns'] = {'optiune': alegere, 'ts': rand['ts']}
            randuri.append(rand)
            _scrie_fir(randuri)
    except OSError:
        logger.exception('Asistent: scrierea firului a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea mesajului.')
    return jsonify({'id': rand['id']}), 201


def _fir_asistent(corp):
    """Mesajul asistentului, cu push optional. 201 {id, push} / 400."""
    try:
        _obiect(corp, 'corpul', CAMPURI_FIR_ASISTENT)
        tip = _enum(corp, 'tip', 'corpul', TIPURI_ASISTENT)
        text = _text(corp, 'text', 'corpul', 2000, nevid=True)
        titlu = _nul_text(corp, 'titlu', 'corpul', 140)
        item_id = _nul_text(corp, 'item_id', 'corpul', 120)
        task_id = _nul_text(corp, 'task_id', 'corpul', 80)
        link = _link(corp, 'link', 'corpul')
        butoane = []
        if corp.get('butoane') is not None:
            butoane = list(_lista(corp, 'butoane', 'corpul', len(BUTOANE)))
            for ix, b in enumerate(butoane):
                if not isinstance(b, str) or b not in BUTOANE:
                    raise EroareCorp('corpul.butoane[%d]: una din %s' % (ix, '|'.join(BUTOANE)))
            if len(set(butoane)) != len(butoane):
                raise EroareCorp('corpul.butoane: valori duplicate')
        raspuns_la = _nul_text(corp, 'raspuns_la', 'corpul', 20)
        if raspuns_la is not None and not _RE_MSG.fullmatch(raspuns_la):
            raise EroareCorp('corpul.raspuns_la: id de mesaj (m_...)')
        optiuni = []
        if tip in TIPURI_CU_OPTIUNI:
            if corp.get('optiuni') is None:
                raise EroareCorp('corpul.optiuni: obligatoriu la %s' % '|'.join(TIPURI_CU_OPTIUNI))
            optiuni = _optiuni(corp, 'corpul')
        elif corp.get('optiuni') is not None:
            raise EroareCorp('corpul.optiuni: doar la %s' % '|'.join(TIPURI_CU_OPTIUNI))
        masina = _enum(corp, 'masina', 'corpul', IDS_MASINI) if corp.get('masina') is not None else None
        ref = _ref(corp['ref'], 'corpul.ref') if corp.get('ref') is not None else None
        prioritate = None
        if corp.get('push') is not None:
            push = _obiect(corp['push'], 'corpul.push', CAMPURI_PUSH)
            prioritate = _enum(push, 'prioritate', 'corpul.push', PRIORITATI) if 'prioritate' in push else 'normal'
    except EroareCorp as e:
        return _eroare(400, str(e))
    try:
        with _blocat():
            randuri = _citeste_fir(True)
            rand = {'id': _id_mesaj(randuri), 'ts': _z(_acum()), 'cine': 'asistent', 'tip': tip, 'titlu': titlu,
                    'text': text, 'sursa': None, 'item_id': item_id, 'task_id': task_id, 'link': link,
                    'butoane': butoane, 'raspuns_la': raspuns_la, 'stare': None, 'stare_detaliu': None, 'via': None,
                    'optiuni': optiuni, 'masina': masina, 'ref': ref, 'raspuns': None}
            randuri.append(rand)
            _scrie_fir(randuri)
    except OSError:
        logger.exception('Asistent: scrierea firului a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea mesajului.')
    if prioritate is None:                                     # fara `push`: nu se trimite nimic
        push = {'incercat': False, 'trimise': 0, 'erori': [], 'motiv': None}
    else:
        push = _trimite_push(rand, prioritate)                 # cu blocarea eliberata: retea
    return jsonify({'id': rand['id'], 'push': push}), 201


@asistent_bp.route('/api/asistent/fir', methods=['POST'])
@login_required
def post_fir():
    """Un mesaj in fir. Cu sesiune sau token de dispozitiv e mesajul lui Ion (`cine` e forțat `ion`;
    `cine=asistent` da 403): {text, sursa?, raspuns_la?} -> 201 {id}, stare `nou`, 30 pe ora (429).
    Cu token de masina: `cine` obligatoriu; `asistent` -> {tip, text, ...push?} -> 201 {id, push};
    `ion` -> ca mai sus. Retrimiterea aceluiasi mesaj il dubleaza (contractul n-are cheie de idempotenta)."""
    corp, eroare = _corp_json(MAX_CORP)
    if eroare:
        return eroare
    if not isinstance(corp, dict):
        return _eroare(400, 'corpul: trebuie sa fie obiect')
    cine = corp.get('cine')
    if 'authenticated' in session or _este_dispozitiv():
        if cine == 'asistent':
            return _eroare(403, 'doar tokenul de masina scrie ca asistent')
        return _fir_ion(corp, 'sesiune' if 'authenticated' in session else 'dispozitiv')
    if cine not in ('asistent', 'ion'):
        return _eroare(400, 'corpul.cine: asistent sau ion')
    return _fir_asistent(corp) if cine == 'asistent' else _fir_ion(corp, 'masina')


# --------------------------------------------------------------------------- rute: tokenurile push

def _citeste_corp_token(campuri):
    corp, eroare = _corp_json(MAX_CORP)
    if eroare:
        return None, eroare
    try:
        _obiect(corp, 'corpul', campuri)
        token = _text(corp, 'token', 'corpul', 4096, nevid=True)
        if any(c.isspace() or ord(c) < 32 or ord(c) > 126 for c in token):
            raise EroareCorp('corpul.token: fara spatii sau caractere in afara ASCII')
        return (corp, token), None
    except EroareCorp as e:
        return None, _eroare(400, str(e))


@asistent_bp.route('/api/asistent/push/token', methods=['POST'])
@login_required
def post_token():
    """Inregistreaza (sau reimprospateaza) tokenul FCM al dispozitivului: upsert pe `token`, cu
    `ultima_vedere`. Idempotent. Pastreaza cele mai recent vazute 20. Raspuns 200: {ok}."""
    rezultat, eroare = _citeste_corp_token(CAMPURI_TOKEN)
    if eroare:
        return eroare
    corp, token = rezultat
    try:
        platforma = _enum(corp, 'platforma', 'corpul', ('android',))
        aplicatie = _text(corp, 'aplicatie', 'corpul', 100, nevid=True)
        if not _RE_APLICATIE.fullmatch(aplicatie):
            raise EroareCorp('corpul.aplicatie: nume de pachet, ex. org.iupif.torqa')
        versiune = _text(corp, 'versiune', 'corpul', 40, nevid=True, optional=True)
    except EroareCorp as e:
        return _eroare(400, str(e))
    acum = _z(_acum())
    try:
        with _blocat():
            tokenuri = _citeste_tokenuri(True)
            existent = next((t for t in tokenuri if t['token'] == token), None)
            if existent is None:
                existent = {'token': token, 'inregistrat': acum}
                tokenuri.append(existent)
            existent.update(platforma=platforma, aplicatie=aplicatie, versiune=versiune, ultima_vedere=acum)
            if len(tokenuri) > MAX_TOKENURI:
                tokenuri.sort(key=lambda t: t.get('ultima_vedere') or '', reverse=True)
                tokenuri = tokenuri[:MAX_TOKENURI]
            _scrie_tokenuri(tokenuri)
    except OSError:
        logger.exception('Asistent: scrierea tokenurilor a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea tokenului.')
    return jsonify({'ok': True})


@asistent_bp.route('/api/asistent/push/token', methods=['DELETE'])
@login_required
def sterge_token():
    """Scoate tokenul FCM (Torqa il cheama la iesire). Idempotent: un token necunoscut da tot 200.
    Raspuns: {ok, scos}."""
    rezultat, eroare = _citeste_corp_token(CAMPURI_TOKEN_STERS)
    if eroare:
        return eroare
    _, token = rezultat
    try:
        with _blocat():
            tokenuri = _citeste_tokenuri(True)
            ramase = [t for t in tokenuri if t['token'] != token]
            scos = len(ramase) != len(tokenuri)
            if scos:
                _scrie_tokenuri(ramase)
    except OSError:
        logger.exception('Asistent: scrierea tokenurilor a esuat pe disc')
        return _eroare(500, 'Eroare pe disc la salvarea tokenului.')
    return jsonify({'ok': True, 'scos': scos})

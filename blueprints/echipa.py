# Echipa Blueprint
# Planul echipei SRP din Gantt-ul „Project Plan" (tab Teams), CITIT de pe server si dat Torqa prin
# `GET /api/echipa` si prin cheia `echipa` din `GET /api/calendar` (vezi `admin.calendar_view`).
#
# DE CE UN SNAPSHOT-FISIER SI DE CE FETCH PE SERVER. Gantt-ul se citeste fara login, cu un
# planId si un secret (un link, nu o parola): serverul il cere singur la cel mult 15 minute si
# tine un snapshot NORMALIZAT in `uploads/echipa/plan.json` (rescris intreg si atomic, ca
# `outlook/calendar.json`). Fara tabela, fara migrare, nu intra in backup. Raspunsul brut al
# Gantt-ului nu se pastreaza: are email-uri, entraId si hash-ul parolei de scriere, iar Torqa
# n-are nevoie de ele. Citirea nu scrie nimic in Gantt. Scrierea (amendament 2026-11-18, mai jos la
# „dashboard -> Gantt") atinge doar etapele in care Ion e resursa, dupa o perioada salvata in
# dashboard sau la cererea lui. Decizia: docs/decizii/2026-11-18-gantt-srp.md.
#
# SECRETUL NU IESE NICIODATA: nici in raspuns, nici in log, nici in mesajele de eroare. De
# aceea URL-ul cererii nu se logheaza si mesajele de eroare ale `urllib` (care pot purta
# adrese) nu se copiaza: se pastreaza doar un motiv scris aici.

import json
import logging
import os
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from blueprints.outlook import _data, _data_ora
from database import get_db
from utils import login_required, UPLOAD_FOLDER

logger = logging.getLogger('pif_dashboard')

echipa_bp = Blueprint('echipa', __name__)

DIR_ECHIPA = os.path.join(UPLOAD_FOLDER, 'echipa')
FISIER_SURSA = 'sursa.json'
FISIER_PLAN = 'plan.json'
FISIER_LOCK = 'reimprospatare.lock'

URL_GANTT = 'https://api.projectplan-powerpoint.com/OnlinePlan/get'
TIMEOUT_GANTT = 5                 # secunde, cat asteapta o citire
MAX_RASPUNS_GANTT = 8 * 1024 * 1024
VALABILITATE = timedelta(minutes=15)
PAUZA_DUPA_INCERCARE = 60         # secunde: dupa un esec (sau cat dureaza o citire) nu se mai incearca
MAX_CORP = 4096
MAX_TEXT = 300

_RE_UUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')
_RE_EMAIL = re.compile(r'[^@\s]{1,100}@[^@\s]{1,100}\.[^@\s]{2,30}')
_RE_DATA_GANTT = re.compile(r'(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?')
# Codul de proiect din textul activitatii radacina: forma scurta `26_287` (cu C optional in fata)
# sau forma lunga cu 6 cifre (`250826E_C1`, `230728_C1`, `250656E`). Ancorat la inceputul textului.
_RE_COD_SCURT = re.compile(r'C?(\d{2}_\d{3})(?!\d)', re.I)
_RE_COD_LUNG = re.compile(r'(\d{6})(E?)(?:_C(\d+))?(?!\d)', re.I)


class EroareGantt(Exception):
    """Gantt-ul nu s-a putut citi sau are alta forma. Mesajul e scris de noi (fara URL, fara
    secret) si poate ajunge in raspuns si in log."""


# ------------------------------------------------------------------------------ fisiere

def _cale(nume):
    return os.path.join(DIR_ECHIPA, nume)


def _scrie_atomic(nume, obiect, privat=False):
    """Fisier alaturat, fsync, apoi `os.replace`: nu ramane niciodata un fisier taiat.
    `privat`: doar proprietarul il citeste (sursa.json are secretul)."""
    os.makedirs(DIR_ECHIPA, exist_ok=True)
    cale = _cale(nume)
    tmp = '%s.%s.tmp' % (cale, secrets.token_hex(3))
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600 if privat else 0o644)
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(obiect, fh, ensure_ascii=False)
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


def _citeste_json(nume):
    try:
        with open(_cale(nume), 'r', encoding='utf-8') as fh:
            return json.load(fh)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logger.warning('Echipa: %s nu se poate citi; se ignora', nume)
        return None


def citeste_sursa():
    """{planId, secret, email} sau None."""
    sursa = _citeste_json(FISIER_SURSA)
    if (not isinstance(sursa, dict)
            or not all(isinstance(sursa.get(c), str) and sursa.get(c) for c in ('planId', 'secret', 'email'))):
        return None
    return sursa


def citeste_snapshot():
    """Snapshot-ul de pe disc, sau None daca nu exista ori nu se poate citi."""
    snap = _citeste_json(FISIER_PLAN)
    if snap is None:
        return None
    if (not isinstance(snap, dict) or not isinstance(snap.get('activitati'), list)
            or not isinstance(snap.get('resurse'), list) or not isinstance(snap.get('generatedAt'), str)):
        logger.warning('Echipa: plan.json are alta forma decat cea scrisa; se ignora')
        return None
    return snap


# ------------------------------------------------------------------------------ Gantt

def _acum():
    return datetime.now(timezone.utc)


def _azi():
    """Data locala a serverului, ca in `calendar_view` (`datetime.now().date()`)."""
    return datetime.now().date().isoformat()


def _descarca(plan_id, secret):
    """Raspunsul Gantt-ului, ca dict (JSON-ul brut). Ridica `EroareGantt` cu un motiv sigur.
    Singura functie care vorbeste cu reteaua (testele o inlocuiesc)."""
    url = URL_GANTT + '?' + urllib.parse.urlencode({'planId': plan_id, 'secret': secret})
    cerere = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'pif-dashboard'})
    try:
        with urllib.request.urlopen(cerere, timeout=TIMEOUT_GANTT) as r:
            if r.status != 200:
                raise EroareGantt('Gantt-ul a raspuns cu codul %d' % r.status)
            brut = r.read(MAX_RASPUNS_GANTT + 1)
    except EroareGantt:
        raise
    except urllib.error.HTTPError as e:
        raise EroareGantt('Gantt-ul a raspuns cu codul %d' % e.code) from None
    except Exception:                            # URLError, timeout, SSL, conexiune: mesajul lor poate purta adrese
        raise EroareGantt('Gantt-ul nu raspunde') from None
    if len(brut) > MAX_RASPUNS_GANTT:
        raise EroareGantt('raspunsul Gantt-ului e prea mare')
    try:
        raspuns = json.loads(brut.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise EroareGantt('Gantt-ul a raspuns cu ceva care nu e JSON') from None
    if not isinstance(raspuns, dict):
        raise EroareGantt('Gantt-ul a raspuns cu alta forma decat un obiect')
    return raspuns


def _json_in_json(valoare, camp):
    """Gantt-ul pune `plan` si `resources` ca STRING JSON; accepta si varianta deja parsata."""
    if isinstance(valoare, str):
        try:
            return json.loads(valoare)
        except (ValueError, RecursionError):
            raise EroareGantt('campul %s din raspunsul Gantt-ului nu e JSON' % camp) from None
    return valoare


def _text(valoare):
    return valoare.strip()[:MAX_TEXT] if isinstance(valoare, str) else ''


def _data_gantt(valoare):
    """`YYYY-MM-DD HH:MM` -> datetime (naiv), sau None."""
    if not isinstance(valoare, str):
        return None
    m = _RE_DATA_GANTT.match(valoare.strip())
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                        int(m.group(4) or 0), int(m.group(5) or 0))
    except ValueError:
        return None


def _id_parinte(valoare):
    """`parent` vine ca 0, int sau string: radacina e 0 / '0' / gol, restul se compara ca str."""
    if valoare is None or isinstance(valoare, bool):
        return None
    s = str(valoare).strip()
    return None if s in ('', '0') else s


def _resurse_activitate(valoare):
    if isinstance(valoare, (str, int)) and not isinstance(valoare, bool):
        valoare = [valoare]
    if not isinstance(valoare, list):
        return []
    return [str(r) for r in valoare if isinstance(r, (str, int)) and not isinstance(r, bool) and str(r)]


def analiza_cod(text):
    """Codul de proiect de la inceputul unui text -> tuplu canonic, sau None.
    Scurt: ('s', '26_287'). Lung: ('l', '250826', 'E' sau '', n sau None)."""
    if not isinstance(text, str):
        return None
    t = text.strip()
    m = _RE_COD_SCURT.match(t)
    if m:
        return ('s', m.group(1))
    m = _RE_COD_LUNG.match(t)
    if m:
        return ('l', m.group(1), 'E' if m.group(2) else '', int(m.group(3)) if m.group(3) else None)
    return None


def cod_text(cod):
    """Forma de afisare a unui cod analizat: `26_287`, `250826E_C1`."""
    if cod is None:
        return None
    if cod[0] == 's':
        return cod[1]
    return cod[1] + cod[2] + ('_C%d' % cod[3] if cod[3] is not None else '')


def coduri_potrivite(a, b):
    """Forma scurta se compara intreaga; forma lunga pe cifre (E nu conteaza) si pe sufixul
    _Cn doar cand exista pe ambele parti. Scurt si lung nu se potrivesc niciodata."""
    if a is None or b is None or a[0] != b[0]:
        return False
    if a[0] == 's':
        return a[1] == b[1]
    return a[1] == b[1] and (a[3] is None or b[3] is None or a[3] == b[3])


def normalizeaza(raspuns, email, acum=None):
    """Raspunsul brut al Gantt-ului -> snapshot normalizat (fara email-uri, entraId, hash-uri).
    `eu` e id-ul resursei cu `email`, sau None daca nu exista. Ridica `EroareGantt`."""
    plan = _json_in_json(raspuns.get('plan'), 'plan')
    resurse_brut = _json_in_json(raspuns.get('resources'), 'resources')
    if not isinstance(plan, dict) or not isinstance(plan.get('data'), list):
        raise EroareGantt('planul din raspunsul Gantt-ului are alta forma decat cea asteptata')
    if not isinstance(resurse_brut, list):
        raise EroareGantt('resursele din raspunsul Gantt-ului au alta forma decat cea asteptata')

    resurse, eu = [], None
    email_l = (email or '').strip().lower()
    for r in resurse_brut:
        if not isinstance(r, dict) or r.get('id') in (None, ''):
            continue
        rid = str(r['id'])
        resurse.append({'id': rid, 'nume': _text(r.get('displayName')) or _text(r.get('fullName'))})
        if email_l and isinstance(r.get('email'), str) and r['email'].strip().lower() == email_l:
            eu = rid

    brut = {}                                     # id -> activitate, pentru urcarea spre radacina
    for a in plan['data']:
        if isinstance(a, dict) and a.get('id') not in (None, ''):
            brut[str(a['id'])] = a

    def radacina(aid):
        curent = aid
        for _ in range(20):                       # garda de ciclu
            p = _id_parinte(brut[curent].get('parent'))
            if p is None or p not in brut or p == curent:
                return curent
            curent = p
        return curent

    activitati, omise = [], 0
    for aid, a in brut.items():
        start = _data_gantt(a.get('start_date'))
        sfarsit = _data_gantt(a.get('end_date'))
        if start is None or sfarsit is None:
            omise += 1
            continue
        # Capatul din Gantt e exclusiv in practica (23:59 sau 01:00 = ziua aceea, 00:00 = ziua dinainte).
        end = max((sfarsit - timedelta(minutes=1)).date(), start.date())
        rad = brut[radacina(aid)]
        cod = analiza_cod(_text(rad.get('text')))
        p = _id_parinte(a.get('parent'))
        resurse_a = _resurse_activitate(a.get('resource'))
        progres = a.get('progress')
        progres = min(1.0, max(0.0, float(progres))) if isinstance(progres, (int, float)) and not isinstance(progres, bool) else 0.0
        stare = a.get('state')
        activitati.append({
            'id': aid,
            'parinte_id': p,
            'text': _text(a.get('text')),
            'proiect_text': _text(rad.get('text')),
            'start': start.date().isoformat(),
            'end': end.isoformat(),
            'stare': stare if isinstance(stare, str) and stare else None,
            'progres': progres,
            'resurse': resurse_a,
            'ale_mele': eu is not None and eu in resurse_a,
            'cod': cod_text(cod),
            'proiect_id': None,
        })
    if omise:
        logger.warning('Echipa: %d activitati fara date valide au fost omise', omise)
    activitati.sort(key=lambda x: (x['start'], x['end'], x['id']))
    return {
        'generatedAt': (acum or _acum()).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'eu': eu,
        'resurse': resurse,
        'activitati': activitati,
    }


# ------------------------------------------------------------------------------ reimprospatare

def _ia_incercarea():
    """True daca ACEST worker face citirea acum. Fisierul `reimprospatare.lock` (creat cu
    O_EXCL) tine locul de lacat intre cei doi workeri si de pauza dupa un esec: cat e mai nou
    de `PAUZA_DUPA_INCERCARE` secunde nu mai incearca nimeni. Dupa succes se sterge. Un worker
    cazut in mijlocul citirii lasa lacatul, care expira singur."""
    os.makedirs(DIR_ECHIPA, exist_ok=True)
    cale = _cale(FISIER_LOCK)
    for _ in range(2):
        try:
            os.close(os.open(cale, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            try:
                varsta = time.time() - os.path.getmtime(cale)
            except OSError:
                continue
            if varsta < PAUZA_DUPA_INCERCARE:
                return False
            try:
                os.remove(cale)
            except OSError:
                pass
    return False


def _elibereaza():
    try:
        os.remove(_cale(FISIER_LOCK))
    except OSError:
        pass


def _vechime(snapshot):
    g = _data_ora(snapshot.get('generatedAt')) if snapshot else None
    return None if g is None else _acum() - g


def snapshot_proaspat():
    """(snapshot, stale). Reimprospateaza daca snapshot-ul lipseste sau are peste 15 minute si
    sursa e configurata. La esec pastreaza snapshot-ul vechi si da `stale=True`. Fara sursa si
    fara snapshot: (None, False). Nu ridica niciodata."""
    snapshot = citeste_snapshot()
    sursa = citeste_sursa()
    varsta = _vechime(snapshot)
    expirat = snapshot is None or varsta is None or varsta >= VALABILITATE
    if expirat and sursa is not None and _ia_incercarea():
        try:
            nou = normalizeaza(_descarca(sursa['planId'], sursa['secret']), sursa['email'])
            _scrie_atomic(FISIER_PLAN, nou)
            snapshot, expirat = nou, False
            _elibereaza()
            if nou['eu'] is None:
                logger.warning('Echipa: email-ul sursei nu mai e printre resursele planului')
        except EroareGantt as e:
            logger.warning('Echipa: reimprospatarea a esuat [cod=gantt_indisponibil]: %s', e)
        except Exception:
            logger.warning('Echipa: reimprospatarea a esuat [cod=eroare_interna]', exc_info=False)
    return snapshot, bool(snapshot is not None and expirat)


# ------------------------------------------------------------------------------ dashboard + avertizari

def _incarca_dashboard():
    """Proiectele (cu cod) si perioadele din baza. Doar citire."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, nume, cod_proiect, status FROM proiecte")
        proiecte = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT id, proiect_id, data_start, data_sfarsit FROM implementari")
        implementari = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    return proiecte, implementari


def _activ(proiect):
    return proiect.get('status') not in ('finalizat', 'anulat')


def _alege_proiect(cod, proiecte_cu_cod):
    """Proiectul din dashboard care se potriveste cu `cod`. La mai multe: cel activ, apoi cel cu
    sufixul _Cn egal pe ambele parti, apoi dupa cod si id (deterministic)."""
    candidati = [p for p in proiecte_cu_cod if coduri_potrivite(cod, p['_cod'])]
    if not candidati:
        return None

    def cheie(p):
        exact = cod[0] == 'l' and cod[3] is not None and p['_cod'][3] == cod[3]
        return (0 if _activ(p) else 1, 0 if exact else 1, cod_text(p['_cod']), str(p['id']))
    return min(candidati, key=cheie)


def _intervale_dashboard(implementari):
    """Perioadele unui proiect ca (start, end, id), cu `YYYY-MM-DD`; perioada fara sfarsit e o zi."""
    iesire = []
    for i in implementari:
        s = str(i.get('data_start') or '')[:10]
        e = str(i.get('data_sfarsit') or '').strip()[:10] or s
        if _data(s) is None or _data(e) is None:
            continue
        iesire.append((s, max(e, s), i['id']))
    return iesire


def _zile(a, b):
    return (_data(b) - _data(a)).days


def _perechi(srp, dash):
    """Imperecheaza intervalele fara pereche exacta: intai dupa suprapunere (cea mai mare
    intai), apoi dupa cea mai apropiata data. -> (perechi [(i, j)], srp_singur [i], dash_singur [j])."""
    candidate = []
    for i, (s1, e1) in enumerate(srp):
        for j, (s2, e2) in enumerate(dash):
            suprapunere = _zile(max(s1, s2), min(e1, e2)) + 1
            if suprapunere > 0:
                scor = (0, -suprapunere, abs(_zile(s1, s2)))
            else:
                scor = (1, -suprapunere, abs(_zile(s1, s2)))     # -suprapunere = zilele dintre ele (+1)
            candidate.append((scor, i, j))
    candidate.sort()
    luat_i, luat_j, perechi = set(), set(), []
    for _, i, j in candidate:
        if i not in luat_i and j not in luat_j:
            luat_i.add(i)
            luat_j.add(j)
            perechi.append((i, j))
    return (perechi,
            [i for i in range(len(srp)) if i not in luat_i],
            [j for j in range(len(dash)) if j not in luat_j])


def _srp(a):
    return {'activitate_id': a['id'], 'text': a['text'], 'start': a['start'], 'end': a['end']}


def _dash(start, end, impl_id):
    return {'implementare_id': impl_id, 'start': start, 'end': end}


def calculeaza_avertizari(snapshot, proiecte, implementari, azi):
    """Cele trei avertizari (perioada_diferita, lipseste_in_dashboard, lipseste_in_srp) si
    `proiect_id` pe fiecare activitate (pe loc). Doar intervalele cu end >= `azi`; pentru
    activitatile lui Ion se folosesc FRUNZELE. Nu scrie nimic."""
    activitati = snapshot['activitati']
    by_id = {a['id']: a for a in activitati}
    parinti = {a['parinte_id'] for a in activitati if a['parinte_id'] is not None}

    def radacina(a):
        for _ in range(20):
            p = a['parinte_id']
            if p is None or p not in by_id or p == a['id']:
                return a
            a = by_id[p]
        return a

    cu_cod = []
    for p in proiecte:
        cod = analiza_cod(p.get('cod_proiect'))      # 'TBD', gol, None: nu se potrivesc cu nimic
        if cod is not None:
            cu_cod.append({**p, '_cod': cod})

    # Fiecare radacina din Gantt: proiectul din dashboard (sau None) si activitatile lui Ion de sub ea.
    radacini = {}
    for a in activitati:
        r = radacina(a)
        info = radacini.get(r['id'])
        if info is None:
            cod = analiza_cod(r['text'])
            info = radacini[r['id']] = {
                'radacina': r, 'cod': cod, 'proiect': _alege_proiect(cod, cu_cod) if cod else None,
                'ion': [], 'frunze_ion': []}
        a['proiect_id'] = info['proiect']['id'] if info['proiect'] else None
        if a['ale_mele']:
            info['ion'].append(a)
            if a['id'] not in parinti:
                info['frunze_ion'].append(a)

    avertizari = []
    primite = {}                                   # id proiect dashboard -> frunzele lui Ion (end >= azi)
    cu_ion = set()                                 # id-urile proiectelor cu cel putin o activitate a lui Ion
    for info in radacini.values():
        if not info['ion']:
            continue
        viitoare = sorted((a for a in info['frunze_ion'] if a['end'] >= azi), key=lambda a: (a['start'], a['end'], a['id']))
        p = info['proiect']
        if p is None:
            if viitoare:
                avertizari.append({'tip': 'lipseste_in_dashboard', 'proiect_id': None, 'cod': cod_text(info['cod']),
                                   'proiect_nume': info['radacina']['text'], 'srp': _srp(viitoare[0]), 'dashboard': None})
            continue
        cu_ion.add(p['id'])
        primite.setdefault(p['id'], []).extend(viitoare)

    proiecte_dupa_id = {p['id']: p for p in cu_cod}
    impl_pe_proiect = {}
    for i in implementari:
        impl_pe_proiect.setdefault(i['proiect_id'], []).append(i)

    for pid in sorted(primite, key=str):
        p = proiecte_dupa_id[pid]
        frunze = {}
        for a in primite[pid]:                     # mulțimea intervalelor: o frunza per interval
            frunze.setdefault((a['start'], a['end']), a)
        dash = {}
        if _activ(p):
            for s, e, iid in _intervale_dashboard(impl_pe_proiect.get(pid, [])):
                if e >= azi:
                    dash.setdefault((s, e), iid)
        exacte = set(frunze) & set(dash)
        srp_l = sorted(set(frunze) - exacte)
        dash_l = sorted(set(dash) - exacte)
        perechi, srp_singur, dash_singur = _perechi(srp_l, dash_l)
        baza = {'proiect_id': pid, 'cod': cod_text(p['_cod']), 'proiect_nume': p.get('nume') or ''}
        randuri = [(srp_l[i], dash_l[j]) for i, j in perechi]
        randuri += [(srp_l[i], None) for i in srp_singur] + [(None, dash_l[j]) for j in dash_singur]
        randuri.sort(key=lambda r: (r[0] or r[1], r[1] or r[0]))
        for s, d in randuri:
            avertizari.append({
                'tip': 'perioada_diferita', **baza,
                'srp': _srp(frunze[s]) if s else None,
                'dashboard': _dash(d[0], d[1], dash[d]) if d else None,
            })

    # In dashboard, nu si in SRP: proiect activ, cu cod, cu o perioada de azi incolo, fara nicio activitate a lui Ion cu acelasi cod.
    activitati_ion = [(analiza_cod(radacina(a)['text']), a) for a in activitati if a['ale_mele']]
    for p in sorted(cu_cod, key=lambda x: str(x['id'])):
        if not _activ(p) or p['id'] in cu_ion:
            continue
        if any(coduri_potrivite(c, p['_cod']) for c, _ in activitati_ion):
            continue
        viitoare = sorted((s, e, iid) for s, e, iid in _intervale_dashboard(impl_pe_proiect.get(p['id'], [])) if e >= azi)
        if viitoare:
            s, e, iid = viitoare[0]
            avertizari.append({'tip': 'lipseste_in_srp', 'proiect_id': p['id'], 'cod': cod_text(p['_cod']),
                               'proiect_nume': p.get('nume') or '', 'srp': None, 'dashboard': _dash(s, e, iid)})
    return avertizari


def _continut():
    """(snapshot cu proiect_id puse, avertizari, stale), sau None fara snapshot. Nu ridica: o
    problema aici nu trebuie sa strice `/api/calendar`."""
    try:
        snapshot, stale = snapshot_proaspat()
        if snapshot is None:
            return None
        proiecte, implementari = _incarca_dashboard()
        avertizari = calculeaza_avertizari(snapshot, proiecte, implementari, _azi())
        return snapshot, avertizari, stale
    except Exception:
        logger.exception('Echipa: citirea planului a esuat [cod=eroare_interna]')
        return None


def echipa_completa():
    """Corpul lui `GET /api/echipa`: snapshot + avertizari + stale, sau None."""
    c = _continut()
    if c is None:
        return None
    snapshot, avertizari, stale = c
    return {'generatedAt': snapshot['generatedAt'], 'stale': stale, 'eu': snapshot['eu'],
            'resurse': snapshot['resurse'], 'activitati': snapshot['activitati'], 'avertizari': avertizari}


def echipa_in_fereastra(start, sfarsit):
    """Cheia `echipa` din `/api/calendar`: activitatile care ating `[start, sfarsit)`
    (stringuri YYYY-MM-DD; `end` e inclusiv, deci `end >= start`), sau None."""
    c = _continut()
    if c is None:
        return None
    snapshot, avertizari, stale = c
    return {'generatedAt': snapshot['generatedAt'], 'stale': stale, 'eu': snapshot['eu'],
            'resurse': snapshot['resurse'],
            'activitati': [a for a in snapshot['activitati'] if a['start'] < sfarsit and a['end'] >= start],
            'avertizari': avertizari}


# ------------------------------------------------------------------------------ dashboard -> Gantt

# Scrierea perioadelor in Gantt (amendament 2026-11-18, docs/decizii/2026-11-18-gantt-srp.md).
# Un singur rand de retea scrie: `_trimite_activitate` (POST); testele o inlocuiesc.
URL_ACTIVITATE = 'https://api.projectplan-powerpoint.com/OnlinePlan/entities/task'
FISIER_LACAT_SCRIERE = 'scriere.lock'
EXPIRARE_LACAT_SCRIERE = 60       # secunde: un lacat mai vechi e al unui worker cazut


def _trimite_activitate(plan_id, secret, activitate):
    """Inlocuieste in Gantt activitatea cu `activitate['id']`: corpul e obiectul INTREG, ca in
    `plan.data`; serverul Gantt-ului suprascrie activitatea cu acelasi id. Fara retry. Ridica
    `EroareGantt` cu un motiv sigur (fara URL, fara secret)."""
    url = URL_ACTIVITATE + '?' + urllib.parse.urlencode(
        {'planId': plan_id, 'secret': secret, 'writePassHash': '', 'taskId': str(activitate['id'])})
    corp = json.dumps(activitate, ensure_ascii=False).encode('utf-8')
    cerere = urllib.request.Request(url, data=corp, method='POST', headers={
        'Content-Type': 'application/json; charset=utf-8', 'Accept': 'application/json',
        'User-Agent': 'pif-dashboard'})
    try:
        with urllib.request.urlopen(cerere, timeout=TIMEOUT_GANTT) as r:
            if r.status != 200:
                raise EroareGantt('Gantt-ul a raspuns cu codul %d la scriere' % r.status)
    except EroareGantt:
        raise
    except urllib.error.HTTPError as e:
        raise EroareGantt('Gantt-ul a raspuns cu codul %d la scriere' % e.code) from None
    except Exception:
        raise EroareGantt('Gantt-ul nu raspunde la scriere') from None


def _ia_scrierea():
    """Un singur worker scrie in Gantt odata (doua salvari rapide nu se calca pe plan)."""
    os.makedirs(DIR_ECHIPA, exist_ok=True)
    cale = _cale(FISIER_LACAT_SCRIERE)
    for _ in range(2):
        try:
            os.close(os.open(cale, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return True
        except FileExistsError:
            try:
                varsta = time.time() - os.path.getmtime(cale)
            except OSError:
                continue
            if varsta < EXPIRARE_LACAT_SCRIERE:
                return False
            try:
                os.remove(cale)
            except OSError:
                pass
    return False


def _elibereaza_scrierea():
    try:
        os.remove(_cale(FISIER_LACAT_SCRIERE))
    except OSError:
        pass


def _rez(status, motiv, activitate_id=None):
    """Cheia `srp` din raspunsul rutelor: status ok|ignorat|protejat|conflict|eroare, un motiv
    stabil (cod, nu text de eroare) si id-ul etapei din Gantt (sau None)."""
    return {'status': status, 'motiv': motiv, 'activitate_id': activitate_id}


def interval_perioada(start, sfarsit):
    """(start, end) inclusiv, `YYYY-MM-DD`; perioada fara sfarsit e o zi. None fara start valid."""
    s = str(start or '').strip()[:10]
    e = str(sfarsit or '').strip()[:10] or s
    if _data(s) is None or _data(e) is None:
        return None
    return (s, max(e, s))


def _interval_brut(a):
    """Intervalul unei activitati brute din Gantt, cu capatul inclusiv ca in snapshot, sau None."""
    s, e = _data_gantt(a.get('start_date')), _data_gantt(a.get('end_date'))
    if s is None or e is None:
        return None
    return (s.date().isoformat(), max((e - timedelta(minutes=1)).date(), s.date()).isoformat())


def _radacina_brut(brut, aid):
    curent = aid
    for _ in range(20):                           # garda de ciclu
        p = _id_parinte(brut[curent].get('parent'))
        if p is None or p not in brut or p == curent:
            return curent
        curent = p
    return curent


def _plan_brut(raspuns, email):
    """(activitati brute pe id, id-ul resursei lui Ion sau None). Ridica `EroareGantt`."""
    plan = _json_in_json(raspuns.get('plan'), 'plan')
    resurse = _json_in_json(raspuns.get('resources'), 'resources')
    if not isinstance(plan, dict) or not isinstance(plan.get('data'), list) or not isinstance(resurse, list):
        raise EroareGantt('planul din raspunsul Gantt-ului are alta forma decat cea asteptata')
    email_l = (email or '').strip().lower()
    eu = None
    for r in resurse:
        if (isinstance(r, dict) and r.get('id') not in (None, '') and email_l
                and isinstance(r.get('email'), str) and r['email'].strip().lower() == email_l):
            eu = str(r['id'])
    brut = {str(a['id']): a for a in plan['data'] if isinstance(a, dict) and a.get('id') not in (None, '')}
    return brut, eu


def _zile_inclusiv(interval):
    return (_data(interval[1]) - _data(interval[0])).days + 1


def _cu_date(activitate, interval, start_vechi):
    """Copia activitatii brute cu DOAR datele schimbate: start_date, end_date (capatul inclusiv ca
    `23:59`), duration (zile calendaristice, inclusiv) si constraint_date, dar numai daca era egala cu
    vechiul start. Restul obiectului ramane identic."""
    nou = dict(activitate)
    nou['start_date'] = interval[0] + ' 00:00'
    nou['end_date'] = interval[1] + ' 23:59'
    nou['duration'] = _zile_inclusiv(interval)
    cd = activitate.get('constraint_date')
    if isinstance(cd, str) and cd[:10] == start_vechi:
        nou['constraint_date'] = interval[0] + cd[10:]
    return nou


def _scor(srp, dash):
    """Cat de aproape sunt doua intervale: suprapunerea (mai mare = mai bine), apoi distanta."""
    suprapunere = _zile(max(srp[0], dash[0]), min(srp[1], dash[1])) + 1
    if suprapunere > 0:
        return (0, -suprapunere, abs(_zile(srp[0], dash[0])))
    return (1, -suprapunere, abs(_zile(srp[0], dash[0])))


def _etapa_noua(brut, radacina_id, eu, interval, eticheta, acum):
    """O etapa noua sub `radacina_id`: campurile unei etape existente (a lui Ion, altfel orice etapa,
    altfel un set minim), cu id numeric nou (ms, ca ale aplicatiei) care nu exista in plan."""
    copii = [a for a in brut.values() if _id_parinte(a.get('parent')) == radacina_id]
    sablon = next((a for a in copii if eu in _resurse_activitate(a.get('resource'))), None)
    sablon = sablon or (copii[0] if copii else next((a for a in brut.values() if _id_parinte(a.get('parent'))), {}))
    nou = dict(sablon)
    nou.pop('state', None)
    n = int(acum.timestamp() * 1000)
    while str(n) in brut:
        n += 1
    nou.update({
        'id': n, 'parent': radacina_id, 'text': _text(eticheta) or 'PIF',
        'start_date': interval[0] + ' 00:00', 'end_date': interval[1] + ' 23:59',
        'duration': _zile_inclusiv(interval), 'progress': 0, 'resource': [eu], 'type': 'task',
        'open': True, 'constraint_type': 'asap', 'constraint_date': interval[0] + ' 00:00',
        'description': '',
    })
    return nou


def _citeste_perioada(impl_id):
    """(perioada, proiect, ocupate, alte_intervale) din baza, sau None daca perioada nu exista.
    `ocupate`: etapele deja legate de ALTE perioade; `alte_intervale`: intervalele celorlalte
    perioade ale proiectului."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, proiect_id, data_start, data_sfarsit, eticheta, srp_activitate_id "
                    "FROM implementari WHERE id = ?", (impl_id,))
        perioada = cur.fetchone()
        if perioada is None:
            return None
        perioada = dict(perioada)
        cur.execute("SELECT id, nume, cod_proiect, status FROM proiecte WHERE id = ?", (perioada['proiect_id'],))
        proiect = cur.fetchone()
        cur.execute("SELECT id, data_start, data_sfarsit, srp_activitate_id FROM implementari "
                    "WHERE proiect_id = ? AND id != ?", (perioada['proiect_id'], impl_id))
        alte = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT srp_activitate_id FROM implementari WHERE id != ? AND srp_activitate_id IS NOT NULL",
                    (impl_id,))
        ocupate = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    intervale = [i for i in (interval_perioada(a['data_start'], a['data_sfarsit']) for a in alte) if i]
    return perioada, (dict(proiect) if proiect else None), ocupate, intervale


def _salveaza_legatura(impl_id, activitate_id):
    conn = get_db()
    try:
        conn.execute('UPDATE implementari SET srp_activitate_id = ? WHERE id = ?', (activitate_id, impl_id))
        conn.commit()
    finally:
        conn.close()


def _sincronizeaza(impl_id, vechi, trimite, activitate_ales):
    sursa = citeste_sursa()
    if sursa is None:
        return _rez('ignorat', 'fara_sursa')
    citit = _citeste_perioada(impl_id)
    if citit is None:
        return _rez('ignorat', 'perioada_inexistenta')
    perioada, proiect, ocupate, alte_intervale = citit
    nou = interval_perioada(perioada['data_start'], perioada['data_sfarsit'])
    if nou is None:
        return _rez('ignorat', 'fara_data')
    if not trimite and vechi is not None and vechi == nou:
        return _rez('ignorat', 'date_neschimbate')
    cod_p = analiza_cod((proiect or {}).get('cod_proiect'))
    if cod_p is None:
        return _rez('ignorat', 'fara_cod')

    if not _ia_scrierea():
        return _rez('eroare', 'sincronizare_in_curs')
    try:
        raspuns = _descarca(sursa['planId'], sursa['secret'])
        brut, eu = _plan_brut(raspuns, sursa['email'])
        _scrie_atomic(FISIER_PLAN, normalizeaza(raspuns, sursa['email']))
        radacini = sorted(aid for aid, a in brut.items()
                          if _id_parinte(a.get('parent')) is None
                          and coduri_potrivite(analiza_cod(_text(a.get('text'))), cod_p))
        if not radacini:
            return _rez('ignorat', 'fara_radacina')
        if eu is None:
            return _rez('protejat', 'email_necunoscut')

        def ale_lui(aid):
            return eu in _resurse_activitate(brut[aid].get('resource'))
        parinti = {_id_parinte(a.get('parent')) for a in brut.values()}
        frunze = [aid for aid in sorted(brut)
                  if aid not in parinti and _radacina_brut(brut, aid) in radacini and ale_lui(aid)
                  and aid not in ocupate and _interval_brut(brut[aid]) is not None]

        # Tinta: etapa aleasa de Ion, legatura salvata, frunza cu intervalul VECHI, frunza cu intervalul
        # NOU (deja sincron: ex. dupa „Use SRP dates"), la „trimite" fara nimic dintre acestea cea mai
        # apropiata frunza libera; altfel etapa noua.
        tinta = perioada['srp_activitate_id']
        if tinta is not None and (tinta not in brut or _radacina_brut(brut, tinta) not in radacini):
            tinta = None
        if activitate_ales is not None:                              # alegerea lui Ion bate legatura salvata
            if activitate_ales not in brut or _radacina_brut(brut, activitate_ales) not in radacini:
                return _rez('protejat', 'etapa_necunoscuta')
            tinta = activitate_ales
        if tinta is None and vechi is not None:
            tinta = next((a for a in frunze if _interval_brut(brut[a]) == vechi), None)
        if tinta is None:
            tinta = next((a for a in frunze if _interval_brut(brut[a]) == nou), None)
        if tinta is None and trimite and activitate_ales is None:
            libere = [a for a in frunze if _interval_brut(brut[a]) not in alte_intervale]
            if libere:
                tinta = min(libere, key=lambda a: (_scor(_interval_brut(brut[a]), nou), a))

        if tinta is not None:
            if not ale_lui(tinta):                                   # protectia: doar etapele lui Ion
                return _rez('protejat', 'ion_nu_e_pe_etapa', tinta)
            curent = _interval_brut(brut[tinta])
            if curent == nou:
                _salveaza_legatura(impl_id, tinta)
                return _rez('ok', 'deja_sincron', tinta)
            if not trimite and vechi is not None and curent != vechi:
                return _rez('conflict', 'etapa_mutata_in_gantt', tinta)
            obiect = _cu_date(brut[tinta], nou, curent[0] if curent else None)
            radacina_id = _radacina_brut(brut, tinta)
            motiv = 'sincronizat'
        else:
            radacina_id = next((r for r in radacini if ale_lui(r)), None)
            if radacina_id is None:
                return _rez('protejat', 'ion_nu_e_pe_radacina')
            obiect = _etapa_noua(brut, radacina_id, eu, nou, perioada['eticheta'], _acum())
            motiv = 'etapa_noua'

        scrieri = []
        radacina = brut[radacina_id]
        r_int = _interval_brut(radacina)
        if r_int is not None and ale_lui(radacina_id) and (nou[0] < r_int[0] or nou[1] > r_int[1]):
            scrieri.append(_cu_date(radacina, (min(r_int[0], nou[0]), max(r_int[1], nou[1])), r_int[0]))
        scrieri.append(obiect)                                       # radacina intai, apoi etapa
        for activitate in scrieri:
            _trimite_activitate(sursa['planId'], sursa['secret'], activitate)

        raspuns = _descarca(sursa['planId'], sursa['secret'])
        brut2, _ = _plan_brut(raspuns, sursa['email'])
        _scrie_atomic(FISIER_PLAN, normalizeaza(raspuns, sursa['email']))
        aid = str(obiect['id'])
        if aid not in brut2 or _interval_brut(brut2[aid]) != nou:
            return _rez('eroare', 'verificare_esuata', aid)
        _salveaza_legatura(impl_id, aid)
        return _rez('ok', motiv, aid)
    finally:
        _elibereaza_scrierea()


def sincronizeaza(impl_id, vechi=None, trimite=False, activitate_ales=None):
    """Aduce in Gantt perioada `impl_id` (datele ei de acum din baza). Nu ridica niciodata: scrierea
    din dashboard e deja facuta si ramane valabila oricum. `vechi`: intervalul perioadei dinaintea
    modificarii (start, end) sau None (perioada noua). `trimite`: decizia explicita a lui Ion
    („Send Torqa dates to SRP"): nu se verifica conflictul, iar fara tinta sigura se alege cea mai
    apropiata etapa libera. Intoarce cheia `srp`: {status, motiv, activitate_id}."""
    try:
        rez = _sincronizeaza(impl_id, vechi, trimite, activitate_ales)
    except EroareGantt as e:
        logger.warning('Echipa: sincronizarea cu Gantt-ul a esuat [cod=gantt_indisponibil]: %s', e)
        return _rez('eroare', 'gantt_indisponibil')
    except Exception as e:
        logger.warning('Echipa: sincronizarea cu Gantt-ul a esuat [cod=eroare_interna]: %s', type(e).__name__)
        return _rez('eroare', 'eroare_interna')
    if rez['status'] in ('protejat', 'conflict', 'eroare'):
        logger.warning('Echipa: sincronizare nefacuta [cod=%s] status=%s', rez['motiv'], rez['status'])
    return rez


# ------------------------------------------------------------------------------ rute

def _mascat(plan_id):
    return '****' + plan_id[-4:]


def _numele_meu(snapshot):
    if not snapshot or snapshot.get('eu') is None:
        return None
    for r in snapshot['resurse']:
        if r.get('id') == snapshot['eu']:
            return r.get('nume') or None
    return None


@echipa_bp.route('/api/echipa', methods=['GET'])
@login_required
def get_echipa():
    """Planul echipei din Gantt (sesiune, `PIF_API_TOKEN` sau `PIF_DEVICE_TOKEN`). Corpul e
    `null` fara sursa si fara snapshot."""
    return jsonify(echipa_completa())


@echipa_bp.route('/api/echipa/trimite', methods=['POST'])
@login_required
def post_trimite():
    """„Send Torqa dates to SRP": trimite in Gantt datele perioadei `implementare_id`, fara sa
    verifice conflictul (e decizia explicita a lui Ion); protectia (doar etapele lui Ion) ramane.
    Deschisa si tokenului de dispozitiv. `activitate_id` (optional) alege etapa cand Torqa stie
    perechea din avertizare. Raspuns: {srp: {status, motiv, activitate_id}}; 404 la o perioada
    necunoscuta, 502 cand Gantt-ul nu a putut fi scris. Aceeasi cerere de doua ori: a doua da
    `ok` / `deja_sincron`."""
    corp = request.get_json(silent=True)
    if not isinstance(corp, dict):
        return jsonify({'error': 'Body JSON invalid sau lipsa'}), 400
    impl_id, activitate = corp.get('implementare_id'), corp.get('activitate_id')
    if not isinstance(impl_id, str) or not 0 < len(impl_id) <= 100:
        return jsonify({'error': 'implementare_id: trebuie sa fie text de 1-100 de caractere'}), 400
    if activitate is not None and (not isinstance(activitate, str) or not 0 < len(activitate) <= 64):
        return jsonify({'error': 'activitate_id: trebuie sa fie text de 1-64 de caractere sau lipsa'}), 400
    if _citeste_perioada(impl_id) is None:
        return jsonify({'error': 'Perioada inexistenta'}), 404
    rez = sincronizeaza(impl_id, trimite=True, activitate_ales=activitate)
    cod = 200
    if rez['status'] == 'eroare':
        cod = 409 if rez['motiv'] == 'sincronizare_in_curs' else 502
    return jsonify({'srp': rez}), cod


@echipa_bp.route('/api/echipa/sursa', methods=['GET'])
@login_required
def get_sursa():
    """{configurat, planId mascat, eu}. Secretul nu iese niciodata."""
    sursa = citeste_sursa()
    if sursa is None:
        return jsonify({'configurat': False, 'planId': None, 'eu': None})
    return jsonify({'configurat': True, 'planId': _mascat(sursa['planId']), 'eu': _numele_meu(citeste_snapshot())})


@echipa_bp.route('/api/echipa/sursa', methods=['PUT'])
@login_required
def put_sursa():
    """Seteaza sursa (planId, secret, email) dupa o citire de proba. Doar sesiune sau
    `PIF_API_TOKEN` (`/api/echipa/sursa` e in `DEVICE_TOKEN_DENIED`). La orice abatere: 400 cu
    motivul si sursa veche ramane. Aceeasi cerere de doua ori lasa aceeasi sursa.
    Raspuns: {ok, configurat, planId (mascat), eu, activitati}."""
    if request.content_length is not None and request.content_length > MAX_CORP:
        return jsonify({'error': 'corp prea mare'}), 413
    brut = request.stream.read(MAX_CORP + 1)
    if len(brut) > MAX_CORP:
        return jsonify({'error': 'corp prea mare'}), 413
    try:
        corp = json.loads(brut.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return jsonify({'error': 'Body JSON invalid sau lipsa'}), 400
    if not isinstance(corp, dict):
        return jsonify({'error': 'corpul trebuie sa fie un obiect JSON'}), 400
    plan_id, secret, email = corp.get('planId'), corp.get('secret'), corp.get('email')
    if not isinstance(plan_id, str) or not _RE_UUID.fullmatch(plan_id):
        return jsonify({'error': 'planId: trebuie sa fie un UUID'}), 400
    if not isinstance(secret, str) or not _RE_UUID.fullmatch(secret):
        return jsonify({'error': 'secret: trebuie sa fie un UUID'}), 400
    if not isinstance(email, str) or len(email) > 254 or not _RE_EMAIL.fullmatch(email.strip()):
        return jsonify({'error': 'email: adresa nu e valida'}), 400
    plan_id, secret, email = plan_id.lower(), secret.lower(), email.strip()

    try:
        snapshot = normalizeaza(_descarca(plan_id, secret), email)
    except EroareGantt as e:
        logger.warning('Echipa: sursa respinsa [cod=gantt_indisponibil]: %s', e)
        return jsonify({'error': 'Gantt-ul nu a putut fi citit: %s' % e}), 400
    if snapshot['eu'] is None:
        logger.warning('Echipa: sursa respinsa [cod=email_necunoscut]')
        return jsonify({'error': 'email-ul nu e printre resursele planului'}), 400
    try:
        _scrie_atomic(FISIER_SURSA, {'planId': plan_id, 'secret': secret, 'email': email}, privat=True)
        _scrie_atomic(FISIER_PLAN, snapshot)
    except OSError:
        logger.exception('Echipa: scrierea pe disc a esuat [cod=disc]')
        return jsonify({'error': 'Eroare pe disc la salvarea sursei.'}), 500
    _elibereaza()
    return jsonify({'ok': True, 'configurat': True, 'planId': _mascat(plan_id),
                    'eu': _numele_meu(snapshot), 'activitati': len(snapshot['activitati'])})

# Materiale Blueprint
# Centralizatorul de materiale al proiectelor deschise: ce e comandat (CT-uri, cu termenele
# confirmate din BC), ce e inca necomandat, listele de materiale (LM) din E100, firul de mailuri
# si alertele. Datele le aduna colectorul de pe PC-ul de job (Knowledge `tools/`, L-V la 08:00 si 13:00)
# si le urca la `PUT /api/materiale`; Torqa le citeste la `GET /api/materiale`. Alertele si taskurile lor
# le calculeaza serverul la PUT cand colectorul trimite `sursa.alerte = "server"` (blueprints/materiale_alerte.py).
#
# DE CE UN FISIER SI NU O TABELA (tiparul `blueprints/outlook.py`, decizia 2026-10-19): fiecare
# rulare trimite snapshot-ul complet, care se reface singur a doua zi; fara schema, fara migrare,
# fara backup. Pe disc stau doua fisiere, scrise atomic:
#   uploads/materiale/snapshot.json       ultima colectare
#   uploads/materiale/snapshot.prev.json  ultima colectare dintr-o zi ANTERIOARA
# Rotatia se face doar cand snapshot-ul nou e din alta zi decat cel curent: o rulare repetata in
# aceeasi zi il inlocuieste doar pe cel curent, deci marcajele raman „fata de ultima zi colectata".
#
# Marcajele (nou, mutat, cantitate, stare, disparut) le calculeaza serverul la citire, ca Torqa doar
# sa le afiseze. Decizia: docs/decizii/2026-11-06-materiale.md.
#
# Bifele manuale (2026-11-25): Ion bifeaza in Torqa ca un articol „a ajuns la destinatie" sau e „livrat", peste
# ce spune colectorul (`PUT /api/materiale/bifa`). Ele NU stau in snapshot (care se inlocuieste la fiecare colectare),
# ci in `app_settings`, cheia `materiale_bife` ({proiect_id: {cod_bc: {stare, la}}}), ca sa intre in backup si sa
# supravietuiasca colectarii urmatoare. `GET /api/materiale` le aplica pe randurile din `proiecte[].materiale`
# (`stare`, `stare_colector`, `intarziat`, `rezumat`); alertele de livrare calculate la PUT le respecta
# (blueprints/materiale_alerte.py). Decizia: docs/decizii/2026-11-25-materiale-bifa.md.
#
# Colectorul inca evolueaza (LM-urile din E100 abia urmeaza), deci validarea e toleranta: campurile
# din contract au tipul verificat, cele in plus se pastreaza cum vin.

import json
import logging
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from blueprints import materiale_alerte
from blueprints.outlook import _data, _data_ora
from database import get_db
from utils import login_required, get_app_setting, UPLOAD_FOLDER

logger = logging.getLogger('pif_dashboard')

materiale_bp = Blueprint('materiale', __name__)

DIR_MATERIALE = os.path.join(UPLOAD_FOLDER, 'materiale')
CURENT = 'snapshot.json'
ANTERIOR = 'snapshot.prev.json'

MAX_CORP = 2 * 1024 * 1024
MAX_PROIECTE = 200
MAX_RANDURI = 5000          # pe lista, pe proiect
MAX_TEXT = 1000

# Termene care in BC nu sunt date reale (Ion, 2026-11-06: „pune data bruta si cu atentionare ca
# este neregula"). Data ramane cum vine; randul primeste `termen_neregulat: true`.
TERMENE_NEREGULATE = frozenset(('1900-01-01', '2030-12-31'))

# O colectare e „veche" cand a trecut mai mult de o zi lucratoare (L-V, fara sarbatori) de la ea,
# plus o marja pentru o rulare intarziata (PC pornit mai tarziu, Outlook lent).
MARJA_VECHI = timedelta(hours=2)

# Bifele manuale: cheia din `app_settings`, nivelul fiecarei stari fata de colector (livrat > la_destinatie > restul)
# si starile colectorului care inca asteapta o livrare (`$InCurs` din tools/materiale-colector.ps1).
CHEIE_BIFE = 'materiale_bife'
NIVEL_BIFA = materiale_alerte.NIVEL_BIFA
STARI_IN_CURS = ('in_tranzit', 'confirmat', 'comandat', 'din_stoc', 'necomandat')
MAX_CORP_BIFA = 16 * 1024

TIPURI_MAIL = ('comanda_mail', 'stare_lm', 'livrare', 'alt')
_RE_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
_RE_TIP = re.compile(r'[a-z_]{1,40}')
_RE_ENTRY_ID = re.compile(r'[0-9A-Fa-f]{20,1024}')
# Data unui mail: YYYY-MM-DDTHH:MM, cu secunde si offset optionale (ora locala de pe PC-ul de job).
_RE_DATA_MAIL = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2})?')


class EroareCorp(ValueError):
    """Corpul nu respecta contractul; mesajul spune calea campului."""


# --------------------------------------------------------------------------- validarea

def _text(obj, camp, cale, obligatoriu=False):
    v = obj.get(camp)
    if v is None and not obligatoriu:
        return
    if not isinstance(v, str):
        raise EroareCorp('%s.%s: trebuie sa fie text' % (cale, camp))
    if len(v) > MAX_TEXT:
        raise EroareCorp('%s.%s: maximum %d de caractere' % (cale, camp, MAX_TEXT))
    if obligatoriu and not v.strip():
        raise EroareCorp('%s.%s: nu poate fi gol' % (cale, camp))


def _numar(obj, camp, cale, obligatoriu=False):
    v = obj.get(camp)
    if v is None and not obligatoriu:
        return
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise EroareCorp('%s.%s: trebuie sa fie numar' % (cale, camp))


def _intreg_sau_null(obj, camp, cale):
    v = obj.get(camp)
    if v is not None and (isinstance(v, bool) or not isinstance(v, int)):
        raise EroareCorp('%s.%s: trebuie sa fie numar intreg sau null' % (cale, camp))


def _data_sau_null(obj, camp, cale):
    v = obj.get(camp)
    if v is not None and _data(v) is None:
        raise EroareCorp('%s.%s: trebuie sa fie YYYY-MM-DD sau null' % (cale, camp))


def _lista(obj, camp, cale, maxim=MAX_RANDURI):
    """Lista din `camp`, sau [] cand lipseste (colectorul poate inca sa nu trimita o sectiune)."""
    v = obj.get(camp)
    if v is None:
        return []
    if not isinstance(v, list):
        raise EroareCorp('%s.%s: trebuie sa fie o lista' % (cale, camp))
    if len(v) > maxim:
        raise EroareCorp('%s.%s: maximum %d de elemente' % (cale, camp, maxim))
    for ix, el in enumerate(v):
        if not isinstance(el, dict):
            raise EroareCorp('%s.%s[%d]: trebuie sa fie obiect' % (cale, camp, ix))
    return v


def _lm(r, cale):
    if isinstance(r.get('nr'), bool) or not isinstance(r.get('nr'), int) or r['nr'] < 0:
        raise EroareCorp('%s.nr: numarul LM-ului, intreg >= 0' % cale)
    _text(r, 'stare', cale)
    _data_sau_null(r, 'data_stare', cale)
    _data_sau_null(r, 'creat', cale)


def _termen(r, cale):
    _text(r, 'ct', cale, obligatoriu=True)
    _text(r, 'cod_articol', cale, obligatoriu=True)
    _data_sau_null(r, 'termen_confirmat', cale)
    _numar(r, 'cantitate_restanta', cale, obligatoriu=True)
    _intreg_sau_null(r, 'lm', cale)
    for camp in ('cod_proiect_bc', 'descriere', 'um', 'furnizor', 'cod_furnizor', 'rezervat_din',
                 'locatie', 'rezervat_pentru', 'automatic_shipping'):
        _text(r, camp, cale)


def _necomandat(r, cale):
    _text(r, 'ct', cale, obligatoriu=True)
    _text(r, 'cod_articol', cale, obligatoriu=True)
    _numar(r, 'cantitate_necomandata', cale, obligatoriu=True)
    _data_sau_null(r, 'data_creare_ct', cale)
    _intreg_sau_null(r, 'lm', cale)
    for camp in ('cod_proiect_bc', 'descriere', 'um', 'furnizor_implicit', 'producator', 'achizitor',
                 'rezervat_din', 'rezervat_pentru', 'automatic_shipping'):
        _text(r, camp, cale)


def _mail(r, cale):
    v = r.get('data')
    if not isinstance(v, str) or not _RE_DATA_MAIL.fullmatch(v):
        raise EroareCorp('%s.data: YYYY-MM-DDTHH:MM (secunde si offset optionale)' % cale)
    _text(r, 'subiect', cale, obligatoriu=True)
    _text(r, 'de_la', cale)
    if r.get('tip') not in TIPURI_MAIL:
        raise EroareCorp('%s.tip: una din %s' % (cale, '|'.join(TIPURI_MAIL)))
    eid = r.get('entry_id')
    if eid not in (None, '') and (not isinstance(eid, str) or not _RE_ENTRY_ID.fullmatch(eid)):
        raise EroareCorp('%s.entry_id: EntryID-ul Outlook (20-1024 de caractere hex), gol sau null' % cale)
    ct = r.get('ct')
    if ct is not None and (not isinstance(ct, list) or not all(isinstance(x, str) for x in ct)):
        raise EroareCorp('%s.ct: lista de texte' % cale)
    _intreg_sau_null(r, 'lm', cale)


def _alerta(r, cale):
    if not isinstance(r.get('tip'), str) or not _RE_TIP.fullmatch(r['tip']):
        raise EroareCorp('%s.tip: 1-40 de caractere din a-z si _' % cale)
    _text(r, 'text', cale, obligatoriu=True)
    _data_sau_null(r, 'din', cale)
    _text(r, 'ref', cale)


SECTIUNI = (('lm', _lm), ('termene', _termen), ('necomandate', _necomandat),
            ('mailuri', _mail), ('alerte', _alerta))


def valideaza_snapshot(corp):
    """Corpul JSON -> snapshot de scris (campurile in plus se pastreaza, sectiunile lipsa devin
    []), sau EroareCorp cu calea campului. Nu scrie nimic."""
    if not isinstance(corp, dict):
        raise EroareCorp('corpul trebuie sa fie un obiect JSON')
    if _data_ora(corp.get('generat')) is None:
        raise EroareCorp('generat: data si ora ISO cu offset, ex. 2026-11-06T08:02:11+02:00')
    sursa = corp.get('sursa')
    if sursa is not None and (not isinstance(sursa, dict)
                              or not all(isinstance(v, str) and len(v) <= MAX_TEXT for v in sursa.values())):
        raise EroareCorp('sursa: obiect cu valori text')
    proiecte = corp.get('proiecte')
    if not isinstance(proiecte, list):
        raise EroareCorp('proiecte: trebuie sa fie o lista')
    if len(proiecte) > MAX_PROIECTE:
        raise EroareCorp('proiecte: maximum %d' % MAX_PROIECTE)
    vazute = set()
    iesire = []
    for ix, p in enumerate(proiecte):
        cale = 'proiecte[%d]' % ix
        if not isinstance(p, dict):
            raise EroareCorp('%s: trebuie sa fie obiect' % cale)
        pid = p.get('proiect_id')
        if not isinstance(pid, str) or not _RE_ID.fullmatch(pid):
            raise EroareCorp('%s.proiect_id: id-ul din /api/proiecte (1-64 de caractere A-Z a-z 0-9 _ -)' % cale)
        if pid in vazute:
            raise EroareCorp('%s.proiect_id: duplicat in snapshot' % cale)
        vazute.add(pid)
        _text(p, 'cod_proiect', cale, obligatoriu=True)
        proiect = dict(p)
        for sectiune, valideaza in SECTIUNI:
            randuri = _lista(p, sectiune, cale)
            for jx, r in enumerate(randuri):
                valideaza(r, '%s.%s[%d]' % (cale, sectiune, jx))
            proiect[sectiune] = randuri
        iesire.append(proiect)
    return {'generat': corp['generat'], 'sursa': sursa or {}, 'proiecte': iesire}


# --------------------------------------------------------------------------- discul

def _cale(nume):
    return os.path.join(DIR_MATERIALE, nume)


def _scrie_atomic(nume, octeti):
    """Fisier alaturat, fsync, apoi `os.replace`: un cititor vede ori fisierul vechi, ori pe cel nou."""
    os.makedirs(DIR_MATERIALE, exist_ok=True)
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


def _citeste(nume):
    """(snapshot, octeti) de pe disc, sau (None, None) daca lipseste ori nu se poate citi. Un
    fisier stricat nu strica GET-ul: se logheaza, iar Torqa vede „fara colectare"."""
    try:
        with open(_cale(nume), 'rb') as fh:
            octeti = fh.read()
        snapshot = json.loads(octeti.decode('utf-8'))
    except FileNotFoundError:
        return None, None
    except (OSError, ValueError):                # ValueError acopera JSONDecodeError si UnicodeDecodeError
        logger.warning('Materiale: %s nu se poate citi; se ignora', nume, exc_info=True)
        return None, None
    if (not isinstance(snapshot, dict) or not isinstance(snapshot.get('proiecte'), list)
            or _data_ora(snapshot.get('generat')) is None):
        logger.warning('Materiale: %s are alta forma decat cea scrisa; se ignora', nume)
        return None, None
    return snapshot, octeti


# --------------------------------------------------------------------------- marcajele

def _cheie_termen(r):
    return (r.get('ct'), r.get('cod_articol'), r.get('rezervat_din'))


def _cheie_necomandat(r):
    return (r.get('ct'), r.get('cod_articol'))


def _pe_chei(randuri, cheie, ordine):
    """{(cheie..., n): rand}. Randurile cu aceeasi cheie (acelasi articol pe acelasi CT, de mai
    multe ori) se numara in ordinea data de `ordine`, ca perechile dintre doua rulari sa fie stabile."""
    grupuri = {}
    for r in randuri:
        grupuri.setdefault(cheie(r), []).append(r)
    iesire = {}
    for k, grup in grupuri.items():
        for n, r in enumerate(sorted(grup, key=ordine)):
            iesire[k + (n,)] = r
    return iesire


def _ordine_termen(r):
    return (str(r.get('cantitate_restanta')), r.get('termen_confirmat') or '')


def _ordine_necomandat(r):
    return (str(r.get('cantitate_necomandata')),)


def _marcheaza(curente, anterioare, cheie, ordine, compara):
    """Pune `schimbare` pe fiecare rand curent si intoarce randurile anterioare care au disparut.
    `compara(rand, anterior)` intoarce un dict cu marcajul si valorile vechi, sau {}."""
    acum = _pe_chei(curente, cheie, ordine)
    inainte = _pe_chei(anterioare, cheie, ordine)
    for k, r in acum.items():
        vechi = inainte.get(k)
        if vechi is None:
            r['schimbare'] = 'nou'
        else:
            r.update(compara(r, vechi) or {'schimbare': None})
    return [dict(v) for k, v in inainte.items() if k not in acum]


def _compara_termen(r, vechi):
    if r.get('termen_confirmat') != vechi.get('termen_confirmat'):
        return {'schimbare': 'mutat', 'termen_anterior': vechi.get('termen_confirmat')}
    if r.get('cantitate_restanta') != vechi.get('cantitate_restanta'):
        return {'schimbare': 'cantitate', 'cantitate_anterioara': vechi.get('cantitate_restanta')}
    return {}


def _compara_necomandat(r, vechi):
    if r.get('cantitate_necomandata') != vechi.get('cantitate_necomandata'):
        return {'schimbare': 'cantitate', 'cantitate_anterioara': vechi.get('cantitate_necomandata')}
    return {}


def _compara_lm(r, vechi):
    if r.get('stare') != vechi.get('stare'):
        return {'schimbare': 'stare', 'stare_anterioara': vechi.get('stare')}
    return {}


def _cheie_mail(r):
    return (r.get('entry_id') or '', '' if r.get('entry_id') else r.get('data'),
            '' if r.get('entry_id') else r.get('subiect'))


def _proiect_cu_marcaje(p, anterior):
    """Copia proiectului pentru GET. Fara proiect in snapshot-ul anterior (proiect nou sau prima
    colectare), randurile nu primesc marcaj: totul ar fi „nou", adica zgomot."""
    p = json.loads(json.dumps(p))                # copie adanca: snapshot-ul citit nu se atinge
    for r in p['termene']:
        r['termen_neregulat'] = r.get('termen_confirmat') in TERMENE_NEREGULATE
    if anterior is None:
        for sectiune, _ in SECTIUNI:
            for r in p[sectiune]:
                r['schimbare'] = None
        p['disparute'] = {'lm': [], 'termene': [], 'necomandate': []}
        return p
    prev = {s: anterior.get(s) if isinstance(anterior.get(s), list) else [] for s, _ in SECTIUNI}
    disparute = {
        'termene': _marcheaza(p['termene'], prev['termene'], _cheie_termen, _ordine_termen, _compara_termen),
        'necomandate': _marcheaza(p['necomandate'], prev['necomandate'], _cheie_necomandat,
                                  _ordine_necomandat, _compara_necomandat),
        'lm': _marcheaza(p['lm'], prev['lm'], lambda r: (r.get('nr'),), lambda r: 0, _compara_lm),
    }
    for r in disparute['termene']:
        r['termen_neregulat'] = r.get('termen_confirmat') in TERMENE_NEREGULATE
    # Mailurile si alertele: doar „nou". Un mail iesit din fereastra colectorului sau o alerta
    # rezolvata nu sunt vesti de afisat.
    mailuri_vechi = {_cheie_mail(m) for m in prev['mailuri']}
    for m in p['mailuri']:
        m['schimbare'] = None if _cheie_mail(m) in mailuri_vechi else 'nou'
    alerte_vechi = {(a.get('tip'), a.get('ref')) for a in prev['alerte']}
    for a in p['alerte']:
        a['schimbare'] = None if (a.get('tip'), a.get('ref')) in alerte_vechi else 'nou'
    p['disparute'] = disparute
    return p


def _adauga_zi_lucratoare(moment):
    zi = moment + timedelta(days=1)
    while zi.weekday() >= 5:                      # sambata, duminica
        zi += timedelta(days=1)
    return zi


def _acum():
    return datetime.now(timezone.utc)


def e_vechi(generat, acum=None):
    """True cand de la colectarea `generat` (ISO cu offset) a trecut mai mult de o zi lucratoare,
    plus MARJA_VECHI. Vineri 08:00 ramane proaspata pana luni 10:00."""
    moment = _data_ora(generat)
    if moment is None:
        return True
    return (acum or _acum()) > _adauga_zi_lucratoare(moment) + MARJA_VECHI


def _date_proiecte(ids):
    """{id: {nume, client, status}} din baza, doar citire. O eroare de baza nu strica GET-ul."""
    if not ids:
        return {}
    try:
        conn = get_db()
        try:
            semne = ','.join('?' * len(ids))
            rows = conn.execute('SELECT id, nume, client, status FROM proiecte WHERE id IN (%s)' % semne,
                                list(ids)).fetchall()
        finally:
            conn.close()
    except Exception:
        logger.exception('Materiale: proiectele nu se pot citi din baza')
        return {}
    return {r['id']: {'nume': r['nume'], 'client': r['client'], 'status': r['status']} for r in rows}


# --------------------------------------------------------------------------- bifele manuale

def _parseaza_bife(brut):
    """{proiect_id: {cod_bc: {stare, la}}} din textul din `app_settings`; {} la lipsa sau text stricat (o valoare
    stricata nu strica GET-ul si nu blocheaza o bifa noua: se logheaza si se rescrie la urmatoarea bifa)."""
    if not brut:
        return {}
    try:
        bife = json.loads(brut)
    except ValueError:
        logger.warning('Materiale: %s din app_settings nu e JSON; se ignora', CHEIE_BIFE)
        return {}
    return bife if isinstance(bife, dict) else {}


def citeste_bife(conn=None):
    """Bifele din `app_settings` (cu `conn` deschis de apelant, altfel pe conexiunea ei). O eroare de baza nu strica
    GET-ul si nici PUT-ul colectorului: se logheaza si se lucreaza fara bife."""
    try:
        if conn is None:
            return _parseaza_bife(get_app_setting(CHEIE_BIFE))
        rand = conn.execute('SELECT value FROM app_settings WHERE key = ?', (CHEIE_BIFE,)).fetchone()
        return _parseaza_bife(rand['value'] if rand else None)
    except sqlite3.Error:
        logger.exception('Materiale: bifele nu se pot citi din baza')
        return {}


def _bifa_valida(bife_proiect, cod_bc):
    """{stare, la} pentru `cod_bc`, sau None cand lipseste ori n-are forma scrisa de PUT-ul bifei."""
    b = bife_proiect.get(cod_bc) if isinstance(bife_proiect, dict) and isinstance(cod_bc, str) else None
    if (isinstance(b, dict) and isinstance(b.get('stare'), str) and b['stare'] in NIVEL_BIFA
            and isinstance(b.get('la'), str)):
        return {'stare': b['stare'], 'la': b['la']}
    return None


def _nivel(stare):
    return NIVEL_BIFA.get(stare, 0) if isinstance(stare, str) else 0


def _scade(rezumat, camp, cheie=None):
    """Scade 1 din rezumat[camp] (sau din rezumat[camp][cheie]); un contor ajuns la 0 pe stare dispare, ca la colector."""
    tinta = rezumat.get(camp)
    if cheie is None:
        if isinstance(tinta, int) and not isinstance(tinta, bool):
            rezumat[camp] = max(0, tinta - 1)
    elif isinstance(tinta, dict) and isinstance(tinta.get(cheie), int):
        tinta[cheie] -= 1
        if tinta[cheie] <= 0:
            del tinta[cheie]


def aplica_bife(p, bife_proiect):
    """Aplica pe loc (pe copia proiectului pentru GET) bifele manuale. Fiecare rand cu bifa valida primeste `bifa:
    {stare, la}`. Cand nivelul bifei e peste starea colectorului (livrat > la_destinatie > orice altceva), randul
    primeste `stare` = bifa, `stare_colector` = starea trimisa de colector si `intarziat` = false, iar `rezumat`
    se ajusteaza (pe_stare, intarziate, dupa_start/aproape_start, urmatoarea, ultima_asteptata). Colectorul a
    ajuns deja la nivelul bifei sau peste: `stare` ramane a lui, `bifa` apare tot. Bifele pe randuri care nu mai
    sunt in snapshot nu se ating (raman stocate, nu se arata)."""
    materiale = p.get('materiale')
    if not bife_proiect or not isinstance(materiale, list):
        return
    rez = p.get('rezumat') if isinstance(p.get('rezumat'), dict) else None
    schimbate = set()
    for m in materiale:
        if not isinstance(m, dict):
            continue
        bifa = _bifa_valida(bife_proiect, m.get('cod_bc'))
        if bifa is None:
            continue
        m['bifa'] = bifa
        veche = m.get('stare')
        if _nivel(bifa['stare']) <= _nivel(veche):
            continue
        m['stare_colector'] = veche
        m['stare'] = bifa['stare']
        era_intarziat, era_start = bool(m.get('intarziat')), m.get('fata_de_start')
        m['intarziat'] = False
        if 'fata_de_start' in m:
            m['fata_de_start'] = None
        schimbate.add(m['cod_bc'])
        if rez is None:
            continue
        pe = rez.get('pe_stare')
        if isinstance(pe, dict):
            if isinstance(veche, str):
                _scade(rez, 'pe_stare', veche)
            n = pe.get(bifa['stare'], 0)
            pe[bifa['stare']] = (n if isinstance(n, int) else 0) + 1
        if era_intarziat:
            _scade(rez, 'intarziate')
        if era_start == 'dupa':
            _scade(rez, 'dupa_start')
        elif era_start == 'aproape':
            _scade(rez, 'aproape_start')
    if not schimbate or rez is None:
        return
    # Ca `$viitoare` din colector: stare care inca asteapta, cu termen, nu intarziata; cea mai apropiata e „urmatoarea".
    viitoare = sorted((m for m in materiale if isinstance(m, dict) and m.get('stare') in STARI_IN_CURS
                       and m.get('termen') and not m.get('intarziat')), key=lambda m: str(m['termen']))
    urm = rez.get('urmatoarea')
    if isinstance(urm, dict) and isinstance(urm.get('cod_bc'), str) and urm['cod_bc'] in schimbate:
        n = viitoare[0] if viitoare else None
        rez['urmatoarea'] = ({'data': n.get('termen'), 'tip': n.get('termen_tip'), 'stare': n.get('stare'),
                              'descriere': n.get('descriere'), 'cod_bc': n.get('cod_bc')} if n else None)
    if 'ultima_asteptata' in rez:
        rez['ultima_asteptata'] = viitoare[-1]['termen'] if viitoare else None


def vedere(curent, anterior, acum=None, bife=None):
    """Raspunsul GET din cele doua snapshot-uri (oricare poate fi None) si bifele manuale
    ({proiect_id: {cod_bc: {stare, la}}}, vezi `aplica_bife`)."""
    if curent is None:
        return {'generat': None, 'comparat_cu': None, 'vechi': True, 'sursa': {}, 'proiecte': []}
    prev_pe_id = {}
    if anterior is not None:
        for p in anterior.get('proiecte', []):
            if isinstance(p, dict) and isinstance(p.get('proiect_id'), str):
                prev_pe_id[p['proiect_id']] = p
    din_baza = _date_proiecte([p['proiect_id'] for p in curent['proiecte']])
    proiecte = []
    for p in curent['proiecte']:
        q = _proiect_cu_marcaje(p, prev_pe_id.get(p['proiect_id']))
        aplica_bife(q, bife.get(p['proiect_id']) if isinstance(bife, dict) else None)
        q['proiect'] = din_baza.get(p['proiect_id'])        # None: proiect sters intre timp
        proiecte.append(q)
    return {
        'generat': curent['generat'],
        'comparat_cu': anterior['generat'] if anterior is not None else None,
        'vechi': e_vechi(curent['generat'], acum),
        'sursa': curent.get('sursa') or {},
        'proiecte': proiecte,
    }


# --------------------------------------------------------------------------- rutele

@materiale_bp.route('/api/materiale', methods=['PUT'])
@login_required
def put_materiale():
    """Inlocuieste snapshot-ul materialelor. Sesiune sau Bearer `PIF_API_TOKEN`; tokenul de
    dispozitiv doar citeste (`DEVICE_TOKEN_READ_ONLY`). Idempotent: aceeasi cerere de doua ori
    lasa aceleasi fisiere. Un snapshot mai vechi decat cel curent da 409 si nu se scrie.
    Raspuns: {ok, proiecte, rotit}; cu `sursa.alerte = "server"` si {alerte, taskuri: {noi, existente, sarite}}."""
    if request.content_length is not None and request.content_length > MAX_CORP:
        return jsonify({'error': 'corp prea mare (maxim 2 MB)'}), 413
    brut = request.stream.read(MAX_CORP + 1)      # si fara Content-Length (chunked) plafonul ramane
    if len(brut) > MAX_CORP:
        return jsonify({'error': 'corp prea mare (maxim 2 MB)'}), 413
    try:
        corp = json.loads(brut.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return jsonify({'error': 'Body JSON invalid sau lipsa'}), 400
    try:
        snapshot = valideaza_snapshot(corp)
    except EroareCorp as e:
        logger.warning('Materiale: snapshot respins: %s', e)
        return jsonify({'error': str(e)}), 400

    curent, octeti_curent = _citeste(CURENT)
    nou = _data_ora(snapshot['generat'])
    rotit = False
    if curent is not None:
        vechi = _data_ora(curent['generat'])
        if nou < vechi:
            return jsonify({'error': 'snapshot mai vechi decat cel curent (%s)' % curent['generat']}), 409
        # Ziua locala din string (primele 10 caractere), ca la calendarul Outlook.
        rotit = snapshot['generat'][:10] != curent['generat'][:10]

    # Alertele pe server (din 2026-11-17): doar cand colectorul o cere, ca un colector vechi sa nu piarda nimic.
    pe_server = snapshot['sursa'].get('alerte') == 'server'
    taskuri, conn = [], None
    if pe_server:
        try:
            conn = get_db()
            cur = conn.cursor()
            taskuri = materiale_alerte.calculeaza(
                snapshot, lambda pid, azi: materiale_alerte.perioada_urmatoare(cur, pid, azi), citeste_bife(conn))
        except Exception:
            logger.exception('Materiale: calculul alertelor a picat')
            if conn is not None:
                conn.close()
            return jsonify({'error': 'Alertele nu s-au putut calcula; snapshot-ul nu s-a scris.'}), 500
    try:
        if rotit:
            _scrie_atomic(ANTERIOR, octeti_curent)
        _scrie_atomic(CURENT, json.dumps(snapshot, ensure_ascii=False).encode('utf-8'))
    except OSError:
        logger.exception('Materiale: scrierea snapshot-ului a esuat pe disc')
        if conn is not None:
            conn.close()
        return jsonify({'error': 'Eroare pe disc la salvarea snapshot-ului.'}), 500
    raspuns = {'ok': True, 'proiecte': len(snapshot['proiecte']), 'rotit': rotit}
    if pe_server:
        raspuns['alerte'] = sum(len(p['alerte']) for p in snapshot['proiecte'])
        try:
            noi, existente, sarite = materiale_alerte.creeaza_taskuri(conn, taskuri)
            raspuns['taskuri'] = {'noi': noi, 'existente': existente, 'sarite': sarite}
        except Exception:
            logger.exception('Materiale: taskurile alertelor nu s-au putut scrie')
            raspuns['taskuri'] = {'eroare': 'taskurile alertelor nu s-au scris; reiau la urmatoarea colectare'}
        finally:
            conn.close()
    return jsonify(raspuns)


@materiale_bp.route('/api/materiale', methods=['GET'])
@login_required
def get_materiale():
    """Ultima colectare, cu marcajele fata de ultima colectare dintr-o zi anterioara. Fara
    colectare (sau cu fisierul stricat): `generat` null, `proiecte` [], tot 200."""
    curent, _ = _citeste(CURENT)
    anterior, _ = _citeste(ANTERIOR) if curent is not None else (None, None)
    return jsonify(vedere(curent, anterior, bife=citeste_bife() if curent is not None else None))


def _eroare_bifa(mesaj, status):
    logger.warning('Materiale: bifa respinsa (%d): %s', status, mesaj)
    return jsonify({'error': mesaj}), status


@materiale_bp.route('/api/materiale/bifa', methods=['PUT'])
@login_required
def put_bifa():
    """Bifa manuala a lui Ion pe un articol: `{proiect_id, cod_bc, stare}`, `stare` din `la_destinatie|livrat` sau
    null (scoate bifa). Sesiune, `PIF_API_TOKEN` sau tokenul de dispozitiv (Torqa; ruta nu e in
    `DEVICE_TOKEN_READ_ONLY`, care e exact-match pe `/api/materiale`). 400 cu mesaj pe camp la corp invalid; 409 fara
    snapshot curent sau cand proiectul / `cod_bc` nu sunt in `proiecte[].materiale` din el. Idempotent: aceeasi
    stare de doua ori lasa bifa (si `la`) neatinse; null pe un articol fara bifa e tot 200. Citirea si scrierea
    din `app_settings` sunt intr-o tranzactie (BEGIN IMMEDIATE), ca doua bife simultane sa nu se strice intre ele.
    Raspuns: {ok: true, bifa: {stare, la} | null}."""
    if request.content_length is not None and request.content_length > MAX_CORP_BIFA:
        return jsonify({'error': 'corp prea mare'}), 413
    corp = request.get_json(silent=True)
    if not isinstance(corp, dict):
        return _eroare_bifa('Body JSON invalid sau lipsa', 400)
    pid, cod, stare = corp.get('proiect_id'), corp.get('cod_bc'), corp.get('stare')
    if not isinstance(pid, str) or not _RE_ID.fullmatch(pid):
        return _eroare_bifa('proiect_id: id-ul din /api/proiecte (1-64 de caractere A-Z a-z 0-9 _ -)', 400)
    if not isinstance(cod, str) or not cod.strip() or len(cod) > MAX_TEXT:
        return _eroare_bifa('cod_bc: text nevid, cel mult %d de caractere' % MAX_TEXT, 400)
    if 'stare' not in corp:                       # null scoate bifa; lipsa campului e o greseala, nu o scoatere
        return _eroare_bifa('stare: lipseste; una din %s sau null' % '|'.join(NIVEL_BIFA), 400)
    if stare is not None and (not isinstance(stare, str) or stare not in NIVEL_BIFA):
        return _eroare_bifa('stare: una din %s sau null' % '|'.join(NIVEL_BIFA), 400)

    curent, _ = _citeste(CURENT)
    if curent is None:
        return _eroare_bifa('nu exista snapshot curent al materialelor', 409)
    proiect = next((p for p in curent['proiecte'] if isinstance(p, dict) and p.get('proiect_id') == pid), None)
    if proiect is None:
        return _eroare_bifa('proiect_id: proiectul nu e in snapshot-ul curent', 409)
    materiale = proiect.get('materiale')
    if not isinstance(materiale, list) or not any(isinstance(m, dict) and m.get('cod_bc') == cod for m in materiale):
        return _eroare_bifa('cod_bc: articolul nu e in materialele proiectului din snapshot-ul curent', 409)

    conn = get_db()
    try:
        conn.execute('BEGIN IMMEDIATE')
        rand = conn.execute('SELECT value FROM app_settings WHERE key = ?', (CHEIE_BIFE,)).fetchone()
        bife = _parseaza_bife(rand['value'] if rand else None)
        pe_proiect = bife.get(pid) if isinstance(bife.get(pid), dict) else {}
        existenta = _bifa_valida(pe_proiect, cod)
        if stare is None:
            rezultat = None
            schimbat = cod in pe_proiect
            pe_proiect.pop(cod, None)
        elif existenta is not None and existenta['stare'] == stare:
            rezultat, schimbat = existenta, False
        else:
            rezultat = {'stare': stare, 'la': _acum().astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
            pe_proiect[cod] = rezultat
            schimbat = True
        if schimbat:
            if pe_proiect:
                bife[pid] = pe_proiect
            else:
                bife.pop(pid, None)
            conn.execute(
                'INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) '
                'ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at',
                (CHEIE_BIFE, json.dumps(bife, ensure_ascii=False), datetime.now().isoformat()))
        conn.commit()
    except sqlite3.OperationalError:
        conn.rollback()
        logger.exception('Materiale: baza ocupata la scrierea bifei')
        return jsonify({'error': 'Baza de date e ocupata; reincearca.'}), 503
    finally:
        conn.close()
    return jsonify({'ok': True, 'bifa': rezultat})

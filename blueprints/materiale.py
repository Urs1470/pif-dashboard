# Materiale Blueprint
# Centralizatorul de materiale al proiectelor deschise: ce e comandat (CT-uri, cu termenele
# confirmate din BC), ce e inca necomandat, listele de materiale (LM) din E100, firul de mailuri
# si alertele. Datele le aduna colectorul de pe PC-ul de job (Knowledge `tools/`, Task Scheduler,
# L-V la 08:00) si le urca la `PUT /api/materiale`; Torqa le citeste la `GET /api/materiale`.
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
# Colectorul inca evolueaza (LM-urile din E100 abia urmeaza), deci validarea e toleranta: campurile
# din contract au tipul verificat, cele in plus se pastreaza cum vin.

import json
import logging
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request

from blueprints.outlook import _data, _data_ora
from database import get_db
from utils import login_required, UPLOAD_FOLDER

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


def vedere(curent, anterior, acum=None):
    """Raspunsul GET din cele doua snapshot-uri (oricare poate fi None)."""
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
    Raspuns: {ok, proiecte, rotit}."""
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
    try:
        if rotit:
            _scrie_atomic(ANTERIOR, octeti_curent)
        _scrie_atomic(CURENT, json.dumps(snapshot, ensure_ascii=False).encode('utf-8'))
    except OSError:
        logger.exception('Materiale: scrierea snapshot-ului a esuat pe disc')
        return jsonify({'error': 'Eroare pe disc la salvarea snapshot-ului.'}), 500
    return jsonify({'ok': True, 'proiecte': len(snapshot['proiecte']), 'rotit': rotit})


@materiale_bp.route('/api/materiale', methods=['GET'])
@login_required
def get_materiale():
    """Ultima colectare, cu marcajele fata de ultima colectare dintr-o zi anterioara. Fara
    colectare (sau cu fisierul stricat): `generat` null, `proiecte` [], tot 200."""
    curent, _ = _citeste(CURENT)
    anterior, _ = _citeste(ANTERIOR) if curent is not None else (None, None)
    return jsonify(vedere(curent, anterior))

# Transport FCM HTTP v1, doar din biblioteca standard (nicio dependenta noua).
# Il foloseste `blueprints/asistent.py`; nu e un blueprint si nu are rute.
#
# DE CE FARA `cryptography` / PyJWT: OAuth2 pentru un cont de serviciu Google cere un JWT semnat
# RS256, iar semnatura RS256 e `pow(mesaj, d, n)` peste un mesaj PKCS#1 v1.5 pe SHA-256: cateva zeci
# de linii cu `int` si `hashlib`. Serverul nu are alt motiv sa instaleze o biblioteca de criptografie
# (`teste/test_cerinte.py` interzice `cryptography`, ramasa din web push-ul retras), iar cheia se
# foloseste o data pe ora, local, fara ca un atacator sa vada durata (nu exista un oracol): timpul
# constant nu conteaza aici. Semnatura se verifica imediat cu cheia publica, ca o greseala de
# implementare sa nu ajunga niciodata la Google.
#
# Config: `FCM_SERVICE_ACCOUNT_FILE` = JSON-ul contului de serviciu (drepturi 600, in afara repo-ului).
# Fara el, `configurat()` e False si nimic nu se trimite. Cheia privata nu se logheaza si nu iese in
# niciun mesaj de eroare; erorile spun doar un cod scris in cod (`HTTP 503`, `retea`, `UNREGISTERED`).
#
# Totul are timeout: `trimite_date` nu depaseste `TIMP_MAXIM` secunde in total (token OAuth + toate
# trimiterile), iar o eroare nu se ridica: se intoarce in lista `erori`.

import base64
import hashlib
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger('pif_dashboard')

SCOPE = 'https://www.googleapis.com/auth/firebase.messaging'
URL_TOKEN = 'https://oauth2.googleapis.com/token'
URL_SEND = 'https://fcm.googleapis.com/v1/projects/%s/messages:send'
TIMP_MAXIM = 10.0                 # secunde, pentru tot apelul `trimite_date`
TIMEOUT_CERERE = 8.0              # plafonul unei singure cereri (se mai taie la timpul ramas)
MAX_ERORI = 10
MARJA_TOKEN = 60                  # secunde: tokenul de acces se reia cu atat inainte sa expire
_PREFIX_SHA256 = bytes.fromhex('3031300d060960864801650304020105000420')   # DigestInfo SHA-256


class EroareFcm(Exception):
    """Mesajul e deja curat: poate ajunge in `push.erori`."""


# --------------------------------------------------------------------------- RS256

def _b64u(octeti):
    return base64.urlsafe_b64encode(octeti).rstrip(b'=').decode('ascii')


def _der(buf, poz):
    """Un element DER la `poz`: (eticheta, inceputul continutului, sfarsitul)."""
    eticheta = buf[poz]
    lung = buf[poz + 1]
    poz += 2
    if lung & 0x80:
        n = lung & 0x7F
        if n == 0 or n > 4:
            raise ValueError('lungime DER neacceptata')
        lung = int.from_bytes(buf[poz:poz + n], 'big')
        poz += n
    if poz + lung > len(buf):
        raise ValueError('DER trunchiat')
    return eticheta, poz, poz + lung


def _intregi(buf, inceput, sfarsit, cate):
    """Primele `cate` INTEGER-e dintr-un SEQUENCE al carui continut e buf[inceput:sfarsit]."""
    iesire, poz = [], inceput
    for _ in range(cate):
        eticheta, i, s = _der(buf, poz)
        if eticheta != 0x02:
            raise ValueError('se astepta INTEGER')
        iesire.append(int.from_bytes(buf[i:s], 'big'))
        poz = s
    return iesire


def cheie_rsa(pem):
    """(n, e, d) dintr-o cheie privata RSA in PEM: PKCS#8 (`BEGIN PRIVATE KEY`, formatul Google)
    sau PKCS#1 (`BEGIN RSA PRIVATE KEY`). ValueError daca nu se poate citi."""
    linii = [l.strip() for l in pem.strip().splitlines()]
    if len(linii) < 3 or not linii[0].startswith('-----BEGIN ') or 'PRIVATE KEY' not in linii[0]:
        raise ValueError('nu e o cheie PEM privata')
    if 'ENCRYPTED' in linii[0]:
        raise ValueError('cheie criptata')
    try:
        der = base64.b64decode(''.join(linii[1:-1]), validate=True)
        eticheta, i, s = _der(der, 0)
        if eticheta != 0x30:
            raise ValueError('se astepta SEQUENCE')
        if linii[0] == '-----BEGIN PRIVATE KEY-----':          # PKCS#8: versiune, algoritm, OCTET STRING cu cheia PKCS#1
            _, _, s1 = _der(der, i)                             # versiune
            _, _, s2 = _der(der, s1)                            # AlgorithmIdentifier
            eticheta, i3, s3 = _der(der, s2)
            if eticheta != 0x04:
                raise ValueError('se astepta OCTET STRING')
            der = der[i3:s3]
            eticheta, i, s = _der(der, 0)
            if eticheta != 0x30:
                raise ValueError('se astepta SEQUENCE')
        _, _, sv = _der(der, i)                                 # RSAPrivateKey: versiune, apoi n, e, d
        n, e, d = _intregi(der, sv, s, 3)
    except (IndexError, ValueError, TypeError) as ex:
        raise ValueError('cheia privata nu se poate citi: %s' % ex)
    if n.bit_length() < 2040 or n.bit_length() > 8200:
        raise ValueError('cheie RSA de marime neasteptata')
    return n, e, d


def semneaza_rs256(mesaj, n, e, d):
    """Semnatura RSASSA-PKCS1-v1_5 cu SHA-256 peste `mesaj` (bytes), verificata cu cheia publica."""
    k = (n.bit_length() + 7) // 8
    t = _PREFIX_SHA256 + hashlib.sha256(mesaj).digest()
    em = b'\x00\x01' + b'\xff' * (k - len(t) - 3) + b'\x00' + t
    m = int.from_bytes(em, 'big')
    s = pow(m, d, n)
    if pow(s, e, n) != m:
        raise ValueError('semnatura nu se verifica cu cheia publica')
    return s.to_bytes(k, 'big')


def jwt_rs256(claims, n, e, d):
    antet = _b64u(json.dumps({'alg': 'RS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
    corp = _b64u(json.dumps(claims, separators=(',', ':')).encode())
    semn = semneaza_rs256(('%s.%s' % (antet, corp)).encode('ascii'), n, e, d)
    return '%s.%s.%s' % (antet, corp, _b64u(semn))


# --------------------------------------------------------------------------- configurare

_CONT = {'cale': None, 'mtime': None, 'val': None}
_TOKEN = {'valoare': None, 'expira': 0.0}
_BLOC = threading.Lock()


def _cont():
    """Contul de serviciu din `FCM_SERVICE_ACCOUNT_FILE`: {project_id, client_email, cheie: (n, e, d)}
    sau None cand lipseste ori nu se poate citi (motivul se logheaza, fara continut)."""
    cale = os.environ.get('FCM_SERVICE_ACCOUNT_FILE', '').strip()
    if not cale:
        return None
    try:
        mtime = os.stat(cale).st_mtime_ns
    except OSError:
        logger.warning('FCM: fisierul FCM_SERVICE_ACCOUNT_FILE nu exista sau nu se poate citi')
        return None
    if _CONT['cale'] == cale and _CONT['mtime'] == mtime:
        return _CONT['val']
    val = None
    try:
        with open(cale, 'rb') as fh:
            brut = json.loads(fh.read().decode('utf-8'))
        if not isinstance(brut, dict):
            raise ValueError('nu e un obiect JSON')
        proiect, email, pem = brut.get('project_id'), brut.get('client_email'), brut.get('private_key')
        if not all(isinstance(x, str) and x for x in (proiect, email, pem)):
            raise ValueError('lipsesc project_id, client_email sau private_key')
        if '/' in proiect or '?' in proiect:
            raise ValueError('project_id invalid')
        val = {'project_id': proiect, 'client_email': email, 'cheie': cheie_rsa(pem)}
    except (OSError, ValueError, RecursionError) as ex:
        logger.warning('FCM: contul de serviciu nu se poate folosi (%s)', ex)
    _CONT.update(cale=cale, mtime=mtime, val=val)
    _TOKEN.update(valoare=None, expira=0.0)                    # alt cont, alt token de acces
    return val


def configurat():
    return _cont() is not None


# --------------------------------------------------------------------------- HTTP

def _http_post(url, date, antete, timeout):
    """(cod HTTP, corp bytes). Ridica OSError (inclusiv URLError, timeout) cand nu ajunge la server.
    Singurul loc care atinge reteaua: testele il inlocuiesc."""
    cerere = urllib.request.Request(url, data=date, headers=antete, method='POST')
    try:
        with urllib.request.urlopen(cerere, timeout=timeout) as r:
            return r.status, r.read(1024 * 1024)
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read(64 * 1024)
        finally:
            e.close()


def _cere(url, date, antete, limita):
    ramas = limita - time.monotonic()
    if ramas <= 0.2:
        raise EroareFcm('timp depasit')
    try:
        return _http_post(url, date, antete, min(TIMEOUT_CERERE, ramas))
    except OSError as ex:                                      # URLError, TimeoutError, ConnectionError
        # Doar tipul: textul unei erori urllib poate purta adresa sau detalii de retea.
        raise EroareFcm('retea (%s)' % type(ex).__name__)


def _json(brut):
    try:
        v = json.loads(brut.decode('utf-8'))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return {}
    return v if isinstance(v, dict) else {}


def _token_acces(cont, limita, acum=None):
    """Tokenul OAuth2 din memorie, sau unul nou (cerut cu JWT-ul semnat). EroareFcm la esec."""
    acum = acum if acum is not None else time.time()
    with _BLOC:
        if _TOKEN['valoare'] and acum < _TOKEN['expira'] - MARJA_TOKEN:
            return _TOKEN['valoare']
    n, e, d = cont['cheie']
    jwt = jwt_rs256({'iss': cont['client_email'], 'scope': SCOPE, 'aud': URL_TOKEN,
                     'iat': int(acum), 'exp': int(acum) + 3600}, n, e, d)
    corp = urllib.parse.urlencode({'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                                   'assertion': jwt}).encode('ascii')
    cod, brut = _cere(URL_TOKEN, corp, {'Content-Type': 'application/x-www-form-urlencoded'}, limita)
    raspuns = _json(brut)
    token = raspuns.get('access_token')
    if cod != 200 or not isinstance(token, str) or not token:
        eroare = raspuns.get('error')
        raise EroareFcm('token OAuth: HTTP %d%s' % (cod, ' %s' % eroare[:40] if isinstance(eroare, str) else ''))
    expira = raspuns.get('expires_in')
    with _BLOC:
        _TOKEN.update(valoare=token, expira=acum + (expira if isinstance(expira, int) and expira > 0 else 3000))
    return token


def _cod_eroare(raspuns):
    """Codul FCM din raspunsul de eroare (`UNREGISTERED`, `INVALID_ARGUMENT`...), sau ''."""
    eroare = raspuns.get('error')
    if not isinstance(eroare, dict):
        return ''
    for det in eroare.get('details') or []:
        if isinstance(det, dict) and isinstance(det.get('errorCode'), str):
            return det['errorCode'][:40]
    stare = eroare.get('status')
    return stare[:40] if isinstance(stare, str) else ''


def _scurt(token):
    return '...' + token[-6:]


def trimite_date(tokeni, date, prioritate_android, timp_maxim=TIMP_MAXIM):
    """Trimite mesajul DOAR de date (toate valorile string) la fiecare token. Intoarce
    {'trimise': int, 'erori': [str], 'nregistrate': [tokeni de scos]}; nu ridica niciodata.
    `nregistrate` = tokenii pe care FCM ii respinge cu 404 / UNREGISTERED."""
    iesire = {'trimise': 0, 'erori': [], 'nregistrate': []}
    cont = _cont()
    if cont is None:
        iesire['erori'].append('cont de serviciu indisponibil')
        return iesire
    limita = time.monotonic() + min(timp_maxim, TIMP_MAXIM)

    def eroare(text):
        if len(iesire['erori']) < MAX_ERORI:
            iesire['erori'].append(text[:200])

    try:
        acces = _token_acces(cont, limita)
    except EroareFcm as ex:
        eroare(str(ex))
        return iesire
    except Exception:                                          # o greseala de cod nu devine 5xx
        logger.exception('FCM: obtinerea tokenului OAuth a esuat neasteptat')
        eroare('token OAuth: eroare interna')
        return iesire
    url = URL_SEND % urllib.parse.quote(cont['project_id'], safe='')
    for token in tokeni:
        mesaj = {'message': {'token': token,
                             'android': {'priority': prioritate_android, 'ttl': '86400s'},
                             'data': date}}
        try:
            cod, brut = _cere(url, json.dumps(mesaj, ensure_ascii=False).encode('utf-8'),
                              {'Content-Type': 'application/json; charset=UTF-8',
                               'Authorization': 'Bearer ' + acces}, limita)
        except EroareFcm as ex:
            eroare('%s: %s' % (_scurt(token), ex))
            if str(ex) == 'timp depasit':
                break
            continue
        except Exception:
            logger.exception('FCM: trimiterea a esuat neasteptat')
            eroare('%s: eroare interna' % _scurt(token))
            continue
        if 200 <= cod < 300:
            iesire['trimise'] += 1
            continue
        cod_fcm = _cod_eroare(_json(brut))
        if cod == 404 or cod_fcm == 'UNREGISTERED':
            iesire['nregistrate'].append(token)
            eroare('%s: UNREGISTERED' % _scurt(token))
            continue
        if cod == 401:                                         # tokenul de acces a fost respins: la urmatoarea cerere se reia
            with _BLOC:
                _TOKEN.update(valoare=None, expira=0.0)
        eroare('%s: HTTP %d%s' % (_scurt(token), cod, ' %s' % cod_fcm if cod_fcm else ''))
    return iesire

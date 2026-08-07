# Push Blueprint
# Notificari pe telefon pentru taskurile PERSONALE care stau fara termen.
#
# Regula (ceruta de Ion): un task personal, deschis, FARA data, mai vechi de
# doua zile, primeste in fiecare dimineata la 08:00 o notificare PROPRIE — nu
# un rezumat. „Trebuie sa apara taskul propriu-zis, separat per notificare,
# trebuie sa pot bifa taskul direct din notificare."
#
# De aceea fiecare notificare poarta doua actiuni: „Facut" si „Azi" — exact
# cele doua iesiri din situatia care a generat-o („nu l-am facut SAU nu i-am
# pus termen"). Pe Android butoanele apar pe notificare; pe iOS nu exista
# butoane de actiune, deci acolo atingerea deschide taskul in aplicatie.
#
# CUM POATE SERVICE WORKER-UL SA BIFEZE UN TASK: nu poate citi cookie-uri,
# deci nu are tokenul CSRF. In loc, fiecare notificare primeste un TOKEN
# SEMNAT (HMAC-SHA256 cu SECRET_KEY) care e capabilitatea de a face done/azi
# pe UN singur task, valabil 48h. Ruta /api/push/action nu cere sesiune —
# tokenul E autentificarea — si e scutita de CSRF prin `_EXEMPT_ENDPOINTS`.
# Payload-ul push e criptat end-to-end catre browser (aes128gcm), deci tokenul
# nu se plimba in clar.

import base64
import hashlib
import hmac
import json
import logging
import threading
import time
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request

from utils import login_required, get_json_or_400, get_app_setting, set_app_setting
from database import get_db, row_to_dict

logger = logging.getLogger(__name__)

push_bp = Blueprint('push', __name__)

# Import gardat: deploy-ul ruleaza `pip install -r requirements.txt`, dar un
# esec e DOAR logat si serviciul reporneste oricum. Fara garda, o instalare
# ratata ar transforma pornirea aplicatiei intr-o eroare 500.
try:
    from pywebpush import webpush, WebPushException
    _PUSH_OK = True
except Exception:  # pragma: no cover — depinde de mediu
    webpush = None
    WebPushException = Exception
    _PUSH_OK = False

PUSH_SUB = 'mailto:ursuion1470@gmail.com'
ORA_TRIMITERE = 8           # ora locala a serverului
ZILE_VECHIME = 2            # „sta fara termen de mai mult de N zile"
TOKEN_VALABIL_ORE = 48      # pana cand vine notificarea de maine
# Cat asteptam serviciul push (FCM/APNs) per dispozitiv. Aceeasi valoare ca in
# google_calendar.py, dar constanta traieste AICI: `send_to_all` o folosea fara
# s-o defineasca in modul, iar `timeout=` se evalueaza inainte de apel — deci
# fiecare trimitere murea cu NameError, era prinsa de `except Exception` de mai
# jos si numarata ca esec. Zero notificari plecate, si la „Trimite test", si
# dimineata, cu un mesaj de eroare care nu arata spre cauza.
HTTP_TIMEOUT = 15

K_SETARI = 'push_setari'
K_VAPID_PRIV = 'push_vapid_private'
K_VAPID_PUB = 'push_vapid_public'
K_SUBS = 'push_subscriptions'
K_DAILY = 'push_daily_last'
K_LAST_ERROR = 'push_last_error'

_secret = b''               # setat de porneste_planificator (threadul n-are app context)
_planificator_pornit = False
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Setarile — O SINGURA SURSA pentru ambele canale
# ---------------------------------------------------------------------------
# `ORA_TRIMITERE` si `ZILE_VECHIME` erau constante scrise si aici, si in
# `frontend/src/lib/notificari.js`, cu un comentariu care cerea sa fie schimbate
# impreuna. O obligatie tinuta de disciplina se rupe tacut: una se schimba, alta
# nu, iar telefonul si serverul incep sa creada lucruri diferite despre aceeasi
# regula. Acum valorile stau in `app_settings`, iar constantele de mai sus sunt
# doar ce se foloseste cand nu s-a ales nimic.

SETARI_IMPLICITE = {
    'ora': ORA_TRIMITERE,
    'zileVechime': ZILE_VECHIME,
    'scadente': True,        # notifica in dimineata zilei de scadenta
    'faraTermen': True,      # notifica zilnic taskurile fara termen
}


def _setari():
    """Setarile curente, completate cu implicitele. Nu arunca niciodata: o
    valoare stricata in baza nu are voie sa opreasca notificarile cu totul."""
    val = get_app_setting(K_SETARI)
    s = dict(SETARI_IMPLICITE)
    if val:
        try:
            s.update({k: v for k, v in json.loads(val).items() if k in SETARI_IMPLICITE})
        except ValueError:
            logger.warning('Push: setari invalide in baza, folosesc implicitele')
    return s


def _valideaza_setari(d):
    """(setari, eroare). Validarea e AICI, nu in interfata: telefonul si browserul
    trimit amandoua spre ruta asta, iar o regula scrisa in doua locuri diverge."""
    out = dict(SETARI_IMPLICITE)
    try:
        ora = int(d.get('ora', out['ora']))
        zile = int(d.get('zileVechime', out['zileVechime']))
    except (TypeError, ValueError):
        return None, 'Ora și pragul trebuie să fie numere.'
    if not 0 <= ora <= 23:
        return None, 'Ora trebuie să fie între 0 și 23.'
    if not 0 <= zile <= 60:
        return None, 'Pragul trebuie să fie între 0 și 60 de zile.'
    out['ora'], out['zileVechime'] = ora, zile
    out['scadente'] = bool(d.get('scadente', out['scadente']))
    out['faraTermen'] = bool(d.get('faraTermen', out['faraTermen']))
    if not out['scadente'] and not out['faraTermen']:
        return None, 'Cel puțin un fel de notificare trebuie să rămână pornit.'
    return out, None


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def _unb64(txt):
    pad = '=' * (-len(txt) % 4)
    return base64.urlsafe_b64decode(txt + pad)


# ---------------------------------------------------------------------------
# Token de actiune (capabilitate pe UN task)
# ---------------------------------------------------------------------------

def _secret_curent():
    """Secretul de semnare. `porneste_planificator` il pune la prima cerere, dar
    ruta de tokenuri poate fi atinsa inainte — iar un token semnat cu `b''` ar fi
    acceptat de un server care si-a pierdut secretul intre timp. Cadem pe cheia
    aplicatiei, care e aceeasi si e persistata pe disc."""
    global _secret
    if not _secret:
        try:
            from flask import current_app
            k = current_app.secret_key
            _secret = k if isinstance(k, bytes) else str(k).encode('utf-8')
        except Exception:
            pass
    return _secret


def mint_token(task_id, acum=None):
    """Token semnat pentru un singur task, valabil TOKEN_VALABIL_ORE."""
    acum = acum or datetime.now()
    _secret_curent()
    exp = int((acum + timedelta(hours=TOKEN_VALABIL_ORE)).timestamp())
    corp = _b64(json.dumps({'tid': task_id, 'exp': exp}).encode('utf-8'))
    sig = _b64(hmac.new(_secret, f'{task_id}:{exp}'.encode('utf-8'), hashlib.sha256).digest())
    return f'{corp}.{sig}'


def verifica_token(token, acum=None):
    """Intoarce task_id daca semnatura si expirarea sunt bune, altfel None."""
    acum = acum or datetime.now()
    _secret_curent()
    try:
        corp, sig = (token or '').split('.', 1)
        date_ = json.loads(_unb64(corp))
        tid, exp = date_['tid'], int(date_['exp'])
    except Exception:
        return None
    asteptat = _b64(hmac.new(_secret, f'{tid}:{exp}'.encode('utf-8'), hashlib.sha256).digest())
    if not hmac.compare_digest(asteptat, sig):
        return None
    if exp < int(acum.timestamp()):
        return None
    return tid


# ---------------------------------------------------------------------------
# Chei VAPID + abonamente
# ---------------------------------------------------------------------------

def _priv_raw(key):
    """Cheia privata in FORMATUL PE CARE IL CITESTE py_vapid: scalarul de 32 de
    octeti, base64url. `Vapid.from_string` face `b64urldecode` pe tot sirul si
    cere fix 32 de octeti — deci ORICE PEM (si PKCS8, si SEC1) esueaza acolo.
    Prima versiune stoca PKCS8 PEM: semnarea crapa inainte sa atinga reteaua,
    iar „Trimite test" pica fara sa spuna de ce."""
    return _b64(key.private_numbers().private_value.to_bytes(32, 'big'))


def _chei_vapid():
    """(cheie privata base64url, cheie publica base64url). Se genereaza o
    SINGURA data: regenerarea ar invalida in tacere toate abonamentele."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    priv = get_app_setting(K_VAPID_PRIV)
    pub = get_app_setting(K_VAPID_PUB)
    if priv and pub:
        if '-----BEGIN' in priv:
            # Cheie salvata de versiunea veche (PKCS8 PEM). O CONVERTIM, nu o
            # regeneram: perechea ramane aceeasi, deci abonamentele deja facute
            # pe telefon continua sa mearga.
            key = serialization.load_pem_private_key(priv.encode('ascii'), password=None)
            priv = _priv_raw(key)
            set_app_setting(K_VAPID_PRIV, priv)
            logger.info('Push: cheia VAPID convertita din PEM in format raw')
        return priv, pub

    key = ec.generate_private_key(ec.SECP256R1())
    priv = _priv_raw(key)
    pub = _b64(key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    ))
    set_app_setting(K_VAPID_PRIV, priv)
    set_app_setting(K_VAPID_PUB, pub)
    return priv, pub


def _abonamente():
    try:
        return json.loads(get_app_setting(K_SUBS) or '{}')
    except ValueError:
        return {}


def _salveaza_abonamente(d):
    set_app_setting(K_SUBS, json.dumps(d))


def _hash_endpoint(endpoint):
    return hashlib.sha256(endpoint.encode('utf-8')).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Trimiterea
# ---------------------------------------------------------------------------

def send_to_all(payload):
    """Trimite un payload la toate dispozitivele abonate. Abonamentele moarte
    (404/410) se curata pe loc — un telefon reinstalat n-are voie sa strice
    trimiterea catre celelalte."""
    if not _PUSH_OK:
        return 0, 0
    subs = _abonamente()
    if not subs:
        return 0, 0
    priv, _ = _chei_vapid()
    trimise, esuate, moarte, motiv = 0, 0, [], ''
    for h, sub in list(subs.items()):
        try:
            webpush(subscription_info={'endpoint': sub['endpoint'], 'keys': sub['keys']},
                    data=json.dumps(payload),
                    vapid_private_key=priv,
                    vapid_claims={'sub': PUSH_SUB},
                    timeout=HTTP_TIMEOUT)
            trimise += 1
        except WebPushException as e:
            cod = getattr(getattr(e, 'response', None), 'status_code', 0)
            if cod in (404, 410):
                moarte.append(h)
            else:
                esuate += 1
                motiv = motiv or f'Serviciul push a răspuns {cod or "eroare"}.'
                logger.error('Push: trimitere esuata (status %s)', cod)
        except Exception as e:
            esuate += 1
            # MOTIVUL, nu doar numarul. Prima versiune scria „N notificari nu au
            # putut fi trimise", ceea ce nu spune daca e cheia, reteaua sau
            # abonamentul — iar fara SSH nu ai de unde afla.
            motiv = motiv or f'{type(e).__name__}: {str(e)[:120]}'
            logger.exception('Push: trimitere esuata')
    if moarte:
        for h in moarte:
            subs.pop(h, None)
        _salveaza_abonamente(subs)
    set_app_setting(K_LAST_ERROR, '' if not esuate else motiv)
    return trimise, esuate


def taskuri_de_notificat(cursor, zile_vechime=None):
    """Taskurile personale care stau fara termen de peste doua zile.

    `date('now','localtime',...)`: `created_at` e ISO LOCAL naiv, iar `'now'`
    simplu in SQLite e UTC — fara `localtime`, un task creat seara ar aluneca
    o zi si ar fi notificat prea devreme. Sfera se scrie LITERAL aici (regula
    casei: un grep pe `FROM global_tasks` trebuie sa arate decizia de sfera).
    """
    zile = int(ZILE_VECHIME if zile_vechime is None else zile_vechime)
    cursor.execute(f'''
        SELECT g.* FROM global_tasks g
        WHERE g.sfera = 'personal' AND g.status != 'done'
          AND (g.data_scadenta IS NULL OR TRIM(g.data_scadenta) = '')
          AND date(g.created_at) <= date('now', 'localtime', '-{zile} days')
        ORDER BY g.created_at ASC
    ''')
    return [row_to_dict(r) for r in cursor.fetchall()]


def _zile_de_cand(created_at, acum):
    try:
        d = datetime.strptime(str(created_at)[:10], '%Y-%m-%d')
        return max(0, (acum.date() - d.date()).days)
    except Exception:
        return ZILE_VECHIME


def check_and_send_daily(now=None, trimite=None):
    """Notificarile de dimineata. `now`/`trimite` sunt injectabile din teste.

    Intoarce: 'devreme' | 'claimed-gata' | 'trimis' | 'nimic'.
    """
    now = now or datetime.now()
    setari = _setari()
    if now.hour < setari['ora']:
        return 'devreme'

    conn = get_db()
    cursor = conn.cursor()
    azi = now.strftime('%Y-%m-%d')
    # CLAIM INAINTE DE TRIMITERE. Doua workere gunicorn si o bucla la 5 minute
    # inseamna multe incercari pe zi; o notificare dubla in fiecare dimineata
    # erodeaza increderea definitiv, pe cand o zi pierduta la un crash se
    # vindeca singura maine. Deci intai punem stampila zilei, apoi trimitem.
    cursor.execute('''
        INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        WHERE app_settings.value <> excluded.value
    ''', (K_DAILY, azi, now.isoformat()))
    conn.commit()
    if cursor.rowcount != 1:
        conn.close()
        return 'claimed-gata'

    randuri = taskuri_de_notificat(cursor, setari['zileVechime']) if setari['faraTermen'] else []
    conn.close()
    if not randuri:
        return 'nimic'      # claim consumat: ziua e gata, fara notificare

    expeditor = trimite or send_to_all
    for t in randuri:
        zile = _zile_de_cand(t.get('created_at'), now)
        expeditor({
            'title': t.get('titlu') or 'Task personal',
            'body': f'Fără termen de {zile} zile — bifează sau pune-i o zi.',
            # Aceeasi eticheta per task: notificarea de maine o INLOCUIESTE pe
            # cea de azi, nu se stivuiesc sapte copii ale aceluiasi task.
            'tag': f"pif-task-{t['id']}",
            'url': f"/#/tasks?sfera=personal&focus=global:{t['id']}",
            'token': mint_token(t['id'], now),
            'actions': True,
        })
    return 'trimis'


def porneste_planificator(secret=b''):
    """Bucla de verificare, o data per worker. Dedup-ul e in baza (claim), nu
    aici — doua workere pot rula linistite acelasi cod.

    Catch-up, nu tick exact: serviciul reporneste la fiecare deploy, deci
    intrebarea nu e „e ora 8 fix?", ci „a trecut ora 8 si n-am trimis azi?".
    """
    global _planificator_pornit, _secret
    _secret = secret if isinstance(secret, bytes) else str(secret).encode('utf-8')
    with _lock:
        if _planificator_pornit:
            return
        _planificator_pornit = True

    def _bucla():
        while True:
            try:
                if _PUSH_OK:
                    check_and_send_daily()
            except Exception:
                logger.exception('Push: verificarea zilnica a esuat')
            time.sleep(300)

    threading.Thread(target=_bucla, daemon=True).start()


# ---------------------------------------------------------------------------
# Rute
# ---------------------------------------------------------------------------

@push_bp.route('/api/push/vapid-public', methods=['GET'])
@login_required
def push_vapid_public():
    if not _PUSH_OK:
        return jsonify({'error': 'Web Push indisponibil pe server.'}), 503
    return jsonify({'cheie': _chei_vapid()[1]})


@push_bp.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = get_json_or_400()
    endpoint = (data.get('endpoint') or '').strip()
    chei = data.get('keys') or {}
    if not endpoint.startswith('https://') or not chei.get('p256dh') or not chei.get('auth'):
        return jsonify({'error': 'Abonament invalid.'}), 400
    subs = _abonamente()
    subs[_hash_endpoint(endpoint)] = {
        'endpoint': endpoint,
        'keys': {'p256dh': chei['p256dh'], 'auth': chei['auth']},
        'adaugat': datetime.now().isoformat(),
        'ua': (request.headers.get('User-Agent') or '')[:120],
    }
    _salveaza_abonamente(subs)
    return jsonify({'ok': True, 'abonamente': len(subs)})


@push_bp.route('/api/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = get_json_or_400()
    endpoint = (data.get('endpoint') or '').strip()
    subs = _abonamente()
    subs.pop(_hash_endpoint(endpoint), None)
    _salveaza_abonamente(subs)
    return jsonify({'ok': True, 'abonamente': len(subs)})


@push_bp.route('/api/push/tokens', methods=['POST'])
@login_required
def push_tokens():
    """Tokenuri de actiune pentru taskurile pe care aplicatia le programeaza.

    DE CE. Butoanele „Facut"/„Azi" de pe notificare sunt tratate de un
    BroadcastReceiver nativ, ca sa nu se deschida aplicatia. Un receiver nu are
    WebView, deci nu are cookie de sesiune si nici token CSRF — exact situatia
    service worker-ului, pentru care `/api/push/action` a fost deja construita:
    token semnat HMAC, UN task, doua actiuni, 48 de ore.

    Deci telefonul cere de aici cate un token pentru fiecare task pe care il
    pune in fereastra de notificari, si il pune in alarma. Tokenul moare odata cu
    notificarea. Ruta cere SESIUNE — se cheama din aplicatie, cand e deschisa.
    """
    date = get_json_or_400()
    ids = date.get('ids')
    if not isinstance(ids, list) or len(ids) > 200:
        return jsonify({'error': 'Trimite `ids`, o listă de cel mult 200.'}), 400
    # Se semneaza DOAR taskuri care exista si sunt personale: altfel ruta ar
    # deveni o masina de tokenuri pentru orice id ghicit.
    conn = get_db()
    cursor = conn.cursor()
    curate = [str(i) for i in ids if isinstance(i, str) and i]
    if not curate:
        conn.close()
        return jsonify({})
    semne = ','.join('?' * len(curate))
    cursor.execute(f"SELECT id FROM global_tasks WHERE sfera = 'personal' AND id IN ({semne})",
                   curate)
    gasite = [r['id'] for r in cursor.fetchall()]
    conn.close()
    return jsonify({tid: mint_token(tid) for tid in gasite})


@push_bp.route('/api/push/setari', methods=['GET'])
@login_required
def push_setari_get():
    return jsonify(_setari())


@push_bp.route('/api/push/setari', methods=['PUT'])
@login_required
def push_setari_put():
    setari, eroare = _valideaza_setari(get_json_or_400())
    if eroare:
        return jsonify({'error': eroare}), 400
    set_app_setting(K_SETARI, json.dumps(setari))
    return jsonify(setari)


@push_bp.route('/api/push/status', methods=['GET'])
@login_required
def push_status():
    s = _setari()
    return jsonify({
        'disponibil': _PUSH_OK,
        'abonamente': len(_abonamente()),
        'ora': f"{s['ora']:02d}:00",
        'regula': f"personale · fără termen · mai vechi de {s['zileVechime']} zile",
        'last_error': get_app_setting(K_LAST_ERROR, '') or '',
        'azi_trimis': (get_app_setting(K_DAILY, '') or '') == datetime.now().strftime('%Y-%m-%d'),
    })


@push_bp.route('/api/push/test', methods=['POST'])
@login_required
def push_test():
    if not _PUSH_OK:
        return jsonify({'error': 'Web Push indisponibil pe server.'}), 503
    if not _abonamente():
        # Un test care „reuseste" trimitand catre nimeni e o minciuna.
        return jsonify({'error': 'Niciun dispozitiv abonat.'}), 400
    trimise, esuate = send_to_all({
        'title': 'Test PIF',
        'body': 'Notificările funcționează.',
        'tag': 'pif-test',
        'url': '/#/tasks?sfera=personal',
    })
    return jsonify({'trimise': trimise, 'esuate': esuate,
                    'motiv': get_app_setting(K_LAST_ERROR, '') or ''})


@push_bp.route('/api/push/action', methods=['POST'])
def push_action():
    """Bifeaza sau planifica un task DIN notificare.

    Fara @login_required: service worker-ul nu poate citi cookie-uri, deci nu
    are tokenul CSRF si nu se poate baza pe sesiune. Tokenul semnat din
    payload E autentificarea — acopera un singur task, doua actiuni, 48h.
    Scutirea de CSRF e in csrf.py (`_EXEMPT_ENDPOINTS`).
    """
    data = get_json_or_400()
    task_id = verifica_token(data.get('token'))
    if not task_id:
        return jsonify({'error': 'Token invalid sau expirat.'}), 403
    actiune = data.get('action')
    if actiune not in ('done', 'azi'):
        return jsonify({'error': 'Acțiune necunoscută.'}), 400

    now = datetime.now()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM global_tasks WHERE id = ?', (task_id,))
    r = cursor.fetchone()
    if r is None:
        conn.close()
        return jsonify({'error': 'Task inexistent.'}), 404
    existing = row_to_dict(r)

    spawned_id = None
    if actiune == 'done':
        # Acelasi guard atomic ca in PUT /api/global-tasks/<id>: doua atingeri
        # pe aceeasi notificare nu au voie sa nasca doua ocurente recurente.
        cursor.execute("UPDATE global_tasks SET status = 'done', updated_at = ? "
                       "WHERE id = ? AND status != 'done'", (now.isoformat(), task_id))
        trecut = cursor.rowcount == 1
        recurenta = (existing.get('recurenta') or '').strip()
        # Recurenta fara data e degenerata (n-ar avea de unde calcula urmatoarea),
        # iar notificarile astea merg exact la taskurile FARA data.
        if trecut and recurenta and (existing.get('data_scadenta') or '').strip():
            from blueprints.tasks import _spawn_recurring_global_task
            spawned_id = _spawn_recurring_global_task(cursor, r, recurenta)
    else:
        cursor.execute('UPDATE global_tasks SET data_scadenta = ?, updated_at = ? WHERE id = ?',
                       (now.strftime('%Y-%m-%d'), now.isoformat(), task_id))
    conn.commit()
    conn.close()

    # Oglindeste in Google Calendar (✓ la bifare, eveniment nou la „Azi").
    from blueprints.google_calendar import sync_enabled, spawn_sync
    if sync_enabled():
        spawn_sync(*([task_id, spawned_id] if spawned_id else [task_id]))

    return jsonify({'ok': True, 'action': actiune})

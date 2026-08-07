# Google Calendar Blueprint
# Sincronizare directa (push) a taskurilor PERSONALE in Google Calendar.
#
# De ce exista: feed-ul .ics e sincronizare automata, dar Google il recititeste
# cand vrea el (ore). Ion a cerut instant — deci push prin Calendar API, in
# momentul in care un task personal se creeaza / muta / bifeaza / sterge.
#
# Forma:
#   - OAuth 2.0 web flow SERVER-SIDE (/oauth/google/start -> consent ->
#     /oauth/google/callback). Client id/secret stau in env
#     (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET); tokenurile in app_settings,
#     sub chei cu prefix `google_` — prefixul e contractul cu backup-ul, care
#     le EXCLUDE din JSON (vezi admin.backup_database), si cu restore-ul, care
#     le PASTREAZA peste stergerea tabelei.
#   - Sync ONE-WAY dashboard -> Google, in thread daemon best-effort, pe
#     tiparul obsidian.sync_project_frontmatter: un esec nu strica niciodata
#     cererea care l-a declansat; resync-ul vindeca.
#   - Doar stdlib (urllib) — fara dependente noi; timeout explicit pe fiecare
#     apel extern (regula codului).
#
# Un task bifat NU dispare din calendar (ales de Ion): titlul primeste „✓ ".
# Divergenta fata de feed-ul .ics (care exclude finalizatele) e INTENTIONATA.

import json
import hmac
import logging
import os
import re
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, redirect, request, session, url_for

from utils import login_required, get_app_setting, set_app_setting, get_json_or_400
from database import get_db, row_to_dict

logger = logging.getLogger(__name__)

google_bp = Blueprint('google', __name__)

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_REVOKE_URL = 'https://oauth2.googleapis.com/revoke'
GCAL_API = 'https://www.googleapis.com/calendar/v3'
# Scope granular: aplicatia poate crea calendare si administra DOAR ce a creat
# ea. Daca Google refuza scope-ul (403 la calendars.insert), fallback-ul e
# scope-ul complet 'https://www.googleapis.com/auth/calendar' — o constanta.
SCOPE = 'https://www.googleapis.com/auth/calendar.app.created'
CALENDAR_NAME = 'PIF Personal'
HTTP_TIMEOUT = 15

# Chei app_settings — TOATE cu prefix `google_` (vezi antetul).
K_REFRESH = 'google_refresh_token'
K_TOKEN = 'google_access_token'      # JSON: {"access_token": ..., "expires_at": epoch}
K_CALENDAR = 'google_calendar_id'
K_LAST_SYNC = 'google_last_sync'
K_LAST_ERROR = 'google_last_error'
# Credentialele OAuth pot veni si din UI (JSON-ul descarcat din consola,
# lipit in modal) — stau tot sub prefixul `google_`, deci excluse din backup
# si pastrate la restore. Env are PRIORITATE cand exista ambele surse.
K_CLIENT_ID = 'google_client_id'
K_CLIENT_SECRET = 'google_client_secret'
# GOOGLE_KEYS = ce sterge DISCONNECT. Credentialele NU sunt aici: deconectarea
# rupe legatura cu contul, nu deconfigureaza aplicatia — reconectarea ramane
# un singur click.
GOOGLE_KEYS = (K_REFRESH, K_TOKEN, K_CALENDAR, K_LAST_SYNC, K_LAST_ERROR)

DATA_RE = re.compile(r'^(\d{4})-(\d{2})-(\d{2})')


def _creds_sursa():
    """((client_id, client_secret), sursa) — env intai, apoi app_settings.
    (None, '') daca nu e configurat nicaieri."""
    cid = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
    sec = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()
    if cid and sec:
        return (cid, sec), 'env'
    cid = (get_app_setting(K_CLIENT_ID) or '').strip()
    sec = (get_app_setting(K_CLIENT_SECRET) or '').strip()
    if cid and sec:
        return (cid, sec), 'setari'
    return None, ''


def _creds():
    """(client_id, client_secret), sau None daca lipseste configurarea."""
    return _creds_sursa()[0]


def _redirect_uri():
    # ProxyFix (x_proto=1) da schema corecta in spatele tunelului Cloudflare.
    # Intrarea din consola Google trebuie sa fie EXACT acest URL.
    return url_for('google.oauth_callback', _external=True)


def sync_enabled():
    """Hook-urile intreaba AICI inainte sa porneasca vreun thread: un env-check
    gratuit + un SELECT local. Fara creds sau fara refresh token, sync-ul nu
    exista si taskurile nu platesc nimic."""
    return bool(_creds()) and bool(get_app_setting(K_REFRESH))


def _del_settings(keys):
    conn = get_db()
    cursor = conn.cursor()
    for k in keys:
        cursor.execute('DELETE FROM app_settings WHERE key = ?', (k,))
    conn.commit()
    conn.close()


def _http(method, url, payload=None, form=None, token=None):
    """Un apel HTTP cu timeout explicit. Intoarce (status, dict) — si pentru
    4xx/5xx (HTTPError se citeste, nu se arunca): apelantii ramifica pe cod.
    Niciun token si niciun body de eroare nu ajunge in logger de aici."""
    headers = {'Accept': 'application/json'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    elif form is not None:
        data = urllib.parse.urlencode(form).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            body = resp.read()
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read()
        status = e.code
    try:
        parsed = json.loads(body) if body else {}
    except ValueError:
        parsed = {}
    return status, parsed


def _access_token():
    """Access token valid, din cache sau prin refresh. None = neconectat.

    Doi workeri gunicorn pot face refresh simultan — Google tine valide mai
    multe access tokens si NU roteste refresh token-ul de web app, deci
    last-write-wins pe cache e inofensiv.
    """
    creds = _creds()
    refresh = get_app_setting(K_REFRESH)
    if not creds or not refresh:
        return None
    raw = get_app_setting(K_TOKEN)
    if raw:
        try:
            cached = json.loads(raw)
            if cached.get('expires_at', 0) - datetime.now().timestamp() > 60:
                return cached.get('access_token')
        except ValueError:
            pass
    status, body = _http('POST', GOOGLE_TOKEN_URL, form={
        'client_id': creds[0], 'client_secret': creds[1],
        'refresh_token': refresh, 'grant_type': 'refresh_token',
    })
    if status == 200 and body.get('access_token'):
        set_app_setting(K_TOKEN, json.dumps({
            'access_token': body['access_token'],
            'expires_at': datetime.now().timestamp() + int(body.get('expires_in', 3600)) - 30,
        }))
        return body['access_token']
    if body.get('error') == 'invalid_grant':
        # Acces revocat sau consent screen ramas in Testing (expira la 7 zile).
        # Starea devine „deconectat" cu explicatie, nu un esec mut.
        _del_settings((K_REFRESH, K_TOKEN))
        set_app_setting(K_LAST_ERROR, 'Conexiunea Google a expirat — reconectează.')
        logger.warning('Google: refresh token invalid (invalid_grant) — deconectat')
    else:
        logger.error('Google: refresh token a esuat cu status %s', status)
    return None


def _gcal(method, path, payload=None):
    """Apel autentificat la Calendar API. La 401 arunca cache-ul si mai
    incearca o data cu un token proaspat."""
    token = _access_token()
    if not token:
        return 0, {}
    status, body = _http(method, GCAL_API + path, payload=payload, token=token)
    if status == 401:
        _del_settings((K_TOKEN,))
        token = _access_token()
        if not token:
            return 401, body
        status, body = _http(method, GCAL_API + path, payload=payload, token=token)
    return status, body


def _event_id(task_id):
    # UUID-ul fara cratime e hex [0-9a-f], subset strict al alfabetului
    # base32hex cerut de Google pentru id-uri — deci id-ul evenimentului e
    # DETERMINIST din id-ul taskului si nu ne trebuie nicio tabela de mapare.
    return str(task_id).replace('-', '').lower()


def _event_body(row):
    m = DATA_RE.match(str(row.get('data_scadenta') or ''))
    if not m:
        return None
    start = m.group(0)
    # DTEND e exclusiv (aceeasi regula ca in exportul .ics): o zi = start+1.
    end = (datetime.strptime(start, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    prefix = '✓ ' if (row.get('status') == 'done') else ''
    return {
        'summary': prefix + (row.get('titlu') or 'Task'),
        'description': row.get('descriere') or '',
        'start': {'date': start},
        'end': {'date': end},
        # Mereu 'confirmed': patch-ul cu status confirmed REINVIE un eveniment
        # anulat — vezi comentariul despre 409 din _upsert_event.
        'status': 'confirmed',
        # CALENDARUL E OGLINDA, NU CLOPOT — si o spune EXPLICIT.
        #
        # Notificarile au un singur proprietar: aplicatia de pe telefon, care
        # pune alarma local (frontend/src/lib/notificari.js). Daca ar suna si
        # calendarul, acelasi task ar bate de doua ori — exact felul de dublura
        # despre care `blueprints/push.py` scrie ca „erodeaza increderea
        # definitiv", si care te invata sa ignori ambele canale.
        #
        # De ce `useDefault: False` cu lista GOALA, si nu campul lasat deoparte:
        # fara `reminders`, `useDefault` e implicit adevarat, deci evenimentul ia
        # mementourile implicite ale calendarului — pe care le poate schimba
        # oricine, oricand, din aplicatia Google Calendar, fara sa treaca pe
        # aici. Tacerea trebuie sa fie o decizie scrisa, nu o coincidenta.
        # (Pe 2026-08-07 implicitele erau goale, si tocmai de-aia doua taskuri
        # scadente a doua zi n-au anuntat nimic: se baza pe ele fara sa stie.)
        'reminders': {'useDefault': False, 'overrides': []},
    }


def _ensure_calendar():
    """Id-ul calendarului „PIF Personal", creat la nevoie."""
    cid = get_app_setting(K_CALENDAR)
    if cid:
        return cid
    status, body = _gcal('POST', '/calendars', {'summary': CALENDAR_NAME})
    if status == 200 and body.get('id'):
        set_app_setting(K_CALENDAR, body['id'])
        return body['id']
    logger.error('Google: crearea calendarului a esuat cu status %s', status)
    return None


def _upsert_event(cid, event_id, body):
    body = dict(body, id=event_id)
    status, resp = _gcal('POST', f'/calendars/{urllib.parse.quote(cid)}/events', body)
    if status == 409:
        # Google nu elibereaza NICIODATA un id de eveniment sters: ramane
        # `cancelled` si orice insert cu acelasi id da 409 pe veci. Patch-ul cu
        # status 'confirmed' il reinvie — fara asta, „scot data / o pun la loc"
        # s-ar rupe silentios.
        status, resp = _gcal(
            'PATCH',
            f'/calendars/{urllib.parse.quote(cid)}/events/{event_id}',
            dict(body))
    return status in (200, 201), status


def _delete_event(cid, event_id):
    status, _ = _gcal('DELETE', f'/calendars/{urllib.parse.quote(cid)}/events/{event_id}')
    # 404/410 = deja sters — succes pentru noi.
    return status in (200, 204, 404, 410), status


def _reconcile_row(cid, task_id, row):
    """UN singur drum de decizie, condus de rand: personal + data valida =>
    upsert; orice altceva (rand lipsa, munca, fara data) => delete. Acopera
    creare, mutare de termen, stergere de termen, bifare (retitrare cu ✓),
    debifare si flip de sfera prin API — fara cazuri speciale pe apelant."""
    eid = _event_id(task_id)
    wants = (row is not None and row.get('sfera') == 'personal'
             and _event_body(row) is not None)
    if not wants:
        ok, status = _delete_event(cid, eid)
        return ok
    ok, status = _upsert_event(cid, eid, _event_body(row))
    if status == 404:
        # 404 la UPSERT (spre deosebire de delete) inseamna ca a disparut
        # CALENDARUL (sters de utilizator in Google). Il recream si reincercam
        # o singura data.
        _del_settings((K_CALENDAR,))
        cid2 = _ensure_calendar()
        if cid2:
            ok, status = _upsert_event(cid2, eid, _event_body(row))
    return ok


def _mark_result(ok, detail=''):
    if ok:
        set_app_setting(K_LAST_SYNC, datetime.now().isoformat())
        set_app_setting(K_LAST_ERROR, '')
    else:
        set_app_setting(K_LAST_ERROR, detail or 'Sincronizarea cu Google a eșuat — vezi logurile.')


def spawn_sync(*task_ids):
    """Intrarea publica a hook-urilor din tasks.py. Se intoarce INSTANT;
    munca se face intr-un thread daemon, best-effort (tiparul
    obsidian.sync_project_frontmatter): un esec nu strica niciodata cererea
    care l-a declansat — resync-ul si urmatoarea modificare vindeca."""
    ids = [t for t in task_ids if t]
    if not ids:
        return

    def _work():
        try:
            cid = _ensure_calendar()
            if not cid:
                _mark_result(False)
                return
            ok = True
            conn = get_db()
            cursor = conn.cursor()
            for tid in ids:
                cursor.execute('SELECT * FROM global_tasks WHERE id = ?', (tid,))
                r = cursor.fetchone()
                row = row_to_dict(r) if r else None
                if not _reconcile_row(cid, tid, row):
                    ok = False
            conn.close()
            _mark_result(ok)
        except Exception:
            logger.exception('Google sync a esuat (best-effort)')
            try:
                _mark_result(False)
            except Exception:
                pass

    threading.Thread(target=_work, daemon=True).start()


def resync_all():
    """Reconciliere completa, BIDIRECTIONALA. Calendarul e creat de aplicatie,
    deci tot ce e in el e al nostru: un listing complet da starea remote, apoi
    (1) fiecare task personal se reconciliaza si (2) evenimentele fara task
    corespondent se sterg — orfanii lasati de hook-uri ratate (server cazut,
    esec best-effort) se vindeca aici."""
    cid = _ensure_calendar()
    if not cid:
        _mark_result(False)
        return

    remote_ids = set()
    page = ''
    while True:
        qs = '?maxResults=2500&showDeleted=false' + (f'&pageToken={urllib.parse.quote(page)}' if page else '')
        status, body = _gcal('GET', f'/calendars/{urllib.parse.quote(cid)}/events{qs}')
        if status != 200:
            logger.error('Google resync: listarea evenimentelor a esuat cu %s', status)
            _mark_result(False)
            return
        remote_ids.update(item.get('id') for item in body.get('items', []))
        page = body.get('nextPageToken') or ''
        if not page:
            break

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM global_tasks WHERE sfera = 'personal'")
    rows = [row_to_dict(r) for r in cursor.fetchall()]
    conn.close()

    ok = True
    local_ids = set()
    for row in rows:
        local_ids.add(_event_id(row['id']))
        if not _reconcile_row(cid, row['id'], row):
            ok = False
    for eid in remote_ids - local_ids:
        if eid and not _delete_event(cid, eid)[0]:
            ok = False
    _mark_result(ok)


def spawn_resync():
    def _work():
        try:
            resync_all()
        except Exception:
            logger.exception('Google resync a esuat (best-effort)')
            try:
                _mark_result(False)
            except Exception:
                pass
    threading.Thread(target=_work, daemon=True).start()


# ---------------------------------------------------------------------------
# Rute
# ---------------------------------------------------------------------------

def _spa(flag):
    """Redirect inapoi in SPA, in vederea personala, cu un semnal in query."""
    return redirect(f'/#/tasks?sfera=personal&google={flag}')


@google_bp.route('/oauth/google/start', methods=['GET'])
@login_required
def oauth_start():
    # In afara /api/: fara rate limit, iar o sesiune expirata ajunge la /login,
    # nu la un JSON 401 (utils.login_required ramifica pe prefix).
    creds = _creds()
    if not creds:
        return _spa('eroare')
    state = secrets.token_urlsafe(32)
    session['google_oauth_state'] = state
    params = urllib.parse.urlencode({
        'client_id': creds[0],
        'redirect_uri': _redirect_uri(),
        'response_type': 'code',
        'scope': SCOPE,
        # offline + consent: refresh token garantat si la RE-conectare
        # (altfel Google il omite la al doilea consent).
        'access_type': 'offline',
        'prompt': 'consent',
        'state': state,
    })
    return redirect(f'{GOOGLE_AUTH_URL}?{params}')


@google_bp.route('/oauth/google/callback', methods=['GET'])
def oauth_callback():
    # Fara @login_required: verificarea e manuala ca sa putem trimite browserul
    # inapoi in aplicatie cu un semnal, nu la un JSON. CSRF-ul fluxului e
    # parametrul `state` legat de sesiune (SameSite=Lax supravietuieste
    # redirectului GET top-level de la Google).
    if 'authenticated' not in session:
        return redirect(url_for('login_page'))
    expected = session.pop('google_oauth_state', '')
    got = request.args.get('state', '')
    if not expected or not got or not hmac.compare_digest(expected, got):
        logger.warning('Google OAuth: state invalid la callback')
        return _spa('eroare')
    code = request.args.get('code', '')
    creds = _creds()
    if not code or not creds:
        return _spa('eroare')
    try:
        status, body = _http('POST', GOOGLE_TOKEN_URL, form={
            'client_id': creds[0], 'client_secret': creds[1],
            'code': code, 'grant_type': 'authorization_code',
            'redirect_uri': _redirect_uri(),
        })
        if status != 200 or not body.get('refresh_token'):
            # Fara refresh token nu avem conexiune durabila — esec franc.
            logger.error('Google OAuth: schimbul de cod a esuat cu status %s', status)
            return _spa('eroare')
        set_app_setting(K_REFRESH, body['refresh_token'])
        set_app_setting(K_TOKEN, json.dumps({
            'access_token': body.get('access_token', ''),
            'expires_at': datetime.now().timestamp() + int(body.get('expires_in', 3600)) - 30,
        }))
        set_app_setting(K_LAST_ERROR, '')
        _ensure_calendar()
        spawn_resync()
        return _spa('conectat')
    except Exception:
        logger.exception('Google OAuth: callback a esuat')
        return _spa('eroare')


def _status_body():
    creds, sursa = _creds_sursa()
    return {
        'configurat': bool(creds),
        'sursa': sursa,
        'conectat': bool(get_app_setting(K_REFRESH)),
        'calendar': CALENDAR_NAME if get_app_setting(K_CALENDAR) else '',
        'last_sync': get_app_setting(K_LAST_SYNC, '') or '',
        'last_error': get_app_setting(K_LAST_ERROR, '') or '',
    }


@google_bp.route('/api/google/status', methods=['GET'])
@login_required
def google_status():
    """Starea conexiunii — NICIODATA tokenurile sau secretul de client."""
    return jsonify(_status_body())


@google_bp.route('/api/google/credentials', methods=['PUT'])
@login_required
def google_credentials():
    """Configurare fara SSH: Ion lipeste in modal JSON-ul OAuth descarcat din
    Google Cloud Console; credentialele se valideaza si intra in app_settings
    (prefixul `google_` le tine afara din backup). Env are prioritate — cand
    sursa e env, endpointul refuza, ca sa nu para ca a schimbat ceva ce nu
    poate schimba."""
    if _creds_sursa()[1] == 'env':
        return jsonify({'error': 'Credențialele vin din variabilele de mediu ale serverului — se schimbă acolo.'}), 400
    data = get_json_or_400()
    cid = (data.get('client_id') or '').strip()
    sec = (data.get('client_secret') or '').strip()
    raw = (data.get('json') or '').strip()
    if raw and not (cid and sec):
        try:
            parsed = json.loads(raw)
        except ValueError:
            return jsonify({'error': 'Fișierul lipit nu e JSON valid.'}), 400
        if 'installed' in parsed:
            return jsonify({'error': 'Ai creat un client de tip Desktop — creează unul de tip „Web application”.'}), 400
        web = parsed.get('web') if isinstance(parsed, dict) else None
        if not isinstance(web, dict):
            return jsonify({'error': 'JSON-ul nu are cheia „web” — descarcă fișierul clientului OAuth de tip Web application.'}), 400
        cid = (web.get('client_id') or '').strip()
        sec = (web.get('client_secret') or '').strip()
        # Fail-early: daca redirect_uris exista si nu contine callback-ul
        # nostru, OAuth ar pica abia la Google, cu un ecran criptic.
        uris = web.get('redirect_uris')
        if isinstance(uris, list) and uris and _redirect_uri() not in uris:
            return jsonify({'error': f'Adaugă în consola Google, la „Authorized redirect URIs”, exact: {_redirect_uri()}'}), 400
    if not cid or not sec:
        return jsonify({'error': 'Lipsesc client_id sau client_secret.'}), 400
    set_app_setting(K_CLIENT_ID, cid)
    set_app_setting(K_CLIENT_SECRET, sec)
    # Raspunsul are forma statusului, ca clientul sa o asigneze direct.
    return jsonify(_status_body())


@google_bp.route('/api/google/resync', methods=['POST'])
@login_required
def google_resync():
    if not sync_enabled():
        return jsonify({'error': 'Google Calendar nu e conectat.'}), 400
    spawn_resync()
    return jsonify({'message': 'Resincronizare pornită'}), 202


@google_bp.route('/api/google/disconnect', methods=['POST'])
@login_required
def google_disconnect():
    refresh = get_app_setting(K_REFRESH)
    if refresh:
        # Revocarea e best-effort: si daca esueaza, tokenurile locale pleaca.
        try:
            _http('POST', GOOGLE_REVOKE_URL, form={'token': refresh})
        except Exception:
            pass
    # Calendarul si evenimentele RAMAN in Google — sunt datele utilizatorului.
    _del_settings(GOOGLE_KEYS)
    return jsonify({'message': 'Deconectat'})

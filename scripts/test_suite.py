#!/usr/bin/env python3
"""Probele de API: invariantii care se vad doar prin HTTP, pe un server de UNICA FOLOSINTA.

Porneste singur aplicatia (`scripts/banc.py`), pe o baza NOUA, cu PIN-ul de proba —
deci nu cere nimic pregatit, nu atinge `pif_dashboard.db` si ruleaza in poarta.

CE A PLECAT DE AICI PE 2026-09-28, si de ce (auditul testelor):
  - `js_function_check` si `api_route_check` scanau `static/app.js`, `core.js`,
    `mobile.js`, sterse din iunie: ieseau „PASS" oricum, fara sa citeasca nimic;
  - `undefined_names_check` era pyflakes a doua oara — `scripts/lint.py` il ruleaza
    pe tot proiectul, nu doar pe 13 fisiere;
  - `db_table_check` si `data_integrity` citeau copia LOCALA a bazei (gitignored,
    veche) — despre cod nu spuneau nimic. Schema pe o baza goala o verifica acum
    `teste/test_migrari.py`;
  - partea de notificari care nu trece prin HTTP (logica zilnica, tokenul, cheia
    VAPID, `send_to_all`) e in `teste/test_push.py`. Aici statea in spatele unui
    login, iar curatenia ei stergea TOATE cheile `push_*` din baza pe care o gasea —
    pe server, asta ar fi oprit notificarile fara niciun semn.
Si serverul pe :5000 + PIN-ul real din mediu + cate un login pe proba: cu limita de
5 logari / 5 minute (`app.py`), un login din browser in aceleasi cinci minute pica
probele de la coada cu 429. Acum: server propriu, un singur login.

RULARE
    python scripts/test_suite.py
Iesire: 0 curat, 1 abatere, 2 instrumentul (serverul n-a pornit etc.) — vezi banc.py.
"""

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banc  # noqa: E402
from banc import out  # noqa: E402

try:
    import requests
except ImportError:  # pragma: nu pe masina de dezvoltare
    requests = None

R = banc.Raport()
APP = None          # banc.Aplicatia pornita in main()


def url(cale):
    return APP.baza + cale


def sectiune(titlu):
    out('\n--- %s ---' % titlu)


def sesiune():
    """UN singur login pentru toata suita (vezi antetul: limita de 5 / 5 minute)."""
    s = requests.Session()
    r = s.post(url('/login'), json={'pin': banc.PIN_TEST}, timeout=5)
    if r.status_code != 200:
        raise banc.InstrumentStricat('login pe serverul de proba -> %d' % r.status_code)
    return s


def hdr(s):
    # Double-submit CSRF: cookie-ul se citeste si se intoarce in header.
    return {'X-CSRF-Token': s.cookies.get('csrf_token', '')}


# ---------------------------------------------------------------------- probe

def api_smoke(s):
    sectiune('RUTELE DE BAZA')
    r = requests.get(url('/api/healthz'), timeout=5)
    R.bifa(r.status_code == 200, 'GET /api/healthz -> 200', 'a raspuns %d' % r.status_code)
    for ep in ('/api/proiecte', '/api/global-tasks', '/api/clienti', '/api/stats'):
        r = s.get(url(ep), timeout=5)
        R.bifa(r.status_code == 200, 'GET %s -> 200' % ep, 'a raspuns %d' % r.status_code)


def sfera(s):
    """Sferele (munca/personal, v38) — modul de esec e SCURGEREA: o interogare pe
    global_tasks fara filtru varsa personalul intr-o suprafata de munca. Fiecare
    asertie de aici corespunde unei suprafete."""
    sectiune('SFERA (munca/personal)')
    today = date.today().isoformat()
    creat = []
    try:
        r = s.post(url('/api/global-tasks'), headers=hdr(s), timeout=5,
                   json={'titlu': '__proba_sfera_azi__', 'sfera': 'personal',
                         'status': 'to_do', 'data_scadenta': today})
        if r.status_code != 201:
            R.pica('POST task personal', 'a raspuns %d' % r.status_code)
            return
        pid = r.json()['id']
        creat.append(pid)
        r = s.post(url('/api/global-tasks'), headers=hdr(s), timeout=5,
                   json={'titlu': '__proba_sfera_fara_termen__', 'sfera': 'personal', 'status': 'to_do'})
        pid2 = r.json()['id']
        creat.append(pid2)

        # 1) Lista implicita e doar munca; `?sfera=personal` le aduce pe ale lui.
        ids_implicit = {t['id'] for t in s.get(url('/api/global-tasks'), timeout=5).json()}
        ids_pers = {t['id'] for t in s.get(url('/api/global-tasks?sfera=personal'), timeout=5).json()}
        R.bifa(pid not in ids_implicit and pid2 not in ids_implicit,
               '/api/global-tasks (implicit) nu contine personalul', 'personalul SCURGE in lista de munca')
        R.bifa(pid in ids_pers and pid2 in ids_pers,
               '?sfera=personal intoarce personalul', 'taskurile personale lipsesc')

        # 2) Valoare necunoscuta -> 400 (fail-closed, nu coercitie)
        r = s.get(url('/api/global-tasks?sfera=xyz'), timeout=5)
        R.bifa(r.status_code == 400, '?sfera=xyz -> 400', 'a raspuns %d' % r.status_code)

        # 3) Boardul Astazi: personal in `personale`, nu in `items`
        ag = s.get(url('/api/agenda/today?today=%s' % today), timeout=5).json()
        in_items = any(x['id'] == pid for x in ag.get('items', []))
        in_pers = any(x['id'] == pid for x in ag.get('personale', []))
        if in_items:
            R.pica('agenda/today', 'personalul SCURGE in `items` (boardul de munca)')
        else:
            R.bifa(in_pers, 'agenda/today: personalul in `personale`, nu in `items`',
                   'taskul personal scadent azi lipseste din `personale`')

        # 4) Pickerul boardului de munca nu ofera taskuri personale
        cand = s.get(url('/api/agenda/candidates?today=%s' % today), timeout=5).json()
        R.bifa(not any(x['id'] == pid2 for x in cand.get('items', [])),
               'agenda/candidates exclude personalul', 'personalul SCURGE in picker')

        # 5) Taskurile zilei din Calendar sunt doar munca — CU MARTOR. O proba
        #    negativa („nu apare X") trece si cand interogarea n-a intors NIMIC
        #    (fereastra gresita, alt camp, ruta mutata). Deci un task de MUNCA scadent
        #    azi trebuie sa APARA, iar cel personal din aceeasi zi sa NU apara.
        r = s.post(url('/api/global-tasks'), headers=hdr(s), timeout=5,
                   json={'titlu': '__proba_sfera_martor_munca__', 'sfera': 'munca',
                         'status': 'to_do', 'data_scadenta': today})
        wid = r.json()['id'] if r.status_code == 201 else None
        if wid:
            creat.append(wid)
        cal = s.get(url('/api/calendar?start=%s&zile=7' % today), timeout=5).json()
        cal_ids = {t['id'] for t in cal.get('taskuri', [])}
        if not wid or wid not in cal_ids:
            R.pica('/api/calendar', 'nu intoarce martorul de munca scadent azi — proba n-a verificat sfera')
        else:
            R.bifa(pid not in cal_ids, '/api/calendar: munca da, personal nu', 'personalul SCURGE in calendar')

        # 6) Recurenta pastreaza sfera (altfel taskul migreaza la munca la bifare)
        r = s.post(url('/api/global-tasks'), headers=hdr(s), timeout=5,
                   json={'titlu': '__proba_sfera_recurenta__', 'sfera': 'personal',
                         'status': 'to_do', 'data_scadenta': today, 'recurenta': 'zilnic'})
        rid = r.json()['id']
        creat.append(rid)
        r = s.put(url('/api/global-tasks/%s' % rid), headers=hdr(s), timeout=5, json={'status': 'done'})
        nou = r.json().get('recurring_spawned')
        if not nou:
            R.pica('recurenta personala', 'nu s-a generat urmatoarea aparitie')
        else:
            creat.append(nou)
            sp = s.get(url('/api/global-tasks/%s' % nou), timeout=5).json()
            R.bifa(sp.get('sfera') == 'personal', 'aparitia noua pastreaza sfera',
                   'a ajuns in %s' % sp.get('sfera'))
    finally:
        for tid in creat:
            try:
                s.delete(url('/api/global-tasks/%s' % tid), headers=hdr(s), timeout=5)
            except Exception:
                pass


def proiect_inchis(s):
    """Ce trimite un proiect INCHIS pe „Astazi", in pickerul lui si in panoul zilei:
    doar ce s-a adaugat in el DUPA inchidere (`TASK_PROIECT_VIU`, utils.py).

    CU MARTOR in ambele sensuri: taskul nou trebuie sa APARA — altfel o absenta a
    celui vechi n-ar dovedi nimic — iar cel vechi sa NU apara. „Vechi" se face
    impingand `created_at` inapoi direct in baza: prin API nu se poate, si exact data
    adaugarii deosebeste un rest al lucrarii de urmarea ei. Scrie DOAR in baza
    serverului de proba (`APP.db`)."""
    sectiune('PROIECT INCHIS (ce trimite pe Astazi)')
    today = date.today().isoformat()
    pid = None
    try:
        r = s.post(url('/api/proiecte'), headers=hdr(s), timeout=5,
                   json={'nume': '__proba_proiect_inchis__', 'status': 'pregatire'})
        if r.status_code not in (200, 201):
            R.pica('POST proiect', 'a raspuns %d' % r.status_code)
            return
        pid = r.json().get('id')

        def task(titlu, **extra):
            r = s.post(url('/api/proiecte/%s/tasks' % pid), headers=hdr(s), timeout=5,
                       json=dict({'titlu': titlu, 'status': 'to_do'}, **extra))
            return r.json().get('id')

        vechi = task('__proba_rest_cu_termen__', data_scadenta=today)
        vechi_fara = task('__proba_rest_fara_termen__')
        c = sqlite3.connect(APP.db)
        c.execute('UPDATE tasks SET created_at = ? WHERE id IN (?, ?)',
                  ((datetime.now() - timedelta(days=10)).isoformat(), vechi, vechi_fara))
        c.commit()
        c.close()

        r = s.put(url('/api/proiecte/%s' % pid), headers=hdr(s), timeout=5, json={'status': 'finalizat'})
        if r.status_code != 200:
            R.pica('PUT finalizat', 'a raspuns %d' % r.status_code)
            return
        nou = task('__proba_urmare_azi__', data_scadenta=today)
        nou_fara = task('__proba_urmare_fara_termen__')

        def idset(cale, cheie=None):
            j = s.get(url(cale), timeout=5).json()
            return {x['id'] for x in (j.get(cheie, []) if cheie else j)}

        for nume, ids, martor, rest in [
            ('agenda/today', idset('/api/agenda/today?today=%s' % today, 'items'), nou, vechi),
            ('agenda/candidates', idset('/api/agenda/candidates?today=%s' % today, 'items'), nou_fara, vechi_fara),
            ('calendar', idset('/api/calendar?start=%s&zile=7' % today, 'taskuri'), nou, vechi),
        ]:
            if martor not in ids:
                R.pica(nume, 'nu arata taskul adaugat DUPA inchidere')
            else:
                R.bifa(rest not in ids, '%s: urmarea da, restul nu' % nume,
                       'scoate la iveala un rest de dinainte de inchidere')

        # Fisa proiectului le arata pe toate: acolo se curata resturile.
        R.bifa({vechi, vechi_fara, nou, nou_fara} <= idset('/api/proiecte/%s/tasks' % pid),
               'fisa proiectului arata si resturile, si urmarea', 'lipsesc taskuri din fisa')
    finally:
        if pid:
            try:
                s.delete(url('/api/proiecte/%s' % pid), headers=hdr(s), timeout=5)
            except Exception:
                pass


def backup_secrete(s):
    """Backup-ul nu scurge chei `push_*` (cheia VAPID privata + abonamentele). Cheia
    falsa se scrie in baza serverului de proba — niciodata in cea de lucru."""
    sectiune('BACKUP (secretele nu pleaca de pe masina)')
    c = sqlite3.connect(APP.db)
    try:
        c.execute("INSERT OR REPLACE INTO app_settings (key, value, updated_at) "
                  "VALUES ('push_vapid_private', 'FALS-PUSH-TEST', '')")
        c.commit()
    finally:
        c.close()
    bk = s.get(url('/api/backup'), timeout=15).json()
    chei = {r0.get('key') for r0 in bk.get('app_settings', [])}
    scurse = {k for k in chei if str(k).startswith('push_')}
    R.bifa(not scurse, 'backup-ul exclude cheile push_*', 'SCURGE %s' % sorted(scurse))
    R.bifa('FALS-PUSH-TEST' not in json.dumps(bk), 'backup-ul nu contine valoarea secretului',
           'valoarea cheii private e in backup')


def push_http(s):
    """Partea de notificari care trece prin HTTP. Restul (logica zilnica, tokenul,
    lantul de trimitere) e in `teste/test_push.py`, in proces."""
    sectiune('NOTIFICARI PUSH (rutele)')
    st = s.get(url('/api/push/status'), timeout=5)
    if st.status_code != 200:
        R.pica('/api/push/status', 'a raspuns %d' % st.status_code)
    else:
        j = st.json()
        # Baza e noua, deci ora e cea implicita — nu setarea cuiva.
        R.bifa(j.get('ora') == '08:00' and 'abonamente' in j and 'disponibil' in j,
               'status: ora implicita 08:00, abonamente, disponibil',
               'raspuns %s' % {k: j.get(k) for k in ('ora', 'abonamente', 'disponibil')})

    k1 = s.get(url('/api/push/vapid-public'), timeout=5)
    if k1.status_code == 503:
        R.nota('pywebpush lipseste pe masina asta — cheia VAPID si abonarea nu s-au probat')
    elif k1.status_code != 200:
        R.pica('/api/push/vapid-public', 'a raspuns %d' % k1.status_code)
    else:
        # Cheia VAPID e STABILA (regenerarea ar invalida abonamentele in tacere)
        k2 = s.get(url('/api/push/vapid-public'), timeout=5)
        cheie = k1.json().get('cheie', '')
        R.bifa(bool(cheie) and cheie == k2.json().get('cheie'), 'cheia VAPID e stabila intre apeluri')

        sub = {'endpoint': 'https://fcm.googleapis.com/fake/T1',
               'keys': {'p256dh': 'cheie-falsa', 'auth': 'auth-fals'}}

        def nr():
            return s.get(url('/api/push/status'), timeout=5).json()['abonamente']
        n0 = nr()
        s.post(url('/api/push/subscribe'), headers=hdr(s), json=sub, timeout=5)
        n1 = nr()
        s.post(url('/api/push/subscribe'), headers=hdr(s), json=sub, timeout=5)
        n2 = nr()
        R.bifa(n1 == n0 + 1 and n2 == n1, 'abonarea: al doilea POST e upsert, nu duplicat',
               '%d -> %d -> %d' % (n0, n1, n2))
        bad = s.post(url('/api/push/subscribe'), headers=hdr(s), json={'endpoint': 'nu-e-https'}, timeout=5)
        R.bifa(bad.status_code == 400, 'abonare invalida -> 400', 'a raspuns %d' % bad.status_code)
        s.post(url('/api/push/unsubscribe'), headers=hdr(s), json={'endpoint': sub['endpoint']}, timeout=5)
        n3 = nr()
        R.bifa(n3 == n0, 'dezabonarea intoarce numarul la %d' % n0, 'a ramas %d' % n3)
        if n3 == 0:
            # Un „test reusit" trimis catre nimeni ar fi o minciuna.
            t = s.post(url('/api/push/test'), headers=hdr(s), json={}, timeout=5)
            R.bifa(t.status_code == 400, 'testul fara abonamente -> 400', 'a raspuns %d' % t.status_code)

    # Ruta de actiune din notificare: FARA header CSRF (service worker-ul nu poate
    # citi cookie-ul), dar tokenul trebuie sa fie bun — pinneaza exceptia din csrf.py.
    rej = s.post(url('/api/push/action'), json={'token': 'gunoi', 'action': 'done'}, timeout=5)
    R.bifa(rej.status_code == 403, 'actiune cu token invalid -> 403', 'a raspuns %d' % rej.status_code)
    R.bifa('CSRF' not in rej.text, 'actiunea e scutita de CSRF (a ajuns la validarea tokenului)',
           'a fost oprita de CSRF, nu de token')


# ----------------------------------------------------------------------- main

def main():
    global APP
    if requests is None:
        raise banc.InstrumentStricat('lipseste `requests` (pip install requests)')
    out('PROBELE DE API — server de unica folosinta, baza noua')
    with banc.Aplicatia(noua=True, prefix='pif-suita-') as app:
        APP = app
        s = sesiune()
        for proba in (api_smoke, sfera, proiect_inchis, backup_secrete, push_http):
            proba(s)
        cod = R.incheie()
        if cod:
            urme = app.urme()
            if urme:
                out('\n--- din logul serverului ---')
                for l in urme:
                    out('  ' + l)
        return cod


if __name__ == '__main__':
    sys.exit(banc.ruleaza(main))

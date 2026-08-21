#!/usr/bin/env python3
"""Foaia de pe telefon: trepte, viteza, voal.

De ce exista, separat de `audit_mobil.py`: acolo se masoara GEOMETRIA in repaus
(ce iese din ecran, ce tinta e prea mica). Aici se masoara ce face foaia CAT TIMP
DEGETUL E PE EA — si exact acolo statea greseala pe care fisierul asta o pazeste:
foaia se intindea printr-un prag IREVERSIBIL, deci dupa prima tragere in sus
singurul drum inapoi era inchiderea. Nu se vede din nicio captura si nu cade
niciun build; se vede doar tragand.

Trei contracte, fiecare cu un mod de esec pe care l-a avut aplicatia:
  1. drumul e continuu in AMBELE sensuri — din treapta de sus se coboara inapoi
     pe cea de baza, nu doar spre inchidere;
  2. pragul asculta VITEZA — o aruncare scurta si iute inchide, o tragere lunga
     si lenesa pana in acelasi loc nu;
  3. voalul URMARESTE degetul — cat timp foaia coboara, opacitatea scade odata
     cu ea, altfel gestul nu e reversibil cu ochii.

Porneste singur aplicatia, pe un port liber si pe o baza de unica folosinta —
acelasi tipar ca `smoke_ui.py`, ca sa nu ceara nimic pregatit dinainte.
"""

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIN_TEST = '000000'
TELEFON = {'width': 390, 'height': 844}

esecuri = []
note = []


def out(s=''):
    sys.stdout.buffer.write((str(s) + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


def bifa(ok, eticheta, detaliu='', nota=''):
    """`detaliu` explica ESECUL, `nota` insoteste reusita — altfel randul verde
    ajunge sa poarte textul unei probleme care nu s-a intamplat."""
    coada = nota if ok else detaliu
    out('  %-5s %s%s' % ('OK' if ok else 'PICA', eticheta, ('  — %s' % coada) if coada else ''))
    if not ok:
        esecuri.append('%s — %s' % (eticheta, detaliu))


def port_liber():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def seamana(cale):
    """Un proiect si cateva taskuri — foaia trebuie sa aiba CE arata.

    Cu baza goala fiecare proba de gest se sare, si atunci scriptul raporteaza
    verde fara sa fi tras de nimic. Datele se scriu prin schema initializata de
    `database.init_db()`, deci nu dubleaza definitia coloanelor.
    """
    sys.path.insert(0, RADACINA)
    os.environ['PIF_DB_PATH'] = cale
    import database
    database.init_db()
    import uuid
    db = sqlite3.connect(cale)
    # Cheile sunt UUID-uri de aplicatie (`id TEXT PRIMARY KEY`), nu autoincrement:
    # scrise fara ele, randurile intra cu `id` NULL si lista ramane goala.
    pid = str(uuid.uuid4())
    db.execute("INSERT INTO proiecte (id, nume, client, tip, status) VALUES (?,?,?,?,?)",
               (pid, 'Retrofit linie ambalare', 'Fabrica 2', 'retrofit', 'pregatire'))
    titluri = [
        'Verifică parametrii Danfoss FC302',
        'Comandă cablu ecranat 4×2,5',
        'Trimite raport PIF — hala 2',
        'Programează recepția cu beneficiarul',
        'Actualizează schema de forță',
        'Test la sarcină — pompa P-102',
        'Instruire operatori',
    ]
    for t in titluri:
        db.execute("INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta) VALUES (?,?,?,?,?)",
                   (str(uuid.uuid4()), pid, t, 'to_do', '2026-08-16'))
    # Pagina /taskuri arata taskurile GLOBALE, nu pe cele de proiect — iar foaia
    # care se deschide dintr-un rand de acolo e cea mai folosita din aplicatie.
    # `sfera` ramane implicit `munca`: la citire, doar aia se intoarce.
    for t in titluri:
        db.execute("INSERT INTO global_tasks (id, titlu, status, categorie, data_scadenta)"
                   " VALUES (?,?,?,?,?)",
                   (str(uuid.uuid4()), t, 'to_do', 'General', '2026-08-16'))
    # Candidati pentru „Adauga task existent": `/api/agenda/candidates` intoarce
    # doar taskuri FARA termen sau cu termen in VIITOR. Fara ei foaia se deschide
    # goala, si proba de la capat n-ar masura nimic.
    for i, t in enumerate(['Revizuie oferta Siemens', 'Curata panoul de comanda',
                           'Comanda senzori PT100', 'Scrie procedura de pornire',
                           'Verifica stocul de sigurante', 'Programeaza service anual']):
        db.execute("INSERT INTO global_tasks (id, titlu, status, categorie, data_scadenta)"
                   " VALUES (?,?,?,?,?)",
                   (str(uuid.uuid4()), t, 'to_do', 'General',
                    None if i % 2 else '2026-09-%02d' % (i + 3)))
    db.commit()
    db.close()


def porneste_serverul(port, db_temp, cale_log):
    env = dict(os.environ)
    env.update({
        'PIF_DB_PATH': db_temp,
        'PIF_DASHBOARD_PIN': PIN_TEST,
        'SESSION_COOKIE_SECURE': 'false',
        'PIF_RATE_LIMIT': '100000',
        'PYTHONIOENCODING': 'utf-8',
    })
    cod = ('from app import app\n'
           'app.run(host="127.0.0.1", port=%d, debug=False, use_reloader=False, threaded=True)\n' % port)
    log = open(cale_log, 'wb')
    proc = subprocess.Popen([sys.executable, '-c', cod], cwd=RADACINA, env=env,
                            stdout=log, stderr=subprocess.STDOUT)
    baza = 'http://127.0.0.1:%d' % port
    for _ in range(120):
        if proc.poll() is not None:
            log.close()
            out(open(cale_log, encoding='utf-8', errors='replace').read()[-3000:])
            raise SystemExit('Serverul a murit la pornire.')
        try:
            urllib.request.urlopen(baza + '/login', timeout=1).read()
            return proc, baza
        except urllib.error.HTTPError:
            return proc, baza
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise SystemExit('Serverul nu a pornit in 60s.')


# ---------- masuratori in pagina ----------

MASOARA = """() => {
  const f = document.querySelector('.modal.sheet');
  const v = document.querySelector('.backdrop');
  if (!f) return null;
  const r = f.getBoundingClientRect();
  const st = getComputedStyle(v);
  return {
    sus: Math.round(r.top),
    vizibil: Math.round(window.innerHeight - r.top),
    intins: f.classList.contains('intins'),
    gest: f.classList.contains('gest'),
    voal: st.backgroundColor,
    voalP: parseFloat(getComputedStyle(v).getPropertyValue('--voal-p') || '1'),
  };
}"""


# `.fa-rand` = randul unui task EXISTENT din foaia de adaugare
# (`components/FoaieAdauga.svelte`). Era `.pk-rand`, din `TaskPickerModal`, care a
# fost inlocuit pe 2026-08-17 (handoff „Rafinare aplicație mobilă TORQA", P3): cele
# trei drumuri de adaugare — cautarea din „Astăzi", formularul din /tasks si linia
# inline din proiect — au devenit o singura foaie. Contractul verificat aici NU s-a
# schimbat: foaia se ridica cu lista deja in mana si nu-si cheama singura tastatura.
# Randul de CREARE (`.fa-creeaza`) nu se numara: el exista si cand nu s-a incarcat
# nimic, deci l-ar face testul sa treaca degeaba.
STARE_ALEGERE = """() => {
  const a = document.activeElement;
  const f = document.querySelector('.modal.sheet');
  return {
    tag: a ? a.tagName : null,
    editabil: !!a && (a.tagName === 'INPUT' || a.tagName === 'TEXTAREA' || a.isContentEditable),
    randuri: document.querySelectorAll('.fa-rand').length,
    sus: f ? Math.round(f.getBoundingClientRect().top) : null,
  };
}"""

SUS_FOAIE = """() => {
  const f = document.querySelector('.modal.sheet');
  return f ? Math.round(f.getBoundingClientRect().top) : null;
}"""


def alfa(culoare):
    """Opacitatea unei culori calculate.

    DOUA formate, nu unul: `color-mix()` face browserul sa raporteze
    `color(srgb r g b / a)`, nu `rgba(r, g, b, a)`. Citit ca rgba, al patrulea
    numar din forma `color()` e canalul ALBASTRU — deci proba masura albastrul si
    raporta ca voalul nu se schimba, desi se schimba. Alfa sta dupa `/` cand
    exista `/`, si pe pozitia a patra altfel.
    """
    if not culoare or '(' not in culoare:
        return 0.0
    corp = culoare[culoare.index('(') + 1:culoare.rindex(')')]
    if '/' in corp:
        return float(corp.split('/')[-1].strip())
    nrs = corp.replace(',', ' ').split()
    return float(nrs[3]) if len(nrs) > 3 else 1.0


# ---------- degetul ----------
# ATINGERE ADEVARATA, prin `Input.dispatchTouchEvent` — nu `page.mouse`.
# Mouse-ul lui Playwright emite `pointerType: 'mouse'`, iar `trageJos` iese exact
# pe conditia asta (pe desktop foaia n-are gest, are `X`). Cu mouse-ul, gestul nu
# porneste deloc: cursorul urca peste voal, `mouseup` devine click pe voal si
# foaia se inchide — adica proba ar raporta „s-a inchis" pentru un gest care nici
# n-a existat. Acelasi tipar ca in `audit_mobil.py`.

def _pct(x, y):
    return {'touchPoints': [{'x': x, 'y': y, 'id': 1, 'radiusX': 6, 'radiusY': 6, 'force': 1}]}


def apuca(cdp, x, y):
    cdp.send('Input.dispatchTouchEvent', dict(type='touchStart', **_pct(x, y)))


def misca(cdp, x, y):
    cdp.send('Input.dispatchTouchEvent', dict(type='touchMove', **_pct(x, y)))


def ridica(cdp, page, pauza=650):
    cdp.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))
    page.wait_for_timeout(pauza)


def trage(page, cdp, x, y, pasi, dt=16):
    """O tragere cu pauze intre cadre — deget lenes."""
    apuca(cdp, x, y)
    for dy in pasi:
        y += dy
        misca(cdp, x, y)
        page.wait_for_timeout(dt)
    ridica(cdp, page)


def zvarle(page, cdp, x, y, distanta):
    """Pornire scurta si lenta, apoi o aruncare fara pauze — deget grabit.
    Aceeasi DISTANTA ca la `trage`, alta viteza: exact perechea care arata ca
    pragul nu mai e doar distanta."""
    apuca(cdp, x, y)
    misca(cdp, x, y + 20)
    page.wait_for_timeout(40)
    for k in range(1, 6):
        misca(cdp, x, y + 20 + (distanta - 20) * k / 5)
    ridica(cdp, page)


def deschide_foaia(page, baza):
    """Foaia taskului, de pe /tasks: e cea mai folosita din aplicatie."""
    page.goto(baza + '/#/tasks', wait_until='load')
    page.wait_for_timeout(1200)
    randuri = page.query_selector_all('.gl-fata')
    if not randuri:
        return False
    randuri[0].click()
    page.wait_for_timeout(700)
    return page.query_selector('.modal.sheet') is not None


def main():
    from playwright.sync_api import sync_playwright

    lucru = tempfile.mkdtemp(prefix='pif-foaie-')
    db = os.path.join(lucru, 'proba.db')
    seamana(db)
    port = port_liber()
    proc, baza = porneste_serverul(port, db, os.path.join(lucru, 'server.log'))

    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport=TELEFON, has_touch=True, is_mobile=True)
            page = ctx.new_page()
            cdp = ctx.new_cdp_session(page)
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', PIN_TEST)
            page.press('#pin', 'Enter')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)

            # ===== 1. TREPTELE, PE FOAIA CARE LE ARE MEREU =====
            # Foaia zilei din Calendar se deschide cu `inalt`, deci are
            # intotdeauna doua trepte (mijloc si ecran plin) — indiferent cat
            # continut e in ea. Pe ea se vede contractul care lipsea: din treapta
            # de sus exista drum INAPOI, nu doar spre inchidere.
            out('\n--- foaia zilei (Calendar): drum in ambele sensuri ---')
            page.goto(baza + '/#/calendar', wait_until='load')
            page.wait_for_timeout(1500)
            zi = page.query_selector('[data-zi]')
            if zi is None:
                bifa(False, 'grila de calendar se randeaza', 'nicio celula [data-zi]')
            else:
                zi.click()
                page.wait_for_timeout(800)
                mij0 = page.evaluate(MASOARA)
                # Ion, 2026-08-21: „nu se poate sa apara din prima pe toata
                # pagina" — `inalt` a ajuns sa insemne „doua trepte", iar
                # deschiderea e pe cea de MIJLOC; sus se ajunge dintr-un gest.
                bifa(mij0 is not None and not mij0['intins']
                     and 0.45 * TELEFON['height'] < mij0['vizibil'] < 0.7 * TELEFON['height'],
                     'se deschide pe treapta de MIJLOC (`inalt` = doua trepte)',
                     'nu s-a deschis' if mij0 is None else 'intins=%s, %s px' % (mij0['intins'], mij0['vizibil']),
                     '%s px' % (mij0 and mij0['vizibil']))
                sus = None
                if mij0:
                    cap_ = page.query_selector('.modal-header').bounding_box()
                    x = cap_['x'] + cap_['width'] / 2
                    # In sus: foaia urca pe treapta de sus.
                    trage(page, cdp, x, cap_['y'] + cap_['height'] / 2, [-25] * 8)
                    sus = page.evaluate(MASOARA)
                    bifa(sus is not None and sus['intins'],
                         'trasa in sus, urca pe treapta de sus',
                         'inchisa' if sus is None else 'intins=%s' % sus['intins'],
                         '%s -> %s px' % (mij0['vizibil'], sus and sus['vizibil']))

                if sus:
                    cap_ = page.query_selector('.modal-header').bounding_box()
                    x = cap_['x'] + cap_['width'] / 2
                    # Coborare LENTA de ~200px: sub pragul de inchidere, dar peste
                    # jumatatea drumului spre treapta de mijloc.
                    trage(page, cdp, x, cap_['y'] + cap_['height'] / 2, [25] * 8)
                    mij = page.evaluate(MASOARA)
                    bifa(mij is not None,
                         'coborata din treapta de sus, foaia NU se inchide',
                         'a disparut — asta era comportamentul de dinainte',
                         'a ramas deschisa')
                    if mij:
                        bifa(not mij['intins'] and mij['vizibil'] < sus['vizibil'] - 100,
                             'se aseaza inapoi pe treapta de MIJLOC',
                             '%s -> %s px' % (sus['vizibil'], mij['vizibil']))

                        # ...si inapoi in sus. Drumul e continuu in ambele sensuri.
                        cap_ = page.query_selector('.modal-header').bounding_box()
                        trage(page, cdp, x, cap_['y'] + cap_['height'] / 2, [-25] * 8)
                        inapoi = page.evaluate(MASOARA)
                        bifa(inapoi is not None and inapoi['intins'],
                             'urca la loc pe treapta de sus',
                             'inchisa' if inapoi is None else 'intins=%s' % inapoi['intins'],
                             '%s -> %s px' % (mij['vizibil'], inapoi and inapoi['vizibil']))

                    # ===== 2. VOALUL URMARESTE DEGETUL =====
                    # Se masoara IN TIMPUL gestului: dupa ridicare totul revine, deci
                    # o masuratoare de dupa n-ar spune nimic.
                    out('\n--- voalul urmareste degetul ---')
                    if page.query_selector('.modal.sheet'):
                        cap_ = page.query_selector('.modal-header').bounding_box()
                        y = cap_['y'] + cap_['height'] / 2
                        apuca(cdp, x, y)
                        a_sus = alfa(page.evaluate(MASOARA)['voal'])
                        # Pana SUB treapta de jos: intre trepte voalul e intreg
                        # cu buna stiinta (nu pierzi nimic mutandu-te intre ele),
                        # si abia sub cea de jos incepe sa se stinga.
                        for i in range(1, 24):
                            misca(cdp, x, y + i * 22)
                            page.wait_for_timeout(16)
                        m_jos = page.evaluate(MASOARA)
                        a_jos = alfa(m_jos['voal'])
                        bifa(a_jos < a_sus - 0.05, 'voalul se subtiaza odata cu foaia',
                             'alfa %.2f -> %.2f (p=%.2f)' % (a_sus, a_jos, m_jos['voalP']))
                        bifa(m_jos['gest'],
                             'inaltimea e a gestului cat timp degetul e pe ecran',
                             'clasa .gest activa')
                        ridica(cdp, page)
                        dupa = page.evaluate(MASOARA)
                        if dupa:
                            bifa(alfa(dupa['voal']) >= a_sus - 0.02, 'voalul revine intreg',
                                 'alfa %.2f' % alfa(dupa['voal']))
                            bifa(not dupa['gest'],
                                 'inaltimea se preda inapoi CSS-ului la ridicare',
                                 'clasa .gest stinsa')

            # ===== 3. VITEZA: aceeasi distanta, doua rezultate =====
            out('\n--- viteza ---')
            if not deschide_foaia(page, baza):
                bifa(False, 'foaia taskului se deschide', 'niciun rand pe /tasks')
            else:
                m0 = page.evaluate(MASOARA)
                bifa(m0 is not None and m0['vizibil'] > 100,
                     'foaia taskului se deschide pe treapta de baza',
                     '%s px' % (m0 and m0['vizibil']))
                cap_ = page.query_selector('.modal-header').bounding_box()
                x = cap_['x'] + cap_['width'] / 2
                y = cap_['y'] + cap_['height'] / 2
                # 18% din inaltimea foii — sub pragul de 28%, deci distanta
                # singura NU trebuie sa inchida.
                distanta = int(m0['vizibil'] * 0.18)
                trage(page, cdp, x, y, [distanta // 8] * 8)
                lent = page.evaluate(MASOARA)
                bifa(lent is not None, 'tragere LENTA sub prag: foaia ramane',
                     '%s px, adica sub cei 28%%' % distanta)

                if lent is not None:
                    cap_ = page.query_selector('.modal-header').bounding_box()
                    zvarle(page, cdp, x, cap_['y'] + cap_['height'] / 2, distanta)
                    iute = page.evaluate(MASOARA)
                    bifa(iute is None,
                         'aruncare IUTE pe ACEEASI distanta: foaia pleaca',
                         'inca deschisa — pragul n-asculta viteza', 'inchisa')

            # ===== 4. MENIUL E O FOAIE, NU UN DROPDOWN =====
            out('\n--- meniul de sortare ---')
            page.goto(baza + '/#/projects', wait_until='load')
            page.wait_for_timeout(1500)
            decl = page.query_selector('.sort-trigger')
            if not decl:
                note.append('pagina Proiecte n-are declansator de sortare')
            else:
                decl.click()
                page.wait_for_timeout(700)
                foaie = page.query_selector('.modal.sheet')
                bifa(foaie is not None, 'sortarea se deschide ca FOAIE pe telefon',
                     'a ramas dropdown')
                if foaie:
                    inaltimi = page.evaluate(
                        """() => [...document.querySelectorAll('.modal.sheet [role=option]')]
                                 .map(e => Math.round(e.getBoundingClientRect().height))""")
                    mic = [h for h in inaltimi if h < 44]
                    bifa(bool(inaltimi) and not mic,
                         'randurile respecta tinta de atingere (>=44px)',
                         'inaltimi %s' % inaltimi)

            # ===== 5. MENIUL DE TEMA: componenta se incarca LENES =====
            # Foaia din antet vine printr-un `import()`, ca sa nu intre in
            # chunk-ul preincarcat la pornire (vezi nota din `Header.svelte`).
            # Componenta dinamica + `bind:open` e exact locul unde o greseala nu
            # cade la build, ci se vede ca un buton care nu face nimic.
            out('\n--- meniul de tema (componenta lenesa) ---')
            # Foaia de sortare a ramas deschisa de la proba dinainte, iar voalul ei
            # acopera antetul. Escape e si el o proba: butonul „inapoi" de pe
            # Android ajunge in aplicatie exact asa.
            if page.query_selector('.modal.sheet'):
                page.keyboard.press('Escape')
                page.wait_for_timeout(600)
                bifa(page.query_selector('.modal.sheet') is None,
                     'Escape inchide foaia de deasupra', 'foaia a ramas dupa Escape')
            buton = page.query_selector('.tema-wrap .h-btn')
            if buton is None:
                bifa(False, 'butonul de tema exista in antet', 'nu s-a gasit .tema-wrap .h-btn')
            else:
                buton.click()
                page.wait_for_timeout(900)
                foaie = page.query_selector('.modal.sheet')
                bifa(foaie is not None, 'tema se deschide ca foaie dupa incarcarea lenesa',
                     'nu s-a deschis nimic — `bind:open` pe componenta dinamica')
                if foaie:
                    randuri = page.evaluate(
                        """() => [...document.querySelectorAll('.modal.sheet [role=menuitemradio]')]
                                 .map(e => Math.round(e.getBoundingClientRect().height))""")
                    bifa(len(randuri) == 3 and all(h >= 44 for h in randuri),
                         'trei moduri, fiecare cu tinta intreaga',
                         'inaltimi %s' % randuri, '%s' % randuri)
                    # Alegerea chiar comuta tema si inchide foaia.
                    page.query_selector_all('.modal.sheet [role=menuitemradio]')[2].click()
                    page.wait_for_timeout(700)
                    bifa(page.query_selector('.modal.sheet') is None,
                         'alegerea inchide foaia', 'a ramas deschisa')
                    bifa(page.evaluate("() => document.documentElement.getAttribute('data-theme')") == 'dark',
                         'alegerea chiar schimba tema', 'data-theme n-a devenit dark')

            # ===== 6. FOAIA DE ADAUGARE VINE CU TASTATURA, INTR-O SINGURA MISCARE =====
            #
            # CONTRACTUL S-A INVERSAT PE 2026-08-17, si merita citit de ce, fiindca
            # aici a fost verificat inainte EXACT contrariul.
            #
            # Prima regula: „o foaie din care ALEGI nu-si cheama singura tastatura".
            # Ion, despre „Adauga task existent": „parca se reincarca pagina" — erau
            # DOUA sosiri, foaia la 340px in ~250ms, apoi tastatura o smulgea la 30 in
            # urmatoarele 160.
            # Numai ca foaia aceea era o CAUTARE prin taskuri existente. Cea de acum
            # (`components/FoaieAdauga.svelte`) e in primul rand pentru SCRIS — vine din
            # butonul „+" — iar fara focus automat sosirile au devenit TREI: foaia, apoi
            # atingerea ta, apoi tastatura. Ion, dupa proba: „cand dau adaugare task si
            # vreau sa tastez, tastatura ridica mai sus, dar animatia nu este fluida
            # deloc; mai bine fa direct cu tastatura deschisa."
            # Deci nu s-a renunţat la principiu — principiul era „o singura miscare", si
            # el se respecta acum invers: tastatura urca ODATA cu foaia.
            #
            # Ce rămâne verificat neschimbat, si e partea care conteaza: dupa ce s-a
            # asezat, foaia NU MAI PLEACA NICAIERI. Aia prinde a doua sosire, oricare ar
            # fi cauza ei.
            out('\n--- foaia de adaugare vine cu tastatura ---')
            page.goto(baza + '/#/tasks', wait_until='load')
            page.wait_for_timeout(1000)
            # Acasa se cere prin hash: pe telefon aterizarea implicita duce la
            # taskurile personale, deci un `goto` direct n-ar ajunge niciodata.
            page.evaluate("() => { location.hash = '#/' }")
            page.wait_for_timeout(1600)
            adauga = page.query_selector('.bh-add')
            if adauga is None:
                note.append('boardul „Astazi" n-are butonul „Adauga task existent"')
            else:
                adauga.click()
                page.wait_for_timeout(900)
                stare = page.evaluate(STARE_ALEGERE)
                bifa(stare['randuri'] > 0, 'foaia se deschide cu lista in mana',
                     'niciun rand — nu s-au randat candidatii')
                bifa(stare['editabil'],
                     'campul are focusul, deci tastatura urca odata cu foaia',
                     'focus pe %s — ai nevoie de o atingere in plus ca sa scrii' % stare['tag'],
                     'focus pe %s' % stare['tag'])
                # ...si foaia sta pe loc dupa ce s-a asezat: o a doua masuratoare,
                # la distanta, prinde orice miscare intarziata.
                page.wait_for_timeout(500)
                dupa = page.evaluate(SUS_FOAIE)
                bifa(dupa is not None and stare['sus'] is not None and abs(dupa - stare['sus']) <= 2,
                     'dupa ce s-a asezat, foaia nu mai pleaca nicaieri',
                     '%s -> %s px' % (stare['sus'], dupa), 'ramane la %s px' % dupa)

                # FARA CHENAR PE CAMPUL FOCALIZAT. Ion: „este un chenar la campul «ce
                # ai de făcut»? albastru, nu-mi place." Venea din regula globala
                # `input:focus { box-shadow: var(--focus-ring) }` — corecta pentru un
                # camp CU cutie, greșita pe primul rand al unei foi, care n-are
                # niciuna. Se masoara `box-shadow` calculat, nu clasa: regula globala
                # se poate reintoarce din orice alt fisier.
                umbra = page.evaluate("""() => {
                  const i = document.querySelector('.fa-cauta input');
                  if (!i) return null;
                  i.focus();
                  const s = getComputedStyle(i).boxShadow;
                  return s;
                }""")
                bifa(umbra in (None, 'none'),
                     'campul focalizat nu deseneaza un chenar',
                     'box-shadow: %s' % umbra, 'fara box-shadow')

                # ===== CEASUL NU STINGE PAGINA A DOUA OARA =====
                # Ion: „cand il deschid parca pagina se stinge si se aprinde."
                # Doua voaluri de 0,6 peste aceiasi pixeli dau ~0,84, apoi foaia de
                # dedesubt si-l stinge pe al ei si revine la 0,6 — de aici trecerea.
                # Peste o foaie, voalul ceasului trebuie sa fie cel SLAB.
                # Proba are nevoie de un task PERSONAL (randul de ora exista doar
                # acolo — `global_tasks.ora`, v41) si de foaia de la apasare lunga.
                # Isi face singura cazul: altfel verificarea ar depinde de ce se
                # intampla sa fie in baza, adica ar tacea exact cand baza e goala.
                page.evaluate("() => { location.hash = '#/tasks?sfera=personal' }")
                page.wait_for_timeout(1800)
                MARCA_P = 'Audit — ora de proba'
                if page.locator('.trow', has_text=MARCA_P).count() == 0:
                    fab = page.locator('.fab').first
                    if fab.count():
                        fab.click()
                        page.wait_for_timeout(900)
                        camp = page.locator('.fa-cauta input').first
                        if camp.count():
                            camp.fill('azi ' + MARCA_P)
                            page.wait_for_timeout(500)
                            page.locator('.fa-creeaza').first.click()
                            page.wait_for_timeout(1800)
                if page.locator('.trow', has_text=MARCA_P).count() == 0:
                    note.append('n-am putut crea un task personal pentru proba ceasului')
                else:
                    # Apasare lunga pe randul lui, ca sa vina foaia cu randul de ora.
                    r = page.evaluate("""(marca) => {
                      const randuri = [...document.querySelectorAll('.trow')];
                      const el = randuri.find(x => x.textContent.includes(marca));
                      if (!el) return null;
                      const b = el.getBoundingClientRect();
                      return [b.left + b.width * 0.5, b.top + b.height / 2];
                    }""", MARCA_P)
                    ok = 'fara-ceas'
                    if r:
                        page.evaluate("""([x, y]) => {
                          const el = document.elementFromPoint(x, y);
                          const ev = (t) => el.dispatchEvent(new PointerEvent(t, {
                            pointerId: 11, pointerType: 'touch', isPrimary: true,
                            clientX: x, clientY: y, bubbles: true, cancelable: true }));
                          ev('pointerdown');
                          window.__sus = () => ev('pointerup');
                        }""", r)
                        page.wait_for_timeout(700)
                        page.evaluate('() => window.__sus && window.__sus()')
                        page.wait_for_timeout(800)
                        ok = page.evaluate("""() => {
                          const so = document.querySelector('.so-trigger');
                          if (!so) return 'fara-ceas';
                          so.click();
                          return 'deschis';
                        }""")
                    if ok == 'fara-ceas':
                        note.append('foaia de actiuni n-a adus randul de ora')
                    else:
                        page.wait_for_timeout(700)
                        v = page.evaluate("""() => {
                          const el = document.querySelector('.so-voal');
                          if (!el) return null;
                          return { slab: el.classList.contains('slab'),
                                   bg: getComputedStyle(el).backgroundColor };
                        }""")
                        if v is None:
                            note.append('ceasul nu s-a deschis ca foaie')
                        else:
                            bifa(v['slab'], 'peste o foaie, voalul ceasului doar separa',
                                 'voal INTREG peste unul existent: %s' % v['bg'],
                                 v['bg'])

            b.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        shutil.rmtree(lucru, ignore_errors=True)

    out()
    for n in note:
        out('  nota: %s' % n)
    if esecuri:
        out('\n%d contracte incalcate:' % len(esecuri))
        for e in esecuri:
            out('  - %s' % e)
        sys.exit(1)
    out('OK — foaia respecta toate contractele.')


if __name__ == '__main__':
    main()

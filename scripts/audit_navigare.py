# -*- coding: utf-8 -*-
"""Audit de navigare: ce se intampla, masurat, cand schimbi tabul.

DE CE EXISTA
Ion, 2026-08-14: „nu sunt omogene, nu sunt peste tot, cel mai mult ma deranjeaza
la schimbul dintre taburi cand se incarca pagina."

Nimic din ce se masoara aici nu arunca vreo eroare. Build-ul e verde, `smoke_ui`
e verde, `audit_design` e curat — si totusi la fiecare apasare de tab se jucau
TREI animatii de intrare peste aceiasi pixeli (`::view-transition-*(root)` 240ms
pe X, `.ruta-in` 220ms pe Y, `.cell-in` in scara pana la 460ms), iar Calendarul
punea un schelet de 360px la FIECARE intrare, nu doar la prima — fiindca starea
lui traia in componenta, pe care `{#key routeKey}` o distruge.

Cele patru contracte verificate aici sunt exact cele care nu se pot vedea intr-o
captura de ecran:

  1. PRIMA INCARCARE are `rutaIn` si `cellIn` — intrarea paginii.
  2. SCHIMBAREA DE TAB le are ACUM pe amandoua (Ion, 2026-08-24: „vreau ca fiecare
     pagina sa aiba animatie la aparitie, gen cum e la planificator"), si NU mai
     porneste un View Transition de rута. Pana atunci VT-ul detinea tranzitia si le
     ascundea (scara se juca sub instantaneu), deci erau gardate pe prima incarcare;
     de cand `navigate` nu mai porneste VT (2026-08-24), sunt singura miscare de
     sosire si se joaca la fiecare navigare. Un al treilea strat (VT) peste ele ar fi
     din nou bugul de pe 14 august.
  3. REVENIREA PE UN TAB nu mai trece prin schelet.
  4. HOVERUL incepe treaba: modulul si datele rutei sunt cerute inainte de click.
  5. O PAGINA NOUA incepe de sus (fereastra deruleaza, nu `.app-content`).

RULARE
    python scripts/audit_navigare.py
    python scripts/audit_navigare.py --vizibil     # cu browserul pe ecran

Porneste singur aplicatia pe un port liber si pe o COPIE a bazei, ca `smoke_ui`.
Iese cu 0 daca totul e curat, 1 daca a gasit ceva.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from smoke_ui import (  # noqa: E402  — reutilizam bootstrapul, nu-l rescriem
    FUS_TEST, PIN_TEST, RADACINA, out, port_liber, porneste_serverul,
)

PROBLEME = []


def nota(ok, eticheta, detaliu=''):
    out('  %-5s %s%s' % ('OK' if ok else 'PICA', eticheta, ('  — ' + detaliu) if detaliu else ''))
    if not ok:
        PROBLEME.append(eticheta + (('  — ' + detaliu) if detaliu else ''))


# ---------------------------------------------------------------- seed de date
def seed(ctx, baza):
    """Un proiect cu o perioada, ca sa existe ceva de desenat in Calendar.

    Fara el, calendarul e gol si testul ar trece pe o pagina care n-are ce
    incarca — adica exact pe cazul care nu doare.

    Merge prin `context.request`, care imparte cookie-urile cu browserul deja
    autentificat; tokenul CSRF se citeste din cookie si se trimite in antet,
    exact ca in aplicatie (`lib/api.js`).
    """
    csrf = ''
    for c in ctx.cookies():
        if c['name'] == 'csrf_token':
            csrf = c['value']
    antete = {'Content-Type': 'application/json', 'X-CSRF-Token': csrf}

    r = ctx.request.get(baza + '/api/proiecte')
    lista = r.json() if r.ok else []
    if isinstance(lista, dict):
        lista = lista.get('projects') or lista.get('proiecte') or []
    if lista:
        return lista[0]['id']

    r = ctx.request.post(baza + '/api/proiecte', headers=antete, data=json.dumps(
        {'nume': 'Audit navigare', 'client': 'Continental', 'tip': 'PIF'}))
    if not r.ok:
        out('  (nu s-a putut crea proiectul de test: HTTP %d)' % r.status)
        return None
    corp = r.json()
    pid = corp.get('id') or (corp.get('proiect') or {}).get('id')
    if pid:
        import datetime
        azi = datetime.date.today()
        ctx.request.post(baza + '/api/proiecte/%s/implementari' % pid, headers=antete, data=json.dumps({
            'data_start': azi.isoformat(),
            'data_sfarsit': (azi + datetime.timedelta(days=3)).isoformat(),
            'eticheta': 'Perioada de audit', 'locatie': 'Site', 'faza': 'implementare',
        }))
    return pid


# ------------------------------------------------------------------ instrumente
SPION = """
window.__anim = [];
window.__schelet = 0;
document.addEventListener('animationstart', (e) => window.__anim.push(e.animationName), true);
new MutationObserver(() => {
  if (document.querySelector('.skeleton, .sk-lista')) window.__schelet++;
}).observe(document.body, { childList: true, subtree: true });
"""


def curata(page):
    page.evaluate("window.__anim = []; window.__schelet = 0;")


def animatii(page):
    return page.evaluate("window.__anim.slice()")


def tab_din_nav(page, cale):
    """Randul unei rute din navigatia de DESKTOP, adica bara laterala.

    Proba ruleaza intr-un singur context, la 1280x800 (vezi `ruleaza`), deci
    navigatia e `Sidebar.svelte`, nu dockul — acela a ramas doar pe telefon si se
    verifica in `audit_mobil.py`.

    ISTORIC, fiindca explica de ce nu mai exista un pas de „arata navigatia":
    pana la bara laterala, desktopul avea dockul ascuns, care iesea doar cand
    cursorul intra in ultimii 48px de jos (`REVEAL_EDGE`). Fara acel pas orice
    `hover` pe un tab expira — elementul era randat, dar tradus SUB fereastra.
    Bara laterala e mereu la vedere, deci pasul a disparut; daca vreodata se
    intoarce o ascundere, se intoarce si el.

    Selectorul intra prin `.rute` INADINS: marca din capul barei e tot un
    `<a href="/">`, iar `.bara a[href="/"]` ar prinde-o pe ea, care nu e un tab.
    """
    return page.locator('.rute a[href="%s"]' % cale).first


def mergi_la(page, tab, astepta=700):
    """Apasa o ruta din navigatie exact ca utilizatorul: hover, apoi click."""
    el = tab_din_nav(page, tab)
    el.hover()
    page.wait_for_timeout(160)      # cat dureaza drumul de la hover la click
    el.click()
    page.wait_for_timeout(astepta)


# ===================== FIECARE TAB, CU LATENTA, PE CADRE =====================
#
# DOUA LUCRURI PE CARE MASURATOAREA DE MAI SUS NU LE PRINDE, si amandoua au
# ascuns cate un defect adevarat pana pe 2026-08-14:
#
#  1. LOCALHOST MINTE. O cerere se intoarce in 5ms, deci plafonul de 250ms al
#     preincarcarii nu se atinge niciodata si totul pare curat. Aplicatia
#     traieste in spatele unui tunel Cloudflare, unde un dus-intors e ~150ms.
#  2. `MutationObserver` RATEAZA CLIPIRILE. El vede modificarea, dar pana ruleaza
#     callbackul scheletul poate fi deja scos — iar unul care prinde UN cadru
#     tot se vede. rAF e granita corecta: daca a fost pe ecran macar un cadru,
#     ochiul a prins schimbarea.
#
# Cu amandoua puse la punct au iesit doua cazuri reale (Taskuri si Calendar,
# click rapid, prima vizita: exact un cadru de schelet). Ion le descrisese fara
# sa le poata numi: „la schimbul pe un alt tab aproape tot timpul vad un schelet
# apoi apare pagina".
# A TREIA CAPCANA, gasita tot pe 2026-08-14: „apare scheletul?" e intrebarea
# GRESITA. Dupa ce scheletele au disparut, Ion a raportat mai departe „tot vad
# schelete sau niste ramasite mai intai apoi apare rapid pagina" — si avea
# dreptate. Ce se vedea nu era un schelet, era RAMA paginii noi fara continut:
# titlul si bara de unelte randate la 221ms, iar randurile abia la 295. Store-ul
# pornea gol fiindca `preia` cere intotdeauna de la server, chiar cand raspunsul
# era deja adus de `pregateste` la hover.
#
# Deci masuram si CATE STARI VIZUALE DISTINCTE se perinda intre pagina veche si
# cea noua. Contractul e doua: ce era, si ce e. Orice a treia stare e o ramasita,
# indiferent cum o cheama clasa ei.
CADRE = """
window.__cadre = 0; window.__cand = []; window.__t = performance.now(); window.__stari = [];
window.__continut = 0;
(function bucla() {
  if (document.querySelector('.page-loading, .page .skeleton, .page .sk-lista')) {
    window.__cadre++;
    if (window.__t) window.__cand.push(Math.round(performance.now() - window.__t));
  }
  try {
    const q = (s) => document.querySelectorAll(s).length;
    if (!window.__continut && q('.page .trow, .page .pcard, .page .zi, .page .lane, .page .arow'))
      window.__continut = Math.round(performance.now() - window.__t);
    const cheie = [location.hash,
      ((document.querySelector('.page h1') || {}).textContent || '').trim(),
      q('.page-loading, .skeleton, .sk-lista'),
      q('.page .trow, .page .arow, .page .pcard, .page .zi, .page .lane'),
      !!document.querySelector('.empty-state, .es-wrap')].join('|');
    if (window.__stari[window.__stari.length - 1] !== cheie) window.__stari.push(cheie);
  } catch (_) {}
  requestAnimationFrame(bucla);
})();
"""

RUTE_TAB = [('/', 'Acasă'), ('/tasks', 'Taskuri'), ('/plan', 'Planificator'),
            ('/calendar', 'Calendar')]


def ruleaza_taburi(page, baza):
    """Doua treceri prin dock: prima vizita (memoria goala) si a doua.

    Hoverul e SCURT cu buna stiinta — 60ms, cat ii ia unei maini sigure de la
    intrarea pe tab pana la click. Cu 250ms trecea tot; defectul aparea abia la
    clicul rapid, adica exact la cel al omului care stie unde apasa."""
    cdp = page.context.new_cdp_session(page)
    cdp.send('Network.enable')
    cdp.send('Network.emulateNetworkConditions', {
        'offline': False, 'latency': 150,
        'downloadThroughput': int(20 * 1024 * 1024 / 8),
        'uploadThroughput': int(6 * 1024 * 1024 / 8)})
    page.add_init_script(CADRE)
    page.goto(baza + '/#/', wait_until='load')
    page.wait_for_timeout(1800)
    try:
        for tur in ('prima vizita', 'a doua vizita'):
            for cale, nume in RUTE_TAB:
                el = tab_din_nav(page, cale)
                page.evaluate("window.__cadre = 0; window.__cand = []; window.__stari = [];"
                              " window.__t = performance.now()")
                el.hover()
                page.wait_for_timeout(60)
                el.click()
                page.wait_for_timeout(1400)
                r = page.evaluate("({ n: window.__cadre, t: window.__cand[0], stari: window.__stari })")
                nota(r['n'] == 0, '%s (%s): fara schelet' % (nume, tur),
                     '%d cadre, primul la %sms' % (r['n'], r['t']) if r['n'] else '')
                # Doua stari: pagina veche si pagina noua. A treia e o ramasita.
                nota(len(r['stari']) <= 2, '%s (%s): fara stare intermediara' % (nume, tur),
                     '%d stari: %s' % (len(r['stari']),
                                       ' → '.join(s.split('|')[1] + '/' + s.split('|')[3] + 'r'
                                                  for s in r['stari'])) if len(r['stari']) > 2 else '')
    finally:
        # Reteaua se lasa asa cum a fost gasita: probele de dupa nu trebuie sa
        # mosteneasca 150ms de latenta fara sa stie.
        cdp.send('Network.emulateNetworkConditions', {
            'offline': False, 'latency': 0,
            'downloadThroughput': -1, 'uploadThroughput': -1})


# ============ A DOUA DESCHIDERE A APLICATIEI NU ASTEAPTA NIMIC ============
#
# Ion: „la pornirea paginilor, mai ales se vede la calendar" si „daca am o
# trimitere catre calendar si dau click de pe acasa sau din planificator".
#
# Toate probele de mai sus masoara navigarea IN sesiune. Patru drumuri o
# ocolesc, si el le nimerise pe toate: deschiderea aplicatiei (pe Android se
# deschide pe ultima ruta), un F5, un `navigate()` chemat de mana, si o
# trimitere cu parametru. In toate patru memoria filei e goala.
#
# De cand `lib/cache.js` se hidrateaza din `localStorage`, pagina se deseneaza
# din primul cadru. Masurat: Proiecte de la 984ms la 25, Planificator de la 791
# la 37.
#
# DOUA CAPCANE DE SCRIS TESTUL, amandoua m-au pacalit:
#  1. `goto` catre acelasi URL cu acelasi hash NU creeaza document nou, deci
#     modulele nu se re-evalueaza si a doua masuratoare o repeta pe prima —
#     cu timpi identici la milisecunda, care arata exact ca „n-a mers nimic".
#     Reincarcarea se face cu `reload()`.
#  2. Scrierea pe disc e amanata pe rand liber, deci intre prima incarcare si
#     reload trebuie lasat timp; altfel testezi un disc gol.
RUTE_REPORNIRE = [('#/plan', 'Planificator'), ('#/projects', 'Proiecte'),
                  ('#/calendar', 'Calendar')]


def ruleaza_repornire(page, baza):
    for ruta, nume in RUTE_REPORNIRE:
        page.goto(baza + '/' + ruta, wait_until='load')
        page.wait_for_timeout(2600)          # si pentru scrierea amanata pe disc
        page.reload(wait_until='load')
        page.wait_for_timeout(1500)
        # Nu se reseteaza nimic dupa `reload`: scriptul de init se re-executa si
        # porneste ceasul la inceputul DOCUMENTULUI — exact reperul potrivit
        # pentru „cat dureaza pana vezi pagina la o repornire".
        r = page.evaluate("({ n: window.__cadre, c: window.__continut })")
        # Nu „zero cadre de asteptare": la o reincarcare adevarata chunkul paginii
        # trebuie adus, deci un cadru-doua de rama sunt inevitabile fara sa
        # inglobam pagina in HTML. Ce se poate cere — si ce chiar conteaza — e ca
        # PAGINA sa fie pe ecran inainte ca ochiul sa apuce sa citeasca o
        # asteptare. Pragul e generos fata de masuratoare (25-40ms), ca proba sa
        # nu pice pe o masina incarcata.
        nota(r['c'] and r['c'] < 300, '%s: continutul apare in <300ms' % nume,
             'la %sms, %d cadre de asteptare' % (r['c'], r['n']))



# ================== COMUTAREA SFEREI NU E O SCHIMBARE DE PAGINA ==================
#
# Ion, 2026-08-15: „la comutatia dintre taskuri personale si lucru parca se
# reincarca pagina si se vede asta." Se vedea fiindca asa era: sfera traieste in
# interogare, comutatorul cheama `navigate`, iar `navigate` pornea o View
# Transition pe RADACINA — tot ecranul, antet inclusiv, pentru o filtrare care
# nu cere nicio cerere. De la „drumul lat" tot ecranul si aluneca 30px.
#
# Contractul: cand CALEA nu se schimba, tranzitia de radacina nu se joaca.
# Pagina isi are propria miscare pentru starea ei.
def ruleaza_sfere(page, baza):
    page.goto(baza + '/#/tasks', wait_until='load')
    page.wait_for_timeout(1500)
    page.evaluate("window.__anim = []")
    tinta = page.locator('.seg').last
    tinta.click()
    page.wait_for_timeout(900)
    an = page.evaluate("window.__anim.slice()")
    radacina = [a for a in an if 'vt-pagina' in a]
    nota(not radacina, 'sfera: nicio tranzitie de radacina',
         'gasite: %s' % sorted(set(radacina)) if radacina else '')
    nota('sfera=personal' in page.evaluate("location.hash"), 'sfera: a comutat',
         page.evaluate("location.hash"))



# ============ TABURILE DIN PAGINA DE PROIECT ============
#
# Ion, 2026-08-15: „cum se deschid taburile de proiecte, acum e cu ramasite si
# schelet, nu se deschide fluent."
#
# A CINCEA OARA aceeasi familie de eroare de masurare: prima sonda asculta
# `animationstart`, si a raportat „nicio animatie". Fals — Svelte 5 ruleaza
# tranzitiile prin Web Animations, care NU emit evenimentul ala. Se numara cu
# `document.getAnimations()`, la mijlocul miscarii.
#
# Ce era adevarat: prima vizita pe „Perioade" si pe „Wiki" trecea printr-un
# cadru de schelet si TREI stari vizuale, fiindca datele lor se cereau abia la
# deschiderea tabului. Se incalzesc acum la deschiderea PAGINII, pe rand liber.
def ruleaza_taburi_proiect(page, baza, pid):
    page.goto(baza + '/#/projects/' + pid, wait_until='load')
    page.wait_for_timeout(2600)          # si pentru incalzirea pe rand liber
    taburi = page.locator('.tab')
    n = taburi.count()
    if not n:
        out('  SARI  pagina de proiect n-are taburi')
        return
    # Ordinea sare peste tabul DEJA activ: un click pe el nu schimba nimic, deci
    # nici n-are ce anima — `alegeTab` iese devreme cu buna stiinta. Masurat pe
    # el, contractul „continutul se misca" ar fi picat pe un comportament corect.
    ordine = list(range(1, n)) + [0]
    for i in ordine:
        et = (taburi.nth(i).text_content() or '').strip()[:10]
        page.evaluate("window.__cadre = 0; window.__stari = []; window.__t = performance.now()")
        taburi.nth(i).click()
        page.wait_for_timeout(60)
        viu = page.evaluate("document.getAnimations().length")
        page.wait_for_timeout(1100)
        r = page.evaluate("({ n: window.__cadre, stari: window.__stari })")
        nota(r['n'] == 0, 'tab „%s": fara schelet' % et, '%d cadre' % r['n'])
        nota(viu > 0, 'tab „%s": continutul se MISCA' % et,
             'nicio animatie activa' if not viu else '')


# ----------------------------------------------------------------------- probe
def ruleaza(page, baza, pid):
    out('\n--- 1. prima incarcare: pagina SOSESTE ---')
    page.goto(baza + '/#/', wait_until='networkidle')
    page.add_init_script(SPION)
    page.reload(wait_until='networkidle')
    page.wait_for_timeout(800)
    a = animatii(page)
    nota('rutaIn' in a, 'prima incarcare joaca rutaIn', 'vazute: %s' % sorted(set(a)))
    nota('cellIn' in a, 'prima incarcare joaca cellIn', 'vazute: %s' % sorted(set(a)))
    nota(page.evaluate("document.documentElement.classList.contains('prima-incarcare')"),
         'steagul prima-incarcare e pus la deschidere')

    out('\n--- 2. schimbarea de tab: PAGINA intra animat, fara VT ---')
    curata(page)
    mergi_la(page, '/calendar')
    a = animatii(page)
    intrari = [n for n in a if n in ('rutaIn', 'cellIn')]
    nota(bool(intrari), 'la schimbarea de tab pagina intra animat (rutaIn/cellIn)',
         'vazute: %s' % sorted(set(a)))
    vt = [n for n in a if n.startswith('vt-pagina')]
    nota(not vt, 'schimbarea de tab NU porneste un View Transition de rута',
         'gasite: %s' % sorted(set(vt)) if vt else '')
    nota(not page.evaluate("document.documentElement.classList.contains('prima-incarcare')"),
         'steagul s-a stins la prima navigare')
    nota(page.locator('.cal').count() > 0 or page.locator('.page').count() > 0,
         'Calendarul chiar s-a randat')

    out('\n--- 3. revenirea pe tab: fara schelet ---')
    mergi_la(page, '/tasks')
    curata(page)
    mergi_la(page, '/calendar')
    nota(page.evaluate("window.__schelet") == 0, 'revenirea pe Calendar nu trece prin schelet',
         '%d aparitii' % page.evaluate("window.__schelet"))

    out('\n--- 4. hoverul incepe treaba ---')
    cereri = []
    page.on('request', lambda r: cereri.append(r.url))
    # Ruta trebuie sa fie una NEVIZITATA in sesiunea asta: pe una proaspata,
    # `preia` intoarce din memorie fara sa atinga reteaua, si atunci „zero
    # cereri la hover" ar fi raspunsul CORECT — dar testul l-ar citi ca esec.
    # Departamentul n-a fost deschis pana aici.
    URL_DEPT = '/api/settings/plan-departament'
    mergi_la(page, '/tasks')
    cereri.clear()
    el = tab_din_nav(page, '/departament')
    el.hover()
    page.wait_for_timeout(500)
    inainte = [u for u in cereri if URL_DEPT in u]
    nota(len(inainte) > 0, 'hoverul cere datele rutei INAINTE de click',
         '%d cereri la hover' % len(inainte))
    cereri.clear()
    el.click()
    page.wait_for_timeout(800)
    dupa = [u for u in cereri if URL_DEPT in u]
    nota(len(dupa) <= 1, 'clicul nu dubleaza cererea deja pornita',
         '%d cereri dupa click' % len(dupa))
    nota(page.evaluate("window.__schelet") == 0, 'ruta preincarcata se deschide fara schelet',
         '%d aparitii' % page.evaluate("window.__schelet"))
    # Reversul aceluiasi contract: pe date proaspete, hoverul NU trage nimic.
    # Fara proba asta, plimbarea cursorului peste doc ar putea deveni un torent
    # de cereri fara ca nimic sa arate altfel pe ecran.
    mergi_la(page, '/tasks')
    cereri.clear()
    tab_din_nav(page, '/departament').hover()
    page.wait_for_timeout(500)
    nota(len([u for u in cereri if URL_DEPT in u]) == 0,
         'hoverul pe date proaspete nu mai cere nimic',
         '%d cereri' % len([u for u in cereri if URL_DEPT in u]))

    out('\n--- 5. o pagina noua incepe de sus ---')
    # Calculatorul e singura pagina sigur mai inalta decat fereastra chiar si pe
    # o baza goala. Pe /tasks fara taskuri nu exista derulare, deci proba ar fi
    # trecut fara sa masoare nimic.
    mergi_la(page, '/calculator', astepta=1200)
    page.evaluate("window.scrollTo(0, 1200)")
    page.wait_for_timeout(150)
    inaltat = page.evaluate("window.scrollY")
    if inaltat == 0:
        out('  SARI  nicio pagina derulabila in baza asta')
    else:
        mergi_la(page, '/calendar')
        nota(page.evaluate("window.scrollY") == 0, 'derularea se reseteaza la schimbarea rutei',
             'pornit de la %dpx, ajuns la %dpx' % (inaltat, page.evaluate("window.scrollY")))

    out('\n--- 6. cadrul nu intra in instantaneul paginii ---')
    # CE E CADRU PE DESKTOP S-A SCHIMBAT DE DOUA ORI, CONTRACTUL NU.
    # Erau doua bucati — antetul de sus si dockul de jos — si fiecare avea nevoie
    # de nume propriu ca sa nu fie inghitita de instantaneul `root` si sa ia
    # alunecarea de ±10px la fiecare schimbare de ruta. Apoi amandoua au devenit
    # bara laterala (`cadru-lateral`), iar la AURORA bara a urcat sus si pluteste
    # (`cadru-bara`). Obiectul e tot unul singur si cerinta e neatinsa; se schimba
    # doar numele. Antetul si dockul mai exista pe telefon, unde `audit_mobil.py`
    # le vede.
    nume = page.evaluate("""(() => {
      const b = document.querySelector('.bara');
      return { bara: b ? getComputedStyle(b).viewTransitionName : 'lipsa' };
    })()""")
    nota(nume['bara'] == 'cadru-bara',
         'bara de sus are nume propriu de tranzitie', str(nume['bara']))

    out('\n--- 7. tenta slotului activ ALUNECA ---')
    # AXA S-A ROTIT DE DOUA ORI, CONTRACTUL NU. In dock tenta se muta pe
    # ORIZONTALA; in bara laterala se mutase pe VERTICALA; la AURORA bara a urcat
    # sus, deci masuram iar pe `left`/`width`. Nimic altceva nu se schimba: un
    # singur slot marcat, tenta fix peste el, si — singura proba care chiar prinde
    # regresia — pozitia LA 90ms, intre plecare si sosire. Dupa ce se termina, o
    # tenta care sare si una care aluneca arata identic.
    mergi_la(page, '/')
    p0 = page.evaluate("""(() => {
      const p = document.querySelector('.pilula');
      const s = document.querySelector('.rute [data-pilula]');
      if (!p || !s) return null;
      const cp = p.getBoundingClientRect(), cs = s.getBoundingClientRect();
      return { y: Math.round(cp.left), h: Math.round(cp.width),
               sy: Math.round(cs.left), sh: Math.round(cs.width),
               marcate: document.querySelectorAll('.rute [data-pilula]').length };
    })()""")
    nota(p0 is not None, 'pastila exista si un singur slot o poarta')
    if p0:
        nota(p0['marcate'] == 1, 'exact UN slot marcat', '%d marcate' % p0['marcate'])
        nota(abs(p0['y'] - p0['sy']) <= 1 and abs(p0['h'] - p0['sh']) <= 1,
             'pastila e fix peste slotul activ',
             'pastila x=%d w=%d / slot x=%d w=%d' % (p0['y'], p0['h'], p0['sy'], p0['sh']))
        el = tab_din_nav(page, '/calendar')
        el.click()
        # 90ms DE CAND PORNESTE, nu de cand apesi — si asta nu e o slabire a probei,
        # e separarea a doua lucruri care erau amestecate.
        # Intre clic si mutarea tentei sta `startViewTransition`: el INGHEATA pagina
        # veche pana se aplica ruta noua (vezi comentariul din `lib/router.svelte.js`,
        # cu cursa de 180ms pe importul chunkului). Masurat pe masina asta: tenta
        # porneste la 190-280ms de la clic, dupa cat de incarcata e masina — deci un
        # prag fix de 90ms masura latenta de navigare, nu alunecarea. Latenta o
        # masoara deja sectiunea 8, pe cadre, si acolo ii e locul.
        # Ce ramane aici e contractul adevarat: tenta trece PRIN pozitii intermediare
        # in loc sa sara. Asteptam sa se clinteasca, apoi ne uitam la 90ms dupa.
        start_x = p0['y']
        page.wait_for_function(
            """(x0) => {
              const p = document.querySelector('.pilula');
              return p && Math.abs(Math.round(p.getBoundingClientRect().left) - x0) > 1;
            }""", arg=start_x, timeout=3000)
        page.wait_for_timeout(90)
        la_mijloc = page.evaluate(
            "Math.round(document.querySelector('.pilula').getBoundingClientRect().left)")
        page.wait_for_timeout(600)
        la_final = page.evaluate("""(() => {
          const p = document.querySelector('.pilula');
          const s = document.querySelector('.rute [data-pilula]');
          return { y: Math.round(p.getBoundingClientRect().left),
                   sy: Math.round(s.getBoundingClientRect().left) };
        })()""")
        nota(abs(la_final['y'] - la_final['sy']) <= 1, 'ajunge pe slotul nou',
             'pastila %d / slot %d' % (la_final['y'], la_final['sy']))
        intre = min(p0['y'], la_final['y']) - 2 < la_mijloc < max(p0['y'], la_final['y']) + 2
        nota(intre and la_mijloc not in (p0['y'], la_final['y']),
             'la 90ms e INTRE cele doua sloturi (aluneca, nu sare)',
             'plecat %d -> la 90ms %d -> ajuns %d' % (p0['y'], la_mijloc, la_final['y']))

    out('\n--- 8. fiecare tab, cu LATENTA si masurat pe CADRE ---')
    ruleaza_taburi(page, baza)

    out('\n--- 9. comutarea sferei nu e o schimbare de pagina ---')
    ruleaza_sfere(page, baza)

    out('\n--- 10. a DOUA deschidere a aplicatiei nu asteapta nimic ---')
    ruleaza_repornire(page, baza)

    if pid:
        out('\n--- 11. taburile DIN pagina de proiect ---')
        ruleaza_taburi_proiect(page, baza, pid)

        out('\n--- 12. pagina de proiect se deschide cu ce stie ---')
        page.goto(baza + '/#/projects', wait_until='networkidle')
        page.wait_for_timeout(600)
        # Cardul e un `role="button"`, nu un link — de aceea are nevoie de
        # preincarcare scrisa pe el, si de aceea se cauta asa.
        card = page.locator('.pcard[role="button"]').first
        if card.count():
            card.hover()
            page.wait_for_timeout(450)
            curata(page)
            card.click()
            page.wait_for_timeout(900)
            nota(page.evaluate("window.__schelet") == 0,
                 'intrarea pe proiect dupa hover nu trece prin schelet',
                 '%d aparitii' % page.evaluate("window.__schelet"))
            nota(page.locator('h1').count() > 0, 'pagina de proiect s-a randat')
        else:
            out('  SARI  nu exista card de proiect in lista')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--vizibil', action='store_true', help='cu browser pe ecran')
    arg = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit('Lipseste playwright. Ruleaza:\n  pip install playwright\n'
                         '  python -m playwright install chromium')

    lucru = tempfile.mkdtemp(prefix='pif-nav-')
    db_temp = os.path.join(lucru, 'audit.db')
    sursa = os.path.join(RADACINA, 'pif_dashboard.db')
    if os.path.exists(sursa):
        shutil.copy2(sursa, db_temp)
    port = port_liber()
    proc, baza = porneste_serverul(port, db_temp, os.path.join(lucru, 'server.log'))

    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(headless=not arg.vizibil)
            ctx = br.new_context(viewport={'width': 1280, 'height': 800},
                                 timezone_id=FUS_TEST)
            page = ctx.new_page()
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', PIN_TEST)
            page.click('button[type="submit"]')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
            out('Autentificat.')

            pid = seed(ctx, baza)
            out('Proiect de test: %s' % (pid or 'niciunul'))

            page.add_init_script(SPION)
            ruleaza(page, baza, pid)
            br.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        try:
            proc._log.close()
        except Exception:
            pass
        shutil.rmtree(lucru, ignore_errors=True)

    out('')
    if PROBLEME:
        out('%d contracte incalcate:' % len(PROBLEME))
        for p in PROBLEME:
            out('  - ' + p)
        return 1
    out('OK — navigarea respecta toate contractele.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

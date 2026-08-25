#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Foile de pe telefon CU TASTATURA: o singura sosire, nimic sub ea, nimic sub deget.

De ce exista, langa `audit_foaie.py`: acela masoara foaia cat timp DEGETUL e pe
ea. Niciun audit nu masura foaia cat timp TASTATURA e pe ecran — si exact acolo
statea ce Ion numea „rupt": foaia urca 280ms, se aseza, apoi sosea `--kb` si o
mai impingea o data 224px in timp ce i se scurta inaltimea de jos. Doua sosiri
pentru un gest. Nu cadea niciun build, nu pica niciun audit, fiindca in Chromium
de pe masina de dezvoltare nu exista tastatura.

TASTATURA SE EMULEAZA FIDEL, nu se sare peste ea: `visualViewport` e inlocuit cu
unul fals care „ridica" tastatura la ~250ms dupa focusul pe un camp si o coboara
la pierderea lui — exact ce face IME-ul de pe Android si exact calea pe care
aplicatia o asculta (`Modal.svelte`, `<script module>`). Deci proba trece prin
ACELASI cod ca telefonul, nu printr-o scurtatura.

Contractele, fiecare cu modul de esec pe care l-a avut aplicatia:
  1. REGIMUL REAL: viewportul se micsoreaza INTR-UN PAS, iar foaia il urmeaza in
     ACELASI cadru — nicio proprietate de layout nu ramane in urma cu o tranzitie.
     Vezi nota lunga de mai jos: asta e ce face Capacitor pe aparat, si exact ce
     emularea veche NU reproducea.
  1b. CELALALT REGIM (browser/PWA): acolo containerul NU se micsoreaza si `--kb`
     chiar trebuie sa ridice foaia. A ramas neacoperit cand sectiunea 1 a trecut pe
     regimul real — si tocmai atunci `--kb` a capatat un prag, deci o regresie
     acolo n-ar fi fost vazuta de nimeni.
  2. NIMIC SUB TASTATURA. Campul focalizat, subsolul foii si corpul ei stau
     deasupra tastaturii; corpul nu deruleaza peste o lista care deruleaza si ea.
  3. EDITORUL DE NOTE urca intreg deasupra tastaturii (zona de scris ramanea de
     55px), iar fara tastatura bara de unelte nu acopera „Salveaza".
  4. UN CLIC E AL FOII DOAR DACA A INCEPUT PE EA. Ridicarea degetului dupa
     apasarea lunga nu inchide si nu apasa nimic in foaia care tocmai a sosit.
  5. FOAIA TASKULUI RASPUNDE IMEDIAT, cu schelet, nu dupa retea.
  6. PAGINA PROIECTULUI deschide taskul in foaie (telefon) / panou (desktop).
  7. FOAIA ZILEI (`inalt`) soseste la inaltime constanta, nu crescand din mers.

DE CE S-A RESCRIS SECTIUNEA 1 (2026-08-21). Varianta veche inlocuia
`window.visualViewport` cu un obiect fals si tinea `window.innerHeight`
CONSTANT. Pe aparat insa, Capacitor (`SystemBars`, in core) pune
`setPadding(0,0,0,imeInsets.bottom)` pe parintele WebView-ului cand vine IME-ul:
micsoreaza fizic WebView-ul, deci `innerHeight` scade IMPREUNA cu `vv.height`,
iar formula din `Modal.svelte` da corect `--kb` = 0. Adica emularea testa un aparat
pe care `--kb` conducea totul, iar aparatul real nu foloseste `--kb` deloc.
Trei runde de reglaje au trecut de auditul asta si n-au schimbat nimic pe
telefon. Acum proba micsoreaza CHIAR viewportul, intr-un pas.

CE A ARATAT APARATUL (2026-08-21, prin `scripts/masoara_tastatura_reala.py`):
„impreuna" NU inseamna „in acelasi cadru". Exista exact un cadru in care
`innerHeight` e deja 493 dar `vv.height` inca raporteaza 187 — tastatura scazuta
a doua oara — si acolo `--kb` iesea 306, turtind foaia la 123px pentru ~17ms.
De-aia `--kb` are acum un prag: zero se crede pe loc, o valoare nenula trebuie
sa se tina. Sectiunea 1b pazeste celalalt capat al pragului.

    python scripts/audit_tastatura.py
"""

import os
import sys
import tempfile

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADACINA, 'scripts'))

from audit_foaie import (PIN_TEST, TELEFON, apuca, bifa, esecuri, out,
                         porneste_serverul, port_liber, ridica, seamana)

DESKTOP = {'width': 1280, 'height': 800}
KB = 312   # inaltimea tastaturii emulate, in px — cat are o tastatura Gboard pe 844
LAT = 420  # ms de la focus pana cand IME-ul e sus — masurat ca ordin de marime pe WebView
KB_URCA = 200  # cat dureaza urcarea tastaturii insasi (vezi `KB_URCA` in Modal)

# NU se mai falsifica `visualViewport`. Pe aparat, ce se schimba e CHIAR
# viewportul (Capacitor micsoreaza WebView-ul), iar Playwright poate face exact
# asta cu `set_viewport_size`. Ce ramane de injectat e doar urma pe cadru.
INIT = r"""
(() => {
  window.__urma = []; let pornita = false;
  window.__porneste = () => { window.__urma = []; pornita = true; window.__t0 = performance.now() };
  window.__opreste = () => { pornita = false; return window.__urma };
  (function s() {
    if (pornita) {
      const f = document.querySelector('.modal.sheet'); const b = document.querySelector('.backdrop');
      const r = f ? f.getBoundingClientRect() : null;
      window.__urma.push({ t: Math.round(performance.now() - window.__t0),
        top: r ? Math.round(r.top) : null, h: r ? Math.round(r.height) : null,
        ih: window.innerHeight,
        pb: b ? Math.round(parseFloat(getComputedStyle(b).paddingBottom)) : null,
        kb: Math.round(parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--kb')) || 0) });
    }
    requestAnimationFrame(s);
  })();
})();
"""

URMA_PORNESTE = 'window.__porneste()'
URMA_OPRESTE = 'window.__go = false; window.__opreste()'

# Telefonul lui Ion are edge-to-edge: safe-area reala. Pe emulator e 0, si exact
# asa au trecut neobservate doua runde de reparatii la foaia zilei.
SAFE = 'html { --safe-top: 48px !important; --safe-bottom: 24px !important; }'

GEOM = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), h: Math.round(r.height) };
}"""


def ridica_tastatura(page, kb=None):
    """Tastatura, ca pe aparat: viewportul se micsoreaza intr-un pas.
    (Capacitor pune padding pe parintele WebView-ului — vezi antetul.)"""
    page.set_viewport_size({'width': TELEFON['width'], 'height': TELEFON['height'] - (kb or KB)})
    page.wait_for_timeout(350)


def coboara_tastatura(page):
    page.set_viewport_size({'width': TELEFON['width'], 'height': TELEFON['height']})
    page.wait_for_timeout(350)


def kb_acum(page):
    """Cat acopera tastatura ACUM, in regimul real: diferenta dintre ecran si
    viewportul ramas."""
    return TELEFON['height'] - page.evaluate('window.innerHeight')


def tap(cdp, page, x, y, pauza=400):
    apuca(cdp, x, y)
    page.wait_for_timeout(30)
    ridica(cdp, page, pauza)


def centru(el):
    b = el.bounding_box()
    return b['x'] + b['width'] / 2, b['y'] + b['height'] / 2


def urma(page, act, coada=900):
    page.evaluate('window.__porneste()')
    act()
    page.wait_for_timeout(coada)
    return page.evaluate('window.__opreste()')


def inchide_tot(page):
    """Escape pana nu mai e nicio foaie; apoi focusul pleaca din orice camp."""
    for _ in range(4):
        if not page.query_selector('.backdrop'):
            break
        page.keyboard.press('Escape')
        page.wait_for_timeout(450)
    page.evaluate('document.activeElement && document.activeElement.blur && document.activeElement.blur()')
    page.wait_for_timeout(400)


def mergi(page, baza, ruta, pauza=1400):
    page.goto(baza + '/#' + ruta, wait_until='load')
    page.wait_for_timeout(pauza)
    page.add_style_tag(content=SAFE)


def cadre_in_repaus(u, de_la):
    """Cadrele de dupa `de_la` ms: cat s-a mai miscat foaia dupa ce ar fi trebuit
    sa stea — adica a doua sosire, daca exista."""
    dupa = [p for p in u if p['t'] >= de_la and p['top'] is not None]
    if not dupa:
        return 0
    return max(p['top'] for p in dupa) - min(p['top'] for p in dupa)


def main():
    from playwright.sync_api import sync_playwright

    lucru = tempfile.mkdtemp(prefix='pif-tastatura-')
    db = os.path.join(lucru, 'proba.db')
    seamana(db)
    port = port_liber()
    proc, baza = porneste_serverul(port, db, os.path.join(lucru, 'server.log'))

    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport=TELEFON, has_touch=True, is_mobile=True)
            ctx.add_init_script(INIT)
            page = ctx.new_page()
            cdp = ctx.new_cdp_session(page)
            erori = []
            page.on('pageerror', lambda e: erori.append(str(e)))
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', PIN_TEST)
            page.press('#pin', 'Enter')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)

            # ===== 1. REGIMUL REAL: UN PAS, SI FOAIA IL URMEAZA IN ACELASI CADRU =====
            # Se micsoreaza CHIAR viewportul (ca `setPadding`-ul lui Capacitor),
            # nu un `visualViewport` fals. Contractul: intre cadrul de dinainte si
            # cel de dupa, foaia si-a luat deja geometria noua — fara sa mai ramana
            # nimic care se anima 220ms in urma.
            out('\n--- tastatura: un pas, iar foaia il urmeaza in acelasi cadru ---')
            mergi(page, baza, '/tasks')
            fab = page.query_selector('.dock-fab')
            if fab is None:
                bifa(False, 'butonul de adaugare exista pe /tasks', 'fara .dock-fab')
            else:
                x, y = centru(fab)
                tap(cdp, page, x, y, 900)
                inainte = page.evaluate(GEOM, '.modal.sheet')
                bifa(inainte is not None, 'foaia de adaugare e deschisa', 'nu s-a deschis')

                # Nicio proprietate de LAYOUT n-are voie sa fie tranzitionata pe
                # foaie sau pe voal: ele depind de viewport, care sare intr-un pas.
                tranzitii = page.evaluate("""() => {
                  const rasp = [];
                  for (const sel of ['.modal.sheet', '.backdrop', '.modal-body', '.modal-footer']) {
                    const el = document.querySelector(sel);
                    if (!el) continue;
                    const cs = getComputedStyle(el);
                    const props = (cs.transitionProperty || '').split(',').map(s => s.trim());
                    const rele = props.filter(p => ['height','max-height','min-height','width',
                      'padding','padding-bottom','padding-top','margin','margin-bottom','top','bottom'].includes(p));
                    if (rele.length) rasp.push(sel + ': ' + rele.join('/'));
                  }
                  return rasp; }""")
                bifa(not tranzitii,
                     'nicio proprietate de layout nu e tranzitionata pe foaie sau voal',
                     'gasite: %s' % '; '.join(tranzitii),
                     'zero')

                # TASTATURA: viewportul se micsoreaza intr-un pas.
                page.evaluate(URMA_PORNESTE)
                page.set_viewport_size({'width': TELEFON['width'], 'height': TELEFON['height'] - KB})
                page.wait_for_timeout(700)
                u = page.evaluate(URMA_OPRESTE)
                cu_foaie = [q for q in u if q['top'] is not None]
                if not cu_foaie:
                    bifa(False, 'foaia ramane pe ecran cand vine tastatura', 'a disparut')
                else:
                    # Cate cadre a durat pana s-a asezat: intr-un regim corect,
                    # geometria noua e deja acolo la primul cadru de dupa.
                    final = cu_foaie[-1]
                    # INALTIMEA (layout) trebuie sa fie instantanee: ea urmeaza
                    # viewportul, care sare intr-un pas. Daca s-ar anima, foaia ar
                    # ramane in urma — defectul reparat in Faza 1.
                    t_h = next(q['t'] for q in cu_foaie if q['h'] == final['h'])
                    bifa(t_h <= 50,
                         'inaltimea (layout) se ia in acelasi cadru cu viewportul',
                         'i-au trebuit %d ms — deci se animeaza layout' % t_h,
                         '%d ms' % t_h)
                    # SI POZITIA e instantanee, si asta e CONTRACTUL, nu o scapare.
                    # O zi a stat aici o glisare (FLIP): foaia se desena inapoi in
                    # locul vechi si aluneca la zero. Locul vechi insa nu mai exista
                    # — WebView-ul s-a micsorat deja — deci foaia se desena TAIATA.
                    # De aceea proba de mai jos e cea care conteaza: nimic desenat
                    # in afara viewportului, niciun cadru.
                    t_top = next(q['t'] for q in cu_foaie if q['top'] == final['top'])
                    bifa(t_top <= 50,
                         'pozitia se ia in acelasi cadru cu viewportul',
                         'i-au trebuit %d ms — deci ceva o plimba' % t_top,
                         '%d ms' % t_top)
                    afara = [q['top'] + q['h'] - q['ih'] for q in cu_foaie
                             if q['top'] + q['h'] > q['ih'] + 1]
                    bifa(not afara,
                         'foaia nu e desenata NICIUN cadru sub marginea viewportului',
                         '%d cadre taiate, pana la %d px (subsolul, cu butonul)'
                         % (len(afara), max(afara) if afara else 0),
                         'zero cadre taiate')
                    bifa(final['top'] + final['h'] <= TELEFON['height'] - KB + 1,
                         'foaia se termina deasupra tastaturii',
                         'jos la %d, tastatura de la %d' % (final['top'] + final['h'], TELEFON['height'] - KB))
                    camp = page.evaluate(GEOM, '.fa-cauta input')
                    bifa(camp is not None and camp['bottom'] <= TELEFON['height'] - KB,
                         'campul „Ce ai de facut?" ramane deasupra tastaturii',
                         'jos la %s' % (camp and camp['bottom']))

                # INCHIDEREA cu tastatura sus: foaia pleaca, iar viewportul creste
                # inapoi in timpul iesirii. Foaia nu are voie sa sara sau sa creasca.
                page.evaluate(URMA_PORNESTE)
                inch = page.query_selector('.modal-close')
                if inch:
                    bb = inch.bounding_box()
                    tap(cdp, page, bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2, 0)
                page.wait_for_timeout(60)
                page.set_viewport_size({'width': TELEFON['width'], 'height': TELEFON['height']})
                page.wait_for_timeout(700)
                u2 = [q for q in page.evaluate(URMA_OPRESTE) if q['top'] is not None]
                if len(u2) > 3:
                    inaltimi = set(q['h'] for q in u2)
                    bifa(len(inaltimi) == 1,
                         'cat coboara, foaia NU-si schimba inaltimea',
                         'a avut inaltimile %s' % sorted(inaltimi),
                         '%d px' % u2[0]['h'])
                    salturi = [b_['top'] - a_['top'] for a_, b_ in zip(u2, u2[1:])]
                    mari = [d for d in salturi if d > 90]
                    bifa(not mari,
                         'coborarea e continua, fara salt cand creste viewportul',
                         'salturi de %s px' % mari,
                         'cel mai mare pas: %d px' % (max(salturi) if salturi else 0))
                inchide_tot(page)

                # ===== 1b. CELALALT REGIM: IN BROWSER, `--kb` CHIAR COMPENSEAZA =====
                #
                # Sectiunea 1 acopera regimul APLICATIEI, unde containerul se
                # micsoreaza singur si raspunsul corect e `--kb` = 0. Dar in browser
                # (PWA, desktop) containerul NU se micsoreaza: doar viewportul vizual
                # se strange, iar acolo `--kb` e singurul lucru care tine foaia
                # deasupra tastaturii.
                #
                # Proba asta exista fiindca regimul ala a ramas NEACOPERIT cand
                # sectiunea 1 a fost rescrisa pe regimul real (2026-08-21), si tot
                # atunci `--kb` a capatat un prag: o valoare nenula se scrie doar dupa
                # ce s-a tinut ~120ms, ca sa nu fie crezut cadrul fantoma masurat pe
                # telefon. Un prag prea lung, sau o regresie in scriere, ar lasa foaia
                # sub tastatura in browser FARA ca vreo alta proba sa observe.
                out('\n--- regimul browser: `--kb` chiar ridica foaia ---')
                mergi(page, baza, '/tasks')
                fab = page.query_selector('.dock-fab')
                if fab is None:
                    bifa(False, 'butonul de adaugare exista pe /tasks', 'fara .dock-fab')
                else:
                    fx, fy = centru(fab)
                    tap(cdp, page, fx, fy, 900)
                    inainte = page.evaluate(GEOM, '.modal.sheet')
                    # Tastatura de BROWSER: `innerHeight` ramane pe loc, doar
                    # `visualViewport.height` scade. Exact ce NU face Capacitor.
                    page.evaluate("""(kb) => {
                      const vv = window.visualViewport;
                      Object.defineProperty(vv, 'height',
                        {get: () => window.innerHeight - kb, configurable: true});
                      vv.dispatchEvent(new Event('resize'));
                    }""", KB)
                    page.wait_for_timeout(60)
                    devreme = page.evaluate(
                        "parseFloat(getComputedStyle(document.documentElement)"
                        ".getPropertyValue('--kb')) || 0")
                    bifa(devreme == 0,
                         'sub prag, `--kb` inca e 0 (cadrul fantoma nu e crezut)',
                         'a sarit la %s px imediat' % devreme)
                    page.wait_for_timeout(400)
                    tarziu = page.evaluate(
                        "parseFloat(getComputedStyle(document.documentElement)"
                        ".getPropertyValue('--kb')) || 0")
                    bifa(tarziu == KB,
                         'dupa prag, `--kb` ia inaltimea tastaturii',
                         'a ramas %s px in loc de %d' % (tarziu, KB),
                         '%d px' % tarziu)
                    dupa = page.evaluate(GEOM, '.modal.sheet')
                    bifa(dupa is not None and dupa['bottom'] <= TELEFON['height'] - KB + 1,
                         'foaia urca deasupra tastaturii de browser',
                         'jos la %s, tastatura de la %d'
                         % (dupa and dupa['bottom'], TELEFON['height'] - KB))
                    bifa(inainte is not None and dupa is not None and dupa['h'] < inainte['h'],
                         'foaia se scurteaza, nu doar se muta',
                         '%s -> %s px' % (inainte and inainte['h'], dupa and dupa['h']))
                    bifa(page.evaluate(
                        "document.documentElement.classList.contains('are-tastatura')"),
                         '`are-tastatura` se pune in regimul browser', 'clasa lipseste')
                    inchide_tot(page)
                    page.reload()          # scapa de `visualViewport` falsificat
                    page.wait_for_timeout(1200)

                # ===== 2. NIMIC SUB TASTATURA =====
                out('\n--- nimic sub tastatura ---')
                page.wait_for_timeout(300)
                fab = page.query_selector('.dock-fab')
                if fab is not None:
                    fx, fy = centru(fab)
                    tap(cdp, page, fx, fy, 800)
                ridica_tastatura(page)
                kb_sus = kb_acum(page)
                bifa(kb_sus == KB, 'tastatura e sus (viewportul s-a micsorat)', 'kb=%s' % kb_sus)
                camp = page.evaluate(GEOM, '.fa-cauta input')
                bifa(camp is not None and camp['bottom'] <= TELEFON['height'] - KB,
                     'campul „Ce ai de făcut?" e deasupra tastaturii',
                     'jos la %s' % (camp and camp['bottom']))
                corp = page.evaluate("""() => {
                  const b = document.querySelector('.modal.sheet .modal-body');
                  return b ? { sh: b.scrollHeight, ch: b.clientHeight } : null }""")
                bifa(corp is not None and corp['sh'] <= corp['ch'] + 1,
                     'corpul foii nu deruleaza peste lista care deruleaza si ea',
                     'scrollHeight %s > clientHeight %s' % (corp and corp['sh'], corp and corp['ch']))
                jos = page.evaluate(GEOM, '.fa-jos')
                bifa(jos is not None and jos['bottom'] <= TELEFON['height'] - KB + 1,
                     'randul „Categorie și recurență" ramane la vedere',
                     'jos la %s' % (jos and jos['bottom']))
                inainte_scris = page.evaluate(GEOM, '.modal.sheet')
                page.keyboard.type('Verifica')
                page.wait_for_timeout(400)
                dupa = page.evaluate(GEOM, '.modal.sheet')
                bifa(dupa is not None and inainte_scris is not None
                     and dupa['h'] == inainte_scris['h'],
                     'foaia nu-si schimba inaltimea cand scrii',
                     '%s -> %s px' % (inainte_scris and inainte_scris['h'], dupa and dupa['h']))

                # Tastatura coboara: foaia se aseaza la loc, jos.
                coboara_tastatura(page)
                f = page.evaluate(GEOM, '.modal.sheet')
                bifa(kb_acum(page) == 0 and f is not None and f['bottom'] >= TELEFON['height'] - 1,
                     'cand tastatura coboara, foaia coboara cu ea pe marginea ecranului',
                     'jos la %s' % (f and f['bottom']))
                inchide_tot(page)

            # ===== 5. FOAIA TASKULUI RASPUNDE IMEDIAT =====
            out('\n--- foaia taskului raspunde imediat ---')
            mergi(page, baza, '/tasks')
            randuri = page.query_selector_all('.gl-fata')
            if len(randuri) < 3:
                bifa(False, 'lista are randuri', 'doar %d' % len(randuri))
            else:
                x, y = centru(randuri[2])
                u = urma(page, lambda: tap(cdp, page, x, y, 0), 700)
                primul = next((q for q in u if q['top'] is not None), None)
                bifa(primul is not None and primul['t'] <= 260,
                     'foaia porneste in cel mult 260 ms de la atingere (nu asteapta reteaua)',
                     'primul cadru cu foaie la %s ms' % (primul and primul['t']),
                     '%d ms' % (primul['t'] if primul else -1))
                # ===== 2b. CAMPUL DE SUBTASK =====
                btn = page.query_selector('.modal.sheet .sub-nou')
                if btn is None:
                    bifa(False, 'foaia are „Adaugă subtask"', 'lipseste .sub-nou')
                else:
                    xx, yy = centru(btn)
                    tap(cdp, page, xx, yy, 500)
                    ridica_tastatura(page)
                    camp = page.evaluate(GEOM, '.modal.sheet .sub-add input')
                    bifa(camp is not None and camp['bottom'] <= TELEFON['height'] - KB,
                         'campul de subtask sta deasupra tastaturii',
                         'jos la %s, tastatura de la %d' % (camp and camp['bottom'], TELEFON['height'] - KB))
                    coboara_tastatura(page)
                inchide_tot(page)

            # ===== 4. APASAREA LUNGA NU APASA NIMIC IN FOAIE =====
            out('\n--- ridicarea degetului dupa apasarea lunga ---')
            mergi(page, baza, '/tasks')
            randuri = page.query_selector_all('.gl-fata')
            nr = len(randuri)
            if nr:
                # PRIMA apasare lunga de pe pagina: foaia e creata odata cu
                # componenta ei, si fara `|global` aparea instant (Ion: „prima
                # data animatia este rupta"). Se masoara ca foaia URCA.
                x, y = centru(randuri[1])
                def lung():
                    apuca(cdp, x, y)
                    page.wait_for_timeout(470)
                    ridica(cdp, page, 0)
                u = urma(page, lung, 900)
                topuri = [q['top'] for q in u if q['top'] is not None]
                bifa(len(set(topuri)) >= 6 and topuri[0] > topuri[-1] + 150,
                     'PRIMA foaie de actiuni urca de jos, nu apare instant',
                     'topuri: %s' % topuri[:12], '%d cadre in miscare' % len(set(topuri)))
                inchide_tot(page)
                randuri = page.query_selector_all('.gl-fata')
                # Randul de JOS: degetul ajunge exact peste foaia care soseste.
                x, y = centru(randuri[min(nr - 1, 6)])
                apuca(cdp, x, y)
                page.wait_for_timeout(460)     # dupa puls (420), inainte de pragul nativ (500)
                sus = page.query_selector('.modal.sheet') is not None
                ridica(cdp, page, 700)
                inca = page.query_selector('.modal.sheet') is not None
                bifa(sus, 'foaia de actiuni soseste sub deget', 'nu s-a deschis la 460 ms')
                bifa(inca, 'ridicarea degetului NU inchide foaia si NU apasa un rand din ea',
                     'foaia a disparut la ridicare')
                bifa(len(page.query_selector_all('.gl-fata')) == nr,
                     'niciun task n-a fost sters sau mutat de clicul de la ridicare',
                     '%d -> %d randuri' % (nr, len(page.query_selector_all('.gl-fata'))))
                # ...dar o atingere adevarata in foaie chiar apasa.
                rand = page.query_selector('.modal.sheet .ft-rand')
                if rand and inca:
                    xx, yy = centru(rand)
                    tap(cdp, page, xx, yy, 600)
                    bifa(page.query_selector('.modal.sheet.varf') is None or page.query_selector('.fa') is not None,
                         'o atingere pornita PE foaie apasa randul ei',
                         'randul n-a raspuns')
                inchide_tot(page)

            # ===== 3. EDITORUL DE NOTE =====
            out('\n--- editorul de note, cu si fara tastatura ---')
            mergi(page, baza, '/tasks')
            randuri = page.query_selector_all('.gl-fata')
            if len(randuri) > 3:
                x, y = centru(randuri[3])
                tap(cdp, page, x, y, 800)
                link = page.query_selector('.modal.sheet .dt-nota-sec button')
                if link is None:
                    bifa(False, 'foaia are „Adaugă notă"', 'lipseste afordanța de notă')
                else:
                    xx, yy = centru(link)
                    tap(cdp, page, xx, yy, 900)
                    doc = page.evaluate(GEOM, '.modal-doc')
                    bifa(doc is not None, 'editorul se deschide ca foaie „doc"', 'fara .modal-doc')
                    if doc:
                        # Fara tastatura: „Salvează" nu e acoperit de bara de unelte.
                        salv = page.evaluate("""() => {
                          const b = [...document.querySelectorAll('.modal-doc .modal-footer button')].pop();
                          if (!b) return null;
                          const r = b.getBoundingClientRect();
                          const el = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
                          return { ok: !!el && (el === b || b.contains(el)), cine: el ? el.className : null, jos: Math.round(r.bottom) } }""")
                        bifa(salv is not None and salv['ok'], 'fara tastatura, „Salvează" nu e acoperit de bara de unelte',
                             'la centrul butonului raspunde %s' % (salv and salv['cine']))
                        ed = page.query_selector('.modal-doc [contenteditable="true"]')
                        ex, ey = centru(ed)
                        tap(cdp, page, ex, ey, 500)
                        ridica_tastatura(page)
                        kb_sus = kb_acum(page)
                        doc2 = page.evaluate(GEOM, '.modal-doc')
                        zona = page.evaluate(GEOM, '.modal-doc .rte-editor')
                        bara = page.evaluate(GEOM, '.modal-doc .rte-toolbar')
                        foot = page.evaluate(GEOM, '.modal-doc .modal-footer')
                        bifa(kb_sus == KB and doc2 is not None and doc2['bottom'] <= TELEFON['height'] - KB + 1,
                             'cu tastatura sus, documentul urca INTREG deasupra ei',
                             'jos la %s, tastatura de la %d' % (doc2 and doc2['bottom'], TELEFON['height'] - KB))
                        bifa(zona is not None and zona['h'] >= 150,
                             'zona de scris ramane de cel putin 150 px (era 55)',
                             '%s px' % (zona and zona['h']), '%s px' % (zona and zona['h']))
                        bifa(bara is not None and foot is not None and bara['bottom'] <= foot['top'] + 1
                             and foot['bottom'] <= TELEFON['height'] - KB + 1,
                             'bara de unelte si „Salvează" stau una sub alta, deasupra tastaturii',
                             'bara jos %s, subsol %s..%s' % (bara and bara['bottom'], foot and foot['top'], foot and foot['bottom']))
                coboara_tastatura(page)
                inchide_tot(page)

            # ===== 7. FOAIA ZILEI =====
            out('\n--- foaia zilei soseste la inaltime constanta ---')
            mergi(page, baza, '/calendar')
            zi = page.query_selector('[data-zi]')
            if zi is None:
                bifa(False, 'grila de calendar se randeaza', 'nicio celula [data-zi]')
            else:
                x, y = centru(zi)
                u = urma(page, lambda: tap(cdp, page, x, y, 0), 700)
                inaltimi = [q['h'] for q in u if q['h'] is not None]
                bifa(inaltimi and max(inaltimi) - min(inaltimi) <= 2,
                     'inaltimea foii `inalt` nu se anima in timpul sosirii',
                     '%s..%s px' % (min(inaltimi) if inaltimi else None, max(inaltimi) if inaltimi else None),
                     '%s px' % (inaltimi[0] if inaltimi else None))
                inchide_tot(page)

            # ===== 6. PAGINA PROIECTULUI: FOAIE PE TELEFON =====
            out('\n--- taskul din proiect se deschide in foaie (telefon) ---')
            mergi(page, baza, '/projects')
            card = page.query_selector('.pcard[role="button"]')
            if card is None:
                bifa(False, 'exista un proiect in lista', 'niciun card')
            else:
                card.click()
                page.wait_for_timeout(1400)
                page.add_style_tag(content=SAFE)
                randuri = page.query_selector_all('.gl-fata')
                if not randuri:
                    bifa(False, 'proiectul are taskuri in tabul Taskuri', 'niciun rand')
                else:
                    x, y = centru(randuri[0])
                    u = urma(page, lambda: tap(cdp, page, x, y, 0), 700)
                    primul = next((q for q in u if q['top'] is not None), None)
                    bifa(primul is not None and primul['t'] <= 260,
                         'atingerea randului deschide o FOAIE, repede',
                         'niciun .modal.sheet in 700 ms' if primul is None else '%d ms' % primul['t'],
                         '%d ms' % (primul['t'] if primul else -1))
                    bifa(page.query_selector('.modal.sheet .dt-referinta') is not None
                         and page.query_selector('.modal.sheet .sub-nou') is not None,
                         'foaia are capul taskului (bifa, titlu) si pasii',
                         'lipseste .dt-referinta sau .sub-nou')
                    bifa(page.query_selector('.subtask-body:not(.modal .subtask-body)') is None,
                         'nimic nu se mai desface in lista', 'a ramas un .subtask-body in lista')
                    inchide_tot(page)

            # ===== 9. ATERIZAREA DE PE „ASTĂZI" =====
            out('\n--- atingerea unui task de pe Acasa: aterizare hasurata ---')
            mergi(page, baza, '/', 1800)
            randuri = page.query_selector_all('.gl-fata')
            if len(randuri) < 2:
                bifa(False, 'boardul de azi are randuri', 'doar %d' % len(randuri))
            else:
                x, y = centru(randuri[1])
                page.evaluate("""() => { window.__A = []; window.__ag = true; (function s() {
                  if (window.__ag) window.__A.push({ t: Math.round(performance.now()), h: location.hash });
                  requestAnimationFrame(s) })() }""")
                tap(cdp, page, x, y, 1100)
                A = page.evaluate('window.__ag = false; window.__A')
                # Ecranul nu are voie sa inghete: intre doua cadre consecutive nu
                # trec mai mult de ~160ms (morph-ul ingheta 600-750).
                goluri = max((b_['t'] - a_['t']) for a_, b_ in zip(A, A[1:])) if len(A) > 1 else 0
                bifa(goluri < 160, 'ecranul nu ingheata la atingere (fara morph pe telefon)',
                     'cel mai lung gol intre cadre: %d ms' % goluri, 'gol maxim %d ms' % goluri)
                ajuns = page.evaluate('location.hash')
                bifa('/projects/' in ajuns or '/tasks' in ajuns, 'a ajuns la pagina taskului', ajuns)
                # Intre apasare si schimbarea paginii (de unde porneste si tranzitia)
                # nu au voie sa treaca mai mult de ~160ms pe atingere.
                h0 = A[0]['h'] if A else None
                schimb = next((q['t'] - A[0]['t'] for q in A if q['h'] != h0), None)
                # 200, nu 160: pragul lasa loc de jitter de masurare (headless
                # variaza ~120-165ms). O regresie reala — asteptarea preincarcarii
                # inainte de tranzitie — era 250ms+, deci tot se prinde.
                bifa(schimb is not None and schimb <= 200,
                     'pagina porneste sa se schimbe in cel mult 200 ms de la atingere',
                     'schimbarea rutei la %s ms' % schimb, '%s ms' % schimb)
                rand = page.evaluate("""() => {
                  const f = document.querySelector('.focus-flash');
                  if (!f) return null;
                  const r = f.getBoundingClientRect();
                  const dock = document.querySelector('.dock');
                  const jos = dock ? dock.getBoundingClientRect().top : window.innerHeight;
                  const sus = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--header-height')) || 0;
                  const fata = f.querySelector('.gl-fata');
                  const anim = fata ? getComputedStyle(fata, '::after').animationName : getComputedStyle(f, '::after').animationName;
                  return { top: Math.round(r.top), bottom: Math.round(r.bottom), sus, jos: Math.round(jos), anim } }""")
                bifa(rand is not None, 'randul-tinta e hasurat (`.focus-flash`) la 1 s dupa atingere', 'niciun .focus-flash')
                if rand:
                    bifa(rand['top'] >= rand['sus'] - 1 and rand['bottom'] <= rand['jos'] + 1,
                         'randul-tinta sta intre antet si dock, nu sub ele',
                         '%d..%d, vizibil %d..%d' % (rand['top'], rand['bottom'], rand['sus'], rand['jos']))
                    bifa(rand['anim'] == 'inelPuls', 'inelul care pulseaza se vede pe fata randului (ca la Calendar)',
                         'animationName=%s' % rand['anim'])

            bifa(not erori, 'nicio eroare de pagina pe tot parcursul', ' | '.join(erori)[:300])
            ctx.close()

            # ===== 6b. DESKTOP: PANOU =====
            out('\n--- taskul din proiect se deschide in panou (desktop) ---')
            ctx = b.new_context(viewport=DESKTOP)
            page = ctx.new_page()
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', PIN_TEST)
            page.press('#pin', 'Enter')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
            page.goto(baza + '/#/projects', wait_until='load')
            page.wait_for_timeout(1400)
            card = page.query_selector('.pcard[role="button"]')
            if card:
                card.click()
                page.wait_for_timeout(1400)
                rand = page.query_selector('.tmain')
                if rand:
                    rand.click()
                    page.wait_for_timeout(700)
                    bifa(page.query_selector('.modal-panou .dt-referinta') is not None,
                         'clicul pe rand deschide panoul lateral, ca in /tasks', 'fara .modal-panou')
                    # Panoul lasa lista la vedere sub un voal slab; un clic pe ea
                    # cade pe voal si inchide panoul — acelasi drum ca in /tasks.
                    bb = rand.bounding_box()
                    page.mouse.click(bb['x'] + bb['width'] / 2, bb['y'] + bb['height'] / 2)
                    page.wait_for_timeout(600)
                    bifa(page.query_selector('.modal-panou') is None,
                         'un clic pe lista de sub panou il inchide', 'panoul a ramas')
            b.close()
    finally:
        proc.terminate()

    out('')
    if esecuri:
        out('PICA — %d contract(e) incalcat(e):' % len(esecuri))
        for e in esecuri:
            out('  - ' + e)
        sys.exit(1)
    out('OK — foile respecta contractele cu tastatura.')


if __name__ == '__main__':
    main()

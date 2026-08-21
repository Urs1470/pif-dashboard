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
  1. DOUA MISCARI, NICIODATA DEODATA. Foaia de adaugare e o foaie normala de jos
     (ca modalul de detalii task): aluneca o data, monoton, SE ASAZA — si abia
     apoi vine tastatura si o ridica. Proba joaca doua latente si cere aceeasi
     secventa. Formele „pagina ancorata sus" si „urcare coregrafiata cu
     tastatura" au fost respinse: acolo cele doua miscari se calcau.
  2. NIMIC SUB TASTATURA. Campul focalizat, subsolul foii si corpul ei stau
     deasupra tastaturii; corpul nu deruleaza peste o lista care deruleaza si ea.
  3. EDITORUL DE NOTE urca intreg deasupra tastaturii (zona de scris ramanea de
     55px), iar fara tastatura bara de unelte nu acopera „Salvează".
  4. UN CLIC E AL FOII DOAR DACA A INCEPUT PE EA. Ridicarea degetului dupa
     apasarea lunga nu inchide si nu apasa nimic in foaia care tocmai a sosit.
  5. FOAIA TASKULUI RASPUNDE IMEDIAT, cu schelet, nu dupa retea.
  6. PAGINA PROIECTULUI deschide taskul in foaie (telefon) / panou (desktop),
     ca /tasks — nu il mai desface in lista.
  7. FOAIA ZILEI (`inalt`) soseste la inaltime constanta, nu crescand din mers.

    python scripts/audit_tastatura.py
"""

import json
import os
import sys
import tempfile

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADACINA, 'scripts'))

from audit_foaie import (PIN_TEST, TELEFON, apuca, bifa, esecuri, misca, out,
                         porneste_serverul, port_liber, ridica, seamana)

DESKTOP = {'width': 1280, 'height': 800}
KB = 312   # inaltimea tastaturii emulate, in px — cat are o tastatura Gboard pe 844
LAT = 420  # ms de la focus pana cand IME-ul e sus — masurat ca ordin de marime pe WebView
KB_URCA = 200  # cat dureaza urcarea tastaturii insasi (vezi `KB_URCA` in Modal)

# Tastatura falsa + urma per cadru. `__kbH` = cat urca la focus (0 = nu vine deloc,
# pentru proba de expirare). `__urma` retine, la fiecare cadru, geometria foii.
INIT = r"""
(() => {
  let kb = 0;
  const L = { resize: new Set(), scroll: new Set() };
  const fake = {
    get height() { return window.innerHeight - kb }, get width() { return window.innerWidth },
    get offsetTop() { return 0 }, get offsetLeft() { return 0 }, get pageTop() { return window.scrollY },
    get pageLeft() { return 0 }, get scale() { return 1 },
    addEventListener(t, f) { L[t]?.add(f) }, removeEventListener(t, f) { L[t]?.delete(f) },
    dispatchEvent(e) { L[e.type]?.forEach(f => f(e)); return true },
  };
  Object.defineProperty(window, 'visualViewport', { value: fake, configurable: true });
  window.__kbH = %d;
  window.__kbLat = %d;
  window.__tastatura = (h) => { kb = h; fake.dispatchEvent(new Event('resize')) };
  window.__kb = () => kb;
  const edit = (el) => !!el && !!el.matches && el.matches('input:not([type=checkbox]):not([type=radio]), textarea, [contenteditable="true"]');
  document.addEventListener('focusin', e => { if (edit(e.target)) setTimeout(() => { if (edit(document.activeElement) && window.__kbH) window.__tastatura(window.__kbH) }, window.__kbLat) }, true);
  document.addEventListener('focusout', () => { setTimeout(() => { if (!edit(document.activeElement)) window.__tastatura(0) }, 60) }, true);
  window.__urma = []; let pornita = false;
  window.__porneste = () => { window.__urma = []; pornita = true; window.__t0 = performance.now() };
  window.__opreste = () => { pornita = false; return window.__urma };
  (function s() {
    if (pornita) {
      const f = document.querySelector('.modal.sheet'); const b = document.querySelector('.backdrop');
      const r = f ? f.getBoundingClientRect() : null;
      window.__urma.push({ t: Math.round(performance.now() - window.__t0),
        top: r ? Math.round(r.top) : null, h: r ? Math.round(r.height) : null,
        pb: b ? Math.round(parseFloat(getComputedStyle(b).paddingBottom)) : null, kb });
    }
    requestAnimationFrame(s);
  })();
})();
""" % (KB, LAT)

# Telefonul lui Ion are edge-to-edge: safe-area reala. Pe emulator e 0, si exact
# asa au trecut neobservate doua runde de reparatii la foaia zilei.
SAFE = 'html { --safe-top: 48px !important; --safe-bottom: 24px !important; }'

GEOM = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), h: Math.round(r.height) };
}"""


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

            # ===== 1. DOUA MISCARI, NICIODATA IN ACELASI TIMP =====
            # Foaia de adaugare e o FOAIE NORMALA de jos — aceeasi ca modalul de
            # detalii task si ca foaia de la apasarea lunga (Ion, 2026-08-21:
            # „vreau o animatie lina precum la modalul detalii task sau la
            # atingere lunga"). Formele „pagina ancorata sus" si „urcare
            # coregrafiata cu tastatura" au fost incercate si RESPINSE — de
            # fiecare data pentru ca doua miscari se calcau: foaia si tastatura
            # pe aceiasi pixeli, in acelasi interval („foarte haotica").
            #
            # Contractul de acum e o SECVENTA, si asta se masoara:
            #   1. foaia aluneca de jos, o singura data, monoton, si SE ASAZA;
            #   2. abia DUPA aceea vine tastatura si o ridica — a doua miscare,
            #      curata, care nu se suprapune peste prima.
            # Proba joaca doua latente de tastatura (devreme si tarziu): secventa
            # trebuie sa fie aceeasi de fiecare data.
            out('\n--- foaia de adaugare: doua miscari, niciodata deodata ---')
            mergi(page, baza, '/tasks')
            fab = page.query_selector('.fab')
            if fab is None:
                bifa(False, 'butonul de adaugare exista pe /tasks', 'fara .fab')
            else:
                asezata = []
                for lat in (900, LAT):
                    page.evaluate('window.__kbLat = %d' % lat)
                    fab = page.query_selector('.fab')
                    x, y = centru(fab)
                    u = urma(page, lambda: tap(cdp, page, x, y, 0), lat + 900)
                    cu_foaie = [q for q in u if q['top'] is not None]
                    if not cu_foaie:
                        bifa(False, 'foaia se deschide (tastatura la %d ms)' % lat, 'niciun cadru cu foaie')
                        continue

                    def kb_px(q):
                        try:
                            return float(str(q['kb']).replace('px', '') or 0)
                        except ValueError:
                            return 0.0

                    # Faza 1: pana la primul cadru cu tastatura (sau tot filmul).
                    idx_kb = next((i for i, q in enumerate(cu_foaie) if kb_px(q) > 0), None)
                    faza1 = cu_foaie[:idx_kb] if idx_kb is not None else cu_foaie
                    topuri1 = [q['top'] for q in faza1]
                    urca = all(b_ <= a_ + 1 for a_, b_ in zip(topuri1, topuri1[1:]))
                    bifa(urca, 'faza 1: foaia urca monoton, fara sa oscileze (tastatura la %d ms)' % lat,
                         'topuri: %s' % topuri1[:30])
                    # Se ASAZA: ultimele cadre ale fazei 1 stau pe loc.
                    coada = [q['top'] for q in faza1[-6:]]
                    bifa(len(coada) >= 3 and max(coada) - min(coada) <= 1,
                         'faza 1: foaia se ASAZA inainte sa vina tastatura',
                         'ultimele cadre: %s' % coada, 'asezata la %d px' % (coada[-1] if coada else -1))
                    # Cat a durat urcarea (contract: ~280ms, ca la detalii task).
                    t_asezat = faza1[-1]['t'] if faza1 else None
                    prima = faza1[0]['t'] if faza1 else 0
                    if faza1:
                        stabil = faza1[-1]['top']
                        t_asezat = next(q['t'] for q in faza1 if abs(q['top'] - stabil) <= 1)
                        bifa(t_asezat - prima <= 420,
                             'faza 1: urcarea tine ~280 ms (ca foaia de detalii task)',
                             'a tinut %d ms' % (t_asezat - prima), '%d ms' % (t_asezat - prima))

                    # Faza 2 exista si vine DUPA. Tastatura nu are voie sa urce cat
                    # timp foaia inca aluneca — asta era „haotic".
                    if idx_kb is not None:
                        t_kb = cu_foaie[idx_kb]['t']
                        bifa(t_kb >= t_asezat,
                             'faza 2: tastatura vine DUPA ce foaia s-a asezat, nu peste ea',
                             'tastatura la %d ms, foaia asezata la %d ms' % (t_kb, t_asezat),
                             'tastatura la %d ms (asezata la %d)' % (t_kb, t_asezat))
                        dupa_kb = [q['top'] for q in cu_foaie[idx_kb:]]
                        coada2 = dupa_kb[-6:]
                        bifa(max(coada2) - min(coada2) <= 1,
                             'faza 2: dupa ce tastatura a urcat, foaia sta pe loc',
                             'ultimele cadre: %s' % coada2)

                    camp = page.evaluate(GEOM, '.fa-cauta input')
                    bifa(camp is not None and camp['bottom'] <= TELEFON['height'] - KB,
                         'campul „Ce ai de făcut?" ramane deasupra tastaturii',
                         'jos la %s, tastatura de la %d' % (camp and camp['bottom'], TELEFON['height'] - KB))
                    ultim = cu_foaie[-1]
                    bifa(ultim['top'] + ultim['h'] <= TELEFON['height'] - KB + 1,
                         'foaia se termina deasupra tastaturii',
                         'jos la %s, tastatura de la %d' % (ultim['top'] + ultim['h'], TELEFON['height'] - KB))
                    if lat == LAT:
                        page.keyboard.type('Verifica')
                        page.wait_for_timeout(400)
                        camp2 = page.evaluate(GEOM, '.fa-cauta input')
                        bifa(camp2 is not None and abs(camp2['top'] - camp['top']) <= 1,
                             'nici cand scrii foaia nu se muta',
                             '%s -> %s' % (camp and camp['top'], camp2 and camp2['top']))
                        asezata = [ultim]
                        break
                    inchide_tot(page)
                page.evaluate('window.__kbLat = %d' % LAT)

                # ===== 2. NIMIC SUB TASTATURA =====
                out('\n--- nimic sub tastatura ---')
                page.wait_for_timeout(300)
                kb_sus = page.evaluate('window.__kb()')
                bifa(kb_sus == KB, 'tastatura emulata e sus', 'kb=%s' % kb_sus)
                bifa(page.evaluate("document.documentElement.classList.contains('are-tastatura')"),
                     '<html> poarta `are-tastatura`', 'clasa lipseste')
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
                page.keyboard.type('Verifica')
                page.wait_for_timeout(400)
                dupa = page.evaluate(GEOM, '.modal.sheet')
                bifa(dupa is not None and dupa['h'] == asezata[-1]['h'] if asezata else False,
                     'foaia nu-si schimba inaltimea cand scrii',
                     '%s -> %s px' % (asezata and asezata[-1]['h'], dupa and dupa['h']))

                # Tastatura coboara: foaia se aseaza la loc, jos.
                page.evaluate('document.activeElement.blur()')
                page.wait_for_timeout(600)
                f = page.evaluate(GEOM, '.modal.sheet')
                bifa(page.evaluate('window.__kb()') == 0 and f is not None and f['bottom'] >= TELEFON['height'] - 1,
                     'cand tastatura coboara, foaia coboara cu ea pe marginea ecranului',
                     'jos la %s' % (f and f['bottom']))
                bifa(not page.evaluate("document.documentElement.classList.contains('are-tastatura')"),
                     '`are-tastatura` pleaca odata cu tastatura', 'clasa a ramas')
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
                    tap(cdp, page, xx, yy, 900)
                    camp = page.evaluate(GEOM, '.modal.sheet .sub-add input')
                    bifa(page.evaluate('window.__kb()') == KB and camp is not None and camp['bottom'] <= TELEFON['height'] - KB,
                         'campul de subtask sta deasupra tastaturii',
                         'jos la %s, kb=%s' % (camp and camp['bottom'], page.evaluate('window.__kb()')))
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
                link = page.query_selector('.modal.sheet .td-link')
                if link is None:
                    bifa(False, 'foaia are „Adaugă notă"', 'lipseste .td-link')
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
                        tap(cdp, page, ex, ey, 900)
                        kb_sus = page.evaluate('window.__kb()')
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
                    bifa(page.query_selector('.modal.sheet .ts-cap') is not None
                         and page.query_selector('.modal.sheet .sub-nou') is not None,
                         'foaia are capul taskului (bifa, titlu) si subtaskurile',
                         'lipseste .ts-cap sau .sub-nou')
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
                    bifa(page.query_selector('.modal-panou .ts-cap') is not None,
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

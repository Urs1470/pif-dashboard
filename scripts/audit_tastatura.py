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
  1. O SINGURA SOSIRE. Cand inaltimea tastaturii e stiuta (a doua deschidere pe
     acelasi aparat), foaia se naste cu podeaua ridicata si urca o singura data,
     la inaltime constanta; sosirea tastaturii nu o mai misca.
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
  8. PREVEDEREA EXPIRA: daca tastatura nu vine, foaia coboara la loc in ~1,2s.

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
  window.__tastatura = (h) => { kb = h; fake.dispatchEvent(new Event('resize')) };
  window.__kb = () => kb;
  const edit = (el) => !!el && !!el.matches && el.matches('input:not([type=checkbox]):not([type=radio]), textarea, [contenteditable="true"]');
  document.addEventListener('focusin', e => { if (edit(e.target)) setTimeout(() => { if (edit(document.activeElement) && window.__kbH) window.__tastatura(window.__kbH) }, 250) }, true);
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
""" % KB

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

            # ===== 1. O SINGURA SOSIRE =====
            out('\n--- foaia de adaugare: o singura sosire, cu tastatura ---')
            mergi(page, baza, '/tasks')
            fab = page.query_selector('.fab')
            if fab is None:
                bifa(False, 'butonul de adaugare exista pe /tasks', 'fara .fab')
            else:
                x, y = centru(fab)
                # PRIMA deschidere: aparatul nu stie inca inaltimea tastaturii, deci
                # o invata acum. Proba e pe a DOUA.
                u1 = urma(page, lambda: tap(cdp, page, x, y, 0), 1100)
                invatat = page.evaluate("localStorage.getItem('pif-kb')")
                bifa(invatat == str(KB), 'inaltimea tastaturii se invata la prima deschidere',
                     'pif-kb=%r' % invatat, '%s px' % invatat)
                bifa(cadre_in_repaus(u1, 330) > 100,
                     'prima deschidere (fara sa stie tastatura) chiar are doua sosiri — proba de control',
                     'a doua miscare a fost de %d px' % cadre_in_repaus(u1, 330),
                     'a doua miscare: %d px' % cadre_in_repaus(u1, 330))
                inchide_tot(page)

                fab = page.query_selector('.fab')
                x, y = centru(fab)
                u2 = urma(page, lambda: tap(cdp, page, x, y, 0), 1100)
                cu_foaie = [q for q in u2 if q['top'] is not None]
                if not cu_foaie:
                    bifa(False, 'foaia se deschide a doua oara', 'niciun cadru cu foaie')
                else:
                    primul = cu_foaie[0]
                    bifa(primul['pb'] == KB, 'podeaua e ridicata din PRIMUL cadru (tastatura prevazuta)',
                         'padding-bottom=%s la %d ms' % (primul['pb'], primul['t']), '%d px' % primul['pb'])
                    inaltimi = [q['h'] for q in cu_foaie]
                    bifa(max(inaltimi) - min(inaltimi) <= 2, 'inaltimea foii e constanta cat urca',
                         '%d..%d px' % (min(inaltimi), max(inaltimi)), '%d px' % inaltimi[0])
                    topuri = [q['top'] for q in cu_foaie]
                    urca = all(b_ <= a_ + 1 for a_, b_ in zip(topuri, topuri[1:]))
                    bifa(urca, 'foaia urca o singura data, fara sa coboare pe drum',
                         'topuri: %s' % topuri[:40])
                    a_doua = cadre_in_repaus(u2, 330)
                    bifa(a_doua <= 2, 'dupa ce s-a asezat, sosirea tastaturii n-o mai misca',
                         'a mai urcat %d px dupa 330 ms' % a_doua, 'a doua miscare: %d px' % a_doua)
                    asezata = [q for q in cu_foaie if q['t'] >= 330]
                    if asezata:
                        bifa(asezata[-1]['top'] + asezata[-1]['h'] <= TELEFON['height'] - KB + 1,
                             'foaia sta in intregime deasupra tastaturii',
                             'jos la %d, tastatura de la %d' % (asezata[-1]['top'] + asezata[-1]['h'], TELEFON['height'] - KB))

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

            # ===== 8. PREVEDEREA EXPIRA =====
            out('\n--- prevederea expira daca tastatura nu vine ---')
            page.evaluate('window.__kbH = 0')
            fab = page.query_selector('.fab')
            if fab:
                x, y = centru(fab)
                tap(cdp, page, x, y, 200)
                devreme = page.evaluate(GEOM, '.modal.sheet')
                page.wait_for_timeout(1500)
                tarziu = page.evaluate(GEOM, '.modal.sheet')
                kb_css = page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--kb')")
                bifa(kb_css.strip() == '0px', 'dupa ~1,2s fara tastatura, `--kb` revine la 0', '--kb=%s' % kb_css)
                bifa(tarziu is not None and tarziu['bottom'] >= TELEFON['height'] - 1,
                     'foaia coboara la loc, pe marginea ecranului',
                     '%s -> %s' % (devreme and devreme['bottom'], tarziu and tarziu['bottom']))
                inchide_tot(page)
            page.evaluate('window.__kbH = %d' % KB)

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

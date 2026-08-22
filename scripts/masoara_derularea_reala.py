# -*- coding: utf-8 -*-
"""CAT DE NETED DERULEAZA LISTA PE TELEFONUL REAL.

Pe masina de dezvoltare, cu 133 de taskuri, derularea pierdea 13-14% din cadre —
iar cu 13 taskuri doar 6%. Cifra aia a fost argumentul pentru virtualizarea
listelor, adica o rescriere care atinge glisarea, apasarea lunga, `animate:flip`,
gruparea si aterizarea hasurata. Inainte de o asemenea schimbare, intrebarea
trebuie pusa acolo unde conteaza raspunsul.

Derularea se face cu `adb shell input swipe` — o aruncare ADEVARATA, prin
conducta de gesturi a sistemului. `Input.dispatchTouchEvent` prin CDP nu trece
prin compozitorul de derulare al Android-ului, deci ar masura altceva.

    python scripts/masoara_derularea_reala.py
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aparat
from playwright.sync_api import sync_playwright

CEAS = """() => {
  window.__c = [];
  let u = performance.now();
  (function f() {
    const n = performance.now();
    window.__c.push(+(n - u).toFixed(1));
    u = n;
    requestAnimationFrame(f);
  })();
  window.__r = () => { window.__c = [] };
  window.__d = () => window.__c;
}"""


def rezuma(c, prag):
    """`prag` vine din cadenta REALA a ecranului, nu din 60Hz presupus: pe un
    ecran de 120Hz un cadru de 16ms inseamna deja unul pierdut."""
    c = [x for x in c if x < 500]
    if len(c) < 20:
        return 'prea putine cadre (%d)' % len(c)
    s = sorted(c)
    lungi = [x for x in c if x > prag]
    return ('median %.1f | p95 %.1f | peste %.0fms: %d din %d (%.0f%%)'
            % (s[len(s) // 2], s[int(len(s) * 0.95)], prag, len(lungi), len(c),
               100.0 * len(lungi) / len(c)))


def main():
    if not aparat.aparat():
        print('Niciun aparat.')
        return 1
    aparat.trezeste()
    aparat.tine_ecranul_aprins(True)
    s = aparat.deschide_puntea()
    if not s:
        print('APK-ul instalat nu e inspectabil.')
        return 2

    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp('http://localhost:%d' % aparat.PORT)
        page = br.contexts[0].pages[0]
        lat, inalt = aparat.ecran()
        page.evaluate("location.hash = '#/tasks'")
        page.wait_for_timeout(2500)

        # CADENTA ECRANULUI, masurata: telefonul e la 120Hz, dar WebView-ul poate
        # fi plafonat. Fara ea, „cadru peste 32ms" ar fi pragul altui aparat.
        page.evaluate(CEAS)
        page.wait_for_timeout(1200)
        repaus = [x for x in page.evaluate('window.__d()') if x < 500]
        cadenta = statistics.median(repaus) if len(repaus) > 10 else 16.7
        prag = cadenta * 1.9
        print('Cadenta ecranului: %.1f ms/cadru (%.0f Hz) -> prag de cadru pierdut: %.0f ms'
              % (cadenta, 1000 / cadenta, prag))
        print('In REPAUS: %s' % rezuma(repaus, prag))

        randuri = page.evaluate("document.querySelectorAll('.trow').length")
        noduri = page.evaluate("document.querySelectorAll('*').length")
        print('Lista: %d randuri, %d noduri DOM' % (randuri, noduri))

        page.evaluate('window.__r()')
        # Patru aruncari de sus in jos, ca un deget grabit.
        x = lat // 2
        for _ in range(4):
            aparat.adb('shell', 'input', 'swipe', str(x), str(int(inalt * 0.75)),
                       str(x), str(int(inalt * 0.25)), '120')
            time.sleep(0.7)
        print('La DERULARE: %s' % rezuma(page.evaluate('window.__d()'), prag))
        br.close()

    aparat.tine_ecranul_aprins(False)
    return 0


if __name__ == '__main__':
    sys.exit(main())

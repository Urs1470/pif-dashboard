# -*- coding: utf-8 -*-
"""CE FACE TASTATURA ADEVARATA, masurat in WebView-ul de pe telefonul lui Ion.

Intrebarea la care raspunde, si la care nicio proba de pe masina de dezvoltare
n-a putut raspunde: cand Gboard urca peste foaia de creare task, viewportul se
micsoreaza INTR-UN PAS sau pe o rampa? Si ce vede pagina — `innerHeight`,
`visualViewport`, `--kb`?

Toata reparatia din 2026-08-21 s-a bazat pe un raspuns DEDUS din citirea sursei
Capacitor (`SystemBars.java:208` pune `setPadding` o data, deci un pas). Aici se
verifica pe aparat.

Nu se emuleaza nimic:
  * atingerea e `adb shell input tap` — eveniment de sistem, deci Gboard chiar
    urca (evenimentele Playwright raman in pagina si nu ajung la IME);
  * geometria se citeste din CHIAR WebView-ul aplicatiei, prin CDP;
  * ce se masoara e ce vede Ion.

    python scripts/masoara_tastatura_reala.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aparat
from playwright.sync_api import sync_playwright

# Urma: un esantion pe cadru, cu tot ce ar putea explica miscarea.
URMA = r"""
(() => {
  window.__u = []; window.__on = false;
  window.__start = () => { window.__u = []; window.__t0 = performance.now(); window.__on = true };
  window.__stop  = () => { window.__on = false; return window.__u };
  // O SINGURA BUCLA PE PAGINA. Fara garda asta, fiecare reinjectare (adica
  // fiecare rulare a probei pe aceeasi pagina) mai porneste un lant care scrie
  // in ACELASI `__u`: prima masuratoare a raportat 366 fps, adica sase bucle
  // suprapuse, cu fiecare cadru numarat de sase ori.
  if (window.__bucla) return;
  window.__bucla = true;
  const cs = getComputedStyle(document.documentElement);
  (function pas() {
    if (window.__on) {
      const f = document.querySelector('.modal.sheet');
      const r = f ? f.getBoundingClientRect() : null;
      const a = document.activeElement;
      const ar = a && a.getBoundingClientRect ? a.getBoundingClientRect() : null;
      const vv = window.visualViewport;
      window.__u.push({
        t: +(performance.now() - window.__t0).toFixed(1),
        ih: window.innerHeight,
        vvh: vv ? +vv.height.toFixed(1) : null,
        vvo: vv ? +vv.offsetTop.toFixed(1) : null,
        vvs: vv ? +vv.scale.toFixed(3) : null,
        top: r ? +r.top.toFixed(1) : null,
        h: r ? +r.height.toFixed(1) : null,
        kb: parseFloat(cs.getPropertyValue('--kb')) || 0,
        sb: parseFloat(cs.getPropertyValue('--safe-bottom')) || 0,
        // BODY nu e un camp. Dupa `blur` el devine `activeElement`, iar
        // marginea lui de jos e a documentului — asta raporta „campul e sub
        // tastatura" pe toata coborarea, cand de fapt niciun camp nu era focalizat.
        actJos: (ar && a !== document.body && a !== document.documentElement)
                ? +ar.bottom.toFixed(1) : null,
      });
    }
    requestAnimationFrame(pas);
  })();
})();
"""


def dreptunghi(page, sel):
    return page.evaluate(
        """(s) => { const e = document.querySelector(s); if (!e) return null;
           const r = e.getBoundingClientRect();
           return {x: r.left + r.width / 2, y: r.top + r.height / 2,
                   top: r.top, jos: r.bottom, h: r.height}; }""", sel)


def cadenta(u):
    """Cate cadre pe secunda a avut urma. Telefonul lui Ion e la 120Hz, deci
    „cate cadre a durat" nu inseamna nimic fara asta."""
    if len(u) < 10:
        return 0.0
    span = u[-1]['t'] - u[0]['t']
    return (len(u) - 1) * 1000.0 / span if span else 0.0


def analiza(u, eticheta):
    print('\n--- %s ---' % eticheta)
    if not u:
        print('  (urma goala)')
        return
    print('  %d cadre in %.0f ms  (%.0f fps)'
          % (len(u), u[-1]['t'] - u[0]['t'], cadenta(u)))

    sch = [(u[i]['t'], u[i - 1]['ih'], u[i]['ih'])
           for i in range(1, len(u)) if u[i]['ih'] != u[i - 1]['ih']]
    if not sch:
        print('  VIEWPORT: neschimbat (%d px)' % u[0]['ih'])
    else:
        for t, a, b in sch:
            print('  VIEWPORT t=%7.1f ms: %d -> %d  (%+d px)' % (t, a, b, b - a))
        print('  FORMA: %s' % ('UN PAS' if len(sch) == 1 else
                               'RAMPA, %d trepte in %.0f ms'
                               % (len(sch), sch[-1][0] - sch[0][0])))

    print('  --kb: %s' % sorted(set(q['kb'] for q in u)))

    v = [q for q in u if q['top'] is not None]
    if not v:
        print('  foaia: absenta din urma')
        return
    print('  foaia: top %.0f -> %.0f,  inaltime %.0f -> %.0f'
          % (v[0]['top'], v[-1]['top'], v[0]['h'], v[-1]['h']))

    if not sch:
        return
    t0 = sch[0][0]
    dupa = [q for q in v if q['t'] >= t0 - 1]
    if len(dupa) < 3:
        print('  DUPA SALT: prea putine cadre')
        return

    pasi = [(b['t'], round(b['top'] - a['top'], 1))
            for a, b in zip(dupa, dupa[1:]) if abs(b['top'] - a['top']) > 0.4]
    if not pasi:
        print('  DUPA SALT: foaia NU s-a miscat — a sarit odata cu viewportul')
    else:
        print('  DUPA SALT: %d cadre de miscare in %.0f ms, cel mai mare pas %.1f px'
              % (len(pasi), pasi[-1][0] - t0, max(abs(d) for _, d in pasi)))
        semne = set(1 if d > 0 else -1 for _, d in pasi)
        print('  SENS: %s' % ('intr-o singura directie'
                              if len(semne) == 1 else 'SCHIMBA DIRECTIA — palpaire'))

    hh = sorted(set(q['h'] for q in dupa))
    print('  inaltimea dupa salt: %s -> %s'
          % (hh, 'un singur pas, corect' if len(hh) <= 2 else 'SE ANIMEAZA (gresit)'))

    camp = [q for q in dupa if q['actJos'] is not None]
    if camp:
        sub = [q for q in camp if q['actJos'] > q['ih'] + 1]
        print('  campul focalizat sub tastatura: %s'
              % ('NU, niciun cadru' if not sub else '%d cadre (GRESIT)' % len(sub)))

    # CADRU CU CADRU IN JURUL SALTULUI. Rezumatele de mai sus spun CE s-a
    # intamplat; asta arata IN CE ORDINE — singurul mod de a vedea daca `vv.height`
    # si `innerHeight` se schimba in acelasi cadru sau unul dupa altul.
    fer = [q for q in u if t0 - 120 <= q['t'] <= t0 + 320]
    if fer:
        print('  ---- cadru cu cadru (%.0f ms in jurul saltului) ----' % 440)
        print('       t      ih    vv.h   --kb   foaie.top  foaie.h')
        ant = None
        for q in fer:
            cheie = (q['ih'], q['vvh'], q['kb'], q['top'], q['h'])
            if cheie == ant:
                continue          # doar cadrele in care S-A SCHIMBAT ceva
            ant = cheie
            print('    %6.1f  %5s  %6s  %5s   %8s  %7s'
                  % (q['t'], q['ih'], q['vvh'], q['kb'],
                     q['top'] if q['top'] is not None else '-',
                     q['h'] if q['h'] is not None else '-'))


def main():
    dev = aparat.aparat()
    if not dev:
        print('Niciun aparat. Verifica USB si `adb devices`.')
        return 1
    print('Aparat: %s' % dev)

    if not aparat.socket_devtools():
        print('Aplicatia nu ruleaza — o pornesc...')
        aparat.porneste_aplicatia()
    s = aparat.deschide_puntea()
    if not s:
        print('FARA SOCKET DEVTOOLS: APK-ul instalat nu e inspectabil.')
        return 2
    print('Socket: %s  ->  localhost:%d' % (s, aparat.PORT))

    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp('http://localhost:%d' % aparat.PORT)
        page = br.contexts[0].pages[0]
        aparat.trezeste()
        aparat.tine_ecranul_aprins(True)
        print('Pagina: %s' % page.url)
        print('Ecran: %sx%s   dpr=%s' % (*aparat.ecran(), page.evaluate('devicePixelRatio')))

        def fara_tastatura():
            """Coboara IME-ul si ASTEAPTA sa se vada in viewport.

            `blur` din pagina, nu `keyevent`: ESC sau BACK ar putea inchide si
            foaia, si atunci masor alt lucru decat cel cerut.
            """
            for _ in range(20):
                page.evaluate('document.activeElement && document.activeElement.blur()')
                page.wait_for_timeout(150)
                if page.evaluate('innerHeight') >= plin - 2:
                    return True
            return False

        # RE-INCARCARE, ca sa nu ramana bucle de urma din rularile anterioare:
        # garda `__bucla` traieste in pagina, deci se curata doar la o incarcare
        # noua. Aplicatia isi reia sesiunea din cookie, deci nu cere PIN.
        page.evaluate("location.hash = '#/tasks'")
        page.reload(wait_until='load')
        page.wait_for_timeout(2500)
        # Inaltimea „plina" se AFLA, nu se presupune: daca la pornire tastatura e
        # deja sus (o sesiune anterioara a lasat-o asa), orice masuratoare de
        # dupa ar porni de la o valoare micsorata si n-ar vedea nicio schimbare.
        plin = 0
        for _ in range(20):
            page.evaluate('document.activeElement && document.activeElement.blur()')
            page.wait_for_timeout(200)
            h = page.evaluate('innerHeight')
            if h == plin:
                break
            plin = h
        # CE BUILD RULEAZA. Fara asta, o masuratoare pe o versiune veche servita
        # din service worker arata identic cu una in care reparatia n-a mers.
        print('Build pe telefon: %s' % page.evaluate(
            "[...document.querySelectorAll('script[src]')].map(s=>s.src.split('/').pop())[0]"))
        print('Viewport fara tastatura: %d px' % plin)
        page.evaluate(URMA)

        # ===== A. SCENARIUL LUI ION =====
        # „se deschide bine, animatia e ok ca viteza, dupa apare brusc tastatura
        # android". Foaia de creare focalizeaza campul singura, deci sosirea foii
        # si sosirea IME-ului sunt in ACEEASI urma — cum le vede si el.
        page.evaluate('window.__start()')
        r = dreptunghi(page, '.fab')
        if not r:
            print('Fara `.fab` pe /tasks.')
            return 3
        x, y = aparat.catre_aparat(page, r['x'], r['y'])
        aparat.atinge(x, y)
        time.sleep(3.0)
        a = page.evaluate('window.__stop()')
        analiza(a, 'A. FOAIA SE DESCHIDE SI VINE TASTATURA (ce vede Ion)')

        # ===== B. TASTATURA URCA PESTE O FOAIE DEJA ASEZATA =====
        fara_tastatura()
        page.wait_for_timeout(500)
        page.evaluate('window.__start()')
        camp = dreptunghi(page, '.modal.sheet input, .modal.sheet textarea, '
                                '.modal.sheet [contenteditable]')
        if camp:
            cx, cy = aparat.catre_aparat(page, camp['x'], camp['y'])
            aparat.atinge(cx, cy)
        time.sleep(2.5)
        b = page.evaluate('window.__stop()')
        analiza(b, 'B. TASTATURA URCA PESTE FOAIA ASEZATA')

        # ===== C. TASTATURA COBOARA =====
        page.evaluate('window.__start()')
        fara_tastatura()
        time.sleep(1.5)
        c = page.evaluate('window.__stop()')
        analiza(c, 'C. TASTATURA COBOARA')

        aparat.tine_ecranul_aprins(False)
        with open('urma_tastatura_reala.json', 'w', encoding='utf-8') as f:
            json.dump({'A': a, 'B': b, 'C': c}, f, indent=1)
        print('\nUrma bruta: urma_tastatura_reala.json')
        br.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())

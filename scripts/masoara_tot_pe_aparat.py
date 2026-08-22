# -*- coding: utf-8 -*-
"""TOATE INTERACTIUNILE, MASURATE PE TELEFONUL LUI ION, CU DATELE LUI.

Tot ce s-a masurat pana acum in emulare se masoara aici pe aparat: deschideri,
inchideri pe fiecare drum, aterizarea hasurata, sosirea tastaturii, derularea pe
fiecare pagina, si reparatiile de ieri (dubla atingere, bara de tragere).

NU SCRIE NIMIC. Datele din aplicatie sunt cele reale ale lui Ion — opt taskuri,
optsprezece proiecte. Deci se masoara doar ce se poate face fara sa se schimbe
ceva: se deschid foi si se inchid, se atinge si se navigheaza, iar gesturile se
opresc SUB prag. Nicio bifare, nicio creare, nicio stergere, nicio planificare.

Atingerea vine din `adb shell input`, nu din CDP: pe aparat gestul trebuie sa
treaca prin conducta sistemului, altfel se masoara altceva (si tastatura nici
n-ar urca).

    python scripts/masoara_tot_pe_aparat.py
"""
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aparat
from playwright.sync_api import sync_playwright

URMA = r"""
(() => {
  if (window.__gata) return;
  window.__gata = true;
  window.__u = []; window.__sel = null;
  window.__start = (s) => { window.__sel = s; window.__u = []; window.__t0 = performance.now() };
  window.__stop = () => { const u = window.__u; window.__sel = null; return u };
  window.__c = []; let ultim = performance.now();
  window.__cr = () => { window.__c = [] };
  window.__cd = () => window.__c;
  (function pas() {
    const acum = performance.now();
    window.__c.push(+(acum - ultim).toFixed(1)); ultim = acum;
    if (window.__sel) {
      const el = document.querySelector(window.__sel);
      const r = el ? el.getBoundingClientRect() : null;
      window.__u.push({ t: +(acum - window.__t0).toFixed(1),
        top: r ? +r.top.toFixed(1) : null, h: r ? +r.height.toFixed(1) : null,
        ih: window.innerHeight,
        kb: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--kb')) || 0 });
    }
    requestAnimationFrame(pas);
  })();
})();
"""

PANDA = r"""() => {
  window.__s = null; window.__t = performance.now();
  const o = new MutationObserver(() => { if (window.__s === null) window.__s = performance.now() - window.__t });
  o.observe(document.body, {attributes: true, childList: true, subtree: true, attributeFilter: ['class','style']});
  window.__sp = () => { o.disconnect(); return window.__s };
}"""


def netezime(u, camp='top'):
    v = [q for q in u if q.get(camp) is not None]
    if len(v) < 3:
        return {'cadre': 0}
    pasi = [b[camp] - a[camp] for a, b in zip(v, v[1:])]
    m = [d for d in pasi if abs(d) > 0.4]
    if not m:
        return {'cadre': 0, 'de_la': round(v[0][camp]), 'la': round(v[-1][camp])}
    intoarceri = sum(1 for a, b in zip(m, m[1:]) if a * b < 0)
    return {'cadre': len(m), 'pas_max': round(max(abs(d) for d in m), 1),
            'intoarceri': intoarceri, 'de_la': round(v[0][camp]), 'la': round(v[-1][camp])}


def cadre(c, prag):
    c = [x for x in c if x < 500]
    if len(c) < 20:
        return 'prea putine (%d)' % len(c)
    s = sorted(c)
    lungi = [x for x in c if x > prag]
    return 'median %.1f | p95 %.1f | peste prag: %d/%d (%.0f%%)' % (
        s[len(s) // 2], s[int(len(s) * 0.95)], len(lungi), len(c), 100.0 * len(lungi) / len(c))


class Aparat:
    def __init__(self, page):
        self.page = page
        self.dpr = page.evaluate('devicePixelRatio')
        self.lat, self.inalt = aparat.ecran()

    def geo(self, sel):
        return self.page.evaluate(
            """(s) => { const e = document.querySelector(s); if (!e) return null;
               const r = e.getBoundingClientRect();
               return {x: r.left + r.width/2, y: r.top + r.height/2, top: r.top,
                       jos: r.bottom, w: r.width, h: r.height}; }""", sel)

    def atinge(self, sel, pauza=0.9):
        g = self.geo(sel)
        if not g:
            return None
        aparat.atinge(g['x'] * self.dpr, g['y'] * self.dpr, pauza)
        return g

    def atinge_xy(self, x, y, pauza=0.9):
        """Coordonate CSS, ca peste tot in fisierul asta.

        Prima varianta era chemata cu `a.lat / a.dpr` — adica deja convertit — si
        inmultea inca o data: atingerea „pe mijlocul voalului" cadea de fapt pe
        marginea din dreapta a ecranului, iar proba raporta ca voalul nu inchide
        foaia. Nu o inchidea nimeni; nimeni n-o atinsese."""
        aparat.atinge(x * self.dpr, y * self.dpr, pauza)

    def trage(self, x1, y1, x2, y2, ms=260):
        aparat.adb('shell', 'input', 'swipe',
                   str(int(x1 * self.dpr)), str(int(y1 * self.dpr)),
                   str(int(x2 * self.dpr)), str(int(y2 * self.dpr)), str(ms))
        time.sleep(0.9)

    def exista(self, sel):
        return self.page.evaluate('(s) => !!document.querySelector(s)', sel)

    def cate(self, sel):
        return self.page.evaluate('(s) => document.querySelectorAll(s).length', sel)

    def mergi(self, ruta, pauza=2000):
        self.page.evaluate('(r) => { location.hash = r }', '#' + ruta)
        self.page.wait_for_timeout(pauza)
        self.page.evaluate(URMA)

    def urma(self, sel, act, coada=900):
        self.page.evaluate('(s) => window.__start(s)', sel)
        act()
        self.page.wait_for_timeout(coada)
        return self.page.evaluate('window.__stop()')

    def raspuns(self, sel):
        g = self.geo(sel)
        if not g:
            return None
        self.page.evaluate(PANDA)
        aparat.atinge(g['x'] * self.dpr, g['y'] * self.dpr, 0.5)
        try:
            v = self.page.evaluate('window.__sp()')
        except Exception:
            return None
        return round(v, 1) if v is not None else None


def main():
    if not aparat.aparat():
        print('Niciun aparat conectat.')
        return 1
    aparat.trezeste()
    aparat.tine_ecranul_aprins(True)
    s = aparat.deschide_puntea()
    if not s:
        print('APK-ul instalat nu e inspectabil.')
        return 2
    try:
        with sync_playwright() as p:
            br = p.chromium.connect_over_cdp('http://localhost:%d' % aparat.PORT)
            page = br.contexts[0].pages[0]
            a = Aparat(page)
            page.evaluate(URMA)
            print('Aparat: %s   ecran %sx%s   dpr %s' % (aparat.aparat(), a.lat, a.inalt, a.dpr))

            # Cadenta ecranului, ca pragul de „cadru pierdut" sa fie al LUI, nu 60Hz presupus.
            page.evaluate('window.__cr()')
            page.wait_for_timeout(1200)
            rep = [x for x in page.evaluate('window.__cd()') if x < 500]
            cad = statistics.median(rep) if len(rep) > 10 else 16.7
            prag = cad * 1.9
            print('Cadenta in repaus: %.1f ms (%.0f Hz) -> prag %.0f ms' % (cad, 1000 / cad, prag))

            print('')
            print('=== RASPUNS LA ATINGERE ===')
            print('  ATENTIE: numarul include si drumul lui `adb shell input tap`')
            print('  (o comanda de shell pornita pe telefon), deci NU e latenta aplicatiei.')
            print('  E util doar ca sa compari intrari intre ele, nu ca valoare absoluta.')
            for ruta, sel, nume in [('/', '.fab', 'Acasa: buton adaugare'),
                                    ('/', '.amain', 'Acasa: rand de task'),
                                    ('/tasks', '.fab', 'Taskuri: buton adaugare'),
                                    ('/tasks', '.tmain', 'Taskuri: rand'),
                                    ('/projects', '.pcard', 'Proiecte: card')]:
                a.mergi(ruta)
                r = a.raspuns(sel)
                print('  %-26s %s ms' % (nume, r if r is not None else 'selector lipsa'))
                aparat.adb('shell', 'input', 'keyevent', '4')
                time.sleep(0.8)

            print('')
            print('=== FOI: sosire si fiecare drum de iesire ===')
            for ruta, decl, nume in [('/tasks', '.fab', 'foaia de adaugare'),
                                     ('/tasks', '.tmain', 'foaia taskului'),
                                     ('/calendar', '.zi', 'foaia zilei')]:
                a.mergi(ruta)
                if not a.exista(decl):
                    print('  %-20s declansator lipsa' % nume)
                    continue
                u = a.urma('.modal.sheet, .modal', lambda: a.atinge(decl, 1.0), coada=500)
                n = netezime(u, 'top')
                h = netezime(u, 'h')
                print('  %-20s sosire: %d cadre, pas max %s, intoarceri %s | inaltimea se anima: %s'
                      % (nume, n.get('cadre', 0), n.get('pas_max', '-'), n.get('intoarceri', '-'),
                         ('DA (%d cadre)' % h['cadre']) if h.get('cadre') else 'nu'))
                for cum in ['BACK', 'voal', 'bara']:
                    if not a.exista('.modal'):
                        a.mergi(ruta)
                        a.atinge(decl, 1.0)
                    if cum == 'BACK':
                        def act():
                            aparat.adb('shell', 'input', 'keyevent', '4')
                            time.sleep(0.9)
                    elif cum == 'voal':
                        # Jumatatea distantei dintre marginea de sus si foaie:
                        # y=40 cade in bara de stare pe un ecran edge-to-edge.
                        gm = a.geo('.modal')
                        def act(gm=gm):
                            lat_css = page.evaluate('innerWidth')
                            y = max(60, int((gm['top'] if gm else 200) / 2))
                            a.atinge_xy(lat_css / 2, y, 0.9)
                    else:
                        g = a.geo('.modal')

                        def act(g=g):
                            if g:
                                a.trage(g['x'], g['top'] + 8, g['x'], g['top'] + 380, 300)
                    u2 = a.urma('.modal.sheet, .modal', act, coada=900)
                    n2 = netezime(u2, 'top')
                    ramas = 'MODAL' if a.exista('.modal') else ('VOAL' if a.exista('.backdrop') else 'curat')
                    print('        iesire prin %-5s: %d cadre, pas max %-6s -> ramas: %s'
                          % (cum, n2.get('cadre', 0), n2.get('pas_max', '-'), ramas))
                    if a.exista('.modal'):
                        aparat.adb('shell', 'input', 'keyevent', '4')
                        time.sleep(0.8)

            print('')
            print('=== ATERIZAREA HASURATA (Acasa -> taskul lui), de trei ori ===')
            for i in range(3):
                a.mergi('/')
                g = a.geo('.amain')
                if not g:
                    print('  agenda de azi e goala — nimic de atins')
                    break
                page.evaluate("""() => { window.__f = []; const t0 = performance.now();
                  const iv = setInterval(() => { window.__f.push([Math.round(performance.now()-t0),
                    !!document.querySelector('.focus-flash')]) }, 25);
                  setTimeout(() => clearInterval(iv), 2600); window.__fd = () => window.__f; }""")
                aparat.atinge(g['x'] * a.dpr, g['y'] * a.dpr, 2.8)
                f = [x for x in page.evaluate('window.__fd()') if x[1]]
                print('  incercarea %d: %s' % (i + 1,
                      ('hasura de la %d la %d ms' % (f[0][0], f[-1][0])) if f else 'NU S-A APRINS'))

            print('')
            print('=== TASTATURA: cum soseste viewportul ===')
            a.mergi('/tasks')
            a.atinge('.fab', 1.2)
            camp = '.modal.sheet input, .fa-cauta input'
            if a.exista(camp):
                u = a.urma('.modal.sheet', lambda: a.atinge(camp, 2.2), coada=600)
                trepte = [(u[i]['t'], u[i - 1]['ih'], u[i]['ih'])
                          for i in range(1, len(u)) if u[i]['ih'] != u[i - 1]['ih']]
                n = netezime(u, 'top')
                print('  viewport: %d trepte -> %s' % (len(trepte),
                      'UN SALT' if len(trepte) <= 1 else 'RAMPA'))
                if trepte:
                    print('        de la %d la %d px, in %.0f ms'
                          % (trepte[0][1], trepte[-1][2], trepte[-1][0] - trepte[0][0]))
                print('  foaia  : %d cadre de miscare, pas max %s | --kb a luat: %s'
                      % (n.get('cadre', 0), n.get('pas_max', '-'),
                         sorted(set(q['kb'] for q in u))))
            else:
                print('  fara camp de text in foaie')
            aparat.adb('shell', 'input', 'keyevent', '4')
            time.sleep(0.6)
            aparat.adb('shell', 'input', 'keyevent', '4')
            time.sleep(0.9)

            print('')
            print('=== DUBLA ATINGERE PE BUTONUL DE ADAUGARE (reparatia de ieri) ===')
            a.mergi('/')
            inainte = a.cate('.arow')
            g = a.geo('.fab')
            if g:
                aparat.atinge(g['x'] * a.dpr, g['y'] * a.dpr, 0.12)
                aparat.atinge(g['x'] * a.dpr, g['y'] * a.dpr, 2.0)
                acum = a.cate('.arow')
                print('  foi deschise: %d (trebuie 1) | randuri: %d (erau %d) -> a adaugat singur: %s'
                      % (a.cate('.modal.sheet'), acum, inainte, acum != inainte))
                aparat.adb('shell', 'input', 'keyevent', '4')
                time.sleep(0.9)

            print('')
            print('=== DERULARE, pe fiecare pagina ===')
            for ruta in ['/', '/tasks', '/projects', '/plan', '/calendar']:
                a.mergi(ruta)
                page.evaluate('window.__cr()')
                x = a.lat // 2
                for _ in range(3):
                    aparat.adb('shell', 'input', 'swipe', str(x), str(int(a.inalt * 0.75)),
                               str(x), str(int(a.inalt * 0.3)), '130')
                    time.sleep(0.6)
                print('  %-11s %s' % (ruta, cadre(page.evaluate('window.__cd()'), prag)))

            print('')
            print('=== NAVIGAREA DIN DOCK ===')
            for i, nume in [(1, 'Acasa'), (2, 'Taskuri'), (3, 'Plan'), (4, 'Calendar')]:
                sel = '.dock-item:nth-of-type(%d)' % i
                if not a.exista(sel):
                    continue
                r = a.raspuns(sel)
                time.sleep(1.0)
                print('  -> %-9s %s ms' % (nume, r if r is not None else '-'))
            br.close()
    finally:
        aparat.tine_ecranul_aprins(False)
    return 0


if __name__ == '__main__':
    sys.exit(main())

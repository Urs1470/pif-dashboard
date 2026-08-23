# -*- coding: utf-8 -*-
"""Banc de proba pentru interactiunile de pe telefon: unelte, nu verdicte.

`audit_mobil.py` verifica CONTRACTE care se stiu dinainte. Fisierul asta e pentru
partea dinaintea contractelor: sa te uiti la o pagina si sa vezi ce face, cadru cu
cadru, cand o atingi — inainte sa stii ce cauti.

Ce da, si de ce fiecare:
  * `Banc` — porneste serverul si o pagina de telefon cu ATINGERE ADEVARATA, cu
    safe-area simulata. Mouse-ul lui Playwright emite `pointerType: 'mouse'`, iar
    gesturile aplicatiei ies exact pe conditia asta: cu el, proba ar raporta verde
    pe un gest care nici n-a pornit.
  * `urma()` — geometria unui selector la fiecare cadru, cat tine o actiune.
  * `raspuns()` — cate ms trec de la deget pana se schimba CEVA pe ecran. Ochiul
    nu vede „a inceput sa se calculeze"; vede prima miscare.
  * `netezime()` — cel mai mare pas intre doua cadre, si daca miscarea schimba
    directia. Un singur salt de 80px strica o animatie care altfel e perfecta.

    from proba_mobil import Banc
    with Banc() as b:
        b.mergi('/tasks')
        print(b.raspuns('.fab'))
"""
import json
import os
import sys
import sqlite3
import tempfile

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RADACINA, 'scripts'))

from audit_foaie import (PIN_TEST, TELEFON, apuca, misca, porneste_serverul,
                         port_liber, ridica, seamana)

# Telefonul lui Ion e edge-to-edge. Pe emulator `env(safe-area-*)` e 0, si exact
# asa au trecut neobservate doua runde de reparatii la foaia zilei.
SAFE = 'html { --safe-top: 48px !important; --safe-bottom: 24px !important; }'

URMA = r"""
(() => {
  if (window.__u_gata) return;
  window.__u_gata = true;
  window.__u = []; window.__sel = null;
  window.__start = (sel) => { window.__sel = sel; window.__u = []; window.__t0 = performance.now(); };
  window.__stop = () => { const u = window.__u; window.__sel = null; return u; };
  (function pas() {
    if (window.__sel) {
      const el = document.querySelector(window.__sel);
      const r = el ? el.getBoundingClientRect() : null;
      window.__u.push({
        t: +(performance.now() - window.__t0).toFixed(1),
        top: r ? +r.top.toFixed(1) : null,
        left: r ? +r.left.toFixed(1) : null,
        w: r ? +r.width.toFixed(1) : null,
        h: r ? +r.height.toFixed(1) : null,
        op: el ? +parseFloat(getComputedStyle(el).opacity).toFixed(3) : null,
        tr: el ? getComputedStyle(el).transform : null,
      });
    }
    requestAnimationFrame(pas);
  })();
})();
"""

# „S-a schimbat ceva pe ecran" masurat pe SCHELETUL paginii, nu pe un selector
# anume: raspunsul poate veni ca o umbra, o tenta, un rand care se muta — iar
# daca proba stie dinainte UNDE sa se uite, rateaza tocmai raspunsurile care nu
# s-au gandit inca.
PANDA = r"""
(() => {
  window.__schimbat = null;
  window.__t0p = performance.now();
  const obs = new MutationObserver(() => {
    if (window.__schimbat === null) window.__schimbat = performance.now() - window.__t0p;
  });
  obs.observe(document.body, {attributes: true, childList: true, subtree: true,
                              attributeFilter: ['class', 'style']});
  window.__opresteP = () => { obs.disconnect(); return window.__schimbat; };
})();
"""


def goleste(cale):
    """Baza cu schema, dar FARA niciun rand.

    Starile goale sunt cele mai rar privite si cele mai usor de stricat: nimeni
    nu ajunge la ele in timpul dezvoltarii, fiindca baza de proba are mereu date.
    """
    sys.path.insert(0, RADACINA)
    os.environ['PIF_DB_PATH'] = cale
    import database
    database.init_db()


def umple(cale, proiecte=24, taskuri=120):
    """Cat sa nu incapa pe un ecran: liste lungi, multe carduri.

    Baza obisnuita are UN proiect si sapte taskuri — adica exact cazul in care
    orice problema de derulare, de aliniere pe randul al doilea sau de taiere la
    marginea de jos e invizibila.
    """
    import uuid
    seamana(cale)
    db = sqlite3.connect(cale)
    clienti = ['Fabrica 2', 'Uzina Nord', 'Depozit Vest', 'Hala 7', 'Statia de tratare']
    tipuri = ['retrofit', 'extindere', 'mentenanta', 'automatizare']
    for i in range(proiecte):
        db.execute(
            "INSERT INTO proiecte (id, nume, client, tip, status) VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()),
             'Proiect %02d — linie de ambalare cu nume lung pentru rupere' % (i + 1),
             clienti[i % len(clienti)], tipuri[i % len(tipuri)],
             'finalizat' if i % 5 == 0 else 'pregatire'))
    for i in range(taskuri):
        db.execute(
            "INSERT INTO global_tasks (id, titlu, status, categorie, data_scadenta)"
            " VALUES (?,?,?,?,?)",
            (str(uuid.uuid4()),
             'Task %03d cu un titlu destul de lung cat sa treaca de o linie' % (i + 1),
             'to_do', 'General', '2026-08-%02d' % (i % 28 + 1)))
    db.commit()
    db.close()


class Banc:
    """UN SINGUR BANC PER PROCES cand schimbi baza.

    `database` retine calea de la primul import, iar `init_db()` chemat a doua
    oara initializeaza tot baza DINTAI — al doilea `Banc` cu alte date cade cu
    „no such table: proiecte". Doua volume de date = doua rulari de Python.
    """

    def __init__(self, latime=None, inaltime=None, date='normal'):
        self.lat = latime or TELEFON['width']
        self.inalt = inaltime or TELEFON['height']
        self.date = date

    def __enter__(self):
        from playwright.sync_api import sync_playwright
        self.lucru = tempfile.mkdtemp(prefix='pif-proba-')
        db = os.path.join(self.lucru, 'proba.db')
        {'gol': goleste, 'mult': umple}.get(self.date, seamana)(db)
        port = port_liber()
        self.proc, self.baza = porneste_serverul(
            port, db, os.path.join(self.lucru, 'server.log'))
        self._pw = sync_playwright().start()
        self.br = self._pw.chromium.launch()
        self.ctx = self.br.new_context(
            viewport={'width': self.lat, 'height': self.inalt},
            has_touch=True, is_mobile=True)
        self.page = self.ctx.new_page()
        self.cdp = self.ctx.new_cdp_session(self.page)
        self.erori = []
        self.page.on('pageerror', lambda e: self.erori.append(str(e)))
        self.page.goto(self.baza + '/login')
        self.page.fill('#pin', PIN_TEST)
        self.page.press('#pin', 'Enter')
        self.page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
        return self

    def __exit__(self, *a):
        try:
            self.br.close()
            self._pw.stop()
        finally:
            self.proc.terminate()

    # ------------------------------------------------------------- navigare
    def mergi(self, ruta, pauza=1500):
        """Pagina, de la ZERO. `goto` catre acelasi hash NU reincarca — e navigare
        in acelasi document — deci o foaie ramasa deschisa din proba dinainte
        supravietuia, si masuratoarea urmatoare pornea cu ea pe ecran. Prima
        varianta a probei a raportat asa „foaia soseste in 0 cadre": era deja
        acolo. Deci se forteaza o incarcare adevarata."""
        tinta = self.baza + '/#' + ruta
        if self.page.url == tinta:
            self.page.reload(wait_until='load')
        else:
            self.page.goto(tinta, wait_until='load')
            if self.page.url != tinta:
                self.page.goto(tinta, wait_until='load')
        self.page.wait_for_timeout(pauza)
        self.page.add_style_tag(content=SAFE)
        self.page.evaluate(URMA)

    def centru(self, sel):
        return self.page.evaluate(
            """(s) => { const e = document.querySelector(s); if (!e) return null;
               const r = e.getBoundingClientRect();
               return {x: r.left + r.width / 2, y: r.top + r.height / 2,
                       top: r.top, jos: r.bottom, st: r.left, dr: r.right,
                       w: r.width, h: r.height}; }""", sel)

    # ------------------------------------------------------------ atingerea
    def atinge(self, sel, pauza=600):
        c = self.centru(sel)
        if not c:
            return None
        apuca(self.cdp, c['x'], c['y'])
        self.page.wait_for_timeout(30)
        ridica(self.cdp, self.page, pauza)
        return c

    def apasa_lung(self, sel, tine=650, pauza=600):
        c = self.centru(sel)
        if not c:
            return None
        apuca(self.cdp, c['x'], c['y'])
        self.page.wait_for_timeout(tine)
        ridica(self.cdp, self.page, pauza)
        return c

    def trage(self, sel, dx, dy, pasi=14, dt=16, ridica_la_final=True):
        c = self.centru(sel)
        if not c:
            return None
        apuca(self.cdp, c['x'], c['y'])
        for i in range(1, pasi + 1):
            misca(self.cdp, c['x'] + dx * i / pasi, c['y'] + dy * i / pasi)
            self.page.wait_for_timeout(dt)
        if ridica_la_final:
            ridica(self.cdp, self.page, 700)
        return c

    # ------------------------------------------------------------- masurare
    def raspuns(self, sel, tine=0):
        """Doua numere, fiindca degetul asteapta doua lucruri diferite.

        `apasare` — ms de la degetul JOS pana se schimba ceva. Asta e confirmarea
        ca atingerea a fost primita (o tenta, o umbra, un rand care se stramta).
        Lipsa ei e ce se simte ca „nu reactioneaza".
        `actiune` — ms de la degetul RIDICAT pana se schimba ceva. Asta e fapta
        propriu-zisa: pagina care pleaca, foaia care urca.

        Prima varianta pornea cronometrul inainte de degetul jos si le amesteca pe
        amandoua cu doua drumuri CDP — masura probei, nu a aplicatiei.
        """
        c = self.centru(sel)
        if not c:
            return None
        self.page.evaluate(PANDA)
        apuca(self.cdp, c['x'], c['y'])
        self.page.wait_for_timeout(tine or 60)
        apasare = self.page.evaluate('window.__schimbat')
        self.page.evaluate(PANDA)          # cronometru nou, pentru ridicare
        ridica(self.cdp, self.page, 400)
        # Daca actiunea a INCARCAT alt document (o ancora obisnuita, nu ruta din
        # hash), cronometrul a plecat odata cu pagina veche. Asta nu e o eroare de
        # masurat, e un raspuns pe care nu-l putem cronometra din interior.
        try:
            actiune = self.page.evaluate('window.__opresteP()')
        except Exception:
            actiune = None
        return {
            'apasare': round(apasare, 1) if apasare is not None else None,
            'actiune': round(actiune, 1) if actiune is not None else None,
        }

    def urma(self, sel, act, coada=900):
        self.page.evaluate('window.__start(%s)' % json.dumps(sel))
        act()
        self.page.wait_for_timeout(coada)
        return self.page.evaluate('window.__stop()')

    @staticmethod
    def netezime(u, camp='top'):
        """Cat de neted a curs.

        `intoarceri` in loc de un simplu „a ezitat": proiectul foloseste
        DINADINS un elan care depaseste tinta cu ~3.8% si se aseaza inapoi
        (`--ease-arc-elan`, vezi comentariul de la `.seg-cursor`). O metrica
        binara raporta elanul ala ca defect — adica exact intentia, pe dos.
        O intoarcere mica, la sfarsit, e elan; mai multe, sau una mare, e
        palpaire.

        CE NU POATE DEOSEBI, si de aceea verdictul se citeste, nu se crede:
        doua animatii LEGITIME una dupa alta arata la fel ca una care palpaie.
        Doua apasari rapide pe „luna urmatoare" dau doua alunecari — exact ce
        cere comentariul de la `{#key anchor}` din Calendar — iar verdictul iese
        „PALPAIE". Cand il vezi, uita-te intai daca n-au fost doua gesturi.
        """
        v = [q for q in u if q.get(camp) is not None]
        if len(v) < 3:
            return {'cadre': len(v), 'pas_max': None, 'de_la': None, 'la': None}
        pasi = [(b[camp] - a[camp]) for a, b in zip(v, v[1:])]
        misca_ = [d for d in pasi if abs(d) > 0.4]
        if not misca_:
            return {'cadre': 0, 'pas_max': 0, 'de_la': round(v[0][camp], 1),
                    'la': round(v[-1][camp], 1)}
        intoarceri = sum(1 for a, b in zip(misca_, misca_[1:]) if a * b < 0)
        drum = abs(v[-1][camp] - v[0][camp])
        semn = 1 if v[-1][camp] >= v[0][camp] else -1
        extrem = max((q[camp] * semn for q in v), default=0)
        peste = max(0.0, extrem - v[-1][camp] * semn)
        # DRUM APROAPE ZERO: o tranzitie `in:` pleaca dintr-un decalaj si se
        # aseaza la locul ei, deci primul si ultimul esantion coincid. Impartind
        # la un drum nul, procentul exploda si verdictul iesea „PALPAIE" pe o
        # alunecare perfect sanatoasa (grila de luni: 8 cadre, pas maxim 10px,
        # raportata 1000% depasire). Cand nu exista drum net, se raporteaza
        # AMPLITUDINEA in pixeli, care acolo e singura marime cu inteles.
        net = drum >= 4
        depasire = round(peste / drum * 100, 1) if net else None
        amplitudine = round(max(q[camp] for q in v) - min(q[camp] for q in v), 1)
        if net:
            verdict = ('curat' if intoarceri == 0 else
                       'elan' if intoarceri == 1 and depasire <= 8 else 'PALPAIE')
        else:
            # Fara drum net, „intoarcere" inseamna dus-intors — adica exact ce
            # face o alunecare `in:`. Palpaie doar daca se rasuceste de mai multe
            # ori.
            verdict = 'curat' if intoarceri <= 1 else 'PALPAIE'
        return {
            'cadre': len(misca_),
            'pas_max': round(max(abs(d) for d in misca_), 1),
            'intoarceri': intoarceri,
            'depasire%': depasire,
            'amplitudine': amplitudine,
            'verdict': verdict,
            'de_la': round(v[0][camp], 1),
            'la': round(v[-1][camp], 1),
        }

    def sub_ecran(self, sel):
        """Ce parte a elementului cade in afara ecranului sau sub dock/antet."""
        return self.page.evaluate(
            """(s) => { const e = document.querySelector(s); if (!e) return null;
               const r = e.getBoundingClientRect();
               const dock = document.querySelector('.dock');
               const antet = document.querySelector('.app-header, .bh');
               const dr = dock ? dock.getBoundingClientRect() : null;
               const ar = antet ? antet.getBoundingClientRect() : null;
               return {
                 iese_jos: Math.max(0, Math.round(r.bottom - innerHeight)),
                 iese_sus: Math.max(0, Math.round(-r.top)),
                 iese_dr: Math.max(0, Math.round(r.right - innerWidth)),
                 iese_st: Math.max(0, Math.round(-r.left)),
                 sub_dock: dr ? Math.max(0, Math.round(r.bottom - dr.top)) : 0,
                 sub_antet: ar ? Math.max(0, Math.round(ar.bottom - r.top)) : 0,
               }; }""", sel)

    def iese_din_ecran(self):
        """Ce depaseste latimea ecranului FARA sa fie intr-un derulator.

        Verificarea trebuie sa urce pe stramosi, nu doar sa se uite la element:
        Planificatorul isi tine grila intr-un `.chart-scroll` cu `overflow-x:
        auto` (1338px de continut in 796 vizibili), deci TOT ce e inauntru
        „depaseste" ecranul — corect, si tocmai asta e ideea. O verificare care
        se uita doar la element raporta cinci defecte inexistente pe peisaj.
        """
        return self.page.evaluate("""() => {
          const inDerulator = (el) => {
            let n = el.parentElement;
            while (n && n !== document.body) {
              const cs = getComputedStyle(n);
              if (cs.overflowX === 'auto' || cs.overflowX === 'scroll'
                  || cs.overflow === 'auto' || cs.overflow === 'scroll'
                  || cs.overflowX === 'hidden') return true;
              n = n.parentElement;
            }
            return false;
          };
          const rele = [];
          document.querySelectorAll('*').forEach(e => {
            const r = e.getBoundingClientRect();
            if (r.width < 8 || r.height < 8) return;
            const cs = getComputedStyle(e);
            if (cs.position === 'fixed') return;
            const peste = Math.round(r.right - innerWidth);
            if (peste <= 1 || inDerulator(e)) return;
            rele.push('.' + (e.className || '').toString().split(' ')
                      .filter(x => !x.startsWith('svelte-')).join('.') + ' +' + peste);
          });
          return [...new Set(rele)].slice(0, 6);
        }""")

    def exista(self, sel):
        return self.page.evaluate('(s) => !!document.querySelector(s)', sel)

    def cate(self, sel):
        return self.page.evaluate('(s) => document.querySelectorAll(s).length', sel)

# -*- coding: utf-8 -*-
"""BANCUL VERIFICATOARELOR: aplicatia, baza, browserul, degetul si raportul — o data.

DE CE EXISTA
Pana pe 2026-09-28 fiecare verificator cu browser isi scria singur aceleasi lucruri:
portul liber, pornirea Flask-ului, copia bazei, loginul, contextul de telefon,
atingerea prin CDP, randul de raport. Auditul din ziua aia a gasit ~600 de linii
copiate in noua scripturi — si, mai rau, copii care se despartisera fara ca cineva sa
fi hotarat asta: doar `smoke_ui` rula `init_db()` in server; `audit_tastatura`, unul
din cei trei din poarta, rula fara fusul orar al lui Ion, cu service worker activ si
ignora `PIF_CHROMIUM`; „telefon" insemna in `smoke_ui` un desktop ingustat, fara
atingere, iar in rest un telefon adevarat. Fiecare diferenta schimba ce poate prinde
un audit, si niciuna nu era o decizie.

Aici sta, o singura data, ce trebuie sa fie la fel peste tot. Ce e al unui singur
audit — masuratorile si contractele lui — ramane in fisierul lui.

CODURI DE IESIRE, aceleasi pentru toate verificatoarele (`ruleaza`):
    0  curat
    1  abatere in APLICATIE
    2  INSTRUMENTUL n-a ajuns la verdict: server mort, Playwright lipsa, baza lipsa,
       sau auditul a crapat pe drum
Diferenta dintre 1 si 2 conteaza: „aplicatia e stricata" si „proba e stricata" cer
reparatii in locuri diferite, iar pana acum aratau la fel.

VOCABULARUL raportului (`Raport`), acelasi peste tot:
    OK        contractul e respectat
    PICA      abatere — SE NUMARA
    NOTA      informatie, nu verdict (nu se numara)
    SARI      nu se aplica aici, cu motivul scris (nu se numara)
    ACCEPTAT  abatere cunoscuta, tinuta cu buna stiinta, cu motivul scris
"""

import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTURI = os.path.join(RADACINA, 'scripts')

# PIN-ul serverului de proba. Nu e al lui Ion: serverul porneste cu el in mediu.
PIN_TEST = '000000'

# FUSUL ORAR AL TESTELOR NU E UTC, CU BUNA STIINTA.
# Ion lucreaza in Romania (UTC+2/+3), iar containerele de test ruleaza pe UTC — unde ora
# locala si UTC coincid, deci orice greseala de conversie e INVIZIBILA. Asa a trecut
# neobservat un bug pe care il vedea la fiecare atingere: butoanele „Azi"/„Mâine"
# construiau data cu `new Date().toISOString()`, adica in UTC, iar miezul noptii local
# intr-un fus de la est de Greenwich cade in ziua precedenta. „Azi" scria IERI, la orice
# ora. Testele erau verzi.
FUS_TEST = 'Europe/Bucharest'

DESKTOP = {'width': 1280, 'height': 800}
TELEFON = {'width': 390, 'height': 844}

# `--tap-min` din tokens.css. O tinta mai mica e o abatere de la regula sistemului;
# pragul de 40 din `audit_mobil` era o toleranta nescrisa nicaieri altundeva.
TINTA_MIN = 44


def out(s=''):
    """Scrie UTF-8 indiferent de consola. Pe Windows, iesirea redirectata e cp1252,
    iar un „ș" dintr-un mesaj de compilator sau dintr-un titlu de task crapa
    `print` — adica auditul murea exact cand avea ceva de spus."""
    sys.stdout.buffer.write((str(s) + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


class InstrumentStricat(Exception):
    """Proba n-a putut masura. NU e un verdict despre aplicatie (iesire 2)."""


def ruleaza(main):
    """`sys.exit(banc.ruleaza(main))`: traduce orice sfarsit in codurile de mai sus."""
    try:
        cod = main()
    except InstrumentStricat as e:
        out('\nINSTRUMENT: %s' % e)
        out('Auditul n-a ajuns la verdict — nu e o afirmatie despre aplicatie.')
        return 2
    except KeyboardInterrupt:
        raise
    except Exception:
        out('\nINSTRUMENT: auditul a crapat pe drum, deci n-a ajuns la verdict.')
        out('Poate fi aplicatia (un element care nu mai apare), poate fi proba (un')
        out('selector ramas in urma) — urma de mai jos spune care:\n')
        out(traceback.format_exc())
        return 2
    return 1 if cod else 0


# ------------------------------------------------------------------- raportul

class Raport:
    """Randurile si numaratoarea unui audit. `incheie()` da codul de iesire."""

    def __init__(self):
        self.esecuri = []
        self.note = []

    def rand(self, stare, text, detaliu=''):
        out('  %-8s %s%s' % (stare, text, ('  — %s' % detaliu) if detaliu else ''))

    def ok(self, text, nota=''):
        self.rand('OK', text, nota)
        return True

    def pica(self, text, detaliu=''):
        self.rand('PICA', text, detaliu)
        self.esecuri.append('%s — %s' % (text, detaliu) if detaliu else text)
        return False

    def bifa(self, ok, text, detaliu='', nota=''):
        """`detaliu` explica ESECUL, `nota` insoteste reusita — altfel randul verde
        ajunge sa poarte textul unei probleme care nu s-a intamplat."""
        return self.ok(text, nota) if ok else self.pica(text, detaliu)

    def nota(self, text):
        self.rand('NOTA', text)
        self.note.append(text)

    def sari(self, text, motiv):
        self.rand('SARI', text, motiv)

    def acceptat(self, text, motiv):
        self.rand('ACCEPTAT', text, motiv)

    def adauga(self, n, eticheta):
        """Pentru auditurile care isi numara singure abaterile pe sectiuni."""
        for _ in range(int(n or 0)):
            self.esecuri.append(eticheta)

    def incheie(self, acceptate=None):
        return incheie(len(self.esecuri), note=self.note, acceptate=acceptate,
                       esecuri=self.esecuri)


def incheie(n, note=(), acceptate=None, esecuri=()):
    """Rezumatul de la capat, in aceeasi forma pentru toate auditurile."""
    out()
    if acceptate:
        out('Acceptate cu buna stiinta (nu se numara):')
        for k, de_ce in acceptate.items():
            out('  %-12s %s' % (k, de_ce))
        out()
    if note:
        out('Note (nu se numara):')
        for n_ in note:
            out('  - %s' % n_)
        out()
    if not n:
        out('OK — nimic de reparat.')
        return 0
    out('PICA — %d %s.' % (n, 'abatere' if n == 1 else 'abateri'))
    for e in list(esecuri)[:30]:
        out('  - %s' % e)
    return 1


def argumente(ap, baza=True, vizibil=True):
    """Flagurile comune, cu acelasi nume peste tot."""
    if baza:
        ap.add_argument('--baza', help='alta baza sursa (implicit pif_dashboard.db din proiect)')
    if vizibil:
        ap.add_argument('--vizibil', action='store_true', help='cu browserul pe ecran, pentru depanare')
    return ap


# ------------------------------------------------------------------ aplicatia

def port_liber():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def schema_noua(cale):
    """Baza goala, cu schema scrisa de `database.init_db()` — nu o a doua definitie a
    coloanelor. `DATABASE_PATH` se citeste la importul modulului, deci o suprascriem
    direct: altfel a doua baza noua din acelasi proces ar ajunge in prima."""
    if RADACINA not in sys.path:
        sys.path.insert(0, RADACINA)
    import database
    vechi = database.DATABASE_PATH
    database.DATABASE_PATH = cale
    try:
        database.init_db()
    finally:
        database.DATABASE_PATH = vechi


class Aplicatia:
    """Flask pe un port liber, pe o baza de UNICA FOLOSINTA. Context manager.

        with banc.Aplicatia() as app:             # copie a pif_dashboard.db (sau --baza)
        with banc.Aplicatia(noua=True, seamana=f): # baza goala + datele scrise de f(cale)

    `app.baza` e URL-ul, `app.db` calea bazei — singura in care o proba are voie sa
    scrie direct. Baza de lucru nu se atinge niciodata, iar directorul temporar se
    sterge la iesire (inainte ramaneau copii de 4 MB in %TEMP% dupa fiecare audit).
    """

    def __init__(self, sursa=None, noua=False, seamana=None, prefix='pif-banc-'):
        self.sursa = sursa
        self.noua = noua
        self.seamana = seamana
        self.prefix = prefix
        self.tmp = None
        self.db = None
        self.baza = None
        self.proc = None
        self._log = None
        self.cale_log = None

    def __enter__(self):
        self.tmp = tempfile.mkdtemp(prefix=self.prefix)
        self.db = os.path.join(self.tmp, 'banc.db')
        try:
            if self.noua:
                schema_noua(self.db)
            else:
                sursa = self.sursa or os.path.join(RADACINA, 'pif_dashboard.db')
                if not os.path.isfile(sursa) or os.path.getsize(sursa) == 0:
                    raise InstrumentStricat(
                        'Nu exista baza sursa %s. Adu una: scripts/sync_db_from_server.sh' % sursa)
                shutil.copy2(sursa, self.db)
            if self.seamana:
                self.seamana(self.db)
            self._porneste()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def _porneste(self):
        port = port_liber()
        env = dict(os.environ)
        env.update({
            'PIF_DB_PATH': self.db,
            'PIF_DASHBOARD_PIN': PIN_TEST,
            'SESSION_COOKIE_SECURE': 'false',
            # Zeci de pagini la rand depasesc pragul normal de 60/minut: am obtine
            # 429-uri peste tot — zgomot care ascunde erorile adevarate.
            'PIF_RATE_LIMIT': '100000',
            'PYTHONIOENCODING': 'utf-8',
            'PYTHONUTF8': '1',
        })
        cod = ('from app import app\n'
               'from database import init_db\n'
               'init_db()\n'
               'app.run(host="127.0.0.1", port=%d, debug=False, use_reloader=False, threaded=True)\n'
               % port)
        # Logul intr-un FISIER, nu intr-un pipe: serverul scrie o linie per cerere, iar
        # cu stdout=PIPE si nimeni care sa citeasca, bufferul de 64 KB se umple dupa
        # doua pagini si serverul se blocheaza in write() — identic cu o aplicatie moarta.
        self.cale_log = os.path.join(self.tmp, 'server.log')
        self._log = open(self.cale_log, 'wb')
        self.proc = subprocess.Popen([sys.executable, '-c', cod], cwd=RADACINA, env=env,
                                     stdout=self._log, stderr=subprocess.STDOUT)
        self.baza = 'http://127.0.0.1:%d' % port
        for _ in range(120):
            if self.proc.poll() is not None:
                raise InstrumentStricat('serverul a murit la pornire:\n%s' % self.coada_log())
            try:
                urllib.request.urlopen(self.baza + '/login', timeout=1).read()
                return
            except urllib.error.HTTPError:
                return                     # raspunde, chiar daca nu cu 200
            except Exception:
                time.sleep(0.5)
        raise InstrumentStricat('serverul nu a raspuns in 60 s')

    def coada_log(self, n=3000):
        try:
            if self._log:
                self._log.flush()
            return open(self.cale_log, encoding='utf-8', errors='replace').read()[-n:]
        except Exception:
            return ''

    def urme(self, n=15):
        """Liniile din logul serverului care explica un 500 vazut de browser."""
        return [l for l in self.coada_log(200000).splitlines()
                if 'Traceback' in l or 'ERROR' in l or ' 500 -' in l][-n:]

    def __exit__(self, *_):
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        if self._log is not None:
            try:
                self._log.close()
            except Exception:
                pass
        if self.tmp and not os.environ.get('PIF_BANC_PASTREAZA'):
            shutil.rmtree(self.tmp, ignore_errors=True)
        return False


# ----------------------------------------------------------------- browserul

def playwright():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise InstrumentStricat('lipseste playwright. Ruleaza:\n'
                                '  pip install playwright\n'
                                '  python -m playwright install chromium')
    return sync_playwright


def browserul(pw, vizibil=False):
    # PIF_CHROMIUM: pentru masinile unde Chromium e deja instalat in alta parte si
    # `playwright install` n-are voie sa descarce. Gol = comportamentul dintotdeauna.
    try:
        return pw.chromium.launch(headless=not vizibil,
                                  executable_path=os.environ.get('PIF_CHROMIUM') or None)
    except Exception as e:
        raise InstrumentStricat('Chromium nu porneste: %s' % str(e).split('\n')[0])


def context(browser, ecran='telefon', **extra):
    """Un context de TELEFON (atingere adevarata, `is_mobile`) sau de DESKTOP.

    Service worker-ul e blocat cu blocarea nativa a lui Playwright: altfel isi pune in
    cache chunkurile si o rulare testeaza ce a ramas de la cea dinainte. NU stubui
    `navigator.serviceWorker` cu undefined — aplicatia il apeleaza direct si ai obtine
    o „eroare" pe care ai fabricat-o tu.
    """
    opt = dict(viewport=dict(TELEFON if ecran == 'telefon' else DESKTOP),
               timezone_id=FUS_TEST, service_workers='block')
    if ecran == 'telefon':
        opt.update(is_mobile=True, has_touch=True)
    opt.update(extra)
    return browser.new_context(**opt)


def autentifica(ctx, baza, inchide=False):
    """Loginul, o singura data per context (cookie-ul e al contextului). Intoarce
    pagina (cu `page.retea`), pe `/#/` dupa redirect — o poti folosi sau inchide."""
    page = pagina(ctx)
    page.goto(baza + '/login', wait_until='load')
    page.fill('#pin', PIN_TEST)
    page.click('button[type="submit"]')
    try:
        page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
    except Exception:
        raise InstrumentStricat('loginul pe serverul de proba n-a trecut (PIN-ul de test?)')
    if inchide:
        page.close()
        return None
    return page


# PAGINA E „LINISTITA" cand nu mai are schelete, nicio animatie FINITA nu mai curge
# (nici CSS, nici arcurile JS din `lib/arc.js`, care se numara in `window.__arcuri`) si
# nicio cerere nu mai e in zbor. Cele infinite (un punct care pulseaza, un spinner) nu
# se termina niciodata, deci nu se asteapta.
#
# Inlocuieste `wait_for_timeout(N)` pus „ca sa se aseze". Auditul din 2026-09-28 a
# numarat ~186 s de asemenea pauze pe drumul portii: fiecare era ghicita pentru masina
# pe care a fost scrisa — prea lunga pe una rapida (timp pierdut la fiecare rulare) si
# prea scurta pe una lenta (masuratoare pe o pagina neasezata, deci un verdict fals).
# O conditie asteapta exact cat e nevoie, pe orice masina.
LINISTE = """() => {
  if (document.querySelector('[class*="skeleton"]')) return false;
  if ((window.__arcuri || 0) > 0) return false;       // arcurile din lib/arc.js (JS, nu CSS)
  return document.getAnimations().every(a => {
    if (a.playState !== 'running') return true;
    const t = a.effect && a.effect.getTiming ? a.effect.getTiming() : null;
    return t && t.iterations === Infinity;
  });
}"""


class Retea:
    """Cererile in zbor ale unei pagini, numarate din evenimentele lui Playwright.
    `networkidle` cere 500 ms de tacere DUPA ultima cerere — mai lent decat pauza pe
    care o inlocuieste; aici stim exact cand s-a intors ultima."""

    def __init__(self, page):
        self.in_zbor = 0
        page.on('request', self._pleaca)
        page.on('requestfinished', self._vine)
        page.on('requestfailed', self._vine)

    def _pleaca(self, _r):
        self.in_zbor += 1

    def _vine(self, _r):
        self.in_zbor = max(0, self.in_zbor - 1)


# Cat trebuie sa stea pagina linistita, la rand, ca sa zicem ca s-a asezat.
LINISTE_UI = 120        # dupa o schimbare de interfata (foaie, tab, filtru)
# Dupa o actiune care SCRIE pe server: aplicatia poate trimite cererea intarziat —
# bifarea asteapta 350 ms stampila (`INTARZIERE_BIFA`), cautarea din foaie 200 ms —
# iar in golul dintre animatie si cerere pagina pare linistita. Fereastra trebuie sa
# fie mai lunga decat orice astfel de amanare.
LINISTE_SERVER = 450


# De ce NU s-a linistit pagina, cand n-a apucat — altfel o asteptare care merge mereu
# pana la plafon arata ca o pauza fixa mai lunga, si nimeni nu vede de ce.
CE_MISCA = """() => {
  if (document.querySelector('[class*="skeleton"]')) return 'schelet';
  if ((window.__arcuri || 0) > 0) return window.__arcuri + ' arc(uri) JS in miscare (lib/arc.js)';
  const a = document.getAnimations().find(a => {
    if (a.playState !== 'running') return false;
    const t = a.effect && a.effect.getTiming ? a.effect.getTiming() : null;
    return !(t && t.iterations === Infinity);
  });
  if (!a) return null;
  const el = a.effect && a.effect.target;
  const cine = el ? (el.tagName.toLowerCase() + (el.className && typeof el.className === 'string'
    ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.') : '')) : '?';
  return (a.animationName || a.transitionProperty || a.constructor.name) + ' pe ' + cine;
}"""

# Jurnalul asteptarilor (`PIF_BANC_JURNAL=1`): cat a durat fiecare si, la plafon, de ce.
JURNAL = []


def asteapta_linistea(page, retea=None, timeout=6000, liniste_ms=LINISTE_UI):
    """True cand pagina a stat linistita `liniste_ms` la rand; False daca n-a apucat in
    `timeout` ms. Nu arunca: cine asteapta decide ce inseamna o pagina care nu se mai
    aseaza. `retea` implicit = cea atasata paginii de `pagina()`."""
    if retea is None:
        retea = getattr(page, 'retea', None)
    t0 = time.monotonic()
    linistita_din = None
    while (time.monotonic() - t0) * 1000 < timeout:
        try:
            ok = (retea is None or retea.in_zbor == 0) and page.evaluate(LINISTE)
        except Exception:
            ok = False                      # navigare in curs: contextul s-a schimbat
        acum = time.monotonic()
        if not ok:
            linistita_din = None
        elif linistita_din is None:
            linistita_din = acum
        elif (acum - linistita_din) * 1000 >= liniste_ms:
            _noteaza(t0, None)
            return True
        page.wait_for_timeout(40)
    motiv = 'cereri in zbor: %d' % retea.in_zbor if retea is not None and retea.in_zbor else None
    if motiv is None:
        try:
            motiv = page.evaluate(CE_MISCA) or '?'
        except Exception as e:
            motiv = 'nu s-a putut citi: %s' % str(e).split('\n')[0][:80]
    _noteaza(t0, motiv)
    return False


def _noteaza(t0, motiv):
    ms = int((time.monotonic() - t0) * 1000)
    JURNAL.append((ms, motiv))
    if os.environ.get('PIF_BANC_JURNAL'):
        out('        [liniste %5d ms%s]' % (ms, (' — PLAFON: %s' % motiv) if motiv else ''))


def pagina(ctx):
    """O pagina noua cu cererile ei urmarite (`page.retea`), ca `asteapta_linistea`
    sa stie si de retea, nu doar de schelete si animatii."""
    page = ctx.new_page()
    page.retea = Retea(page)
    return page


# ------------------------------------------------------------------- degetul
# ATINGERE ADEVARATA, prin `Input.dispatchTouchEvent` — nu `page.mouse`. Mouse-ul lui
# Playwright emite `pointerType: 'mouse'`, iar foile ies exact pe conditia asta (pe
# desktop n-au gest, au `X`): cu mouse-ul gestul nu porneste deloc, iar proba ar
# raporta un rezultat pentru un gest care n-a existat.

def cdp(page):
    return page.context.new_cdp_session(page)


def _punct(x, y):
    return {'touchPoints': [{'x': x, 'y': y, 'id': 1, 'radiusX': 6, 'radiusY': 6, 'force': 1}]}


def apuca(sesiune, x, y):
    sesiune.send('Input.dispatchTouchEvent', dict(type='touchStart', **_punct(x, y)))


def misca(sesiune, x, y):
    sesiune.send('Input.dispatchTouchEvent', dict(type='touchMove', **_punct(x, y)))


def ridica(sesiune):
    sesiune.send('Input.dispatchTouchEvent', dict(type='touchEnd', touchPoints=[]))


def atinge(sesiune, x, y):
    apuca(sesiune, x, y)
    ridica(sesiune)


def centru(el):
    """Centrul unui element (ElementHandle sau Locator), in coordonate de fereastra."""
    b = el.bounding_box()
    if not b:
        return None
    return b['x'] + b['width'] / 2, b['y'] + b['height'] / 2

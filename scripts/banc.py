# -*- coding: utf-8 -*-
"""BANCUL VERIFICATOARELOR: aplicatia pe o baza de unica folosinta, raportul si codurile de iesire.

DE CE EXISTA
Pana pe 2026-09-28 fiecare verificator isi scria singur aceleasi lucruri: portul liber,
pornirea Flask-ului, copia bazei, loginul, randul de raport. Auditul din ziua aia a gasit ~600
de linii copiate in noua scripturi — si copii care se despartisera fara ca cineva sa fi hotarat
asta. Aici sta, o singura data, ce trebuie sa fie la fel peste tot.

CE A PLECAT PE 2026-10-03, odata cu interfata veche: tot ce tinea de browser (Playwright,
Chromium, contextul de telefon, atingerea prin CDP, asteptarea „paginii linistite"). Au ramas
doar ce folosesc `scripts/test_suite.py` si `teste/` (`schema_noua`): serverul de unica
folosinta, raportul si codurile de iesire. Cum se aduce banc-ul intreg inapoi:
`docs/decizii/2026-10-03-retragerea-interfetei-vechi.md`.

CODURI DE IESIRE, aceleasi pentru toate verificatoarele (`ruleaza`):
    0  curat
    1  abatere in APLICATIE
    2  INSTRUMENTUL n-a ajuns la verdict: server mort, baza lipsa, sau proba a crapat pe drum
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

# PIN-ul serverului de proba. Nu e al lui Ion: serverul porneste cu el in mediu.
PIN_TEST = '000000'


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
        out('Poate fi aplicatia (un raspuns care nu mai arata ca inainte), poate fi proba (un')
        out('camp ramas in urma) — urma de mai jos spune care:\n')
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
            # Zeci de cereri la rand depasesc pragul normal de 60/minut: am obtine
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
        """Liniile din logul serverului care explica un 500 vazut de o proba."""
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

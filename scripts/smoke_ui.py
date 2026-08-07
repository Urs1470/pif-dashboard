# -*- coding: utf-8 -*-
"""Test de fum pentru interfata: deschide fiecare ruta si fiecare proiect intr-un
browser headless si pica la orice exceptie neprinsa sau eroare de consola.

DE CE EXISTA
Build-ul Svelte compileaza CURAT o pagina care crapa la rulare: componentele
folosite in template se rezolva la RULARE, nu la compilare. Pe 2026-07-27 un
import lipsa (`AlertCircle`) a lasat toate proiectele de tip Service blocate pe
schelet, cu build verde si `test_suite` 12/12 — pentru ca greseala statea pe o
ramura {#if project.tip === 'Service'}. Singurul mod de a prinde clasa asta e sa
deschizi paginile pe date reale.

De aceea testul nu se multumeste cu rutele: trece prin TOATE proiectele (ca sa
atinga ramurile dupa tip/date), prin toate taburile paginii de proiect, si
repeta totul pe latime de telefon (Planificatorul are markup exclusiv mobil, pe
care desktopul nu-l randeaza niciodata).

RULARE
    python scripts/smoke_ui.py            # tot: rute + proiecte, desktop + mobil
    python scripts/smoke_ui.py --rapid    # doar rutele, doar desktop
    python scripts/smoke_ui.py --vizibil  # cu browserul pe ecran, pentru depanare

CERINTE (o singura data, doar pe masina de dezvoltare — NU intra in requirements.txt)
    pip install playwright
    python -m playwright install chromium

Porneste singur aplicatia, pe un port liber si pe o COPIE a bazei de date
(PIF_DB_PATH), deci nu atinge `pif_dashboard.db`. Iese cu 0 daca totul e curat,
1 daca a gasit ceva.
"""

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

RADACINA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# FUSUL ORAR AL TESTELOR NU E UTC, CU BUNA STIINTA.
# Ion lucreaza in Romania (UTC+2/+3), iar containerele de test ruleaza pe UTC —
# unde ora locala si UTC coincid, deci orice greseala de conversie e INVIZIBILA.
# Asa a trecut neobservat un bug pe care il vedea la fiecare atingere: butoanele
# „Azi"/„Mâine" construiau data cu `new Date().toISOString()`, adica in UTC, iar
# miezul noptii local intr-un fus de la est de Greenwich cade in ziua precedenta.
# „Azi" scria IERI, la orice ora. Testele erau verzi.
FUS_TEST = 'Europe/Bucharest'

PIN_TEST = '000000'

RUTE = [
    ('/', 'Acasa'),
    ('/projects', 'Proiecte'),
    ('/tasks', 'Taskuri'),
    # Vederea personala e un query pe aceeasi ruta — fara intrarea explicita,
    # smoke-ul n-ar vizita-o niciodata.
    ('/tasks?sfera=personal', 'Taskuri personale'),
    ('/plan', 'Planificator'),
    ('/calendar', 'Calendar'),
    ('/departament', 'Departament'),
    ('/calculator', 'Calculator'),
]

ECRANE = [('desktop', 1280, 800), ('mobil', 390, 844)]

# Zgomot cunoscut, fara legatura cu codul aplicatiei. Tine lista SCURTA si
# comenteaza fiecare intrare — altfel testul devine decorativ.
IGNORATE = (
    'net::ERR_INTERNET_DISCONNECTED',   # fara retea; fonturile/CDN-ul pica, nu e vina noastra
    'net::ERR_ABORTED',                 # cereri taiate cand inchidem pagina la final
    # Windows ramane fara bufere de socket dupa sute de conexiuni scurte la rand
    # (54 de pagini x ~40 de assets). E o limita a masinii, nu ceva ce poate cauza
    # codul aplicatiei — o cerere nu pleaca deloc, nu primeste un raspuns gresit.
    'net::ERR_NO_BUFFER_SPACE',
    # Adaptorul de retea si-a schimbat configuratia in timpul rularii (Wi-Fi,
    # VPN, IP nou). Cererea nu pleaca deloc — nu poate fi cauzata de codul nostru.
    'net::ERR_NETWORK_CHANGED',
)


def out(s=''):
    sys.stdout.buffer.write((str(s) + '\n').encode('utf-8', 'replace'))
    sys.stdout.flush()


def port_liber():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def porneste_serverul(port, db_temp, cale_log):
    """Aplicatia Flask, pe baza de unica folosinta, fara HTTPS (suntem pe http local).

    Logul merge intr-un FISIER, nu intr-un pipe. Serverul de dezvoltare scrie o
    linie per cerere, iar o pagina trage ~40 de assets: cu stdout=PIPE si nimeni
    care sa citeasca, bufferul sistemului (64 KB) se umple dupa doua pagini si
    serverul se blocheaza in write() — arata identic cu o aplicatie moarta.
    """
    env = dict(os.environ)
    env.update({
        'PIF_DB_PATH': db_temp,
        'PIF_DASHBOARD_PIN': PIN_TEST,
        'SESSION_COOKIE_SECURE': 'false',
        # Zeci de pagini la rand depasesc pragul normal de 60/minut si am obtine
        # 429-uri peste tot — zgomot care ascunde erorile adevarate.
        'PIF_RATE_LIMIT': '100000',
        'PYTHONIOENCODING': 'utf-8',
    })
    cod = (
        'from app import app\n'
        'from database import init_db\n'
        'init_db()\n'
        'app.run(host="127.0.0.1", port=%d, debug=False, use_reloader=False, threaded=True)\n' % port
    )
    log = open(cale_log, 'wb')
    proc = subprocess.Popen(
        [sys.executable, '-c', cod],
        cwd=RADACINA, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    proc._log = log
    baza = 'http://127.0.0.1:%d' % port
    for _ in range(120):
        if proc.poll() is not None:
            log.close()
            out(open(cale_log, encoding='utf-8', errors='replace').read()[-3000:])
            raise SystemExit('Serverul a murit la pornire.')
        try:
            urllib.request.urlopen(baza + '/login', timeout=1).read()
            return proc, baza
        except urllib.error.HTTPError:
            return proc, baza          # raspunde, chiar daca nu cu 200
        except Exception:
            time.sleep(0.5)
    proc.terminate()
    raise SystemExit('Serverul nu a pornit in 60s.')


class Colector:
    """Aduna ce s-a stricat intr-o pagina. `pageerror` e cel care prinde
    ReferenceError-ul unei componente neimportate."""

    def __init__(self, page):
        self.erori = []
        page.on('pageerror', lambda e: self.erori.append('EXCEPTIE: %s' % str(e).split('\n')[0]))
        page.on('console', self._consola)
        page.on('requestfailed', self._cerere)

    def _consola(self, msg):
        if msg.type == 'error':
            self.erori.append('CONSOLA: %s' % msg.text.replace('\n', ' ')[:300])

    def _cerere(self, req):
        fail = (req.failure or '')
        self.erori.append('CERERE: %s %s' % (fail, req.url[:160]))

    def curate(self):
        return [e for e in self.erori if not any(z in e for z in IGNORATE)]


def deschide(context, url, latime, inalt):
    page = context.new_page()
    page.set_viewport_size({'width': latime, 'height': inalt})
    col = Colector(page)
    page.goto(url, wait_until='load', timeout=30000)
    # Randarea e asincrona: asteptam sa dispara scheletele. Daca raman, pagina a
    # ramas blocata la incarcare — exact simptomul bug-ului cu AlertCircle.
    try:
        page.wait_for_function(
            "() => document.querySelectorAll('[class*=\"skeleton\"]').length === 0",
            timeout=15000)
        blocata = False
    except Exception:
        blocata = True
    page.wait_for_timeout(350)
    return page, col, blocata


def verifica(context, baza, ruta, eticheta, ecran, taburi=False):
    nume, latime, inalt = ecran
    page, col, blocata = deschide(context, baza + '/#' + ruta, latime, inalt)
    probleme = []
    if blocata:
        probleme.append('BLOCATA: scheletele nu au disparut in 15s')

    if taburi:
        butoane = page.locator('.tabs button')
        for i in range(butoane.count()):
            try:
                butoane.nth(i).click(timeout=5000)
                page.wait_for_timeout(450)
            except Exception as e:
                probleme.append('TAB %d: %s' % (i, str(e).split('\n')[0]))

    # Pagina goala = pagina care nu s-a randat, chiar daca n-a aruncat nimic.
    try:
        text = page.inner_text('#main-content', timeout=3000)
    except Exception:
        text = page.inner_text('body')
    if len(text.strip()) < 40:
        probleme.append('GOALA: sub 40 de caractere in continut')

    probleme.extend(col.curate())
    page.close()

    stare = 'OK  ' if not probleme else 'PICA'
    out('  %s  %-9s %-28s %s' % (stare, nume, eticheta[:28], '' if not probleme else probleme[0]))
    for p in probleme[1:]:
        out('        %s' % p)
    return probleme


def verifica_aterizarea(context, baza):
    """Aterizarea implicita, adica ce vezi cand deschizi aplicatia FARA ruta in URL.

    Pe telefon trebuie sa fie taskurile personale (asa se deschide PWA-ul de pe
    ecranul principal, cu `start_url: "/"`), pe desktop trebuie sa ramana Acasa.
    Probele de rute de mai jos NU acopera cazul asta: ele navigheaza mereu la
    `/#<ruta>`, deci hash-ul e deja pus si redirectarea nu se declanseaza
    niciodata — exact drumul pe care intra Ion in fiecare dimineata.
    """
    probleme = []
    for nume, latime, inalt, asteptat in (
            ('mobil', 390, 844, '#/tasks?sfera=personal'),
            ('desktop', 1280, 800, ''),
    ):
        page = context.new_page()
        page.set_viewport_size({'width': latime, 'height': inalt})
        page.goto(baza + '/', wait_until='load', timeout=30000)
        page.wait_for_timeout(600)
        hash_final = page.evaluate('() => window.location.hash')
        ok = hash_final == asteptat
        if not ok:
            probleme.append('%s: hash "%s", asteptat "%s"' % (nume, hash_final, asteptat))
        # Pe telefon nu e destul sa nimeresti ruta: sfera trebuie sa fie personala.
        if ok and nume == 'mobil':
            try:
                page.wait_for_selector('button.seg.on', timeout=10000)
                activ = page.inner_text('button.seg.on').strip()
                if 'Personal' not in activ:
                    probleme.append('mobil: segmentul activ e „%s", nu „Personal"' % activ)
            except Exception as e:
                probleme.append('mobil: comutatorul de sfera nu s-a randat (%s)'
                                % str(e).split('\n')[0])
        page.close()
        out('  %s  %-9s aterizare implicita%s'
            % ('OK  ' if not probleme else 'PICA', nume,
               '' if not probleme else '  ' + probleme[-1]))
    return probleme


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rapid', action='store_true', help='doar rutele, doar desktop')
    ap.add_argument('--vizibil', action='store_true', help='cu browser pe ecran')
    ap.add_argument('--baza', help='alta baza sursa (implicit pif_dashboard.db din proiect)')
    arg = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise SystemExit(
            'Lipseste playwright. Ruleaza:\n'
            '  pip install playwright\n'
            '  python -m playwright install chromium')

    db_sursa = arg.baza or os.path.join(RADACINA, 'pif_dashboard.db')
    if not os.path.isfile(db_sursa):
        raise SystemExit('Nu exista pif_dashboard.db local. Adu una: scripts/sync_db_from_server.sh')

    tmp = tempfile.mkdtemp(prefix='pif-smoke-')
    db_temp = os.path.join(tmp, 'smoke.db')
    shutil.copy2(db_sursa, db_temp)

    cale_log = os.path.join(tmp, 'server.log')
    port = port_liber()
    proc, baza = porneste_serverul(port, db_temp, cale_log)
    out('Server pe %s (baza: copie de unica folosinta)' % baza)

    esecuri = 0
    try:
        with sync_playwright() as pw:
            # PIF_CHROMIUM: pentru masinile unde Chromium e deja instalat in alta
            # parte si `playwright install` n-are voie sa descarce (containere,
            # sesiuni la distanta). Gol = comportamentul dintotdeauna.
            cale_chromium = os.environ.get('PIF_CHROMIUM') or None
            browser = pw.chromium.launch(headless=not arg.vizibil,
                                         executable_path=cale_chromium)
            # service_workers='block' e blocarea nativa a lui Playwright. NU stubui
            # navigator.serviceWorker cu undefined: aplicatia il apeleaza direct si
            # ai obtine o „eroare" pe care ai fabricat-o tu, in fiecare pagina.
            context = browser.new_context(
                viewport={'width': 1280, 'height': 800}, service_workers='block',
                timezone_id=FUS_TEST)

            page = context.new_page()
            page.goto(baza + '/login', wait_until='load')
            page.fill('#pin', PIN_TEST)
            page.click('button[type="submit"]')
            page.wait_for_url(lambda u: not u.endswith('/login'), timeout=15000)
            out('Autentificat.')

            proiecte = context.request.get(baza + '/api/proiecte').json()
            if isinstance(proiecte, dict):
                proiecte = proiecte.get('proiecte') or proiecte.get('data') or []
            page.close()
            out('%d proiecte de verificat.\n' % len(proiecte))

            out('--- aterizarea implicita ---')
            if verifica_aterizarea(context, baza):
                esecuri += 1
            out()

            ecrane = ECRANE[:1] if arg.rapid else ECRANE
            for ecran in ecrane:
                out('--- %s ---' % ecran[0])
                for ruta, eticheta in RUTE:
                    if verifica(context, baza, ruta, eticheta, ecran):
                        esecuri += 1
                if not arg.rapid:
                    for p in proiecte:
                        et = '%s [%s]' % (p.get('nume', '?'), p.get('tip', '?'))
                        if verifica(context, baza, '/projects/' + p['id'], et, ecran, taburi=True):
                            esecuri += 1
                out()
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        try:
            proc._log.close()
        except Exception:
            pass
        if esecuri:
            # Erorile 500 din server explica de multe ori ce a vazut browserul.
            jurnal = open(cale_log, encoding='utf-8', errors='replace').read()
            urme = [l for l in jurnal.splitlines()
                    if 'Traceback' in l or 'ERROR' in l or ' 500 -' in l]
            if urme:
                out('\n--- din logul serverului ---')
                for l in urme[-15:]:
                    out('  ' + l)
        shutil.rmtree(tmp, ignore_errors=True)

    if esecuri:
        out('PICAT: %d pagini cu probleme.' % esecuri)
        return 1
    out('OK — toate paginile s-au randat curat.')
    return 0


if __name__ == '__main__':
    sys.exit(main())

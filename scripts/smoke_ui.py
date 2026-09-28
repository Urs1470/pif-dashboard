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
repeta totul pe latime de telefon (Calendarul isi comuta panoul zilei intr-o
foaie sub 768px — markup pe care desktopul nu-l randeaza niciodata).

RULARE
    python scripts/smoke_ui.py             # tot: rute + TOATE proiectele, desktop + telefon
    python scripts/smoke_ui.py --esantion  # rute + un proiect din fiecare fel (poarta)
    python scripts/smoke_ui.py --rapid     # doar rutele, doar desktop
    python scripts/smoke_ui.py --vizibil   # cu browserul pe ecran, pentru depanare

ESANTIONUL (poarta, din 2026-09-28). Turul complet deschide aceeasi pagina de proiect
de 42 de ori (21 de proiecte x 2 latimi) si dura 127 s — din care ~77 s erau pauze
fixe. Ce cauta el sunt RAMURILE dupa date (`{#if project.tip === 'Service'}`), nu
proiectele in sine: deci poarta ia cel mai nou proiect din fiecare combinatie
tip x status x „are o perioada viitoare", iar turul complet ramane pentru
`verifica.py --complet`.

CERINTE (o singura data, doar pe masina de dezvoltare — NU intra in requirements.txt)
    pip install playwright
    python -m playwright install chromium

Porneste singur aplicatia (`banc.Aplicatia`), pe un port liber si pe o COPIE a bazei,
deci nu atinge `pif_dashboard.db`. Iesire: 0 curat, 1 abatere, 2 instrumentul.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banc  # noqa: E402
from banc import out  # noqa: E402

RUTE = [
    ('/', 'Acasa'),
    ('/projects', 'Proiecte'),
    ('/tasks', 'Taskuri'),
    # Vederea personala e un query pe aceeasi ruta — fara intrarea explicita,
    # smoke-ul n-ar vizita-o niciodata.
    ('/tasks?sfera=personal', 'Taskuri personale'),
    ('/calendar', 'Calendar'),
    ('/departament', 'Departament'),
    ('/calculator', 'Calculator'),
]

# Telefonul e un context de TELEFON (atingere, `is_mobile`), nu un desktop ingustat:
# pana pe 2026-09-28 „mobil" aici era 390x844 fara atingere, iar in celelalte audituri
# un telefon adevarat — deci aceeasi pagina se putea purta altfel in doua probe.
ECRANE = ['desktop', 'mobil']

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

    def taiate(self):
        """Ce s-a filtrat prin `IGNORATE`, ca sa se poata SPUNE cand conteaza.

        Zgomotul de retea nu e vina codului — de aceea e ignorat — dar nu e nici
        fara urmari: daca cererea care nu pleaca e chiar CHUNKUL rutei, pagina
        nu se randeaza deloc. Atunci raportul ramanea cu „GOALA" si fara cauza,
        fiindca singurul semn fusese taiat. Vezi `verifica`."""
        return [e for e in self.erori if any(z in e for z in IGNORATE)]


def deschide(context, url, latime=None, inalt=None):
    page = banc.pagina(context)
    if latime:
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
    # In locul celor 350 ms fixi: pana se intoarce ultima cerere si se opreste ultima
    # animatie — o eroare venita dintr-un fetch tarziu apuca sa ajunga in colector.
    if not blocata:
        banc.asteapta_linistea(page)
    return page, col, blocata


def _motiv(linie):
    """Doar codul de retea din linia colectata — `net::ERR_...`, fara URL."""
    for z in IGNORATE:
        if z in linie:
            return z
    return linie[:60]


def _incearca(context, baza, ruta, taburi):
    """O singura vizita: intoarce `(probleme, zgomot_de_retea_filtrat)`.

    Nu scrie nimic in raport — decizia e a lui `verifica`, fiindca doar el stie
    daca mai are voie sa reia."""
    page, col, blocata = deschide(context, baza + '/#' + ruta)
    probleme = []
    if blocata:
        probleme.append('BLOCATA: scheletele nu au disparut in 15s')

    if taburi:
        butoane = page.locator('.tabs button')
        for i in range(butoane.count()):
            try:
                butoane.nth(i).click(timeout=5000)
                # In locul celor 450 ms fixi dupa fiecare tab (42 de vizite x 3 taburi
                # = ~57 s din turul complet): pana s-a incarcat si s-a asezat tabul.
                banc.asteapta_linistea(page)
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
    taiate = col.taiate()
    page.close()
    return probleme, taiate


def rand(ok, ecran, text, detaliu=''):
    out('  %-8s %-8s %-30s %s' % ('OK' if ok else 'PICA', ecran, text[:30], detaliu))


def verifica(context, baza, ruta, eticheta, ecran, taburi=False):
    probleme, taiate = _incearca(context, baza, ruta, taburi)

    # O PAGINA GOALA DIN CAUZA RETELEI NU E O PAGINA STRICATA — DAR NICI TACERE.
    #
    # Pe Windows, dupa sute de conexiuni scurte la rand, socketurile raman fara
    # bufere: `net::ERR_NO_BUFFER_SPACE`, deja in `IGNORATE` fiindca „o cerere nu
    # pleaca deloc". Adevarat despre CAUZA, dar nu si despre urmari: cand cererea
    # care nu pleaca e chunkul lazy al rutei, nu se monteaza nimic — zero schelete
    # (deci asteptarea trece), `#main-content` gol, si niciun mesaj, fiindca
    # singurul semn tocmai a fost filtrat. Ramanea „GOALA", pe pagina de dupa cea
    # mai grea (Calculator, 881 kB), la intamplare.
    # Masurat pe 2026-08-26, reluand secventa reala de 8 ori: o singura cerere
    # cazuta (`EditorLung`), si continutul paginii a scazut de la 270 la 94 de
    # caractere. Cu chunkul rutei in loc, scade la zero si trece pragul de 40.
    # Deci: se reia O DATA, si daca reluarea e curata se scrie de ce.
    gol_si_retea = taiate and any(p.startswith(('GOALA', 'BLOCATA')) for p in probleme)
    if gol_si_retea:
        probleme, _ = _incearca(context, baza, ruta, taburi)
        if not probleme:
            rand(True, ecran, eticheta, '(reluat — %s)' % _motiv(taiate[0]))
            return probleme
        probleme = probleme + ['CAUZA PROBABILA: %s' % taiate[0][:140]]

    rand(not probleme, ecran, eticheta, '' if not probleme else probleme[0])
    for p in probleme[1:]:
        out('                    %s' % p)
    return probleme


def verifica_aterizarea(contexte, baza):
    """Aterizarea implicita, adica ce vezi cand deschizi aplicatia FARA ruta in URL.

    Pe telefon trebuie sa fie taskurile personale (asa se deschide PWA-ul de pe
    ecranul principal, cu `start_url: "/"`), pe desktop trebuie sa ramana Acasa.
    Probele de rute de mai jos NU acopera cazul asta: ele navigheaza mereu la
    `/#<ruta>`, deci hash-ul e deja pus si redirectarea nu se declanseaza
    niciodata — exact drumul pe care intra Ion in fiecare dimineata.

    Fiecare ecran isi numara problemele LUI. Pana pe 2026-09-28 lista era comuna,
    deci o problema pe telefon aparea si pe randul desktopului, ca PICA.
    """
    total = 0
    for ecran, asteptat in (('mobil', '#/tasks?sfera=personal'), ('desktop', '')):
        probleme = []
        page = contexte[ecran].new_page()
        page.goto(baza + '/', wait_until='load', timeout=30000)
        try:
            page.wait_for_function('(h) => location.hash === h', arg=asteptat, timeout=5000)
        except Exception:
            pass
        hash_final = page.evaluate('() => window.location.hash')
        if hash_final != asteptat:
            probleme.append('hash "%s", asteptat "%s"' % (hash_final, asteptat))
        # Pe telefon nu e destul sa nimeresti ruta: sfera trebuie sa fie personala.
        elif ecran == 'mobil':
            try:
                page.wait_for_selector('button.seg.on', timeout=10000)
                activ = page.inner_text('button.seg.on').strip()
                if 'Personal' not in activ:
                    probleme.append('segmentul activ e „%s", nu „Personal"' % activ)
            except Exception as e:
                probleme.append('comutatorul de sfera nu s-a randat (%s)' % str(e).split('\n')[0])
        page.close()
        rand(not probleme, ecran, 'aterizare implicita', '; '.join(probleme))
        total += 1 if probleme else 0
    return total


def esantion(proiecte):
    """Cel mai nou proiect din fiecare combinatie tip x status x „are o perioada
    viitoare" — ramurile dupa date pe care turul complet le atingea de 21 de ori."""
    alese = {}
    for p in proiecte:                          # API-ul le da pe cele noi primele
        alese.setdefault((p.get('tip'), p.get('status'), bool(p.get('urmatoarea'))), p)
    return list(alese.values())


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--rapid', action='store_true', help='doar rutele, doar desktop')
    g.add_argument('--esantion', action='store_true',
                   help='un proiect din fiecare tip x status (poarta), nu toate')
    banc.argumente(ap)
    arg = ap.parse_args()
    sync_playwright = banc.playwright()

    esecuri = 0
    with banc.Aplicatia(sursa=arg.baza, prefix='pif-smoke-') as app:
        out('Server pe %s (baza: copie de unica folosinta)' % app.baza)
        with sync_playwright() as pw:
            br = banc.browserul(pw, arg.vizibil)
            contexte = {'desktop': banc.context(br, 'desktop'), 'mobil': banc.context(br, 'telefon')}
            for ctx in contexte.values():
                banc.autentifica(ctx, app.baza, inchide=True)
            proiecte = contexte['desktop'].request.get(app.baza + '/api/proiecte').json()
            de_vazut = [] if arg.rapid else esantion(proiecte) if arg.esantion else proiecte
            out('%d proiecte in baza, %d de verificat%s.\n'
                % (len(proiecte), len(de_vazut), ' (esantion)' if arg.esantion else ''))

            out('--- aterizarea implicita ---')
            esecuri += verifica_aterizarea(contexte, app.baza)
            out()

            for ecran in (['desktop'] if arg.rapid else ECRANE):
                out('--- %s ---' % ecran)
                for ruta, eticheta in RUTE:
                    if verifica(contexte[ecran], app.baza, ruta, eticheta, ecran):
                        esecuri += 1
                for p in de_vazut:
                    et = '%s [%s]' % (p.get('nume', '?'), p.get('tip', '?'))
                    if verifica(contexte[ecran], app.baza, '/projects/' + p['id'], et, ecran, taburi=True):
                        esecuri += 1
                out()
            br.close()
        if esecuri:
            # Erorile 500 din server explica de multe ori ce a vazut browserul.
            urme = app.urme()
            if urme:
                out('--- din logul serverului ---')
                for l in urme:
                    out('  ' + l)
    return banc.incheie(esecuri)


if __name__ == '__main__':
    sys.exit(banc.ruleaza(main))

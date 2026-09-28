#!/usr/bin/env python3
"""Cat de VIU raspunde ecranul la deget. Nu ce se vede, ci cand si cum de neted.

Celelalte probe intreaba „arata bine?" (`audit_design`), „incape?" (`audit_mobil`),
„se randeaza?" (`smoke_ui`), „gestul face ce trebuie?" (`audit_foaie`). Niciuna nu
intreaba lucrul pe care mana il simte primul: CAT DUREAZA pana se intampla ceva, si
daca ce se intampla curge sau se poticneste.

Patru masuratori, fiecare cu un prag scris in aplicatie sau in fiziologie:

  A. RASPUNSUL LA ATINGERE. Din clipa in care degetul atinge, pana la primul cadru
     in care s-a schimbat ceva pe ecran. Pragul e cel scris in `tokens.css` la
     `--dur-press`: „sub ~100ms legatura cauza-efect se citeste ca instantanee".
     Peste 100ms, apesi a doua oara — adica actiunea de doua ori.

  B. PROFILUL MISCARII. O animatie corecta nu e doar „ajunge unde trebuie". Se
     verifica patru lucruri, si fiecare are un mod de esec pe care aplicatia
     chiar l-a avut:
       - PORNESTE la timp (sub 100ms de la declansare) — altfel pare blocata;
       - e MONOTONA — un obiect care se inchide n-are voie sa se intoarca; doua
         miscari pe aceeasi axa, in sensuri opuse, se citesc exact ca lag
         (vezi nota din `Modal.svelte` despre `trasY` la iesire);
       - n-are SALTURI — intre doua cadre vecine nu se face mai mult de 45% din
         drum; un salt inseamna ca geometria s-a schimbat sub animatie;
       - SE TERMINA — ajunge la capat, nu se stinge la jumatate.

  C. CADRE PIERDUTE. Cate cadre au durat peste 32ms (adica doua rate la 60Hz) in
     timpul interactiunii. Un cadru pierdut la mijlocul unei miscari e singurul
     defect de fluenta pe care ochiul il prinde fara sa stie ce a vazut.

  D. GESTUL URMARESTE DEGETUL. Cat ramane obiectul in urma degetului in timpul
     unei trageri. Peste cativa px, gestul nu mai e „obiectul e in mana mea", e
     „obiectul raspunde la mana mea" — si aia e alta senzatie, mai proasta.

Atingere ADEVARATA peste tot (`Input.dispatchTouchEvent`): mouse-ul lui Playwright
emite `pointerType: 'mouse'`, iar jumatate din gesturile aplicatiei ies exact pe
conditia asta — vezi nota din `audit_foaie.py`.
"""

import os
import sqlite3
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banc  # noqa: E402
from banc import out, apuca, misca, ridica  # noqa: E402

R = banc.Raport()
bifa = R.bifa
nota = R.nota


def aseaza(page):
    """Inainte de o masuratoare, pagina trebuie sa stea: nicio cerere, nicio
    animatie, niciun arc. O pauza fixa lasa uneori un fetch sau o tranzitie sa curga
    PESTE fereastra masurata — si atunci aplicatia e acuzata de munca altcuiva."""
    banc.asteapta_linistea(page)


# Pragul de raspuns, din `tokens.css` (`--dur-press`, nota lui).
PRAG_RASPUNS = 100
# Un cadru „pierdut". 40ms, nu 32: la 60Hz un cadru dublu e fix 33,3ms, si el
# apare si pe o masina sanatoasa la orice recalcul de stil mai lat — inclusiv la
# schimbarea de tema, care CHIAR trebuie sa repicteze tot. Sub 40 e jitter; peste,
# s-a pierdut cel putin un cadru intreg in plus, si ochiul chiar prinde asta.
CADRU_LUNG = 40
# Cat poate ramane obiectul in urma degetului, in px.
PRAG_URMARIRE = 12

def seamana(cale):
    """Destule randuri cat sa existe ce derula si ce atinge. Schema o scrie `banc`."""
    db = sqlite3.connect(cale)
    pid = str(uuid.uuid4())
    db.execute("INSERT INTO proiecte (id, nume, client, tip, status) VALUES (?,?,?,?,?)",
               (pid, 'Retrofit linie ambalare', 'Fabrica 2', 'retrofit', 'pregatire'))
    titluri = ['Verifică parametrii Danfoss FC302', 'Comandă cablu ecranat 4×2,5',
               'Trimite raport PIF — hala 2', 'Programează recepția cu beneficiarul',
               'Actualizează schema de forță', 'Test la sarcină — pompa P-102',
               'Instruire operatori', 'Măsoară izolația motorului',
               'Verifică strângerile în tablou', 'Backup parametri drive']
    for t in titluri:
        db.execute("INSERT INTO tasks (id, proiect_id, titlu, status, data_scadenta)"
                   " VALUES (?,?,?,?,?)", (str(uuid.uuid4()), pid, t, 'to_do', '2026-08-16'))
        db.execute("INSERT INTO global_tasks (id, titlu, status, categorie, data_scadenta)"
                   " VALUES (?,?,?,?,?)", (str(uuid.uuid4()), t, 'to_do', 'General', '2026-08-16'))
    for i, t in enumerate(['Revizuie oferta Siemens', 'Curăță panoul de comandă',
                           'Comandă senzori PT100', 'Scrie procedura de pornire',
                           'Verifică stocul de siguranțe', 'Programează service anual']):
        db.execute("INSERT INTO global_tasks (id, titlu, status, categorie, data_scadenta)"
                   " VALUES (?,?,?,?,?)", (str(uuid.uuid4()), t, 'to_do', 'General',
                                           None if i % 2 else '2026-09-%02d' % (i + 3)))
    db.commit()
    db.close()


# ---------------------------------------------------------------- inregistrarea
# Un magnetofon de cadre, in pagina. Porneste pe `rAF` si retine, per cadru:
# momentul, si valoarea sondei (o functie care intoarce un numar sau null).
# Din el ies toate cele patru masuratori: intarzierea (primul cadru in care
# sonda s-a schimbat), profilul (sirul), cadrele pierdute (diferentele de timp).
INREGISTRARE = """([sondaSir, durata]) => {
  // UN SINGUR argument, destructurat. `page.evaluate(fn, arg)` paseaza exact
  // unul: scris ca `(sondaSir, durata)`, al doilea ramane `undefined`, iar
  // `t - t0 < undefined` e fals — deci se inregistra UN cadru si toate probele
  // raportau „niciun raspuns". Trei defecte inventate din doua paranteze.
  const sonda = new Function('return (' + sondaSir + ')')();
  window.__cadre = [];
  const t0 = performance.now();
  window.__t0 = t0;
  // MOMENTUL DECLANSARII, luat din pagina, nu din scriptul de proba.
  // Masurat de la pornirea inregistrarii, orice raspuns parea intarziat cu exact
  // cat asteptasem inainte sa apas (~60ms + drumul prin CDP) — adica proba isi
  // masura propria latenta si o punea in cartea aplicatiei. Ascultatorul de aici
  // vede apasarea in acelasi ceas cu cadrele.
  window.__declansat = null;
  const marcheaza = () => { if (window.__declansat === null) window.__declansat = performance.now() - t0; };
  // Fara `once`: ascultatorul ramane, iar „primul eveniment" se decide prin
  // `__declansat === null`. Cu `once`, un eveniment ratacit dinainte de actiune
  // consuma ascultatorul, marcajul ramanea de la el, si pornirea iesea NEGATIVA.
  addEventListener('mousedown', marcheaza, { capture: true });
  addEventListener('touchstart', marcheaza, { capture: true });
  addEventListener('click', marcheaza, { capture: true });
  // Si tastatura: inchiderea foii se declanseaza cu Escape (butonul „inapoi" de
  // pe Android ajunge tot asa). Fara el, masuratoarea pornea de la inregistrare
  // si raporta ~60ms in plus — propria mea asteptare, pusa in cartea aplicatiei.
  addEventListener('keydown', marcheaza, { capture: true });
  const pas = () => {
    const t = performance.now();
    let v = null;
    try { v = sonda(); } catch (e) { v = null; }
    window.__cadre.push([Math.round((t - t0) * 10) / 10, v]);
    if (t - t0 < durata) requestAnimationFrame(pas);
  };
  requestAnimationFrame(pas);
}"""


def porneste_inregistrarea(page, sonda_js, durata=1200):
    page.evaluate(INREGISTRARE, [sonda_js, durata])


def ia_cadrele(page, durata=1200):
    page.wait_for_timeout(durata + 120)
    return page.evaluate('() => window.__cadre || []')


def armeaza(page):
    """Se cheama IMEDIAT inainte de actiunea masurata: sterge orice marcaj vechi,
    ca „primul eveniment" sa fie chiar al ei."""
    page.evaluate('() => { window.__declansat = null }')


def momentul_apasarii(page):
    """Cand a inceput interactiunea, in ceasul inregistrarii. 0 daca n-a fost
    prinsa — atunci masuratoarea ramane de la pornire, si o spune."""
    v = page.evaluate('() => window.__declansat')
    return v if isinstance(v, (int, float)) else 0.0


def analizeaza(cadre, nume, drum_minim=8, apasat=0.0):
    """Din sirul de cadre scoate cele patru numere. Intoarce un dict."""
    puncte = [(t, v) for t, v in cadre if isinstance(v, (int, float))]
    r = {'nume': nume, 'cadre': len(cadre), 'puncte': len(puncte)}
    if len(puncte) < 3:
        r['gol'] = True
        return r

    # CADRE PIERDUTE — dar numai cele care se VAD.
    #
    # Un cadru lung inainte ca obiectul sa se miste e cost de CONSTRUCTIE: se
    # creeaza DOM-ul foii, se randeaza lista, se muta focusul. Ochiul nu are ce
    # pierde acolo, fiindca inca nu se misca nimic — se pierde doar inceputul
    # animatiei, iar pe ala il masoara separat `pornire`.
    # Un cadru lung IN TIMPUL miscarii e altceva: obiectul se opreste in aer si
    # apoi sare. Aia e singura poticneala pe care mana o simte.
    # Masurat pe foaia de adaugare: 44ms la montare, 0 in timpul miscarii —
    # doua lucruri diferite, si numai unul e defect.
    puncte_t = [t for t, v in cadre if isinstance(v, (int, float))]
    t_start_miscare = puncte_t[0] if puncte_t else 0
    sarite = 0
    maxim = 0
    sarite_construire = 0
    for i in range(1, len(cadre)):
        d = cadre[i][0] - cadre[i - 1][0]
        if d > CADRU_LUNG:
            if cadre[i][0] <= t_start_miscare:
                sarite_construire += 1
            else:
                sarite += 1
                maxim = max(maxim, d)
    r['cadre_sarite'] = sarite
    r['cadru_max'] = round(maxim, 1)
    r['sarite_construire'] = sarite_construire

    start = puncte[0][1]
    final = puncte[-1][1]
    drum = abs(final - start)
    r['drum'] = round(drum, 1)
    if drum < drum_minim:
        r['nemiscat'] = True
        return r

    # A. cand a inceput sa se miste: primul cadru care a facut >3% din drum
    r['pornire'] = None
    for t, v in puncte:
        if abs(v - start) > drum * 0.03:
            # Marcajul apasarii se ia din pagina; daca iese dupa primul cadru
            # miscat (ceasuri diferite, sau evenimentul prins e altul decat cel
            # care a declansat), masuratoarea nu e de incredere — se raporteaza
            # de la pornirea inregistrarii, si nota o spune.
            r['pornire'] = round(t - apasat, 1)
            if r['pornire'] < 0:
                r['pornire'] = round(t, 1)
                r['marcaj_dubios'] = True
            break

    # B. monotonie: cat s-a mers in sens INVERS fata de sensul general
    sens = 1 if final > start else -1
    invers = 0.0
    for i in range(1, len(puncte)):
        d = (puncte[i][1] - puncte[i - 1][1]) * sens
        if d < 0:
            invers += -d
    r['invers'] = round(invers, 1)
    r['invers_pct'] = round(invers / drum * 100, 1)

    # C. cel mai mare salt intre doua cadre vecine, ca procent din drum
    salt = 0.0
    for i in range(1, len(puncte)):
        salt = max(salt, abs(puncte[i][1] - puncte[i - 1][1]))
    r['salt_pct'] = round(salt / drum * 100, 1)
    return r


def raporteaza(r, prag_pornire=PRAG_RASPUNS, prag_invers=6.0, prag_salt=45.0):
    n = r['nume']
    # UN OBIECT CARE N-A APARUT SAU NU S-A MISCAT E O ABATERE, nu o nota (2026-09-28):
    # pana atunci o foaie care nu se deschidea deloc trecea — „nimic de masurat".
    if r.get('gol'):
        bifa(False, '%s: obiectul exista' % n, 'sonda n-a intors numere — nu s-a deschis/randat')
        return
    if r.get('nemiscat'):
        bifa(False, '%s: se misca' % n, 'drum %s px — n-a plecat din loc' % r.get('drum'))
        return
    # O MASURATOARE IN CARE NU AM INCREDERE NU ARE VOIE SA ACUZE.
    # Cand marcajul apasarii iese dupa primul cadru miscat, singurul lucru pe care
    # il stiu sigur e ca proba a masurat gresit — nu ca aplicatia raspunde greu.
    # Se raporteaza ca NOTA, nu ca esec: altfel harnessul isi trece propriile
    # scapari in cartea codului, si atunci fiecare rulare cere iar investigatie.
    # (Masurat curat, aceleasi drumuri pornesc la 34-38ms.)
    if r.get('marcaj_dubios'):
        nota('%s: momentul declansarii n-a fost prins curat — nu se poate judeca pornirea '
             '(cel mai devreme cadru miscat: %sms de la pornirea probei)' % (n, r['pornire']))
    else:
        bifa(r['pornire'] is not None and r['pornire'] <= prag_pornire,
             '%s: porneste sub %dms' % (n, prag_pornire),
             'a pornit la %sms' % r['pornire'], 'la %sms' % r['pornire'])
    bifa(r['invers_pct'] <= prag_invers,
         '%s: merge intr-un singur sens' % n,
         's-a intors %s%% din drum (%s px)' % (r['invers_pct'], r['invers']),
         '%s%% inapoi' % r['invers_pct'])
    bifa(r['salt_pct'] <= prag_salt,
         '%s: fara salturi intre cadre' % n,
         'un cadru a facut %s%% din drum' % r['salt_pct'],
         'max %s%%/cadru' % r['salt_pct'])
    if r.get('sarite_construire'):
        nota('%s: %d cadru(e) lung(i) INAINTE de miscare — cost de construire, nu poticneala'
             % (n, r['sarite_construire']))
    bifa(r['cadre_sarite'] == 0,
         '%s: niciun cadru pierdut in timpul miscarii' % n,
         '%d cadre peste %dms (cel mai lung %sms)' % (r['cadre_sarite'], CADRU_LUNG, r['cadru_max']),
         'cadru max %sms' % r['cadru_max'])


def main():
    sync_playwright = banc.playwright()
    with banc.Aplicatia(noua=True, seamana=seamana, prefix='pif-react-') as app:
        baza = app.baza
        with sync_playwright() as p:
            b = banc.browserul(p)
            ctx = banc.context(b, 'telefon')
            page = banc.autentifica(ctx, baza)
            cdp = banc.cdp(page)
            erori = []
            page.on('pageerror', lambda e: erori.append(str(e).split('\n')[0]))
            page.goto(baza + '/#/tasks', wait_until='load')
            aseaza(page)

            # ============ A. RASPUNSUL LA ATINGERE ============
            out('\n--- A. raspunsul la atingere ---')
            # CE se masoara: lantul REAL de sub deget, nu un selector ghicit.
            # Prima varianta masura `.gl-fata` (invelisul randului) si raporta „nu
            # raspunde nimic" — cand de fapt raspunsul era pe `BUTTON.tmain`, doi
            # copii mai jos. Elementul care poarta `:active` nu e cel pe care il
            # numesti, e cel pe care browserul il nimereste; deci se ia de la
            # `elementFromPoint` in sus, patru trepte, si se intreaba daca S-A
            # SCHIMBAT CEVA VIZIBIL pe vreuna din ele.
            LANT = """([x, y]) => {
              const lant = []; let e = document.elementFromPoint(x, y);
              for (let i = 0; i < 4 && e; i++) { lant.push(e); e = e.parentElement; }
              window.__lant = lant;
              return lant.map(el => el.tagName + '.' + [...el.classList].slice(0, 2).join('.'));
            }"""
            # Semnatura: scalare + opacitate + fond, intr-un singur numar. Orice
            # raspuns la apasare din aplicatie trece prin una din cele trei.
            SEMNATURA = """() => {
              const l = window.__lant || []; let s = 0;
              for (const e of l) { const c = getComputedStyle(e);
                const m = new DOMMatrixReadOnly(c.transform === 'none' ? '' : c.transform);
                const bg = (c.backgroundColor.match(/[\\d.]+/g) || []).reduce((a, b) => a + (+b), 0);
                s += Math.abs(1 - m.a) * 1000 + Math.abs(1 - parseFloat(c.opacity)) * 1000 + bg; }
              return Math.round(s * 10) / 10;
            }"""

            tinte = [
                ('rand de task', '.trow-wrap .gl-fata, .trow'),
                ('buton de actiune (dock)', '.dock-fab'),
                ('slot de dock', '.dock-item'),
            ]
            # Capetele de grupa NU sunt in lista: sunt etichete lipite sus, nu
            # controale. O proba care le cere raspuns la apasare ar cere unei
            # suprafete sa promita un gest pe care nu-l are — exact greseala pe
            # care aplicatia si-o reproseaza la manerul-decor.
            for nume, sel in tinte:
                el = page.query_selector(sel)
                if el is None:
                    bifa(False, '%s: exista' % nume, 'lipseste `%s`' % sel)
                    continue
                box = el.bounding_box()
                if not box:
                    bifa(False, '%s: are geometrie' % nume, 'nu e randat')
                    continue
                x, y = box['x'] + box['width'] / 2, box['y'] + box['height'] / 2
                lant = page.evaluate(LANT, [x, y])
                porneste_inregistrarea(page, SEMNATURA, 420)
                page.wait_for_timeout(60)
                # APASARE DE MOUSE, nu atingere, si NUMAI aici.
                # Ce se masoara in sectiunea asta e raspunsul CSS (`:active`), nu
                # logica unui gest — iar `:active` NU se aplica la atingerile
                # sintetice prin `Input.dispatchTouchEvent`: verificat, regula
                # exista pe element si `el.matches(':active')` ramane `false` cat
                # tine atingerea. Cu deget sintetic proba raporta „nu raspunde
                # nimic" pentru trei suprafete care raspund perfect.
                # Media queries nu se schimba (contextul ramane telefon), deci
                # regulile din `@media (hover: none) and (pointer: coarse)` sunt
                # in continuare cele masurate.
                armeaza(page)
                page.mouse.move(x, y)
                page.mouse.down()
                page.wait_for_timeout(300)
                page.mouse.up()
                cadre = ia_cadrele(page, 420)
                apasat = momentul_apasarii(page)
                pct = [(t, v) for t, v in cadre if isinstance(v, (int, float))]
                baza_v = pct[0][1] if pct else 0
                brut = next((t for t, v in pct if abs(v - baza_v) > 0.5), None)
                cand = None if brut is None else round(brut - apasat, 1)
                bifa(cand is not None and cand <= PRAG_RASPUNS,
                     '%s: raspunde sub %dms' % (nume, PRAG_RASPUNS),
                     'nimic vizibil in 420ms (lant: %s)' % ' < '.join(lant),
                     'la %sms' % cand)
                # O atingere e si o APASARE: randul deschide foaia, butonul
                # plutitor deschide foaia de adaugare, slotul de dock navigheaza.
                # Fara curatenia asta, proba urmatoare masoara alt ecran decat
                # crede — si a doua oara nici nu mai ajunge la tinta, fiindca
                # voalul o acopera.
                page.keyboard.press('Escape')
                aseaza(page)
                if not page.url.endswith('#/tasks'):
                    page.goto(baza + '/#/tasks', wait_until='load')
                aseaza(page)

            # ============ B+C. PROFILUL MISCARII ============
            out('\n--- B. profilul miscarii (foaia taskului) ---')
            SONDA_FOAIE = ("""() => { const m = document.querySelector('.modal.sheet');
              return m ? Math.round(m.getBoundingClientRect().top * 10) / 10 : null; }""")

            rand = page.query_selector('.trow-wrap .gl-fata') or page.query_selector('.trow')
            if rand is None:
                bifa(False, 'lista are un rand de task pentru profilul foii', 'niciun rand')
            else:
                porneste_inregistrarea(page, SONDA_FOAIE, 900)
                page.wait_for_timeout(60)
                armeaza(page)
                rand.click()
                c = ia_cadrele(page, 900)
                raporteaza(analizeaza(c, 'deschiderea foii', apasat=momentul_apasarii(page)))

                aseaza(page)
                porneste_inregistrarea(page, SONDA_FOAIE, 900)
                page.wait_for_timeout(60)
                armeaza(page)
                page.keyboard.press('Escape')
                c = ia_cadrele(page, 900)
                raporteaza(analizeaza(c, 'inchiderea foii', apasat=momentul_apasarii(page)))
                aseaza(page)

            # Schimbarea de tab NU se masoara aici: miscarea ei e a unui
            # pseudo-element (`::view-transition-*`), pe care `getComputedStyle`
            # nu-l vede. `audit_navigare.py` o masoara direct, pe pastila
            # dockului, si o face mai bine. Doua probe pentru acelasi lucru, una
            # oarba, e mai rau decat una singura.

            # ============ B2. FOAIA DE ADAUGARE + TRECEREA DE TEMA ============
            out('\n--- B. foaia de adaugare si trecerea de tema ---')
            page.goto(baza + '/#/tasks', wait_until='load')
            aseaza(page)
            fab = page.query_selector('.dock-fab')
            if fab is None:
                bifa(False, 'exista butonul de adaugare din dock', 'lipseste .dock-fab')
            else:
                porneste_inregistrarea(page, SONDA_FOAIE, 1000)
                page.wait_for_timeout(60)
                armeaza(page)
                fab.click()
                c = ia_cadrele(page, 1000)
                raporteaza(analizeaza(c, 'foaia de adaugare', apasat=momentul_apasarii(page)))
                page.keyboard.press('Escape')
                aseaza(page)

            # TRECEREA DE TEMA, pe drumul REAL: butonul din antet -> foaia de
            # tema -> alegerea unui mod. Nu simulata dintr-un `evaluate`, fiindca
            # o simulare masoara ce cred eu ca face codul, nu ce face.
            # Aici s-a prins prima varianta a tranzitiei (tranzitie de culoare pe
            # tot arborele): cinci cadre pierdute, unul de 252ms.
            SONDA_CADRU = ("""() => { const s = getComputedStyle(document.body);
              const n = (s.backgroundColor.match(/[\\d.]+/g) || []).reduce((a, b) => a + (+b), 0);
              return Math.round(n * 10) / 10; }""")
            btnTema = page.query_selector('.tema-wrap .h-btn')
            if btnTema is None:
                bifa(False, 'antetul are butonul de tema', 'lipseste .tema-wrap .h-btn')
            else:
                btnTema.click()
                aseaza(page)
                moduri = page.query_selector_all('[role="menuitemradio"]')
                if len(moduri) < 3:
                    bifa(False, 'foaia de tema are cele trei moduri', '%d moduri' % len(moduri))
                else:
                    porneste_inregistrarea(page, SONDA_CADRU, 900)
                    page.wait_for_timeout(60)
                    armeaza(page)
                    # Al treilea mod e „Întunecat"; din tema deschisa e o
                    # schimbare reala, deci fondul chiar variaza.
                    moduri[2].click()
                    c = ia_cadrele(page, 900)
                    r = analizeaza(c, 'trecerea de tema', drum_minim=20,
                                   apasat=momentul_apasarii(page))
                    if r.get('nemiscat') or r.get('gol'):
                        bifa(False, 'trecerea de tema schimba fondul',
                             'fondul n-a variat — din tema deschisa, „Întunecat" trebuia sa-l schimbe')
                    else:
                        # UN cadru lung e permis, si e chiar mecanismul.
                        # `startViewTransition` fotografiaza tot ecranul: ala e un
                        # cadru scump prin definitie (~70ms), dar in timpul lui se
                        # afiseaza imaginea VECHE, inghetata — nu se intrerupe
                        # nicio miscare, fiindca stingerea inca n-a inceput.
                        # Peste unul inseamna ca s-a intors cineva la tranzitii pe
                        # tot arborele: varianta aceea dadea CINCI, cu unul de
                        # 252ms, si atunci chiar se vedea ecranul inghetand.
                        bifa(r['cadre_sarite'] <= 1,
                             'trecerea de tema: cel mult cadrul de instantaneu',
                             '%d cadre peste %dms (cel mai lung %sms) — s-a intors la '
                             'tranzitii pe tot arborele?'
                             % (r['cadre_sarite'], CADRU_LUNG, r['cadru_max']),
                             '%d cadru de instantaneu, %sms' % (r['cadre_sarite'], r['cadru_max']))
                page.keyboard.press('Escape')
                aseaza(page)

            # ============ D. GESTUL URMARESTE DEGETUL ============
            out('\n--- D. gestul urmareste degetul ---')
            page.goto(baza + '/#/tasks', wait_until='load')
            aseaza(page)
            rand = page.query_selector('.trow-wrap .gl-fata') or page.query_selector('.trow')
            if rand is None:
                bifa(False, 'lista are un rand pentru urmarire', 'niciun rand')
            else:
                rand.click()
                aseaza(page)
                cap = page.query_selector('.modal-header')
                if cap is None:
                    bifa(False, 'foaia are antet (de el se trage)', 'lipseste .modal-header')
                else:
                    bx = cap.bounding_box()
                    x, y = bx['x'] + bx['width'] / 2, bx['y'] + bx['height'] / 2
                    sus0 = page.evaluate(SONDA_FOAIE)
                    apuca(cdp, x, y)
                    ramaneri = []
                    for i in range(1, 11):
                        misca(cdp, x, y + i * 12)
                        page.wait_for_timeout(24)
                        sus = page.evaluate(SONDA_FOAIE)
                        if sus is None:
                            break
                        asteptat = sus0 + i * 12
                        ramaneri.append(abs(asteptat - sus))
                    ridica(cdp)
                    aseaza(page)
                    if ramaneri:
                        rmax = round(max(ramaneri), 1)
                        rmed = round(sum(ramaneri) / len(ramaneri), 1)
                        bifa(rmax <= PRAG_URMARIRE,
                             'foaia sta in mana (sub %dpx in urma)' % PRAG_URMARIRE,
                             'a ramas pana la %spx in urma (media %s)' % (rmax, rmed),
                             'max %spx, media %spx' % (rmax, rmed))
                    else:
                        bifa(False, 'gestul pe foaie se inregistreaza', 'foaia a disparut sub deget')
                page.keyboard.press('Escape')
                aseaza(page)

            # ============ E. TRAGE SA REINCARCI ============
            out('\n--- E. trage sa reincarci ---')
            page.goto(baza + '/#/tasks', wait_until='load')
            aseaza(page)
            page.evaluate('() => window.scrollTo(0, 0)')
            apuca(cdp, 195, 200)
            vazut = False
            for i in range(1, 14):
                misca(cdp, 195, 200 + i * 14)
                page.wait_for_timeout(22)
                if page.query_selector('.ptr'):
                    vazut = True
            prag = page.evaluate("() => { const d = document.querySelector('.ptr-disc');"
                                 " return d ? d.classList.contains('plin') : null }")
            ridica(cdp)
            page.wait_for_timeout(140)
            roteste = page.evaluate("() => { const e = document.querySelector('.ptr');"
                                    " return e ? e.classList.contains('roteste') : false }")
            bifa(vazut, 'arcul apare cand tragi de la capatul de sus', 'nu a aparut deloc')
            bifa(prag is True, 'arcul se umple pana la prag', 'n-a ajuns la prag (plin=%s)' % prag)
            bifa(roteste, 'dupa prag se roteste cat tine cererea', 'nu s-a rotit')
            # Pleaca dupa ce sosesc datele: se asteapta chiar asta, cu plafon.
            try:
                page.wait_for_function("() => !document.querySelector('.ptr')", timeout=4000)
            except Exception:
                pass
            plecat = page.query_selector('.ptr') is None
            bifa(plecat, 'arcul pleaca dupa ce sosesc datele', 'a ramas pe ecran')

            # sub o foaie deschisa, gestul NU e al paginii
            rand = page.query_selector('.trow-wrap .gl-fata') or page.query_selector('.trow')
            if rand:
                rand.click()
                aseaza(page)
                apuca(cdp, 195, 300)
                for i in range(1, 8):
                    misca(cdp, 195, 300 + i * 14)
                    page.wait_for_timeout(20)
                fura = page.query_selector('.ptr') is not None
                ridica(cdp)
                aseaza(page)
                bifa(not fura, 'sub o foaie deschisa, gestul ramane al foii',
                     'arcul de reincarcare a furat gestul foii')

            bifa(not erori, 'nicio exceptie in pagina', ' · '.join(erori[:3]))
            b.close()
    return R.incheie()


if __name__ == '__main__':
    sys.exit(banc.ruleaza(main))

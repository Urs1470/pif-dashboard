#!/usr/bin/env python3
"""Audit al sistemului de design — culoare, miscare, stari.

De ce exista. `smoke_ui.py` prinde ce CRAPA, `audit_mobil.py` prinde ce nu incape.
Niciunul nu poate prinde ce e doar INCOERENT: o a doua paleta copiata in alta pagina
si rotita cu doua pozitii se randeaza perfect, trece testele si arata bine in
izolare — se vede doar cand pui doua ecrane alaturi. Exact asa a trait luni de zile
divergenta dintre Calendar si Planificator: 43% dintre proiecte aveau doua culori.

Regulile de mai jos sunt cele pe care le-am incalcat efectiv, nu o lista de bune
practici luata de undeva. Fiecare are un comentariu cu ce s-a stricat.

    python scripts/audit_design.py            # raporteaza, iese 1 daca sunt abateri
    python scripts/audit_design.py --lista    # si listeaza fiecare aparitie
"""
import argparse
import re
import sys
from pathlib import Path

RADACINA = Path(__file__).resolve().parent.parent
SRC = RADACINA / 'frontend' / 'src'
TOKENS = SRC / 'styles' / 'tokens.css'

# Tokenuri de culoare definite O SINGURA data, cu buna stiinta.
#
# `--chart-1/2/3` sunt SERIILE unui grafic: acolo culoarea e DATE (curbe de motor
# in Calculator), nu identitate. O curba care isi schimba culoarea cu tema isi
# schimba intelesul — cititi doua capturi de ecran alaturate si nu mai stii daca
# rosul de pe una e aceeasi serie cu rosul de pe cealalta. Sunt alese sa treaca
# pe ambele fonduri, tocmai ca sa nu aiba nevoie de doua valori.
#
# (`--loc-*` si `--on-color` au devenit aliasuri la redesignul din 2026-08-08 si
# se scutesc singure prin regula de alias — raman aici doar ca istoric.)
INDEPENDENTE_DE_TEMA = {'--loc-site', '--loc-sediu', '--on-color',
                        '--chart-1', '--chart-2', '--chart-3'}

# Proprietati scrise la RULARE din JS (`element.style.setProperty`), nu declarate
# in tokens.css. Nu sunt tokenuri de design, sunt stare de gest transmisa catre CSS
# — de aceea se folosesc mereu cu valoare de rezerva, `var(--gl-p, 0)`.
#   --gl-p  : cat din drumul pana la pragul de bifare a facut degetul (0..1),
#             pus de lib/glisare.js ca sa creasca pista de bifare odata cu gestul.
#   --gl-s  : oglinda lui --gl-p pentru gestul spre STANGA (verbul de pe pista
#             de stanga: „Planifică" pe randul de task, „Șterge" pe subtask).
#   --trasY : cat a coborat sheet-ul sub deget, in px, pus de Modal.svelte.
#   --kb    : cat din ecran acopera TASTATURA, in px, pus de RichTextEditor din
#             `visualViewport` — singura sursa care stie asta (`innerHeight` si
#             `dvh` urmaresc bara de adresa, nu tastatura). Bara de unelte se
#             ridica deasupra ei; fara `visualViewport` ramane 0 si bara sta pe
#             marginea de jos, deci valoarea de rezerva e chiar comportamentul
#             vechi.
DIN_JS = {'--gl-p', '--gl-s', '--trasY', '--kb'}

# Fisiere in care valorile brute sunt legitime, cu motiv.
SCUTITE_HEX = {
    # Sursa unica a paletei de identitate — aici valorile TREBUIE sa fie brute.
    'lib/culori.js',
    # Pagina embed-uita a planului de departament: iframe strain, fara tokenurile noastre.
    'pages/Departament.svelte',
}


def fisiere():
    for p in sorted(SRC.rglob('*.svelte')):
        yield p
    for p in sorted(SRC.rglob('*.css')):
        yield p


def rel(p):
    # `.as_posix()`, nu `str()`: pe Windows str() da `pages\Departament.svelte`,
    # iar SCUTITE_HEX (si orice comparatie de cale de aici) e scris cu `/` — deci
    # scutirile nu se potriveau niciodata si `#fff`-ul legitim din pagina embed
    # era raportat ca abatere la fiecare rulare.
    return p.relative_to(SRC).as_posix()


def fara_comentarii(text):
    """Neutralizeaza comentariile CSS/JS ca sa nu raportam exemple din explicatii.

    Le inlocuieste cu spatii de aceeasi lungime, PASTRAND liniile noi: altfel
    pozitiile se decaleaza si raportul arata numere de linie care nu exista in
    fisierul real (prima versiune a facut exact asta si a trimis la randuri
    nevinovate)."""
    def goleste(m):
        return re.sub(r'[^\n]', ' ', m.group(0))
    text = re.sub(r'/\*.*?\*/', goleste, text, flags=re.S)
    text = re.sub(r'(?m)//[^\n]*', goleste, text)
    return text


def blocuri_print(text):
    """Intervalele acoperite de @media print — acolo cerneala inchisa e corecta
    indiferent de tema, pentru ca hartia e alba."""
    spans = []
    for m in re.finditer(r'@media\s+print[^{]*\{', text):
        i, adanc = m.end(), 1
        while i < len(text) and adanc:
            if text[i] == '{':
                adanc += 1
            elif text[i] == '}':
                adanc -= 1
            i += 1
        spans.append((m.start(), i))
    return spans


def in_span(poz, spans):
    return any(a <= poz < b for a, b in spans)


class Audit:
    def __init__(self):
        self.abateri = []       # (regula, fisier, linie, fragment)

    def abatere(self, regula, p, text, poz, fragment):
        linie = text.count('\n', 0, poz) + 1
        self.abateri.append((regula, rel(p), linie, fragment.strip()[:100]))

    # -- R1 -----------------------------------------------------------------
    def r1_transition_all(self, p, text, curat):
        """`transition: all` urmareste si proprietatile care reaseaza pagina
        (width/height/padding), animate pe firul principal. Foloseste
        var(--transition-colors) sau var(--transition-pressable)."""
        for m in re.finditer(r'transition:\s*all\b', curat):
            self.abatere('R1 transition:all', p, curat, m.start(), m.group(0))

    # -- R10 ----------------------------------------------------------------
    def r10_prescurtare_in_tranzitie(self, p, text, curat):
        """Prescurtarile in `transition:` animeaza TOATE sub-proprietatile.

        `transition: background` nu inseamna „culoarea de fond": inseamna si
        `background-image`, si `background-position`, si `background-size`. Pe
        un element cu gradient asta e paint pe fiecare cadru — masurat pe
        telefon, celulele Calendarului (42 deodata, cu liniile de grila desenate
        dintr-un `linear-gradient`) animau `background-position-x` si `-y` la
        FIECARE hover si la fiecare schimbare de tab. Se randeaza perfect, deci
        nu se vede decat masurand.

        Sistemul are deja raspunsul scris: `--transition-colors` enumera
        `background-color`, nu `background`. Erau 21 de locuri care il ocoleau.

        `border` si `font` sunt in aceeasi familie: `border` trage dupa el
        `border-width`, care reaseaza."""
        for m in re.finditer(r'transition:[^;{}]*', curat):
            for pres in ('background', 'border', 'font', 'flex', 'mask'):
                if re.search(r'\b%s\s+(?:var\(|\d)' % pres, m.group(0)):
                    self.abatere('R10 prescurtare in transition (%s)' % pres,
                                 p, curat, m.start(), m.group(0)[:70])

    # -- R2 -----------------------------------------------------------------
    def r2_hex_brut(self, p, text, curat):
        """Culoare scrisa de mana in loc de token. Asa au aparut TREI ambere
        diferite pentru acelasi „sediu" (#c99a3a, #b98a2e, #c9a13a)."""
        if rel(p) in SCUTITE_HEX or p.name == 'tokens.css':
            return
        printuri = blocuri_print(curat)
        for m in re.finditer(r'#[0-9a-fA-F]{3,8}\b', curat):
            val = m.group(0).lower()
            # #fff/#000 in color-mix sunt operatii de deschidere/inchidere, nu culori.
            inainte = curat[max(0, m.start() - 90):m.start()]
            # In `color-mix` alb/negru sunt operatii de deschidere/inchidere.
            # Intr-o MASCA (`mask-image`) negrul nu e culoare, e canalul alfa:
            # „aici se vede". Nu se schimba cu tema si n-are token.
            if val in ('#fff', '#000', '#ffffff', '#000000') and (
                    'color-mix' in inainte or 'mask-image' in inainte):
                continue
            if in_span(m.start(), printuri):
                continue
            self.abatere('R2 hex brut', p, curat, m.start(), m.group(0))

        # `rgb()`/`rgba()`/`hsl()` sunt tot culori scrise de mana, doar in alta
        # notatie — iar regula de mai sus cauta doar `#`, deci treceau nevazute.
        # Punct orb gasit la auditul din 2026-08-15: 14 aparitii, toate scrimuri
        # si umbre fara token. Un audit care raporteaza „curat" fara sa se uite
        # e mai rau decat unul care lipseste: te invata sa te bazezi pe el.
        #
        # `rgba(0,0,0,α)` NU e scutit, desi e „doar negru cu alfa": exact asta erau
        # toate cele 14 — valuri si umbre scrise de mana, cu PATRU opacitati
        # diferite (.5, .55, .6, .65) pentru acelasi lucru. E acelasi tipar ca
        # cele trei ambere, doar in alta notatie. Negru cu alfa e legitim ca
        # PRIMITIVA, adica in definitia unui token (`--shadow-*`, `--scrim-*` in
        # tokens.css, care e scutit intreg), nu la locul de folosire.
        for m in re.finditer(r'\b(?:rgba?|hsla?)\(([^)]*)\)', curat):
            if in_span(m.start(), printuri):
                continue
            inainte = curat[max(0, m.start() - 90):m.start()]
            # In `color-mix` si intr-o masca, negrul/albul sunt operatii, nu culori.
            # `flood-color` la fel: intr-un filtru SVG negrul e canalul umbrei, iar
            # intensitatea sta separat in `flood-opacity` — nu e o culoare de tema.
            if ('color-mix' in inainte or 'mask-image' in inainte
                    or 'flood-color' in inainte):
                continue
            self.abatere('R2 culoare bruta', p, curat, m.start(), m.group(0))

    # -- R3 -----------------------------------------------------------------
    def r3_durata_bruta(self, p, text, curat):
        """Durata scrisa in cifre intr-o tranzitie: scara de miscare se
        desincronizeaza pe tacute. Foloseste var(--dur-fast/base/slow/press)."""
        if p.name == 'tokens.css':
            return
        for m in re.finditer(r'transition:[^;{}]*', curat):
            frag = m.group(0)
            for d in re.finditer(r'(?<![\w-])\d*\.?\d+m?s\b', frag):
                self.abatere('R3 durata bruta', p, curat, m.start(), frag)
                break

    # -- R4 -----------------------------------------------------------------
    def r4_easing_brut(self, p, text, curat):
        """cubic-bezier scris de mana in loc de var(--ease)."""
        if p.name == 'tokens.css':
            return
        for m in re.finditer(r'cubic-bezier\(', curat):
            self.abatere('R4 easing brut', p, curat, m.start(), 'cubic-bezier(...)')

    # -- R5 -----------------------------------------------------------------
    def r5_paleta_duplicata(self, p, text, curat):
        """O a doua paleta de identitate in afara lib/culori.js. Regula asta
        exista din cauza divergentei Calendar <-> Planificator."""
        if rel(p) in SCUTITE_HEX:
            return
        for m in re.finditer(r'\[\s*(?:\'#[0-9a-fA-F]{3,8}\'\s*,\s*){2,}', curat):
            self.abatere('R5 paleta duplicata', p, curat, m.start(), m.group(0))
    # -- R8 -----------------------------------------------------------------
    def r8_tranzitie_fara_easing(self, p, text, curat):
        """O tranzitie Svelte fara `easing` cade pe implicitul bibliotecii —
        `linear` la `fade`, `cubicOut` la `scale`. Adica a DOUA curba pe acelasi
        ecran, langa `--ease` pe care o respecta tot CSS-ul. Capcana e
        documentata in `motion.svelte.js` si a fost reintrodusa de sase ori."""
        tip = r'(?:transition|in|out):(?:slide|fly|fade|scale|blur|draw)(?:\|\w+)?='
        for m in re.finditer(tip + r'\{\{([^}]*)\}\}', curat):
            if 'easing' not in m.group(1):
                self.abatere('R8 tranzitie fara easing', p, curat, m.start(),
                             m.group(0))

    # -- R9 -----------------------------------------------------------------
    # -- R11 ----------------------------------------------------------------
    def r11_tipografie_bruta(self, p, text, curat):
        """`letter-spacing` scris in cifre. Scara are trei valori, atat.

        Nu se vedea pana la auditul din 2026-08-15, fiindca auditul nu se uita:
        erau cinci locuri, dintre care doua cu `-0.015em` scris de mana langa un
        `--tracking-tight` de `-0.01em`. Doua valori pentru „stramt" e exact
        felul in care s-au nascut cele trei ambere.

        `line-height` NU e prins aici, cu buna stiinta: `line-height: 1` pe o
        cutie de iconita sau pe un numar e idiomul „cutia strange glifa" — un
        reset de layout, nu o alegere tipografica, si niciun token din scara
        (1.15 / 1.35 / 1.55 / 1.7) nu inseamna asta. O regula care l-ar cere
        tokenizat ar produce doar zgomot.
        """
        if p.name == 'tokens.css':
            return
        printuri = blocuri_print(curat)
        for m in re.finditer(r'letter-spacing:\s*([^;{}]+)', curat):
            val = m.group(1).strip()
            if val.startswith('var(--tracking') or 'inherit' in val or 'normal' == val:
                continue
            if in_span(m.start(), printuri):
                continue
            self.abatere('R11 letter-spacing brut', p, curat, m.start(), m.group(0))

    def r9_touch_action_fara_gest(self, p, text, curat):
        """`touch-action: none` ii ia browserului derularea pe acel element.
        Se plateste doar daca exista un gest care s-o inlocuiasca. Pe `.bar` din
        Planificator statea fara niciun gest tactil in spate (acela era oprit din
        cod), deci mancarea derularea si nu dadea nimic in schimb."""
        if 'touch-action' not in curat:
            return
        # Un gest exista daca se foloseste o actiune de gest, daca se cheama
        # direct pornirea unei trageri, SAU daca elementul isi trateaza singur
        # pointerul (asa e scris gestul foii din `Modal.svelte`).
        are_gest = re.search(r'use:(glisare|tragere|reordonare)|incepeTragere|'
                             r'tragePeZile|onpointerdown', curat)
        if are_gest:
            return
        for m in re.finditer(r'touch-action:\s*none', curat):
            self.abatere('R9 touch-action: none fara gest', p, curat, m.start(),
                         m.group(0))

    # -- R10 ----------------------------------------------------------------
    def r10_zindex_literal(self, p, text, curat):
        """Un `z-index` scris de mana nu se poate compara cu scara din tokens,
        deci stivele se ciocnesc in tacere: paleta si modalul stateau amandoua pe
        1000 si ordinea de pictare venea din ordinea din DOM."""
        # Sub 100 sunt ordonari LOCALE intr-un singur component (un maner peste
        # banda lui, o eticheta peste o bara). Ele NU se pot ciocni de scara
        # aplicatiei, care incepe la `--z-dropdown: 100` — deci nu sunt clasa de
        # bug pe care o cauta regula. Se raporteaza doar valorile care intra in
        # banda tokenurilor, adica exact cele care se pot suprapune tacut peste
        # dropdown / sticky / modal / toast / tooltip.
        for m in re.finditer(r'z-index:\s*(-?\d+)\s*;', curat):
            if abs(int(m.group(1))) < 100:
                continue
            self.abatere('R10 z-index in banda tokenurilor, scris de mana',
                         p, curat, m.start(), m.group(0))

    # -- R11 ----------------------------------------------------------------
    def r11_hover_only(self, p, text, curat):
        """Un control ascuns cu `opacity: 0` care se aprinde DOAR la `:hover` e
        invizibil pe telefon — acolo nu exista hover. Perechea obligatorie e ori
        `:focus-within` (tastatura), ori un bloc `(hover: none)` care il arata
        altfel. Asa a stat pubela de subtask permanent pe rand, si asa ar fi
        ramas manerele de intindere invizibile la deget."""
        for m in re.finditer(r'\.([\w-]+)\s*\{[^}]*opacity:\s*0[^}]*\}', curat):
            cls = m.group(1)
            # (1) Doar CONTROALE. Un decor ascuns (o umbra, un indiciu) n-are ce
            #     sa piarda pe telefon; regula e despre lucruri pe care le APESI.
            if not re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b[^"]*"[^>]*on(click|pointerdown)',
                             curat) and not re.search(
                             r'on(click|pointerdown)[^>]*class="[^"]*\b' + re.escape(cls) + r'\b',
                             curat):
                continue
            # (2) `:hover` chiar il APRINDE? `.modal-close` are `opacity: 0`
            #     cand nu e varful stivei, si un `:hover` care schimba doar
            #     fondul — nu e un control ascuns pana treci cursorul, e unul
            #     scos din uz cu bunastiinta. Discriminantul: regula de hover
            #     trebuie sa atinga chiar `opacity`.
            aprins = False
            for h in re.finditer(r'([^{}]*:hover[^{}]*)\{([^}]*)\}', curat):
                if re.search(r'\.' + re.escape(cls) + r'\b', h.group(1)) \
                        and re.search(r'opacity:\s*[^0]', h.group(2)):
                    aprins = True
                    break
            if not aprins:
                continue
            # (3) Perechea se cauta PE ACEEASI CLASA, nu oriunde in fisier: un
            #     `(hover: none)` care vorbeste despre alt element nu salveaza
            #     controlul asta. Prima varianta cauta `hover: none` in tot
            #     fisierul si de aceea nu raporta aproape nimic.
            are_focus = re.search(r'\.' + re.escape(cls) + r'\b[^{;]*:focus(-within|-visible)?',
                                  curat)
            are_touch = False
            # Garda de touch e scrisa in sistem si ca `(hover: none)`, si ca
            # `(max-width: …)` — amandoua inseamna „aici nu exista cursor".
            for b in re.finditer(r'@media[^{]*(?:hover:\s*none|max-width)[^{]*\{', curat):
                # corpul blocului media, pana la acolada perechea lui
                i, adanc = b.end(), 1
                while i < len(curat) and adanc:
                    if curat[i] == '{': adanc += 1
                    elif curat[i] == '}': adanc -= 1
                    i += 1
                if re.search(r'\.' + re.escape(cls) + r'\b', curat[b.end():i]):
                    are_touch = True
                    break
            if not are_focus and not are_touch:
                self.abatere('R11 control aprins doar la hover', p, curat, m.start(),
                             '.' + cls)




def tokenuri_definite(text):
    """Tokenurile declarate, pe bloc de tema, plus cele care sunt ALIASURI.

    Un alias e un token a carui valoare trimite la alt token (`var(--x)`, direct
    sau printr-un `color-mix`). El nu are nevoie de o a doua definitie pe tema
    deschisa: `var()` se rezolva la LOCUL FOLOSIRII, deci tokenul urmeaza
    automat ce urmeaza tinta lui. A cere paritate pentru el ar insemna sa scrii
    aceeasi linie de doua ori — adica exact a doua sursa de adevar pe care
    regula incearca s-o previna.
    """
    blocuri, aliasuri = {}, set()
    for m in re.finditer(r'(:root[^{]*|\[data-theme="[^"]+"\][^{]*)\{(.*?)\n\}', text, re.S):
        corp = m.group(2)
        blocuri[m.group(1).strip()] = set(re.findall(r'(--[\w-]+)\s*:', corp))
        for d in re.finditer(r'(--[\w-]+)\s*:([^;]*);', corp):
            if 'var(' in d.group(2):
                aliasuri.add(d.group(1))
    return blocuri, aliasuri


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--lista', action='store_true', help='listeaza fiecare aparitie')
    args = ap.parse_args()

    if not SRC.exists():
        print(f'nu gasesc {SRC}', file=sys.stderr)
        return 2

    a = Audit()
    texte = {}
    for p in fisiere():
        text = p.read_text(encoding='utf-8')
        texte[p] = text
        curat = fara_comentarii(text)
        a.r1_transition_all(p, text, curat)
        a.r10_prescurtare_in_tranzitie(p, text, curat)
        a.r2_hex_brut(p, text, curat)
        a.r3_durata_bruta(p, text, curat)
        a.r4_easing_brut(p, text, curat)
        a.r5_paleta_duplicata(p, text, curat)
        a.r8_tranzitie_fara_easing(p, text, curat)
        a.r9_touch_action_fara_gest(p, text, curat)
        a.r11_tipografie_bruta(p, text, curat)
        a.r10_zindex_literal(p, text, curat)
        a.r11_hover_only(p, text, curat)

    # -- R6: tokenuri folosite dar nedefinite -------------------------------
    tk = TOKENS.read_text(encoding='utf-8')
    blocuri, aliasuri = tokenuri_definite(tk)
    definite = set().union(*blocuri.values()) if blocuri else set()
    # tokenurile derivate din env()/definite local in componente sunt permise
    locale = set()
    for p, text in texte.items():
        locale |= set(re.findall(r'(--[\w-]+)\s*:', text))
    folosite = {}
    for p, text in texte.items():
        for m in re.finditer(r'var\(\s*(--[\w-]+)', text):
            folosite.setdefault(m.group(1), []).append(p)
    nedefinite = sorted(t for t in folosite
                        if t not in definite and t not in locale and t not in DIN_JS)

    # -- R7: paritate intre teme -------------------------------------------
    dark = blocuri.get(':root,\n[data-theme="dark"]') or next(
        (v for k, v in blocuri.items() if 'dark' in k or k.startswith(':root')), set())
    light = next((v for k, v in blocuri.items() if 'light' in k), set())
    # Tokenurile de culoare trebuie sa existe in ambele teme; scarile structurale
    # (spacing/typography/z-index) se definesc o singura data, in :root.
    culoare = re.compile(r'--(accent|bg|text|border|success|warning|danger|info|purple|service|chart|loc|on-color|shadow)')
    doar_dark = sorted(t for t in dark - light
                       if culoare.match(t)
                       and t not in INDEPENDENTE_DE_TEMA
                       and t not in aliasuri)

    # -- raport -------------------------------------------------------------
    print('AUDIT SISTEM DE DESIGN\n' + '=' * 60)
    reguli = {}
    for regula, f, l, frag in a.abateri:
        reguli.setdefault(regula, []).append((f, l, frag))

    total = 0
    for regula in sorted(reguli):
        ap_ = reguli[regula]
        total += len(ap_)
        print(f'\n{regula}: {len(ap_)}')
        aratate = ap_ if args.lista else ap_[:5]
        for f, l, frag in aratate:
            print(f'   {f}:{l}  {frag}')
        if not args.lista and len(ap_) > 5:
            print(f'   … si inca {len(ap_) - 5} (--lista pentru toate)')

    if nedefinite:
        total += len(nedefinite)
        print(f'\nR6 token folosit dar nedefinit: {len(nedefinite)}')
        for t in nedefinite:
            print(f'   {t}  (in {rel(folosite[t][0])})')

    if doar_dark:
        total += len(doar_dark)
        print(f'\nR7 token de culoare doar in tema dark: {len(doar_dark)}')
        for t in doar_dark:
            print(f'   {t}')

    print('\n' + '=' * 60)
    if total == 0:
        print('curat — nicio abatere')
        return 0
    print(f'{total} abateri')
    return 1


if __name__ == '__main__':
    sys.exit(main())

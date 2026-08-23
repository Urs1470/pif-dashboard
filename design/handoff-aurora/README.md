# Handoff: Ecranul Acasă + iconița TORQA (direcția „sticlă cu muchie-lentilă")

## Overview

Redesign vizual al ecranului **Acasă** din TORQA (aplicație de urmărire a punerilor în funcțiune — proiecte, taskuri, deplasări) plus **marca și iconița de aplicație** nouă.

Structura ecranului nu se schimbă față de codul existent: aceleași blocuri, aceleași poziții, aceeași densitate, aceleași comportamente. Se schimbă **stratul de tokenuri** (paletă, tipografie, forme, umbre), **poziția navigației** și **materialul barelor de navigație**. Plus o marcă nouă care înlocuiește pulsul pătrat de până acum.

Repo sursă: `Urs1470/pif-dashboard`, branch `master`, subarbore `frontend/src`.

## About the Design Files

Fișierele din `design/` sunt **referințe de design realizate în HTML** — prototipuri care arată aspectul și comportamentul intenționat, **nu cod de producție de copiat direct**. Sunt scrise într-un runtime propriu (`support.js`, fișiere `.dc.html`) care nu are legătură cu aplicația țintă.

Sarcina e **recrearea acestor design-uri în codul existent** — aplicația reală e **Svelte**, cu `frontend/src/styles/tokens.css` și `global.css` — folosind componentele și convențiile ei. Singurele fișiere din pachet gândite să intre ca atare în cod sunt:

- `assets/torqa-app-icon.svg` — iconița de aplicație
- `assets/torqa-logomark.svg` — marca pentru bara aplicației
- valorile din `design/tokens-variante.css` — de transcris în `tokens.css` (aceleași **nume de roluri**, alte valori)

Deschiderea prototipurilor: `design/*.dc.html` se deschid direct în browser (au nevoie de `support.js` lângă ele, inclus).

## Fidelity

**High-fidelity.** Culorile, tipografia, spațierile, razele, umbrele și tranzițiile sunt finale. Geometria de layout (înălțimi de rând, gap-uri, lățimea coloanei de conținut, ținte de atingere) e preluată din codul existent și **nu trebuie schimbată** — dacă un număr din acest document contrazice codul actual pe geometrie, codul are dreptate.

---

## Design Tokens

Se transcriu în `frontend/src/styles/tokens.css`, păstrând **exact aceleași nume de roluri** care există deja. Mai jos e setul complet.

### Comune (ambele teme)

| Token | Valoare |
|---|---|
| `--font-sans` | `'Gabarito', system-ui, sans-serif` |
| `--font-mono` | `'DM Mono', ui-monospace, monospace` |
| `--font-title` | `var(--font-sans)` |
| `--w-title` | `600` |
| `--ls-title` | `-0.02em` |
| `--w-row` | `500` |
| `--w-ctrl` | `500` |
| `--radius-xs` | `999px` (controale pastilă) |
| `--radius-sm` | `14px` |
| `--radius-md` | `24px` |
| `--radius-lg` | `30px` |
| `--radius-full` | `9999px` |
| `--ease` | `cubic-bezier(.32, .72, .28, 1)` |
| `--transition-colors` | `background-color .12s var(--ease), border-color .12s var(--ease), color .12s var(--ease), box-shadow .12s var(--ease), opacity .12s var(--ease)` |
| `--glass-sheen` | `none` — vezi nota de mai jos |

> **Nota despre `--glass-sheen`:** a fost eliminat intenționat. Sticla **nu** are spălare de gradient peste suprafață; volumul vine exclusiv din muchie. Tokenul rămâne definit ca `none` doar ca punct de extensie.

### Temă întunecată (cărbune — **nu** AMOLED)

| Token | Valoare |
|---|---|
| `--bg` | `#15151a` |
| `--bg-surface` | `#1e1e25` |
| `--bg-elevated` | `#27272f` |
| `--border` | `#30303a` |
| `--border-strong` | `#45454f` |
| `--text` | `#ededf2` |
| `--text-secondary` | `#a6a6b2` |
| `--text-dim` | `#86868f` |
| `--accent` | `#a3a3cc` |
| `--accent-deep` | `#c4c4e6` |
| `--accent-subtle` | `#262633` |
| `--accent-text` | `#14141b` |
| `--danger` | `#e08a7c` |
| `--danger-deep` | `#f0a598` |
| `--success` | `#86c4a6` |
| `--panel-line` | `rgba(255,255,255,.04)` |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,.35)` |
| `--shadow-md` | `0 2px 4px rgba(0,0,0,.30), 0 24px 48px -28px rgba(0,0,0,.80)` |
| `--halo` | `radial-gradient(60% 34% at 50% -12%, rgba(163,163,204,.14), transparent 76%)` |

### Temă deschisă

| Token | Valoare |
|---|---|
| `--bg` | `#f5f5f9` |
| `--bg-surface` | `#ffffff` |
| `--bg-elevated` | `#eeeef4` |
| `--border` | `#e3e3eb` |
| `--border-strong` | `#c7c7d4` |
| `--text` | `#1c1c24` |
| `--text-secondary` | `#55555f` |
| `--text-dim` | `#7a7a86` |
| `--accent` | `#63638f` |
| `--accent-deep` | `#4a4a72` |
| `--accent-subtle` | `#ececf4` |
| `--accent-text` | `#ffffff` |
| `--danger` | `#a8483a` |
| `--danger-deep` | `#85372b` |
| `--success` | `#3a7a5e` |
| `--panel-line` | `rgba(28,28,36,.06)` |
| `--shadow-sm` | `0 1px 2px rgba(40,40,70,.06)` |
| `--shadow-md` | `0 2px 4px rgba(40,40,70,.05), 0 24px 48px -30px rgba(40,40,70,.28)` |
| `--halo` | `radial-gradient(60% 34% at 50% -12%, rgba(163,163,204,.24), transparent 76%)` |

### Tokenuri de sticlă (noi)

| Token | Întunecat | Deschis |
|---|---|---|
| `--glass-bg` | `rgba(44,44,56,.50)` | `rgba(255,255,255,.55)` |
| `--glass-filter` | `saturate(180%) blur(26px)` | `saturate(180%) blur(26px)` |
| `--glass-edge` | `blur(1px) saturate(210%) brightness(1.22)` | `blur(1px) saturate(200%) brightness(1.06)` |
| `--glass-rim` | `inset 0 1px 0 rgba(255,255,255,.22), inset 0 2px 1px -1px rgba(255,255,255,.10), inset 0 0 0 1px rgba(255,255,255,.07), inset 0 -1px 0 rgba(0,0,0,.36)` | `inset 0 1px 0 #fff, inset 0 2px 1px -1px rgba(255,255,255,.9), inset 0 0 0 1px rgba(28,28,36,.07), inset 0 -1px 0 rgba(28,28,36,.07)` |
| `--glass-cast` | `0 1px 2px rgba(0,0,0,.45), 0 16px 34px -14px rgba(0,0,0,.70)` | `0 1px 2px rgba(40,40,70,.07), 0 16px 34px -14px rgba(40,40,70,.22)` |
| `--glass-fill` (element activ) | `rgba(163,163,204,.14)` | `rgba(255,255,255,.80)` |
| `--glass-sel` (ramă element activ) | `inset 0 0 0 1px rgba(163,163,204,.24), inset 0 1px 0 rgba(255,255,255,.22), inset 0 -1px 0 rgba(0,0,0,.24)` | `inset 0 0 0 1px rgba(28,28,36,.10), inset 0 1px 0 #fff, inset 0 -1px 0 rgba(28,28,36,.05)` |
| `--glass-spec-a` / `-b` (reflex) | `rgba(214,214,255,.20)` / `rgba(214,214,255,.06)` | `rgba(255,255,255,.85)` / `rgba(255,255,255,.30)` |
| `--bar-bg` (rezervă fără blur) | `rgba(21,21,26,.62)` | `rgba(245,245,249,.70)` |
| `--dock-bg` (rezervă fără blur) | `rgba(30,30,38,.55)` | `rgba(255,255,255,.60)` |
| `--fab-bg` | `#a3a3cc` | `#63638f` |
| `--fab-rim` | `inset 0 1px 0 rgba(255,255,255,.38), inset 0 -1px 0 rgba(0,0,0,.20)` | `inset 0 1px 0 rgba(255,255,255,.34), inset 0 -1px 0 rgba(0,0,0,.14)` |
| `--fab-glow` | `0 2px 6px rgba(0,0,0,.45), 0 10px 22px -10px rgba(163,163,204,.35)` | `0 2px 6px rgba(40,40,70,.16), 0 10px 22px -10px rgba(99,99,143,.40)` |

### Reguli de culoare

- **Un singur accent.** `--accent` e singura culoare de identitate. Nu se introduc alte culori decorative.
- **Roșul e rezervat severității** (`--danger`): termene depășite, perioade neînchise. Nu se folosește ornamental.
- Pe temă deschisă accentul coboară de la `#A3A3CC` la `#63638F` ca să rămână lizibil pe alb (contrast text pe `--bg-surface`).

---

## Componenta cheie: suprafața de sticlă

Se folosește pentru **bara de sus pe desktop**, **antetul de pe telefon** și **dockul plutitor de pe telefon**. E o stivă de straturi absolute peste un container cu `isolation: isolate`, în ordinea de mai jos. Containerul însuși **nu are `background`** — altfel straturile de dedesubt nu au ce refracta.

```html
<div class="glass">            <!-- box-shadow: var(--glass-rim), var(--glass-cast); isolation: isolate -->
  <span class="g-blur"></span> <!-- 1. blur + saturație -->
  <span class="g-edge"></span> <!-- 2. banda-lentilă pe contur -->
  <span class="g-tint"></span> <!-- 3. tenta -->
  <span class="g-spec"></span> <!-- 4. reflexul care urmărește cursorul -->
  <!-- conținutul, cu position: relative -->
</div>
```

```css
.glass {
  position: relative;
  box-shadow: var(--glass-rim), var(--glass-cast);
  isolation: isolate;
  /* border-radius: var(--radius-full) pe bara desktop, 30px pe dock */
}
.glass > span { position: absolute; inset: 0; border-radius: inherit; pointer-events: none; }

/* 1 */
.g-blur { -webkit-backdrop-filter: var(--glass-filter); backdrop-filter: var(--glass-filter); }

/* 2 — inelul de 13px de pe margine, cu blur mic si luminozitate mare.
      mask-composite decupeaza centrul, deci filtrul se aplica DOAR pe banda. */
.g-edge {
  padding: 13px;
  -webkit-backdrop-filter: var(--glass-edge); backdrop-filter: var(--glass-edge);
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
          mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor; mask-composite: exclude;
}

/* 3 */
.g-tint { background: var(--glass-bg); }

/* 4 */
.g-spec {
  opacity: var(--spec, 0);
  transition: opacity .35s var(--ease);
  background: radial-gradient(150px 74px at calc(var(--mx, .5) * 100%) calc(var(--my, .5) * 100%),
              var(--glass-spec-a), var(--glass-spec-b) 42%, transparent 72%);
}
```

Reflexul (stratul 4) e singura parte cu JS. Pe `pointermove` peste suprafață se scriu `--mx`/`--my` (0…1) și `--spec: 1`; pe `pointerleave`, `--spec: 0`:

```js
el.addEventListener('pointermove', (e) => {
  const r = el.getBoundingClientRect();
  el.style.setProperty('--mx', ((e.clientX - r.left) / r.width).toFixed(3));
  el.style.setProperty('--my', ((e.clientY - r.top) / r.height).toFixed(3));
  el.style.setProperty('--spec', '1');
});
el.addEventListener('pointerleave', () => el.style.setProperty('--spec', '0'));
```

Pe dockul de telefon raza reflexului e `110px 60px` în loc de `150px 74px`.

**De ce așa și nu altfel:**
- Filtrele SVG în `backdrop-filter: url(#…)` **nu funcționează în Chromium** — încercarea inițială cu `feDisplacementMap` a fost abandonată. Banda-lentilă cu `mask-composite` dă același efect de „grosime de sticlă" și se randează peste tot.
- Fără stratul 2, rezultatul e glassmorphism obișnuit (blur + chenar + umbră). Muchia e ce face diferența.
- Dacă `backdrop-filter` nu e disponibil, stratul 3 trebuie să cadă pe `--bar-bg` / `--dock-bg` (aceleași culori, alfa mai mare), altfel textul devine ilizibil.

**Accesibilitate:** textul care stă pe sticlă are în spate blur de 26px, care aplatizează conținutul de dedesubt. Nu reduceți blurul sub ~20px fără să reverificați contrastul — e critica principală adusă acestui material.

---

## Screens / Views

### 1. Acasă — desktop (`design/Ecran Acasa.dc.html`)

**Purpose:** panoul de start. Arată următoarea deplasare, alertele deschise și boardul „Astăzi" cu taskurile zilei.

**Layout:**
- Rădăcină `position: relative; overflow: hidden`, `background: var(--bg)`.
- Un strat de halou: `position: absolute; inset: 0; z-index: 0; background: var(--halo)`.
- Bara de navigație (vezi mai jos) — `position: absolute; z-index: 3`, deci conținutul trece pe sub ea.
- Un distanțier de `80px` înălțime în fluxul normal, ca prima linie de conținut să nu intre sub bară.
- Conținut: `position: relative; z-index: 1`, `max-width: 1400px; margin: 0 auto`, interior `padding: 24px; max-width: 920px; margin-inline: auto`.

**Bara de sus (dockul mutat sus):**
- `position: absolute; top: 14px; left: 18px; right: 18px; height: 54px`, `border-radius: var(--radius-full)`, suprafață de sticlă completă (stiva de 4 straturi).
- `padding: 0 8px 0 18px`, `display: flex; align-items: center; gap: 18px`.
- **Stânga:** marca, `40 × 40 px`, doar semnul (`assets/torqa-logomark.svg`), `stroke: var(--accent)`. Fără text lângă ea.
- **Centru:** `<nav>` cu `flex: 1; display: flex; justify-content: center; gap: 2px`. Elementele sunt etichete text grupate, nu distribuite pe lățime.
  - Element: `height: 34px; padding: 0 14px; border-radius: var(--radius-full); font-size: 0.8125rem; letter-spacing: -0.005em; white-space: nowrap`.
  - Inactiv: `color: var(--text-secondary)`, `font-weight: 400`, fundal transparent. Hover → `color: var(--text)`.
  - **Activ:** `color: var(--text)`, `font-weight: 500`, `background: var(--glass-fill)`, `box-shadow: var(--glass-sel)`, plus `backdrop-filter: saturate(200%) blur(20px)` propriu — o pastilă de sticlă în sticlă.
  - Pagini, în ordine: Acasă, Proiecte, Taskuri, Planificator, Calendar, Departament, Calculator.
- **Dreapta:** două butoane rotunde `34 × 34 px`, `border-radius: var(--radius-full)`, `color: var(--text-secondary)`, hover `color: var(--text); background: var(--bg-hover)`: căutare (Ctrl+K) și comutator de temă. Iconițe Lucide outline, `16–17px`, `stroke-width: 1.5`.

**Linia de ieșiri** (sub bară, un singur rând, `flex-wrap: nowrap`, `gap: 12px`):
- Buton „următoarea deplasare": `min-height: 38px; padding: 0 14px; border-radius: var(--radius-xs)` (pastilă), `background: var(--bg-surface)`, `border: 1px solid var(--panel-line)`, `box-shadow: var(--shadow-sm)`. Conține: pin `15px` în `var(--accent)`; „Mâine" în `var(--accent-deep)`, `font-weight: var(--w-ctrl)`; numele clientului în `var(--text)`; descrierea în `var(--text-secondary)` cu `text-overflow: ellipsis` (`flex: 0 1 auto; min-width: 0`); perioada în `var(--font-mono)`, `0.75rem`, `var(--text-dim)`.
- Distanțier `flex: 1 0 12px`.
- Două cip-uri la dreapta, `flex: none`, `padding: 4px 8px 4px 10px`, `border-radius: var(--radius-xs)`, `font-size: 0.8125rem`:
  - neutru — `background: var(--bg-surface)`, `color: var(--text-dim)`, text „N fără perioadă";
  - de severitate — `background: var(--danger-subtle)`, `color: var(--danger-deep)`, text „N perioade trecute, proiect neînchis" + chevron.

**Panoul „Astăzi":** `background: var(--bg-surface)`, `border: 1px solid var(--panel-line)`, `border-radius: var(--radius-md)`, `box-shadow: var(--shadow-md)`, `padding: 20px 8px 6px`.
- Titlu `1.5625rem`, `font-family: var(--font-title)`, `font-weight: var(--w-title)`, `letter-spacing: var(--ls-title)`; lângă el ziua în `0.8125rem var(--text-dim)` și indicatorul „N restante" cu bulină de `7px` în `var(--danger)`.
- Buton „Adaugă task": `height: 38px; padding: 0 14px; border-radius: var(--radius-sm)`, `background: var(--bg-elevated)`, `border: 1px solid var(--panel-line)`.
- Câmp de adăugare rapidă: `min-height: 44px`, `background: var(--bg-elevated)`, `border: 1px solid var(--border)`, `border-radius: var(--radius-sm)`, placeholder în `var(--text-dim)`.
- Antet de grup (Muncă / Personal): `0.75rem`, `text-transform: uppercase`, `letter-spacing: 0.05em`, `color: var(--text-secondary)`, cu iconiță `13px` și contorul în `var(--font-mono)`.
- **Rând de task:** `min-height: 46px; padding: 0 12px; border-radius: var(--radius-sm); gap: 12px`. Separator de `1px` în `var(--border)` poziționat absolut sus, doar de la al doilea rând. Hover: `background: var(--bg-elevated)` + apar acțiunile.
  - Mâner de tragere `16px`, opacitate 0 → 1 la hover.
  - Cerc de bifare `18px`, `border: 1.5px solid`, culoarea: `var(--danger)` dacă termenul e depășit, `var(--accent)` dacă e azi, `var(--border-strong)` altfel.
  - Titlu `0.9375rem`, `font-weight: var(--w-row)`, cu elipsă; context `0.8125rem var(--text-dim)`.
  - Indicator de subtaskuri: inel SVG de `12px` + „gata/total" cu `font-variant-numeric: tabular-nums`.
  - Acțiuni la hover (Mâine / Altă zi / Scoate): `height: 32px`, `border-radius: var(--radius-xs)`, `opacity` + `translateX(8px)` cu `.22s var(--ease)`.
  - Termenul, la dreapta: lățime fixă `46px`, `var(--font-mono)`, `0.75rem`, `tabular-nums`; `var(--danger)` la depășire, altfel `var(--text-dim)`.

### 2. Acasă — telefon (`design/Ecran Acasa Telefon.dc.html`)

Referință de viewport: **428 × 932** (Honor Magic 6 Pro).

- **Antet:** `min-height: 56px; padding: 4px 16px`, suprafață de sticlă (straturi 1 + 3, plus `box-shadow: inset 0 -1px 0 var(--border)` în loc de ramă completă — e lipit de marginea de sus). Marca `42 × 42 px` în stânga, fără text; căutare și temă ca butoane rotunde `40px` în dreapta.
- **Linia de ieșiri:** un singur rând (`flex-wrap: nowrap`) — cardul de deplasare `flex: 1 1 auto; min-width: 0` cu descrierea trunchiată și perioada la capăt, plus cipul compact de severitate „N neînchise" `flex: none`.
- **Panoul „Astăzi":** identic ca reguli, titlu `1.75rem`, rânduri `min-height: 52px`, cerc de bifare `20px`, ținte de minim `44px`.
- **Dock plutitor:** `position: absolute; left: 12px; right: 12px; bottom: 6px`, `border-radius: 30px`, `padding: 5px`, suprafață de sticlă completă (toate cele 4 straturi).
  - 5 elemente `flex: 1 1 0; min-height: 56px; border-radius: 24px`, iconiță `22px` + etichetă `0.6875rem`.
  - Activ: `color: var(--text)`, `font-weight: 600`, `background: var(--glass-fill)`, `box-shadow: var(--glass-sel)`. Inactiv: `color: var(--text-dim)`, `font-weight: 500`.
  - Separator vertical de `1px` (`var(--border-strong)`, `opacity: .5`, `margin: 12px 5px`), apoi **acțiunea principală „+"**: buton rotund `48px`, `background: var(--fab-bg)`, `color: var(--accent-text)`, `box-shadow: var(--fab-rim), var(--fab-glow)`, `transform: scale(.94)` la apăsare.
  - Butonul „+" a fost **mutat din colțul ecranului în dock** ca să nu mai acopere ultimul rând din listă.
- Distanțier de `var(--dock-space)` (128px) la finalul conținutului, ca ultimul rând să nu rămână sub dock.

---

## Interactions & Behavior

| Interacțiune | Comportament |
|---|---|
| Pointer peste bară / dock | Reflex specular care urmărește cursorul; apariție instant, stingere `.35s var(--ease)` la ieșire |
| Hover pe rând de task | `background: var(--bg-elevated)` (`.22s`), apar acțiunile (`opacity` + `translateX`), apare mânerul de tragere |
| Hover pe element de navigație | `color: var(--text)`, `.12s` |
| Apăsare pe „+" | `transform: scale(.94)`, `.16s var(--ease)` |
| Comutator de temă | Schimbă `data-theme` pe rădăcină între `dark` și `light` |
| Derulare | Conținutul trece **pe sub** bară și pe sub dock — de aceea sunt translucide |

### Acțiunea „+" e contextuală

Butonul stă în același loc pe toate paginile, dar ce creează depinde de pagina activă. Etichetă (`aria-label` + `title`):

| Pagină | Etichetă |
|---|---|
| Acasă | Adaugă task pentru azi |
| Taskuri | Adaugă task |
| Plan | Planifică o zi |
| Calendar | Adaugă în calendar |
| Mai mult | Adaugă |

Pe paginile unde crearea nu are sens (ex. Calculator) butonul se ascunde.

## State Management

Prototipurile sunt statice; starea reală vine din aplicație. Ce e nevoie pentru redare:

- `tema: 'dark' | 'light'` — persistată, aplicată ca `data-theme` pe rădăcină.
- `paginaActiva` — determină elementul activ din navigație **și** acțiunea „+".
- Lista de taskuri, grupată (Muncă / Personal), fiecare cu: titlu, context, termen, delta în zile față de azi (`k`), subtaskuri gata/total.
  - `k < 0` → inel și termen în `var(--danger)`; `k === 0` → inel în `var(--accent)`; altfel `var(--border-strong)`.
- Următoarea deplasare + numărul de perioade neînchise și de proiecte fără perioadă.
- `--mx` / `--my` / `--spec` — stare pur vizuală, ținută direct pe element, **nu** în store (altfel se re-randează la fiecare mișcare de mouse).

Formatarea termenelor și pragurile de severitate există deja în `lib/formatters.js` (`dueRing`) și `lib/grupare.js` (`etichetaTermenScurt`) — se refolosesc ca atare.

## Assets

| Fișier | Ce e | Unde se folosește |
|---|---|---|
| `assets/torqa-app-icon.svg` | Iconița de aplicație, `viewBox 0 0 64 64`, exportată la 512px | Ecran de start, favicon, store. Scalabilă la orice mărime; la sub ~32px se recomandă o variantă fără caroiaj |
| `assets/torqa-logomark.svg` | Doar semnul, `stroke="currentColor"` | Bara aplicației, documente, orice context monocrom |

**Semnul** e o sinusoidă de o perioadă înscrisă într-un cerc — simbolul de sursă alternativă. Trecerile prin zero cad exact pe axa orizontală (x = 20, 32, 44), vârfurile la mijlocul fiecărei semiperioade, amplitudini egale sus și jos (punctele de control sunt la 4A/3, deci vârful atinge exact amplitudinea, nu o aproximează). Cercul: rază 18, grosime 5. Sinusoida: grosime 4.2.

**Iconița de aplicație** adaugă în spate o „planșă de schițe": corp cu gradient vertical (`#1b1b30` → `#3f3f66` la 55% → `#7878a6`), caroiaj de 4 unități, axe punctate, repere de colț, iar semnul deasupra într-un gradient metalic (`#ffffff` → `#e6e6f2` → `#b6b6d0`) cu umbră proprie. **Această construcție rămâne doar iconiță de aplicație** — în interiorul aplicației se folosește numai marca, altfel arată ca un corp străin în interfață.

Alte explorări de semn (punte de invertor, legătură DC, convertor, modulație) sunt în `design/Iconita TORQA.dc.html`, dacă e nevoie de o familie de iconițe mai târziu.

Fonturile (Gabarito variabil, DM Mono 400/500) există deja în `frontend/static/fonts/`.

Iconițele de navigație sunt path-urile din `components/ui/SolidIcon.svelte`, nemodificate. Restul sunt Lucide outline la `stroke-width: 1.5`.

## Files

```
design/
  Ecran Acasa.dc.html          — desktop, prototip complet
  Ecran Acasa Telefon.dc.html  — telefon 428×932, prototip complet
  tokens-variante.css          — setul de tokenuri (sursa tabelelor de mai sus)
  Iconita TORQA.dc.html        — explorări de iconiță; varianta adoptată e 7d
  support.js                   — runtime-ul prototipurilor (nu se copiază în aplicație)
assets/
  torqa-app-icon.svg
  torqa-logomark.svg
```

Corespondența cu sursa: `pages/Home.svelte`, `components/UrmatoareaIesire.svelte`, `components/TodayBoard.svelte`, `components/layout/Header.svelte`, `components/layout/Dock.svelte`, `components/ui/SolidIcon.svelte`, `components/ui/ContorPasi.svelte`, `styles/tokens.css`, `styles/global.css`.

## Ordinea recomandată de implementare

1. Transcrie tokenurile în `tokens.css` (ambele teme). Aplicația trebuie să arate corect încă de aici, cu dockul pe poziția veche.
2. Adaugă utilitarul de sticlă (stiva de 4 straturi) ca o componentă Svelte reutilizabilă și aplic-o pe `Header.svelte` și `Dock.svelte`.
3. Mută navigația în bara de sus pe desktop; păstrează dockul jos pe telefon și fă-l plutitor.
4. Mută „+" în dock și fă-l contextual.
5. Înlocuiește marca; adaugă iconița de aplicație.

---
description: Sistemul de design — culoare, tipografie, mișcare, componente. Se încarcă doar când atingi frontendul.
paths:
  - "frontend/src/**/*.svelte"
  - "frontend/src/**/*.css"
  - "frontend/src/**/*.js"
---

# Design system

Sursa unica: `frontend/src/styles/tokens.css` — **citeste-l inainte sa atingi CSS**. Estetica:
AURORA („sticla cu muchie-lentila", 2026-08-23) — carbune si un liliac rece, doua teme
(dark implicit + light), amandoua in tokens. Handoff: `design/handoff-aurora/`.

- **Suprafete:** `--bg` < `--bg-surface` < `--bg-elevated`. Elevatia se citeste din umbra, nu
  din chenare peste tot.
- **STICLA e permisa, dar DOAR pe barele de navigatie** (`BaraSus`, `Header`, `Dock`) —
  acolo continutul chiar trece pe dedesubt, si de-aia sunt translucide. NU e o textura de
  imprastiat pe carduri. Se pune cu `use:sticla` (`lib/sticla.js`) plus clasa `.sticla`;
  regulile stau in `global.css`, fiindca straturile se creeaza la RULARE si Svelte TAIE din
  build regulile ale caror selectoare nu le gaseste in markup. Volumul vine din MUCHIE
  (`--glass-edge`, decupata cu `mask-composite`), nu dintr-o spalare peste suprafata —
  `--glass-sheen` e `none` cu buna stiinta. Blurul NU coboara sub ~20px fara reverificarea
  contrastului. `--bar-bg`/`--dock-bg` sunt rezerva cand `backdrop-filter` lipseste.
- **Culoarea e stare, nu decor. UN accent** (`--accent`, liliac rece). Text pe tenta ia intotdeauna
  varianta `-deep`. `--warning`/`--info`/`--purple`/`--service-*` sunt **aliasuri** — nu
  introduce o a treia stare. Pe randurile de task culoarea e rezervata **severitatii**
  (inelul bifei + textul termenului, amandoua din `--ring`, pus cu `dueRing()`).
  **Muchia colorata de 3px nu mai exista nicaieri.**
- **Tipografie — cinci trepte, doua familii:** Gabarito (tot textul), DM Mono (cifre care se
  compara pe verticala). `--font-title` 25 · `--font-h2` 21 · `--font-h3`=`--font-body` 15 ·
  `--font-small` 13 · `--font-label` 12. **Nu exista 14px.** Nimic scris de mana:
  `font-size`, `letter-spacing`, `line-height` in afara `tokens.css` sunt abateri.
  Greutatile au si nume de ROL, din AURORA: `--w-title` (600, cu `--ls-title` -0.02em),
  `--w-row` si `--w-ctrl` (500).
- **Raza — patru trepte:** `--radius-xs` e **PASTILA** (999px: cip si control mic),
  `--radius-sm` 14 (rand si camp), `--radius-md` 24 (suprafata), `--radius-lg` 30 (dock si
  foaie), cerc doar bifa. `--radius-celula` (8px) e o exceptie cu motiv scris — reperul zilei
  selectate din Calendar trebuie sa ramana DREPTUNGHI, altfel se citeste ca bifa unui task.
- **Miscare — patru durate, trei curbe** (verifica in tokens, nu din memorie):
  `--dur-press` .09 · `--dur-base` .22 · `--dur-slow` .28 · `--dur-fast` .12 (vopsea, nu
  miscare); `--ease` la SOSIRE, `--ease-iesire` la PLECARE (accelereaza, nu franeaza —
  ce pleaca nu mai e urmarit), `--ease-spring` cand ceva urmareste degetul, `--ease-arc` /
  `--ease-arc-elan` pentru arcele lungi. NU `transition: all` — foloseste
  `--transition-colors` sau `--transition-pressable`. Doar `transform`/`opacity` in animatii.
- **Componente:** `components/ui/` — `<Input>`, `<Textarea>`, `<Select>`, `<DatePicker>`
  (NU `type="date"`), `<Modal>`, `<Toast>`, `<EmptyState>`, `<ErrorState>`, `<Skeleton>`
  (DOAR la prima incarcare), `<SelectorZi>`. Numaratorile folosesc `.count` din `global.css`.
- **Tinte touch:** `--tap-min` 44px. Control nou = da-i `:active`.
- **Navigatie:** desktop (>768px) = `BaraSus.svelte`, bara de sticla care PLUTESTE sus
  (14px/18px), peste care trece continutul; rezerva de sus o tine `--bara-h`, MASURATA.
  Telefon = `Header.svelte` (sus, lipit) + `Dock.svelte` (jos, plutitor la 6px + safe-area).
  Niciodata amandoua: fiecare scrie `--dock-h` pe `<html>`, iar bara scrie si `--sidebar-w: 0`
  (coloana nu mai exista, dar tokenul ramane fiindca cinci locuri isi socotesc pozitia din el).
  Tenta rutei active e `.pilula` — UN obiect care ALUNECA, masurat de `audit_navigare`; nu se
  picteaza pe slot.
- **Actiunea „+" e a DOCULUI**, nu a paginii: pagina declara ce creeaza, cu
  `inregistreazaActiune()` din `lib/actiuneNoua.svelte.js`; dockul o deseneaza (`.dock-fab`).
  Unde nu se inregistreaza nimeni, butonul nu exista. `.dock-item` ramane doar pentru
  sloturile de NAVIGATIE — `audit_mobil` numara exact cinci.
- **Marca** e semnul AURORA: o sinusoida de o perioada inscrisa intr-un cerc (trecerile prin
  zero la x = 20, 32, 44; cerc raza 18 grosime 5, unda grosime 4.2). In interfata ia
  `--accent`, deci urmeaza tema. Canonic: `design/handoff-aurora/assets/torqa-logomark.svg`.
  Iconita de aplicatie (planseta cu caroiaj si gradient) e ALT obiect si ramane doar iconita —
  in interfata s-ar citi ca un corp strain.
- **Inainte de commit:** `python scripts/lint.py` (secunde — prinde regula CSS taiata din
  build, `let` citit in markup care nu redeseneaza, import care nu se rezolva),
  `python scripts/audit_design.py` (coerenta — build-ul trece vesel peste o a doua paleta
  copiata) **si** `python scripts/audit_contrast.py` (contrastul, pe amandoua temele —
  obligatoriu la orice atingere a unei culori din `tokens.css`).

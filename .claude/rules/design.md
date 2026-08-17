---
description: Sistemul de design — culoare, tipografie, mișcare, componente. Se încarcă doar când atingi frontendul.
paths:
  - "frontend/src/**/*.svelte"
  - "frontend/src/**/*.css"
  - "frontend/src/**/*.js"
---

# Design system

Sursa unica: `frontend/src/styles/tokens.css` — **citeste-l inainte sa atingi CSS**. Estetica:
otel pe hartie, doua teme (dark implicit + light), amandoua in tokens.

- **Suprafete:** `--bg` < `--bg-surface` < `--bg-elevated`. Elevatia se citeste din umbra, nu
  din chenare peste tot; `backdrop-filter` e scos din sistem.
- **Culoarea e stare, nu decor. UN accent** (`--accent`, otel). Text pe tenta ia intotdeauna
  varianta `-deep`. `--warning`/`--info`/`--purple`/`--service-*` sunt **aliasuri** — nu
  introduce o a treia stare. Pe randurile de task culoarea e rezervata **severitatii**
  (inelul bifei + textul termenului, amandoua din `--ring`, pus cu `dueRing()`).
  **Muchia colorata de 3px nu mai exista nicaieri.**
- **Tipografie — cinci trepte, doua familii:** Gabarito (tot textul), DM Mono (cifre care se
  compara pe verticala). `--font-title` 25 · `--font-h2` 21 · `--font-h3`=`--font-body` 15 ·
  `--font-small` 13 · `--font-label` 12. **Nu exista 14px.** Nimic scris de mana:
  `font-size`, `letter-spacing`, `line-height` in afara `tokens.css` sunt abateri.
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
- **Inainte de commit:** `python scripts/audit_design.py` — singurul test care prinde
  incoerenta (build-ul trece vesel peste o a doua paleta copiata).

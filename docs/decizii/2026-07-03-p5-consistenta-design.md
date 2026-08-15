# 2026-07-03 — P5 consistență design (parțial, vizibil)

- **2026-07-03 — P5 consistență design (parțial, vizibil)** (SW v73): unificat iconografia mixtă —
  înlocuit glifele Unicode cu Lucide/SVG: `≔`→`ListTodo`, `!`→`AlertTriangle` (Tasks), `◔`→`CalendarDays`
  (AgendaColumn), `◳`/`⟳`→`Zap`/`Wrench` (tip-chip PIF/Service în Projects), `&times;`→`<X>` (Modal close).
  Nou token `--radius-chip: 7px` (consolidează radiile ad-hoc 7/8px pe `.ico` + `.tip-chip`). Verificat
  Playwright: `.ico svg`/`.tip-chip svg`/`.ico-vio svg` prezente, 0 erori. **Deliberat amânat** (refactor
  intern, zero payoff vizual, risc de regresie pe 6 search-box-uri funcționale): componentele comune
  `SearchPill`/`CountBadge`/`DropdownMenu`. Rămâne oportunist.

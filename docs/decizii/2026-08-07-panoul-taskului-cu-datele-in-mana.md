# 2026-08-07 — Panoul taskului se deschide cu datele in mana, nu inainte

- **2026-08-07 — Panoul taskului se deschide cu datele in mana, nu inainte.**
  Ion: „partea din al doilea screenshot apare mai tarziu taiat". Cauza: `expandedTask`
  se seta INAINTE de `await loadSubtasks`, deci `slide` masura inaltimea starii
  „Se încarcă…" — iar `slide` masoara O SINGURA DATA, la primul cadru. Sectiunea de
  subtaskuri, sosita dupa aceea, nu incapea in tinta si se vedea taiata pana cand
  tranzitia se termina si inaltimea sarea la loc. Un gest, doua evenimente vizuale.
  Fix: intai `await incarcaSubtaskuri`, apoi `expandedTask = id` (idem `deschideFoaia`
  pe telefon), plus preincarcare pe `pointerenter` (desktop) cu harta `inZbor` — fara
  ea, plimbatul mouse-ului peste lista ar putea manca limita de 60 cereri/minut.
  Ramura „Se încarcă…" a fost SCOASA din ambele pagini: nu se mai poate randa.
  Tranzitia noua `desfacere` (lib/motion.svelte.js) strange TOT ce ocupa spatiu
  vertical — inaltime, padding, margini SI ambele rame — fiindca panoul din
  ProjectDetail are rama pe patru laturi si `margin-bottom`; `slide` pe inaltime
  singura lasa ~13px care apar dintr-un cadru. Masurat dupa: o singura inserare in
  DOM, `scrollHeight` constant tot timpul animatiei, 0 → 283px in ~240ms.

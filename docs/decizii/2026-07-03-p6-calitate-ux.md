# 2026-07-03 — P6 calitate/UX

- **2026-07-03 — P6 calitate/UX** (SW v72): (1) **ErrorState + retry** pe listele care înghiteau
  erorile → fals „empty": `Tasks.svelte` (pe `globalTasks.error`), `Params.svelte` (nou `curError`
  derivat din `params.error`/`faultCodes.error`; adăugat `faultCodes.error` în store). ProjectDetail
  avea deja. (2) **Undo-toast** — infrastructură nouă în `stores/ui.svelte.js`: `toastUndo(msg,
  {onUndo, onCommit, duration})` cu semantică *deferred-commit* (scoți optimist din UI, ștergerea
  reală rulează în `onCommit` la expirare/închidere ~6s, „Anulează" apelează `onUndo`). `closeToast`
  (X pe un undo-toast încă nedecis = comite) + `runToastAction`. `Toast.svelte` randează butonul
  `actionLabel` + `aria-live=polite`. Aplicat la **ștergerea subtask-ului** din ProjectDetail (era
  instant fără plasă de siguranță → acum reversibil). Task/atașament păstrează ConfirmDialog-urile
  existente (deja au plasă). (3) **Ctrl+Enter / Ctrl+S salvează** în `RichTextEditor` (prop nou
  `onsave`; Ctrl+S nu mai moare degeaba) — legat în ProjectDetail (câmp + notițe task) și Tasks (notițe).

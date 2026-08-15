# 2026-08-14 — Handoff „interactiuni, modale si miscare" (T1-T17) + audit de UI

- **2026-08-14 — Handoff „interactiuni, modale si miscare" (T1-T17) + audit de UI.**
  Aplicat integral. Ce trebuie tinut minte, fiindca s-a platit scump:
  **(1) `stiva.varf++` chemat dintr-un `$effect` = bucla.** E o CITIRE si o
  scriere a aceleiasi stari reactive, deci efectul se re-porneste singur: la
  `Modal` a iesit `effect_update_depth_exceeded` (si odata cu el a murit Escape
  peste tot), la `DatePicker` o oscilatie tacuta care lasa varful pe o valoare
  gresita. Garda (`untrack`) sta ACUM IN `nivelNou`/`nivelInchis`, nu la
  apelanti — al treilea consumator ar fi uitat-o, si simptomul lui ar fi aratat
  cu totul altfel.
  **(2) `ResizeObserver.contentRect` NU include paddingul.** Dockul are 8+8, deci
  `--dock-h` iesea 56 pentru o bara de 72 — adica exact eroarea pe care T5 o
  repara, doar cu alt numar. Se citeste `borderBoxSize[0].blockSize`.
  **(3) Gestul de pe telefon s-a INTORS (T8).** Decizia din 2026-08-08 („pe
  telefon pista se citeste, nu se manipuleaza") a fost rasturnata: gestul exista
  la deget, dupa apasare lunga, cu banda ridicata si manere de 44px. Sectiunea
  „perioadele se trag" din `audit_mobil.py` a fost intoarsa odata cu el.
  **(4) `.banda.se-trage` trebuie sa stea la FINALUL foii:** `.banda.pregatire`
  si `.banda.facuta` din blocul mobil pun `box-shadow: none` la aceeasi
  specificitate, deci scrisa mai sus era anulata exact pe starile mutate cel mai
  des. Un `@media` nu adauga specificitate.
  **(5) Capcana de test:** proba de mutare din `audit_mobil` alegea prima banda
  din DOM. Cand aceea apartine unui proiect INCHIS, mutarea reuseste dar
  `/api/calendar` o taie la `data_finalizare` (v35) — deci proba raporta „NU s-a
  mutat" exact cand se mutase. Alege acum o banda de pe un proiect deschis.
  **(6) Rebranding TORQA + marca „Unda"** (semnal PWM, `M10 42 H21.5 V22 H32 V42
  H42.5 V22 H54`, viewBox 64, tile rx 14). `appId` RAMANE `org.iupif.pif` — un
  appId nou = aplicatie noua pe telefon, cu notificarile vechi ramase in urma.
  Iconita de notificare ramane VECTOR (`ic_stat_torqa.xml`), nu PNG-uri per
  densitate. `audit_design.py` are patru reguli noi (R8-R11).
  **De decis cu Ion (raportat, NEaplicat):** accentul de tema DESCHISA cade sub
  AA in ambele roluri (`--accent` ca text 4,15/3,80; `--accent-text` pe fill
  4,15) — singurul rol din sistem care cade, si numai pe tema pe care o folosesti
  in hala.

# 2026-07-31 — Dock-ul pe telefon: tinte de 56px si ascundere la derulare

- **2026-07-31 (3) — Dock-ul pe telefon: tinte de 56px si ascundere la derulare,
  ca bara de adresa.** Ion: „sensul era sa le faci si putin mai mari iconitele din
  dock acum, tinand cont de spatiul aparut" + „poti sa faci cu autohide dockul pe
  principiul cum e la browser autohide la bara de cautare".
  **Marime:** tinta 44 -> **56px**, iconita 20 -> **24px**, cu `gap: 4px` si
  separatorul INAPOI (fusesera scoase doar fiindca opt tinte nu incapeau). Socoteala
  pe cel mai ingust telefon testat (360px): `5×56 + 4×4 + 12 = 308px` din 348. Pragul
  CSS e 768px, acelasi cu cel care decide ca sunt cinci — doua praguri diferite ar da
  o latime la care ai opt iconite marite si dock-ul iese din ecran.
  **Ascundere la derulare:** cobori -> pleaca, urci -> revine IMEDIAT (fara prag de
  revenire: cand vrei navigatia, o vrei acum). Sus (<60px) si la capatul paginii sta
  mereu afara. Prag de 8px acumulati, iar `ultimY` NU se actualizeaza sub prag, ca un
  gest lent sa se adune in loc sa fie ignorat la nesfarsit. Deplasarea de ascundere e
  proprie telefonului: cea de desktop (`100% + 6px`) e calibrata sa lase manerul
  afara, dar pe telefon manerul e `display: none`, deci ar ramane o dunga de dock
  peste continut.
  **ASTA INLOCUIESTE regula veche „pe mobil dock FIX, fara autohide"** (tot cerinta
  lui Ion, dar mai veche). Comentariul din cod o spune explicit, ca sa n-o „repare"
  cineva inapoi.
  **BUG-UL DE REACTIVITATE, meritat de retinut:** prima varianta pastra `hidden` ca
  `$state` setat dintr-un `apply()`. Efectul care readuce dock-ul la schimbarea rutei
  chema `apply()`, iar `apply()` CITEA `scrollHidden` — deci efectul devenea dependent
  de el si il stingea imediat ce se aprindea. Dock-ul nu se ascundea NICIODATA, cu
  build verde si zero exceptii. Reparat facand `hidden` `$derived`: fara „cine cheama
  recalcularea" nu mai exista cerc. `isMobile` se citeste acum si el imediat, nu dupa
  montare, ca dock-ul sa nu porneasca ascuns si sa sara la vedere dupa primul paint.
  **Regresie acoperita:** sectiune noua `dockul_pe_telefon` in `audit_mobil.py` (7
  verificari). Ruleaza pe **Calculator**, nu pe Taskuri: cu baza de test lista de
  taskuri incape intr-un ecran, deci nu exista derulare de masurat si prima varianta a
  testului „trecea" degeaba. Verificat prin injectarea ambelor regresii (ascunderea
  dezactivata + deplasarea de desktop): pica exact cele doua randuri asteptate.
  **Capcana de mediu, a doua oara:** pe langa `PIF_RATE_LIMIT` (60/min pe `/api/*`)
  exista un limitator SEPARAT si neconfigurabil pe login — `LOGIN_LIMIT = 5` incercari
  la `LOGIN_WINDOW = 300s`, in memoria procesului. De aici 429-urile care se prezinta
  drept „PIN incorect". Pentru teste: logheaza-te O DATA si refoloseste
  `storage_state`, sau porneste un server nou (contorul e per proces).
  Verificat: `audit_design` curat, `smoke_ui` 28/28, `audit_mobil` complet OK
  (inclusiv cele 7 noi), `test_suite` 12/12.

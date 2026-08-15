# 2026-08-15 — MEMORIA SUPRAVIETUIESTE REPORNIRII (local-first)

- **2026-08-15 — MEMORIA SUPRAVIETUIESTE REPORNIRII (local-first).** Ion, dupa
  patru runde: „la pornirea paginilor, mai ales se vede la calendar, apare un
  schelet si dupa foarte rapid apare pagina", si „daca am o trimitere catre
  calendar si dau click de pe acasa sau din planificator".
  - Tot ce se facuse pana aici ajuta doar cand raspunsul era in memoria FILEI.
    Patru drumuri o ocolesc, si le nimerise pe toate: deschiderea aplicatiei (pe
    Android se deschide pe ultima ruta), un F5, `navigate()` chemat de mana (din
    afara actiunii `link`), si o trimitere cu parametru (`#/calendar?zi=…`, alt
    URL). Nu masurasem niciodata incarcarea LA RECE pe o ruta.
  - `lib/cache.js` se hidrateaza acum SINCRON din `localStorage` la incarcarea
    modulului. `localStorage`, nu IndexedDB, tocmai fiindca e sincron: IndexedDB
    n-ar fi gata la primul cadru. Pretul (scriere care blocheaza) se plateste
    amanat, pe `requestIdleCallback`, cu plafon de 600 KB si vechime de 7 zile.
  - **Masurat: Proiecte 984ms → 25ms, Planificator 791 → 37, Calendar → 26.**
  - `navigate()` preincarca si el, nu doar actiunea `link`: jumatate din
    navigarile aplicatiei il cheama de mana (cardul de proiect, banda din
    Planificator catre `#/calendar?zi=…`, paleta).
  - **Intarzierea de 110ms de pe `Skeleton` a fost o reparatie GRESITA si a fost
    scoasa.** Rezolva clipirea de un cadru, dar cand asteptarea chiar exista
    ADAUGA o stare: rama la 611ms, scheletul la 727 (dupa cele 110), continutul
    la 800. Reparatia adevarata era la date, nu la schelet.
  - `.asteptare` (nou, `global.css`): starea de asteptare SOSESTE, ca pagina —
    pe INVELIS, nu pe fiecare dunga, altfel patru dungi sosesc separat.
  - **Doua capcane de scris testul, amandoua m-au pacalit intai:** `goto` catre
    acelasi URL cu acelasi hash NU creeaza document nou (deci a doua masuratoare
    o repeta pe prima, cu timpi identici la milisecunda — arata exact ca „nu
    merge"); si scrierea pe disc fiind amanata, intre incarcari trebuie lasat
    timp. Reincarcarea se face cu `reload()`.
  - Al treilea bug gasit pe drum: Calendarul punea datele din cache dar NU stingea
    `loading` (care porneste `true`), deci scheletul acoperea grila deja desenata.
  - Regresia: `audit_navigare.py` sectiunea 9. Contractul nu e „zero cadre de
    asteptare" — la o reincarcare adevarata chunkul trebuie adus — ci
    **continutul pe ecran sub 300ms**.

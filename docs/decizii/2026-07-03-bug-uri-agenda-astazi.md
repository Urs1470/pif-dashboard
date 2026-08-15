# 2026-07-03 — 2 bug-uri agenda „Astăzi" (raportate de Ion)

- **2026-07-03 — 2 bug-uri agenda „Astăzi" (raportate de Ion)** (SW v74): (1) **Deadline nu se muta
  la amânare** — un task cu `data_scadenta`=azi apare în agendă (clauza due-today din `_AGENDA_WHERE`).
  Amânarea din agendă seta doar `data_planificata`, lăsând deadline-ul în trecut → task veșnic restant.
  Fix în `stores/agenda.svelte.js`: `moveToDate`/`moveToTomorrow` acceptă `opts.data_scadenta` și mută
  ȘI `data_scadenta` pe noua zi. **v75 (cerut de Ion):** deadline-ul existent se mută ÎNTOTDEAUNA la
  reprogramare (apropiat sau îndepărtat) — nu doar când e ≤ azi — fiindcă noua dată reflectă când crede
  că se poate face. Taskurile FĂRĂ deadline rămân fără (nu inventăm termen din simpla planificare).
  TodayBoard paseaza `{data_scadenta: it.data_scadenta}` la onTomorrow/onMoveDate. Verificat E2E: task
  due-azi → amânat +9z → `data_scadenta` mutat, iese din azi, pe ziua-țintă e scadent nu restant.
  (2) **Bifarea în „Astăzi" nu updata cardul „urgente"** până la refresh/schimbare tab — TodayBoard
  (store `agenda`) și cardul urgente (`dashboard.urgent_tasks` din `/api/dashboard/home`) sunt surse
  separate. Fix: TodayBoard primeste prop `onchange`; Home îl leagă la `loadDashboard(true)` (reload
  **silent** — fără skeleton pe toată pagina). Efectul de animație KPI acum face *snap* la reload-urile
  ulterioare (nu reanimă de la 0, dar actualizează cifra). `onchange()` apelat după toggle/tomorrow/
  remove/moveDate/quickAdd. Verificat Playwright: bifez task urgent în agendă → dispare din card fără refresh.

# 2026-08-10 — Integrarea Google Calendar a plecat de tot (v40)

- **2026-08-10 — Integrarea Google Calendar a plecat de tot (v40).** Ion:
  „sterge integrarea google calendar." Intai butonul si modalul din /tasks, apoi
  serverul: `blueprints/google_calendar.py` (554 linii, 6 rute), inregistrarea
  din `app.py`, si cele PATRU situri de sincronizare — `tasks.py` la creare /
  editare / stergere de task global si `push.py` la actiunea de pe notificare.
  Toate treceau prin `spawn_sync`, care decidea singur upsert vs. delete.
  **Migrarea v40 sterge cheile `google_*` din `app_settings`, si asta e partea
  care conteaza:** filtrul anti-scurgere din `admin.py` (`CHEI_PROTEJATE`) le
  excludea din backup; odata relaxat la doar `push_`, un `google_refresh_token`
  ramas ar fi INCEPUT sa curga in JSON-ul de backup, care se descarca in browser.
  Deci: sterge randurile intai, relaxeaza filtrul dupa.
  Ce NU s-a atins: feedul `.ics` (`/api/export/ics` + `ics_feed_key`) — abonare
  prin URL, fara OAuth, merge in orice calendar; si `fonts.googleapis.com` din
  CSP (Google Fonts, nu integrarea). Zero pachete de sters din `requirements.txt`
  (integrarea era stdlib pura), zero coloane orfane (`google_event_id` n-a
  existat — id-ul se derivase determinist din UUID).
  Cioturi curatate in acelasi pas: `gcal_reminders_check` din `test_suite.py`
  (importa `_event_body` din modulul sters — ar fi picat poarta statica la
  prima rulare), `google_sync_test` (pasul lui 7, proba ca backupul nu scurge
  secrete, a devenit `backup_secrete_test`, doar pe `push_`), 14 clase CSS
  orfane `.g-*` din `Tasks.svelte` — restul (`.g-ico`, `.g-punct`, `.g-text`…)
  raman, le foloseste fereastra de notificari — si `.g-actiuni`, clasa din
  markup care n-avea nicio regula (perechea ei se numea `.g-actiune`).

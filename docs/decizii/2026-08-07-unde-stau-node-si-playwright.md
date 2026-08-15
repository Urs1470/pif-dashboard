# 2026-08-07 — Unde stau Node si Playwright pe masina asta

- **2026-08-07 — Unde stau Node si Playwright pe masina asta (m-au pacalit o data).**
  `node` NU e in `Program Files` si nu e in PATH-ul procesului: e portabil, la
  `C:\Users\Ion Ursu\Tools\node-v24.19.0-win-x64`, inscris doar in PATH-ul de
  UTILIZATOR din registru — deci un shell pornit mai devreme nu-l vede. Se
  prefixeaza manual: `$env:PATH = "C:\Users\Ion Ursu\Tools\node-v24.19.0-win-x64;" + $env:PATH`.
  Playwright NU e in Python-ul de sistem, e in `venv\Scripts\python.exe` din
  repo, cu Chromium deja descarcat in `%LOCALAPPDATA%\ms-playwright`. Deci
  `smoke_ui`/`audit_mobil` se ruleaza cu `venv\Scripts\python.exe`, nu cu `python`.
  **Baza locala `pif_dashboard.db` exista dar e GOALA** (schema, zero randuri):
  `smoke_ui` raporteaza „0 proiecte de verificat" si trece pe langa orice ramura
  care are nevoie de date. Pentru benzi/taskuri trebuie insamantata o copie.
  `test_suite.py` cere separat un server LIVE pe 5000 si `PIF_DASHBOARD_PIN` in
  mediu — fara ele da 4 esecuri care n-au nicio legatura cu codul.

# 2026-08-07 — Poarta de verificare dadea un verdict FALS pe masina asta

- **2026-08-07 — Poarta de verificare dadea un verdict FALS pe masina asta.**
  `.claude/hooks/gate.py` pica pe „build" cu „npm nu exista in PATH", desi
  `npm run build` merge. TREI cauze in lant, fiecare descoperita dupa ce era
  reparata cea dinainte — toate reparate:
  (1) `npm()` folosea `shutil.which`, care vede doar PATH-ul MOSTENIT de proces —
  iar Node-ul e portabil si sta doar in PATH-ul persistent din registru, adaugat
  dupa ce aplicatia pornise. Acum, la esec, se cauta si in PATH-ul din registru
  (`cai_persistente`, HKCU + HKLM).
  (2) Verificatoarele porneau cu `sys.executable`, adica Python-ul de sistem —
  care n-are nici flask, nici playwright. Build-ul era doar PRIMA poarta atinsa;
  `smoke_ui` si `audit_mobil` ar fi picat imediat dupa, cu ModuleNotFoundError.
  Acum se prefera `venv/Scripts/python.exe` (`python_probe`), cu cadere pe
  `sys.executable` daca venv-ul lipseste. Si linia „Reproduci cu:" arata
  interpretorul chiar folosit, nu `python`.
  (3) Gasit npm, build-ul tot pica: `'"node"' is not recognized`. `npm.cmd` e un
  SHIM care cheama `node` din PATH, iar procesul copil mostenea tot PATH-ul vechi.
  `mediu_probe()` pune acum directorul lui npm in FATA lui PATH pentru copii.
  **Proba:** `gate.ruleaza()` chemat direct dintr-un shell fara npm mostenit —
  audit_design, build, smoke_ui si audit_mobil trec toate patru.
  **De ce conteaza:** o poarta care da rosu fara sa fi rulat nimic te invata s-o
  ignori — si atunci nu mai prinde nici esecurile adevarate, care sunt tot rostul ei.

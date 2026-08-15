# 2026-08-14 — „APK-ul e semnat" NU inseamna „e semnat cu cheia buna"

- **2026-08-14 (2) — „APK-ul e semnat" NU inseamna „e semnat cu cheia buna".**
  `apksigner verify --print-certs` spune doar CA e semnat. Autoritatea e
  `$AMPRENTA` din `scripts/build-apk.ps1`, care compara amprenta certificatului
  cu cea pinuita — si build-ul de release PICA daca nu se potriveste. Eu am
  sarit peste ea (iesirea PowerShell era goala, am dedus reusita din faptul ca
  fisierul APK exista) si era sa livrez un APK nesigur de instalat.
  **REZOLVAT in aceeasi zi, decizia lui Ion.** Keystore-ul de pe masina asta
  (`Tools/keys/pif-release.jks`, alias `pif`, din 2026-08-07) contine
  `753182ea…c38ecbf0` — cheia VECHE; cea pinuita pe 2026-08-09
  (`7ea67415…7ab11988`) nu e nicaieri in `keys/`. Cum telefonul ruleaza tot
  aplicatia semnata cu cea veche, Ion a ales sa ramanem pe ea („ca sa nu mai
  reinstalez aplicatia"): `$AMPRENTA` din `build-apk.ps1` s-a intors pe
  `753182ea…`, cu istoricul ambelor rotiri scris langa ea. Build-ul de release
  trece poarta, iar APK-ul se instaleaza peste cel de pe telefon.
  Cheia are acum backup pe Google Drive, in folderul `pif-dashboard`
  (`pif-release.jks` + o nota cu amprenta, unde se pune inapoi si cum se
  verifica). PAROLELE nu sunt in backup — stau in `keystore.properties`, local.
  Nu „repara" pinul ca sa treaca build-ul: el e singurul lucru care opreste un
  release care ar rupe actualizarile pentru totdeauna. Daca se roteste vreodata,
  se roteste cand o reinstalare e acceptata, nu ca sa treaca un build.
  **A doua capcana din aceeasi zona:** `npx cap sync` NU regenereaza iconitele.
  Copierea surselor in `frontend/assets/` nu schimba nimic in APK — trebuie
  `npx capacitor-assets generate --android`, care rescrie `res/mipmap-*`.

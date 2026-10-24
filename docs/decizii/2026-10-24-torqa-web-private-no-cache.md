# 2026-10-24 Torqa web: fișierele care se reverifică sunt `private, no-cache`, iar versiunea nouă o aduce service worker-ul

Ion apăsa Ctrl+Shift+F5 ca să vadă un build nou al Torqa web. Cererea lui (observația 19, runda a doua).

- **Cauza (din cod, nereprodusă într-un browser).** Service worker-ul Angular răspunde la navigare
  cu build-ul instalat și abia apoi, în fundal, cere `ngsw.json` și descarcă build-ul nou
  (`ngsw-worker.js`, `handleFetch`: verificarea e programată după ce pagina a fost servită). Build-ul
  nou apare deci la a doua reîncărcare, iar o pagină lăsată deschisă nu-l vede deloc. Ctrl+Shift+F5
  trece peste service worker. Serverul nu era vinovat de asta: originea trimite deja `no-cache` pe
  document și pe fișierele nehash-uite și `immutable` pe cele hash-uite (testele din
  `teste/test_torqa_web.py`; proba cu clientul de test, înainte și după).
- **Ce a făcut Cloudflare (măsurat pe productie, 2026-10-24, `curl -sI`).** Pe fișierele pe care le
  socotește cacheabile după extensie, un `Cache-Control` mai scurt decât „Browser Cache TTL" (4 ore,
  implicit; developers.cloudflare.com/cache/how-to/edge-browser-cache-ttl/) e înlocuit cu
  `max-age=14400`: `ngsw-worker.js`, `safety-worker.js`, `assets/themes/torqa.css` și `favicon.ico`
  au ajuns la browser cu `max-age=14400` (`cf-cache-status: REVALIDATED` sau `MISS`), în timp ce
  `ngsw.json` și `manifest.json` (`.json`, `DYNAMIC`) și-au păstrat `no-cache`. Pentru service worker
  nu strică (deducție, nemăsurată: scriptul principal al unui worker se cere cu `no-cache` la
  `updateViaCache: 'imports'`, implicitul, iar fișierele lui sunt verificate pe hash), dar `torqa.css` putea rămâne vechi până la 4 ore într-un browser fără
  service worker.
- **Schimbarea de aici.** `CACHE_REVERIFICA = 'private, no-cache'` în loc de `no-cache` pe document și
  pe tot ce nu e hash-uit; bundle-urile hash-uite rămân `public, max-age=31536000, immutable`.
  Raționamentul: un răspuns `private` nu se ține în cache la margine, deci nu are ce suprascrie;
  browserul îl ține și îl reverifică cu ETag (304), ca înainte. **Neverificat până la deploy:**
  după el, `curl -sI https://pif.iupif.org/torqa/ngsw-worker.js` trebuie să arate `private, no-cache`;
  dacă arată tot `max-age=14400`, a rămas setarea Cloudflare „Browser Cache TTL: Respect Existing
  Headers" (în tabloul de bord, nu în cod).
- **Ce NU s-a adăugat: o rută de versiune.** Nici `GET /api/torqa/web/version`, nici `version.json`:
  service worker-ul știe deja ce versiune are serverul (`ngsw.json`, 44 KB, hash pe fiecare fișier) și
  descarcă ce s-a schimbat, deci o a doua sursă de adevăr ar putea doar să-l contrazică. Contractul cu
  APK-urile instalate rămâne neatins: nicio rută nouă și niciun câmp nou.
- **Clientul** (repo-ul torqa-sp, `TorqaWebUpdateService`): întreabă service worker-ul (`checkForUpdate`)
  când pagina revine în față, când fereastra primește focus și la fiecare 10 minute; când build-ul nou
  e descărcat arată „New version available · Reload". Nu reîncarcă singur, ca să nu piardă un câmp
  pe jumătate scris. Doar web: aplicația Android își are codul web în APK.

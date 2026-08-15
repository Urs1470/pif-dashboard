# Android: fără rețea, barele sistemului, plecarea pe teren (12c/12d/15, 2026-08-08)

- **„Fără rețea" (12c).** `capacitor.config.json` are `server.url`, deci aplicația **e**
  site-ul: fără rețea rămâneai cu pagina de eroare a lui Chrome. `server.errorPath`
  încarcă acum `fara-retea.html`, care vine din **asset-urile aplicației** (Capacitor îl
  servește de pe `https://localhost`), deci nu cere nimic din rețea. Scris de mână, cu
  patru culori copiate din `tokens.css`: foaia aia e în bundle-ul de pe server, adică
  exact lucrul care lipsește.
  - **Nu poate citi `localStorage`-ul aplicației** — alt origin. Ce spune („ultima dată
    văzut", „N notificări programate") vine de la partea nativă, prin `NotificariPif.stare()`.
    Ultima vizită o scrie `MainActivity` dintr-un `WebViewListener`, **filtrat pe adresa
    serverului**: `onPageLoaded` vine și pentru pagina locală de eroare, deci fără filtru
    „ultima dată văzut" ar fi mereu „acum".
  - „Încearcă din nou" cheamă `NotificariPif.reincarca()`, care ia adresa din punte — o a
    doua copie a ei în HTML ar fi cea care rămâne în urmă.
- **Barele sistemului (12d).** `setDecorFitsSystemWindows(false)` + bare transparente +
  `setNavigationBarContrastEnforced(false)` (altfel Android desenează singur un scrim gri,
  adică exact culoarea proprie pe care n-o vrem). Merge doar împreună cu
  `viewport-fit=cover`, care era deja în `index.html` — abia atunci WebView-ul dă valori
  reale în `env(safe-area-inset-*)`, din care ies `--safe-top/bottom`. Iconițele barelor
  comută cu tema sistemului.
- **Alarma exactă se verifică la fiecare pornire** (`MainActivity.onResume`), dar ecranul de
  sistem se deschide **o singură dată per retragere** (`exacte_intrebat`, resetat când
  permisiunea revine): un ecran de sistem care se deschide singur de fiecare dată e o
  capcană, nu un ajutor. Drumul care rămâne mereu la îndemână e caseta din fereastra de
  notificări, cu „Deschide ecranul".
- **Turul 15 — notificarea de plecare pe teren.** Alarmă pe **prima zi** a unei ieșiri cu
  `loc = Site`, **seara dinainte** (18:00 implicit, reglabil), pe canalul propriu
  „Deplasări", **fără butoane** (o plecare nu se bifează, iar un buton care mută planul de
  pe ecranul de blocare e ireversibil de acolo).
  - **Canalul e unitatea pe care o poate opri utilizatorul din Android.** „Nu vreau să mă
    anunțe seara că plec" și „nu vreau taskurile de dimineață" sunt două decizii diferite;
    pe același canal ar trebui luate împreună.
  - **Regula ieșirii trăiește acum într-un singur loc:** `lib/deplasari.js`
    (`grupeazaDeplasari`, cheia `loc|client`). Calendarul o folosește în locul derivării
    lui locale. Scrisă de două ori s-ar fi rupt tăcut — calendarul ar arăta o ieșire,
    telefonul ar suna de două ori. De aici ies gratis cele trei cazuri care **nu**
    declanșează: pregătirea la Sediu, zilele 2…n, și a doua perioadă alipită la același
    `loc|client`.
  - **Fereastra e de 60 de zile, nu 7** ca la dimineți: diminețile se recalculează din
    lista de taskuri, care se schimbă zilnic; o deplasare se pune în calendar cu săptămâni
    înainte și nu se mai schimbă. Alarmele sunt ieftine, tăcerea nu.
  - Al treilea comutator, cu ora lui, e în fereastra de notificări și **nu** intră în regula
    „cel puțin un fel pornit" — aia păzește taskurile. Rândul lui **nu e un `<label>`
    întreg**: eticheta ar prinde și clicul pe selectorul de oră, deci alegerea orei ar
    stinge comutatorul.
  - Prins în aceeași trecere: `zileDeCand` din `notificari.js` returna `ZILE_VECHIME`, o
    constantă **inexistentă în modul** — pe un `created_at` necitibil arunca ReferenceError
    și tăcea toată reprogramarea, nu doar taskul cu data stricată.

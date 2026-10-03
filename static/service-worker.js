// TORQA — service worker-ul interfetei vechi, care se retrage singur.
//
// DE CE ARE ACEST CONTINUT. Pana pe 2026-10-03 fisierul asta era service worker-ul
// dashboardului vechi (SPA-ul Svelte, calculatorul public, notificarile push): tinea in
// cache shell-ul si fisierele din /assets/ si le servea din cache cand reteaua lipsea.
// Interfata a fost retrasa (docs/decizii/2026-10-03-retragerea-interfetei-vechi.md), dar
// browserele care o instalasera au inca acel worker, cu scope `/`, si ar continua sa-i
// serveasca shell-ul vechi din cache. Stergerea fisierului nu retrage nimic: la verificarea
// de actualizare browserul primeste 404 si pastreaza worker-ul vechi. De-aia URL-ul
// ramane, iar continutul lui e acest worker. Browserul cauta o versiune noua a scriptului
// la navigarea intr-o pagina din scope (cel mult o data la 24 de ore), iar interfata veche
// mai cerea si singura, la 15 minute si la revenirea pe fila (`reg.update()` din main.js).
// Browserul il instaleaza peste cel vechi, iar el isi sterge cache-urile, se dezinregistreaza
// si reincarca ferestrele pe care le controla. Dupa asta nu mai ramane niciun worker de
// dashboard.
//
// NU ATINGE TORQA WEB (/torqa/). Torqa are propriul service worker (`ngsw-worker.js`, scope
// /torqa/) si propriile cache-uri (`ngsw:...`). Worker-ul de aici:
//   - nu are handler de `fetch`: nu raspunde la nicio cerere, deci nu poate nici sa serveasca,
//     nici sa puna in cache nimic din Torqa (nici API-ul lui);
//   - sterge doar cache-urile dashboardului vechi, pe prefixele lor, niciodata `ngsw:`;
//   - nu reincarca ferestrele de sub /torqa/.
// Nu are nici handler de `push`: notificarile web au plecat odata cu interfata veche, iar
// dezinregistrarea desface si abonamentul browserului.
//
// Fisierul poate fi sters cand nu mai exista niciun browser cu worker-ul vechi; pana atunci
// nu costa nimic sa ramana. Verificat de teste/js/service-worker.test.mjs.

// Cache-urile dashboardului vechi, dupa prefix. Au fost doua serii in istoria fisierului:
// `pif-static-vN` / `pif-api-vN` (pana la numele Torqa) si `torqa-static-vN` / `torqa-api-vN`.
// Nu se sterge "tot ce nu e ngsw:": doar ce a scris worker-ul vechi.
const PREFIXE_CACHE_VECHI = ['pif-static-', 'pif-api-', 'torqa-static-', 'torqa-api-'];

const CALE_TORQA = '/torqa/';

function esteCacheVechi(nume) {
  return PREFIXE_CACHE_VECHI.some((prefix) => nume.startsWith(prefix));
}

function esteTorqa(adresa) {
  const url = new URL(adresa);
  return url.origin === self.location.origin &&
    (url.pathname === '/torqa' || url.pathname.startsWith(CALE_TORQA));
}

// Preia imediat locul worker-ului vechi, fara sa astepte inchiderea paginilor lui.
self.addEventListener('install', () => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(retrage());
});

// Ordinea conteaza: intai cache-urile, apoi dezinregistrarea, abia la urma ferestrele — o
// fereastra reincarcata inainte de dezinregistrare ar fi controlata iar de acest worker.
// Fiecare pas se apara singur de esec: un cache care nu se sterge nu are voie sa opreasca
// dezinregistrarea, iar o fereastra care refuza navigarea nu le opreste pe celelalte.
async function retrage() {
  try {
    const nume = await caches.keys();
    await Promise.allSettled(nume.filter(esteCacheVechi).map((n) => caches.delete(n)));
  } catch (_) {
    /* fara acces la cache-uri: se dezinregistreaza oricum */
  }

  try {
    await self.registration.unregister();
  } catch (_) {
    /* worker-ul ramane inregistrat, dar fara handlere nu face nimic */
  }

  // Doar ferestrele controlate de acest worker (`includeUncontrolled` ramane fals): pe cele
  // necontrolate `navigate()` oricum e refuzat. Adresa se da FARA fragment: interfata veche
  // tinea ruta in fragment (`/#/tasks`), `client.url` il poarta cand documentul a fost creat cu
  // el, iar redirectul de la `/` il pastreaza — fereastra ar ajunge la `/torqa/#/tasks`, cu ruta
  // interfetei vechi agatata de Torqa. (Chromium reincarca si cu fragment; se scoate pentru
  // destinatie, nu ca sa se produca reincarcarea.)
  try {
    const ferestre = await self.clients.matchAll({ type: 'window' });
    await Promise.allSettled(
      ferestre
        .filter((fereastra) => !esteTorqa(fereastra.url))
        .map(async (fereastra) => {
          const url = new URL(fereastra.url);
          url.hash = '';
          await fereastra.navigate(url.href);
        })
    );
  } catch (_) {
    /* ferestrele ramase se reincarca la urmatoarea navigare */
  }
}

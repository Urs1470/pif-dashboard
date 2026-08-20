// ESTI SAU NU CONECTAT — un fapt, scris o data.
//
// DE CE EXISTA. Service workerul serveste GET-urile din `API_CACHE` (network-first
// cu rezerva), dar sare peste tot ce nu e GET (`service-worker.js`, „Skip non-GET
// requests"). Deci fara semnal aplicatia se deschide, listele sunt acolo, totul
// pare in regula — si abia cand bifezi un task afli, dintr-un toast, ca n-a mers.
// Fiecare actiune esueaza separat, iar `navigator.onLine` nu era citit nicaieri in
// frontend: nimic, in niciun moment, nu spunea ca esti deconectat.
//
// DOUA SURSE, IN ORDINEA INCREDERII.
//   1. O cerere care chiar a picat din retea E dovada. `navigator.onLine === true`
//      inseamna doar „am un adaptor si un IP" — intr-o hala cu Wi-Fi fara iesire,
//      sau pe date mobile cu semnal la o bara, steagul zice `true` si `fetch`
//      pica. De aceea `picat()` bate steagul.
//   2. Evenimentele `online`/`offline` sunt semnalul rapid, si singurul care
//      exista inainte sa apuci sa ceri ceva.
// Reintoarcerea o confirma tot o cerere: `reusit()`, chemat din `apiFetch` la
// orice raspuns primit de la server (inclusiv 4xx/5xx — serverul care raspunde
// „nu" e tot un server care raspunde).

import { eRetea } from './erori.js'

export const reteaua = $state({
  /** Ultimul lucru pe care il stim, nu ultimul lucru pe care il speram. */
  online: typeof navigator === 'undefined' || navigator.onLine !== false,
})

/** O cerere a picat. Daca a picat DIN RETEA, asta e dovada ca esti deconectat. */
export function picat(eroare) {
  if (eRetea(eroare?.message ?? eroare)) reteaua.online = false
}

/** Serverul a raspuns ceva — deci exista drum pana la el. */
export function reusit() {
  reteaua.online = true
}

if (typeof window !== 'undefined') {
  window.addEventListener('offline', () => { reteaua.online = false })
  // `online` e o promisiune, nu o confirmare (vezi mai sus): il credem, dar prima
  // cerere care pica il contrazice imediat.
  window.addEventListener('online', () => { reteaua.online = true })
}

// CE SCRIE BROWSERUL NU E CE CITESTE OMUL.
//
// Cand pica reteaua, `fetch` respinge cu un mesaj propriu, in engleza si diferit de
// la un browser la altul: „Failed to fetch" (Chrome), „Load failed" (Safari),
// „NetworkError when attempting to fetch resource." (Firefox).
//
// Regula asta traia in `ErrorState.svelte`, deci acoperea DOAR esecurile de
// CITIRE — cele care golesc o pagina. Esecurile de SCRIERE (71 de apeluri
// `toast(`Eroare: ${e.message}`)` in 13 fisiere) treceau pe langa ea si ajungeau
// pe ecran ca atare. Masurat: fara retea, „Creează proiectul" da toastul
// „Eroare: Failed to fetch" la 400ms.
//
// Rezultatul era pe dos fata de cat conteaza: pagina care nu se incarca vorbea
// romaneste, iar salvarea care nu se face — engleza browserului. Iar salvarile
// sunt exact ce faci pe teren, cu semnal prost.
//
// De aceea functia sta AICI si e chemata din `toast()` (stores/ui.svelte.js) si
// din `ErrorState`: cele 71 de locuri se repara fara sa fie atinse niciunul.

const RETEA = /failed to fetch|load failed|networkerror|network request failed|err_internet_disconnected|err_network_changed|err_name_not_resolved|err_connection|err_address_unreachable/i
const SESIUNE = /^\s*(eroare:\s*)?unauthorized\s*$/i

/** A picat reteaua, nu serverul? (Serverul care raspunde 500 nu intra aici.) */
export function eRetea(mesaj) {
  return RETEA.test((mesaj || '').toString())
}

/**
 * Mesajul pe care il vede omul.
 *
 * Cand e retea, INTREG textul e inlocuit — nu doar sirul browserului. Prefixul
 * celor 71 de apelanti e „Eroare", adica exact ce spune deja iconita rosie a
 * toastului; iar cele patru care spun ceva („la export", „Perioade") spun CE
 * cerere a picat, ceea ce nu schimba nici cauza, nici ce ai de facut. Fara
 * retea, singurul lucru care conteaza e ca n-ai retea.
 */
export function umanizeaza(mesaj) {
  const s = (mesaj || '').toString().trim()
  if (!s) return ''
  if (RETEA.test(s)) return 'Pare că nu e rețea. Verifică semnalul și încearcă din nou.'
  if (SESIUNE.test(s)) return 'Sesiunea a expirat. Intră din nou cu PIN-ul.'
  return s
}

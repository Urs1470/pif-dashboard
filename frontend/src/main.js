import { mount } from 'svelte'
import './styles/global.css'
import App from './App.svelte'
import { apiJson } from './lib/api.js'
import { inapoi, router } from './lib/router.svelte.js'
import { loadGlobalTasks } from './stores/tasks.svelte.js'
import { todayISO } from './lib/calendarDates.js'
import { esteNativ, reprogrameaza } from './lib/notificari.js'
import { App as CapApp } from '@capacitor/app'
import { verifica as verificaActualizarea, descarcaSiInstaleaza } from './lib/actualizare.js'
import { toastFix, actualizeazaToast } from './stores/ui.svelte.js'
// Dashboard-ul e in spatele login-ului -> runtime.docsOk e implicit true (vezi runtime.svelte.js),
// deci extrasele de carti se vad. Pe /calc public, calc-main.js le gateaza dupa autentificare.

// DATELE ATERIZARII PLEACA ODATA CU CODUL EI, NU DUPA.
//
// Masurat la prima deschidere pe telefon (4G, procesor incetinit de patru ori):
// `main.js` termina la 813ms, chunkul paginii de taskuri la 1123ms, si abia
// ATUNCI pornea `/api/global-tasks` — care se intorcea la 1542ms. Trei etape
// puse cap la cap, desi ultima nu depinde de a doua: cererea are nevoie doar de
// URL, iar URL-ul e aici, in bundle-ul principal.
//
// Se cheama INAINTE de `mount`, deci pleaca in aceeasi rafala cu chunkul rutei.
// Cand pagina se monteaza, `loadGlobalTasks` din ea cade pe aceeasi cerere prin
// impartirea celor in zbor din `cache.js` — deci raman una singura, pornita cu
// vreo 900ms mai devreme.
//
// Doar pe ruta de aterizare, si doar daca ea CHIAR e lista: pe desktop se
// deschide Acasa, iar o notificare atinsa deschide alta ruta. Ce nu se
// potriveste nu se incalzeste — o cerere degeaba ar fura banda exact de la
// chunkul care se astepta.
if (router.path === '/tasks') {
  // `sfera: 'toate'` — aceleasi optiuni cu care o cere pagina (vezi Tasks.svelte).
  // Alte optiuni ar da alt URL, deci alta cerere, deci doua in loc de una.
  loadGlobalTasks({ sfera: 'toate' })
}

const app = mount(App, {
  target: document.getElementById('app'),
})

// NOTIFICARILE DE DIMINEATA, cand aplicatia ruleaza in shell-ul Android.
// In browser `esteNativ()` e fals si nu se intampla nimic — acelasi bundle e
// servit si pe PC. Detaliile si regula: `lib/notificari.js`.
//
// Lista se cere DIRECT, nu prin `loadGlobalTasks`: acela scrie in `globalTasks`,
// care e si vederea paginii Taskuri. O reprogramare declansata cat esti pe
// „Muncă" ti-ar repicta lista cu taskurile personale — fix capcana descrisa in
// `stores/tasks.svelte.js`.
if (esteNativ()) {
  const reprogrameazaDinServer = async () => {
    try {
      // Setarile, taskurile SI perioadele, in paralel: trei cereri independente,
      // iar programarea are nevoie de toate trei ca sa fie corecta. Perioadele
      // sunt pentru alarma de plecare pe teren (turul 15) — o fereastra de 60 de
      // zile, mai lunga decat cele 7 zile de notificari, ca sa prinda si o
      // deplasare planificata de mult.
      const [d, setari, cal] = await Promise.all([
        apiJson('/api/global-tasks?sfera=personal'),
        apiJson('/api/push/setari').catch(() => null),
        // `todayISO()`, NU `toISOString()`: a doua e in UTC, iar la est de
        // Greenwich miezul noptii local cade in ziua precedenta — fereastra ar
        // porni cu o zi mai devreme, fix in orele in care se pune alarma de seara.
        apiJson(`/api/calendar?start=${todayISO()}&zile=60`).catch(() => null),
      ])
      await reprogrameaza(Array.isArray(d) ? d : d.tasks || [], setari, cal?.perioade || [])
    } catch (e) {
      // Fara retea nu putem reprograma, dar alarmele deja puse raman valabile —
      // exact motivul pentru care fereastra e de mai multe zile.
    }
  }
  // Nu se mai leaga niciun ascultator de actiuni: butoanele sunt tratate nativ,
  // fara sa deschida aplicatia (vezi comentariul de la finalul `notificari.js`).
  reprogrameazaDinServer()
  // La fiecare revenire in aplicatie: taskuri bifate de pe PC ies din programare.
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) reprogrameazaDinServer()
  })
}

// GESTUL „INAPOI" PE ANDROID = UN PAS INAPOI IN APLICATIE, NU IN WEBVIEW.
//
// Fara ascultator pe `backButton`, Capacitor face `webView.goBack()` pe
// istoricul BRUT al WebView-ului — care nu e istoricul aplicatiei: aterizarea
// il rescrie cu `replaceState`, login-ul lasa un redirect in urma, iar
// `focus.js` mai curata cate un query. Gestul cadea deci pe prima intrare
// (pagina fara hash = Acasa), nu pe ultima miscare; iar cand WebView-ul nu mai
// avea unde, nu facea nimic. Ordinea de aici:
//   1. un strat deschis (modal/foaie, calendar, paleta) se inchide INTAI;
//   2. altfel, ruta precedenta din istoricul ruterului (`inapoi()`);
//   3. pe radacina, aplicatia trece IN FUNDAL (`minimizeApp`), nu se inchide
//      brusc — starea ramane calda pentru urmatoarea deschidere.
//
// Stratul se inchide printr-un Escape SINTETIC, nu printr-o a doua logica de
// inchidere: Escape inseamna deja „inchide UN strat" peste tot in aplicatie
// (calendarul il prinde pe captura si opreste propagarea, ca modalul de sub el
// sa ramana deschis — vezi `DatePicker.svelte`), deci gestul mosteneste gratis
// exact ierarhia corecta. Se trimite pe elementul focalizat, fiindca modalul
// isi asculta propriul backdrop, nu fereastra; cand focusul e in alta parte,
// pe strat — pentru voalul modalului e totuna, pentru calendar oricum conteaza
// doar captura pe fereastra.
if (esteNativ()) {
  const inchideStratulDeSus = () => {
    // Selectorii sunt markup-ul real al straturilor care asculta Escape:
    // `.backdrop` (Modal), `.dp-pop` (DatePicker), `.palette-backdrop` (paleta).
    const strat = document.querySelector('.backdrop, .dp-pop, .palette-backdrop')
    if (!strat) return false
    const activ = document.activeElement
    const tinta = activ && activ !== document.body ? activ : strat
    tinta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }))
    return true
  }
  CapApp.addListener('backButton', () => {
    if (inchideStratulDeSus()) return
    if (!inapoi()) CapApp.minimizeApp()
  })
}

if ('serviceWorker' in navigator && !import.meta.env.DEV) {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('/service-worker.js')

      // (1) Un worker poate fi DEJA in asteptare, instalat intr-o sesiune trecuta.
      // Atunci `updatefound` nu mai apare niciodata, deci bannerul nu s-ar arata.
      if (reg.waiting && navigator.serviceWorker.controller) showUpdateBanner(reg)

      // (2) Browserul verifica singur doar la navigare si cam o data pe zi.
      // Dashboard-ul sta deschis zile intregi (si ca PWA pe telefon, niciodata
      // inchis complet), deci intrebam noi: la revenirea pe fila si din 15 in 15
      // minute. Fara asta, un deploy putea sa nu ajunga la utilizator DELOC.
      const verificaActualizari = () => { reg.update().catch(() => {}) }
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) verificaActualizari()
      })
      setInterval(verificaActualizari, 15 * 60 * 1000)

      reg.addEventListener('updatefound', () => {
        const newSW = reg.installing
        if (!newSW) return
        newSW.addEventListener('statechange', () => {
          if (newSW.state === 'installed' && navigator.serviceWorker.controller) {
            showUpdateBanner(reg)
          }
        })
      })
    } catch (e) {
      if (import.meta.env.DEV) console.log('[SW] Registration failed:', e)
    }
  })

  navigator.serviceWorker.addEventListener('message', (event) => {
    if (event.data?.type === 'SW_UPDATED' && import.meta.env.DEV) {
      console.log('[SW] Updated to', event.data.version)
    }
    // Atingerea unei notificari, cu aplicatia deja deschisa: schimbam DOAR
    // hash-ul, pe care ruterul il asculta oricum. O navigare adevarata ar
    // reincarca aplicatia si ar pierde starea.
    if (event.data?.type === 'NAVIGHEAZA' && event.data.url) {
      const h = String(event.data.url).split('#')[1]
      if (h) window.location.hash = '#' + h
    }
  })
}

// ANUNTUL DE ACTUALIZARE E UN TOAST, NU O BANDA PROPRIE.
//
// Mecanica de aici nu s-a schimbat cu nimic — verificarea la 15 minute,
// `skipWaiting` inainte de reload, procentul in timpul descarcarii, eroarea care
// RAMANE pe ecran in loc sa treaca. S-a schimbat doar CINE deseneaza: banda era
// construita cu `document.createElement`, deci era singurul loc de interfata din
// aplicatie in afara Svelte — si se vedea (buton de 26px pe telefon, chenar
// colorat, fara `aria-live`, imposibil de inchis, si se putea dubla).
//
// Toastul avea deja tot ce-i lipsea benzii. Vezi `toastFix` in `stores/ui`:
// `cheie` tine una singura pe ecran, `prioritate` decide care, cand apar
// amandoua.
const PRIO_INTERFATA = 1
const PRIO_CARCASA = 2       // carcasa cere o INSTALARE; interfata doar o reincarcare

function showUpdateBanner(reg) {
  toastFix('actualizare', {
    message: 'Versiune nouă a interfeței',
    ico: 'reload',
    actionLabel: 'Reîncarcă',
    prioritate: PRIO_INTERFATA,
    onAction: () => {
      // (3) Reincarcam DUPA ce noul worker a preluat pagina. Un reload imediat era
      // servit tot de workerul vechi: bannerul reaparea si nimic nu se schimba.
      navigator.serviceWorker.addEventListener('controllerchange',
        () => window.location.reload(), { once: true })
      reg.waiting?.postMessage('skipWaiting')
      // Plasa de siguranta daca `controllerchange` nu vine (worker blocat).
      setTimeout(() => window.location.reload(), 2500)
    },
  })
}

// ACTUALIZAREA CARCASEI NATIVE — acelasi anunt ca cel al service worker-ului,
// pentru ca inseamna acelasi lucru pentru tine: „ce rulezi e vechi, apasa aici".
// Diferenta e sub capota (un APK, nu un bundle) si nu are de ce sa se vada.
// Verificam o SINGURA data, la pornire: carcasa se schimba de cateva ori pe an,
// iar o verificare la fiecare revenire in aplicatie ar fi trafic pentru nimic.
if (esteNativ()) {
  ;(async () => {
    const stare = await verificaActualizarea(apiJson)
    if (!stare?.nou) return
    const mb = stare.size ? ` · ${(stare.size / 1048576).toFixed(1)} MB` : ''

    async function descarca() {
      // Chipul nu mai e buton cat timp se descarca: `progres` il transforma in
      // afisaj. Asa nu mai trebuie disabled si nu mai poti porni a doua
      // descarcare peste prima.
      actualizeazaToast(id, { message: 'Se descarcă…', rol: 'accent', actionLabel: '', progres: 0 })
      try {
        await descarcaSiInstaleaza((p) => actualizeazaToast(id, { progres: p }))
        // Dialogul de sistem preia de aici.
        actualizeazaToast(id, { message: 'Instalează…', progres: null })
      } catch (e) {
        // Mesajul serverului RAMANE pe ecran, exact cum vine, si nu pleaca singur:
        // daca a picat permisiunea de instalare, trebuie sa poti citi ce ai de
        // facut. Tocmai de asta anuntul e un toast FIX, nu unul de 4 secunde.
        actualizeazaToast(id, {
          message: e.message, rol: 'restant', ico: 'eroare',
          progres: null, actionLabel: 'Încearcă din nou',
        })
      }
    }

    const id = toastFix('actualizare', {
      message: `Aplicație nouă: ${stare.nume}${mb}`,
      ico: 'descarca',
      actionLabel: 'Actualizează',
      prioritate: PRIO_CARCASA,
      onAction: descarca,
    })
  })()
}

// INSTALAREA PE ECRANUL PRINCIPAL.
//
// `preventDefault()` opreste indiciul propriu al browserului, deci de aici
// inainte SINGURA cale de instalare e a noastra. Multa vreme n-a existat niciuna:
// `pifInstallApp` era expus si nu-l chema nimeni, deci aplicatia nu se putea
// instala nici de la noi, nici de la browser. Cine il cheama acum: randul din
// foaia „Mai mult" a docului (`Dock.svelte`), aratat doar dupa evenimentul de
// mai jos.
//
// `pifPoateInstala` exista fiindca evenimentul poate trece INAINTE ca dockul sa
// se monteze: un ascultator pus dupa aceea n-ar mai auzi nimic, iar randul n-ar
// aparea decat la urmatoarea incarcare.
let deferredInstallPrompt = null
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  deferredInstallPrompt = e
  window.dispatchEvent(new CustomEvent('pif-install-ready'))
})

window.pifPoateInstala = () => !!deferredInstallPrompt

window.pifInstallApp = async () => {
  if (!deferredInstallPrompt) return false
  deferredInstallPrompt.prompt()
  const result = await deferredInstallPrompt.userChoice
  // Promptul se consuma la prima folosire, indiferent de raspuns: browserul nu
  // mai accepta un al doilea `prompt()` pe acelasi eveniment.
  deferredInstallPrompt = null
  return result.outcome === 'accepted'
}

export default app

import { mount } from 'svelte'
import './styles/global.css'
import App from './App.svelte'
import { apiJson } from './lib/api.js'
import { navigate } from './lib/router.svelte.js'
import { esteNativ, reprogrameaza, legaActiunile } from './lib/notificari.js'
// Dashboard-ul e in spatele login-ului -> runtime.docsOk e implicit true (vezi runtime.svelte.js),
// deci extrasele de carti se vad. Pe /calc public, calc-main.js le gateaza dupa autentificare.

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
      const d = await apiJson('/api/global-tasks?sfera=personal')
      await reprogrameaza(Array.isArray(d) ? d : d.tasks || [])
    } catch (e) {
      // Fara retea nu putem reprograma, dar alarmele deja puse raman valabile —
      // exact motivul pentru care fereastra e de mai multe zile.
    }
  }
  legaActiunile({ apiJson, navigate, peSchimbare: reprogrameazaDinServer })
  reprogrameazaDinServer()
  // La fiecare revenire in aplicatie: taskuri bifate de pe PC ies din programare.
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) reprogrameazaDinServer()
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

function showUpdateBanner(reg) {
  const bar = document.createElement('div')
  bar.className = 'sw-update-bar'
  bar.innerHTML = '<span>Versiune nouă disponibilă</span><button>Actualizează</button>'
  bar.querySelector('button').onclick = () => {
    // (3) Reincarcam DUPA ce noul worker a preluat pagina. Un reload imediat era
    // servit tot de workerul vechi: bannerul reaparea si nimic nu se schimba.
    navigator.serviceWorker.addEventListener('controllerchange',
      () => window.location.reload(), { once: true })
    reg.waiting?.postMessage('skipWaiting')
    // Plasa de siguranta daca `controllerchange` nu vine (worker blocat).
    setTimeout(() => window.location.reload(), 2500)
  }
  document.body.appendChild(bar)
}

let deferredInstallPrompt = null
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault()
  deferredInstallPrompt = e
  window.dispatchEvent(new CustomEvent('pif-install-ready'))
})

window.pifInstallApp = async () => {
  if (!deferredInstallPrompt) return false
  deferredInstallPrompt.prompt()
  const result = await deferredInstallPrompt.userChoice
  deferredInstallPrompt = null
  return result.outcome === 'accepted'
}

export default app

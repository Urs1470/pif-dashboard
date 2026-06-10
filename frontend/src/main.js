import { mount } from 'svelte'
import './styles/global.css'
import App from './App.svelte'

const app = mount(App, {
  target: document.getElementById('app'),
})

if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('/service-worker.js')
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
      console.log('[SW] Registration failed:', e)
    }
  })

  navigator.serviceWorker.addEventListener('message', (event) => {
    if (event.data?.type === 'SW_UPDATED') {
      console.log('[SW] Updated to', event.data.version)
    }
  })
}

function showUpdateBanner(reg) {
  const bar = document.createElement('div')
  bar.className = 'sw-update-bar'
  bar.innerHTML = '<span>Versiune noua disponibila</span><button>Actualizeaza</button>'
  bar.querySelector('button').onclick = () => {
    reg.waiting?.postMessage('skipWaiting')
    window.location.reload()
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

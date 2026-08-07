// Abonarea la notificari, partea de browser (serverul: blueprints/push.py).
//
// De ce `navigator.serviceWorker.ready` si nu registration-ul din main.js:
// acela traieste in interiorul listenerului de `load` si nu e exportat. `ready`
// intoarce acelasi worker, oricand, fara sa legam doua module intre ele.

import { apiJson } from './api.js'

export function suportaPush() {
  return typeof window !== 'undefined'
    && 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window
}

/** iPhone/iPad in Safari, cu aplicatia NEinstalata pe ecranul principal.
 *  Acolo Web Push pur si simplu nu exista (iOS 16.4+ il da doar din PWA
 *  instalata), deci merita spus explicit, nu lasat sa esueze mut. */
export function esteIosNeinstalat() {
  if (typeof window === 'undefined') return false
  const ua = navigator.userAgent || ''
  const ios = /iPad|iPhone|iPod/.test(ua)
    || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  if (!ios) return false
  const standalone = window.matchMedia?.('(display-mode: standalone)')?.matches
    || window.navigator.standalone === true
  return !standalone
}

export function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const out = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i)
  return out
}

export async function stareAbonament() {
  if (!suportaPush()) return { permisiune: 'unsupported', abonat: false, endpoint: '' }
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  return {
    permisiune: Notification.permission,
    abonat: !!sub,
    endpoint: sub?.endpoint || '',
  }
}

export async function aboneaza() {
  if (!suportaPush()) throw new Error('Browserul nu suportă notificări push.')
  const permisiune = await Notification.requestPermission()
  if (permisiune !== 'granted') throw new Error('Permisiunea pentru notificări a fost refuzată.')
  const { cheie } = await apiJson('/api/push/vapid-public')
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(cheie),
  })
  return apiJson('/api/push/subscribe', { method: 'POST', body: sub.toJSON() })
}

export async function dezaboneaza() {
  const reg = await navigator.serviceWorker.ready
  const sub = await reg.pushManager.getSubscription()
  if (!sub) return { ok: true }
  const endpoint = sub.endpoint
  await sub.unsubscribe()
  return apiJson('/api/push/unsubscribe', { method: 'POST', body: { endpoint } })
}

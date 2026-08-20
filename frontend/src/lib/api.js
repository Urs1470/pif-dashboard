import { picat, reusit } from './retea.svelte.js'

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : ''
}

export async function apiFetch(url, opts = {}) {
  const method = (opts.method || 'GET').toUpperCase()
  const headers = { ...opts.headers }

  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    headers['X-CSRF-Token'] = getCsrfToken()
  }

  if (opts.body && typeof opts.body === 'object' && !(opts.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
    opts.body = JSON.stringify(opts.body)
  }

  // STAREA RETELEI SE AFLA DE AICI, nu din `navigator.onLine`. Steagul spune doar
  // ca exista un adaptor; o cerere care pica din retea spune ca nu exista drum.
  // Vezi `lib/retea.svelte.js`.
  let res
  try {
    res = await fetch(url, {
      credentials: 'same-origin',
      ...opts,
      method,
      headers,
    })
  } catch (e) {
    picat(e)
    throw e
  }
  // Serverul a raspuns ceva — si 4xx/5xx e un raspuns, deci drumul exista.
  reusit()

  if (res.status === 401) {
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  return res
}

export async function apiJson(url, opts = {}) {
  const res = await apiFetch(url, opts)
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`)
  return data
}

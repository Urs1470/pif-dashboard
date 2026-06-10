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

  const res = await fetch(url, {
    credentials: 'same-origin',
    ...opts,
    method,
    headers,
  })

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

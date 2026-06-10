export const router = $state({ path: getPath(), params: {} })

function getPath() {
  const hash = window.location.hash
  return hash.startsWith('#') ? hash.slice(1) || '/' : '/'
}

function matchRoute(pattern, path) {
  const patternParts = pattern.split('/')
  const pathParts = path.split('/')
  if (patternParts.length !== pathParts.length) return null
  const params = {}
  for (let i = 0; i < patternParts.length; i++) {
    if (patternParts[i].startsWith(':')) {
      params[patternParts[i].slice(1)] = pathParts[i]
    } else if (patternParts[i] !== pathParts[i]) {
      return null
    }
  }
  return params
}

export function navigate(path) {
  window.location.hash = '#' + path
}

export function link(node) {
  function handleClick(e) {
    if (e.ctrlKey || e.metaKey || e.shiftKey) return
    e.preventDefault()
    const href = node.getAttribute('href')
    if (href) navigate(href)
  }
  node.addEventListener('click', handleClick)
  return { destroy() { node.removeEventListener('click', handleClick) } }
}

export function resolveRoute(routes) {
  const path = router.path
  for (const [pattern, component] of Object.entries(routes)) {
    const params = matchRoute(pattern, path)
    if (params !== null) return { component, params }
  }
  return null
}

if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', () => {
    router.path = getPath()
  })
}

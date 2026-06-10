export const ui = $state({
  sidebarCollapsed: localStorage.getItem('sidebar-collapsed') === 'true',
  theme: localStorage.getItem('theme') || 'dark',
  toasts: [],
})

let toastId = 0

export function toggleSidebar() {
  ui.sidebarCollapsed = !ui.sidebarCollapsed
  localStorage.setItem('sidebar-collapsed', ui.sidebarCollapsed)
}

export function setTheme(theme) {
  ui.theme = theme
  localStorage.setItem('theme', theme)
  document.documentElement.setAttribute('data-theme', theme)
}

export function toggleTheme() {
  setTheme(ui.theme === 'dark' ? 'light' : 'dark')
}

export function toast(message, type = 'info', duration = 3000) {
  const id = ++toastId
  ui.toasts.push({ id, message, type })
  if (duration > 0) {
    setTimeout(() => dismissToast(id), duration)
  }
}

export function dismissToast(id) {
  const idx = ui.toasts.findIndex(t => t.id === id)
  if (idx !== -1) ui.toasts.splice(idx, 1)
}

if (typeof document !== 'undefined') {
  document.documentElement.setAttribute('data-theme', ui.theme)
}

import { apiJson } from '../lib/api.js'

export const params = $state({
  items: [],
  families: [],
  total: 0,
  page: 1,
  totalPages: 1,
  loading: false,
  error: null,
  filters: { search: '', familie: '', page: 1, limit: 50 },
})

export async function loadFamilies() {
  try {
    const data = await apiJson('/api/parametri/familii')
    params.families = data.families || []
  } catch (e) {
    params.families = []
  }
}

export async function loadParams() {
  params.loading = true
  params.error = null
  try {
    const p = new URLSearchParams()
    if (params.filters.search) p.set('search', params.filters.search)
    if (params.filters.familie) p.set('familie', params.filters.familie)
    p.set('page', params.filters.page)
    p.set('limit', params.filters.limit)
    const data = await apiJson(`/api/parametri?${p}`)
    params.items = data.params || []
    params.total = data.total || 0
    params.page = data.page || 1
    params.totalPages = data.totalPages || 1
  } catch (e) {
    params.error = e.message
  } finally {
    params.loading = false
  }
}

export const faultCodes = $state({
  items: [],
  families: [],
  loading: false,
  filters: { search: '', familie: '', page: 1, limit: 50 },
  total: 0,
  totalPages: 1,
})

export async function loadFaultFamilies() {
  try {
    const data = await apiJson('/api/fault-codes/familii')
    faultCodes.families = data.families || []
  } catch (e) {
    faultCodes.families = []
  }
}

export async function loadFaultCodes() {
  faultCodes.loading = true
  try {
    const p = new URLSearchParams()
    if (faultCodes.filters.search) p.set('search', faultCodes.filters.search)
    if (faultCodes.filters.familie) p.set('familie', faultCodes.filters.familie)
    p.set('page', faultCodes.filters.page)
    p.set('limit', faultCodes.filters.limit)
    const data = await apiJson(`/api/fault-codes?${p}`)
    faultCodes.items = data.params || data.codes || []
    faultCodes.total = data.total || 0
    faultCodes.totalPages = data.totalPages || 1
  } catch (e) {
    faultCodes.items = []
  } finally {
    faultCodes.loading = false
  }
}

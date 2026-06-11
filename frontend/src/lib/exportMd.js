import { apiJson } from './api.js'

function fmtHours(s) {
  if (!s) return '0h'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  return h > 0 ? `${h}h ${m}m` : `${m}m`
}

function escMd(txt) {
  return (txt || '').replace(/\|/g, '\\|')
}

export function formatFileSize(bytes) {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export async function exportMarkdown(projectId) {
  const [project, tasks, jurnal, attachments, timer, echipamente] = await Promise.all([
    apiJson(`/api/proiecte/${projectId}`),
    apiJson(`/api/proiecte/${projectId}/tasks`).catch(() => []),
    apiJson(`/api/proiecte/${projectId}/jurnal`).catch(() => []),
    apiJson(`/api/proiecte/${projectId}/atasamente`).catch(() => []),
    apiJson(`/api/proiecte/${projectId}/timer`).catch(() => ({ sessions: [], total_secunde: 0 })),
    apiJson(`/api/proiecte/${projectId}/echipamente`).catch(() => []),
  ])

  const isPIF = project.tip === 'PIF'
  const isService = project.tip === 'Service'
  const today = new Date().toISOString().split('T')[0]

  let md = ''

  // FRONTMATTER YAML (Obsidian-compatible)
  md += `---\n`
  md += `tags:\n`
  if (isPIF) md += `  - proiect\n  - pif\n`
  if (isService) md += `  - service\n  - interventie\n`
  if (project.producator && project.producator !== 'Altul')
    md += `  - ${project.producator.toLowerCase()}\n`
  md += `client: ${project.client || ''}\n`
  md += `locatie: ${project.locatie || ''}\n`
  md += `echipament_principal: ${project.echipament_principal || ''}\n`
  md += `data_export: ${today}\n`
  if (isPIF) {
    md += `data_incepere: ${project.data_incepere || ''}\n`
    md += `deadline: ${project.deadline || ''}\n`
  }
  if (isService) md += `data_crearii: ${project.data_crearii || today}\n`
  md += `status: ${project.status || 'activ'}\n`
  if (project.cod_proiect) md += `cod_proiect: ${project.cod_proiect}\n`
  md += `total_ore_lucrate: ${fmtHours(timer.total_secunde)}\n`
  md += `---\n\n`

  md += isPIF ? `# PIF — ${project.nume}\n\n` : `# Service — ${project.nume}\n\n`

  let section = 1

  // 1. Detalii administrative
  md += `## ${section++}. Detalii administrative\n\n`
  md += `| Câmp | Valoare |\n|---|---|\n`
  md += `| Client | ${escMd(project.client) || '—'} |\n`
  md += `| Locație | ${escMd(project.locatie) || '—'} |\n`
  md += `| Producător | ${escMd(project.producator) || '—'} |\n`
  md += `| Echipament principal | ${escMd(project.echipament_principal) || '—'} |\n`
  if (project.pm) md += `| Project Manager | ${escMd(project.pm)} |\n`
  if (project.nr_comanda) md += `| Nr. Comandă | ${escMd(project.nr_comanda)} |\n`
  if (project.nr_contract) md += `| Nr. Contract | ${escMd(project.nr_contract)} |\n`
  if (project.cod_proiect) md += `| Cod proiect | ${escMd(project.cod_proiect)} |\n`
  if (project.folder_server) md += `| Folder server | ${escMd(project.folder_server)} |\n`
  md += `| Status | ${escMd(project.status) || 'activ'} |\n`
  md += `| Total ore lucrate | ${fmtHours(timer.total_secunde)} |\n`
  md += `\n`

  // 2. Continut tehnic
  if (isPIF && project.observatii) {
    md += `## ${section++}. Observații tehnice\n\n${project.observatii}\n\n`
  }
  if (isService) {
    md += `## ${section++}. Fișă intervenție\n\n`
    if (project.service_before) {
      md += `### Constatări înainte de intervenție\n\n${project.service_before}\n\n`
    }
    if (project.service_after) {
      md += `### Acțiuni efectuate și rezultat\n\n${project.service_after}\n\n`
    }
  }

  // 3. Lista taskuri
  if (tasks.length > 0) {
    md += `## ${section++}. Listă taskuri\n\n`
    const prioOrder = { urgent: 0, normal: 1, minor: 2 }
    const prioBadge = { urgent: '[Urgent]', normal: '[Normal]', minor: '[Minor]' }
    const pkey = (t) => (t.prioritate || 'normal').toLowerCase()
    const sorted = [...tasks].sort((a, b) => (prioOrder[pkey(a)] ?? 1) - (prioOrder[pkey(b)] ?? 1))

    const pending = sorted.filter(t => t.status !== 'done')
    const done = sorted.filter(t => t.status === 'done')

    if (pending.length > 0) {
      md += `### To Do\n\n`
      pending.forEach(t => {
        const badge = prioBadge[pkey(t)] || '[Normal]'
        const term = t.data_scadenta ? ` · termen ${t.data_scadenta}` : ''
        md += `- [ ] ${escMd(t.titlu)} ${badge}${term}\n`
      })
      md += `\n`
    }
    if (done.length > 0) {
      md += `### Finalizate\n\n`
      done.forEach(t => {
        const badge = prioBadge[pkey(t)] || '[Normal]'
        const finalizat = t.data_finalizare ? ` · finalizat ${t.data_finalizare.split('T')[0]}` : ''
        md += `- [x] ${escMd(t.titlu)} ${badge}${finalizat}\n`
      })
      md += `\n`
    }
  }

  // 5. Echipamente
  if (echipamente && echipamente.length > 0) {
    md += `## ${section++}. Echipamente\n\n`
    md += `| # | Nume | Producător | Model | Serie | Parametri |\n|---|---|---|---|---|---|\n`
    const parseParams = (eq) => {
      try { return typeof eq.params_json === 'string' ? JSON.parse(eq.params_json || '{}') : (eq.params_json || {}) } catch { return {} }
    }
    echipamente.forEach((eq, idx) => {
      const params = parseParams(eq)
      md += `| ${idx + 1} | ${escMd(eq.nume) || '—'} | ${escMd(eq.producator) || '—'} | ${escMd(eq.model) || '—'} | ${escMd(eq.serial_number) || '—'} | ${Object.keys(params).length} |\n`
    })
    md += `\n`
    echipamente.forEach((eq, idx) => {
      const entries = Object.entries(parseParams(eq))
      if (entries.length === 0) return
      md += `### Echipament #${idx + 1} — ${escMd(eq.nume)} · parametri modificați\n\n`
      md += `| Cod | Valoare |\n|---|---|\n`
      entries.forEach(([k, v]) => { md += `| \`${k}\` | ${escMd(String(v))} |\n` })
      md += `\n`
    })
  }

  // 6. Jurnal de lucru + sesiuni timer
  if (jurnal.length > 0 || (timer.sessions && timer.sessions.length > 0)) {
    md += `## ${section++}. Jurnal de lucru\n\n`
    const sessions = (timer.sessions || []).slice()
    const matched = new Set()
    for (const j of jurnal) {
      const jt = new Date(j.created_at || j.data || 0).getTime()
      if (!jt) continue
      const found = sessions.find(s => {
        const stopIso = s.stop_time || s.end_time
        if (matched.has(s.id) || !stopIso) return false
        return Math.abs(jt - new Date(stopIso).getTime()) < 2 * 60 * 1000
      })
      if (found) { matched.add(found.id); j._duration_secunde = found.durata_secunde }
    }
    ;[...jurnal].reverse().forEach(entry => {
      const durSuffix = entry._duration_secunde ? ` · ${fmtHours(entry._duration_secunde)}` : ''
      md += `### ${entry.data || ''}${durSuffix}\n\n${entry.continut || ''}\n\n`
    })
    const unmatched = sessions.filter(s => !matched.has(s.id) && (s.stop_time || s.end_time))
    if (unmatched.length > 0) {
      md += `### Sesiuni timer fără notă\n\n`
      unmatched.forEach(s => {
        const date = s.start_time ? s.start_time.substring(0, 10) : ''
        md += `- ${date} · ${fmtHours(s.durata_secunde)}\n`
      })
      md += `\n`
    }
  }

  // 7. Atasamente
  if (attachments.length > 0) {
    md += `## ${section++}. Atașamente\n\n`
    md += `| Fișier | Tip | Mărime | Adăugat |\n|---|---|---|---|\n`
    attachments.forEach(att => {
      md += `| ${escMd(att.nume_fisier)} | ${escMd(att.tip_fisier)} | ${formatFileSize(att.dimensiune)} | ${escMd(att.data) || '—'} |\n`
    })
    md += `\n`
  }

  md += `\n---\n\n`
  md += `*Document generat automat din PIF Dashboard · ${today} · Ion Ursu*\n`

  const filename = project.cod_proiect
    ? `${project.cod_proiect}_${(project.nume || 'proiect').replace(/[^a-z0-9]/gi, '_')}.md`
    : `${(project.nume || 'proiect').replace(/[^a-z0-9]/gi, '_')}.md`

  const blob = new Blob([md], { type: 'text/markdown; charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

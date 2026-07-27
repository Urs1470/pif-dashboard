import { apiJson } from './api.js'

function escMd(txt) {
  return (txt || '').replace(/\|/g, '\\|')
}

export async function exportMarkdown(projectId) {
  const [project, tasks] = await Promise.all([
    apiJson(`/api/proiecte/${projectId}`),
    apiJson(`/api/proiecte/${projectId}/tasks`).catch(() => []),
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
  }
  if (isService) md += `data_crearii: ${project.data_crearii || today}\n`
  md += `status: ${project.status || 'activ'}\n`
  if (project.cod_proiect) md += `cod_proiect: ${project.cod_proiect}\n`
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
    // Prioritatea a plecat in v34: sortam dupa termen, cele fara termen la coada.
    const cheie = (t) => (t.data_scadenta || '9999-12-31').slice(0, 10)
    const sorted = [...tasks].sort((a, b) => cheie(a).localeCompare(cheie(b)))

    const pending = sorted.filter(t => t.status !== 'done')
    const done = sorted.filter(t => t.status === 'done')

    if (pending.length > 0) {
      md += `### To Do\n\n`
      pending.forEach(t => {
        const term = t.data_scadenta ? ` · termen ${t.data_scadenta}` : ''
        md += `- [ ] ${escMd(t.titlu)} ${badge}${term}\n`
      })
      md += `\n`
    }
    if (done.length > 0) {
      md += `### Finalizate\n\n`
      done.forEach(t => {
        const finalizat = t.data_finalizare ? ` · finalizat ${t.data_finalizare.split('T')[0]}` : ''
        md += `- [x] ${escMd(t.titlu)} ${badge}${finalizat}\n`
      })
      md += `\n`
    }
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

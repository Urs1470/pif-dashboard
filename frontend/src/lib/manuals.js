// Mapare familie drive -> manual PDF. Folosit in Params (detaliu parametru) si
// pe cardul echipamentului din detaliul proiectului (B3).
export const MANUAL_MAP = {
  'ACS880': 'ACS880_Primary_Firmware_Manual.pdf',
  'ACS580': 'ACS580_Firmware_Manual.pdf',
  'ACS380': 'ACS580_Firmware_Manual.pdf',
  'ACS180': 'ACS580_Firmware_Manual.pdf',
  'SINAMICS_G120': 'SINAMICS_G120_List_Manual.pdf',
  'SINAMICS_G120C': 'SINAMICS_G120_List_Manual.pdf',
  'SINAMICS_S120': 'SINAMICS_S120_S150_List_Manual.pdf',
  'SINAMICS_S150': 'SINAMICS_S120_S150_List_Manual.pdf',
  'SINAMICS_S120_S150': 'SINAMICS_S120_S150_List_Manual.pdf',
  'SINAMICS_G130_G150': 'SINAMICS_G120_List_Manual.pdf',
  'Danfoss_VLT_FC302': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
  'FC302': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
  'FC301': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
  'FC202': 'Danfoss_VLT_FC302_Programming_Guide.pdf',
  'Lenze_i550': 'Lenze_i550_Manual.pdf',
  'i550': 'Lenze_i550_Manual.pdf',
  'Lenze_i950': 'Lenze_i950_Manual.pdf',
  'i650': 'Lenze_i950_Manual.pdf',
  'i950': 'Lenze_i950_Manual.pdf',
}

// Replica _familie_from_echipament din backend (blueprints/projects.py):
// producator + model -> familie canonica (pentru fault codes + manual).
export function familieForEquip(producator = '', model = '') {
  const p = (producator || '').toLowerCase()
  const m = (model || '').toLowerCase()
  if (p.includes('danfoss')) return 'Danfoss_VLT_FC302'
  if (p.includes('abb')) return m.includes('880') ? 'ACS880' : 'ACS580'
  if (p.includes('siemens')) {
    if (m.includes('s120') || m.includes('s150')) return 'SINAMICS_S120_S150'
    if (m.includes('g130') || m.includes('g150')) return 'SINAMICS_G130_G150'
    return 'SINAMICS_G120'
  }
  if (p.includes('lenze')) return m.includes('950') ? 'Lenze_i950' : 'Lenze_i550'
  return ''
}

// URL-ul manualului (PDF) pentru un echipament; gol daca nu se poate determina.
export function manualUrlForEquip(producator, model, pagina) {
  const filename = MANUAL_MAP[familieForEquip(producator, model)]
  if (!filename) return ''
  let url = '/manuals/' + encodeURIComponent(filename)
  if (pagina) url += '#page=' + pagina
  return url
}

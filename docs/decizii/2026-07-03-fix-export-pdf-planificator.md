# 2026-07-03 — FIX export PDF Planificator: pagina alba + portrait

- **2026-07-03 — FIX export PDF Planificator: pagina alba + portrait** (SW v81, raportat de Ion cu PDF-ul
  real): exportul iesea **pagina alba (doar titlul) si portrait**. Doua cauze: (1) A4 portrait ≈ 794px
  latime CSS < breakpoint-ul `@media (max-width:820px)` care ascunde `.chart` (vederea mobila) — iar
  `.mlist` era si ea ascunsa in print → nimic de aratat. Fix: in print CSS `.chart{display:block!important;
  overflow:visible}` + `.mlist` ramane hidden, ca swimlane-ul sa se afiseze indiferent de latime. (2)
  `@page{size:A4 landscape}` era in `<style>`-ul SCOPED al componentei si NU se aplica → mutat in
  `global.css` (nescopat). Verificat cu `page.pdf({preferCSSPageSize:true})`: 841×595 = A4 landscape +
  swimlane-ul complet randat (testat pe 3L/90z ca in exportul lui Ion). Lectie: testul initial trecuse
  doar fiindca `page.pdf({landscape:true})` forta >820px; testeaza print-ul la latimea REALA a paginii.

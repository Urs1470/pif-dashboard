# 2026-07-31 — Miscarea la standardul gestului: `sosire` + `--ease-spring`

- **2026-07-31 (6) — Miscarea la standardul gestului: `sosire` + `--ease-spring`.**
  Inventarul miscarii a aratat ca mult e deja la standard (View Transitions API
  nativ pe navigare — masurat un singur `.content-width` pe toata durata; toast
  fly+flip; Select fly; shimmer; apasare <100ms; reduced-motion global). Doua
  lipsuri, ambele reparate:
  **(1) Iesirea exista, intrarea nu** — `sosire` in lib/motion.svelte.js
  (perechea lui `plecare`): opacitate + ridicare 5px, DOAR transform/opacity
  (vecinii isi fac loc prin `animate:flip`; doua animatii de layout pe acelasi
  eveniment s-ar calca). Pe toate cele trei liste, cu `|local` — REGULA: prima
  incarcare a paginii nu se joaca, intrarea e a randului nou (adaugat sau mutat
  intre grupe), nu a paginii. Masurat: opacitate 1 din primul cadru la load,
  ~10 cadre de fade la adaugare.
  **(2) Foaia eliberata se oprea mecanic** — token `--ease-spring` in tokens.css:
  `linear()` care esantioneaza un spring amortizat (~5% depasire), folosit DOAR
  pentru revenirea din gest (translate-ul sheet-ului, cu --dur-slow), cu rezerva
  pe `--ease` pentru browsere fara `linear()` (prima linie de `transition` din
  aceeasi regula). R4 din audit_design ramane curat fiindca tokenul sta in
  tokens.css. Masurat pe gest: 72px -> 0 -> −3.6px -> 0.
  Toate 4 harnessurile verzi dupa.

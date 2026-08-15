# 2026-07-03 — Dock FIX pe mobil (fără autohide)

- **2026-07-03 — Dock FIX pe mobil (fără autohide)** (SW v77, cerut de Ion): pe touch (`pointer:coarse`
  sau ≤768px) dock-ul e mereu vizibil, fără autohide — se ascunde DOAR cât timp e deschisă tastatura
  (focus pe câmp editabil), ca să nu plutească peste ea. Pe DESKTOP rămâne autohide v4 (cursor push la
  marginea de jos). Implementare în `Dock.svelte`: `isMobile` (matchMedia + resize), `apply()` = pe
  mobil `hidden=kbLocked`, pe desktop `!inZone`. `onMove` (cursor) și `revealFromPeek` no-op pe mobil.
  Manerul „peek" (`.dock-grip`) ascuns pe `pointer:coarse` (afordanță moartă când e fix). Verificat
  Playwright 390px: vizibil la load, se ascunde la focus input, reapare la blur.

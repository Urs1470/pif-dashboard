import { mount } from 'svelte'
import './styles/global.css'
import CalcApp from './CalcApp.svelte'
import { runtime } from './lib/runtime.svelte.js'

// /calc e public: ascunde extrasele de carti (copyright) pentru vizitatori anonimi,
// dar afiseaza-le daca esti autentificat (tu, in aceeasi sesiune din dashboard).
runtime.docsOk = false
fetch('/api/me', { credentials: 'same-origin' })
  .then((r) => (r.ok ? r.json() : null))
  .then((d) => { runtime.docsOk = !!(d && d.authenticated) })
  .catch(() => {})

// Aplicatie de sine statatoare: doar calculatorul (fara sidebar/auth), public la /calc.
mount(CalcApp, { target: document.getElementById('app') })

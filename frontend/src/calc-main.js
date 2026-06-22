import { mount } from 'svelte'
import './styles/global.css'
import CalcApp from './CalcApp.svelte'
import { runtime } from './lib/runtime.svelte.js'

// /calc afiseaza si linkurile catre extrasele de carti (doar paginile citate). Ruta /docs
// e publica (cu noindex), deci si vizitatorii de pe /calc pot deschide extrasele.
runtime.docsOk = true

// Aplicatie de sine statatoare: doar calculatorul (fara sidebar/auth), public la /calc.
mount(CalcApp, { target: document.getElementById('app') })

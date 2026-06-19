import { mount } from 'svelte'
import './styles/global.css'
import CalcApp from './CalcApp.svelte'

// Aplicatie de sine statatoare: doar calculatorul (fara sidebar/auth), public la /calc.
mount(CalcApp, { target: document.getElementById('app') })

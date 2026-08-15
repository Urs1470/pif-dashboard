# Mișcarea: o curbă, un ceas, o adâncime (tura 8, 2026-08-07)

Stratul de mișcare era deja construit. Problema era că fiecare bucată fusese reglată
singură — aplicația se mișca bine în bucăți și prost între ele.

- **Curba.** `--ease` era respectată peste tot în CSS, dar **nicio** tranziție Svelte
  n-o folosea — nu dintr-o decizie, ci fiindcă `motion.svelte.js` exporta doar
  duratele. `fade`, `sosire` și `plecare` rămâneau pe implicitul Svelte, care e
  **liniar**. (`fly` și `slide` au deja `cubicOut` — verificat, nu se ating.)
  **`svelte/easing` NU exportă un `cubicBezier` generic**, deci curba se rezolvă
  local (Newton-Raphson + înjumătățire), verificată față de o eșantionare
  parametrică independentă.
- **Bifarea.** Zborul dura 240ms, comiterea venea pe `setTimeout(160)`: rândul era
  **teleportat înapoi în ecran** la opacitate 1, ca apoi `plecare` să-l împingă din
  nou afară. Ultimul lucru pe care îl vedeai nu era plecarea, era revenirea. Acum
  comiterea așteaptă `transitionend`, cu cronometru de rezervă — sub
  `reduced-motion` durata e 0, iar o tranziție de durată zero nu emite eveniment.
- **Foaia.** `trasY = 0` la ridicarea degetului punea revenirea **cu arc** (care are
  voie să depășească) peste ieșirea care cobora foaia: prima jumătate a ieșirii se
  anula singură și se citea ca lag de atingere. Voalul se stingea în 120ms, când
  foaia mai avea ~170px de coborât. **Voalul ține obiectul, deci pleacă odată cu el
  sau după el — niciodată înainte.** Deblocarea derulării așteaptă acum sfârșitul
  ieșirii; altfel `window.scrollTo` mișca pagina din spate sub o foaie încă vizibilă.
- **Tabul.** `startViewTransition` pornea `import()` fără să-l aștepte, deci
  tranziția se termina pe schelet — iar scheletul are aceeași formă pentru Calendar,
  Planificator și Calculator. Routerul nu știe să încarce module (`lazyCache` e în
  App), deci App își **înregistrează** încărcătorul prin `setPreincarcaRuta`, iar
  `navigate` îl așteaptă cu o cursă de 180ms.
- **Staggerul.** Scara `nth-child` se oprea la 8: cardurile 9–12 aveau întârziere 0
  și **soseau primele** — ordinea văzută era inversul ordinii din listă. Indexul vine
  acum de la element. **Variabila se numește `--celula`, nu `--i`:** `--i` înseamnă
  deja „rândul benzii" în Calendar, iar proprietățile custom se moștenesc.
- **Apăsarea.** Durata era tokenizată, adâncimea nu — patru valori scrise de mână.
  `.ts-rand` se strângea cu 0,5% (sub pragul vizibil), `.status-pill` cu 8%. Acum
  `--press-scale` .97 și `--press-scale-sm` .93; nimic nu-și mai alege singur
  adâncimea.

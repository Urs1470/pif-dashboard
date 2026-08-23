<script>
  // ===== BARA DE SUS (doar desktop) =====
  //
  // AURORA, 2026-08-23. Inainte, navigatia de desktop era o coloana lipita in
  // stanga (`Sidebar.svelte`, sters). Handoff-ul „sticla cu muchie-lentila" o
  // aduce sus, ca o bara plutitoare de sticla peste care trece continutul —
  // `design/handoff-aurora/design/Ecran Acasa.dc.html`.
  //
  // CE S-A PASTRAT DIN COLOANA, fiindca nu tinea de estetica:
  //  - `.pilula` — tenta rutei active e UN SINGUR obiect care ALUNECA, nu un
  //    fundal care se stinge intr-un loc si se aprinde in altul. Doar ca acum
  //    aluneca pe ORIZONTALA. `audit_navigare` o masoara (sectiunea 7), si
  //    cauta exact `.pilula` si `.rute [data-pilula]` — numele nu se schimba.
  //  - marca cu APASARE LUNGA: in aplicatia Android nu exista bara de adresa,
  //    deci asta e singurul mod de a porni jurnalul de pe aparat (`lib/urma.js`).
  //  - `FaraRetea`: singurul semn ca aplicatia e offline. Prototipul nu-l are,
  //    fiindca prototipul e o fotografie a unui ecran sanatos.
  //  - `ComutaTema` cu cele TREI moduri (auto/deschis/inchis). Prototipul comuta
  //    doar intre doua si ar sterge modul „Sistem".
  //  - `<a href>` + `use:link` + `aria-current`. In prototip elementele de
  //    navigatie sunt `<span title>` — adica desen, nu navigatie.
  //
  // MARCA E ALT SUBIECT. Aici s-a pus semnul nou (cerc + sinusoida) fiindca el
  // se vede pe ecran; dar `frontend/public/favicon.svg`, tila de asset si
  // iconita Android inca poarta semnul vechi (PWM) si NU se pot schimba din
  // acelasi pas — au hexul scris, nu tokenuri. Vezi `design/handoff-aurora/`.
  import { Search } from '@lucide/svelte'
  import ComutaTema from './ComutaTema.svelte'
  import FaraRetea from './FaraRetea.svelte'
  import { router, link } from '../../lib/router.svelte.js'
  import { apasareLunga } from '../../lib/apasareLunga.js'
  import { sticla } from '../../lib/sticla.js'
  import { urmaActiva, porneste as pornesteUrma } from '../../lib/urma.js'
  import { toast } from '../../stores/ui.svelte.js'

  let { deschideCautarea = () => {} } = $props()

  // ORDINEA E CEA DIN `ORDINE_NAV` (App.svelte), fiindca din ea iese SENSUL
  // tranzitiei de pagina: mai la dreapta in bara -> continutul soseste din
  // dreapta. Doua ordini diferite ar face ca aceeasi navigare sa alunece
  // intr-un sens pe telefon si in celalalt pe desktop.
  const items = [
    { path: '/', label: 'Acasă' },
    { path: '/projects', label: 'Proiecte' },
    { path: '/tasks', label: 'Taskuri' },
    { path: '/plan', label: 'Planificator' },
    { path: '/calendar', label: 'Calendar' },
    { path: '/departament', label: 'Departament' },
    { path: '/calculator', label: 'Calculator' },
  ]

  function isActive(path) {
    if (path === '/') return router.path === '/'
    return router.path.startsWith(path)
  }

  const rutaActiva = $derived(items.find((i) => isActive(i.path))?.path ?? null)

  // ===== CE SPATIU OCUPA NAVIGATIA =====
  //
  // Doua variabile, acelasi tipar ca inainte („un singur scriitor per variabila",
  // ca `--nav-sens` in App si `--kb` in Modal), doar ca acum bara nu mai ocupa
  // LATIME, ci INALTIME:
  //   --sidebar-w : 0 — nu mai exista coloana. Cinci locuri isi socotesc pozitia
  //                 din ea (App, Modal, TrageReincarca, Urma); cu 0 devin toate
  //                 corecte fara sa fie atinse.
  //   --dock-h    : 0 — pe desktop nu exista bara de jos. Opt locuri isi socotesc
  //                 distanta de jos din ea.
  //   --bara-h    : cat sa se rezerve SUS ca primul rand de continut sa nu intre
  //                 pe sub bara. Se masoara, nu se scrie: bara e plutitoare, deci
  //                 rezerva e `top + inaltime + aer`, nu doar inaltimea.
  //
  // Se sterg la demontare, conditionat: ordinea montare/demontare intre cele doua
  // navigatii nu e garantata, iar o stergere oarba ar putea sterge exact valoarea
  // pe care dockul tocmai a masurat-o. Aceeasi garda, simetric, in `Dock.svelte`.
  let barEl = $state(null)
  let inaltime = $state(0)

  $effect(() => {
    const st = document.documentElement.style
    st.setProperty('--sidebar-w', '0px')
    st.setProperty('--dock-h', '0px')
    return () => {
      if (st.getPropertyValue('--dock-h') === '0px') st.removeProperty('--dock-h')
      if (st.getPropertyValue('--sidebar-w') === '0px') st.removeProperty('--sidebar-w')
    }
  })

  $effect(() => {
    // 14px de sus (pozitia barei) + inaltimea ei + `--space-lg` de aer.
    const rezerva = inaltime ? 14 + inaltime + 24 : 0
    document.documentElement.style.setProperty('--bara-h', rezerva + 'px')
    return () => document.documentElement.style.removeProperty('--bara-h')
  })

  // ===== TENTA RUTEI ACTIVE ALUNECA (pe orizontala acum) =====
  // Slotul care poarta tenta e MARCAT in markup (`data-pilula`), nu cautat dupa
  // `.active`: o cautare dupa clasa ar gasi si un rand care doar seamana.
  let pilula = $state({ x: 0, w: 0, r: '', gata: false })
  let pilulaAsezata = $state(false)
  let amMasurat = false   // NEreactiv: citit in efectul care scrie `pilula`

  function masoaraPilula() {
    const slot = barEl?.querySelector('[data-pilula]')
    if (!slot) { pilula.gata = false; return false }
    // `offsetLeft` se masoara fata de cutia de PADDING a lui `offsetParent` —
    // exact reperul fata de care se aseaza si un copil absolut cu `left: 0`.
    pilula.x = slot.offsetLeft
    pilula.w = slot.offsetWidth
    // Raza se CITESTE din slot: o a doua copie a regulii s-ar desincroniza.
    pilula.r = getComputedStyle(slot).borderRadius
    pilula.gata = true
    return true
  }

  $effect(() => {
    router.path
    if (!barEl) return
    const are = masoaraPilula()
    if (are && !amMasurat) {
      amMasurat = true
      // Un cadru fara tranzitie, ca PRIMA asezare sa nu alunece din stanga — ar
      // arata ca o navigare care n-a avut loc.
      requestAnimationFrame(() => { pilulaAsezata = true })
    }
  })

  // Latimea barei se schimba cu fereastra, iar etichetele se re-aseaza. Fara
  // reMasurare, tenta ar ramane pe pozitia veche.
  $effect(() => {
    if (!barEl) return
    const ro = new ResizeObserver(() => masoaraPilula())
    ro.observe(barEl)
    return () => ro.disconnect()
  })

  // JURNALUL DE PE APARAT SE PORNESTE DE PE MARCA, CU APASARE LUNGA. Vezi nota
  // din antetul fisierului si `lib/urma.js`.
  function comutaUrma() {
    const acum = !urmaActiva()
    pornesteUrma(acum)
    toast(acum ? 'Urmă pornită — deschide o foaie, apoi apasă „Urmă”' : 'Urmă oprită', 'success')
    window.dispatchEvent(new CustomEvent('pif-urma'))
  }
</script>

<header class="bara sticla sticla-bara" bind:this={barEl} bind:clientHeight={inaltime}
        use:sticla={{ spec: '150px 74px' }} aria-label="Navigație principală">
  <a href="/" class="brand" use:link title="TORQA"
     use:apasareLunga={{ actiune: comutaUrma }} oncontextmenu={(e) => e.preventDefault()}>
    <!-- SEMNUL: o sinusoida de o perioada inscrisa intr-un cerc — simbolul de
         sursa alternativa. Trecerile prin zero cad exact pe axa (x = 20, 32, 44),
         amplitudini egale sus si jos. Coordonatele sunt cele din
         `design/handoff-aurora/assets/torqa-logomark.svg`, care e varianta
         canonica; prototipul de ecran poarta o versiune mai veche, cu raza 15 si
         trecerile la 22/32/42. Aici semnul ia `--accent`, deci URMEAZA TEMA. -->
    <svg class="brand-semn" width="40" height="40" viewBox="0 0 64 64" aria-hidden="true">
      <g fill="none" stroke="var(--accent)" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 32a18 18 0 1 0 36 0 18 18 0 1 0-36 0" stroke-width="5" />
        <path d="M20 32c4-11.33 8-11.33 12 0s8 11.33 12 0" stroke-width="4.2" />
      </g>
    </svg>
  </a>

  <nav class="rute">
    <!-- Tenta rutei active. Primul copil, ca sa fie clar ca sta DEDESUBT; e
         absoluta, deci nu intra in flexul listei. -->
    <span class="pilula" class:gata={pilula.gata} class:asezata={pilulaAsezata}
          style="--px:{pilula.x}px; --pw:{pilula.w}px; --pr:{pilula.r}"
          aria-hidden="true"></span>
    {#each items as item (item.path)}
      <a
        href={item.path}
        use:link
        onclick={(e) => e.currentTarget.blur()}
        class="ruta"
        class:active={isActive(item.path)}
        data-pilula={rutaActiva === item.path ? '' : undefined}
        aria-current={isActive(item.path) ? 'page' : undefined}
      >{item.label}</a>
    {/each}
  </nav>

  <div class="actiuni">
    <FaraRetea />
    <!-- Cautarea si-a pierdut randul cu numele ei odata cu coloana; scurtatura
         ramane scrisa in `title`, ca sa nu dispara de tot. -->
    <button class="b-btn" onclick={deschideCautarea} aria-label="Caută (Ctrl+K)" title="Caută — Ctrl K">
      <Search size={17} strokeWidth={1.5} />
    </button>
    <ComutaTema varianta="buton" sens="jos" />
  </div>
</header>

<style>
  .bara {
    /* Perechea lui `cadru-doc` de la dock: bara de navigatie e CADRU, nu
       continut, deci nu intra in instantaneul `root` si nu ia alunecarea de
       ±10px la fiecare schimbare de ruta. `audit_navigare` verifica numele
       (sectiunea 6) — daca il schimbi aici, schimba-l si acolo. */
    view-transition-name: cadru-bara;
    position: fixed;
    top: 14px;
    left: calc(18px + var(--safe-left));
    right: calc(18px + var(--safe-right));
    height: 54px;
    z-index: var(--z-sticky);
    display: flex;
    align-items: center;
    gap: var(--space-md);
    /* Asimetric: marca respira in stanga, butoanele rotunde au nevoie doar de 8. */
    padding: 0 var(--space-sm) 0 var(--space-md);
    border-radius: var(--radius-full);
    /* Fondul, muchia si umbra vin din `.sticla` (global.css) — containerul NU are
       `background` propriu, altfel straturile n-ar avea ce refracta. */
  }

  .brand {
    /* FARA inaltime scrisa: cutia o da SVG-ul de 40px dinauntru. 40 nu e o treapta
       din scara de controale (28/32/38/46) si nici n-ar trebui sa fie — marca e
       logotip, nu control, acelasi motiv pentru care `--font-brand` sta si el in
       afara scarii de text. */
    flex: none;
    display: flex;
    align-items: center;
    color: var(--text);
    text-decoration: none;
  }
  .brand-semn { flex: none; display: block; }

  .rute {
    /* `relative` NU e decor: `.pilula` e absoluta, iar `--px` vine din
       `slot.offsetLeft`. Amandoua trebuie sa se raporteze la ACEEASI cutie,
       altfel tenta se aseaza langa ruta activa, nu pe ea (masurat: pastila la
       211px, slotul la 121px). */
    position: relative;
    /* Etichetele stau GRUPATE la mijloc, nu distribuite pe toata latimea: o
       navigatie intinsa pe 1400px n-ar mai fi un obiect, ar fi o linie de titluri. */
    flex: 1;
    min-width: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2xs);
    height: 100%;
  }

  /* TENTA E UN SINGUR OBIECT CARE ALUNECA. Sta SUB randuri, deci fiecare ruta are
     nevoie de context propriu ca sa picteze deasupra (vezi `.ruta`).
     Materialul e cel al sticlei: o pastila de sticla IN sticla. */
  .pilula {
    position: absolute;
    top: 50%;
    left: 0;
    width: var(--pw, 0px);
    height: var(--ctrl-sm);
    border-radius: var(--pr, var(--radius-full));
    background: var(--glass-fill);
    box-shadow: var(--glass-sel);
    transform: translate(var(--px, 0px), -50%);
    opacity: 0;
    pointer-events: none;
    z-index: 0;
  }
  /* Vizibila abia dupa prima masuratoare — pana atunci ar fi lipita de marginea
     din stanga, adica exact de unde n-are voie sa alunece. */
  .pilula.gata { opacity: 1; }
  /* ELAN. Tenta traverseaza o distanta pe care O VEZI, deci are voie sa arate ca
     a avut viteza: depaseste cu ~4% si revine. Doar `transform` si `width`:
     OPACITATEA ramane pe curba de vopsea — o depasire pe opacitate se citeste ca
     palpait, si e chiar regula scrisa in tokens („effects — NICIODATA"). */
  .pilula.asezata {
    transition: transform var(--dur-arc-elan) var(--ease-arc-elan),
                width var(--dur-arc-elan) var(--ease-arc-elan),
                opacity var(--dur-fast) var(--ease);
  }

  .ruta {
    /* Peste pastila. Vezi nota de la `.pilula`. */
    position: relative;
    z-index: 1;
    display: inline-flex;
    align-items: center;
    height: var(--ctrl-sm);
    padding: 0 var(--space-14);
    border-radius: var(--radius-full);
    /* `--text-secondary`, nu `--text-dim`: un drum inactiv trebuie sa se poata
       CITI, nu doar ghici — e singura harta a aplicatiei. */
    color: var(--text-secondary);
    font-size: var(--font-small);
    font-weight: var(--fw-normal);
    letter-spacing: var(--tracking-normal);
    text-decoration: none;
    white-space: nowrap;
    transition: var(--transition-colors), transform var(--dur-press) var(--ease);
  }
  @media (hover: hover) {
    .ruta:hover { color: var(--text); }
  }
  .ruta:active { color: var(--text); transform: scale(var(--press-scale)); }
  /* Activ = doar cerneala si greutate; fondul il poarta `.pilula`. */
  .ruta.active { color: var(--text); font-weight: var(--fw-medium); }
  .ruta.active:active { transform: none; }

  .actiuni {
    flex: none;
    display: flex;
    align-items: center;
    gap: var(--space-xs);
  }

  .b-btn {
    width: var(--ctrl-sm);
    height: var(--ctrl-sm);
    display: grid;
    place-items: center;
    border-radius: var(--radius-full);
    background: none;
    color: var(--text-secondary);
    transition: var(--transition-pressable);
  }
  @media (hover: hover) {
    .b-btn:hover { color: var(--text); background: var(--bg-hover); }
  }
  .b-btn:active { transform: scale(var(--press-scale)); }

  /* Bara nu exista pe telefon — acolo navigatia e antetul plus dockul de jos.
     Regula e o PLASA: `App.svelte` oricum nu randeaza componenta sub 768px
     (`ecran.telefon`), dar intre schimbarea mediei si re-randare exista un cadru. */
  @media (max-width: 768px) {
    .bara { display: none; }
  }
</style>

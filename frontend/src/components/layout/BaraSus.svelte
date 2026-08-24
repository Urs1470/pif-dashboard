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
  import { router, link, navigate } from '../../lib/router.svelte.js'
  import { apasareLunga } from '../../lib/apasareLunga.js'
  import { sticla } from '../../lib/sticla.js'
  import { urmaActiva, porneste as pornesteUrma } from '../../lib/urma.js'
  import { toast } from '../../stores/ui.svelte.js'
  import { creeazaArc } from '../../lib/arc.js'

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
  // `x` si `w` NU mai stau in `$state`: le poarta ARCUL, care scrie direct in
  // element la fiecare cadru (vezi `lib/arc.js`). Aici rămân doar cele care se
  // schimba rar — raza, citita din slot, si `gata`, care aprinde opacitatea.
  let pilula = $state({ r: '', gata: false })
  let pilulaAsezata = $state(false)
  let pilulaEl = null
  let amMasurat = false   // NEreactiv: citit in efectul care aseaza pastila

  // ARCUL TENTEI. Inainte era o tranzitie CSS pe `transform` si `width`, cu
  // `--ease-arc-elan`. Arata identic cat timp porneste din repaus — dar la
  // RETARGETARE in zbor o tranzitie CSS reporneste de la viteza ZERO, si se vedea
  // o clipa de stagnare inainte sa se intoarca (masurat: +8.7, +5.6, +3.2, +1.2
  // px/cadru in directia VECHE, dupa ce apasasei deja alt tab).
  // Un arc preia viteza pe care o avea. Durata si bounce dau exact varful
  // esantionului livrat (1.0384), deci caracterul nu se schimba — vezi nota din
  // `lib/arc.js` pentru de ce .298 si nu .28.
  const arcPilula = creeazaArc({
    durata: 0.38,
    bounce: 0.298,
    scrie: ({ x, w }) => {
      if (!pilulaEl) return
      if (x !== undefined) pilulaEl.style.setProperty('--px', x + 'px')
      if (w !== undefined) pilulaEl.style.setProperty('--pw', w + 'px')
    },
  })

  /** Duce tenta pe un slot. `instant` = fara miscare (prima asezare, redimensionare). */
  function aseazaPe(el, instant = false) {
    arcPilula.tinteste('x', el.offsetLeft, { instant })
    arcPilula.tinteste('w', el.offsetWidth, { instant })
    // Raza se CITESTE din slot: o a doua copie a regulii s-ar desincroniza.
    pilula.r = getComputedStyle(el).borderRadius
    pilula.gata = true
  }

  function masoaraPilula({ instant = false } = {}) {
    // CINE APASA ULTIMUL ARE DREPTATE. Garda sta AICI, nu la apelant, fiindca sunt
    // doi apelanti: efectul pe `router.path` SI `ResizeObserver`-ul. Cat timp ai
    // apasat o ruta la care routerul inca n-a ajuns, orice re-masurare ar citi
    // slotul rutei VECHI si ar trage tenta inapoi la ea — masurat pe cadre: pleca
    // spre tabul abandonat si se aseza acolo, ~200ms. Ruta veche aterizeaza dupa
    // ce ai apasat deja alta, fiindca `startViewTransition` o tine in aer ~180ms.
    if (intentia && rutaActiva !== intentia) return false
    intentia = null
    const slot = barEl?.querySelector('[data-pilula]')
    if (!slot) { pilula.gata = false; return false }
    // `offsetLeft` se masoara fata de cutia de PADDING a lui `offsetParent` —
    // exact reperul fata de care se aseaza si un copil absolut cu `left: 0`.
    // Prima asezare e mereu INSTANT: altfel tenta ar aluneca din marginea din
    // stanga la incarcarea paginii, ca si cum ai fi navigat.
    aseazaPe(slot, instant || !amMasurat)
    return true
  }

  // TENTA URMEAZA INTENTIA, NU ATERIZAREA RUTEI.
  //
  // Masurat pe cadre: apesi un tab, iar la 206ms apesi altul — tenta CONTINUA spre
  // primul, se aseaza acolo, si abia pe la 450ms pleaca inapoi. Doua sute de
  // milisecunde in care ecranul se duce unde nu mai vrei.
  // Cauza: pastila urmarea `router.path`, care se schimba abia cand se APLICA ruta
  // — iar intre clic si aplicare sta `startViewTransition`, care ingheata pagina
  // veche (vezi cursa de 180ms din `lib/router.svelte.js`).
  // Unde te duci se stie insa din clipa apasarii. Deci tinta se pune ACUM, din
  // elementul apasat; efectul de mai jos o re-masoara cand ruta chiar aterizeaza,
  // pe aceleasi valori, deci nu se vede nicio a doua miscare.
  // WWDC23 „Animate with springs": miscarea trebuie sa raspunda gestului, nu sa-l
  // astepte. Perechea acestei reparatii — pastrarea VITEZEI la retargetare — e
  // facuta de arcul de mai sus.
  // `intentia` e ruta pe care ai APASAT-O ultima data, cat timp routerul inca n-a
  // ajuns la ea. NEreactiva: o citeste efectul de mai jos, si daca ar fi reactiva
  // l-ar reporni singura.
  let intentia = null

  function tinteste(el, cale) {
    if (!el) return
    intentia = cale
    aseazaPe(el)
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
    // INSTANT: o redimensionare de fereastra nu e o navigare. Daca ar aluneca,
    // tragerea marginii ferestrei ar arata ca si cum ai fi apasat un alt tab.
    const ro = new ResizeObserver(() => masoaraPilula({ instant: true }))
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

  // ===== SCURTATURI DE NAVIGARE (doar desktop) =====
  //
  // Ion, 2026-08-24: „ceva gen ctrl+shift+ sageata dreapta sau stanga, sau gaseste
  // tu ceva mai comod". Sunt doua feluri de drum, si merita amandoua:
  //
  //   Alt+1 … Alt+7      sari DIRECT la o ruta, in ordinea din bara
  //   Ctrl+Shift+←/→     vecinul din stanga / din dreapta, cu roata la capete
  //
  // DE CE `Alt+cifra` SI NU `Ctrl+cifra`, desi a doua e conventia din Slack si din
  // editoare: in browser `Ctrl+1..9` e a BROWSERULUI (schimba taburile lui) si nu
  // poate fi luata dintr-o pagina obisnuita. `Alt+cifra` e libera. In aplicatia
  // Android nu conteaza — acolo nu exista tastatura fizica si nici bara asta.
  // `Alt+←/→` ar fi fost mai scurta pentru vecin, dar aia e inapoi/inainte in
  // istoricul browserului; de aceea ramane perechea propusa de Ion.
  //
  // TAC CAT TIMP SCRII. `Ctrl+Shift+←/→` selecteaza cuvant cu cuvant intr-un camp,
  // iar `Alt+cifra` poate ajunge intr-un editor. Daca focusul e pe ceva in care se
  // scrie, scurtatura nu exista.
  //
  // Tenta se muta prin acelasi drum ca la clic (`tinteste`), nu asteptand ruta —
  // vezi nota de la ea.
  const SCRIS = /^(INPUT|TEXTAREA|SELECT)$/

  function seScrie(t) {
    return !!t && (t.isContentEditable || SCRIS.test(t.tagName))
  }

  function duLa(cale) {
    // Elementul exista in bara, deci tenta poate tinti INAINTE sa aterizeze ruta.
    const el = barEl?.querySelector('.ruta[href="' + cale + '"]')
    tinteste(el, cale)
    navigate(cale)
  }

  function scurtaturi(e) {
    if (seScrie(e.target) || !items.length) return

    if (e.altKey && !e.ctrlKey && !e.metaKey && e.key >= '1' && e.key <= '9') {
      const i = Number(e.key) - 1
      if (i < items.length) {
        e.preventDefault()
        duLa(items[i].path)
      }
      return
    }

    if (e.ctrlKey && e.shiftKey && !e.altKey &&
        (e.key === 'ArrowLeft' || e.key === 'ArrowRight')) {
      e.preventDefault()
      const acum = items.findIndex((x) => x.path === rutaActiva)
      const de_la = acum === -1 ? 0 : acum
      const pas = e.key === 'ArrowRight' ? 1 : -1
      // Cu roata: de pe ultima ruta, „dreapta" duce la prima. Sapte drumuri intr-un
      // inel se parcurg mai repede decat intr-o linie cu doua capete moarte.
      duLa(items[(de_la + pas + items.length) % items.length].path)
    }
  }

  $effect(() => {
    window.addEventListener('keydown', scurtaturi)
    return () => window.removeEventListener('keydown', scurtaturi)
  })
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
    <!-- `--px`/`--pw` NU sunt in binding: le scrie arcul, direct in element, la
         fiecare cadru. Un `$state` scris de 60 de ori pe secunda ar pune tot
         arborele componentei pe drumul de reactualizare degeaba. -->
    <span class="pilula" bind:this={pilulaEl}
          class:gata={pilula.gata} class:asezata={pilulaAsezata}
          style="--pr:{pilula.r}"
          aria-hidden="true"></span>
    {#each items as item, i (item.path)}
      <a
        href={item.path}
        use:link
        onclick={(e) => { tinteste(e.currentTarget, item.path); e.currentTarget.blur() }}
        class="ruta"
        title="{item.label} (Alt+{i + 1})"
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
  /* NUMAI OPACITATEA MAI E TRANZITIE CSS. Poziția si latimea le poarta ARCUL din
     `lib/arc.js`, fiindca o tranzitie CSS nu poate reprezenta o viteza initiala si
     reporneste de la zero cand tinta se schimba in zbor.
     Opacitatea RAMANE pe curba de vopsea — o depasire pe opacitate se citeste ca
     palpait, si e chiar regula scrisa in tokens („effects — NICIODATA"). */
  .pilula.asezata {
    transition: opacity var(--dur-fast) var(--ease);
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

# Bară laterală în loc de dock, pe desktop

*2026-08-23. Cerut de Ion: „vreau doar să trecem la sidebar în loc de dock", cu structura și
așezarea paginilor neschimbate.*

## Ce s-a schimbat

Peste 768px navigația e o coloană fixă de 220px în stânga, mereu vizibilă, care **împinge**
conținutul (`padding-left: var(--sidebar-w)` pe `.app-main`). Sub 768px nu se schimbă
absolut nimic: dockul de jos rămâne cum era — cinci sloturi, foaia „Mai mult", ascunderea la
tastatură, pastila care alunecă.

Antetul a dispărut de pe desktop. Marca, comutatorul de temă și chipul „Fără rețea" au urcat
în bară; pe telefon antetul rămâne neatins.

## De ce

**Pe desktop, în repaus, aplicația nu arăta nicio navigație.** Dockul de acolo era ascuns
implicit (decizia din [2026-07-03](2026-07-03-dock-autohide-v4.md)) și ieșea doar când
împingeai cursorul în ultimii 48px de jos. Harta aplicației era un lucru pe care trebuia
să-l *chemi*, și trebuia să știi că poți. O bară laterală nu se cheamă.

**Antetul de desktop ținea două obiecte și 1200px de gol.** Marca în stânga, un buton de temă
în dreapta. 56px de înălțime pentru atât — pe un Planificator care numără zile în coloane și
pe un Calendar care numără șapte, înălțimea aia se vede.

**Etichetele încap.** În dock, pe desktop, cele șapte rute erau șapte iconițe fără nume
(numele trăia doar în `title`). Într-o coloană de 220px fiecare rută își scrie numele, iar
căutarea devine un rând care își arată scurtătura — singurul loc din aplicație unde `Ctrl+K`
e scris undeva.

**Nu e o întoarcere din capriciu.** Aplicația a avut sidebar înainte de
[redesignul „Bento"](2026-07-02-redesign-bento.md), care l-a înlocuit cu dockul plutitor.
Ce s-a învățat între timp e că dockul e răspunsul corect pe **telefon** — unde degetul mare
ajunge jos — și răspunsul greșit pe desktop, unde nu există deget și nici margine de ecran la
care să te oprești. Deci nu una dintre ele peste tot, ci fiecare unde e bună.

## Cum se ține geometria, ca să nu mintă

Opt locuri își socoteau distanța de jos din `--dock-h`, iar șapte își socoteau marginea de sus
din `--header-height`. Dacă bara laterală ar fi apărut lângă ele, toate ar fi rezervat spațiu
pentru obiecte care nu mai există: 68px de gol sub fiecare pagină și 56px de decalaj la fiecare
antet lipicios.

Nu s-au atins cele cincisprezece locuri. S-au mutat **valorile**:

- `Sidebar.svelte` scrie `--dock-h: 0px` cât timp e montată — exact ca `Dock.svelte`, care își
  scrie înălțimea măsurată. Cine ține navigația ține și cât spațiu ocupă ea.
- `--header-height` devine `0px` peste 768px, într-un `@media` din `tokens.css`. Nu e o valoare
  de complezență: pe desktop antetul chiar nu există, deci înălțimea lui chiar e zero.

Ștergerea lui `--dock-h` la demontare e **condiționată** de faptul că valoarea de pe `<html>`
e încă a componentei care pleacă. Ordinea montare/demontare între cele două navigații nu e
garantată, iar o ștergere oarbă ar fi șters exact înălțimea pe care cealaltă tocmai a scris-o —
și `--dock-h` ar fi căzut pe implicitul de 68px, fără ca nimic să se fi schimbat pe ecran.

## Ce s-a rupt și nu se vedea

Un audit pe cinci lentile (fixat-la-stânga, `--dock-h`, antet, scripturi, lățime) a dat 56 de
semnalări, din care **16** au trecut de o pasă de respingere. Patru erau reale:

1. **`Urma.svelte`** — butonul jurnalului de pe aparat stă la `left: 16px` cu `z-index` 2001,
   adică peste orice altceva. Bara e la `--z-sticky` = 200. Butonul ar fi pictat fix peste
   rândurile de navigație. Acum pornește după `var(--sidebar-w)`.
2. **`Modal.svelte`** — pragul de la care panoul lateral **împinge** lista în loc s-o acopere
   se citea din `window.innerWidth`, care nu știe de bară. Pe o fereastră de 1200px, bara ia
   220 din stânga și panoul până la 560 din dreapta: rămâneau 420px de listă împinsă — sub
   lățimea la care un rând de task mai e citibil, adică exact cazul pe care pragul de 1100
   fusese pus să-l oprească. Acum se scade lățimea reală a barei.
3. **`audit_navigare.py`** — proba rulează la 1280x800, deci pe desktop. Șase aserțiuni
   căutau `.dock`, `.dock-pilula` și `cadru-antet`; toate ar fi devenit `null` și proba ar fi
   picat pe instrument, nu pe aplicație. Contractul e neschimbat, doar axa s-a rotit: ce se
   măsura pe `left` se măsoară pe `top`.
4. **`TrageReincarca.svelte`** — arcul e centrat cu `left: 50%` pe fereastră; pe un laptop cu
   ecran tactil (peste prag, deci cu bară) ar fi ieșit cu 110px la stânga de centrul a ceea ce
   tragi.

Restul de 40 au fost respinse: erau reguli din blocuri de telefon, sau voaluri de modal care
oricum acoperă tot ecranul dinadins.

## Contrastul a devenit verificabil

`tokens.css` își scrie singur în comentarii rațiile pe care le-a calibrat — și tot el notează
că nimic nu le verifică: *„`audit_design.py` verifică paritatea tokenurilor între teme,
NICIODATĂ contrastul"*. Rolul care a căzut ultima oară (accentul ca text pe o suprafață) nu era
numit de nicio regulă scrisă, și cădea numai pe tema pe care Ion o folosește în hală.

`scripts/audit_contrast.py` măsoară acum perechile care chiar apar pe ecran, pe amândouă
temele, rezolvând aliasurile și cele cinci `color-mix()` exact ca browserul (oklab și sRGB).
Prima rulare a reprodus, cifră cu cifră, toate valorile scrise de mână în comentarii — deci
unealta e de încredere. Pe prima paletă candidat a prins imediat o pereche la 4,45 față de
pragul de 4,5, invizibilă cu ochiul.

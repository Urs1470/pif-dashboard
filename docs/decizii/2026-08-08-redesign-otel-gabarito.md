# Redesign complet: oțel, Gabarito, o singură axă de culoare (2026-08-08)

Handoff-ul „Design audit complet dashboard" (10 prototipuri `.dc.html` + `DIRECTIA-DE-DESIGN.md`).
Ce s-a schimbat la nivel de sistem și **de ce**, ca să nu se re-deschidă din instinct:

- **Accentul amber a plecat.** Nu ca stil: amberul Bento, movul „info/purple" și „service"
  erau a **doua și a treia culoare de brand**, iar `--accent` și `--warning` erau *exact
  același hex*. Acum accentul e unul, iar restul culorilor spun doar **stare** (restant,
  făcut). Ce era codificat cromatic și nu mai e: identitatea proiectului în Calendar,
  locația (Site/Sediu), tipul PIF/Service, weekendul.
- **Cele ~25 de nume vechi de token sunt ALIASURI**, nu roluri în plus (`--warning` →
  `--danger`, `--purple`/`--info`/`--service-*` → accent, `--text-faint` → `--text-dim`).
  Aliasul rezolvă prin `var()`, deci urmează automat tema țintei — de aceea
  `audit_design.py` scutește aliasurile de regula de paritate între teme (R7); a cere o a
  doua definiție ar însemna exact a doua sursă de adevăr pe care regula o previne.
  `--accent-on-subtle` e literal `--accent-deep`, deci regula „text pe tentă ia adâncul" se
  repară singură în cele ~20 de locuri care o încălcau.
- **Fonturi: Gabarito (text) + DM Mono (cifre)**, self-hosted în `static/fonts/`. Inter,
  Space Grotesk și JetBrains Mono au ieșit. Subsetul `latin` are â/î, `latin-ext` are ă/ș/ț
  — **verificat pe `cmap`, nu presupus**; împreună acoperă româna.
- **Scara: 12 · 13 · 15 · 21 · 25.** Pe telefon **pagina crește** (28) și corpul crește (16);
  rândul rămâne 15, fiindcă el poartă densitate. `--font-h3` s-a colapsat la 15/600
  („etichetă de pagină"), nu la 17 — 17 nu mai există în scară.
- **Raze: 8 chip · 10 control/rând · 14 suprafață · 20 foaie · cerc doar bifa.** Nimic între.
- **Elevația se citește din UMBRĂ, nu din linii peste tot** — două niveluri. Deci: fondul
  redevine o culoare (glowurile radiale de sub fiecare card au plecat), `backdrop-filter`
  a plecat de pe header, dock, paletă și voaluri, iar cardurile pierd chenarul.
- **Mișcare: 90 apăsare · 220 element · 280 suprafață**, o curbă standard și **un singur**
  arc (`cubic-bezier(.34,1.35,.42,1)`). Staggerul e 40ms, plafonat la **șase** celule.
  **`reduced-motion` nu mai înseamnă durată ZERO, ci 120ms fără translație** — o tranziție
  de durată zero nu emite `transitionend`, iar bifarea se sincronizează pe el.

**RÂNDUL DE TASK E UN SINGUR OBIECT, în trei liste.** `/tasks`, boardul „Astăzi" și tabul
Taskuri al proiectului au acum aceeași geometrie, până la pixel: 46px înălțime, gap 12,
**termenul pironit într-o coloană de 46px cu valoare pe fiecare rând**, acțiunile cu **text**
(nu iconițe mute) apărute la hover **la stânga** termenului, titlul cedează lățimea.
Coloana de 16px a mânerului de reordonare e **rezervată pe toate rândurile**, ca absența să
nu pară greșeală. Listele n-au rânduri-card: un separator de 1px cu marjă laterală.
Ce a plecat de pe rând: categoria, indicatorul de notiță, săgeata de desfacere.
(Fracția de pași plecase și ea; s-a întors pe 2026-08-15 — vezi mai jos.)
Dacă schimbi forma, schimb-o în **toate trei** — sursa e `Tasks.svelte`.

**O singură cale de adăugare per ecran:** linia cu Enter pe desktop, butonul mare cu plus pe
telefon (`/tasks`). Pe „Astăzi" rămâne compozitorul, fiindcă acolo e al boardului.

**Căutarea trăiește într-un singur loc: paleta din dock.** Câmpurile locale de pe `/tasks` și
`/projects` au plecat — același gest („caut un task") avea două unelte cu rezultate diferite,
iar paleta le găsește pe toate și aterizează pe rând (`?focus=`). Pe telefon lupa rămâne în
cap, fiindcă dockul de acolo n-o are.

**Panoul face loc, nu acoperă.** În Calendar coloana panoului apare **odată cu el**, iar la
încărcare **nu e selectată nicio zi** — grila trece de la 127 la 176px pe zi, exact pragul de
la care eticheta unei lucrări se poate citi în bara ei. „Proiecte fără perioadă" a urcat din
panou în capul paginii: e o **sursă**, nu un detaliu al zilei, și în panou nu se vedea tocmai
când n-aveai nicio zi deschisă.

**Tabul „Calcule" a plecat din pagina proiectului — și cu el, butonul „Proiect" din
Calculator.** Handoff-ul cerea doar tabul, dar tabul era **singurul cititor** al lui
`POST /api/proiecte/<id>/calcule`: scos singur, ar fi rămas un buton care salvează într-un loc
pe care nu-l mai poți deschide. Ruta de API și datele existente sunt neatinse — dacă
funcția se reia, se reia cu ambele capete.

**Un singur toast pe ecran, 4s.** Cel înlocuit **se comite** (`onCommit`), nu se aruncă:
altfel rândul rămânea șters din interfață și neșters din bază.

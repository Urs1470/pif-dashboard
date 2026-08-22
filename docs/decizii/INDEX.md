# Decizii — index

Arhiva raționamentelor. Fiecare fișier păstrează textul **integral**, așa cum a fost scris
atunci: nu se rescrie, nu se rezumă — valoarea lui e că spune *de ce*, nu *ce*.

Un `grep` pe fișierul ăsta trebuie să fie de-ajuns ca să știi dacă merită deschis un fișier.
Cârligul spune **ce s-a decis**. Ordinea: cea mai nouă sus.

Unde aceeași decizie a fost scrisă de două ori (o dată în `CLAUDE.md`, o dată în
`docs/memory/MEMORY.md`), ambele texte stau în **același** fișier, sub `## Din CLAUDE.md` și
`## Din MEMORY.md`. Nu s-a ales între ele: sunt două unghiuri, scrise în momente diferite.

**Ce e aici e istorie, nu contract.** Regula în vigoare se citește din cod și din invarianții
din `CLAUDE.md`; un fișier de aici poate descrie o stare depășită (multe chiar o fac — vezi
toată epoca Gantt din iulie, ștearsă pe 2026-08-15).

## 2026-08-22

- [2026-08-22 Pornirea rece se filmează](2026-08-22-pornirea-rece-se-filmeaza.md) — `screenrecord` pe telefon, lansat prin atingere reală; două cadre de ecran gol pe care nicio deducție nu le-a găsit; regula: un cadru cu o stare care n-a existat e real.

## 2026-08-21

- [2026-08-21 Verifică instrumentul înainte de subiect](2026-08-21-verifica-instrumentul-inainte-de-subiect.md) — trei din patru „defecte" de pe mobil erau ale sondei; `:active` nu se vede prin atingere sintetică, orice regulă CSS are `cssRules` truthy, iar un control care răspunde sub 25 ms nu are nevoie de semn de apăsare.
- [2026-08-21 Foile cu tastatura: o singură sosire](2026-08-21-foile-cu-tastatura-o-singura-sosire.md) — tastatura se PREVEDE (înălțimea știută, pusă pe `<html>` înainte de randare), o singură sursă `--kb` (editorul nu mai fixează bare), clicul de la ridicarea degetului nu e al foii, foaia taskului cu schelet în ≤120 ms, taskul din proiect în foaie/panou. Audit nou: `audit_tastatura.py`.

## 2026-08-17

- [2026-08-17 Handoff „Rafinare mobil": ce s-a luat, ce s-a respins](2026-08-17-handoff-rafinare-mobil-triaj.md) — auditul de 31 de interacțiuni descria PROTOTIPUL: 10 din 17 „rupturi" erau deja reparate în cod. Luat: `--ease-iesire` (ieșirea accelerează, nu frânează) + trecerea lină de temă. Respins: pragul fix de 118px și două curbe în plus. Apăsarea lungă, respinsă întâi, a fost livrată în paralel de altă sesiune — cu obiecția rezolvată, nu ignorată.

## 2026-08-15

- [2026-08-15 Sfera se comută cu degetul, pe toată pagina](2026-08-15-sfera-gest-toata-pagina.md) — gestul de sferă urcă de pe bara de 46px pe `.page`; excepția: un gest pornit pe un rând rămâne al rândului.
- [2026-08-15 Banda de pregătire a plecat din Planificator](2026-08-15-banda-pregatire-plecat.md) — obiectul derivat „pregătire" scos de pe pistă; faza `pregatire` a unei perioade reale rămâne.
- [2026-08-15 Taburile din pagina de proiect](2026-08-15-taburi-proiect-deschidere.md) — a cincea eroare de măsurare din aceeași familie: Svelte 5 rulează tranzițiile prin Web Animations, deci `animationstart` nu le vede.
- [2026-08-15 Perioada e o șină la baza rândului](2026-08-15-perioada-sina-baza-randului.md) — perioada devine șină de 4px la baza rândului cu pastilă la cap; taskul rămâne reper de o zi. 0 text tăiat pe toate cele cinci orizonturi.
- [2026-08-15 Comutarea sferei nu e o schimbare de pagina](2026-08-15-comutarea-sferei-nu-e-navigare.md) — sfera trăiește în interogare, deci comutarea naviga; acum schimbă starea fără să reîncarce pagina.
- [2026-08-15 Șapte variante de mișcare, alese de Ion din simulări](2026-08-15-sapte-variante-de-miscare.md) — separarea Material 3 `spatial` (are voie să depășească) vs `effects` (niciodată): tokenurile `--dur-arc` / `--ease-arc`.
- [2026-08-15 Contorul de pași se întoarce pe rând](2026-08-15-contor-pasi-pe-rand.md) — ridică interdicția E1: inel + fracție lângă titlu, în toate cele patru liste; fără culoare, fără mono.
- [2026-08-15 Ganttul din pagina de proiect a plecat, cu tot cu server](2026-08-15-gantt-proiect-sters.md) — tabul „Gantt" devine „Perioade"; rutele rămase fără cititor au fost șterse odată cu el.
- [2026-08-15 „Avem un răspuns" nu e „avem rânduri"](2026-08-15-raspuns-gol-vs-fara-raspuns.md) — garda `loading && items.length === 0` confunda „încă n-am primit nimic" cu „răspunsul e gol".
- [2026-08-15 Memoria supraviețuiește repornirii (local-first)](2026-08-15-memoria-supravietuieste-repornirii.md) — cache persistat, ca pagina să se deschidă cu date vechi în loc de schelet.

## 2026-08-14

- [2026-08-14 Ce se animă pe telefon, inventariat din `getAnimations()`](2026-08-14-inventar-animatii-telefon.md) — `transition: background` e o capcană în 21 de locuri: prescurtarea animează și `background-image`, și `background-position`.
- [2026-08-14 „Apare scheletul?" era întrebarea greșită](2026-08-14-rama-fara-continut.md) — ce se vedea nu era schelet, era rama paginii noi fără conținut.
- [2026-08-14 Pornirea pe telefon și scheletele rămase](2026-08-14-pornirea-pe-telefon-schelete.md) — localhost minte: auditul pe `127.0.0.1` nu reproduce ce vede telefonul.
- [2026-08-14 Schimbarea de tab: trei animații au devenit una](2026-08-14-schimbarea-de-tab.md) — la fiecare apăsare se jucau trei animații de intrare peste aceiași pixeli; și datele nu mai mor cu componenta.
- [2026-08-14 „APK-ul e semnat" nu înseamnă „cu cheia bună"](2026-08-14-apk-semnat-cu-cheia-buna.md) — autoritatea e amprenta pinuită din `scripts/build-apk.ps1`, nu `apksigner verify`.
- [2026-08-14 Handoff „interacțiuni, modale și mișcare" (T1–T17)](2026-08-14-handoff-interactiuni-modale.md) — `stiva.varf++` chemat dintr-un `$effect` = buclă (citire + scriere a aceleiași stări reactive).

## 2026-08-10

- [2026-08-10 Integrarea Google Calendar a plecat de tot (v40)](2026-08-10-google-calendar-sters-v40.md) — blueprint, rute, cele patru situri de sincronizare și cheile din DB; rămâne doar feedul `.ics`.

## 2026-08-08

- [2026-08-08 Redesign complet: oțel, Gabarito, o singură axă de culoare](2026-08-08-redesign-otel-gabarito.md) — accentul amber pleacă, culoarea devine stare; ~25 de nume vechi de token rămân ALIASURI; Gabarito + DM Mono; elevația se citește din umbră.
- [2026-08-08 Planificator: înălțimea vine din împachetare](2026-08-08-planificator-inaltime-impachetare.md) — `packRows` măsoară bara PLUS titlul care iese din ea; antetul e grosier peste fin (săptămâni peste zile).
- [2026-08-08 Un singur editor pentru toate câmpurile lungi](2026-08-08-editor-unic-campuri-lungi.md) — `EditorLung.svelte`: închiderea COMITE, cu „Anulează" în toast; nu există buton care aruncă.
- [2026-08-08 Fereastra de notificări: patru reglaje](2026-08-08-fereastra-notificari.md) — reglajele sunt ale REGULII, nu ale canalului, deci se arată și pe web; comutatorul „scadente" chiar comută ceva.
- [2026-08-08 Perioada se întinde, iar vecinul se dă la o parte](2026-08-08-perioada-se-intinde-vecinul-se-muta.md) — același `loc|client` = alipire, altfel vecinul e împins cu o zi lucrătoare, propagat; pe telefon gestul e oprit.
- [2026-08-08 Android: fără rețea, barele sistemului, plecarea pe teren](2026-08-08-android-fara-retea-bare-plecare.md) — `errorPath` local, bare transparente, și alarma de plecare pe canal propriu, fără butoane.

## 2026-08-07

- [2026-08-07 Acasă își spune ziua; docul nu mai pierde trei rute](2026-08-07-acasa-ziua-si-docul.md) — salutul stătea în bara ascunsă sub 768px, deci pe telefon nu scria nicăieri ce zi e.
- [2026-08-07 Tipografia: șase trepte și o regulă de familii](2026-08-07-tipografie-sase-trepte.md) — 8 trepte, 4 greutăți, 7 trackinguri reduse la o scară; regula „dacă textul se poate traduce, nu e mono". (Scara a fost rescrisă pe 2026-08-08.)
- [2026-08-07 O excepție care nu se potrivește e mai rea decât una lipsă](2026-08-07-exceptie-de-audit-care-nu-se-potriveste.md) — `ACCEPTATE` din `audit_mobil.py` se potrivește pe SUBȘIR; cheia rămăsese pe vechiul selector.
- [2026-08-07 Un gest = un verb; gestul duce la ALEGEREA zilei](2026-08-07-gest-un-verb-alegerea-zilei.md) — stânga execută un verb în loc să deschidă un panou de acțiuni; verbul e un date picker, nu „mâine".
- [2026-08-07 Subtaskul: atingerea bifează, glisarea șterge, undo peste tot](2026-08-07-subtask-atingere-glisare-undo.md) — cea mai mare țintă făcea lucrul cel mai rar (redenumirea); acum redenumirea e pe apăsare lungă.
- [2026-08-07 Grila de proiecte: culoarea rămâne doar pe ce variază](2026-08-07-grila-proiecte-culoarea.md) — tipul PIF/Service avea două culori pentru același fapt în aceeași pagină; acum nu mai are fill.
- [2026-08-07 Modalul se deschide cu datele în mână](2026-08-07-modal-cu-datele-in-mana.md) — caseta se dimensiona pe lista goală și sărea 146px; plafon de 250ms + schelet; `scale` trece pe `--ease`.
- [2026-08-07 Taskurile de proiect se grupează după termen](2026-08-07-taskuri-proiect-grupate-pe-termen.md) — era singura listă care nu grupa, deci un restant putea sta al patrulea.
- [2026-08-07 Tura 13: mișcarea nu se reinventează, se pune unde lipsea](2026-08-07-tura13-miscare-unde-lipsea.md) — patru locuri neprinse: deschiderea paginii, schimbarea lunii, panoul zilei, benzile din planificator.
- [2026-08-07 Perioadele se trag cu mâna (pointer events, nu HTML5 DnD)](2026-08-07-perioade-trase-cu-mana.md) — HTML5 DnD nu declanșează la deget, nu poate exprima redimensionarea; ziua APUCATĂ e cea care ajunge sub cursor. (Răsturnat parțial pe 2026-08-08: la deget gestul e oprit.)
- [2026-08-07 Cheia VAPID: RAW, nu PEM](2026-08-07-cheia-vapid-raw.md) — `py_vapid.from_string` cere fix 32 de octeți, deci orice PEM crapă înainte de orice trimitere.
- [2026-08-07 Severitatea pleacă de pe muchie](2026-08-07-severitatea-pleaca-de-pe-muchie.md) — muchia colorată de 3px purta cinci înțelesuri și distingea două; severitatea trece pe inelul bifei + textul termenului.
- [2026-08-07 Mișcarea: o curbă, un ceas, o adâncime](2026-08-07-miscarea-o-curba-un-ceas.md) — tranzițiile Svelte nu foloseau `--ease` (erau liniare); bifarea aștepta un `setTimeout` în loc de `transitionend`.
- [2026-08-07 Panoul taskului se deschide cu datele în mână](2026-08-07-panoul-taskului-cu-datele-in-mana.md) — `slide` măsoară o singură dată, la primul cadru, deci măsura starea „Se încarcă…".
- [2026-08-07 „S-a făcut" e despre PERIOADĂ, nu despre proiect (v39)](2026-08-07-s-a-facut-e-despre-perioada-v39.md) — butonul din panoul zilei închidea proiectul; acum scrie `implementari.confirmata`.
- [2026-08-07 Notificări push: o notificare PER TASK](2026-08-07-push-o-notificare-per-task.md) — task personal, deschis, fără termen, mai vechi de 2 zile → o notificare cu „Făcut"/„Azi" pe ea.
- [2026-08-07 Poarta de verificare dădea un verdict FALS](2026-08-07-poarta-verdict-fals.md) — `shutil.which` vede doar PATH-ul moștenit, deci `npm` „nu exista"; trei cauze în lanț.
- [2026-08-07 Unde stau Node și Playwright pe mașina asta](2026-08-07-unde-stau-node-si-playwright.md) — node e portabil, în `~\Tools\`, doar în PATH-ul de utilizator din registru.
- [2026-08-07 `test_suite.py` crăpa pe Windows înainte de orice test](2026-08-07-test-suite-encoding-windows.md) — `Path.read_text()` fără `encoding` cade pe cp1252 la prima ghilimea românească.

## 2026-08-04

- [2026-08-04 Sfera nu e filtru: comutator segmentat, nu chip-uri](2026-08-04-sfera-nu-e-filtru.md) — sfera schimbă ÎN CE LUME ești; filtrul alege ce subset vezi din ea.
- [2026-08-04 Butonul Google nu mai e chip](2026-08-04-buton-google-iconita-fantoma.md) — o acțiune de setări era desenată ca un filtru: aceeași haină pentru lucruri diferite.
- [2026-08-04 Credențialele Google se pot lipi din UI](2026-08-04-credentiale-google-din-ui.md) — secretele nu circulă prin chat și sesiunile remote n-au SSH; `PUT /api/google/credentials`. (Plecat cu v40.)
- [2026-08-04 Google Calendar API: push instant pentru taskuri personale](2026-08-04-google-calendar-api.md) — OAuth server-side + sincronizare la creare/editare/ștergere. (Plecat cu v40.)
- [2026-08-04 Taskuri personale: `global_tasks.sfera` (v38), nu tabelă nouă](2026-08-04-sfera-taskuri-personale-v38.md) — o tabelă separată ar fi dublat recurența, subtaskurile și CRUD-ul; fiecare interogare trebuie să filtreze.

## 2026-07-31

- [2026-07-31 HERMES.md șters + runda de design ca sistem](2026-07-31-hermes-sters.md) — briefingul agentului Hermes iese; partea de design devine secțiune în CLAUDE.md.
- [2026-07-31 Mișcarea la standardul gestului: `sosire` + `--ease-spring`](2026-07-31-sosire-si-ease-spring.md) — inventar de mișcare; două lipsuri, ambele la sosirea rândurilor.
- [2026-07-31 Aprofundarea consolidării: stările, nu doar suprafața](2026-07-31-consolidare-starile.md) — metoda: taie serverul (500) sub fiecare pagină și fotografiază ce rămâne.
- [2026-07-31 Consolidare UI/UX: unde s-a abătut codul de la propriile reguli](2026-07-31-consolidare-abateri-de-la-reguli.md) — șapte abateri măsurate contra `tokens.css`, niciuna cu vreo eroare aruncată.
- [2026-07-31 Dock-ul pe telefon: ținte de 56px și ascundere la derulare](2026-07-31-dock-telefon-56px.md) — modelul barei de adresă din browser.
- [2026-07-31 Dock-ul ține CINCI lucruri pe telefon](2026-07-31-dock-cinci-lucruri-pe-telefon.md) — și o rută scoasă din navigație trebuie să rămână cu un drum.
- [2026-07-31 Glisarea spre dreapta își spune intenția din primul milimetru](2026-07-31-glisarea-isi-spune-intentia.md) — problema nu era culoarea, era MOMENTUL în care apare semnalul.

## 2026-07-30

- [2026-07-30 Culoarea unui proiect era o proprietate a PAGINII](2026-07-30-culoarea-e-a-proiectului.md) — aceeași lucrare avea o culoare în Calendar și alta în Planificator; paleta se re-rezolvă, nu se ajustează pe bucăți.
- [2026-07-30 Rândul bifat pleacă vizibil](2026-07-30-randul-bifat-pleaca-vizibil.md) — animația e cinci linii; drumul până la ea a scos două capcane Svelte care o suprimau în tăcere.
- [2026-07-30 Trecere de meșteșug pe rândul de task](2026-07-30-mestesug-rand-de-task.md) — o singură axă de culoare, și cod care nu se putea randa.
- [2026-07-30 Marginea din stânga a rândului de task, și invariantul „azi"](2026-07-30-marginea-din-stanga-si-azi.md) — pe 375px titlul începea la x=96, un sfert din ecran, pe fiecare rând.
- [2026-07-30 Lista de taskuri e o listă DE FĂCUT](2026-07-30-lista-de-facut.md) — gruparea la CITIRE pe termen (Restante → … → Fără termen), termen scris relativ, adăugare + planificare într-un singur gest.
- [2026-07-30 A doua trecere pe telefon: măsurată, nu privită](2026-07-30-a-doua-trecere-pe-telefon.md) — patru reguli scrise pentru telefon care nu se aplicau nici pe telefon; naște `audit_mobil.py`.
- [2026-07-30 Rândul de task pe telefon: o linie + glisare](2026-07-30-rand-task-pe-telefon.md) — `lib/glisare.js` ca acțiune Svelte refolosită de toate listele; Planificatorul își recapătă timpul.
- [2026-07-30 Aplicația pe telefon: „fără compromisuri"](2026-07-30-aplicatia-pe-telefon.md) — audit automat pe fiecare rută la 375×812 și 360×740; headerul „sticky" nu se lipise niciodată.
- [2026-07-30 Trei câmpuri scoase din formularul de proiect (v36)](2026-07-30-trei-campuri-scoase-v36.md) — `nr_contract`, `pm`, `data_incepere`; ultima dubla prima perioadă, deci banda se calculează din perioade.
- [2026-07-30 O perioadă de mai multe zile e UN element](2026-07-30-perioada-un-singur-element.md) — nu N bucăți: benzi peste celule cu `grid-column: span`, nume scris o dată pe felie de săptămână.
- [2026-07-30 Un proiect închis se oprește în ziua ÎNCHIDERII](2026-07-30-proiect-inchis-ziua-inchiderii-v35.md) — reperul e `data_finalizare` (v35), nu ziua în care te uiți; tăierea e doar la citire.

## 2026-07-27

- [2026-07-27 Calendarul, în locul celor trei liste](2026-07-27-calendarul-in-locul-listelor.md) — o întrebare spațială („unde sunt marți") primea trei liste de text; și cum arată o zi: o bară per lucrare, bandă stabilă, antet de înălțime fixă.
- [2026-07-27 Două perioade, zero deadline-uri (v30)](2026-07-27-perioade-nu-deadline-v30.md) — deadline-ul pleacă (2 proiecte din 18 îl aveau); în loc, `implementari.faza` și `urmatoarea`.
- [2026-07-27 Restrângere de scop (v28)](2026-07-27-restrangere-de-scop-v28.md) — dashboard-ul nu mai dublează wiki-ul: `parametri_master`, `fault_codes`, `echipamente`, `atasamente` șterse.
- [2026-07-27 Date calendaristice (v29)](2026-07-27-date-calendaristice-v29.md) — nu stocăm niciodată o dată pe care nu o putem citi; `norm_date()` la granița scrierilor, `probleme[]` la citire.
- [2026-07-27 Proprietatea suprafețelor de planificare](2026-07-27-proprietatea-suprafetelor.md) — Calendar = perioadele, Planificator = taskurile, ProjectDetail = ambele; vocabularul perioadă vs termen.
- [2026-07-27 Două statusuri de proiect (v31)](2026-07-27-doua-statusuri-proiect-v31.md) — `in_asteptare`, `blocat`, `anulat` erau în cod și pe zero rânduri; rămân `pregatire` și `finalizat`.
- [2026-07-27 Cod scos pentru că nu putea fi folosit (v32)](2026-07-27-cod-scos-v32.md) — `tasks.faza` era o funcție pe jumătate (nicio formă n-o putea seta); `GET /api/dashboard/home` rămăsese fără cititor.
- [2026-07-27 Un task are O SINGURĂ dată (v33)](2026-07-27-un-task-o-singura-data-v33.md) — `data_planificata` pleacă; a pune un task pe azi = a-i da termenul de azi.
- [2026-07-27 Taskul e făcut sau nu (v34)](2026-07-27-task-facut-sau-nefacut-v34.md) — statusul era deja mort, prioritatea era saturată (54% „urgent"); severitatea se citește din termen.
- [2026-07-27 Planul de departament (`/departament`)](2026-07-27-planul-de-departament.md) — plan extern încorporat, nu importat; cheia de acces stă în `app_settings`, niciodată în git.

## 2026-07-15

- [2026-07-15 Taskuri = repere cu etichetă](2026-07-15-taskuri-repere-cu-eticheta.md) — taskurile lui Ion sunt aproape toate de o zi, deci pe luni întregi barele deveneau dungi de 3px.
- [2026-07-15 Gantt per-proiect refăcut ca listă read-only + timeline](2026-07-15-gantt-proiect-lista-readonly.md) — taskurile se gestionează în tabul Taskuri, fără procentaje. (Ganttul a plecat de tot pe 2026-08-15.)
- [2026-07-15 Gantt per-proiect simplificat (calm by default)](2026-07-15-gantt-proiect-calm-by-default.md) — toggle „Avansat" ascunde uneltele PM. (Ganttul a plecat de tot pe 2026-08-15.)

## 2026-07-03

> Epoca Gantt + prima construcție a Planificatorului și a dock-ului. Aproape tot ce descriu
> fișierele de mai jos a fost desfăcut între timp (Ganttul de proiect a plecat pe 2026-08-15,
> autohide-ul dockului pe 2026-07-31, exporturile odată cu Ganttul). Se păstrează pentru
> raționament, nu ca descriere a aplicației de azi.

- [2026-07-03 Perioade de implementare pe Planificator + fix Gantt empty-state](2026-07-03-perioade-pe-planificator.md) — o perioadă pe un proiect fără taskuri nu se vedea deloc.
- [2026-07-03 Perioade de implementare per proiect (Site / Sediu EGB)](2026-07-03-perioade-implementare-per-proiect.md) — naște tabela `implementari` (schema v26), separată de taskuri.
- [2026-07-03 Gantt de proiect: cele 4 îmbunătățiri + faze](2026-07-03-gantt-imbunatatiri-si-faze.md) — logo + semnătură în PDF, drag/resize, grupare pe faze (WBS).
- [2026-07-03 Excel Gantt real, nu tabel + grilă](2026-07-03-excel-gantt-real.md) — coloane pe ZI, bandă de lună merged deasupra.
- [2026-07-03 Gantt fazele 3 și 4: dependențe cu săgeți + export](2026-07-03-gantt-faza3-si-faza4.md) — săgeți SVG peste corpul graficului, creare prin link-mode.
- [2026-07-03 Gantt faza 2: view-ul (tab în ProjectDetail)](2026-07-03-gantt-faza2-view.md) — layout two-pane GanttProject-style.
- [2026-07-03 Gantt faza 1: schema + backend](2026-07-03-gantt-faza1-schema.md) — fundația (schema v24): start/sfârșit, progres, dependențe, milestones.
- [2026-07-03 FIX export PDF Planificator: pagină albă + portrait](2026-07-03-fix-export-pdf-planificator.md) — A4 portrait ≈ 794px cade sub breakpointul care ascunde graficul.
- [2026-07-03 Planificator: export PDF + rail „Backlog" + drag-to-schedule](2026-07-03-planificator-export-pdf-backlog.md) — export = print-to-PDF client, nu reportlab.
- [2026-07-03 Planificator: orizonturi lungi + coloane adaptive](2026-07-03-planificator-orizonturi-lungi.md) — 7/14/30/90/180 zile; sub 31z pe zi, sub 92z pe săptămână, altfel pe lună.
- [2026-07-03 Planificator faza 2: drag & drop pe swimlane](2026-07-03-planificator-faza2-drag-drop.md) — corpul barei mută spanul, marginile mută o muchie.
- [2026-07-03 Feature nou „Planificator" (swimlane operațional 14 zile)](2026-07-03-planificator-feature-nou.md) — ales de Ion dintre 3 schițe de Gantt; ruta `/plan`.
- [2026-07-03 Dock FIX pe mobil (fără autohide)](2026-07-03-dock-fix-mobil.md) — pe touch dockul e mereu vizibil; se ascunde doar cât e deschisă tastatura.
- [2026-07-03 Verificare mobil + fixuri](2026-07-03-verificare-mobil.md) — trecere Playwright la 390px pe toate paginile.
- [2026-07-03 Două bug-uri în agenda „Astăzi"](2026-07-03-bug-uri-agenda-astazi.md) — amânarea seta doar data de plan, lăsând termenul în trecut → task veșnic restant.
- [2026-07-03 P5 consistență design](2026-07-03-p5-consistenta-design.md) — glifele Unicode înlocuite cu Lucide/SVG.
- [2026-07-03 P6 calitate/UX](2026-07-03-p6-calitate-ux.md) — ErrorState + retry pe listele care înghițeau erorile și arătau fals „gol".
- [2026-07-03 Șters backend Checklist PIF + Template-uri + Hermes AI](2026-07-03-sters-checklist-template-hermes.md) — backend complet fără niciun UI în SPA.
- [2026-07-03 Faza 2 quick-wins, batch 2](2026-07-03-quickwins-batch2.md) — B3/B4/B5/B6: manual + coduri de eroare pe cardul echipamentului.
- [2026-07-03 Dock autohide v4: pur pe cursor](2026-07-03-dock-autohide-v4.md) — ascuns implicit, apare doar cât cursorul e jos; toată logica de scroll a plecat.
- [2026-07-03 Dock autohide: fix `:focus-within`](2026-07-03-dock-autohide-fix-focus-within.md) — linkul rămâne focusat după click, deci dockul nu se mai ascundea niciodată.
- [2026-07-03 Faza 2 quick-wins, batch 1](2026-07-03-quickwins-batch1.md) — codurile de parametri din echipament devin clickabile.
- [2026-07-03 Glosar Rich/Extra: diacritizare completă](2026-07-03-glosar-diacritizare.md) — agenți read-and-rewrite, unul per fișier, în locul unei pase scriptate.
- [2026-07-03 Dock autohide v3 (reveal la cursor jos)](2026-07-03-dock-autohide-v3.md) — pragul de viteză era prea strict, deci nu se ascundea niciodată.
- [2026-07-03 Diacritice subsistem Calculator (partea 2)](2026-07-03-diacritice-calculator.md) — inclusiv cele trei overlay-uri de glosar.
- [2026-07-03 Diacritice complete + DatePicker portal](2026-07-03-diacritice-complete-datepicker.md) — regula: NU se ating valorile, cheile de status, `familie`/`producator`, cheile localStorage.

## 2026-07-02

- [2026-07-02 Redesign complet „Bento"](2026-07-02-redesign-bento.md) — temă dark warm + amber, Inter/Space Grotesk/JetBrains Mono, Dock plutitor în locul Sidebar + BottomNav. (Înlocuit integral pe 2026-08-08 de redesignul „oțel".)

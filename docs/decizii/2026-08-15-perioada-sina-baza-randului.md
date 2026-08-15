# Perioada e o șină la baza rândului (2026-08-15)

## Din CLAUDE.md

Ion: *„nu arată prea bine"* — despre perioadele de o zi, tăiate. Simptomul era însă al unei
structuri: perioada e un **interval** care ținea toată înălțimea rândului și își scria numele
**înăuntru**, pe aceiași pixeli orizontali pe care îi voiau titlurile taskurilor, care sunt
**puncte**. Măsurat pe aplicație (14z, pistă 1034px, 4 proiecte, 6 perioade, 13 taskuri):

| orizont | text tăiat | text peste text | benzi fără nume |
|---|---|---|---|
| 7z | 3 | 0 | 0 |
| 14z | **4** | 0 | 0 |
| 30z | 1 | 0 | **4** |
| 3L / 6L | 0 | **2** | 0 |

Cazul cel mai rău: „Sediu EGB · Verificare parametri" primea **36px din 183** — 20% din nume.
Iar înălțimea venea din **coliziuni**, nu din conținut: eticheta benzii ținea rândul întâi al
împachetării, deci un proiect cu patru taskuri ajungea la 112px.

**Perioada e CONTEXT („unde ești"), taskul e CONȚINUT („ce ai de făcut").** Contextul coboară
într-o **șină de 4px la baza rândului** — convenția baseline din Gantt, unde bara subțire e
contextul și cea groasă e subiectul. Aceeași gramatică o folosesc uneltele de resurse (Float,
Resource Guru țin disponibilitatea într-o bară separată de rezervări). Rezultat măsurat:
**0 tăiat și 0 suprapus pe toate cele cinci orizonturi**, graficul de la 410 la 371px.

- **Fâșia de jos e goală, deci eticheta are loc.** Locul se scrie într-o **pastilă la capul
  șinei** („⚲ Site" / „🏢 Sediu EGB"), iar golul se măsoară până la **începutul perioadei
  următoare** — deci pastila încape întreagă sau nu se randează. Nu există stare în care se
  taie. Vechiul prag (`BANDA_TEXT_MIN`, în **procente din fereastră**) pretindea că măsoară
  dacă textul încape, dar procentele nu spun nimic despre pixeli: o zi la 14z trece pragul de
  6,5% fie că înseamnă 48px, fie 95.
- **`packRows(repere, [])`** — `blocate` a rămas fără obiect. De aici vine scăderea de
  înălțime, fără să dispară nimic de pe ecran.
- **`.lane-track` se ancorează sus** (`flex-start`), nu se mai centrează. Înălțimea rândului
  poate fi dictată de coloana din stânga când ea cere mai mult decât formula (nume + contor +
  chip, ~25px); centrată, surplusul cobora stiva în fâșia șinei — măsurat, exact așa apărea o
  suprapunere între eticheta unei perioade și titlul unui task.
- **Pastila merge cu zilele.** Fereastra pornește mereu din azi, deci o deplasare **în curs**
  e tăiată la stânga; ancorată la capul *vizibil* al șinei, pastila stă pe muchia ferestrei și
  avansează pe măsură ce perioada se scurtează — rămâne citibilă exact când ești pe teren.
  **Pe `clipL` șina nu primește terminator**, altfel capul ei ar afirma că deplasarea începe azi.
- **Șina e plină, nu tentă.** Pe 4px înălțime o tentă de 10% nu se mai vede — aceeași
  compensare de suprafață pe care pista mobilă (34px) o făcea deja, desenând banda mai tare
  decât desktopul.
- **Au plecat:** `.impl-band.lung`, `.ib-out`, `.ib-txt`, `.ib-zile`, `flip` de pe bandă,
  `BANDA_TEXT_MIN`, `BANDA_ZILE_MIN`, și `--h-stiva` n-a mai rămas cu niciun consumator în CSS.
- **Capcană, pista mobilă:** `.mp-track .impl-band` trebuie să-și **reafirme `height: auto` și
  `display: flex`**. Cu `top`, `bottom` și `height` puse toate trei, `height` câștigă — deci
  fără prima, blocul de 34px de pe telefon devenea șina de 4px; fără a doua, iconița cădea în
  colțul din stânga-sus, fiindcă baza nouă nu mai e flex.

## Din MEMORY.md

- **2026-08-15 (6) — Perioada e o sina la baza randului (Planificator).** Ion, despre
  perioadele de o zi: „acum este taiata si nu arata prea bine". Simptomul era al
  structurii: perioada e un INTERVAL care tinea toata inaltimea randului si isi scria
  numele INAUNTRU, pe aceiasi pixeli pe care ii voiau titlurile taskurilor, care sunt
  PUNCTE.
  - **Masurat pe aplicatia care ruleaza** (14z, pista 1034px): 4 din 6 etichete taiate —
    „Sediu EGB · Verificare parametri" primea **36px din 183**; la 30z patru benzi
    ramaneau MUTE; la 3L/6L doua etichete se tipareau UNA PESTE ALTA (bug in productie,
    `.ib-out` iesea din banda fara sa verifice daca locul e liber). Dupa: **0 taiat, 0
    suprapus pe toate cele cinci orizonturi**, grafic 410 -> 371px.
  - **Pragul in PROCENTE era greseala de fond.** `BANDA_TEXT_MIN = 6.5` pretindea ca
    masoara daca textul incape, dar procentele nu spun nimic despre pixeli: o zi la 14z
    trece pragul fie ca inseamna 48px, fie 95. Acum golul se masoara in px, pana la
    inceputul perioadei urmatoare — pastila incape intreaga sau nu se randeaza.
  - **`packRows(repere, [])`** — `blocate` a ramas fara obiect, si de aici vine scaderea
    de inaltime. **`.lane-track` se ancoreaza sus**, altfel surplusul cerut de coloana din
    stanga coboara stiva in fasia sinei.
  - **Capcana:** `.mp-track .impl-band` trebuie sa-si reafirme `height: auto` SI
    `display: flex` — cu top/bottom/height puse toate trei castiga `height`, iar baza noua
    nu mai e flex.
  - Detaliile si tabelul de masuratori: CLAUDE.md, „Perioada e o sina la baza randului".

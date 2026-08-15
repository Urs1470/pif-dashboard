# Lista de taskuri e o lista DE FACUT (2026-07-30)

## Din CLAUDE.md

Ion: *„taskurile sunt cele mai importante pentru mine pe mobil. Poti sa faci ca o
aplicatie de to do?"*

Ce lipsea nu era aspectul, ci **ordinea** si **drumul pana la actiune**.

- **Ordinea e informatie.** `/api/global-tasks` intoarce `ORDER BY created_at DESC`,
  adica ordinea in care le-ai scris. `lib/grupare.js` grupeaza la CITIRE dupa termen:
  **Restante → Azi → Mâine → Zilele astea → Mai târziu → Fără termen**, cu cap de
  grupa lipit si numar. „Fără termen" e ULTIMA cu buna stiinta — e sertarul, nu
  agenda; un task fara data nu e urgent prin faptul ca n-are data.
- **Termenul se scrie relativ** (`etichetaTermen`): „azi", „acum 3 zile", „vineri".
  Si nu se scrie deloc in grupele care l-au spus deja in cap.
- **Panoul de glisare e Azi · Mâine · Dată · Șterge**, la fel pe `/tasks` si in
  pagina de proiect. Planificarea e ce faci des cu un task; editarea titlului o faci
  o data. Nota si editarea stau in randul desfasurat.
- **Adaugarea si planificarea sunt un singur gest:** cat timp scrii, sub compozitor
  apar „Azi / Mâine / Alege data". Enter ramane „fara termen".
- **Bifarea se poate anula** (`toastUndo`) pe toate cele trei liste — pe telefon se
  bifeaza si prin glisare, deci si din greseala, iar randul pleaca intr-o sectiune
  inchisa.

Gruparea NU se aplica taskurilor de proiect: acolo randurile sunt o secventa de
lucru cu `ordine`, iar o regrupare dupa zi ar rupe tocmai ce le tine impreuna.

**Culoarea e rezervata severitatii.** Randul avea trei sisteme de culoare care se
bateau — severitatea (pe atunci bordura + termenul; azi inelul bifei + termenul,
vezi tura 9), mov (categoria), amber (subtaskuri,
recurenta, numele proiectului) — iar ierarhia iesea pe dos: indexul decorativ „01"
era 16px/700 colorat, deasupra titlului de 12.8px. Acum titlul e `--font-body`,
indexul e o fantoma, si singurul lucru colorat pe rand e TERMENUL. Pe boardul
„Astăzi" cele doua pastile („Restant", „Termen azi") au plecat: pe un board unde
totul e scadent azi sau restant, ele partitionau lista si atat, iar „Restant"
repeta in cuvinte ce spunea data rosie de langa. Ramane data, scrisa relativ.

**Vederea activa nu contine taskuri bifate.** `/api/global-tasks` adauga
`AND status != 'done'` cand nu ceri arhiva. Deci o sectiune „N finalizate" in
lista activa e cod care nu se poate randa (a existat, gardata pe o conditie
imposibila). Ce ai terminat se vede in „Arhivă", si starea goala o spune.

## Din MEMORY.md

- **2026-07-30 (7) — Taskurile se comporta ca o lista DE FACUT, nu ca un depozit.**
  Ion: „poti sa faci ca o aplicatie de to do". Ce lipsea nu era aspectul, ci ORDINEA
  si DRUMUL pana la actiune.
  **(1) Ordinea E informatie.** `/api/global-tasks` intoarce `ORDER BY created_at DESC`
  — ordinea in care le-ai scris. Pe ecran iesea: 30.07, 31.07, fara termen, 29.07
  (restant, rosu), fara termen. Adica randul care tipa era al patrulea. Acum
  `lib/grupare.js` grupeaza dupa termen: **Restante → Azi → Mâine → Zilele astea →
  Mai târziu → Fără termen**, cu cap de grupa lipit (`sticky`) si numar. „Fără termen"
  e ULTIMA cu buna stiinta: e sertarul, nu agenda.
  **(2) Termenul se scrie relativ** (`etichetaTermen`): „azi", „mâine", „acum 3 zile",
  „vineri", „12 aug". „30.07.2026" te pune sa calculezi la fiecare rand. Si NU se
  scrie deloc in grupele „Azi"/„Mâine"/„Fără termen" — capul a spus-o deja.
  **(3) Planificarea a urcat in gest.** Panoul de glisare avea Notă/Editează/Șterge,
  deci mutarea unui termen — cea mai deasa actiune de pe un task — costa patru
  atingeri prin modalul de editare. Acum panoul e **Azi · Mâine · Dată · Șterge**,
  identic pe /tasks si in pagina de proiect (doua liste cu acelasi rand n-au voie sa
  raspunda diferit la acelasi gest). Nota si editarea au coborat in randul desfasurat.
  Patru butoane, nu sapte: la 58px bucata, sapte n-ar mai fi lasat nimic din titlu.
  **(4) Adaugarea si planificarea sunt UN gest.** Cat timp ai text in compozitor apar
  chipurile „Azi / Mâine / Alege data"; Enter ramane „fara termen". Focusul ramane in
  camp dupa adaugare — intr-o lista de facut adaugi trei lucruri la rand.
  **(5) „Anulează" la bifat**, pe toate cele trei liste (Astăzi, Taskuri, proiect).
  Pe telefon se bifeaza si prin glisare, deci se bifeaza si din greseala, iar randul
  DISPARE intr-o sectiune inchisa. `toastUndo` exista deja din 2026-07 (era folosit
  doar la stergerea unui subtask).
  **(6) Croma de deasupra listei**, pe telefon: eticheta cartonasului si coloana
  „Agenda — 7 zile" au plecat (a doua e acum o copie a gruparii), cautarea se plieaza
  intr-o iconita de 44px, sageata de desfasurare a plecat de pe rand, iar categoria
  e text simplu — pastila mov era cel mai tare lucru de pe rand, mai tare decat
  titlul si decat termenul. Titlul are voie sa cada pe DOUA randuri: pe una singura,
  „Reinnoire certificat de acces in site Co…" nu spune la ce site.
  **Capcane prinse pe drum:** `.quick-add` era `flex-direction: row`, deci chipurile
  de zi se asezau LANGA camp si ieseau din ecran; `.sub-add-btn` n-avea `flex-shrink: 0`
  si se stringea la 12px (masurat); „sterge subtask" era `opacity: 0` pana la hover,
  adica invizibil pentru totdeauna pe touch; indexul mono renumara de la 01 in
  fiecare grupa („01, 01, 01, 02") pana l-am facut continuu.
  Verificat cu `scripts/audit_mobil.py`, care are acum si sectiunea „lista de facut"
  (12 verificari: gruparea, ordinea grupelor, adaugarea cu zi, mutarea din gest,
  „Anulează" dus si intors). **Gotcha de testare:** un gest sintetic din PointerEvent
  NU produce `click`-ul pe care il trimite browserul dupa ridicarea degetului — iar
  `glisare.js` inghite exact acel click. Fara el in test, steagul „tocmai am glisat"
  ramane ridicat si prima apasare pe un buton din panou e inghitita; arata identic cu
  „butonul nu functioneaza".

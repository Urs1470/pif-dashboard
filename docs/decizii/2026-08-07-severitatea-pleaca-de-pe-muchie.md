# Severitatea pleacă de pe muchie (tura 9, 2026-08-07)

Fiecare rând de task purta o dungă colorată de 3px pe muchia din stânga. Nu spunea
cât de urgent e: `dueColor()` ramifica în cinci, dar **`--accent` și `--warning` sunt
exact același hex** (`#ffb454`), iar ultimele două ramuri cădeau pe `--border-strong`
— culoarea bordurii pe care rândul o are oricum. Cinci ramuri, **două** lucruri
deosebibile: „azi" și „în două zile" erau literalmente același pixel.

Mai grav: aceeași muchie de 3px purta **cinci înțelesuri** în aplicație — severitatea
unui task, identitatea proiectului, locația, tipul unui toast, un citat. În pagina de
proiect un rând de task și unul de implementare stăteau unul sub altul cu aceeași
dungă: una spunea „urgent", cealaltă „proiectul X".

**Muchia colorată de 3px nu mai există nicăieri.** Nu s-a rezervat niciunui rol.
Verificat loc cu loc, în șase din șapte întrebuințări era a doua codificare a unui
lucru **deja spus** — de o iconiță colorată, de un fundal tentat, sau de banda plină
pe care o repeta în aceeași culoare. Ștergerea n-a scos informație, a scos duplicat.

- **Severitatea** = `dueRing()` (trei trepte) pe **inelul bifei** + pe **textul
  termenului**. Cercul e deja la marginea din stânga, deja rotund, și e chiar ținta
  pe care o apeși — culoarea devine invitație, nu etichetă. Ambele canale citesc
  **același `--ring`**, deci nu se pot desincroniza.
- **Neutrul e `--border`, NU `--border-strong`:** inelul în repaus trebuie să rămână
  exact bifa de dinainte, altfel fiecare rând neurgent s-ar schimba la vedere.
- **Hoverul ADAUGĂ un halou**, nu rescrie inelul — exact greșeala de la muchie, unde
  `:hover` ștergea `--sev` și trebuia reafirmat de mână în trei locuri.
- **Bifa era definită de cinci ori** (18/16/14/22px în trei fișiere, plus
  `.mcheck-gol` în Planificator). Acum o singură `.check-empty` în `global.css` —
  neschopat, fiindcă acolo trăiesc regulile puse din markup.
- **Identitatea** trece pe ce avea deja rândul: fill, iconiță, sau — în liste mixte —
  un punct de 6px. `.banda.inceput` din Calendar marchează începutul prin **rază**,
  nu prin culoare: banda e deja plină cu `var(--c)`.
- **Toastul e singurul care primea informație din dungă** (n-are nici iconiță, nici
  fill): o ia o iconiță Lucide în capul rândului.

**Geometrie:** bordura scade de la 3px la 1px, deci fiecare selector atins primește
înapoi în `padding` exact câți pixeli a pierdut. Fără asta, fiecare listă se
decalează față de antetul ei.

Textul suportă **o treaptă în plus** față de inel („mâine" rămâne scris, în gri):
un cuvânt poate ce un cerc de 2px nu poate.

`border-left: 3px` supraviețuiește **doar pe citate și callout-uri** în conținut de
notiță (`MarkdownView`, `RichTextEditor`, `.atentie` din Departament) — convenție
tipografică, nu cod de culoare.

# Planificatorul scos, ziua intreaga in Calendar (2026-08-26)

Ion: „cred ca vom ramane doar cu calendar. vom scoate planificatorul. nu am nevoie atat de
vizualizare taskuri."

## Ce s-a decis

`/plan` — swimlane-ul pe proiecte, cu cinci orizonturi, impachetare, coloana de restante si
export PDF — a plecat. `/api/plan` la fel. Ce a intrat in loc, in panoul zilei din Calendar:
o **lista** cu taskurile scadente in ziua aleasa. Nu bare, nu orizonturi, nu grupare pe
proiect — Ion a spus limpede ca nu vizualizarea ii lipsea.

Ruta veche nu duce in gol: `MUTATE` din `lib/router.svelte.js` o rescrie catre `/calendar` cu
`replaceState`, inainte de prima citire a hash-ului. Semnele de carte, aplicatia de pe telefon
(care isi tine ultima ruta si o cere la pornire) si notificarile vechi aterizeaza pe raspunsul
lor, nu pe o pagina alba.

## De ce nu s-a sters pur si simplu

Fiindca stergerea singura ar fi adancit defectul, nu l-ar fi inchis.

Masurat pe 25 august 2026, pe datele reale de pe `pif.iupif.org`: panoul zilei din Calendar
scria **„Liber."** — corect despre perioade, nu era nicio deplasare — in timp ce trei taskuri
erau scadente chiar in ziua aia (*De revăzut aplicațiile*, *De pregatit si de planificat
modificarile*, *Retragere deconturi 1710 lei*). Doua pagini, doua jumatati de adevar despre
aceeasi zi.

Planificatorul tinea jumatatea cu taskuri. Scos fara sa mutam nimic, „Liber." ar fi ramas
scris peste zile in care ai treaba — si ar fi disparut si ultimul loc din care puteai alege o
zi ca sa vezi ce e pe ea. Deci ordinea a fost: intai panoul, apoi stergerea.

Si cuvantul „Liber." si-a schimbat inţelesul odata cu ziua: acum apare doar cand nu e NICI
perioada, NICI task. Altfel ramanea exact minciuna de dinainte, cu raspunsul scris cu un
centimetru mai jos.

## Ce s-a pierdut cu buna stiinta

- **Citirea pe PROIECT** — care proiect sta, care se aglomereaza. Se citea dintr-un rand gol
  pe swimlane; grila de luna nu o poate da. Cu 4 randuri si 9 taskuri in fereastra reala,
  intrebarea nu merita 2.954 de linii.
- **Orizonturile de 3 si 6 luni.** La 6L o zi are 5px: acolo banda pe proiecte nu era un stil,
  era singura forma care incapea. Nu mai exista nicio suprafata care sa raspunda la „cum arata
  urmatoarele sase luni".
- **Exportul PDF al planificatorului** (print din browser). `/api/export/pdf` e alt obiect si
  ramane.
- **Tragerea unui task pe o zi.** Se replanifica din `SelectorZi` (Azi · Mâine · Alege), care
  exista in toate cele patru liste.

Ce NU s-a pierdut: sertarul „Taskuri fara termen" (grupa „Fără termen" din `/tasks` il tinea
oricum), lista completa (`/tasks`, grupata pe termen), ziua de azi (`Acasă`).

## Detaliul care se strica tacut

`/api/calendar` intoarce acum si taskuri, deci **imbatraneste la fiecare scriere pe un task**.
Invalidarile din `stores/tasks.svelte.js` nu s-au sters odata cu `/api/plan`, s-au MUTAT pe
`/api/calendar`. Fara asta: bifezi un task, deschizi Calendarul, si ziua ti-l arata inapoi
nefacut — pentru cateva cadre sau pana la urmatoarea reincarcare.

Conditiile interogarii sunt cele din `/api/plan`, cuvant cu cuvant (proiect deschis, task
nefinalizat, fara ocurentele viitoare ale unei recurente, globalele doar `sfera = 'munca'`).
Regula era deja scrisa in `tasks.py`: aceeasi intrebare nu poate avea doua raspunsuri pe doua
rute care hranesc acelasi ecran. Cand una dintre rute dispare, conditia ei trebuie sa
supravietuiasca in cealalta — altfel „ce am de facut" isi schimba inţelesul fara ca nimeni sa
fi decis asta.

Proba de `sfera` din `test_suite.py` s-a mutat de pe `/api/plan` pe `/api/calendar`, si a
capatat un **martor**: un task de munca scadent azi trebuie sa APARA, nu doar cel personal sa
lipseasca. O proba negativa singura trece si cand interogarea n-a intors nimic — exact verdele
fals gasit cu o ora mai devreme in `audit_mobil`, unde un gest care rata tinta confirma
afirmatia „nu s-a mutat nimic".

## Ce a ramas cu un nume care nu se mai potriveste

`lib/planDates.js` — numele e al Planificatorului, continutul nu mai e. Au ramas patru functii
generice (`localToday`, `isoDate`, `parseISO`, `addDays`, `isoWeek`) folosite de `parserTask`
si de `ImplPeriodModal`. Nu s-a topit in `calendarDates.js` fiindca acela isi are propriile
`parseISO`/`addDays`, scrise pentru grila lunii, iar `parserTask` are un banc de probe scris
peste acestea. Doua implementari care arata la fel dar nu sunt aceeasi nu se contopesc fara sa
se masoare intai.

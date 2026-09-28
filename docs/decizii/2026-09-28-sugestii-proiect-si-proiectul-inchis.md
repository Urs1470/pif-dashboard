# Sugestii de proiect in foaia de adaugare; proiectul inchis trimite ce adaugi dupa (2026-09-28)

Ion: „cand adaug un task de acasa pentru azi si vreau sa fie pentru un proiect anume,
trebuie toata denumirea proiectului, nu ai putea sa faci sa-mi apara sugestii din toate
proiectele nu doar din cele active?"

Si, la intrebarea ce se intampla cu taskurile unui proiect inchis: „trebuie sa apara in
astazi taskul ce il adaug si in fisa proiect; celelalte vechi nu trebuiesc atinse din
moment ce este inchis proiectul."

## Ce s-a decis

**1. Sugestii de proiect, din toate proiectele.** Parserul recunostea un proiect doar dupa
NUMELE INTREG, iar numele reale (22 pe server, 20–53 de caractere) arata asa: „PIF tablouri
MCC Biochem Podari — G120". Acum orice cuvant scris, de la 3 litere, care e inceputul unui
cuvant din numele, codul, clientul sau locatia unui proiect il propune intr-o sectiune
„Pentru proiectul" sub randul „Creează". O atingere il alege: cuvintele care l-au propus
pleaca din camp (au devenit chipul), tastatura ramane sus. Nimic nu se ataseaza singur.
Deschise si inchise; la scor egal, cele deschise primele. Regulile stau in
`sugereazaProiecte` (`frontend/src/lib/parserTask.js`), testele pe lista reala in
`parserTask.test.js`.

**2. Cuvantul comun nu propune.** Un cuvant potrivit cu mai mult de 3 proiecte tace:
„Upgrade" (7), „G120" (7), „PIF" (5), „Service" (5), „Continental" (12). Pragul e de
FRECVENTA, nu de inteles — „motor" sta intr-un singur nume („motoare" nu incepe cu
„motor"), deci propune. E doar o propunere; mai scump ar fi fost un proiect care nu apare.

**3. Un proiect inchis trimite pe „Astăzi" ce ai adaugat in el DUPA inchidere.** Pana acum
nu trimitea nimic (2026-08-21), deci un task creat de pe Acasa pentru azi pe un proiect
finalizat se crea si aparea doar in pagina proiectului. Conditia e una, `TASK_PROIECT_VIU`
din `utils.py`, pusa pe cele trei rute care raspund la „ce am de facut": boardul, pickerul
lui si panoul zilei din Calendar. Resturile de dinainte de inchidere raman ascunse — acolo
e motivul din 2026-08-21, si ramane valabil.

## Taskurile vechi nu se ating — si un caz anume

Prima forma a regulii („adaugat dupa inchidere") ar fi scos la iveala exact un task:
„De trimis PV" din „Înlocuire fibră optică — S150" — proiect inchis pe 19.08, taskul adaugat
pe 21.08, termen 21.08. Ar fi aparut pe Acasa ca restanta de cinci saptamani. Ion a cerut ca
cele vechi sa ramana cum sunt, deci conditia mai are o jumatate: `created_at` de la
2026-09-28 incolo. Data e scrisa in cod, cu motivul langa ea. Daca vrea „De trimis PV" pe
Acasa, il muta din pagina proiectului (sau il bifeaza).

## Verificat

- `node --test src/lib/parserTask.test.js`: 30/30, dintre care 11 noi pe lista reala.
- `scripts/test_suite.py`, proba noua `proiect_inchis_test`: pe azi / picker / calendar,
  taskul adaugat dupa inchidere APARE (martor) si restul cu `created_at` impins inapoi NU
  apare; fisa proiectului le arata pe toate.
- In browser, pe o copie a bazei cu cele 22 de proiecte reale: „raport Oro" -> Oromax,
  „trimite PV Biochem" -> Biochem (finalizat); amandoua au aterizat pe Astăzi, iar
  „De trimis PV" nu. Pe 375px, „Extruder TDE" pune primul proiectul care le are pe amandoua.

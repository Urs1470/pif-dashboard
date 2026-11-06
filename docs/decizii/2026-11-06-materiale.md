# 2026-11-06 Centralizatorul de materiale: snapshot-fișier la `/api/materiale`, marcajele calculate pe server

Ion vrea o pagină care să centralizeze materialele proiectelor deschise: ce e comandat și cu ce termen,
ce e încă necomandat, listele de materiale (LM) din E100, comenzile date pe mail și alertele. Datele le
adună un colector de pe PC-ul de job (Knowledge `tools/`, Task Scheduler, L–V la 08:00): BC prin SQL-ul
E100 (`spRpt_TermeneProductie`, `spRpt_Productie_CantitateNecomandataCT`, aceleași interogări ca Excelul
„Termene Productie”), E100 și Outlook. Brief aprobat de Ion pe 2026-11-06, după machete; pagina e în
Torqa (serverul nu mai are interfață), cu brief separat.

- **Deciziile lui Ion (06.11), pe machete.** Doar o pagină globală „Materials” în bara laterală Torqa;
  pagina proiectului rămâne cum e. Termenele `1900-01-01` și `2030-12-31` din BC se arată brute, cu
  avertisment de neregulă. Alerta „comandă pe mail, fără LM în E100 după 2 zile lucrătoare” devine și task
  pe proiect, creat de colector prin rutele de taskuri existente (serverul nu se schimbă pentru asta).
- **De ce fișier și nu tabelă.** Fiecare rulare trimite tot, iar a doua zi totul se reface: nimic de
  păstrat. Tiparul calendarului Outlook (decizia 2026-10-19): `uploads/materiale/snapshot.json`, scris
  atomic, fără schemă, fără migrare, **în afara backup-ului** (după un restore apare la următoarea rulare).
- **Două fișiere, rotație pe zi.** `snapshot.prev.json` e ultima colectare dintr-o zi **anterioară**.
  Un PUT din altă zi decât cel curent mută întâi copia curentă în „anterior” (scrisă și ea atomic, deci
  un cititor nu prinde niciodată o clipă fără snapshot), apoi scrie noul curent. Un PUT din aceeași zi
  înlocuiește doar curentul: o rulare repetată de mână nu șterge marcajele zilei. Ziua e cea locală din
  string (primele 10 caractere), ca la Outlook. Un snapshot mai vechi decât cel curent dă **409** și nu se
  scrie: o reîncercare întârziată nu suprascrie o colectare mai nouă.
- **Contractul (v1), toleranța.** `generat` ISO cu offset (obligatoriu, ca `generatedAt` la Outlook),
  `sursa` obiect cu texte, `proiecte[]` cu `proiect_id` (id-ul din `/api/proiecte`, unic) și
  `cod_proiect`. Secțiunile `lm`, `termene`, `necomandate`, `mailuri`, `alerte` sunt opționale (lipsă =
  `[]`): colectorul încă nu trimite LM-urile din E100. Câmpurile cheie au tipul verificat (`ct` și
  `cod_articol` text nevid, cantitățile numere, datele `YYYY-MM-DD` sau null, `mailuri[].tip` din
  `comanda_mail|stare_lm|livrare|alt`, `entry_id` hex ca la Outlook); **câmpurile în plus se păstrează**,
  spre deosebire de Outlook, ca o coloană nouă din colector să ajungă la Torqa fără schimbare aici.
  Orice abatere dă 400 cu calea câmpului (`proiecte[0].termene[14].ct`) și lasă snapshot-ul neatins.
  Corp maxim 2 MB (413), 200 de proiecte, 5000 de rânduri pe secțiune.
- **Marcajele, pe server.** `GET /api/materiale` compară curentul cu anteriorul și pune pe rânduri
  `schimbare`: `nou`, `mutat` (cu `termen_anterior`), `cantitate` (cu `cantitate_anterioara`), `stare` la LM
  (cu `stare_anterioara`) sau `null`; pe proiect, `disparute` (termene, necomandate, LM ieșite din listă).
  Mailurile și alertele primesc doar `nou`: un mail ieșit din fereastra colectorului sau o alertă rezolvată
  nu sunt vești. Un proiect care lipsea din anterior (sau prima colectare) nu primește marcaje, altfel totul
  ar fi „nou”. Identitatea rândurilor: termene (CT, articol, rezervat din), necomandate (CT, articol), LM
  (nr), mail (entry_id, altfel data și subiectul). Același articol de mai multe ori pe același CT (cazul
  real CT26003799) se împerechează în ordinea (cantitate, termen). Torqa doar afișează.
- **Ce mai adaugă GET-ul.** `termen_neregulat` pe termenele din lista de mai sus; `proiect` (`nume`,
  `client`, `status`) citit din `proiecte`, `null` pentru un proiect șters; `comparat_cu` (data
  anteriorului); `vechi`, adevărat când de la `generat` a trecut mai mult de o zi lucrătoare (L–V, fără
  sărbători) plus 2 ore de marjă: vinerea de la 08:00 rămâne proaspătă până luni la 10:00. Fără snapshot
  sau cu fișier stricat: 200, `generat` null, `vechi` true, `proiecte` [] (warning în log, nu 500).
- **Cine scrie, cine citește.** `login_required`; `/api/materiale` e în `DEVICE_TOKEN_READ_ONLY`: Torqa
  (tokenul de dispozitiv) citește, scrie doar colectorul (`PIF_API_TOKEN`). PUT cu tokenul de dispozitiv dă
  401, ca la celelalte rute refuzate lui.
- **Cod:** `blueprints/materiale.py`, `app.py` (înregistrarea), `utils.py` (`DEVICE_TOKEN_READ_ONLY`),
  teste în `teste/test_materiale.py` (22: contractul, 400/401/409/413, rotația, marcajele, articolul
  repetat pe CT, vechimea, dispozitivul; verificate să pice pe două greșeli puse intenționat).

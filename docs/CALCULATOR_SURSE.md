# Surse — Calculator acționări electrice

Lista consolidată a tuturor surselor folosite în calculator (95 module). Fiecare card
afișează sursa proprie; aici sunt grupate pe tip. **Notație și standarde primare = europene
(IEC / EN / ISO)**; standardele americane (IEEE / NEMA / CEMA / HI) sunt citate doar ca
**echivalent US**, în paranteză.

---

## 1. Standarde europene — IEC / EN / ISO (primare)

| Standard | Domeniu | Folosit la |
|---|---|---|
| **IEC/EN 60034-1** | Mașini rotative: regimuri de serviciu S1–S10, derating, timp de demaraj, dezechilibru | regimuri-s, run-up, termic, dezechilibru, derating-armonici-motor |
| **IEC 60034-12** | Caracteristici de pornire (categorii N/H) | run-up |
| **IEC/EN 60034-18-41** | Sisteme de izolație pe convertizor (anvelopă tensiune, dv/dt) | unda-reflectata |
| **IEC/EN 60034-25** | Mașini alimentate de la convertizor (undă reflectată, encoder, derating) | unda-reflectata, encoder-offset, derating-armonici-motor |
| **IEC/EN 60034-27-4** | Rezistența de izolație & indicele de polarizare (PI) | izolatie |
| **IEC 60034-30-1 / -30-2** | Clase de randament IE1–IE5 | clase-ie |
| **IEC/EN 61800-2** | Sisteme de acționare (PDS) — valori nominale | franare-rezistenta, notch-rezonanta |
| **IEC/EN 61800-3** | Compatibilitate electromagnetică (categorii C1–C4) | retea-emc |
| **IEC/EN 61800-5-1** | Cerințe de siguranță electrică | franare-rezistenta |
| **IEC/EN 61800-5-2** | Funcții de siguranță (STO / SS1) | sto-ss1, run-up |
| **IEC 60364** | Instalații JT — legare la pământ (TN / TT / IT) | retea-emc |
| **IEC 60364-5-52** | Ampacitatea cablurilor (factori de corecție) | cablu-protectii |
| **IEC 60364-5-54** | Verificare termică I²t adiabatică (S = I·√t / k) | cablu-protectii |
| **IEC 61000-2-4** | Niveluri de compatibilitate pentru armonici | ieee519 |
| **IEC 61000-3-12** | Limite de armonici de curent (cu raportul Rsce) | ieee519, comparatie-frontend |
| **IEC 61000-4-30** | Metode de măsurare a calității energiei | dezechilibru |
| **IEC 60909-0** | Curenți de scurtcircuit (Icc, contribuția motoarelor) | scurtcircuit, dip-pornire |
| **IEC 60204-1** | Echipamentul electric al mașinilor (categorii de stop 0/1) | sto-ss1 |
| **IEC 60079-7** | Atmosfere explozive — protecție „e"; timpul tE | run-up |
| **IEC 60076-1, Anexa E** | Factorul K al transformatorului la sarcini neliniare | factor-k |
| **EN ISO 9906** | Încercări de performanță pompe (NPSH3, criteriul 3 %) | pompa-sistem, npsh |
| **EN 50160** | Calitatea tensiunii rețelei publice (THD_U ≤ 8 %) | dezechilibru, ieee519, comparatie-frontend, dip-pornire |
| **EN 805** | Regim tranzitoriu în rețele de apă (lovitura de berbec) | lovitura-berbec |

---

## 2. Standarde americane — citate ca echivalent (US)

| Standard | Echivalent IEC/EN | Folosit la |
|---|---|---|
| **IEEE 43** | IEC 60034-27-4 (PI / rezistență izolație) | izolatie |
| **IEEE 112** | teste motor (gol / rotor blocat) | teste-parametri |
| **IEEE 141** (Red Book) | dip de tensiune la pornire (~15 %) | dip-pornire |
| **IEEE 519** | IEC 61000-3-12 (limite armonici, TDD) | ieee519, comparatie-frontend |
| **IEEE C57.110** | IEC 60076-1 (derating trafo la armonici) | factor-k |
| **NEMA MG-1** (Part 30/31, §12.50, §14.35) | derating PWM, izolație, porniri/oră, dezechilibru | derating-armonici-motor, unda-reflectata, porniri-ora, dezechilibru |
| **CEMA Belt Book** | forța de tracțiune transportoare | transportor |
| **Hydraulic Institute** | EN ISO 9906 (pompe) | pompa-sistem |

---

## 3. Cărți de referință (autori clasici)

| Carte | Folosită la | Extras local |
|---|---|---|
| **Chapman** — *Electric Machinery Fundamentals* | asincron (turație, cuplu, Thévenin, bilanț putere, teste), c.c., sincron, curbe V | ✅ `chapman-...-extras.pdf` (login /docs) |
| **Mohan** — *Power Electronics* | VFD (Udc, V/f), punte comandată, pierderi de comutație, filtru LC | ✅ `mohan-...-extras.pdf` |
| **Hughes** — *Electric Motors and Drives* | pornire, servo (Kt/Ke, τ), model termic, derating PWM | ✅ `hughes-...-extras.pdf` |
| **Nise** — *Control Systems Engineering* | răspuns ordin 2, acordare bucle | ✅ `nise-...-extras.pdf` |
| **Leonhard** — *Control of Electrical Drives* | slăbire de câmp (M∝1/n, M_max∝1/n²) | ❌ fără PDF local |
| **Fitzgerald** — *Electric Machinery* | pornire c.c. în trepte (progresie geometrică) | ❌ fără PDF local |

Extrasele conțin **doar paginile citate** (drept de autor respectat), servite protejat cu login la `/docs`,
ascunse pe `/calc` public. PDF.js le deschide la pagină + evidențiază termenul.

---

## 4. Ghiduri & manuale producători

| Sursă | Folosită la | Local |
|---|---|---|
| **ABB Technical Guide Book** (compilație No.1–No.9) | majoritatea modulelor (legi mecanice, sarcini, frânare, armonici, motion) | ✅ găzduit public `static/docs/` |
| **ABB Technical Guide No.1** (DTC) | taper / winder | ✅ găzduit public |
| **ABB ACS580/880, ACS880-01 catalog** | selecție drive (I_Hd/I_Ld), PID intern, parametri | citat (manuale online ABB) |
| **Siemens SINAMICS S120 / G120** | parametri (p1082, p1990/p1980, technology controller) | datasheet-uri locale (1PH8, 6SL3000, 6SL3210, 6SE6430) |
| **WEG** — motoare pe PWM (curbe derating) | derating-vfd-motor | online |
| **KSB** — *Centrifugal Pump Lexicon* | pompă-sistem, NPSH, turație specifică | online |
| **Danfoss / SEW** — ghiduri rezistențe de frânare | franare-rezistenta | online |

---

## 5. Resurse online / aplicative

- **Wikipedia EN** — 26 articole de bază (motor asincron, VFD, FOC, armonici, NPSH, rezonanță, PID etc.), cu evidențiere pe propoziția de referință.
- **MathWorks** — curbe de constrângere PMSM / IPMSM (I_ch, elipsă tensiune, MTPA).
- **EngineeringToolbox** — legi de afinitate ventilator, legi de diametru rotor.
- **Oriental Motor / LinearMotionTips** — dimensionare șurub cu bile, mecanisme liniare.
- **Schneider Electrical Installation Guide** — rezonanță condensatoare, reactor de detunare.
- **Technosoft / Industrial Monitor Direct** — profile de mișcare (trapezoidal vs S-curve).
- **NPTEL / TCF Fan Engineering / Pumps & Systems / ChangYu** — volant compresor, ventilatoare, debit minim, randament pompă.

---

## 6. Cum sunt servite PDF-urile locale

| Locație | Conținut | Acces |
|---|---|---|
| `private_docs/` | extrase Chapman / Hughes / Mohan / Nise (doar paginile citate) | `/docs` public + noindex (accesibil și de pe /calc) |
| `private_docs/standards/` | **18 standarde IEC/EN ca extrase** (doar paginile citate) | `/docs/standards` public + noindex |
| `static/docs/` | ABB Technical Guide Book + No.1 (ghiduri ABB libere) | public |

**Standardele IEC/EN cu PDF local** (60034-1/-12/-25/-18-41/-30-1, 61800-2/-3/-5-1/-5-2, 60364-5-52,
60909, 60204-1, 61000-2/-3-12/-4-30, 60076-1, ISO 9906, EN 50160) au extrase cu paginile citate +
link cu evidențiere (PDF.js). Standardele **fără PDF local** (60034-27-4, 60076-5, 61378-1, 60079-7,
EN 805) și cele americane (IEEE/NEMA) rămân ca citări text. Extrasele de standarde sunt cited-pages-only
+ `noindex` (documente cu plată — mitigare de copyright).

---

*Generat din `SOURCES` în `frontend/src/lib/driveCalc.js`. La adăugarea de module noi, completează și sursa pe card.*

// Glosar de marimi pentru calculatorul de actionari electrice.
// Cheia = `key`-ul field-ului/rezultatului. Pentru simboluri ambigue intre familii
// (ex. Q = reactiva la asincron vs debit la pompe) se foloseste cheia `familie:key`,
// cu fallback pe cheia simpla. Modalul afiseaza si eticheta + unitatea reale ale marimii.
//
// Fiecare intrare: { def, ia (de unde se ia / cum se obtine), practic (la ce ajuta la PIF) }.

export const GLOSSARY = {
  // --- turatie / frecventa ---
  f: { def: 'Frecventa tensiunii de alimentare la bornele motorului.', ia: 'Retea (50 Hz) sau setarea/referinta convertizorului de frecventa.', practic: 'Pe convertizor o reglezi direct; determina turatia campului si a motorului.' },
  fn: { def: 'Frecventa nominala de pe placuta motorului (uzual 50 Hz).', ia: 'Placuta motorului.', practic: 'Punctul de baza al caracteristicii V/f; peste ea intri in slabire de camp.' },
  p: { def: 'Numarul total de poli ai motorului (par: 2, 4, 6, 8...).', ia: 'Placuta motorului sau dedus din turatia nominala.', practic: '4 poli = ~1500 rpm la 50 Hz. Verifica-l la introducerea datelor in drive.' },
  ppp: { def: 'Numarul de perechi de poli (= poli / 2).', ia: 'Din numarul de poli al motorului.', practic: 'Folosit la frecventa electrica f_e = p_pp·n/60 (servo/PMSM).' },
  n: { def: 'Turatia mecanica a arborelui.', ia: 'Masurata (tahometru/encoder) sau de pe placuta (turatia nominala).', practic: 'O compari cu referinta pentru a valida reglajul; baza pentru cuplu si putere.' },
  ns: { def: 'Turatia campului magnetic invartitor (turatia de sincronism).', ia: 'Calculata: n_s = 120·f / p.', practic: 'Turatia maxima teoretica; stabileste f_max in drive (ABB 30.12 / Siemens p1082).' },
  s: { def: 'Alunecarea: diferenta relativa intre turatia sincrona si cea reala.', ia: 'Calculata: s = (n_s − n)/n_s · 100.', practic: 'Creste cu sarcina — indicator de incarcare; folosita la slip compensation.' },
  w: { def: 'Viteza unghiulara mecanica a arborelui.', ia: 'Calculata: ω = 2π·n / 60.', practic: 'Baza pentru putere (P = M·ω) si energie cinetica (½J·ω²).' },
  omega: { def: 'Viteza unghiulara mecanica.', ia: 'ω = 2π·n / 60.', practic: 'Leaga cuplul de putere si intra in timpii de rampa.' },
  fr: { def: 'Frecventa curentilor indusi in rotor (frecventa de alunecare).', ia: 'f_r = s·f.', practic: '~1-3 Hz la sarcina nominala; benzile de slip in spectru (MCSA) indica bare rupte.' },

  // --- tensiune / curent / putere ---
  U: { def: 'Tensiunea de linie (intre faze).', ia: 'Reteaua (400/690 V) sau iesirea convertizorului.', practic: 'Cuplul motorului ∝ U²; verifica caderile de tensiune pe cablu.' },
  Un: { def: 'Tensiunea nominala a motorului.', ia: 'Placuta motorului.', practic: 'Referinta pentru V/f si pentru caracteristica de cuplu.' },
  I: { def: 'Curentul absorbit de linie.', ia: 'Calculat din putere sau masurat cu clestele ampermetric.', practic: 'Dimensionare cablu/protectii/drive; orientativ ~1.7-2 A/kW la 400 V.' },
  In: { def: 'Curentul nominal al motorului.', ia: 'Placuta motorului.', practic: 'Referinta pentru protectia termica si alegerea convertizorului.' },
  I0: { def: 'Curentul de mers in gol (de magnetizare).', ia: 'Masurat la gol sau ~ I_n·sin φ_n.', practic: 'Aproape constant; sub el curentul nu mai scade cu sarcina.' },
  Igol: { def: 'Curentul de mers in gol (de magnetizare).', ia: '≈ I_n·sin φ_n.', practic: 'Explica de ce cos φ se prabuseste la sarcini mici.' },
  cosphi: { def: 'Factorul de putere: cos al unghiului dintre tensiune si curent.', ia: 'Placuta (cos φ nominal) sau masurat.', practic: 'Scade mult la sarcini partiale; afecteaza curentul si compensarea.' },
  cosphin: { def: 'Factorul de putere nominal.', ia: 'Placuta motorului.', practic: 'Referinta pentru curba cos φ vs sarcina.' },
  eta: { def: 'Randamentul: raportul putere utila / putere absorbita.', ia: 'Placuta / clasa IE / masurat (bilant de putere).', practic: 'Motor supradimensionat → randament prost sub ~50% sarcina.' },
  Pn: { def: 'Puterea nominala (mecanica la arbore).', ia: 'Placuta motorului.', practic: 'Baza dimensionarii; M_n = 9550·P_n / n_n.' },
  P: { def: 'Puterea (mecanica la arbore, daca nu se specifica altfel).', ia: 'Placuta sau P = M·ω.', practic: 'Leaga cuplul de turatie; baza pentru curent si energie.' },
  Pel: { def: 'Puterea activa electrica absorbita din retea.', ia: 'P_el = P_n / η.', practic: 'Folosita la bilant energetic, cost si calculul reactivei.' },
  S: { def: 'Puterea aparenta.', ia: 'S = √3·U·I.', practic: 'Dimensionarea transformatorului si a aparatajului (kVA).' },
  Q: { def: 'Puterea reactiva (de fundamentala).', ia: 'Q = √(S² − P²).', practic: 'Se compenseaza cu baterii de condensatoare pentru a ridica cos φ.' },

  // --- cuplu / dinamica ---
  M: { def: 'Cuplul (electromagnetic / la arbore).', ia: 'M = 9550·P / n  (P in kW, n in rpm).', practic: 'Marimea-cheie la potrivirea motor-sarcina.' },
  Mn: { def: 'Cuplul nominal.', ia: 'M_n = 9550·P_n / n_n.', practic: 'Referinta pentru cuplurile de pornire si maxim (multipli din M_n).' },
  Mp: { def: 'Cuplul de pornire.', ia: 'M_p = k_p·M_n (k_p ~1.5-2.5).', practic: 'Trebuie sa depaseasca cuplul rezistent la pornire (cu marja).' },
  Mmax: { def: 'Cuplul maxim (breakdown / pull-out).', ia: 'M_max = k_m·M_n (k_m ~2-3).', practic: 'Marja de stabilitate; scade cu patratul tensiunii (∝ U²).' },
  kp: { def: 'Factorul cuplului de pornire (multiplu din M_n).', ia: 'Catalog / placuta (clasa NEMA/IEC).', practic: 'Tipic 1.5-2.5; verifica fata de cuplul de desprindere al sarcinii.' },
  km: { def: 'Factorul cuplului maxim (multiplu din M_n).', ia: 'Catalog / placuta.', practic: 'Tipic 2-3; marja fata de varfurile de cuplu ale procesului.' },
  J: { def: 'Momentul de inertie (rezistenta la accelerare).', ia: 'Catalog (J sau GD² = 4·J), sau redus la axul motor (J/i²).', practic: 'Determina timpul de accelerare, rampele si energia de franat.' },
  Jtot: { def: 'Inertia totala (motor + sarcina redusa la ax).', ia: 'J_tot = J_motor + J_sarcina/i².', practic: 'Intra direct in timpul de accelerare si in cuplul dinamic.' },
  Macc: { def: 'Cuplul disponibil pentru accelerare.', ia: 'Cuplul motorului in timpul pornirii (peste cuplul nominal).', practic: 'Diferenta (M_acc − M_load) accelereaza inertia.' },
  Mload: { def: 'Cuplul rezistent al sarcinii.', ia: 'Din tipul de sarcina (pompa, banda, etc.) sau masurat.', practic: 'Daca depaseste cuplul motorului, motorul nu porneste/accelereaza.' },
  tacc: { def: 'Timpul de accelerare de la o turatie la alta.', ia: 't = J·Δω / (M_acc − M_load).', practic: 'Il setezi ca rampa in drive (ABB 23.12 / Siemens p1120).' },
  Ecin: { def: 'Energia cinetica a maselor in rotatie.', ia: 'E = ½·J·ω².', practic: 'Energia care trebuie disipata la franare (dimensionare rezistor).' },
  RJ: { def: 'Raportul de inertie sarcina/motor.', ia: 'R_J = J_sarcina_redusa / J_motor.', practic: 'Tinta < 5 (servo) ... < 10 (uz general) pentru reglaj stabil.' },
  i: { def: 'Raportul de transmisie al reductorului.', ia: 'i = n_intrare / n_iesire = z2/z1.', practic: 'Multiplica cuplul si reduce inertia sarcinii (÷i²) la axul motor.' },

  // --- c.c. / servo / sincron ---
  Kt: { def: 'Constanta de cuplu (servo/PMSM).', ia: 'Catalog servo (uzual Nm/A_rms).', practic: 'M = K_t·I_q. Ia-o din catalog — nu o recalcula din tensiune.' },
  Iq: { def: 'Curentul de cuadratura (axa q).', ia: 'Comanda de cuplu in control vectorial.', practic: 'Componenta producatoare de cuplu (cu I_d = 0 la SPM).' },
  E: { def: 'Tensiunea electromotoare indusa (t.c.e.m. / back-EMF).', ia: 'E = k·Φ·ω (c.c.) sau din excitatie (sincron).', practic: 'Proportionala cu turatia; bază pentru reglajul de tensiune/turatie.' },
  Ra: { def: 'Rezistenta circuitului de indus.', ia: 'Autotuning (ID-run) sau masurare (test c.c.).', practic: 'Determina caderea I·R si constantele de timp ale buclei de curent.' },
  La: { def: 'Inductanta circuitului de indus.', ia: 'Autotuning sau catalog.', practic: 'Constanta de timp electrica τ_a = L_a/R_a (raspunsul curentului).' },
  kPhi: { def: 'Constanta masinii × fluxul (k·Φ), in SI [V·s/rad = Nm/A].', ia: 'Din datele motorului c.c. / identificare.', practic: 'Leaga E de ω si M de I_a; la flux constant M ∝ I_a.' },
  Xs: { def: 'Reactanta sincrona (masina sincrona).', ia: 'Date motor / catalog.', practic: 'Limiteaza puterea: P = U·E·sinδ / X_s.' },
  delta: { def: 'Unghiul de sarcina (intre tensiune si t.e.m.).', ia: 'Rezulta din incarcare.', practic: 'Cuplu maxim (pull-out) la δ = 90°; stabil doar pentru δ < 90°.' },

  // --- convertizor / instalatie ---
  Udc: { def: 'Tensiunea circuitului intermediar (DC bus).', ia: 'U_dc ≈ 1.35·U_linie (punte cu diode).', practic: 'Pragul chopperului de franare; o monitorizezi la fault overvoltage.' },
  fsw: { def: 'Frecventa de comutatie (purtatoare PWM).', ia: 'Setare convertizor.', practic: 'Compromis: mai mare = mai silentios dar pierderi mai mari → derating de curent.' },
  uk: { def: 'Tensiunea de scurtcircuit / impedanta procentuala.', ia: 'Placuta transformatorului / reactorului.', practic: 'I_cc = I_n / (u_k/100); determina si caderea pe reactor.' },
  Icc: { def: 'Curentul de scurtcircuit prezumat.', ia: 'I_cc = I_n_trafo / (u_k/100) + contributia motoarelor.', practic: 'Alegerea capacitatii de rupere a disjunctorului (Icu ≥ Icc).' },
  THD: { def: 'Distorsiunea armonica totala a curentului.', ia: 'Din masuratori / estimat pe topologie (6-puls ~30-40%).', practic: 'Verifica fata de limita IEEE 519 la punctul de racord (TDD).' },

  // --- pompe (familie: pompe) ---
  'pompe:Q': { def: 'Debitul pompei/ventilatorului.', ia: 'Cerinta procesului / curba pompei.', practic: 'La turatie variabila Q ∝ n (legea afinitatii).' },
  H: { def: 'Inaltimea de pompare (presiunea exprimata in m coloana).', ia: 'Curba pompei / cerinta sistemului.', practic: 'H ∝ n² (afinitate); cu inaltime statica apare o turatie minima utila.' },
  Hstatic: { def: 'Inaltimea statica (diferenta de nivel + contrapresiune).', ia: 'Din configuratia instalatiei.', practic: 'Reduce economia fata de legea cubului si impune o turatie minima.' },
  NPSHrn: { def: 'NPSH cerut de pompa la turatia nominala.', ia: 'Curba producatorului pompei.', practic: 'NPSH_a trebuie sa fie ≥ NPSH_r + marja, altfel cavitatie.' },
  nq: { def: 'Turatia specifica a pompei.', ia: 'n_q = n·√Q / H^0.75.', practic: 'Identifica tipul rotorului (radial/mixt/axial) si forma curbei.' },
  DC: { def: 'Durata de conectare (factor de serviciu intermitent).', ia: 'Din ciclul real de sarcina (regim S3/S6).', practic: 'La DC < 100% poti incarca motorul peste P_S1: P ∝ 1/√(DC).' },

  // --- mecanic / general ---
  rho: { def: 'Densitatea fluidului.', ia: 'Tabel / proces (apa ~1000, aer ~1.2 kg/m³).', practic: 'Presiunea si puterea pompei/ventilatorului sunt proportionale cu ρ.' },
  m: { def: 'Masa care se deplaseaza sau se ridica.', ia: 'Din mecanism / proces.', practic: 'Forta = m·g; inertia redusa la ax = m·(pas/2π)² (surub) sau m·r².' },
  v: { def: 'Viteza liniara.', ia: 'Cerinta procesului.', practic: 'Putere = F·v; v = π·D·n/60.' },
  D: { def: 'Diametrul (tambur, roata, pinion, rotor).', ia: 'Desen mecanic.', practic: 'Cuplu = F·D/2; viteza liniara = π·D·n/60.' },
  F: { def: 'Forta (liniara / tangentiala / de tractiune).', ia: 'Din proces (masa, frecare, panta).', practic: 'Cuplu = F·r; putere = F·v.' },
  r: { def: 'Raza de aplicare a fortei (tambur, parghie).', ia: 'Desen mecanic.', practic: 'Cuplu = F·r.' },
  t: { def: 'Timpul (de masura / declansare / franare).', ia: 'Cerinta sau setare.', practic: 'Vezi eticheta pentru rolul exact in modul.' },
  tau: { def: 'Constanta de timp (termica / electrica / mecanica).', ia: 'Catalog sau calcul.', practic: 'Timpul pana la ~63% din raspuns. Vezi eticheta.' },
  ratio: { def: 'Raport adimensional intre doua marimi.', ia: 'Calculat.', practic: 'Interpretarea depinde de modul (diametre, curenti, varf/continuu).' },
  df: { def: 'Factor de derating (subunitar).', ia: 'Curba producatorului / standard.', practic: 'Capacitatea ramasa = valoarea nominala × df.' },

  // --- economie ---
  pret: { def: 'Pretul energiei electrice.', ia: 'Factura / contract (lei/kWh).', practic: 'Baza calculului de economie si payback.' },
  ore: { def: 'Orele de functionare pe an.', ia: 'Regimul de exploatare.', practic: 'Multiplica economia de putere → economie anuala.' },
  invest: { def: 'Investitia (cost echipament).', ia: 'Oferta.', practic: 'Payback = investitie / economie anuala.' },
  nproc: { def: 'Turatia de proces (% din nominal).', ia: 'Cerinta procesului.', practic: 'Economia cu VFD ∝ (n%)³ la sarcina patratica.' },
  Pvana: { def: 'Puterea cu reglaj prin vana/clapeta (100% debit).', ia: 'Regimul actual, fara VFD.', practic: 'Referinta pentru economia adusa de VFD.' },

  // --- afinitate pompe ---
  n1: { def: 'Turatia initiala / de referinta.', ia: 'Nominala sau masurata.', practic: 'Punct de plecare pentru legile afinitatii.' },
  n2: { def: 'Turatia noua / dorita.', ia: 'Cerinta procesului.', practic: 'La pompe Q∝n, H∝n², P∝n³.' },
  Q1: { def: 'Debitul la turatia initiala.', ia: 'Punctul de functionare nominal.', practic: 'Q ∝ n (afinitate).' },
  Q2: { def: 'Debitul la turatia noua.', ia: 'Calculat din afinitate.', practic: 'Q2 = Q1·(n2/n1).' },
  H1: { def: 'Inaltimea la turatia initiala.', ia: 'Curba pompei.', practic: 'H ∝ n².' },
  H2: { def: 'Inaltimea la turatia noua.', ia: 'Calculat.', practic: 'H2 = H1·(n2/n1)².' },
  P1: { def: 'Puterea la turatia initiala.', ia: 'Nominala.', practic: 'P ∝ n³.' },
  P2: { def: 'Puterea la turatia noua.', ia: 'Calculat.', practic: 'P2 = P1·(n2/n1)³ — baza economiei VFD.' },
  Hnom: { def: 'Inaltimea la debitul nominal.', ia: 'Curba pompei.', practic: 'Defineste coeficientul curbei sistemului.' },
  Qnom: { def: 'Debitul nominal.', ia: 'Curba pompei.', practic: 'Referinta pentru curba sistemului si afinitate.' },
  Hshut: { def: 'Inaltimea la debit zero (shutoff).', ia: 'Curba pompei.', practic: 'Turatia minima utila = n·√(H_static/H_shut).' },
  QBEP: { def: 'Debitul la randament maxim (BEP).', ia: 'Curba pompei.', practic: 'Pompa lucreaza eficient si stabil langa BEP.' },
  Qtarget: { def: 'Debitul cerut de proces.', ia: 'Cerinta.', practic: 'Determina turatia/frecventa de setat in drive.' },

  // --- asincron extins ---
  etan: { def: 'Randamentul nominal.', ia: 'Placuta / clasa IE.', practic: 'Referinta pentru curba randament vs sarcina.' },
  Pconst: { def: 'Pierderile fixe (fier + frecare + ventilatie).', ia: 'Fisa motor / separare pierderi.', practic: 'Dominante la sarcina mica → randament prost.' },
  Tamb: { def: 'Temperatura ambianta.', ia: 'Conditiile de instalare.', practic: 'Peste 40°C → derating de curent (~1%/°C).' },
  R1: { def: 'Rezistenta infasurarii statorice.', ia: 'Test c.c. / autotuning.', practic: 'Pierderi Cu stator = 3·I²·R1.' },

  // --- servo / c.c. ---
  Ia: { def: 'Curentul de indus (rotor) la masina de c.c.', ia: 'Masurat / nominal.', practic: 'La flux constant M ∝ I_a; limita de curent = limita de cuplu.' },
  Ld: { def: 'Inductanta pe axa d (PMSM/sincron).', ia: 'Date motor.', practic: 'Curent caracteristic I_ch = ψ_m/L_d (slabire de camp).' },
  Lq: { def: 'Inductanta pe axa q (PMSM/sincron).', ia: 'Date motor.', practic: 'La IPM (Lq>Ld) apare cuplu de reluctanta.' },
  psim: { def: 'Fluxul magnetilor permanenti (ψ_m).', ia: 'Date motor PMSM.', practic: 'Cuplu de magneti = (3/2)·p·ψ_m·I_q.' },
  Imax: { def: 'Curentul maxim (de varf).', ia: 'Catalog drive/motor.', practic: 'Limiteaza cuplul de varf si gama de putere constanta.' },
  kt: { def: 'Constanta de cuplu (model c.c. serie).', ia: 'Date motor.', practic: 'M = k_t·I_a² (pana la saturatie).' },
  c: { def: 'Constanta de tensiune (model c.c. serie).', ia: 'Identificare.', practic: 'Turatia ~ 1/I_a → pericol de ambalare la gol.' },
  Rt: { def: 'Rezistenta totala a circuitului (indus + excitatie).', ia: 'Masurare.', practic: 'Caderea I·R si constanta de timp.' },
  Mvarf: { def: 'Cuplul de varf cerut de ciclu.', ia: 'Din profilul de miscare (accelerare).', practic: 'Trebuie ≤ cuplul de varf al motorului/driveului.' },
  Mcont: { def: 'Cuplul continuu al motorului.', ia: 'Catalog servo.', practic: 'M_rms al ciclului trebuie ≤ M_cont.' },
  Mrms: { def: 'Cuplul termic echivalent pe ciclu.', ia: 'M_rms = √(ΣM²·t / Σt).', practic: 'Baza dimensionarii termice a servomotorului.' },
  PPR: { def: 'Impulsuri pe rotatie (encoder incremental).', ia: 'Fisa encoder.', practic: 'Rezolutie = 360/(4·PPR) cu decodare in cuadratura.' },
  imp: { def: 'Impulsuri numarate intr-o fereastra de timp.', ia: 'Din encoder.', practic: 'Turatie = 60·imp/(4·PPR·t).' },

  // --- instalatie / retea ---
  Strafo: { def: 'Puterea transformatorului.', ia: 'Placuta trafo.', practic: 'I_n = S/(√3·U); I_cc = I_n/(u_k/100).' },
  Pdrive: { def: 'Puterea totala a drive-urilor alimentate.', ia: 'Suma sarcinilor.', practic: 'Dimensionarea transformatorului (kVA).' },
  Iporn: { def: 'Curentul de pornire.', ia: 'I_p = k·I_n (DOL, k~5-7).', practic: 'Provoaca dip de tensiune pe bara la pornire.' },
  Sccbus: { def: 'Puterea de scurtcircuit a barei.', ia: 'Din retea / transformator.', practic: 'Dip ≈ S_pornire/(S_pornire + S_cc).' },
  IccPCC: { def: 'Curentul de scurtcircuit la punctul de racord (PCC).', ia: 'De la operatorul de retea.', practic: 'Raportul Isc/IL stabileste limita TDD (IEEE 519).' },
  Iload: { def: 'Curentul de sarcina maxim.', ia: 'Suma sarcinilor.', practic: 'Numitorul raportului Isc/IL pentru IEEE 519.' },
  Ssc: { def: 'Puterea de scurtcircuit (MVA).', ia: 'Date retea.', practic: 'Ordinul de rezonanta cu bateria: h = √(S_sc/Q_c).' },

  // --- ambigue dezambiguizate pe familie ---
  'comun:L': { def: 'Lungimea cablului motor.', ia: 'Traseul instalatiei.', practic: 'Peste o lungime critica apare supratensiune la borne (du/dt).' },
  'servo:L': { def: 'Inductanta infasurarii.', ia: 'Date motor.', practic: 'Constanta de timp electrica τ_e = L/R.' },
  'comun:T': { def: 'Cuplul (la ax / la iesire).', ia: 'T = F·r.', practic: 'Marimea transmisa mecanic catre sarcina.' },
  'pompe:T': { def: 'Temperatura aerului/gazului.', ia: 'Proces.', practic: 'Densitatea scade cu temperatura → presiune si cuplu mai mici.' },

  Ulinie: { def: 'Tensiunea de linie de alimentare.', ia: 'Reteaua (400/690 V).', practic: 'Bază pentru U_dc ≈ 1.35·U_linie si pentru V/f.' },
  Ps1: { def: 'Puterea in regim continuu S1.', ia: 'Placuta motorului.', practic: 'Baza recalcularii la regim intermitent: P ∝ 1/√(DC).' },
  Jsarc: { def: 'Momentul de inertie al sarcinii.', ia: 'Catalog / calcul (geometrie + masa).', practic: 'Redus la axul motor = J_sarcina/i².' },
  Jmot: { def: 'Momentul de inertie al motorului.', ia: 'Catalog motor.', practic: 'Numitorul raportului de inertie R_J (tinta < 5-10).' },
  etap: { def: 'Randamentul pompei.', ia: 'Curba pompei.', practic: 'P_arbore = P_hidraulic / η_pompa.' },
  etam: { def: 'Randamentul motorului.', ia: 'Placuta / clasa IE.', practic: 'Parte din lantul wire-to-water.' },
  etad: { def: 'Randamentul convertizorului.', ia: 'Catalog (~0.97-0.99).', practic: 'Putere din retea = P_motor / η_drive.' },
  etalow: { def: 'Randamentul clasei de eficienta joase (ex. IE2).', ia: 'Catalog motor.', practic: 'Comparatie de economie intre clase IE.' },
  etahigh: { def: 'Randamentul clasei superioare (ex. IE3/IE4).', ia: 'Catalog motor.', practic: 'Economia anuala fata de clasa joasa.' },
  dpret: { def: 'Diferenta de pret a motorului premium.', ia: 'Oferta.', practic: 'Payback = Δpret / economia anuala.' },
  payback: { def: 'Perioada de recuperare a investitiei.', ia: 'Investitie / economia anuala.', practic: 'Sub ~2-3 ani justifica investitia in VFD sau motor premium.' },
  Pies: { def: 'Puterea de iesire a convertizorului catre motor.', ia: 'Din puterea motorului.', practic: 'Baza estimarii pierderilor convertizorului si a deratingului.' },
  Iech: { def: 'Curentul termic echivalent (RMS) pe ciclul de sarcina.', ia: 'I_ech = √(Σ I²·t / Σ t).', practic: 'Se compara cu curentul nominal pentru dimensionare termica la sarcini ciclice.', teorie: 'Incalzirea depinde de media patratica a curentului (efect Joule I²t).' },
  I1: { def: 'Curentul primului segment al ciclului de sarcina.', ia: 'Din profilul de sarcina (regim intermitent).', practic: 'Intra in calculul curentului termic echivalent.' },
  t1: { def: 'Durata primului segment de sarcina.', ia: 'Din ciclul de lucru.', practic: 'Pondereaza segmentul in curentul echivalent.' },
  t2: { def: 'Durata celui de-al doilea segment de sarcina.', ia: 'Din ciclul de lucru.', practic: 'Pondereaza segmentul in curentul echivalent.' },
  Ps3: { def: 'Puterea admisibila in regim intermitent S3.', ia: 'P_S1 / √(DC/100).', practic: 'Dimensionarea motorului la sarcina intermitenta periodica.', teorie: 'La DC < 100% puterea admisa creste cu 1/√DC fata de regimul continuu.' },
  falt: { def: 'Factor de derating la altitudine.', ia: '1 − (H−1000)/10000, peste 1000 m.', practic: 'Reduce curentul admisibil; verifica curba producatorului.', teorie: 'Racirea scade cu densitatea aerului la altitudine (~1%/100 m).' },
  ftemp: { def: 'Factor de derating la temperatura ambianta.', ia: '1 − (T−40)/100, peste 40°C.', practic: 'Reduce curentul admisibil ~1%/°C peste 40°C.', teorie: 'Capacitatea de evacuare a caldurii scade cu temperatura mediului.' },
  OLHD: { def: 'Suprasarcina admisa in regim Heavy Duty.', ia: '150% I_n timp de 1 min la fiecare 5 min (ABB).', practic: 'Pentru cupluri de soc: concasoare, benzi incarcate, mecanisme de ridicat.' },
  OLND: { def: 'Suprasarcina admisa in regim Normal / Light Duty.', ia: '110% I_n timp de 1 min la fiecare 5 min (ABB).', practic: 'Pentru pompe si ventilatoare (sarcina patratica).' },
  Inest: { def: 'Curentul nominal estimat al motorului la 400 V.', ia: '~1.9·P[kW] (orientativ).', practic: 'Util cand lipseste placuta; verifica intotdeauna valoarea reala.', teorie: 'I = P / (√3·U·cosφ·η).' },
  f1: { def: 'Frecventa retelei de alimentare.', ia: '50 Hz in Europa.', practic: 'Baza pentru frecventa de acord a reactorului si de rezonanta.' },
  tride: { def: 'Timpul de sustinere a convertizorului la microintreruperi (ride-through).', ia: 'Energia DC bus / puterea sarcinii.', practic: 'Compara cu durata tipica a dip-urilor de retea (zeci de ms).', teorie: 't = ½·C·(U1² − U2²) / P.' },
  I5: { def: 'Curentul armonic de ordin 5 (% din fundamentala).', ia: 'Masurat sau tipic redresor 6-puls.', practic: 'Cea mai mare armonica; pondere importanta in factorul K.', teorie: 'Armonica 5 e de secventa inversa.' },
  I7: { def: 'Curentul armonic de ordin 7 (% din fundamentala).', ia: 'Masurat sau tipic 6-puls.', practic: 'Contribuie la factorul K si la incalzirea transformatorului.' },
  I11: { def: 'Curentul armonic de ordin 11 (% din fundamentala).', ia: 'Masurat.', practic: 'Pondere mare in factorul K (creste cu h²).', teorie: 'Tipica puntilor de 6 pulsuri.' },
  I13: { def: 'Curentul armonic de ordin 13 (% din fundamentala).', ia: 'Masurat.', practic: 'Pondere mare in factorul K (creste cu h²).' },
  K: { def: 'Factorul K al transformatorului pentru sarcini neliniare.', ia: 'K = Σ (I_h/I_1)²·h².', practic: 'Alege transformator K-rated (K-4/13/20) sau deratuieste-l.', teorie: 'Cuantifica pierderile turbionare suplimentare produse de armonici.' },
}

// Glosar extins (generat) — completeaza acoperirea la toate marimile.
import EXTRA from './glossaryExtra.json'
// Teorie aplicabila (generata) — pentru marimile fara campul "teorie".
import TEORIE from './glossaryTeorie.json'

// Cautare cu fallback pe familie, apoi in glosarul extins.
// Daca intrarea gasita nu are "teorie", o completeaza din glossaryTeorie.json.
export function lookupTerm(key, family) {
  if (!key) return null
  const base = (
    GLOSSARY[`${family}:${key}`] || GLOSSARY[key] ||
    EXTRA[`${family}:${key}`] || EXTRA[key] || null
  )
  if (!base) return null
  if (base.teorie && String(base.teorie).trim()) return base
  const t = TEORIE[`${family}:${key}`] || TEORIE[key]
  return t ? { ...base, teorie: t } : base
}

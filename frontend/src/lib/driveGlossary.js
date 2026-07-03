// Glosar de marimi pentru calculatorul de actionari electrice.
// Cheia = `key`-ul field-ului/rezultatului. Pentru simboluri ambigue intre familii
// (ex. Q = reactiva la asincron vs debit la pompe) se foloseste cheia `familie:key`,
// cu fallback pe cheia simpla. Modalul afiseaza si eticheta + unitatea reale ale marimii.
//
// Fiecare intrare: { def, ia (de unde se ia / cum se obtine), practic (la ce ajuta la PIF) }.

export const GLOSSARY = {
  // --- turatie / frecventa ---
  f: { def: 'Frecvența tensiunii de alimentare la bornele motorului.', ia: 'Rețea (50 Hz) sau setarea/referința convertizorului de frecvență.', practic: 'Pe convertizor o reglezi direct; determină turația câmpului și a motorului.' },
  fn: { def: 'Frecvența nominală de pe plăcuța motorului (uzual 50 Hz).', ia: 'Plăcuța motorului.', practic: 'Punctul de bază al caracteristicii V/f; peste ea intri în slăbire de câmp.' },
  p: { def: 'Numărul total de poli ai motorului (par: 2, 4, 6, 8...).', ia: 'Plăcuța motorului sau dedus din turația nominală.', practic: '4 poli = ~1500 rpm la 50 Hz. Verifică-l la introducerea datelor în drive.' },
  ppp: { def: 'Numărul de perechi de poli (= poli / 2).', ia: 'Din numărul de poli al motorului.', practic: 'Folosit la frecvența electrică f_e = p_pp·n/60 (servo/PMSM).' },
  n: { def: 'Turația mecanică a arborelui.', ia: 'Măsurată (tahometru/encoder) sau de pe plăcuță (turația nominală).', practic: 'O compari cu referința pentru a valida reglajul; bază pentru cuplu și putere.' },
  ns: { def: 'Turația câmpului magnetic învârtitor (turația de sincronism).', ia: 'Calculată: n_s = 120·f / p.', practic: 'Turația maximă teoretică; stabilește f_max în drive (ABB 30.12 / Siemens p1082).' },
  s: { def: 'Alunecarea: diferența relativă între turația sincronă și cea reală.', ia: 'Calculată: s = (n_s − n)/n_s · 100.', practic: 'Crește cu sarcina — indicator de încărcare; folosită la slip compensation.' },
  w: { def: 'Viteza unghiulară mecanică a arborelui.', ia: 'Calculată: ω = 2π·n / 60.', practic: 'Bază pentru putere (P = M·ω) și energie cinetică (½J·ω²).' },
  omega: { def: 'Viteza unghiulară mecanică.', ia: 'ω = 2π·n / 60.', practic: 'Leagă cuplul de putere și intră în timpii de rampă.' },
  fr: { def: 'Frecvența curenților induși în rotor (frecvența de alunecare).', ia: 'f_r = s·f.', practic: '~1-3 Hz la sarcina nominală; benzile de slip în spectru (MCSA) indică bare rupte.' },

  // --- tensiune / curent / putere ---
  U: { def: 'Tensiunea de linie (între faze).', ia: 'Rețeaua (400/690 V) sau ieșirea convertizorului.', practic: 'Cuplul motorului ∝ U²; verifică căderile de tensiune pe cablu.' },
  Un: { def: 'Tensiunea nominală a motorului.', ia: 'Plăcuța motorului.', practic: 'Referință pentru V/f și pentru caracteristica de cuplu.' },
  I: { def: 'Curentul absorbit de linie.', ia: 'Calculat din putere sau măsurat cu cleștele ampermetric.', practic: 'Dimensionare cablu/protecții/drive; orientativ ~1.7-2 A/kW la 400 V.' },
  In: { def: 'Curentul nominal al motorului.', ia: 'Plăcuța motorului.', practic: 'Referință pentru protecția termică și alegerea convertizorului.' },
  I0: { def: 'Curentul de mers în gol (de magnetizare).', ia: 'Măsurat la gol sau ~ I_n·sin φ_n.', practic: 'Aproape constant; sub el curentul nu mai scade cu sarcina.' },
  Igol: { def: 'Curentul de mers în gol (de magnetizare).', ia: '≈ I_n·sin φ_n.', practic: 'Explică de ce cos φ se prăbușește la sarcini mici.' },
  cosphi: { def: 'Factorul de putere: cos al unghiului dintre tensiune și curent.', ia: 'Plăcuța (cos φ nominal) sau măsurat.', practic: 'Scade mult la sarcini parțiale; afectează curentul și compensarea.' },
  cosphin: { def: 'Factorul de putere nominal.', ia: 'Plăcuța motorului.', practic: 'Referință pentru curba cos φ vs sarcină.' },
  eta: { def: 'Randamentul: raportul putere utilă / putere absorbită.', ia: 'Plăcuța / clasa IE / măsurat (bilanț de putere).', practic: 'Motor supradimensionat → randament prost sub ~50% sarcină.' },
  Pn: { def: 'Puterea nominală (mecanică la arbore).', ia: 'Plăcuța motorului.', practic: 'Baza dimensionării; M_n = 9550·P_n / n_n.' },
  P: { def: 'Puterea (mecanică la arbore, dacă nu se specifică altfel).', ia: 'Plăcuța sau P = M·ω.', practic: 'Leagă cuplul de turație; bază pentru curent și energie.' },
  Pel: { def: 'Puterea activă electrică absorbită din rețea.', ia: 'P_el = P_n / η.', practic: 'Folosită la bilanț energetic, cost și calculul reactivei.' },
  S: { def: 'Puterea aparentă.', ia: 'S = √3·U·I.', practic: 'Dimensionarea transformatorului și a aparatajului (kVA).' },
  Q: { def: 'Puterea reactivă (de fundamentală).', ia: 'Q = √(S² − P²).', practic: 'Se compensează cu baterii de condensatoare pentru a ridica cos φ.' },

  // --- cuplu / dinamica ---
  M: { def: 'Cuplul (electromagnetic / la arbore).', ia: 'M = 9550·P / n  (P în kW, n în rpm).', practic: 'Mărimea-cheie la potrivirea motor-sarcină.' },
  Mn: { def: 'Cuplul nominal.', ia: 'M_n = 9550·P_n / n_n.', practic: 'Referință pentru cuplurile de pornire și maxim (multipli din M_n).' },
  Mp: { def: 'Cuplul de pornire.', ia: 'M_p = k_p·M_n (k_p ~1.5-2.5).', practic: 'Trebuie să depășească cuplul rezistent la pornire (cu marjă).' },
  Mmax: { def: 'Cuplul maxim (breakdown / pull-out).', ia: 'M_max = k_m·M_n (k_m ~2-3).', practic: 'Marjă de stabilitate; scade cu pătratul tensiunii (∝ U²).' },
  kp: { def: 'Factorul cuplului de pornire (multiplu din M_n).', ia: 'Catalog / plăcuța (clasa NEMA/IEC).', practic: 'Tipic 1.5-2.5; verifică față de cuplul de desprindere al sarcinii.' },
  km: { def: 'Factorul cuplului maxim (multiplu din M_n).', ia: 'Catalog / plăcuța.', practic: 'Tipic 2-3; marjă față de vârfurile de cuplu ale procesului.' },
  J: { def: 'Momentul de inerție (rezistența la accelerare).', ia: 'Catalog (J sau GD² = 4·J), sau redus la axul motor (J/i²).', practic: 'Determină timpul de accelerare, rampele și energia de frânat.' },
  Jtot: { def: 'Inerția totală (motor + sarcină redusă la ax).', ia: 'J_tot = J_motor + J_sarcina/i².', practic: 'Intră direct în timpul de accelerare și în cuplul dinamic.' },
  Macc: { def: 'Cuplul disponibil pentru accelerare.', ia: 'Cuplul motorului în timpul pornirii (peste cuplul nominal).', practic: 'Diferența (M_acc − M_load) accelerează inerția.' },
  Mload: { def: 'Cuplul rezistent al sarcinii.', ia: 'Din tipul de sarcină (pompă, bandă, etc.) sau măsurat.', practic: 'Dacă depășește cuplul motorului, motorul nu pornește/accelerează.' },
  tacc: { def: 'Timpul de accelerare de la o turație la alta.', ia: 't = J·Δω / (M_acc − M_load).', practic: 'Îl setezi ca rampă în drive (ABB 23.12 / Siemens p1120).' },
  Ecin: { def: 'Energia cinetică a maselor în rotație.', ia: 'E = ½·J·ω².', practic: 'Energia care trebuie disipată la frânare (dimensionare rezistor).' },
  RJ: { def: 'Raportul de inerție sarcină/motor.', ia: 'R_J = J_sarcina_redusa / J_motor.', practic: 'Ținta < 5 (servo) ... < 10 (uz general) pentru reglaj stabil.' },
  i: { def: 'Raportul de transmisie al reductorului.', ia: 'i = n_intrare / n_iesire = z2/z1.', practic: 'Multiplică cuplul și reduce inerția sarcinii (÷i²) la axul motor.' },

  // --- c.c. / servo / sincron ---
  Kt: { def: 'Constanta de cuplu (servo/PMSM).', ia: 'Catalog servo (uzual Nm/A_rms).', practic: 'M = K_t·I_q. Ia-o din catalog — nu o recalcula din tensiune.' },
  Iq: { def: 'Curentul de cuadratură (axa q).', ia: 'Comanda de cuplu în control vectorial.', practic: 'Componenta producătoare de cuplu (cu I_d = 0 la SPM).' },
  E: { def: 'Tensiunea electromotoare indusă (t.c.e.m. / back-EMF).', ia: 'E = k·Φ·ω (c.c.) sau din excitație (sincron).', practic: 'Proporțională cu turația; bază pentru reglajul de tensiune/turație.' },
  Ra: { def: 'Rezistența circuitului de indus.', ia: 'Autotuning (ID-run) sau măsurare (test c.c.).', practic: 'Determină căderea I·R și constantele de timp ale buclei de curent.' },
  La: { def: 'Inductanța circuitului de indus.', ia: 'Autotuning sau catalog.', practic: 'Constanta de timp electrică τ_a = L_a/R_a (răspunsul curentului).' },
  kPhi: { def: 'Constanta mașinii × fluxul (k·Φ), în SI [V·s/rad = Nm/A].', ia: 'Din datele motorului c.c. / identificare.', practic: 'Leagă E de ω și M de I_a; la flux constant M ∝ I_a.' },
  Xs: { def: 'Reactanța sincronă (mașina sincronă).', ia: 'Date motor / catalog.', practic: 'Limitează puterea: P = U·E·sinδ / X_s.' },
  delta: { def: 'Unghiul de sarcină (între tensiune și t.e.m.).', ia: 'Rezultă din încărcare.', practic: 'Cuplu maxim (pull-out) la δ = 90°; stabil doar pentru δ < 90°.' },

  // --- convertizor / instalatie ---
  Udc: { def: 'Tensiunea circuitului intermediar (DC bus).', ia: 'U_dc ≈ 1.35·U_linie (punte cu diode).', practic: 'Pragul chopperului de frânare; o monitorizezi la fault overvoltage.' },
  fsw: { def: 'Frecvența de comutație (purtătoare PWM).', ia: 'Setare convertizor.', practic: 'Compromis: mai mare = mai silențios dar pierderi mai mari → derating de curent.' },
  uk: { def: 'Tensiunea de scurtcircuit / impedanța procentuală.', ia: 'Plăcuța transformatorului / reactorului.', practic: 'I_cc = I_n / (u_k/100); determină și căderea pe reactor.' },
  Icc: { def: 'Curentul de scurtcircuit prezumat.', ia: 'I_cc = I_n_trafo / (u_k/100) + contribuția motoarelor.', practic: 'Alegerea capacității de rupere a disjunctorului (Icu ≥ Icc).' },
  THD: { def: 'Distorsiunea armonică totală a curentului.', ia: 'Din măsurători / estimat pe topologie (6-puls ~30-40%).', practic: 'Verifică față de limita IEEE 519 la punctul de racord (TDD).' },

  // --- pompe (familie: pompe) ---
  'pompe:Q': { def: 'Debitul pompei/ventilatorului.', ia: 'Cerința procesului / curba pompei.', practic: 'La turație variabilă Q ∝ n (legea afinității).' },
  H: { def: 'Înălțimea de pompare (presiunea exprimată în m coloană).', ia: 'Curba pompei / cerința sistemului.', practic: 'H ∝ n² (afinitate); cu înălțime statică apare o turație minimă utilă.' },
  Hstatic: { def: 'Înălțimea statică (diferența de nivel + contrapresiune).', ia: 'Din configurația instalației.', practic: 'Reduce economia față de legea cubului și impune o turație minimă.' },
  NPSHrn: { def: 'NPSH cerut de pompă la turația nominală.', ia: 'Curba producătorului pompei.', practic: 'NPSH_a trebuie să fie ≥ NPSH_r + marjă, altfel cavitație.' },
  nq: { def: 'Turația specifică a pompei.', ia: 'n_q = n·√Q / H^0.75.', practic: 'Identifică tipul rotorului (radial/mixt/axial) și forma curbei.' },
  DC: { def: 'Durata de conectare (factor de serviciu intermitent).', ia: 'Din ciclul real de sarcină (regim S3/S6).', practic: 'La DC < 100% poți încărca motorul peste P_S1: P ∝ 1/√(DC).' },

  // --- mecanic / general ---
  rho: { def: 'Densitatea fluidului.', ia: 'Tabel / proces (apă ~1000, aer ~1.2 kg/m³).', practic: 'Presiunea și puterea pompei/ventilatorului sunt proporționale cu ρ.' },
  m: { def: 'Masa care se deplasează sau se ridică.', ia: 'Din mecanism / proces.', practic: 'Forța = m·g; inerția redusă la ax = m·(pas/2π)² (șurub) sau m·r².' },
  v: { def: 'Viteza liniară.', ia: 'Cerința procesului.', practic: 'Putere = F·v; v = π·D·n/60.' },
  D: { def: 'Diametrul (tambur, roată, pinion, rotor).', ia: 'Desen mecanic.', practic: 'Cuplu = F·D/2; viteza liniară = π·D·n/60.' },
  F: { def: 'Forța (liniară / tangențială / de tracțiune).', ia: 'Din proces (masă, frecare, pantă).', practic: 'Cuplu = F·r; putere = F·v.' },
  r: { def: 'Raza de aplicare a forței (tambur, pârghie).', ia: 'Desen mecanic.', practic: 'Cuplu = F·r.' },
  t: { def: 'Timpul (de măsură / declanșare / frânare).', ia: 'Cerință sau setare.', practic: 'Vezi eticheta pentru rolul exact în modul.' },
  tau: { def: 'Constanta de timp (termică / electrică / mecanică).', ia: 'Catalog sau calcul.', practic: 'Timpul până la ~63% din răspuns. Vezi eticheta.' },
  ratio: { def: 'Raport adimensional între două mărimi.', ia: 'Calculat.', practic: 'Interpretarea depinde de modul (diametre, curenți, vârf/continuu).' },
  df: { def: 'Factor de derating (subunitar).', ia: 'Curba producătorului / standard.', practic: 'Capacitatea rămasă = valoarea nominală × df.' },

  // --- economie ---
  pret: { def: 'Prețul energiei electrice.', ia: 'Factură / contract (lei/kWh).', practic: 'Baza calculului de economie și payback.' },
  ore: { def: 'Orele de funcționare pe an.', ia: 'Regimul de exploatare.', practic: 'Multiplică economia de putere → economie anuală.' },
  invest: { def: 'Investiția (cost echipament).', ia: 'Ofertă.', practic: 'Payback = investiție / economie anuală.' },
  nproc: { def: 'Turația de proces (% din nominal).', ia: 'Cerința procesului.', practic: 'Economia cu VFD ∝ (n%)³ la sarcină pătratică.' },
  Pvana: { def: 'Puterea cu reglaj prin vană/clapetă (100% debit).', ia: 'Regimul actual, fără VFD.', practic: 'Referință pentru economia adusă de VFD.' },

  // --- afinitate pompe ---
  n1: { def: 'Turația inițială / de referință.', ia: 'Nominală sau măsurată.', practic: 'Punct de plecare pentru legile afinității.' },
  n2: { def: 'Turația nouă / dorită.', ia: 'Cerința procesului.', practic: 'La pompe Q∝n, H∝n², P∝n³.' },
  Q1: { def: 'Debitul la turația inițială.', ia: 'Punctul de funcționare nominal.', practic: 'Q ∝ n (afinitate).' },
  Q2: { def: 'Debitul la turația nouă.', ia: 'Calculat din afinitate.', practic: 'Q2 = Q1·(n2/n1).' },
  H1: { def: 'Înălțimea la turația inițială.', ia: 'Curba pompei.', practic: 'H ∝ n².' },
  H2: { def: 'Înălțimea la turația nouă.', ia: 'Calculat.', practic: 'H2 = H1·(n2/n1)².' },
  P1: { def: 'Puterea la turația inițială.', ia: 'Nominală.', practic: 'P ∝ n³.' },
  P2: { def: 'Puterea la turația nouă.', ia: 'Calculat.', practic: 'P2 = P1·(n2/n1)³ — baza economiei VFD.' },
  Hnom: { def: 'Înălțimea la debitul nominal.', ia: 'Curba pompei.', practic: 'Definește coeficientul curbei sistemului.' },
  Qnom: { def: 'Debitul nominal.', ia: 'Curba pompei.', practic: 'Referință pentru curba sistemului și afinitate.' },
  Hshut: { def: 'Înălțimea la debit zero (shutoff).', ia: 'Curba pompei.', practic: 'Turația minimă utilă = n·√(H_static/H_shut).' },
  QBEP: { def: 'Debitul la randament maxim (BEP).', ia: 'Curba pompei.', practic: 'Pompa lucrează eficient și stabil lângă BEP.' },
  Qtarget: { def: 'Debitul cerut de proces.', ia: 'Cerință.', practic: 'Determină turația/frecvența de setat în drive.' },

  // --- asincron extins ---
  etan: { def: 'Randamentul nominal.', ia: 'Plăcuța / clasa IE.', practic: 'Referință pentru curba randament vs sarcină.' },
  Pconst: { def: 'Pierderile fixe (fier + frecare + ventilație).', ia: 'Fișa motor / separare pierderi.', practic: 'Dominante la sarcină mică → randament prost.' },
  Tamb: { def: 'Temperatura ambiantă.', ia: 'Condițiile de instalare.', practic: 'Peste 40°C → derating de curent (~1%/°C).' },
  R1: { def: 'Rezistența înfășurării statorice.', ia: 'Test c.c. / autotuning.', practic: 'Pierderi Cu stator = 3·I²·R1.' },

  // --- servo / c.c. ---
  Ia: { def: 'Curentul de indus (rotor) la mașina de c.c.', ia: 'Măsurat / nominal.', practic: 'La flux constant M ∝ I_a; limita de curent = limita de cuplu.' },
  Ld: { def: 'Inductanța pe axa d (PMSM/sincron).', ia: 'Date motor.', practic: 'Curent caracteristic I_ch = ψ_m/L_d (slăbire de câmp).' },
  Lq: { def: 'Inductanța pe axa q (PMSM/sincron).', ia: 'Date motor.', practic: 'La IPM (Lq>Ld) apare cuplu de reluctanță.' },
  psim: { def: 'Fluxul magneților permanenți (ψ_m).', ia: 'Date motor PMSM.', practic: 'Cuplu de magneți = (3/2)·p·ψ_m·I_q.' },
  Imax: { def: 'Curentul maxim (de vârf).', ia: 'Catalog drive/motor.', practic: 'Limitează cuplul de vârf și gama de putere constantă.' },
  kt: { def: 'Constanta de cuplu (model c.c. serie).', ia: 'Date motor.', practic: 'M = k_t·I_a² (până la saturație).' },
  c: { def: 'Constanta de tensiune (model c.c. serie).', ia: 'Identificare.', practic: 'Turația ~ 1/I_a → pericol de ambalare la gol.' },
  Rt: { def: 'Rezistența totală a circuitului (indus + excitație).', ia: 'Măsurare.', practic: 'Căderea I·R și constanta de timp.' },
  Mvarf: { def: 'Cuplul de vârf cerut de ciclu.', ia: 'Din profilul de mișcare (accelerare).', practic: 'Trebuie ≤ cuplul de vârf al motorului/driveului.' },
  Mcont: { def: 'Cuplul continuu al motorului.', ia: 'Catalog servo.', practic: 'M_rms al ciclului trebuie ≤ M_cont.' },
  Mrms: { def: 'Cuplul termic echivalent pe ciclu.', ia: 'M_rms = √(ΣM²·t / Σt).', practic: 'Baza dimensionării termice a servomotorului.' },
  PPR: { def: 'Impulsuri pe rotație (encoder incremental).', ia: 'Fișa encoder.', practic: 'Rezoluție = 360/(4·PPR) cu decodare în cuadratură.' },
  imp: { def: 'Impulsuri numărate într-o fereastră de timp.', ia: 'Din encoder.', practic: 'Turație = 60·imp/(4·PPR·t).' },

  // --- instalatie / retea ---
  Strafo: { def: 'Puterea transformatorului.', ia: 'Plăcuța trafo.', practic: 'I_n = S/(√3·U); I_cc = I_n/(u_k/100).' },
  Pdrive: { def: 'Puterea totală a drive-urilor alimentate.', ia: 'Suma sarcinilor.', practic: 'Dimensionarea transformatorului (kVA).' },
  Iporn: { def: 'Curentul de pornire.', ia: 'I_p = k·I_n (DOL, k~5-7).', practic: 'Provoacă dip de tensiune pe bară la pornire.' },
  Sccbus: { def: 'Puterea de scurtcircuit a barei.', ia: 'Din rețea / transformator.', practic: 'Dip ≈ S_pornire/(S_pornire + S_cc).' },
  IccPCC: { def: 'Curentul de scurtcircuit la punctul de racord (PCC).', ia: 'De la operatorul de rețea.', practic: 'Raportul Isc/IL stabilește limita TDD (IEEE 519).' },
  Iload: { def: 'Curentul de sarcină maxim.', ia: 'Suma sarcinilor.', practic: 'Numitorul raportului Isc/IL pentru IEEE 519.' },
  Ssc: { def: 'Puterea de scurtcircuit (MVA).', ia: 'Date rețea.', practic: 'Ordinul de rezonanță cu bateria: h = √(S_sc/Q_c).' },

  // --- ambigue dezambiguizate pe familie ---
  'comun:L': { def: 'Lungimea cablului motor.', ia: 'Traseul instalației.', practic: 'Peste o lungime critică apare supratensiune la borne (du/dt).' },
  'servo:L': { def: 'Inductanța înfășurării.', ia: 'Date motor.', practic: 'Constanta de timp electrică τ_e = L/R.' },
  'comun:T': { def: 'Cuplul (la ax / la ieșire).', ia: 'T = F·r.', practic: 'Mărimea transmisă mecanic către sarcină.' },
  'pompe:T': { def: 'Temperatura aerului/gazului.', ia: 'Proces.', practic: 'Densitatea scade cu temperatura → presiune și cuplu mai mici.' },

  Ulinie: { def: 'Tensiunea de linie de alimentare.', ia: 'Rețeaua (400/690 V).', practic: 'Bază pentru U_dc ≈ 1.35·U_linie și pentru V/f.' },
  Ps1: { def: 'Puterea în regim continuu S1.', ia: 'Plăcuța motorului.', practic: 'Baza recalculării la regim intermitent: P ∝ 1/√(DC).' },
  Jsarc: { def: 'Momentul de inerție al sarcinii.', ia: 'Catalog / calcul (geometrie + masă).', practic: 'Redus la axul motor = J_sarcina/i².' },
  Jmot: { def: 'Momentul de inerție al motorului.', ia: 'Catalog motor.', practic: 'Numitorul raportului de inerție R_J (ținta < 5-10).' },
  etap: { def: 'Randamentul pompei.', ia: 'Curba pompei.', practic: 'P_arbore = P_hidraulic / η_pompa.' },
  etam: { def: 'Randamentul motorului.', ia: 'Plăcuța / clasa IE.', practic: 'Parte din lanțul wire-to-water.' },
  etad: { def: 'Randamentul convertizorului.', ia: 'Catalog (~0.97-0.99).', practic: 'Putere din rețea = P_motor / η_drive.' },
  etalow: { def: 'Randamentul clasei de eficiență joase (ex. IE2).', ia: 'Catalog motor.', practic: 'Comparație de economie între clase IE.' },
  etahigh: { def: 'Randamentul clasei superioare (ex. IE3/IE4).', ia: 'Catalog motor.', practic: 'Economia anuală față de clasa joasă.' },
  dpret: { def: 'Diferența de preț a motorului premium.', ia: 'Ofertă.', practic: 'Payback = Δpret / economia anuală.' },
  payback: { def: 'Perioada de recuperare a investiției.', ia: 'Investiție / economia anuală.', practic: 'Sub ~2-3 ani justifică investiția în VFD sau motor premium.' },
  Pies: { def: 'Puterea de ieșire a convertizorului către motor.', ia: 'Din puterea motorului.', practic: 'Baza estimării pierderilor convertizorului și a deratingului.' },
  Iech: { def: 'Curentul termic echivalent (RMS) pe ciclul de sarcină.', ia: 'I_ech = √(Σ I²·t / Σ t).', practic: 'Se compară cu curentul nominal pentru dimensionare termică la sarcini ciclice.', teorie: 'Încălzirea depinde de media pătratică a curentului (efect Joule I²t).' },
  I1: { def: 'Curentul primului segment al ciclului de sarcină.', ia: 'Din profilul de sarcină (regim intermitent).', practic: 'Intră în calculul curentului termic echivalent.' },
  t1: { def: 'Durata primului segment de sarcină.', ia: 'Din ciclul de lucru.', practic: 'Ponderează segmentul în curentul echivalent.' },
  t2: { def: 'Durata celui de-al doilea segment de sarcină.', ia: 'Din ciclul de lucru.', practic: 'Ponderează segmentul în curentul echivalent.' },
  Ps3: { def: 'Puterea admisibilă în regim intermitent S3.', ia: 'P_S1 / √(DC/100).', practic: 'Dimensionarea motorului la sarcină intermitentă periodică.', teorie: 'La DC < 100% puterea admisă crește cu 1/√DC față de regimul continuu.' },
  falt: { def: 'Factor de derating la altitudine.', ia: '1 − (H−1000)/10000, peste 1000 m.', practic: 'Reduce curentul admisibil; verifică curba producătorului.', teorie: 'Răcirea scade cu densitatea aerului la altitudine (~1%/100 m).' },
  ftemp: { def: 'Factor de derating la temperatura ambiantă.', ia: '1 − (T−40)/100, peste 40°C.', practic: 'Reduce curentul admisibil ~1%/°C peste 40°C.', teorie: 'Capacitatea de evacuare a căldurii scade cu temperatura mediului.' },
  OLHD: { def: 'Suprasarcina admisă în regim Heavy Duty.', ia: '150% I_n timp de 1 min la fiecare 5 min (ABB).', practic: 'Pentru cupluri de șoc: concasoare, benzi încărcate, mecanisme de ridicat.' },
  OLND: { def: 'Suprasarcina admisă în regim Normal / Light Duty.', ia: '110% I_n timp de 1 min la fiecare 5 min (ABB).', practic: 'Pentru pompe și ventilatoare (sarcină pătratică).' },
  Inest: { def: 'Curentul nominal estimat al motorului la 400 V.', ia: '~1.9·P[kW] (orientativ).', practic: 'Util când lipsește plăcuța; verifică întotdeauna valoarea reală.', teorie: 'I = P / (√3·U·cosφ·η).' },
  f1: { def: 'Frecvența rețelei de alimentare.', ia: '50 Hz în Europa.', practic: 'Baza pentru frecvența de acord a reactorului și de rezonanță.' },
  tride: { def: 'Timpul de susținere a convertizorului la microîntreruperi (ride-through).', ia: 'Energia DC bus / puterea sarcinii.', practic: 'Compară cu durata tipică a dip-urilor de rețea (zeci de ms).', teorie: 't = ½·C·(U1² − U2²) / P.' },
  I5: { def: 'Curentul armonic de ordin 5 (% din fundamentală).', ia: 'Măsurat sau tipic redresor 6-puls.', practic: 'Cea mai mare armonică; pondere importantă în factorul K.', teorie: 'Armonica 5 e de secvență inversă.' },
  I7: { def: 'Curentul armonic de ordin 7 (% din fundamentală).', ia: 'Măsurat sau tipic 6-puls.', practic: 'Contribuie la factorul K și la încălzirea transformatorului.' },
  I11: { def: 'Curentul armonic de ordin 11 (% din fundamentală).', ia: 'Măsurat.', practic: 'Pondere mare în factorul K (crește cu h²).', teorie: 'Tipică punților de 6 pulsuri.' },
  I13: { def: 'Curentul armonic de ordin 13 (% din fundamentală).', ia: 'Măsurat.', practic: 'Pondere mare în factorul K (crește cu h²).' },
  K: { def: 'Factorul K al transformatorului pentru sarcini neliniare.', ia: 'K = Σ (I_h/I_1)²·h².', practic: 'Alege transformator K-rated (K-4/13/20) sau deratuiește-l.', teorie: 'Cuantifică pierderile turbionare suplimentare produse de armonici.' },
}

// Glosar extins (generat) — completeaza acoperirea la toate marimile.
import EXTRA from './glossaryExtra.json'
// Teorie aplicabila (generata) — pentru marimile fara campul "teorie".
import TEORIE from './glossaryTeorie.json'
// Strat imbogatit (def + teorie mai detaliate, notatie RO/IEC + KaTeX) — suprascrie baza.
import RICH from './glossaryRich.json'

// Cautare cu fallback pe familie, apoi in glosarul extins.
// Daca intrarea gasita nu are "teorie", o completeaza din glossaryTeorie.json.
// Stratul RICH (glossaryRich.json) suprascrie def + teorie cand exista.
export function lookupTerm(key, family) {
  if (!key) return null
  const base = (
    GLOSSARY[`${family}:${key}`] || GLOSSARY[key] ||
    EXTRA[`${family}:${key}`] || EXTRA[key] || null
  )
  const rich = RICH[`${family}:${key}`] || RICH[key] || null
  if (!base && !rich) return null
  let out = base ? { ...base } : {}
  if (!(out.teorie && String(out.teorie).trim())) {
    const t = TEORIE[`${family}:${key}`] || TEORIE[key]
    if (t) out.teorie = t
  }
  if (rich) out = { ...out, ...rich }
  return out
}

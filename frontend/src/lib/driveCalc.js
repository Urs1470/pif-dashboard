// Calculator actionari electrice — motor de calcul data-driven.
//
// Fiecare modul declara:
//   id, family, tier, title, subtitle?, note?, params? (referinte drive ABB/Siemens)
//   fields[]  : intrari { key, label, unit, default, step?, min? }
//   results[] : iesiri  { key, label, unit, tex (LaTeX), calc(v, r), dec? }
//
// calc(v, r): v = valorile de intrare (coercite la numere), r = rezultatele deja
// calculate in acest modul (in ordine). Intoarce null => se afiseaza "—".
//
// Formule verificate adversarial (workflow drive-calc-equations / -motor-types) si
// confirmate din wiki_job: ABB Technical Guide Book No.7/8/9 + Chapman + Hughes.
// Parametri drive confirmati din manualele de firmware (ACS880/DCS880/G120/S120/DCM).
// Tensiune doar JT (400/690 V).

export const FAMILIES = [
  { id: 'asincron', label: 'Asincron' },
  { id: 'pompe', label: 'Pompe & ventilatoare' },
  { id: 'cc', label: 'Curent continuu' },
  { id: 'servo', label: 'Servo / PMSM' },
  { id: 'sincron', label: 'Sincron' },
  { id: 'comun', label: 'Comune' },
]

// --- Structura: categorii de nivel 1 (taburi principale) ---
// 'aplicatii' si 'motoare' au sub-taburi; restul sunt categorii directe.
export const CATEGORIES = [
  { id: 'aplicatii', label: 'Aplicatii' },
  { id: 'motoare', label: 'Masini electrice' },
  { id: 'vfd', label: 'Convertizor / VFD' },
  { id: 'armonici', label: 'Armonici & calitate energie' },
  { id: 'instalatie', label: 'Instalatie electrica' },
  { id: 'termic', label: 'Termic, regimuri & eficienta' },
  { id: 'utilitare', label: 'Utilitare' },
]
// Sub-taburi pentru 'Motoare' (pe tip de motor).
export const MOTOR_FAMS = [
  { id: 'asincron', label: 'Asincron' },
  { id: 'cc', label: 'Curent continuu' },
  { id: 'servo', label: 'Servo / PMSM' },
  { id: 'sincron', label: 'Sincron' },
  { id: 'transformator', label: 'Transformatoare' },
]
// 'Aplicatii' inglobeaza fostele taburi Pompe & Mecanica (grupate pe tip de masina/proces).
// APP_OF da O SINGURA casa fiecarui card -> FARA dublare.
export const APPLICATIONS = [
  { id: 'pompe-vent', label: 'Pompe & ventilatoare' },
  { id: 'compresoare', label: 'Compresoare' },
  { id: 'ridicare', label: 'Macarale & ridicare' },
  { id: 'transportoare', label: 'Transportoare' },
  { id: 'winder', label: 'Infasurare (winder)' },
  { id: 'mecanica-gen', label: 'Mecanica generala' },
]
export const APP_OF = {
  'pompa-sistem': 'pompe-vent', 'turatie-minima': 'pompe-vent', 'npsh': 'pompe-vent', 'putere-pompa': 'pompe-vent', 'ventilator-densitate': 'pompe-vent', 'turatie-specifica': 'pompe-vent', 'economie-profil': 'pompe-vent', 'randament-pompa': 'pompe-vent', 'debit-minim': 'pompe-vent', 'trimming-rotor': 'pompe-vent', 'sarcina-afinitate': 'pompe-vent',
  'compresor-volant': 'compresoare',
  'macara': 'ridicare', 'contragreutate': 'ridicare',
  'transportor': 'transportoare', 'frecare': 'transportoare',
  'winder': 'winder', 'taper': 'winder',
  'dinamica': 'mecanica-gen', 'raport-inertie': 'mecanica-gen', 'transmisii': 'mecanica-gen', 'cuplaj': 'mecanica-gen', 'turatie-critica': 'mecanica-gen', 'surub-bile': 'mecanica-gen', 'liniar-raza': 'mecanica-gen',
  // adaugiri PIF
  'run-up': 'mecanica-gen', 'lovitura-berbec': 'pompe-vent', 'pid-drive': 'pompe-vent',
}
// Categoria de domeniu a celorlalte module (cele de motor cad implicit pe 'motoare').
export const CAT_OF = {
  // convertizor / VFD
  'vfd': 'vfd', 'selectie-drive': 'vfd', 'comutatie': 'vfd', 'unda-reflectata': 'vfd', 'filtru-iesire': 'vfd', 'ride-through': 'vfd', 'kinetic-buffer': 'vfd', 'curenti-rulment': 'vfd', 'derating-vfd-motor': 'vfd',
  'moduri-control': 'vfd', 'control-vf': 'vfd', 'modulatie-busdc': 'vfd', 'ripple-pwm': 'vfd',
  // armonici & calitate energie
  'armonici': 'armonici', 'ieee519': 'armonici', 'factor-putere-vfd': 'armonici', 'comparatie-frontend': 'armonici', 'rezonanta-cond': 'armonici', 'reactor-detunare': 'armonici',
  // instalatie electrica
  'cablu': 'instalatie', 'cablu-protectii': 'instalatie', 'scurtcircuit': 'instalatie', 'dip-pornire': 'instalatie',
  'protectie-motor': 'instalatie', 'pe-defect': 'instalatie',
  // transformatoare (sub-tab in 'Masini electrice') — au family:'transformator', deci NU sunt in CAT_OF (cad pe 'motoare')
  // termic, regimuri & eficienta
  'termic': 'termic', 'motor-termic': 'termic', 'regimuri-s': 'termic', 'viata-termica-s10': 'termic', 'porniri-ora': 'termic', 'derating-armonici-motor': 'termic', 'clase-ie': 'termic', 'energie-roi': 'termic', 'lcc': 'termic',
  // utilitare
  'conversii': 'utilitare', 'vibratii': 'utilitare', 'grade-ip': 'utilitare',
  // adaugiri PIF
  'izolatie': 'instalatie', 'franare-rezistenta': 'vfd', 'sto-ss1': 'vfd', 'retea-emc': 'instalatie', 'sil-pl': 'vfd',
}
// Categoria unui modul: aplicatie (daca e in APP_OF) -> 'aplicatii'; altfel domeniul; altfel 'motoare'.
export function catOf(m) { return APP_OF[m.id] ? 'aplicatii' : (CAT_OF[m.id] || 'motoare') }

// Ordinea logica de afisare a modulelor in fiecare familie (flux ingineresc:
// de la marimile de placuta spre dimensionare/diagnoza).
export const MODULE_ORDER = [
  // asincron: marimi de baza -> diagnoza avansata (schema echiv./teste/randament)
  'motor-turatie', 'putere-curent', 'cuplu', 'asincron-camp-slabit', 'sarcina-afinitate', 'pornire', 'incarcare',
  'motor-echivalent', 'bilant-putere', 'teste-parametri', 'randament-sarcina', 'dezechilibru',
  'motor-termic', 'clase-ie', 'derating-vfd-motor',
  'cosphi-sarcina', 'derating-armonici-motor', 'regimuri-s', 'viata-termica-s10', 'porniri-ora',
  // pompe & ventilatoare
  'pompa-sistem', 'turatie-minima', 'npsh', 'putere-pompa', 'ventilator-densitate', 'turatie-specifica',
  'economie-profil', 'randament-pompa', 'debit-minim', 'trimming-rotor',
  // c.c.: fundamental -> tipuri -> reglaj -> camp -> comutatie -> convertor -> factor forma -> franare -> serie -> randament -> pornire
  'cc-baza', 'cc-excitatii', 'cc-reglaj', 'cc-camp', 'cc-comutatie', 'cc-drive', 'cc-factor-forma', 'cc-franare', 'cc-serie', 'cc-randament', 'cc-pornire-trepte',
  // servo: model -> ciclu -> feedback -> camp slabit -> control (PI/raspuns/profil)
  'pmsm-model', 'pmsm-ciclu', 'pmsm-feedback', 'pmsm-camp-slabit', 'acordare-pi', 'raspuns-ord2', 'profil-miscare',
  'ipmsm-mtpa', 'suprasarcina-servo',
  // sincron: turatie -> putere -> poli aparenti -> SynRM
  'sincron-turatie', 'sincron-putere', 'sincron-poli-aparenti', 'synrm', 'vcurves',
  // transformatoare (sub-tab in Masini electrice)
  'transformator', 'ploturi', 'trafo-grupa-conexiuni', 'trafo-12pulse', 'trafo-scurtcircuit', 'incarcare-trafo', 'factor-k', 'compensare',
  // comune: selectie -> convertizor -> dinamica/tuning/rezonanta -> mecanica -> energie
  //         -> instalatie (cablu/protectii/scurtcircuit/trafo/dip) -> calitate energie -> utilitar
  'selectie-drive', 'vfd', 'moduri-control', 'control-vf', 'modulatie-busdc', 'ripple-pwm', 'comutatie', 'unda-reflectata', 'filtru-iesire', 'ride-through', 'kinetic-buffer', 'curenti-rulment',
  'dinamica', 'raport-inertie', 'turatie-critica', 'transmisii', 'cuplaj',
  'surub-bile', 'liniar-raza', 'macara', 'contragreutate', 'transportor', 'winder', 'taper', 'frecare', 'compresor-volant',
  'energie-roi', 'lcc', 'cablu', 'cablu-protectii', 'scurtcircuit', 'dip-pornire', 'protectie-motor', 'pe-defect',
  'termic', 'armonici', 'factor-putere-vfd', 'ieee519', 'comparatie-frontend', 'rezonanta-cond', 'reactor-detunare', 'conversii', 'vibratii', 'grade-ip',
  // adaugiri PIF (verificare 2026)
  'izolatie', 'run-up', 'franare-rezistenta', 'encoder-offset', 'notch-rezonanta', 'sto-ss1', 'sil-pl', 'lovitura-berbec', 'pid-drive', 'retea-emc',
]

// Proveninta formulelor (verificat din carti/ghiduri — vezi wiki_job/theory).
export const SOURCES = {
  'motor-turatie': 'Chapman, Electric Machinery Fundamentals — ec. 7-1/7-3/7-8 (p.363-365)',
  'putere-curent': 'ABB Technical Guide Book No.4 (p.166) + triunghiul puterilor (No.6, p.260)',
  'cuplu': 'ABB Technical Guide Book No.7 (p.169) + Chapman (cuplu max, p.388)',
  'asincron-camp-slabit': 'ABB Technical Guide Book No.7 (zona de putere constanta) + Mohan/Leonhard (M~1/n zona II, M_max~1/n² zona III); IEC 60034-1. Putere constanta pana la n2 = k_m·n_baza.',
  'sarcina-afinitate': 'ABB Technical Guide Book No.7 — Load types, lege afinitate (p.288)',
  'pornire': 'Hughes, Electric Motors and Drives — cap.6 Starting (p.197-200)',
  'incarcare': 'P_ax: definitie putere trifazata. Incarcare din curent: regula practica de teren (estimare)',
  'dinamica': 'ABB Technical Guide Book No.7 — Basic mechanical laws (cap.5.1, ec.5.2-5.4)',
  'energie-roi': 'ABB Technical Guide Book No.7 — Load types, lege cubica P~n³ (p.288)',
  'protectie-motor': 'IEC 60947-4-1 (relee de suprasarcina, clase de declansare 10/20/30 la 7,2·Ie din cald); model I²t orientativ',
  'pe-defect': 'IEC 60364-4-41 (protectie la soc, timpi de deconectare 0,4/5 s) + 60364-5-54 (sectiune conductor PE) + NP I7-2011',
  'lcc': 'Analiza cost pe ciclu de viata (CAPEX + energie actualizata, factor de anuitate); metoda economica standard (ex. ghiduri pompe Europump/Hydraulic Institute)',
  'cuplaj': 'Dimensionare cuplaj dupa factor de serviciu (uzanta producatori: KTR / Flender / Rexnord)',
  'vfd': 'Mohan, Power Electronics (Udc=1.35·U, V/f cap.14) + ABB TGB No.4 (randament)',
  'cablu': 'Cadere de tensiune trifazata: ΔU=√3·I·L·(R·cosφ+X·sinφ), aici cu X neglijat',
  'termic': 'I_ech (RMS) / IEC 60034-1 regim S3 + derating ABB ACS880 (manual HW)',
  'armonici': 'Impedanta procentuala reactor + regula THD: ABB TGB No.6 (p.248)',
  'compensare': 'Triunghiul puterilor (Q=P·tanφ) — dimensionare baterie condensatoare',
  'transmisii': 'ABB Technical Guide Book No.7 — Gears & inertia (cap.5.2, p.286-287)',
  'selectie-drive': 'ABB ACS880-01 Single Drives Catalog (p.17, I_Hd / I_Ld)',
  'raport-inertie': 'Regula de proiectare servo (raport inertie) + ABB TGB No.7 cap.5.2',
  'turatie-critica': 'Frecventa naturala ω_n=√(k/m); ABB TGB No.4 (turatii critice, p.180)',
  'conversii': 'Definitii de unitati SI',
  'cc-baza': 'Chapman, Electric Machinery Fundamentals — cap.8-9 (ec. 8-38/8-49, 9-7)',
  'cc-reglaj': 'Chapman cap.9.4 (slabire camp, p.520-521) + ABB TGB No.7 (putere const.)',
  'cc-drive': 'Mohan, Power Electronics — punte comandata (ec. 6-40/6-41) + constante timp (ec. 13-25/26)',
  'pmsm-model': 'Hughes (Kt=Ke, p.103-104) + Chapman (f_e, p.279)',
  'pmsm-ciclu': 'Regula servo-sizing (cuplu RMS) — fise tehnice producatori (ABB/Siemens/B&R)',
  'pmsm-feedback': 'Hughes (τ_e=L/R, τ_m=RJ/k², p.119) + metrologie encoder cuadratura',
  'sincron-turatie': 'Chapman — cap.4-5 (n_s ec.4-34, diagrama fazoriala p.261-263)',
  'sincron-putere': 'Chapman — cap.5.6 (ec. 5-20/5-21/5-22, p.264-265)',
  'motor-echivalent': 'Chapman — schema echivalenta / Thevenin (ec. 7-41…7-50, p.383-385)',
  'bilant-putere': 'Chapman — diagrama flux de putere (Fig. 7-13, p.371)',
  'teste-parametri': 'Chapman — teste gol / c.c. / rotor blocat (ec. 7-58…7-68) + IEEE 112',
  'randament-sarcina': 'Chapman — separare pierderi fixe/variabile (p.371-372) + ABB TGB',
  'dezechilibru': 'IEC/EN 60034-1 (derating la dezechilibru) + EN 50160 / IEC 61000-4-30 (componente simetrice); (NEMA MG-1 §14.35 echiv. US)',
  'pompa-sistem': 'EN ISO 9906 (incercari pompe) + KSB Centrifugal Pump Lexicon — punct functionare curba sistem × pompa. (Hydraulic Institute echiv. US)',
  'turatie-minima': 'Pumps & Systems — capcana capului static / turatie minima utila',
  'npsh': 'EN ISO 9906 (NPSH3, criteriu de scadere 3%) + KSB Lexicon; NPSHr ∝ n²',
  'putere-pompa': 'Putere hidraulica P=ρgQH; wire-to-water (lant de randamente)',
  'ventilator-densitate': 'EngineeringToolbox — fan affinity + densitate aer; TCF Fan Engineering FE-1600',
  'turatie-specifica': 'KSB Centrifugal Pump Lexicon — turatie specifica n_q',
  'cablu-protectii': 'IEC 60364-5-54 (I²t adiabatic, S=I√t/k) + IEC 60364-5-52 (ampacitate, factori)',
  'scurtcircuit': 'IEC 60909-0 (Icc; Icc_trafo=I_n/u_k; contributie motor ~ rotor blocat)',
  'ieee519': 'IEC 61000-3-12 (limite armonici cu Rsce) + IEC 61000-2-4 (niveluri compatibilitate) + EN 50160 (THD_U ≤ 8%); (IEEE 519 Tab.2 echiv. US)',
  'rezonanta-cond': 'Schneider Electrical Installation Guide — h_rez=√(S_sc/Q_c)',
  'transformator': 'IEC 60076-1 (putere nominala) + IEC 61378-1 (trafo pt convertizoare). Dimensionare din sarcina (S_tr=S·k_rez) SI din pornire (S_tr=k_por·S_mot·u_k/ΔU_max, legat de caderea la pornire). Raport trafo/motor pe tip de pornire.',
  'trafo-grupa-conexiuni': 'IEC 60076-1 (marcarea bornelor & grupe de conexiuni); indice orar ×30°. Dyn11 standard JT. Paralel: aceeasi grupa + raport + u_k apropiat.',
  'trafo-12pulse': 'IEC 61378-1 (trafo pt convertizoare) + IEC 61000-2-4 (niveluri compatibilitate industriale); doua secundare la 30° (Dy11+Dd0) -> 12 pulsuri; armonici caracteristice h=12k±1; anulare 5/7 ~85-95%.',
  'trafo-scurtcircuit': 'IEC 60909-0 (Icc=I_n/u_k) + IEC 60076-5 (tinuta la scurtcircuit); varf i_p=κ√2·Icc (κ≈1.8 JT); I²t solicitare termica; inrush 8-12×I_n. (IEEE C57 echiv. US)',
  'incarcare-trafo': 'IEC 60076-7 (ghid de incarcare trafo in ulei): hot-spot θh=θa+Δθo+Δθh; rata de imbatranire V=2^((θh-98)/6). Limite 98/120/140°C.',
  'ploturi': 'IEC 60076-21 (regulatoare de tensiune pas cu pas) + IEC 60076-1; domeniu reglaj ±n·pas, off-load ±2×2,5% uzual sau OLTC.',
  'sil-pl': 'IEC 62061 (SIL la masini) + ISO 13849-1 (PL din PFH/MTTFd/DC/Categorie) + IEC 61800-5-2 (STO/SS1). STO uzual SIL2/PLd/Cat3.',
  'vibratii': 'IEC 60034-14 (vibratii mecanice — limite de severitate mm/s RMS pe inaltime de ax, grad A/B) + ISO 20816 (sistem montat).',
  'grade-ip': 'IEC 60034-5 (grade de protectie IP pentru masini rotative): prima cifra=corpuri solide, a doua=apa.',
  'dip-pornire': 'ΔU≈S_pornire/(S_pornire+S_cc); IEC/EN 60909 + EN 50160. (IEEE 141 echiv. US, limita ~15%)',
  'comutatie': 'Mohan — pierderi comutatie/conductie (ec. 2-6/2-7) + datasheet IGBT (E_on+E_off)',
  'moduri-control': 'Mohan/Leonhard (V/f, FOC) + ABB Technical Guide (DTC, ghid nr.1); cifre acuratete catalog ABB/Siemens',
  'control-vf': 'V/f scalar (Mohan cap.8 / Leonhard); boost IR + compensare alunecare din manuale ABB/Siemens/Danfoss',
  'modulatie-busdc': 'Mohan — SVPWM (U_LL,RMS = U_dc/√2 ≈ 0.707·U_dc); redresor diode 6-puls U_dc = 1.35·U_retea (3√2/π)',
  'ripple-pwm': 'Mohan — ondulatie de curent PWM; ΔI_pp ≈ U_dc/(8·L_σ·f_sw) (aproximare medie, L_σ = inductanta de scapari)',
  'unda-reflectata': 'IEC/EN 60034-25 + IEC/TS 60034-18-41 (anvelopa izolatie, dv/dt) + ABB TGB No.5; L_crit=v·t_r/2. (NEMA MG-1 Part 31 echiv. US)',
  'ride-through': 'E=½C·U²; prag undervoltage VFD ~0.65·U_dc (voltage-disturbance.com)',
  'curenti-rulment': 'ABB Technical Guide Book No.5 (Bearing currents) — U_cm∝U_dc, BVR',
  'surub-bile': 'Oriental Motor — Motor Sizing (J=m(p/2π)²) + ABB TGB No.7 (T=F·r)',
  'liniar-raza': 'LinearMotionTips + ABB TGB No.7 (T=F·r, v=ω·r, J=m·r²)',
  'macara': 'ABB Technical Guide Book No.8 (Crane, motoring/generating) — P=m·g·v/η',
  'transportor': 'CEMA Belt Book (forta de tractiune, P=F·v/η)',
  'winder': 'ABB Technical Guide Book No.7 (winder, putere constanta, T=F·r)',
  'frecare': 'Frecare statica vs dinamica (Oriental Motor / Fluid Power Journal) — T=μ·N·r',
  'acordare-pi': 'Modulus & symmetric optimum (proiectare drive) + Nise cap.4',
  'raspuns-ord2': 'Nise, Control Systems Engineering — cap.4 (Mp, t_s, t_p, ω_BW)',
  'pmsm-camp-slabit': 'MathWorks — PMSM Constraint Curves (I_ch=ψ_m/L_d, elipsa de tensiune)',
  'profil-miscare': 'Technosoft / Industrial Monitor Direct — trapezoidal vs S-curve (jerk)',
  'sincron-poli-aparenti': 'Chapman — masini sincrone poli aparenti (P cu 2 termeni)',
  'synrm': 'Teorie SynRM/IPM — M=(3/2)p(L_d−L_q)i_d i_q, MTPA la 45° (MDPI/IET)',
  'cc-serie': 'Chapman — motor c.c. serie (M∝I_a², n~1/I_a)',
  'cc-randament': 'Chapman cap.8 (diagrama flux putere c.c.) + Hughes cap.3',
  'cc-excitatii': 'Chapman cap.8-9 (excitatie separat/sunt/serie/compus) + Hughes (serie n~1/√M, ambalare la gol) — recunoastere retrofit',
  'cc-camp': 'Chapman (circuit de excitatie, raspuns L/R, slabire de camp) + Mohan (alimentare camp prin redresor, fortare) + IEC 60034-1; ABB DCS880 grup 28 / Siemens DCM p50080/p50100/p50105',
  'cc-comutatie': 'Chapman/Fitzgerald/Say (reactia indusului, poli auxiliari, infasurare de compensare) + Hughes (limita viteza periferica 30-40 m/s, raport slabire camp) + ABB TGB No.8',
  'cc-factor-forma': 'Mohan (ondulatie curent indus la redresor comandat) + IEC 60034-1 (factor de forma, incalzire) + IEC 60034-19 (incercari masini c.c.); 12 pulsuri ~ injumatatire ondulatie (analiza armonica B6/B12)',
  'cc-franare': 'Chapman (franare dinamica pe rezistor, M_b=kΦI_b) + Mohan (franare recuperativa, convertor 4 cadrane) + ABB DCS880 / Siemens DCM (2Q/4Q)',
  'motor-termic': 'Hughes — constanta de timp termica (p.45); model I²t protectie motor',
  'clase-ie': 'IEC 60034-30-1 / 30-2 (clase IE1-IE5) — pierderi & economie',
  'derating-vfd-motor': 'WEG — motoare pe PWM (curbe derating autovent./fortat); Hughes cap.7',
  'cosphi-sarcina': 'Chapman — curent activ vs magnetizant (model triunghi de curenti)',
  'derating-armonici-motor': 'IEC/EN 60034-25 (motor pe convertizor) + IEC 60034-1 (derating); (HVF din NEMA MG-1 Part 30 echiv. US)',
  'regimuri-s': 'IEC 60034-1 §4.2 (regimuri S1-S10, CDF per tip); S2 din model termic exponential, S6 cu pierderi mers-in-gol, Pech = echivalent termic RMS',
  'viata-termica-s10': 'IEC 60034-1 S10 + Annex A (durata de viata termica relativa); regula Montsinger/10K (IEC 60085 clase termice)',
  'porniri-ora': 'Hughes (energie/incalzire la pornire) + NEMA MG-1 §12.50 (z0)',
  'economie-profil': 'ABB Technical Guide Book (flow control) — economie ponderata pe profil',
  'randament-pompa': 'Putere arbore cu η(Q) la BEP (ChangYu / Powderprocess)',
  'debit-minim': 'Pumps & Systems — MCSF / debit minim stabil (~10-25% Q_BEP)',
  'trimming-rotor': 'EngineeringToolbox — legi de diametru (Q~D, H~D², P~D³)',
  'compresor-volant': 'NPTEL Flywheel (J=ΔE/(C_s·ω²)) + Ariel (process motor sizing)',
  'reactor-detunare': 'Schneider EIG / xbrele — p=X_L/X_C, f_acord=f1/√p, U_C=U_n/(1-p)',
  'factor-k': 'IEC 60076-1 Anexa E (factor de pierderi armonice FHL / factor K); K = Σ(I_h/I_1)²h². (IEEE C57.110 echiv. US)',
  'factor-putere-vfd': 'ABB Technical Guide Book No.6 — PF vs DPF, μ=1/√(1+THD²)',
  'comparatie-frontend': 'ABB TGB No.6 (THD tipic 6/12-puls/AFE) + IEC 61000-3-12 / EN 50160; (IEEE 519 TDD echiv. US)',
  'filtru-iesire': 'Mohan (filtru LC, f_c=1/2π√LC) + ABB TGB (du/dt filter)',
  'kinetic-buffer': 'ABB Technical Guide Book No.8 (energie cinetica) — E=½J(ω1²-ω2²)',
  'contragreutate': 'Echilibrarea ascensoarelor (counterbalancing) + ABB TGB No.8 (4Q)',
  'taper': 'ABB Technical Guide Book No.1 (DTC winder, control tensiune) — taper',
  'ipmsm-mtpa': 'MathWorks — IPMSM M=1.5p[ψ_m·I_q+(L_d−L_q)I_d·I_q], MTPA',
  'suprasarcina-servo': 'Curba overload servo I²t (ACS880/S120) + Hughes (model termic)',
  'cc-pornire-trepte': 'Progresie geometrica (Fitzgerald) — R=U/I_max, trepte γ=I_max/I_min',
  'vcurves': 'Chapman — curbele in V (I_a vs I_f la P const), Q=(U·E·cosδ−U²)/X_s',
  // adaugiri PIF (verificare 2026, surse IEC/EN)
  'izolatie': 'IEC/EN 60034-27-4 (rezistenta izolatie & indice de polarizare); IR_min=(U_n[kV]+1) MΩ. Echiv. US: IEEE 43',
  'run-up': 'IEC/EN 60034-1 (timp de demaraj) + IEC 60034-12 (caracteristici pornire); t_E la motoare Ex: IEC 60079-7',
  'franare-rezistenta': 'IEC/EN 61800-2/-5-1; E=½·J·(ω1²−ω2²); ghiduri rezistente de franare ABB/Danfoss/SEW',
  'encoder-offset': 'IEC/EN 60034-25; autophasing ABB ACS880 / Siemens SINAMICS S120 (pole position p1990/p1980)',
  'notch-rezonanta': 'IEC/EN 61800-2; sistem cu 2 inertii (cuplaj elastic); literatura control servo (Ellis, Control System Design)',
  'sto-ss1': 'IEC/EN 61800-5-2 (functii de siguranta STO/SS1) + IEC 60204-1 (categorii de stop 0/1)',
  'lovitura-berbec': 'EN 805 (regim tranzitoriu retele de apa); principiul Joukowsky Δp=ρ·a·Δv; timp critic Tc=2L/a',
  'pid-drive': 'Ziegler-Nichols (oscilatie critica Ku/Tu); manuale ABB ACS580/880 (PID intern), Siemens G120 (technology controller)',
  'retea-emc': 'IEC 60364 (legare la pamant TN/TT/IT) + IEC/EN 61800-3 (EMC C1-C4); manuale instalare ABB ACS580/880 si Siemens G120 (IT / corner-grounded)',
}

// --- Documentatie: manuale ABB gazduite (deep-link la pagina) + surse online (engleza) ---
// Ghidurile ABB sunt compilate in abb-technical-guide-book.pdf (448 pag); #page sare la ghidul corect.
// PDF.js viewer gazduit: deschide manualul la pagina SI cauta+hasureaza termenul (search + phrase=true).
const _PDFJS = '/static/pdfjs/web/viewer.html?file='
const _ABB_FILE = encodeURIComponent('/static/docs/abb-technical-guide-book.pdf')
const _NO1_FILE = encodeURIComponent('/static/docs/abb-technical-guide-no1.pdf')
const abbView = (search, page) => `${_PDFJS}${_ABB_FILE}#page=${page}&search=${encodeURIComponent(search)}&phrase=true`
// Ancore ABB pe TOPIC (nu pe ghid generic) — fiecare cade pe formula/paragraful relevant,
// verificat ca prima potrivire e in CORP, nu in cuprins.
const ABB = {
  flow: { label: 'ABB Ghid No.4 — reglaj debit vs vana (economie)', href: abbView('throttling or bypass control', 172) },
  mech: { label: 'ABB Ghid No.7 — legi mecanice (cuplu, inertie, accelerare)', href: abbView('One of the basic equations of an induction motor', 283) },
  load: { label: 'ABB Ghid No.7 — tipuri de sarcina (cuplu patratic)', href: abbView('quadratic torque', 288) },
  thd: { label: 'ABB Ghid No.6 — distorsiune armonica (THD)', href: abbView('Total harmonic distortion', 249) },
  brake: { label: 'ABB Ghid No.8 — franare electrica', href: abbView('Flux braking is a method based on motor losses', 321) },
  motion: { label: 'ABB Ghid No.9 — motion control (following error)', href: abbView('following error', 388) },
  dtc: { label: 'ABB Ghid No.1 — Direct Torque Control', href: `${_PDFJS}${_NO1_FILE}#page=1&search=${encodeURIComponent('Direct torque control')}&phrase=true` },
}
// frag = textul evidentiat pe pagina (Scroll-To-Text-Fragment): browserul sare la el si il hasureaza.
const W = (slug, label, frag) => ({
  label: `${label} (Wikipedia EN)`,
  href: `https://en.wikipedia.org/wiki/${slug}${frag ? `#:~:text=${encodeURIComponent(frag)}` : ''}`,
})
// frag = propozitie verbatim din paragraful relevant (verificata ca exista in articolul live),
// ca highlight-ul sa cada pe explicatie, nu pe titlu/cuprins.
const WEB = {
  induction: W('Induction_motor', 'Induction motor', 'an induction motor always operates slightly slower than synchronous speed'),
  affinity: W('Affinity_laws', 'Affinity laws', 'the relationship between variables involved in pump or fan performance'),
  npsh: W('Net_positive_suction_head', 'NPSH', 'may refer to one of two quantities in the analysis of cavitation'),
  thd: W('Total_harmonic_distortion', 'Total harmonic distortion', 'defined as the ratio of the sum of the powers of all harmonic components'),
  pf: W('Power_factor', 'Power factor', 'the ratio of the real power absorbed by the load to the apparent power'),
  dcMotor: W('DC_motor', 'DC motor', 'the counter-Electro motive force produced by the field winding is weak'),
  syncMotor: W('Synchronous_motor', 'Synchronous motor', 'the rotation of the shaft is synchronized with the frequency of the supply current'),
  foc: W('Vector_control_(motor)', 'Vector control / FOC', 'field flux linkage component of current is aligned along the d axis'),
  vfd: W('Variable-frequency_drive', 'Variable-frequency drive', 'that controls speed and torque by varying the frequency of the input electricity'),
  centrifugal: W('Centrifugal_pump', 'Centrifugal pump', 'The fluid gains both velocity and pressure while passing through the impeller'),
  specificSpeed: W('Specific_speed', 'Specific speed', 'Specific speed is an index used to predict desired pump or turbine performance'),
  shortCircuit: W('Short_circuit', 'Short circuit', 'to travel along an unintended path with no or very low electrical impedance'),
  transformer: W('Transformer', 'Transformer', 'a voltage is induced in each winding proportional to its number of turns'),
  reluctance: W('Reluctance_motor', 'Reluctance motor (SynRM)', 'the rotor torque is in the direction that reduces reluctance'),
  inertia: W('Moment_of_inertia', 'Moment of inertia', 'the ratio between the torque applied and the resulting angular acceleration'),
  resonance: W('Resonance', 'Resonance', 'the outside vibration will cause the system to oscillate at a higher amplitude'),
  encoder: W('Rotary_encoder', 'Rotary encoder', 'two output signals, A and B, which issue a periodic digital waveform in quadrature'),
  pid: W('PID_controller', 'PID controller', 'Term P is proportional to the current value'),
  damping: W('Damping', 'Damping ratio', 'an oscillatory system that has the effect of reducing or preventing its oscillation'),
  inverter: W('Power_inverter', 'Power inverter / IGBT', 'a power electronic device or circuitry that changes direct current (DC) to alternating current (AC)'),
  cable: W('Voltage_drop', 'Voltage drop', 'the decrease of electric potential along the path of a current flowing in a circuit'),
  flywheel: W('Flywheel', 'Flywheel', 'the stored (rotational) energy is directly associated with the square of its rotational speed'),
  voltageSag: W('Voltage_sag', 'Voltage sag', 'is a short-duration reduction in the voltage of an electric power distribution system'),
  powerQuality: W('Power_quality', 'Power quality', 'the degree to which the voltage, frequency, and waveform of a power supply system conform'),
  ie: W('Premium_efficiency', 'IE efficiency classes', 'when used in reference to specific types of Electric Motors'),
  duty: W('Duty_cycle', 'Duty cycle (S1-S10)', 'the fraction of one period in which a signal or system is active'),
}
// Implicit pe familie — DOAR surse online relevante (fara ABB generic, ca sa nu cada toate pe acelasi loc).
const FAM_DOCS = {
  asincron: [WEB.induction],
  pompe: [WEB.centrifugal, WEB.affinity],
  cc: [WEB.dcMotor],
  servo: [WEB.foc],
  sincron: [WEB.syncMotor],
  comun: [],
}
// Per modul: ancora ABB pe TOPICUL modulului (nu un ghid generic) + sursa online relevanta.
const DOC_LINKS = {
  // asincron
  'putere-curent': [WEB.pf],
  'cuplu': [WEB.induction],
  'asincron-camp-slabit': [ABB.mech, WEB.vfd],
  'sarcina-afinitate': [ABB.load, WEB.affinity],
  'incarcare': [ABB.load],
  'motor-echivalent': [WEB.induction],
  'bilant-putere': [WEB.induction],
  'teste-parametri': [WEB.induction],
  'randament-sarcina': [WEB.induction],
  'dezechilibru': [WEB.powerQuality],
  'cosphi-sarcina': [WEB.pf],
  'derating-armonici-motor': [ABB.thd, WEB.thd],
  'clase-ie': [WEB.ie],
  'regimuri-s': [WEB.duty],
  'viata-termica-s10': [WEB.duty],
  'porniri-ora': [WEB.duty],
  'derating-vfd-motor': [WEB.vfd, WEB.induction],
  // pompe & ventilatoare
  'npsh': [WEB.npsh],
  'turatie-specifica': [WEB.specificSpeed],
  'economie-profil': [ABB.flow, WEB.affinity],
  // servo / PMSM
  'pmsm-ciclu': [ABB.motion, WEB.foc],
  'pmsm-feedback': [ABB.motion, WEB.encoder],
  'acordare-pi': [WEB.pid],
  'raspuns-ord2': [WEB.damping],
  'pmsm-camp-slabit': [WEB.foc],
  'profil-miscare': [ABB.motion],
  'ipmsm-mtpa': [WEB.foc],
  'suprasarcina-servo': [ABB.motion, WEB.duty],
  // sincron
  'synrm': [WEB.reluctance],
  // comun — mecanica / actionari
  'dinamica': [ABB.mech, WEB.inertia],
  'transmisii': [ABB.mech, WEB.inertia],
  'raport-inertie': [ABB.mech, WEB.inertia],
  'selectie-drive': [ABB.load],
  'surub-bile': [ABB.mech, WEB.inertia],
  'liniar-raza': [ABB.mech],
  'transportor': [ABB.mech],
  'winder': [ABB.mech],
  'frecare': [ABB.mech],
  'compresor-volant': [ABB.mech, WEB.flywheel],
  // comun — energie
  'energie-roi': [ABB.flow, WEB.affinity],
  'vfd': [WEB.vfd],
  // comun — instalatie electrica
  'cablu': [WEB.cable],
  'cablu-protectii': [WEB.cable],
  'scurtcircuit': [WEB.shortCircuit],
  'transformator': [WEB.transformer],
  'trafo-grupa-conexiuni': [WEB.transformer],
  'trafo-12pulse': [ABB.thd, WEB.thd],
  'trafo-scurtcircuit': [WEB.shortCircuit, WEB.transformer],
  'dip-pornire': [WEB.voltageSag],
  'turatie-critica': [WEB.resonance],
  'termic': [WEB.duty],
  'motor-termic': [WEB.duty],
  'conversii': [],
  // comun — armonici / calitate energie
  'armonici': [ABB.thd, WEB.thd],
  'ieee519': [ABB.thd, WEB.thd],
  'rezonanta-cond': [ABB.thd, WEB.resonance],
  'reactor-detunare': [ABB.thd, WEB.resonance],
  'factor-k': [ABB.thd, WEB.thd],
  'factor-putere-vfd': [ABB.thd, WEB.pf],
  'comparatie-frontend': [ABB.thd, WEB.thd],
  'compensare': [WEB.pf],
  // comun — convertizor / iesire
  'comutatie': [WEB.inverter],
  'unda-reflectata': [WEB.inverter],
  'filtru-iesire': [WEB.inverter],
  'curenti-rulment': [WEB.inverter],
  // comun — franare / energie cinetica
  'macara': [ABB.brake],
  'contragreutate': [ABB.brake],
  'ride-through': [ABB.brake, WEB.voltageSag],
  'kinetic-buffer': [ABB.brake, WEB.flywheel],
  'taper': [ABB.dtc],
  // adaugiri PIF (verificare 2026)
  'franare-rezistenta': [ABB.brake],
  'run-up': [ABB.mech, WEB.induction],
  'encoder-offset': [ABB.motion, WEB.foc],
  'notch-rezonanta': [ABB.motion, WEB.resonance],
  'pid-drive': [WEB.pid],
  'lovitura-berbec': [WEB.centrifugal],
}
// Manuale cu drept de autor — DOAR paginile citate (extras), servite protejat la /docs (login).
// protected:true => ascunse pe /calc public; vizibile doar in dashboard (logat). PDF.js deschide + hasureaza.
const _bookView = (file, search) => `${_PDFJS}${encodeURIComponent('/docs/' + file)}#search=${encodeURIComponent(search)}&phrase=true`
const _CHAP = 'chapman-electric-machinery-extras.pdf'
const _MOHAN = 'mohan-power-electronics-extras.pdf'
const _HUGHES = 'hughes-electric-motors-drives-extras.pdf'
const _NISE = 'nise-control-systems-extras.pdf'
const BOOK = {
  chapThevenin: { protected: true, label: 'Chapman — schema echivalenta / Thevenin (extras)', href: _bookView(_CHAP, 'Thevenin equivalent') },
  chapPowerFlow: { protected: true, label: 'Chapman — diagrama flux de putere (extras)', href: _bookView(_CHAP, 'power-flow diagram') },
  chapVcurves: { protected: true, label: 'Chapman — curbele in V (sincron) (extras)', href: _bookView(_CHAP, 'Synchronous motor V curves') },
  chapSyncP: { protected: true, label: 'Chapman — cuplu/putere masina sincrona (extras)', href: _bookView(_CHAP, 'induced torque in a synchronous') },
  chapDCmotor: { protected: true, label: 'Chapman — schema echivalenta masina c.c. (extras)', href: _bookView(_CHAP, 'equivalent circuit of a dc motor') },
  chapDCspeed: { protected: true, label: 'Chapman — reglaj turatie c.c. (extras)', href: _bookView(_CHAP, 'Speed Control of Shunt') },
  chapIndSpeed: { protected: true, label: 'Chapman — motor asincron: turatie / sincronism (extras)', href: _bookView(_CHAP, 'synchronous speed') },
  chapSyncPhasor: { protected: true, label: 'Chapman — masina sincrona: diagrama fazoriala (extras)', href: _bookView(_CHAP, 'phasor diagram') },
  mohanSwitch: { protected: true, label: 'Mohan — pierderi de comutatie (extras)', href: _bookView(_MOHAN, 'switching losses') },
  mohanRect: { protected: true, label: 'Mohan — redresor Ud=1.35·U (extras)', href: _bookView(_MOHAN, '1.35') },
  hughesStart: { protected: true, label: 'Hughes — pornire motor (extras)', href: _bookView(_HUGHES, 'torque per amp') },
  hughesThermal: { protected: true, label: 'Hughes — constanta de timp termica (extras)', href: _bookView(_HUGHES, 'Thermal time constant') },
  hughesMTPA: { protected: true, label: 'Hughes — cuplu maxim pe amper (extras)', href: _bookView(_HUGHES, 'maximum torque per ampere') },
  niseOrd2: { protected: true, label: 'Nise — raspuns de ordin 2 (extras)', href: _bookView(_NISE, 'percent overshoot is a function only of the damping ratio') },
}
const BOOK_DOCS = {
  'motor-echivalent': [BOOK.chapThevenin],
  'teste-parametri': [BOOK.chapThevenin],
  'cuplu': [BOOK.chapThevenin],
  'bilant-putere': [BOOK.chapPowerFlow],
  'randament-sarcina': [BOOK.chapPowerFlow],
  'sincron-putere': [BOOK.chapSyncP],
  'sincron-poli-aparenti': [BOOK.chapSyncP],
  'vcurves': [BOOK.chapVcurves],
  'cc-baza': [BOOK.chapDCmotor],
  'cc-serie': [BOOK.chapDCmotor],
  'cc-randament': [BOOK.chapDCmotor],
  'cc-reglaj': [BOOK.chapDCspeed],
  'cc-excitatii': [BOOK.chapDCmotor, BOOK.chapDCspeed],
  'cc-camp': [BOOK.chapDCspeed],
  'cc-comutatie': [BOOK.chapDCmotor],
  'cc-factor-forma': [BOOK.mohanRect],
  'cc-franare': [BOOK.chapDCmotor],
  'vfd': [BOOK.mohanRect],
  'cc-drive': [BOOK.mohanRect],
  'comutatie': [BOOK.mohanSwitch],
  'filtru-iesire': [BOOK.mohanSwitch],
  'pornire': [BOOK.hughesStart],
  'motor-termic': [BOOK.hughesThermal],
  'pmsm-model': [BOOK.hughesMTPA],
  'ipmsm-mtpa': [BOOK.hughesMTPA],
  'acordare-pi': [BOOK.niseOrd2],
  'raspuns-ord2': [BOOK.niseOrd2],
  // consistenta: module care citeaza o carte in SOURCES -> link clickabil catre extras (ancora verificata in extras)
  'motor-turatie': [BOOK.chapIndSpeed],
  'sincron-turatie': [BOOK.chapSyncPhasor],
  'cosphi-sarcina': [BOOK.chapThevenin],
  'pmsm-feedback': [BOOK.hughesMTPA],
  'derating-vfd-motor': [BOOK.hughesThermal],
  'porniri-ora': [BOOK.hughesStart],
  'suprasarcina-servo': [BOOK.hughesThermal],
}
// --- Standarde IEC/EN — extrase cu paginile citate (private_docs/standards), servite la /docs/standards.
// PDF.js deschide la pagina + evidentiaza fraza (search&phrase). 61800-3 are text fragmentat -> doar #page. ---
const _stdView = (file, search) => `${_PDFJS}${encodeURIComponent('/docs/standards/' + file)}#${search ? 'search=' + encodeURIComponent(search) + '&phrase=true' : 'page=1'}`
const STD = {
  iec60034_1: { protected: true, label: 'IEC 60034-1 — regimuri de serviciu & rating (extras)', href: _stdView('iec60034-1-extras.pdf', 'duty type') },
  iec60034_12: { protected: true, label: 'IEC 60034-12 — caracteristici de pornire (extras)', href: _stdView('iec60034-12-extras.pdf', 'locked rotor') },
  iec60034_25: { protected: true, label: 'IEC 60034-25 — masini AC pe convertizor (extras)', href: _stdView('iec60034-25-extras.pdf', 'voltage stress') },
  iec60034_18_41: { protected: true, label: 'IEC 60034-18-41 — descarcari partiale (PD) la PWM (extras)', href: _stdView('iec60034-18-41-extras.pdf', 'partial discharge') },
  iec60034_30_1: { protected: true, label: 'IEC 60034-30-1 — clase de randament IE (extras)', href: _stdView('iec60034-30-1-extras.pdf', 'efficiency classes') },
  iec61800_2: { protected: true, label: 'IEC 61800-2 — sisteme de actionare (PDS), rating (extras)', href: _stdView('iec61800-2-extras.pdf', 'overload') },
  iec61800_3: { protected: true, label: 'IEC 61800-3 — EMC, categorii C1-C4 (extras)', href: _stdView('iec61800-3-extras.pdf') },
  iec61800_5_1: { protected: true, label: 'IEC 61800-5-1 — siguranta electrica & termica (extras)', href: _stdView('iec61800-5-1-extras.pdf', 'protective') },
  iec61800_5_2: { protected: true, label: 'IEC 61800-5-2 — siguranta functionala STO/SS1 (extras)', href: _stdView('iec61800-5-2-extras.pdf', 'safe torque off') },
  iec60364_5_52: { protected: true, label: 'IEC 60364-5-52 — ampacitate cabluri (extras)', href: _stdView('iec60364-5-52-extras.pdf', 'current-carrying capacity') },
  iec60909: { protected: true, label: 'IEC 60909 — curenti de scurtcircuit (extras)', href: _stdView('iec60909-extras.pdf', 'short-circuit current') },
  iec60204_1: { protected: true, label: 'IEC 60204-1 — echipament electric masini, categorii stop (extras)', href: _stdView('iec60204-1-extras.pdf', 'stop category') },
  iec61000_3_12: { protected: true, label: 'IEC 61000-3-12 — limite armonici 16-75 A (extras)', href: _stdView('iec61000-3-12-extras.pdf', 'harmonic current') },
  iec61000_2: { protected: true, label: 'IEC 61000-2-4 — niveluri de compatibilitate (extras)', href: _stdView('iec61000-2-extras.pdf', 'compatibility level') },
  iec61000_4_30: { protected: true, label: 'IEC 61000-4-30 — masurarea calitatii energiei (extras)', href: _stdView('iec61000-4-30-extras.pdf', 'measurement method') },
  iec60076_1: { protected: true, label: 'IEC 60076-1 — transformatoare de putere (extras)', href: _stdView('iec60076-1-extras.pdf', 'rated power') },
  iso9906: { protected: true, label: 'EN ISO 9906 — incercari pompe, NPSH (extras)', href: _stdView('iso9906-extras.pdf', 'NPSH') },
  en50160: { protected: true, label: 'EN 50160 — caracteristicile tensiunii retelei (extras)', href: _stdView('en50160-extras.pdf', 'harmonic voltage') },
  // standarde adaugate (carduri noi + surse noi)
  iec60076_7: { protected: true, label: 'IEC 60076-7 — ghid de incarcare trafo in ulei (extras)', href: _stdView('iec60076-7-extras.pdf', 'hot-spot') },
  iec60034_14: { protected: true, label: 'IEC 60034-14 — vibratii mecanice (extras)', href: _stdView('iec60034-14-extras.pdf', 'vibration velocity') },
  iec62061: { protected: true, label: 'IEC 62061 — siguranta masinilor, SIL (extras)', href: _stdView('iec62061-extras.pdf', 'safety integrity level') },
  iso13849_1: { protected: true, label: 'ISO 13849-1 — parti de siguranta, PL (extras)', href: _stdView('iso13849-1-extras.pdf') },
  iec60034_5: { protected: true, label: 'IEC 60034-5 — grade de protectie IP (extras)', href: _stdView('iec60034-5-extras.pdf', 'degrees of protection') },
  iec60076_21: { protected: true, label: 'IEC 60076-21 — regulatoare de tensiune (ploturi) (extras)', href: _stdView('iec60076-21-extras.pdf', 'voltage regulator') },
  iec60034_30_2: { protected: true, label: 'IEC 60034-30-2 — clase IES (motoare pe VFD) (extras)', href: _stdView('iec60034-30-2-extras.pdf', 'IES') },
  iec60034_17: { protected: true, label: 'IEC 60034-17 — motoare colivie pe convertizor (extras)', href: _stdView('iec60034-17-extras.pdf', 'derating') },
  iec60034_18: { protected: true, label: 'IEC 60034-18 — evaluarea sistemelor de izolatie (extras)', href: _stdView('iec60034-18-extras.pdf', 'insulation system') },
  iec61800_6: { protected: true, label: 'IEC 61800-6 — tipuri de sarcina / dimensionare curent (extras)', href: _stdView('iec61800-6-extras.pdf', 'duty') },
  npi7: { protected: true, label: 'NP I7-2011 — normativ instalatii electrice JT (RO) (extras)', href: _stdView('npi7-2011-extras.pdf', 'sectiune') },
}
// Link direct catre figura regimului, la pagina ei in extrasul IEC 60034-1 deja gazduit
// (deschide figura REALA in vizualizatorul PDF.js — nu o incorporam ca imagine). Fraza e unica per figura.
// Link la pagina exacta a figurii in PDF.js (#page=N, 1-indexat) — determinist, verificat cu PyMuPDF.
const _figPg = (file, page, label) => ({ href: `${_PDFJS}${encodeURIComponent('/docs/standards/' + file)}#page=${page}`, label })
const _figABB = (page, label) => ({ href: `${_PDFJS}${_ABB_FILE}#page=${page}`, label })
const _figIEC = (page, n) => _figPg('iec60034-1-extras.pdf', page, `Figura ${n} — regim S${n} (IEC 60034-1)`)
export const FIG_LINKS = {
  Ps1: _figIEC(2, 1),
  PS2: _figIEC(3, 2), tP: _figIEC(3, 2),
  PS3: _figIEC(4, 3), DC: _figIEC(4, 3), CDFcalc: _figIEC(4, 3), tload: _figIEC(4, 3), tpauza: _figIEC(4, 3), kp: _figIEC(4, 3),
  PS6: _figIEC(7, 6), k0: _figIEC(7, 6), Pech: _figIEC(7, 6),
  TL: _figIEC(13, 10), AR: _figIEC(13, 10), dTref: _figIEC(13, 10), H: _figIEC(13, 10),
  p1: _figIEC(13, 10), p2: _figIEC(13, 10), p3: _figIEC(13, 10), p4: _figIEC(13, 10),
  f1: _figIEC(13, 10), f2: _figIEC(13, 10), f3: _figIEC(13, 10), f4: _figIEC(13, 10),
}
// Figura/tabelul-cheie din extrasul standardului, la nivel de CARD (orice marime din card o primeste
// daca nu are deja una proprie in FIG_LINKS). Deschide pagina REALA in PDF.js — nu incorporam imaginea.
// Paginile (1-indexate) sunt verificate ca aterizeaza pe figura/tabelul corect.
export const MODULE_FIG = {
  'scurtcircuit': _figPg('iec60909-extras.pdf', 2, 'Forme de curent de scurtcircuit (IEC 60909, Fig. 1-3)'),
  'trafo-scurtcircuit': _figPg('iec60909-extras.pdf', 2, 'Forme de curent de scurtcircuit (IEC 60909)'),
  'clase-ie': _figPg('iec60034-30-1-extras.pdf', 2, 'Tabele limite de randament IE1-IE4 (IEC 60034-30-1)'),
  'grade-ip': _figPg('iec60034-5-extras.pdf', 3, 'Tabel grade de protectie IP (IEC 60034-5)'),
  'comutatie': _figPg('iec60034-25-extras.pdf', 1, 'Pierderi suplimentare vs frecventa de puls (IEC 60034-25, Fig. 6)'),
  'derating-vfd-motor': _figPg('iec60034-25-extras.pdf', 1, 'Pierderi pe convertizor vs frecventa de puls (IEC 60034-25, Fig. 6)'),
  'derating-armonici-motor': _figPg('iec60034-17-extras.pdf', 1, 'Forme de unda & pierderi pe convertizor (IEC 60034-17)'),
  'franare-rezistenta': _figPg('iec61800-2-extras.pdf', 1, 'Cadrane de functionare (IEC 61800-2, Fig. 3)'),
  'cablu': _figPg('iec60364-5-52-extras.pdf', 1, 'Metode de pozare a cablurilor (IEC 60364-5-52, Tab. 52-3)'),
  'cablu-protectii': _figPg('iec60364-5-52-extras.pdf', 1, 'Metode de pozare a cablurilor (IEC 60364-5-52)'),
  'ploturi': _figPg('iec60076-21-extras.pdf', 2, 'Limite de temperatura & ploturi trafo (IEC 60076-21)'),
  'izolatie': _figPg('iec60034-18-extras.pdf', 4, 'Calificare sistem de izolatie (IEC 60034-18, Fig. 1-2)'),
  'unda-reflectata': _figPg('iec60034-18-41-extras.pdf', 4, 'Forme de unda admise la test PD (IEC 60034-18-41, Tab. 5)'),
  'sil-pl': _figPg('iec62061-extras.pdf', 3, 'Relatia IEC 62061 cu alte standarde (Fig. 1)'),
  'vibratii': _figPg('iec60034-14-extras.pdf', 4, 'Limite de vibratii vs turatie (IEC 60034-14, Fig. 1)'),
  'ieee519': _figPg('iec61000-3-12-extras.pdf', 5, 'Tabele limite de emisie armonica (IEC 61000-3-12, Tab. 3-5)'),
  // figuri ABB Technical Guide Book (pagini verificate cu PyMuPDF)
  'armonici': _figABB(231, 'Continut armonic al curentului (ABB Fig. 2.2)'),
  'comparatie-frontend': _figABB(252, 'Componente armonice 6 vs 12 pulsuri (ABB Fig. 7.8)'),
  'reactor-detunare': _figABB(255, 'Filtru pasiv detunat / reactor (ABB Fig. 8.1)'),
  'rezonanta-cond': _figABB(255, 'Amplificarea armonicilor sub frecventa de acord (ABB Fig. 8.1)'),
  'selectie-drive': _figABB(314, 'Harta aplicatii: turatie vs cuplu (ABB Fig. 1.1)'),
  'transmisii': _figABB(286, 'Reductor: randament & raport n1:n2 (ABB Fig. 5.2)'),
  'cuplu': _figABB(277, 'Curba cuplu/turatie motor asincron (ABB Fig. 4.1)'),
  'motor-turatie': _figABB(277, 'Curba cuplu/turatie/alunecare (ABB Fig. 4.1)'),
  'vfd': _figABB(274, 'Structura convertizorului: redresor / circuit DC / invertor (ABB Fig. 2.1)'),
  'asincron-camp-slabit': _figABB(279, 'Cuplu max, tensiune & flux vs frecventa — slabire de camp (ABB Fig. 4.3)'),
  'curenti-rulment': _figABB(204, 'Curenti de rulment & fluting (ABB, bearing currents Fig. 1)'),
  'retea-emc': _figABB(128, 'Filtru EMC in drive / laturi curata-murdara (ABB Fig. 3-3)'),
  'sarcina-afinitate': _figABB(288, 'Sarcina cu cuplu patratic — afinitate (ABB Fig. 6.2)'),
  'pmsm-model': _figABB(359, 'Curbe de cuplu servomotor (ABB Fig. 5.1)'),
  'pmsm-feedback': _figABB(364, 'Reglaj pozitie/turatie/curent (ABB Fig. 7.2)'),
  'acordare-pi': _figABB(357, 'Bucla cascadata turatie & curent (ABB Fig. 4.2)'),
  'encoder-offset': _figABB(363, 'Semnal encoder SinCos & interpolare (ABB Fig. 6.3/6.4)'),
  'winder': _figABB(368, 'Limitator dinamic follower (ABB Fig. 8.6)'),
  'moduri-control': _figABB(328, 'Diagrama de control DTC (ABB Fig. 3.7)'),
  // figuri/tabele din extrase de standard (pagini verificate)
  'motor-termic': _figPg('iec60034-1-extras.pdf', 2, 'Regim continuu S1 — incalzire (IEC 60034-1, Fig. 1)'),
  'pmsm-ciclu': _figPg('iec60034-1-extras.pdf', 4, 'Regim intermitent S3 (IEC 60034-1, Fig. 3)'),
  'porniri-ora': _figPg('iec60034-1-extras.pdf', 5, 'Regim S4 cu porniri (IEC 60034-1, Fig. 4)'),
  'run-up': _figPg('iec60034-1-extras.pdf', 5, 'Regim S4 — pornire (IEC 60034-1, Fig. 4)'),
  'npsh': _figPg('iso9906-extras.pdf', 3, 'Metode de determinare NPSH3 (ISO 9906, Tab. 10)'),
  'incarcare-trafo': _figPg('iec60076-21-extras.pdf', 2, 'Limite de temperatura trafo (IEC 60076-21)'),
  'pornire': _figPg('iec60034-12-extras.pdf', 1, 'Cuplu/curent de pornire DOL & stea-triunghi (IEC 60034-12)'),
}
const STD_DOCS = {
  'regimuri-s': [STD.iec60034_1], 'viata-termica-s10': [STD.iec60034_1], 'termic': [STD.iec60034_1], 'asincron-camp-slabit': [STD.iec60034_1],
  'dezechilibru': [STD.iec60034_1, STD.iec61000_4_30],
  'run-up': [STD.iec60034_12, STD.iec61800_5_2],
  'derating-armonici-motor': [STD.iec60034_25, STD.iec60034_17, STD.iec60034_1],
  'unda-reflectata': [STD.iec60034_25, STD.iec60034_18_41],
  'encoder-offset': [STD.iec60034_25], 'clase-ie': [STD.iec60034_30_1, STD.iec60034_30_2],
  'izolatie': [STD.iec60034_18], 'selectie-drive': [STD.iec61800_6],
  'franare-rezistenta': [STD.iec61800_2, STD.iec61800_5_1], 'notch-rezonanta': [STD.iec61800_2],
  'retea-emc': [STD.iec61800_3], 'sto-ss1': [STD.iec61800_5_2, STD.iec60204_1], 'sil-pl': [STD.iec62061, STD.iso13849_1],
  'cablu': [STD.iec60364_5_52, STD.npi7], 'cablu-protectii': [STD.iec60364_5_52, STD.npi7],
  'scurtcircuit': [STD.iec60909, STD.npi7], 'trafo-scurtcircuit': [STD.iec60909],
  'dip-pornire': [STD.iec60909, STD.en50160, STD.npi7],
  'ieee519': [STD.iec61000_3_12, STD.en50160], 'comparatie-frontend': [STD.iec61000_3_12, STD.en50160],
  'trafo-12pulse': [STD.iec61000_2],
  'transformator': [STD.iec60076_1, STD.iec60076_7], 'trafo-grupa-conexiuni': [STD.iec60076_1], 'factor-k': [STD.iec60076_1],
  'incarcare-trafo': [STD.iec60076_7], 'ploturi': [STD.iec60076_21],
  'vibratii': [STD.iec60034_14], 'grade-ip': [STD.iec60034_5],
  'npsh': [STD.iso9906], 'pompa-sistem': [STD.iso9906], 'putere-pompa': [STD.iso9906],
  'randament-pompa': [STD.iso9906], 'debit-minim': [STD.iso9906], 'turatie-minima': [STD.iso9906],
}
// --- Simbol TeX dintr-o cheie de camp/rezultat, pentru randare KaTeX a etichetelor (subscript/superscript) ---
const _GREEK = { omega: '\\omega', eta: '\\eta', rho: '\\rho', delta: '\\delta', tau: '\\tau', phi: '\\varphi', psi: '\\psi', mu: '\\mu', lambda: '\\lambda', sigma: '\\sigma', theta: '\\theta', zeta: '\\zeta', alpha: '\\alpha', beta: '\\beta', gamma: '\\gamma' }
const _SYM = {
  // litere/marimi cu notatie speciala
  w: '\\omega', wn: '\\omega_n', cosphi: '\\cos\\varphi', cosphin: '\\cos\\varphi_n', kPhi: 'k\\Phi', psim: '\\psi_m',
  nq: 'n_q', ratio: 'k', imp: 'N_{\\mathrm{imp}}', PPR: '\\mathrm{PPR}', RJ: 'R_J', dE: '\\Delta E', dpret: '\\Delta\\,\\mathrm{pret}',
  // acronime / factori (roman drept)
  THD: '\\mathrm{THD}', THDest: '\\mathrm{THD}_{\\mathrm{est}}', HVF: '\\mathrm{HVF}', PF: '\\mathrm{PF}', DPF: '\\mathrm{DPF}', DC: '\\mathrm{DC}', BVR: '\\mathrm{BVR}',
  PF1: '\\mathrm{PF}_1', PF2: '\\mathrm{PF}_2', IB: 'I_B', kDOL: 'k_{\\mathrm{DOL}}', QBEP: 'Q_{\\mathrm{BEP}}',
  NPSHrn: '\\mathrm{NPSH_r}', OLHD: '\\mathrm{OL_{HD}}', OLND: '\\mathrm{OL_{ND}}', Ps1: 'P_{S1}', Ps3: 'P_{S3}',
  // cuvinte (nu sunt simboluri reale) -> roman
  invest: '\\mathrm{invest}', pret: '\\mathrm{pret}', ore: '\\mathrm{ore}', drop: '\\mathrm{drop}', frac: '\\mathrm{frac}', taper: '\\mathrm{taper}', alt: '\\mathrm{alt}',
  // tensiuni de test / armonice -> U (notatie romaneasca)
  Vdc: 'U_{\\mathrm{dc}}', Vnl: 'U_{\\mathrm{nl}}', Vlr: 'U_{\\mathrm{lr}}', V5: 'U_5', V7: 'U_7', V11: 'U_{11}', V13: 'U_{13}',
  // unitati (modulul conversii)
  kW: '\\mathrm{kW}', hp: '\\mathrm{hp}', kgf: '\\mathrm{kgf}', kgfm: '\\mathrm{kgf{\\cdot}m}', rpm: '\\mathrm{rpm}', Nm: '\\mathrm{N{\\cdot}m}', N: 'N',
  IccPCC: 'I_{cc,PCC}', Sccbus: 'S_{cc,bus}',
}
export function symTeX(key) {
  if (!key) return ''
  if (_SYM[key]) return _SYM[key]
  // prefix grecesc: ex. etap -> \eta_p, omega -> \omega
  for (const g in _GREEK) {
    if (key === g) return _GREEK[g]
    if (key.startsWith(g) && key.length > g.length) {
      const rest = key.slice(g.length)
      return _GREEK[g] + (/^[0-9]+$/.test(rest) ? `_{${rest}}` : `_{\\mathrm{${rest}}}`)
    }
  }
  // acronim (>=2 majuscule) -> roman drept
  if ((key.match(/[A-Z]/g) || []).length >= 2) return `\\mathrm{${key}}`
  const base = key[0]
  const rest = key.slice(1)
  if (!rest) return base
  if (/^[0-9]+$/.test(rest)) return `${base}_{${rest}}`
  return `${base}_{\\mathrm{${rest}}}`
}

// Eticheta descriptiva fara simbolul lipit la coada (ex. "Cadere conductie Uce0" -> "Cadere conductie").
export function descLabel(label, key) {
  if (!label || !key) return label || ''
  const esc = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return label.replace(new RegExp(`\\s*${esc}\\s*$`, 'i'), '').trim() || label
}

// Linkuri de documentatie pentru un modul: ABB/online (publice) + extrase carti (protected:true).
export function docsForModule(mod) {
  const base = DOC_LINKS[mod.id] || FAM_DOCS[mod.family] || []
  return [...base, ...(BOOK_DOCS[mod.id] || []), ...(STD_DOCS[mod.id] || [])]
}

const SQRT3 = Math.sqrt(3)
const omega = (n) => (2 * Math.PI * n) / 60 // rpm -> rad/s
const rad = (deg) => (deg * Math.PI) / 180

// Culori grafice (CSS vars se adapteaza light/dark). Patru serii distincte:
// a=amber accent, b=verde (chart-2, validat CVD), c=rosu danger, op=violet info.
const COL = { a: 'var(--accent)', b: 'var(--chart-2)', c: 'var(--danger)', op: 'var(--info)' }
// Genereaza puncte {x,y} pentru o functie y=fn(x) pe intervalul [xMin, xMax].
function curve(xMin, xMax, fn, steps = 160) {
  const pts = []
  for (let i = 0; i <= steps; i++) {
    const x = xMin + ((xMax - xMin) * i) / steps
    const y = fn(x)
    if (Number.isFinite(y)) pts.push({ x, y })
  }
  return pts
}

export const MODULES = [
  // ============================================================== ASINCRON
  {
    id: 'motor-turatie',
    family: 'asincron',
    tier: 1,
    title: 'Motor & turatie',
    subtitle: 'Turatie sincrona, alunecare, viteza unghiulara',
    params: 'Turatie max: ABB 30.12 · Siemens p1082',
    fields: [
      { key: 'f', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 0 },
      { key: 'p', label: 'Numar de poli', unit: '', default: 4, step: 2, min: 2 },
      { key: 'n', label: 'Turatie masurata', unit: 'rpm', default: 1450, step: 10, min: 0 },
    ],
    results: [
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', tex: 'n_s = \\dfrac{120\\,f}{p}',
        calc: (v) => (v.p ? (120 * v.f) / v.p : null), dec: 0 },
      { key: 's', label: 'Alunecare', unit: '%', tex: 's = \\dfrac{n_s - n}{n_s}\\cdot 100',
        calc: (v, r) => (r.ns ? ((r.ns - v.n) / r.ns) * 100 : null), dec: 2 },
      { key: 'w', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega = \\dfrac{2\\pi n}{60}',
        calc: (v) => omega(v.n), dec: 2 },
      { key: 'fr', label: 'Frecventa rotorica', unit: 'Hz', tex: 'f_r = \\dfrac{s}{100}\\,f',
        calc: (v, r) => (r.s != null ? (r.s / 100) * v.f : null), dec: 2 },
    ],
  },
  {
    id: 'putere-curent',
    family: 'asincron',
    tier: 1,
    title: 'Putere & curent',
    subtitle: 'Curent absorbit, putere aparenta si reactiva',
    params: 'Date motor: ABB 99.6-99.12 · Siemens p0304-p0312',
    fields: [
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'cosphi', label: 'Factor de putere', unit: '', default: 0.85, step: 0.01, min: 0 },
      { key: 'eta', label: 'Randament', unit: '%', default: 90, step: 1, min: 0 },
    ],
    results: [
      { key: 'I', label: 'Curent absorbit', unit: 'A', tex: 'I = \\dfrac{P_n\\cdot 1000}{\\sqrt{3}\\,U\\cos\\varphi\\,\\eta}',
        calc: (v) => { const d = SQRT3 * v.U * v.cosphi * (v.eta / 100); return d ? (v.Pn * 1000) / d : null }, dec: 1 },
      { key: 'Pel', label: 'Putere activa absorbita', unit: 'kW', tex: 'P_{el} = \\dfrac{P_n}{\\eta}',
        calc: (v) => (v.eta ? v.Pn / (v.eta / 100) : null), dec: 2 },
      { key: 'S', label: 'Putere aparenta', unit: 'kVA', tex: 'S = \\dfrac{\\sqrt{3}\\,U I}{1000}',
        calc: (v, r) => (r.I != null ? (SQRT3 * v.U * r.I) / 1000 : null), dec: 2 },
      { key: 'Q', label: 'Putere reactiva', unit: 'kVAr', tex: 'Q = \\sqrt{S^2 - P_{el}^2}',
        calc: (v, r) => { if (r.S == null || r.Pel == null) return null; const q = r.S * r.S - r.Pel * r.Pel; return q > 0 ? Math.sqrt(q) : 0 }, dec: 2 },
    ],
  },
  {
    id: 'cuplu',
    family: 'asincron',
    tier: 1,
    title: 'Cuplu',
    subtitle: 'Cuplu nominal, de pornire si maxim',
    params: 'Limita cuplu: ABB 30.19/30.20 · Siemens p1520',
    charts: [(v) => {
      if (!v.n || !v.P) return null
      const pp = Math.max(1, Math.round(3000 / v.n)); const ns = 3000 / pp
      const Mn = (9550 * v.P) / v.n, Mmax = v.km * Mn, Mstart = v.kp * Mn
      const X = Mstart > 0 ? (2 * Mmax) / Mstart : 0
      let sk = X > 2 ? (X - Math.sqrt(X * X - 4)) / 2 : 0.2
      if (!(sk > 0 && sk < 1)) sk = 0.2
      const kloss = (s) => (2 * Mmax) / (s / sk + sk / s)
      const motor = curve(1, ns, (n) => kloss((ns - n) / ns))
      const load = curve(0, ns, (n) => Mn * (n / v.n) ** 2)
      let op = null
      for (let n = ns * 0.4; n <= ns; n += ns / 240) {
        const Ml = Mn * (n / v.n) ** 2
        if (kloss((ns - n) / ns) <= Ml) { op = { x: Math.round(n), y: Math.round(Ml), label: 'functionare', color: COL.op }; break }
      }
      return {
        xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
        series: [{ label: 'M motor', color: COL.a, points: motor }, { label: 'M rezistent (pompa)', color: COL.b, dash: true, points: load }],
        markers: op ? [op] : [],
      }
    }],
    fields: [
      { key: 'P', label: 'Putere', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'n', label: 'Turatie nominala', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'kp', label: 'Factor cuplu pornire', unit: '×Mₙ', default: 2.0, step: 0.1, min: 0 },
      { key: 'km', label: 'Factor cuplu maxim', unit: '×Mₙ', default: 2.5, step: 0.1, min: 0 },
    ],
    results: [
      { key: 'Mn', label: 'Cuplu nominal', unit: 'Nm', tex: 'M_n = \\dfrac{9550\\,P}{n}',
        calc: (v) => (v.n ? (9550 * v.P) / v.n : null), dec: 1 },
      { key: 'Mp', label: 'Cuplu de pornire', unit: 'Nm', tex: 'M_p = k_p\\,M_n',
        calc: (v, r) => (r.Mn != null ? v.kp * r.Mn : null), dec: 1 },
      { key: 'Mmax', label: 'Cuplu maxim (breakdown)', unit: 'Nm', tex: 'M_{max} = k_m\\,M_n',
        calc: (v, r) => (r.Mn != null ? v.km * r.Mn : null), dec: 1 },
      { key: 'w', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega = \\dfrac{2\\pi n}{60}',
        calc: (v) => omega(v.n), dec: 2 },
    ],
  },
  {
    id: 'asincron-camp-slabit',
    family: 'asincron',
    tier: 2,
    title: 'Slabire de camp',
    subtitle: 'Cuplu si putere vs turatie peste turatia de baza',
    note: 'Peste $n_{baza}$ (la $f_n$) tensiunea e plafonata, deci fluxul scade $\\propto 1/n$. Zona I (sub $n_{baza}$): cuplu constant $M_n$. Zona II (pana la $n_2 = k_m\\,n_{baza}$): putere constanta, $M \\propto 1/n$. Zona III (peste $n_2$): limitat de cuplul de rasturnare, $M \\propto 1/n^2$ si $P \\propto 1/n$.',
    params: 'Limita turatie/flux: ABB 30.12 (f_max) · Siemens p1082 (n_max). La PIF verifica M_sarcina < M disponibil pe tot domeniul de turatie.',
    charts: [
      (v) => {
        if (!v.Pn || !v.nbaza) return null
        const Mn = (9550 * v.Pn) / v.nbaza
        const n2 = v.km * v.nbaza
        const nx = Math.max(v.nmax * 1.05, n2 * 1.3, v.nbaza * 1.1) // arata toate cele 3 zone
        const Mavail = (n) => (n <= v.nbaza ? Mn : (n <= n2 ? (Mn * v.nbaza) / n : v.km * Mn * (v.nbaza / n) ** 2))
        const Mbreak = (n) => (n <= v.nbaza ? v.km * Mn : v.km * Mn * (v.nbaza / n) ** 2)
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
          series: [
            { label: 'M rasturnare ~1/n²', color: COL.c, dash: true, points: curve(0, nx, Mbreak) },
            { label: 'M disponibil', color: COL.a, points: curve(0, nx, Mavail) },
          ],
          markers: [
            { x: v.nbaza, y: Mn, label: 'n baza', color: COL.op },
            { x: Math.round(n2), y: (Mn * v.nbaza) / n2, label: 'n2', color: COL.b },
            { x: v.nmax, y: Mavail(v.nmax), label: 'n max', color: COL.op },
          ],
        }
      },
      (v) => {
        if (!v.Pn || !v.nbaza) return null
        const n2 = v.km * v.nbaza
        const nx = Math.max(v.nmax * 1.05, n2 * 1.3, v.nbaza * 1.1)
        const P = (n) => (n <= v.nbaza ? v.Pn * (n / v.nbaza) : (n <= n2 ? v.Pn : (v.Pn * n2) / n))
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Putere P [kW]',
          series: [{ label: 'P disponibil', color: COL.a, points: curve(0, nx, P) }],
          markers: [
            { x: v.nbaza, y: v.Pn, label: 'n baza', color: COL.op },
            { x: Math.round(n2), y: v.Pn, label: 'n2 (sfarsit P const)', color: COL.b },
            { x: v.nmax, y: P(v.nmax), label: 'n max', color: COL.op },
          ],
        }
      },
    ],
    fields: [
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'nbaza', label: 'Turatie de baza', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'km', label: 'Factor cuplu maxim', unit: '×Mₙ', default: 2.5, step: 0.1, min: 1 },
      { key: 'nmax', label: 'Turatie maxima dorita', unit: 'rpm', default: 3000, step: 10, min: 1 },
    ],
    results: [
      { key: 'Mn', label: 'Cuplu nominal', unit: 'Nm', tex: 'M_n = \\dfrac{9550\\,P_n}{n_{baza}}',
        calc: (v) => (v.nbaza ? (9550 * v.Pn) / v.nbaza : null), dec: 1 },
      { key: 'ncp', label: 'Turatie sfarsit putere constanta', unit: 'rpm', tex: 'n_2 = k_m\\,n_{baza}',
        calc: (v) => v.km * v.nbaza, dec: 0 },
      { key: 'rcamp', label: 'Raport flux la n_max (Φ/Φₙ)', unit: '%', tex: '\\dfrac{\\Phi}{\\Phi_n} = \\dfrac{n_{baza}}{n_{max}}',
        calc: (v) => (v.nmax > v.nbaza ? (v.nbaza / v.nmax) * 100 : 100), dec: 1 },
      { key: 'Mdisp', label: 'Cuplu disponibil la n_max', unit: 'Nm', tex: 'M_{disp} = M_n\\dfrac{n_{baza}}{n}\\ (\\text{zona II})',
        calc: (v, r) => { const Mn = r.Mn; if (Mn == null) return null; const n = v.nmax, nb = v.nbaza, n2 = v.km * v.nbaza; if (n <= nb) return Mn; if (n <= n2) return (Mn * nb) / n; return v.km * Mn * (nb / n) ** 2 }, dec: 1 },
      { key: 'Pdisp', label: 'Putere disponibila la n_max', unit: 'kW', tex: 'P_{disp} = \\dfrac{M_{disp}\\,n_{max}}{9550}',
        calc: (v, r) => (r.Mdisp != null ? (r.Mdisp * v.nmax) / 9550 : null), dec: 2 },
    ],
  },
  {
    id: 'sarcina-afinitate',
    family: 'asincron',
    tier: 1,
    title: 'Legile afinitatii (pompe/ventilatoare)',
    subtitle: 'Debit, inaltime si putere la turatie variabila',
    note: 'Valabil pentru sarcina patratica (pompe centrifuge, ventilatoare).',
    charts: [
      (v) => {
        if (!v.n1) return null
        const xmax = Math.max(v.n1, v.n2)
        const pts = curve(0, xmax, (n) => v.P1 * (n / v.n1) ** 3)
        const op = { x: v.n2, y: v.P1 * (v.n2 / v.n1) ** 3, label: 'la n2', color: COL.op }
        return { xLabel: 'Turatie n [rpm]', yLabel: 'Putere P [kW]', series: [{ label: 'P(n) ~ n³', color: COL.a, points: pts }], markers: [op] }
      },
      (v) => {
        if (!v.Q1) return null
        const a = v.H1 / v.Q1 ** 2
        const pts = curve(0, v.Q1 * 1.15, (Q) => a * Q ** 2)
        return {
          xLabel: 'Debit Q [m³/h]', yLabel: 'Inaltime H [m]',
          series: [{ label: 'Locus afinitate H~Q²', color: COL.b, points: pts }],
          markers: [{ x: v.Q1, y: v.H1, label: 'n1', color: COL.a }, { x: v.Q1 * (v.n2 / v.n1), y: v.H1 * (v.n2 / v.n1) ** 2, label: 'n2', color: COL.op }],
        }
      },
    ],
    fields: [
      { key: 'n1', label: 'Turatie initiala', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'n2', label: 'Turatie noua', unit: 'rpm', default: 1160, step: 10, min: 0 },
      { key: 'Q1', label: 'Debit la n1', unit: 'm³/h', default: 100, step: 5, min: 0 },
      { key: 'H1', label: 'Inaltime la n1', unit: 'm', default: 32, step: 1, min: 0 },
      { key: 'P1', label: 'Putere la n1', unit: 'kW', default: 15, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'Q2', label: 'Debit la n2', unit: 'm³/h', tex: 'Q_2 = Q_1\\dfrac{n_2}{n_1}',
        calc: (v) => (v.n1 ? v.Q1 * (v.n2 / v.n1) : null), dec: 1 },
      { key: 'H2', label: 'Inaltime la n2', unit: 'm', tex: 'H_2 = H_1\\left(\\dfrac{n_2}{n_1}\\right)^2',
        calc: (v) => (v.n1 ? v.H1 * (v.n2 / v.n1) ** 2 : null), dec: 1 },
      { key: 'P2', label: 'Putere la n2', unit: 'kW', tex: 'P_2 = P_1\\left(\\dfrac{n_2}{n_1}\\right)^3',
        calc: (v) => (v.n1 ? v.P1 * (v.n2 / v.n1) ** 3 : null), dec: 2 },
      { key: 'econ', label: 'Economie de putere', unit: '%', tex: '\\eta_{ec} = \\left(1-\\left(\\dfrac{n_2}{n_1}\\right)^3\\right)100',
        calc: (v) => (v.n1 ? (1 - (v.n2 / v.n1) ** 3) * 100 : null), dec: 1 },
    ],
  },
  {
    id: 'pornire',
    family: 'asincron',
    tier: 2,
    title: 'Metode de pornire',
    subtitle: 'Curent de pornire: DOL, stea-triunghi, softstart, VFD',
    params: 'Limita curent VFD: ABB 30.17 · Siemens p0640',
    charts: [(v) => {
      const shape = (x) => v.In * (1 + (v.kDOL - 1) * (1 - (x / 100) ** 3))
      return {
        xLabel: 'Turatie [% sincron]', yLabel: 'Curent [A]',
        series: [
          { label: 'DOL', color: COL.c, points: curve(0, 100, shape) },
          { label: 'Softstart', color: COL.b, points: curve(0, 100, (x) => shape(x) * (v.Usoft / 100)) },
          { label: 'VFD', color: COL.a, points: curve(0, 100, () => v.climit * v.In) },
        ],
      }
    }],
    fields: [
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 0 },
      { key: 'kDOL', label: 'Factor pornire DOL', unit: '×Iₙ', default: 6, step: 0.5, min: 0 },
      { key: 'Usoft', label: 'Tensiune softstart', unit: '%', default: 70, step: 5, min: 0 },
      { key: 'climit', label: 'Factor curent VFD', unit: '×Iₙ', default: 1.3, step: 0.1, min: 0 },
    ],
    results: [
      { key: 'IpDOL', label: 'Curent pornire DOL', unit: 'A', tex: 'I_{p,DOL} = k\\,I_n',
        calc: (v) => v.kDOL * v.In, dec: 1 },
      { key: 'IpY', label: 'Curent pornire stea-triunghi', unit: 'A', tex: 'I_{p,Y} = I_{p,DOL}/3',
        calc: (v, r) => r.IpDOL / 3, dec: 1 },
      { key: 'IpSoft', label: 'Curent pornire softstart', unit: 'A', tex: 'I_{p,soft} = I_{p,DOL}\\dfrac{U}{U_n}',
        calc: (v, r) => r.IpDOL * (v.Usoft / 100), dec: 1 },
      { key: 'MSoft', label: 'Cuplu pornire softstart', unit: '%', tex: 'M_{p,soft} = \\left(\\dfrac{U}{U_n}\\right)^2 100',
        calc: (v) => (v.Usoft / 100) ** 2 * 100, dec: 0 },
      { key: 'IpVFD', label: 'Curent pornire VFD', unit: 'A', tex: 'I_{p,VFD} = c\\,I_n',
        calc: (v) => v.climit * v.In, dec: 1 },
    ],
  },
  {
    id: 'incarcare',
    family: 'asincron',
    tier: 2,
    title: 'Incarcare din masuratori',
    subtitle: 'Estimarea incarcarii motorului din curent/putere',
    note: 'Foloseste incarcarea din PUTERE. Cea din curent e estimare grosiera (interpolare liniara) — supraestimeaza la sarcini medii, unde cos φ scade.',
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'Im', label: 'Curent masurat', unit: 'A', default: 22, step: 0.5, min: 0 },
      { key: 'cosphi', label: 'cos φ masurat', unit: '', default: 0.82, step: 0.01, min: 0 },
      { key: 'eta', label: 'Randament', unit: '%', default: 90, step: 1, min: 0 },
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 1 },
      { key: 'I0', label: 'Curent mers in gol', unit: 'A', default: 10, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'Pax', label: 'Putere la arbore (estimat)', unit: 'kW', tex: 'P_{ax} = \\dfrac{\\sqrt{3}\\,U I\\cos\\varphi\\,\\eta}{1000}',
        calc: (v) => (SQRT3 * v.U * v.Im * v.cosphi * (v.eta / 100)) / 1000, dec: 2 },
      { key: 'incP', label: 'Incarcare din putere', unit: '%', tex: '\\dfrac{P_{ax}}{P_n}\\cdot 100',
        calc: (v, r) => (v.Pn ? (r.Pax / v.Pn) * 100 : null), dec: 0 },
      { key: 'incI', label: 'Incarcare din curent', unit: '%', tex: '\\dfrac{I - I_0}{I_n - I_0}\\cdot 100',
        calc: (v) => { const d = v.In - v.I0; return d > 0 ? ((v.Im - v.I0) / d) * 100 : null }, dec: 0 },
    ],
  },

  // ================================================================ COMUNE
  {
    id: 'dinamica',
    family: 'comun',
    tier: 1,
    title: 'Dinamica (rampe)',
    subtitle: 'Timp de accelerare si energie cinetica',
    params: 'Rampe: ABB 23.12/23.13 · Siemens p1120/p1121',
    fields: [
      { key: 'J', label: 'Inertie totala', unit: 'kg·m²', default: 0.5, step: 0.1, min: 0 },
      { key: 'n1', label: 'Turatie initiala', unit: 'rpm', default: 0, step: 10, min: 0 },
      { key: 'n2', label: 'Turatie finala', unit: 'rpm', default: 1450, step: 10, min: 0 },
      { key: 'Macc', label: 'Cuplu disponibil', unit: 'Nm', default: 100, step: 5, min: 0 },
      { key: 'Mload', label: 'Cuplu rezistent', unit: 'Nm', default: 40, step: 5, min: 0 },
    ],
    results: [
      { key: 'dw', label: 'Variatie viteza unghiulara', unit: 'rad/s', tex: '\\Delta\\omega = \\dfrac{2\\pi(n_2-n_1)}{60}',
        calc: (v) => omega(v.n2 - v.n1), dec: 2 },
      { key: 'tacc', label: 'Timp de accelerare', unit: 's', tex: 't_{acc} = \\dfrac{J\\,\\Delta\\omega}{M_{acc}-M_{load}}',
        calc: (v, r) => { const dm = v.Macc - v.Mload; return dm > 0 && r.dw != null ? (v.J * r.dw) / dm : null }, dec: 2 },
      { key: 'Ecin', label: 'Energie cinetica (la n2)', unit: 'J', tex: 'E_{cin} = \\tfrac{1}{2} J\\,\\omega_2^{2}',
        calc: (v) => 0.5 * v.J * omega(v.n2) ** 2, dec: 0 },
    ],
  },
  {
    id: 'energie-roi',
    family: 'comun',
    tier: 1,
    title: 'Energie & economii VFD',
    subtitle: 'Economie fata de reglaj prin vana/clapeta + payback',
    note: 'Economia presupune sarcina patratica (pompa/ventilator) reglata prin turatie.',
    fields: [
      { key: 'Pvana', label: 'Putere cu vana (100%)', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'nproc', label: 'Turatie proces', unit: '%', default: 80, step: 1, min: 0 },
      { key: 'ore', label: 'Ore functionare', unit: 'h/an', default: 4000, step: 100, min: 0 },
      { key: 'pret', label: 'Pret energie', unit: 'lei/kWh', default: 0.8, step: 0.05, min: 0 },
      { key: 'invest', label: 'Investitie VFD', unit: 'lei', default: 5000, step: 100, min: 0 },
    ],
    results: [
      { key: 'Pvfd', label: 'Putere cu VFD', unit: 'kW', tex: 'P_{vfd} = P_{vana}\\left(\\dfrac{n\\%}{100}\\right)^3',
        calc: (v) => v.Pvana * (v.nproc / 100) ** 3, dec: 2 },
      { key: 'dP', label: 'Economie de putere', unit: 'kW', tex: '\\Delta P = P_{vana}-P_{vfd}',
        calc: (v, r) => (r.Pvfd != null ? v.Pvana - r.Pvfd : null), dec: 2 },
      { key: 'Wsav', label: 'Economie anuala', unit: 'kWh/an', tex: 'W_{sav} = \\Delta P\\cdot ore',
        calc: (v, r) => (r.dP != null ? r.dP * v.ore : null), dec: 0 },
      { key: 'Csav', label: 'Economie in bani', unit: 'lei/an', tex: 'C_{sav} = W_{sav}\\cdot pret',
        calc: (v, r) => (r.Wsav != null ? r.Wsav * v.pret : null), dec: 0 },
      { key: 'payback', label: 'Recuperare investitie', unit: 'ani', tex: 'T = \\dfrac{Investitie}{C_{sav}}',
        calc: (v, r) => (r.Csav > 0 ? v.invest / r.Csav : null), dec: 1 },
    ],
  },
  {
    id: 'vfd',
    family: 'comun',
    tier: 2,
    title: 'Convertizor de frecventa (VFD)',
    subtitle: 'Tensiune DC bus, V/f, derating, pierderi',
    params: 'V/f: Siemens p1300+ · Udc monitorizat',
    charts: [(v) => {
      if (!v.fn) return null
      const boost = 0.08 * v.Ulinie
      const Uf = (f) => (f <= v.fn ? boost + (v.Ulinie - boost) * (f / v.fn) : v.Ulinie)
      return {
        xLabel: 'Frecventa f [Hz]', yLabel: 'Tensiune U [V]',
        series: [{ label: 'Caracteristica V/f', color: COL.a, points: curve(0, v.fn * 2, Uf) }],
        markers: [{ x: v.f, y: Uf(v.f), label: 'punct curent', color: COL.op }],
      }
    }],
    fields: [
      { key: 'Ulinie', label: 'Tensiune retea/motor', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'fn', label: 'Frecventa nominala', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'f', label: 'Frecventa de lucru', unit: 'Hz', default: 40, step: 1, min: 0 },
      { key: 'Pies', label: 'Putere de iesire', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'Tamb', label: 'Temperatura ambianta', unit: '°C', default: 45, step: 1, min: 0 },
    ],
    results: [
      { key: 'Udc', label: 'Tensiune DC bus', unit: 'V', tex: 'U_{dc} = 1.35\\,U_{linie}',
        calc: (v) => 1.35 * v.Ulinie, dec: 0 },
      { key: 'Udcpk', label: 'DC bus varf (gol)', unit: 'V', tex: 'U_{dc,pk} = \\sqrt{2}\\,U_{linie}',
        calc: (v) => Math.SQRT2 * v.Ulinie, dec: 0 },
      { key: 'Uies', label: 'Tensiune iesire (V/f)', unit: 'V', tex: 'U_{ies} = \\dfrac{U_n}{f_n}\\,f',
        calc: (v) => (v.fn ? (v.Ulinie / v.fn) * v.f : null), dec: 0 },
      { key: 'derT', label: 'Derating temperatura', unit: '%', tex: '1-\\dfrac{T_{amb}-40}{100}',
        calc: (v) => (v.Tamb > 40 ? (1 - (v.Tamb - 40) / 100) * 100 : 100), dec: 0 },
      { key: 'Ppierd', label: 'Pierderi convertizor', unit: 'kW', tex: 'P_{pierderi}\\approx 0.03\\,P_{ies}',
        calc: (v) => 0.03 * v.Pies, dec: 2 },
    ],
  },
  {
    id: 'cablu',
    family: 'comun',
    tier: 2,
    title: 'Cablu & cadere de tensiune',
    subtitle: 'Cadere de tensiune si sectiune minima',
    note: 'rho cupru ≈ 0.0225, aluminiu ≈ 0.036 Ω·mm²/m.',
    params: 'Lungime max cablu motor: vezi manual HW (du/dt)',
    fields: [
      { key: 'I', label: 'Curent', unit: 'A', default: 28, step: 1, min: 0 },
      { key: 'L', label: 'Lungime cablu', unit: 'm', default: 50, step: 5, min: 0 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'cosphi', label: 'cos φ', unit: '', default: 0.85, step: 0.01, min: 0 },
      { key: 'S', label: 'Sectiune cablu', unit: 'mm²', default: 6, step: 1, min: 0.1 },
      { key: 'rho', label: 'Rezistivitate', unit: 'Ω·mm²/m', default: 0.0225, step: 0.001, min: 0 },
    ],
    results: [
      { key: 'dU', label: 'Cadere de tensiune', unit: 'V', tex: '\\Delta U = \\dfrac{\\sqrt{3}\\,\\rho L I\\cos\\varphi}{S}',
        calc: (v) => (v.S ? (SQRT3 * v.rho * v.L * v.I * v.cosphi) / v.S : null), dec: 2 },
      { key: 'dUproc', label: 'Cadere de tensiune', unit: '%', tex: '\\Delta U\\% = \\dfrac{\\Delta U}{U}\\cdot 100',
        calc: (v, r) => (r.dU != null && v.U ? (r.dU / v.U) * 100 : null), dec: 2 },
      { key: 'Smin', label: 'Sectiune minima (3%)', unit: 'mm²', tex: 'S_{min} = \\dfrac{\\sqrt{3}\\,\\rho L I\\cos\\varphi}{0.03\\,U}',
        calc: (v) => (v.U ? (SQRT3 * v.rho * v.L * v.I * v.cosphi) / (0.03 * v.U) : null), dec: 2 },
    ],
  },
  {
    id: 'termic',
    family: 'comun',
    tier: 2,
    title: 'Termic & regimuri',
    subtitle: 'Curent echivalent, regim S3, derating',
    note: 'Derating altitudine doar pentru H > 1000 m. Verifica curba producatorului.',
    fields: [
      { key: 'I1', label: 'Curent segment 1', unit: 'A', default: 30, step: 1, min: 0 },
      { key: 't1', label: 'Timp segment 1', unit: 's', default: 20, step: 1, min: 0 },
      { key: 'I2', label: 'Curent segment 2', unit: 'A', default: 10, step: 1, min: 0 },
      { key: 't2', label: 'Timp segment 2', unit: 's', default: 40, step: 1, min: 0 },
      { key: 'DC', label: 'Durata de conectare (S3)', unit: '%', default: 40, step: 5, min: 1 },
      { key: 'Ps1', label: 'Putere in S1', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'H', label: 'Altitudine', unit: 'm', default: 2000, step: 100, min: 0 },
      { key: 'Tamb', label: 'Temperatura ambianta', unit: '°C', default: 45, step: 1, min: 0 },
    ],
    results: [
      { key: 'Iech', label: 'Curent termic echivalent', unit: 'A', tex: 'I_{ech} = \\sqrt{\\dfrac{I_1^2 t_1 + I_2^2 t_2}{t_1 + t_2}}',
        calc: (v) => { const t = v.t1 + v.t2; return t > 0 ? Math.sqrt((v.I1 ** 2 * v.t1 + v.I2 ** 2 * v.t2) / t) : null }, dec: 1 },
      { key: 'Ps3', label: 'Putere admisibila S3', unit: 'kW', tex: 'P_{S3} = \\dfrac{P_{S1}}{\\sqrt{DC/100}}',
        calc: (v) => (v.DC > 0 ? v.Ps1 / Math.sqrt(v.DC / 100) : null), dec: 2 },
      { key: 'falt', label: 'Factor derating altitudine', unit: '%', tex: 'f_{alt} = 1-\\dfrac{H-1000}{10000}',
        calc: (v) => (v.H > 1000 ? (1 - (v.H - 1000) / 10000) * 100 : 100), dec: 1 },
      { key: 'ftemp', label: 'Factor derating temperatura', unit: '%', tex: 'f_{temp} = 1-\\dfrac{T_{amb}-40}{100}',
        calc: (v) => (v.Tamb > 40 ? (1 - (v.Tamb - 40) / 100) * 100 : 100), dec: 1 },
    ],
  },
  {
    id: 'armonici',
    family: 'comun',
    tier: 2,
    title: 'Armonici & reactoare',
    subtitle: 'Inductanta reactor, cadere, regula THD',
    note: 'Soc DC/reactor AC ~ impedanta u_k (tipic 3-5%). Spectru 6-puls fara reactor: a5~63%; cu reactor: a5~30% (ABB TGB No.6, fig.7.5). Limita tensiune retea THD_U ≤ 8% (EN 50160).',
    params: 'Reactor de linie AC / reactor DC bus',
    fields: [
      { key: 'Un', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 1 },
      { key: 'fn', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'uk', label: 'Impedanta reactor', unit: '%', default: 4, step: 0.5, min: 0 },
      { key: 'P', label: 'Putere motor', unit: 'kW', default: 15, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'Lr', label: 'Inductanta reactor', unit: 'mH', tex: 'L = \\dfrac{u_k\\,U_n}{100\\,\\sqrt{3}\\,2\\pi f I_n}',
        calc: (v) => { const d = SQRT3 * 2 * Math.PI * v.fn * v.In; return d ? ((v.uk / 100) * v.Un / d) * 1000 : null }, dec: 2 },
      { key: 'dUr', label: 'Cadere pe reactor', unit: 'V', tex: '\\Delta U = \\sqrt{3}\\,2\\pi f L I_n',
        calc: (v) => { const L = (v.uk / 100) * v.Un / (SQRT3 * 2 * Math.PI * v.fn * v.In); return SQRT3 * 2 * Math.PI * v.fn * L * v.In }, dec: 1 },
      { key: 'Ldc', label: 'Inductanta soc DC (echivalent)', unit: 'mH', tex: 'L_{dc} = \\dfrac{(u_k/100)\\,U_{dc}^2}{2\\pi f\\,P},\\; U_{dc}=1.35\\,U_n,\\; P\\,[\\mathrm{kW}]',
        calc: (v) => { const Udc = 1.35 * v.Un; return v.P ? ((v.uk / 100) * Udc * Udc) / (2 * Math.PI * v.fn * v.P) : null }, dec: 2 },
    ],
  },
  {
    id: 'compensare',
    family: 'transformator',
    tier: 2,
    title: 'Compensare cos φ',
    subtitle: 'Putere reactiva, capacitate, curent baterie',
    note: 'La motor pe VFD NU compensa in amonte; niciodata condensatoare pe iesirea VFD.',
    fields: [
      { key: 'P', label: 'Putere activa', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'PF1', label: 'cos φ initial', unit: '', default: 0.75, step: 0.01, min: 0.01 },
      { key: 'PF2', label: 'cos φ tinta', unit: '', default: 0.95, step: 0.01, min: 0.01 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'f', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 1 },
    ],
    results: [
      { key: 'k', label: 'Factor compensare', unit: 'kvar/kW', tex: 'k = \\tan\\varphi_1 - \\tan\\varphi_2',
        calc: (v) => Math.tan(Math.acos(v.PF1)) - Math.tan(Math.acos(v.PF2)), dec: 3 },
      { key: 'Qc', label: 'Putere reactiva necesara', unit: 'kVAr', tex: 'Q_c = P(\\tan\\varphi_1 - \\tan\\varphi_2)',
        calc: (v, r) => v.P * r.k, dec: 2 },
      { key: 'Cd', label: 'Capacitate (triunghi)', unit: 'µF', tex: 'C_\\triangle = \\dfrac{Q_c}{3\\cdot 2\\pi f U^2}',
        calc: (v, r) => { const d = 3 * 2 * Math.PI * v.f * v.U ** 2; return d ? (r.Qc * 1000 / d) * 1e6 : null }, dec: 1 },
      { key: 'Ic', label: 'Curent baterie', unit: 'A', tex: 'I_c = \\dfrac{Q_c}{\\sqrt{3}\\,U}',
        calc: (v, r) => (v.U ? (r.Qc * 1000) / (SQRT3 * v.U) : null), dec: 1 },
    ],
  },
  {
    id: 'transmisii',
    family: 'comun',
    tier: 2,
    title: 'Transmisii mecanice',
    subtitle: 'Reductor: turatie, cuplu, inertie redusa, viteza liniara',
    fields: [
      { key: 'Pmotor', label: 'Putere motor', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'nin', label: 'Turatie intrare', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'i', label: 'Raport de transmisie', unit: ':1', default: 10, step: 0.5, min: 0.1 },
      { key: 'eta', label: 'Randament reductor', unit: '%', default: 95, step: 1, min: 0 },
      { key: 'Jsarc', label: 'Inertie sarcina', unit: 'kg·m²', default: 50, step: 1, min: 0 },
      { key: 'D', label: 'Diametru tambur', unit: 'm', default: 0.3, step: 0.05, min: 0 },
    ],
    results: [
      { key: 'nout', label: 'Turatie iesire', unit: 'rpm', tex: 'n_{out} = n_{in}/i',
        calc: (v) => (v.i ? v.nin / v.i : null), dec: 1 },
      { key: 'Min', label: 'Cuplu la motor', unit: 'Nm', tex: 'M_{in} = \\dfrac{9550\\,P}{n_{in}}',
        calc: (v) => (v.nin ? (9550 * v.Pmotor) / v.nin : null), dec: 1 },
      { key: 'Mout', label: 'Cuplu la iesire', unit: 'Nm', tex: 'M_{out} = M_{in}\\,i\\,\\eta',
        calc: (v, r) => (r.Min != null ? r.Min * v.i * (v.eta / 100) : null), dec: 1 },
      { key: 'Jred', label: 'Inertie redusa la ax motor', unit: 'kg·m²', tex: 'J_{red} = J_{sarcina}/i^2',
        calc: (v) => (v.i ? v.Jsarc / v.i ** 2 : null), dec: 3 },
      { key: 'vlin', label: 'Viteza liniara (tambur)', unit: 'm/s', tex: 'v = \\dfrac{\\pi D\\,n_{out}}{60}',
        calc: (v, r) => (r.nout != null ? (Math.PI * v.D * r.nout) / 60 : null), dec: 2 },
    ],
  },
  {
    id: 'selectie-drive',
    family: 'comun',
    tier: 2,
    title: 'Selectie drive (HD/ND)',
    subtitle: 'Curent si suprasarcina heavy/normal duty',
    note: 'Drive ales dupa curent: I_cont ≥ I_n motor. Suprasarcina ABB 150% (Heavy) / 110% (Light) timp de 1 min la fiecare 5 min. Curentul estimat e orientativ (~1.7 motoare eficiente ... 2.0 mici) — foloseste placuta.',
    fields: [
      { key: 'In', label: 'Curent nominal motor', unit: 'A', default: 28, step: 1, min: 0 },
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'OLHD', label: 'Suprasarcina HD (150%/60s)', unit: 'A', tex: 'I_{OL,HD} = 1.5\\,I_n',
        calc: (v) => 1.5 * v.In, dec: 1 },
      { key: 'OLND', label: 'Suprasarcina ND (110%/60s)', unit: 'A', tex: 'I_{OL,ND} = 1.1\\,I_n',
        calc: (v) => 1.1 * v.In, dec: 1 },
      { key: 'Inest', label: 'Curent estimat (la 400 V)', unit: 'A', tex: 'I_n \\approx 1.9\\,P[\\text{kW}]',
        calc: (v) => 1.9 * v.Pn, dec: 1 },
    ],
  },
  {
    id: 'raport-inertie',
    family: 'comun',
    tier: 2,
    title: 'Raport de inertie',
    subtitle: 'Pentru tuning bucla de turatie',
    note: 'Tinta R_J < 5 (servo) ... < 10 (uz general) pentru reglaj stabil.',
    fields: [
      { key: 'Jmot', label: 'Inertie motor', unit: 'kg·m²', default: 0.05, step: 0.01, min: 0.0001 },
      { key: 'Jsarc', label: 'Inertie sarcina', unit: 'kg·m²', default: 2.5, step: 0.1, min: 0 },
      { key: 'i', label: 'Raport de transmisie', unit: ':1', default: 5, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'Jred', label: 'Inertie sarcina redusa', unit: 'kg·m²', tex: 'J_{red} = J_{sarcina}/i^2',
        calc: (v) => (v.i ? v.Jsarc / v.i ** 2 : null), dec: 4 },
      { key: 'RJ', label: 'Raport de inertie', unit: '×', tex: 'R_J = J_{red}/J_{motor}',
        calc: (v, r) => (v.Jmot ? r.Jred / v.Jmot : null), dec: 2 },
    ],
  },
  {
    id: 'turatie-critica',
    family: 'comun',
    tier: 2,
    title: 'Turatie critica & skip',
    subtitle: 'Rezonanta mecanica si benzi de evitat',
    params: 'Skip: ABB 22.51-22.57 · Siemens p1091-1094/p1101',
    fields: [
      { key: 'k', label: 'Rigiditate', unit: 'N/m', default: 1e7, step: 1e5, min: 0 },
      { key: 'm', label: 'Masa', unit: 'kg', default: 50, step: 1, min: 0.1 },
      { key: 'fskip', label: 'Frecventa de evitat', unit: 'Hz', default: 25, step: 1, min: 0 },
      { key: 'df', label: 'Latime banda', unit: 'Hz', default: 2, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'ncrit', label: 'Turatie critica', unit: 'rpm', tex: 'n_{crit} = \\dfrac{60}{2\\pi}\\sqrt{\\dfrac{k}{m}}',
        calc: (v) => (v.m ? (60 / (2 * Math.PI)) * Math.sqrt(v.k / v.m) : null), dec: 0 },
      { key: 'bjos', label: 'Banda skip - jos', unit: 'Hz', tex: 'f_{skip} - \\Delta f',
        calc: (v) => v.fskip - v.df, dec: 1 },
      { key: 'bsus', label: 'Banda skip - sus', unit: 'Hz', tex: 'f_{skip} + \\Delta f',
        calc: (v) => v.fskip + v.df, dec: 1 },
    ],
  },
  {
    id: 'conversii',
    family: 'comun',
    tier: 2,
    title: 'Conversii de unitati',
    subtitle: 'HP, kgf·m, rad/s, kgf',
    fields: [
      { key: 'hp', label: 'Putere', unit: 'HP', default: 20, step: 1, min: 0 },
      { key: 'kgfm', label: 'Cuplu', unit: 'kgf·m', default: 10, step: 1, min: 0 },
      { key: 'rpm', label: 'Turatie', unit: 'rpm', default: 1450, step: 10, min: 0 },
      { key: 'kgf', label: 'Forta', unit: 'kgf', default: 100, step: 5, min: 0 },
    ],
    results: [
      { key: 'kW', label: 'Putere', unit: 'kW', tex: 'kW = HP\\cdot 0.7457',
        calc: (v) => v.hp * 0.7457, dec: 2 },
      { key: 'Nm', label: 'Cuplu', unit: 'Nm', tex: 'Nm = kgf{\\cdot}m\\cdot 9.807',
        calc: (v) => v.kgfm * 9.807, dec: 2 },
      { key: 'rads', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega = rpm\\cdot\\dfrac{2\\pi}{60}',
        calc: (v) => omega(v.rpm), dec: 2 },
      { key: 'N', label: 'Forta', unit: 'N', tex: 'N = kgf\\cdot 9.807',
        calc: (v) => v.kgf * 9.807, dec: 1 },
    ],
  },

  // ======================================================== CURENT CONTINUU
  {
    id: 'cc-baza',
    family: 'cc',
    tier: 2,
    title: 'Motor c.c. — marimi fundamentale',
    subtitle: 'TCEM, turatie, cuplu, putere (flux constant)',
    note: 'k·Φ in SI [V·s/rad = Nm/A]. M = k·Φ·Ia, E = k·Φ·ω.',
    charts: [(v) => {
      if (!v.kPhi) return null
      const Mrated = v.kPhi * v.Ia
      const nM = (M) => ((v.U - (M / v.kPhi) * v.Ra) * 60) / (2 * Math.PI * v.kPhi)
      return {
        xLabel: 'Cuplu M [Nm]', yLabel: 'Turatie n [rpm]',
        series: [{ label: 'n(M) separat excitat', color: COL.a, points: curve(0, Math.max(Mrated * 2, 1), nM) }],
        markers: [{ x: Mrated, y: nM(Mrated), label: 'functionare', color: COL.op }],
      }
    }],
    params: 'DCS880: U arm 99.12, Ia 99.11, Ra 27.32 · DCM: p50101/p50100/p50110',
    fields: [
      { key: 'U', label: 'Tensiune indus', unit: 'V', default: 440, step: 10, min: 0 },
      { key: 'Ia', label: 'Curent indus', unit: 'A', default: 80, step: 1, min: 0 },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', default: 0.15, step: 0.01, min: 0 },
      { key: 'kPhi', label: 'Constanta masinii', unit: 'V·s/rad', default: 2.6, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'E', label: 'TCEM (back-EMF)', unit: 'V', tex: 'E = U - I_a R_a',
        calc: (v) => v.U - v.Ia * v.Ra, dec: 1 },
      { key: 'n', label: 'Turatie', unit: 'rpm', tex: 'n = \\dfrac{60\\,E}{2\\pi\\,k\\Phi}',
        calc: (v, r) => (v.kPhi ? (60 * r.E) / (2 * Math.PI * v.kPhi) : null), dec: 0 },
      { key: 'M', label: 'Cuplu electromagnetic', unit: 'Nm', tex: 'M = k\\Phi\\,I_a',
        calc: (v) => v.kPhi * v.Ia, dec: 1 },
      { key: 'Pem', label: 'Putere electromagnetica', unit: 'kW', tex: 'P_{em} = E\\,I_a',
        calc: (v, r) => (r.E * v.Ia) / 1000, dec: 2 },
    ],
  },
  {
    id: 'cc-reglaj',
    family: 'cc',
    tier: 2,
    title: 'Motor c.c. — reglaj de turatie',
    subtitle: 'Turatie de baza si slabire de camp',
    note: 'Peste $n_{baza}$: slabire de camp (putere constanta), $M \\propto 1/n$. $I_f$ din curba de magnetizare. Raport tipic de slabire 2:1...4:1 (limitat de comutatie).',
    params: 'DCS880: EMF/field mode 28.17, turatie baza 99.14 · DCM: p50081/p50115',
    charts: [
      (v) => {
        if (!v.nbaza) return null
        const nmax = Math.max(v.ndorit, v.nbaza * 1.05)
        const M = (n) => (n <= v.nbaza ? v.Mnom : (v.Mnom * v.nbaza) / n)
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
          series: [{ label: 'M disponibil (∝1/n in slabire)', color: COL.a, points: curve(0, nmax, M) }],
          markers: [{ x: v.nbaza, y: v.Mnom, label: 'n baza', color: COL.op }],
        }
      },
      (v) => {
        if (!v.nbaza) return null
        const nmax = Math.max(v.ndorit, v.nbaza * 1.05)
        const Pmax = (v.Mnom * v.nbaza) / 9550
        const P = (n) => (n <= v.nbaza ? Pmax * (n / v.nbaza) : Pmax)
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Putere P [kW]',
          series: [{ label: 'P (constanta peste n baza)', color: COL.b, points: curve(0, nmax, P) }],
          markers: [{ x: v.nbaza, y: Pmax, label: 'n baza', color: COL.op }],
        }
      },
    ],
    fields: [
      { key: 'nbaza', label: 'Turatie de baza', unit: 'rpm', default: 1500, step: 10, min: 1 },
      { key: 'ndorit', label: 'Turatie dorita', unit: 'rpm', default: 2200, step: 10, min: 1 },
      { key: 'Mnom', label: 'Cuplu nominal', unit: 'Nm', default: 200, step: 5, min: 0 },
    ],
    results: [
      { key: 'rcamp', label: 'Raport flux (Φ/Φn)', unit: '%', tex: '\\dfrac{\\Phi}{\\Phi_n} = \\dfrac{n_{baza}}{n}',
        calc: (v) => (v.ndorit ? Math.min(1, v.nbaza / v.ndorit) * 100 : null), dec: 1 },
      { key: 'Mdisp', label: 'Cuplu disponibil', unit: 'Nm', tex: 'M = M_n\\dfrac{n_{baza}}{n}',
        calc: (v) => (v.ndorit ? v.Mnom * Math.min(1, v.nbaza / v.ndorit) : null), dec: 1 },
      { key: 'Pconst', label: 'Putere (zona camp slabit)', unit: 'kW', tex: 'P = \\dfrac{M_n\\,n_{baza}}{9550}',
        calc: (v) => (v.Mnom * v.nbaza) / 9550, dec: 2 },
    ],
  },
  {
    id: 'cc-drive',
    family: 'cc',
    tier: 2,
    title: 'Convertor c.c. (DC drive)',
    subtitle: 'Redresor comandat, constante de timp',
    note: 'Punte trifazata complet comandata (B6), functionare in 4 cadrane. $U_d = U_{d0}\\cos\\alpha$ este valoarea medie ideala (la gol); sub sarcina tensiunea reala scade cu caderea de comutatie (suprapunere) $\\approx (3X_c/\\pi)I_d$ plus caderea pe tiristoare. $\\alpha>90°$ → regim de invertor (recuperare).',
    params: 'DCS880 / Siemens DCM (redresor cu tiristoare)',
    fields: [
      { key: 'Ulinie', label: 'Tensiune retea', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'alpha', label: 'Unghi de aprindere', unit: '°', default: 20, step: 1, min: 0 },
      { key: 'La', label: 'Inductanta indus', unit: 'mH', default: 5, step: 0.5, min: 0 },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', default: 0.15, step: 0.01, min: 0.0001 },
      { key: 'J', label: 'Inertie', unit: 'kg·m²', default: 2, step: 0.5, min: 0 },
      { key: 'kPhi', label: 'Constanta masinii', unit: 'V·s/rad', default: 2.6, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'Ud0', label: 'Tensiune medie max', unit: 'V', tex: 'U_{d0} = 1.35\\,U_{linie}',
        calc: (v) => 1.35 * v.Ulinie, dec: 0 },
      { key: 'Ud', label: 'Tensiune medie indus', unit: 'V', tex: 'U_d = U_{d0}\\cos\\alpha',
        calc: (v, r) => r.Ud0 * Math.cos(rad(v.alpha)), dec: 1 },
      { key: 'taua', label: 'Constanta de timp electrica', unit: 'ms', tex: '\\tau_a = L_a/R_a',
        calc: (v) => (v.Ra ? v.La / v.Ra : null), dec: 1 },
      { key: 'taum', label: 'Constanta de timp mecanica', unit: 's', tex: '\\tau_m = \\dfrac{J R_a}{(k\\Phi)^2}',
        calc: (v) => (v.kPhi ? (v.J * v.Ra) / v.kPhi ** 2 : null), dec: 3 },
    ],
  },

  // =========================================================== SERVO / PMSM
  {
    id: 'pmsm-model',
    family: 'servo',
    tier: 2,
    title: 'Servo / PMSM — model de cuplu',
    subtitle: 'Cuplu, back-EMF, frecventa electrica',
    note: 'Kt din catalog (uzual Nm/A_rms). Kt[Nm/A] = Ke[V·s/rad].',
    charts: [(v) => {
      if (!v.n) return null
      const Mcont = v.Kt * v.Iq, Mpeak = 3 * Mcont, nb = v.n, nmax = v.n * 3
      const env = (Mflat) => curve(0, nmax, (n) => (n <= nb ? Mflat : (Mflat * nb) / n))
      return {
        xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
        series: [{ label: 'Cuplu varf (≈3×)', color: COL.b, dash: true, points: env(Mpeak) }, { label: 'Cuplu continuu', color: COL.a, points: env(Mcont) }],
        markers: [{ x: nb, y: Mcont, label: 'nominal', color: COL.op }],
      }
    }],
    params: 'S120: tip motor p0300; Kt/Ke din date motor',
    fields: [
      { key: 'Kt', label: 'Constanta de cuplu', unit: 'Nm/A', default: 1.2, step: 0.1, min: 0 },
      { key: 'Iq', label: 'Curent de cuadratura', unit: 'A', default: 8, step: 0.5, min: 0 },
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 3000, step: 50, min: 0 },
      { key: 'ppp', label: 'Perechi de poli', unit: '', default: 4, step: 1, min: 1 },
    ],
    results: [
      { key: 'M', label: 'Cuplu', unit: 'Nm', tex: 'M = K_t\\,I_q',
        calc: (v) => v.Kt * v.Iq, dec: 2 },
      { key: 'E', label: 'Back-EMF', unit: 'V', tex: 'E = K_e\\,\\omega,\\; K_e = K_t',
        calc: (v) => v.Kt * omega(v.n), dec: 1 },
      { key: 'fe', label: 'Frecventa electrica', unit: 'Hz', tex: 'f_e = \\dfrac{p_{pp}\\,n}{60}',
        calc: (v) => (v.ppp * v.n) / 60, dec: 1 },
      { key: 'P', label: 'Putere', unit: 'kW', tex: 'P = M\\,\\omega',
        calc: (v, r) => (r.M * omega(v.n)) / 1000, dec: 2 },
    ],
  },
  {
    id: 'pmsm-ciclu',
    family: 'servo',
    tier: 2,
    title: 'Servo — dimensionare pe ciclu',
    subtitle: 'Cuplu RMS si cuplu de varf',
    note: 'M_rms ≤ M_continuu(n); M_varf ≤ M_varf_motor(n).',
    fields: [
      { key: 'Macc', label: 'Cuplu accelerare', unit: 'Nm', default: 10, step: 0.5, min: 0 },
      { key: 'tacc', label: 'Timp accelerare', unit: 's', default: 0.2, step: 0.05, min: 0 },
      { key: 'Mconst', label: 'Cuplu constant', unit: 'Nm', default: 4, step: 0.5, min: 0 },
      { key: 'tconst', label: 'Timp constant', unit: 's', default: 1, step: 0.1, min: 0 },
      { key: 'Mdec', label: 'Cuplu decelerare', unit: 'Nm', default: 8, step: 0.5, min: 0 },
      { key: 'tdec', label: 'Timp decelerare', unit: 's', default: 0.2, step: 0.05, min: 0 },
      { key: 'tdwell', label: 'Timp pauza', unit: 's', default: 0.5, step: 0.1, min: 0 },
    ],
    results: [
      { key: 'tciclu', label: 'Timp ciclu', unit: 's', tex: 't_{ciclu} = \\sum t_i',
        calc: (v) => v.tacc + v.tconst + v.tdec + v.tdwell, dec: 2 },
      { key: 'Mrms', label: 'Cuplu RMS (termic)', unit: 'Nm', tex: 'M_{rms} = \\sqrt{\\dfrac{\\sum M_i^2 t_i}{\\sum t_i}}',
        calc: (v, r) => { const num = v.Macc ** 2 * v.tacc + v.Mconst ** 2 * v.tconst + v.Mdec ** 2 * v.tdec; return r.tciclu > 0 ? Math.sqrt(num / r.tciclu) : null }, dec: 2 },
      { key: 'Mvarf', label: 'Cuplu de varf', unit: 'Nm', tex: 'M_{varf} = \\max(M_i)',
        calc: (v) => Math.max(v.Macc, v.Mconst, v.Mdec), dec: 2 },
    ],
  },
  {
    id: 'pmsm-feedback',
    family: 'servo',
    tier: 2,
    title: 'Servo — feedback & dinamica',
    subtitle: 'Encoder, viteza, constante de timp',
    note: 'Cuadratura ×4 la encoder incremental.',
    fields: [
      { key: 'PPR', label: 'Impulsuri/rotatie', unit: 'PPR', default: 2500, step: 100, min: 1 },
      { key: 'imp', label: 'Impulsuri numarate', unit: '', default: 625, step: 1, min: 0 },
      { key: 't', label: 'Timp de masura', unit: 's', default: 0.01, step: 0.001, min: 0.0001 },
      { key: 'L', label: 'Inductanta', unit: 'mH', default: 8, step: 0.5, min: 0 },
      { key: 'R', label: 'Rezistenta', unit: 'Ω', default: 1.5, step: 0.1, min: 0.0001 },
      { key: 'J', label: 'Inertie', unit: 'kg·m²', default: 0.0005, step: 0.0001, min: 0 },
      { key: 'Kt', label: 'Constanta de cuplu', unit: 'Nm/A', default: 1.2, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'pas', label: 'Rezolutie unghiulara', unit: '°', tex: '\\Delta\\theta = \\dfrac{360}{4\\,PPR}',
        calc: (v) => (v.PPR ? 360 / (4 * v.PPR) : null), dec: 4 },
      { key: 'nimp', label: 'Turatie din impulsuri', unit: 'rpm', tex: 'n = \\dfrac{60\\,imp}{4\\,PPR\\,t}',
        calc: (v) => { const d = 4 * v.PPR * v.t; return d ? (60 * v.imp) / d : null }, dec: 1 },
      { key: 'taue', label: 'Constanta de timp electrica', unit: 'ms', tex: '\\tau_e = L/R',
        calc: (v) => (v.R ? v.L / v.R : null), dec: 2 },
      { key: 'taum', label: 'Constanta de timp mecanica', unit: 'ms', tex: '\\tau_m = \\dfrac{J R}{K_t^2}',
        calc: (v) => (v.Kt ? (v.J * v.R) / v.Kt ** 2 * 1000 : null), dec: 2 },
    ],
  },

  // ================================================================ SINCRON
  {
    id: 'sincron-turatie',
    family: 'sincron',
    tier: 2,
    title: 'Motor sincron — turatie & excitatie',
    subtitle: 'Turatie sincrona, t.e.m. din excitatie',
    note: 'Alunecare zero (n = n_s). Reglaj FP prin excitatie (supraexcitat = capacitiv).',
    fields: [
      { key: 'f', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 0 },
      { key: 'p', label: 'Numar de poli', unit: '', default: 4, step: 2, min: 2 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'Ia', label: 'Curent indus', unit: 'A', default: 50, step: 1, min: 0 },
      { key: 'Xs', label: 'Reactanta sincrona', unit: 'Ω', default: 2.5, step: 0.1, min: 0 },
      { key: 'phi', label: 'Unghi factor de putere', unit: '°', default: 20, step: 1, min: 0 },
    ],
    results: [
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', tex: 'n_s = \\dfrac{120\\,f}{p}',
        calc: (v) => (v.p ? (120 * v.f) / v.p : null), dec: 0 },
      { key: 'ws', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega_s = \\dfrac{2\\pi n_s}{60}',
        calc: (v, r) => (r.ns != null ? omega(r.ns) : null), dec: 2 },
      { key: 'E', label: 'T.e.m. indusa', unit: 'V', tex: 'E = \\sqrt{(U + I_a X_s\\sin\\varphi)^2 + (I_a X_s\\cos\\varphi)^2}',
        calc: (v) => { const a = v.U + v.Ia * v.Xs * Math.sin(rad(v.phi)); const b = v.Ia * v.Xs * Math.cos(rad(v.phi)); return Math.sqrt(a * a + b * b) }, dec: 1 },
    ],
  },
  {
    id: 'sincron-putere',
    family: 'sincron',
    tier: 2,
    title: 'Motor sincron — putere & cuplu',
    subtitle: 'Unghi de sarcina, cuplu de desprindere',
    note: 'U, E = tensiuni de linie. Stabil pentru δ < 90°; pull-out la δ = 90°.',
    charts: [(v) => {
      if (!v.Xs) return null
      const Pmax = (v.U * v.E) / v.Xs / 1000
      return {
        xLabel: 'Unghi de sarcina δ [°]', yLabel: 'Putere P [kW]',
        series: [{ label: 'P(δ) = U·E·sinδ / Xs', color: COL.a, points: curve(0, 180, (deg) => Pmax * Math.sin(rad(deg))) }],
        markers: [{ x: v.delta, y: Pmax * Math.sin(rad(v.delta)), label: 'δ curent', color: COL.op }],
      }
    }],
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'E', label: 'T.e.m. (excitatie)', unit: 'V', default: 420, step: 10, min: 0 },
      { key: 'Xs', label: 'Reactanta sincrona', unit: 'Ω', default: 2.5, step: 0.1, min: 0.01 },
      { key: 'delta', label: 'Unghi de sarcina', unit: '°', default: 30, step: 1, min: 0 },
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', default: 1500, step: 10, min: 1 },
    ],
    results: [
      { key: 'ws', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega_s = \\dfrac{2\\pi n_s}{60}',
        calc: (v) => omega(v.ns), dec: 2 },
      { key: 'P', label: 'Putere electromagnetica', unit: 'kW', tex: 'P = \\dfrac{U E\\sin\\delta}{X_s}',
        calc: (v) => (v.Xs ? (v.U * v.E * Math.sin(rad(v.delta))) / v.Xs / 1000 : null), dec: 2 },
      { key: 'M', label: 'Cuplu', unit: 'Nm', tex: 'M = P/\\omega_s',
        calc: (v, r) => (r.ws ? (r.P * 1000) / r.ws : null), dec: 1 },
      { key: 'Mmax', label: 'Cuplu de desprindere', unit: 'Nm', tex: 'M_{max} = \\dfrac{U E}{X_s\\,\\omega_s}',
        calc: (v, r) => (v.Xs && r.ws ? (v.U * v.E) / v.Xs / r.ws : null), dec: 1 },
    ],
  },

  // ============================================ P1: ASINCRON "REAL" (diagnoza)
  {
    id: 'motor-echivalent',
    family: 'asincron',
    tier: 3,
    title: 'Schema echivalenta (Thevenin)',
    subtitle: 'Cuplu si curent reale din R1,X1,Xm,R2,X2',
    note: 'Tensiuni pe faza interne (U_linie/√3). Aproximatie clasica cu Rm neglijat.',
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'f', label: 'Frecventa', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'p', label: 'Numar de poli', unit: '', default: 4, step: 2, min: 2 },
      { key: 'R1', label: 'Rezistenta stator R1', unit: 'Ω', default: 0.5, step: 0.05, min: 0 },
      { key: 'X1', label: 'Reactanta stator X1', unit: 'Ω', default: 1.2, step: 0.1, min: 0 },
      { key: 'Xm', label: 'Reactanta magnetizare Xm', unit: 'Ω', default: 40, step: 1, min: 0.1 },
      { key: 'R2', label: 'Rezistenta rotor R2', unit: 'Ω', default: 0.4, step: 0.05, min: 0.001 },
      { key: 'X2', label: 'Reactanta rotor X2', unit: 'Ω', default: 1.2, step: 0.1, min: 0 },
      { key: 'n', label: 'Turatie (punct)', unit: 'rpm', default: 1450, step: 10, min: 0 },
    ],
    charts: [
      (v) => {
        if (!v.p) return null
        const ns = 120 * v.f / v.p, ws = omega(ns)
        const Vth = (v.U / SQRT3) * v.Xm / Math.sqrt(v.R1 ** 2 + (v.X1 + v.Xm) ** 2)
        const Rth = v.R1 * (v.Xm / (v.X1 + v.Xm)) ** 2
        const Xth = v.X1
        const M = (n) => { const s = (ns - n) / ns || 1e-4; return (3 * Vth ** 2 * (v.R2 / s)) / (ws * ((Rth + v.R2 / s) ** 2 + (Xth + v.X2) ** 2)) }
        const sOp = (ns - v.n) / ns || 1e-4
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
          series: [{ label: 'M(n) schema echiv.', color: COL.a, points: curve(1, ns, M) }],
          markers: [{ x: v.n, y: M(v.n), label: 'functionare', color: COL.op }],
        }
      },
      (v) => {
        if (!v.p) return null
        const ns = 120 * v.f / v.p
        const Vth = (v.U / SQRT3) * v.Xm / Math.sqrt(v.R1 ** 2 + (v.X1 + v.Xm) ** 2)
        const Rth = v.R1 * (v.Xm / (v.X1 + v.Xm)) ** 2
        const I2 = (n) => { const s = (ns - n) / ns || 1e-4; return Vth / Math.sqrt((Rth + v.R2 / s) ** 2 + (v.X1 + v.X2) ** 2) }
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Curent rotor I_2 [A]',
          series: [{ label: 'I2(n)', color: COL.c, points: curve(1, ns, I2) }],
          markers: [{ x: v.n, y: I2(v.n), label: 'functionare', color: COL.op }],
        }
      },
    ],
    results: [
      { key: 'Vth', label: 'Tensiune Thevenin', unit: 'V', tex: 'U_{th} = \\dfrac{U_{ph}\\,X_m}{\\sqrt{R_1^2+(X_1+X_m)^2}}',
        calc: (v) => (v.U / SQRT3) * v.Xm / Math.sqrt(v.R1 ** 2 + (v.X1 + v.Xm) ** 2), dec: 1 },
      { key: 'I2', label: 'Curent rotor (la n)', unit: 'A', tex: 'I_2 = \\dfrac{U_{th}}{\\sqrt{(R_{th}+R_2/s)^2+(X_{th}+X_2)^2}}',
        calc: (v, r) => { if (!v.p) return null; const ns = 120 * v.f / v.p; const s = (ns - v.n) / ns || 1e-4; const Rth = v.R1 * (v.Xm / (v.X1 + v.Xm)) ** 2; return r.Vth / Math.sqrt((Rth + v.R2 / s) ** 2 + (v.X1 + v.X2) ** 2) }, dec: 1 },
      { key: 'M', label: 'Cuplu (la n)', unit: 'Nm', tex: 'M = \\dfrac{3\\,U_{th}^2\\,(R_2/s)}{\\omega_s[(R_{th}+R_2/s)^2+(X_{th}+X_2)^2]}',
        calc: (v, r) => { if (!v.p) return null; const ns = 120 * v.f / v.p; const ws = omega(ns); const s = (ns - v.n) / ns || 1e-4; const Rth = v.R1 * (v.Xm / (v.X1 + v.Xm)) ** 2; return (3 * r.Vth ** 2 * (v.R2 / s)) / (ws * ((Rth + v.R2 / s) ** 2 + (v.X1 + v.X2) ** 2)) }, dec: 1 },
      { key: 'smax', label: 'Alunecare critica', unit: '%', tex: 's_{max} = \\dfrac{R_2}{\\sqrt{R_{th}^2+(X_{th}+X_2)^2}}',
        calc: (v) => { const Rth = v.R1 * (v.Xm / (v.X1 + v.Xm)) ** 2; return (v.R2 / Math.sqrt(Rth ** 2 + (v.X1 + v.X2) ** 2)) * 100 }, dec: 2 },
      { key: 'Mmax', label: 'Cuplu maxim (breakdown)', unit: 'Nm', tex: 'M_{max} = \\dfrac{3\\,U_{th}^2}{2\\,\\omega_s[R_{th}+\\sqrt{R_{th}^2+(X_{th}+X_2)^2}]}',
        calc: (v, r) => { if (!v.p) return null; const ws = omega(120 * v.f / v.p); const Rth = v.R1 * (v.Xm / (v.X1 + v.Xm)) ** 2; return (3 * r.Vth ** 2) / (2 * ws * (Rth + Math.sqrt(Rth ** 2 + (v.X1 + v.X2) ** 2))) }, dec: 1 },
    ],
  },
  {
    id: 'bilant-putere',
    family: 'asincron',
    tier: 3,
    title: 'Bilant de puteri & randament',
    subtitle: 'Defalcarea pierderilor (power-flow)',
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'I', label: 'Curent de linie', unit: 'A', default: 18, step: 0.5, min: 0 },
      { key: 'cosphi', label: 'Factor de putere', unit: '', default: 0.85, step: 0.01, min: 0 },
      { key: 'R1', label: 'Rezistenta stator R1', unit: 'Ω', default: 0.5, step: 0.05, min: 0 },
      { key: 's', label: 'Alunecare', unit: '%', default: 3.33, step: 0.1, min: 0 },
      { key: 'Pcore', label: 'Pierderi in fier', unit: 'W', default: 150, step: 10, min: 0 },
      { key: 'Pfw', label: 'Frecare + ventilatie', unit: 'W', default: 100, step: 10, min: 0 },
      { key: 'Pstray', label: 'Pierderi suplimentare', unit: 'W', default: 50, step: 10, min: 0 },
    ],
    results: [
      { key: 'Pin', label: 'Putere absorbita', unit: 'W', tex: 'P_{in} = \\sqrt{3}\\,U I\\cos\\varphi',
        calc: (v) => SQRT3 * v.U * v.I * v.cosphi, dec: 0 },
      { key: 'Pscl', label: 'Pierderi Cu stator', unit: 'W', tex: 'P_{scl} = 3 I^2 R_1',
        calc: (v) => 3 * v.I ** 2 * v.R1, dec: 0 },
      { key: 'Pag', label: 'Putere intrefier', unit: 'W', tex: 'P_{ag} = P_{in}-P_{scl}-P_{fier}',
        calc: (v, r) => r.Pin - r.Pscl - v.Pcore, dec: 0 },
      { key: 'Prcl', label: 'Pierderi Cu rotor', unit: 'W', tex: 'P_{rcl} = s\\,P_{ag}',
        calc: (v, r) => (v.s / 100) * r.Pag, dec: 0 },
      { key: 'Pout', label: 'Putere la arbore', unit: 'W', tex: 'P_{out} = (1-s)P_{ag}-P_{fw}-P_{stray}',
        calc: (v, r) => r.Pag - r.Prcl - v.Pfw - v.Pstray, dec: 0 },
      { key: 'eta', label: 'Randament', unit: '%', tex: '\\eta = \\dfrac{P_{out}}{P_{in}}\\cdot 100',
        calc: (v, r) => (r.Pin ? (r.Pout / r.Pin) * 100 : null), dec: 1 },
    ],
  },
  {
    id: 'teste-parametri',
    family: 'asincron',
    tier: 3,
    title: 'Parametri din teste',
    subtitle: 'Schema echivalenta din test gol / c.c. / rotor blocat',
    note: 'Test c.c. pe 2 faze (R1). Reactante la frecventa de test — corecteaza la f nominala.',
    fields: [
      { key: 'Vdc', label: 'Test c.c.: tensiune', unit: 'V', default: 10, step: 1, min: 0 },
      { key: 'Idc', label: 'Test c.c.: curent', unit: 'A', default: 20, step: 1, min: 0.1 },
      { key: 'Vnl', label: 'Gol: tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'Inl', label: 'Gol: curent', unit: 'A', default: 8, step: 0.5, min: 0.1 },
      { key: 'Vlr', label: 'Rotor blocat: tensiune', unit: 'V', default: 90, step: 5, min: 0 },
      { key: 'Ilr', label: 'Rotor blocat: curent', unit: 'A', default: 30, step: 1, min: 0.1 },
      { key: 'Plr', label: 'Rotor blocat: putere', unit: 'W', default: 1800, step: 50, min: 0 },
    ],
    results: [
      { key: 'R1', label: 'Rezistenta stator R1', unit: 'Ω', tex: 'R_1 = \\dfrac{U_{dc}}{2 I_{dc}}',
        calc: (v) => (v.Idc ? v.Vdc / (2 * v.Idc) : null), dec: 3 },
      { key: 'R2', label: 'Rezistenta rotor R2', unit: 'Ω', tex: 'R_2 = Z_{lr}\\cos\\theta - R_1',
        calc: (v, r) => { const Z = v.Vlr / SQRT3 / v.Ilr; const ct = v.Plr / (SQRT3 * v.Vlr * v.Ilr); return Z * ct - r.R1 }, dec: 3 },
      { key: 'Xlr', label: 'Reactanta X1+X2', unit: 'Ω', tex: 'X_1+X_2 = Z_{lr}\\sin\\theta',
        calc: (v) => { const Z = v.Vlr / SQRT3 / v.Ilr; const ct = v.Plr / (SQRT3 * v.Vlr * v.Ilr); return Z * Math.sqrt(Math.max(0, 1 - ct ** 2)) }, dec: 3 },
      { key: 'Xm', label: 'Reactanta magnetizare Xm', unit: 'Ω', tex: 'X_m \\approx Z_{nl} - X_1',
        calc: (v, r) => { const Znl = v.Vnl / SQRT3 / v.Inl; return Znl - r.Xlr / 2 }, dec: 2 },
    ],
  },
  {
    id: 'randament-sarcina',
    family: 'asincron',
    tier: 3,
    title: 'Randament vs sarcina',
    subtitle: 'De ce motorul supradimensionat e ineficient',
    note: 'Randamentul scade sub ~50% sarcina; maxim acolo unde pierderile fixe = cele variabile.',
    fields: [
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0.1 },
      { key: 'etan', label: 'Randament nominal', unit: '%', default: 90, step: 0.5, min: 1 },
      { key: 'Pconst', label: 'Pierderi fixe (fier+fw)', unit: 'W', default: 350, step: 10, min: 0 },
    ],
    charts: [(v) => {
      const Ploss = v.Pn * 1000 * (1 / (v.etan / 100) - 1)
      const Pvar = Math.max(0, Ploss - v.Pconst)
      const eta = (x) => { const Po = x * v.Pn * 1000; return (Po / (Po + v.Pconst + x ** 2 * Pvar)) * 100 }
      return {
        xLabel: 'Sarcina [% din P_n]', yLabel: 'Randament η [%]',
        series: [{ label: 'η(sarcina)', color: COL.a, points: curve(10, 120, (xp) => eta(xp / 100)) }],
        markers: [{ x: 100, y: eta(1), label: 'nominal', color: COL.op }],
      }
    }],
    results: [
      { key: 'Pvar', label: 'Pierderi variabile nom.', unit: 'W', tex: 'P_{var} = P_{loss,n} - P_{const}',
        calc: (v) => Math.max(0, v.Pn * 1000 * (1 / (v.etan / 100) - 1) - v.Pconst), dec: 0 },
      { key: 'xopt', label: 'Sarcina la η maxim', unit: '%', tex: 'x^* = \\sqrt{P_{const}/P_{var}}',
        calc: (v, r) => (r.Pvar > 0 ? Math.sqrt(v.Pconst / r.Pvar) * 100 : null), dec: 0 },
      { key: 'eta50', label: 'Randament la 50%', unit: '%', tex: '\\eta(0.5)',
        calc: (v, r) => { const Po = 0.5 * v.Pn * 1000; return (Po / (Po + v.Pconst + 0.25 * r.Pvar)) * 100 }, dec: 1 },
      { key: 'eta25', label: 'Randament la 25%', unit: '%', tex: '\\eta(0.25)',
        calc: (v, r) => { const Po = 0.25 * v.Pn * 1000; return (Po / (Po + v.Pconst + 0.0625 * r.Pvar)) * 100 }, dec: 1 },
    ],
  },
  {
    id: 'dezechilibru',
    family: 'asincron',
    tier: 3,
    title: 'Dezechilibru de tensiune',
    subtitle: 'Derating si supraincalzire (IEC 60034-1)',
    note: 'Peste 5% dezechilibru: nu porni motorul. Factor derating ~ aproximare curba NEMA.',
    fields: [
      { key: 'Uab', label: 'Tensiune A-B', unit: 'V', default: 400, step: 1, min: 0 },
      { key: 'Ubc', label: 'Tensiune B-C', unit: 'V', default: 395, step: 1, min: 0 },
      { key: 'Uca', label: 'Tensiune C-A', unit: 'V', default: 390, step: 1, min: 0 },
    ],
    results: [
      { key: 'Umed', label: 'Tensiune medie', unit: 'V', tex: 'U_{med} = \\dfrac{U_{AB}+U_{BC}+U_{CA}}{3}',
        calc: (v) => (v.Uab + v.Ubc + v.Uca) / 3, dec: 1 },
      { key: 'UV', label: 'Dezechilibru', unit: '%', tex: 'UV = \\dfrac{\\Delta U_{max}}{U_{med}}\\cdot 100',
        calc: (v, r) => { const d = Math.max(Math.abs(v.Uab - r.Umed), Math.abs(v.Ubc - r.Umed), Math.abs(v.Uca - r.Umed)); return r.Umed ? (d / r.Umed) * 100 : null }, dec: 2 },
      { key: 'df', label: 'Factor de derating', unit: '×', tex: 'k \\approx 1 - 0.0125\\,UV^2',
        calc: (v, r) => (r.UV <= 1 ? 1 : Math.max(0.7, 1 - 0.0125 * r.UV ** 2)), dec: 3 },
      { key: 'dT', label: 'Crestere incalzire (relativ)', unit: '% nom', tex: '\\Delta\\theta\\,[\\%] \\approx 2\\,UV^2',
        calc: (v, r) => 2 * r.UV ** 2, dec: 1 },
      { key: 'Iunb', label: 'Dezechilibru de curent', unit: '%', tex: '\\approx 8\\,UV',
        calc: (v, r) => 8 * r.UV, dec: 1 },
    ],
  },

  // ===================================== P2: POMPE & VENTILATOARE
  {
    id: 'pompa-sistem',
    family: 'pompe',
    tier: 3,
    title: 'Punct de functionare (curba sistem)',
    subtitle: 'Pompa x sistem cu inaltime statica',
    note: 'Cu cap static H_static > 0 economia e mai mica decat legea cubului si apare turatie minima.',
    fields: [
      { key: 'Hstatic', label: 'Inaltime statica', unit: 'm', default: 10, step: 1, min: 0 },
      { key: 'Hnom', label: 'Inaltime la debit nom.', unit: 'm', default: 32, step: 1, min: 0 },
      { key: 'Qnom', label: 'Debit nominal', unit: 'm³/h', default: 100, step: 5, min: 1 },
      { key: 'Hshut', label: 'Inaltime la debit 0', unit: 'm', default: 40, step: 1, min: 0 },
      { key: 'n1', label: 'Turatie nominala', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'Qtarget', label: 'Debit cerut', unit: 'm³/h', default: 70, step: 5, min: 0 },
    ],
    charts: [(v) => {
      if (!v.Qnom || !v.Hshut) return null
      const k = (v.Hnom - v.Hstatic) / v.Qnom ** 2
      const a = (v.Hshut - v.Hnom) / v.Qnom ** 2
      const r2 = (v.Hstatic + (k + a) * v.Qtarget ** 2) / v.Hshut
      const nr = v.n1 * Math.sqrt(Math.max(0, r2))
      const Qmax = v.Qnom * 1.15
      return {
        xLabel: 'Debit Q [m³/h]', yLabel: 'Inaltime H [m]',
        series: [
          { label: 'Sistem', color: COL.b, points: curve(0, Qmax, (Q) => v.Hstatic + k * Q ** 2) },
          { label: 'Pompa @n1', color: COL.a, points: curve(0, Qmax, (Q) => v.Hshut - a * Q ** 2) },
          { label: 'Pompa @n cerut', color: COL.c, dash: true, points: curve(0, Qmax, (Q) => v.Hshut * r2 - a * Q ** 2) },
        ],
        markers: [
          { x: v.Qnom, y: v.Hnom, label: 'nominal', color: COL.a },
          { x: v.Qtarget, y: v.Hstatic + k * v.Qtarget ** 2, label: 'cerut', color: COL.op },
        ],
      }
    }],
    results: [
      { key: 'Hreq', label: 'Inaltime ceruta', unit: 'm', tex: 'H = H_{static} + k\\,Q^2',
        calc: (v) => { const k = (v.Hnom - v.Hstatic) / v.Qnom ** 2; return v.Hstatic + k * v.Qtarget ** 2 }, dec: 1 },
      { key: 'nreq', label: 'Turatie ceruta', unit: 'rpm', tex: 'n = n_1\\sqrt{\\dfrac{H_{static}+(k+a)Q^2}{H_{shut}}}',
        calc: (v) => { if (!v.Hshut) return null; const k = (v.Hnom - v.Hstatic) / v.Qnom ** 2; const a = (v.Hshut - v.Hnom) / v.Qnom ** 2; return v.n1 * Math.sqrt(Math.max(0, (v.Hstatic + (k + a) * v.Qtarget ** 2) / v.Hshut)) }, dec: 0 },
      { key: 'freq', label: 'Frecventa ceruta', unit: 'Hz', tex: 'f = 50\\,n/n_1',
        calc: (v, r) => (v.n1 ? 50 * r.nreq / v.n1 : null), dec: 1 },
    ],
  },
  {
    id: 'turatie-minima',
    family: 'pompe',
    tier: 3,
    title: 'Turatie minima utila',
    subtitle: 'Pragul sub care pompa nu mai da debit',
    note: 'Sub n_min, H_pompa < H_static => debit zero. Seteaza min frequency in drive peste acest prag.',
    fields: [
      { key: 'Hstatic', label: 'Inaltime statica', unit: 'm', default: 10, step: 1, min: 0 },
      { key: 'Hshut', label: 'Inaltime la debit 0 (nom.)', unit: 'm', default: 40, step: 1, min: 0.1 },
      { key: 'nnom', label: 'Turatie nominala', unit: 'rpm', default: 1450, step: 10, min: 1 },
    ],
    results: [
      { key: 'ratio', label: 'Raport turatie minima', unit: '%', tex: '\\dfrac{n_{min}}{n_{nom}} = \\sqrt{\\dfrac{H_{static}}{H_{shut}}}',
        calc: (v) => (v.Hshut ? Math.sqrt(v.Hstatic / v.Hshut) * 100 : null), dec: 1 },
      { key: 'nmin', label: 'Turatie minima', unit: 'rpm', tex: 'n_{min} = n_{nom}\\sqrt{H_{static}/H_{shut}}',
        calc: (v, r) => (r.ratio != null ? v.nnom * r.ratio / 100 : null), dec: 0 },
      { key: 'fmin', label: 'Frecventa minima', unit: 'Hz', tex: 'f_{min} = 50\\sqrt{H_{static}/H_{shut}}',
        calc: (v, r) => (r.ratio != null ? 50 * r.ratio / 100 : null), dec: 1 },
    ],
  },
  {
    id: 'npsh',
    family: 'pompe',
    tier: 3,
    title: 'NPSH (cavitatie)',
    subtitle: 'NPSH disponibil vs cerut + marja',
    note: 'Conditie: NPSHa ≥ NPSHr + marja (0.5-1 m). La boost peste turatia nominala, NPSHr creste cu n².',
    fields: [
      { key: 'patm', label: 'Presiune atmosferica', unit: 'bar', default: 1.013, step: 0.01, min: 0 },
      { key: 'pvap', label: 'Presiune vapori lichid', unit: 'bar', default: 0.023, step: 0.001, min: 0 },
      { key: 'rho', label: 'Densitate lichid', unit: 'kg/m³', default: 1000, step: 10, min: 1 },
      { key: 'Hasp', label: 'Inaltime aspiratie (+inecat)', unit: 'm', default: 2, step: 0.5, min: -20 },
      { key: 'Hfrec', label: 'Pierderi pe aspiratie', unit: 'm', default: 1.5, step: 0.1, min: 0 },
      { key: 'NPSHrn', label: 'NPSH cerut (nominal)', unit: 'm', default: 3, step: 0.5, min: 0 },
      { key: 'nratio', label: 'Turatie', unit: '% nom', default: 100, step: 5, min: 0 },
    ],
    results: [
      { key: 'NPSHa', label: 'NPSH disponibil', unit: 'm', tex: 'NPSH_a = \\dfrac{p_{atm}-p_{vap}}{\\rho g} + H_{asp} - H_{frec}',
        calc: (v) => ((v.patm - v.pvap) * 1e5) / (v.rho * 9.81) + v.Hasp - v.Hfrec, dec: 2 },
      { key: 'NPSHr', label: 'NPSH cerut (la n)', unit: 'm', tex: 'NPSH_r(n) = NPSH_{r,n}(n/n_{nom})^2',
        calc: (v) => v.NPSHrn * (v.nratio / 100) ** 2, dec: 2 },
      { key: 'marja', label: 'Marja', unit: 'm', tex: 'NPSH_a - NPSH_r',
        calc: (v, r) => r.NPSHa - r.NPSHr, dec: 2 },
    ],
  },
  {
    id: 'putere-pompa',
    family: 'pompe',
    tier: 3,
    title: 'Putere pompa (wire-to-water)',
    subtitle: 'Hidraulica → arbore → motor → retea',
    fields: [
      { key: 'rho', label: 'Densitate', unit: 'kg/m³', default: 1000, step: 10, min: 1 },
      { key: 'Q', label: 'Debit', unit: 'm³/h', default: 100, step: 5, min: 0 },
      { key: 'H', label: 'Inaltime', unit: 'm', default: 32, step: 1, min: 0 },
      { key: 'etap', label: 'Randament pompa', unit: '%', default: 75, step: 1, min: 1 },
      { key: 'etam', label: 'Randament motor', unit: '%', default: 92, step: 1, min: 1 },
      { key: 'etad', label: 'Randament drive', unit: '%', default: 97, step: 1, min: 1 },
    ],
    results: [
      { key: 'Phid', label: 'Putere hidraulica', unit: 'kW', tex: 'P_{hid} = \\dfrac{\\rho g Q H}{1000}',
        calc: (v) => (v.rho * 9.81 * (v.Q / 3600) * v.H) / 1000, dec: 2 },
      { key: 'Parb', label: 'Putere la arbore', unit: 'kW', tex: 'P_{arb} = P_{hid}/\\eta_{pompa}',
        calc: (v, r) => r.Phid / (v.etap / 100), dec: 2 },
      { key: 'Pmot', label: 'Putere absorbita motor', unit: 'kW', tex: 'P_{mot} = P_{arb}/\\eta_{motor}',
        calc: (v, r) => r.Parb / (v.etam / 100), dec: 2 },
      { key: 'Pret', label: 'Putere din retea', unit: 'kW', tex: 'P_{retea} = P_{mot}/\\eta_{drive}',
        calc: (v, r) => r.Pmot / (v.etad / 100), dec: 2 },
    ],
  },
  {
    id: 'ventilator-densitate',
    family: 'pompe',
    tier: 3,
    title: 'Ventilator — corectie densitate',
    subtitle: 'Presiune si putere vs temperatura/altitudine',
    note: 'La densitate redusa (gaz cald, altitudine) presiunea si CUPLUL scad proportional cu ρ.',
    fields: [
      { key: 'T', label: 'Temperatura aer/gaz', unit: '°C', default: 20, step: 5, min: -50 },
      { key: 'alt', label: 'Altitudine', unit: 'm', default: 0, step: 100, min: 0 },
      { key: 'rho0', label: 'Densitate de referinta', unit: 'kg/m³', default: 1.2, step: 0.05, min: 0.1 },
      { key: 'Pref', label: 'Putere la ρ referinta', unit: 'kW', default: 15, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'rho', label: 'Densitate reala', unit: 'kg/m³', tex: '\\rho = \\dfrac{p_{atm}}{R\\,(T+273.15)}',
        calc: (v) => { const p = 101325 * (1 - 2.25577e-5 * v.alt) ** 5.25588; return p / (287.05 * (v.T + 273.15)) }, dec: 3 },
      { key: 'ratio', label: 'Raport densitate', unit: '×', tex: '\\rho/\\rho_0',
        calc: (v, r) => (v.rho0 ? r.rho / v.rho0 : null), dec: 3 },
      { key: 'Preal', label: 'Putere reala', unit: 'kW', tex: 'P = P_{ref}\\,\\rho/\\rho_0',
        calc: (v, r) => v.Pref * r.ratio, dec: 2 },
    ],
  },
  {
    id: 'turatie-specifica',
    family: 'pompe',
    tier: 3,
    title: 'Turatie specifica (nq)',
    subtitle: 'Tipul rotorului din n, Q, H',
    note: 'nq ~10-30 radial · 30-80 mixt · 80-200 axial. Axialul are cuplu mare la debit mic.',
    fields: [
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'Q', label: 'Debit (la BEP)', unit: 'm³/h', default: 100, step: 5, min: 0.1 },
      { key: 'H', label: 'Inaltime (la BEP)', unit: 'm', default: 32, step: 1, min: 0.1 },
    ],
    results: [
      { key: 'nq', label: 'Turatie specifica', unit: 'rpm', tex: 'n_q = \\dfrac{n\\sqrt{Q}}{H^{0.75}}',
        calc: (v) => (v.n * Math.sqrt(v.Q / 3600)) / v.H ** 0.75, dec: 1 },
    ],
  },

  // ============================= P3: INSTALATIE & CALITATEA ENERGIEI
  {
    id: 'cablu-protectii',
    family: 'comun',
    tier: 3,
    title: 'Cablu — protectii (I²t & ampacitate)',
    subtitle: 'Verificare termica scurtcircuit + curent admisibil',
    note: 'k: Cu-PVC 115, Cu-XLPE 143, Al-PVC 76, Al-XLPE 94. Compara S_min cu sectiunea aleasa.',
    fields: [
      { key: 'Icc', label: 'Curent scurtcircuit', unit: 'A', default: 6000, step: 100, min: 0 },
      { key: 't', label: 'Timp declansare', unit: 's', default: 0.1, step: 0.01, min: 0.001 },
      { key: 'k', label: 'Constanta k (material)', unit: '', default: 143, step: 1, min: 1 },
      { key: 'It', label: 'Curent admisibil tabelar', unit: 'A', default: 40, step: 1, min: 0 },
      { key: 'Ca', label: 'Factor temperatura', unit: '', default: 0.94, step: 0.01, min: 0.1 },
      { key: 'Cg', label: 'Factor grupare', unit: '', default: 0.8, step: 0.05, min: 0.1 },
      { key: 'IB', label: 'Curent de sarcina', unit: 'A', default: 28, step: 1, min: 0 },
    ],
    results: [
      { key: 'Smin', label: 'Sectiune minima termica', unit: 'mm²', tex: 'S_{min} = \\dfrac{I_{cc}\\sqrt{t}}{k}',
        calc: (v) => (v.k ? (v.Icc * Math.sqrt(v.t)) / v.k : null), dec: 2 },
      { key: 'Iz', label: 'Curent admisibil corectat', unit: 'A', tex: 'I_z = I_t\\,C_a\\,C_g',
        calc: (v) => v.It * v.Ca * v.Cg, dec: 1 },
      { key: 'rezerva', label: 'Rezerva fata de sarcina', unit: 'A', tex: 'I_z - I_B',
        calc: (v, r) => r.Iz - v.IB, dec: 1 },
    ],
  },
  {
    id: 'scurtcircuit',
    family: 'comun',
    tier: 3,
    title: 'Curent de scurtcircuit (Icc)',
    subtitle: 'La bara, din transformator + contributie motoare',
    note: 'Pentru capacitatea de rupere a disjunctorului (Icu ≥ Icc). Contributia motoarelor ~ rotor blocat.',
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'Strafo', label: 'Putere transformator', unit: 'kVA', default: 630, step: 10, min: 1 },
      { key: 'uk', label: 'Tensiune de scurtcircuit', unit: '%', default: 6, step: 0.5, min: 0.1 },
      { key: 'Pmot', label: 'Putere motoare (suma)', unit: 'kW', default: 200, step: 10, min: 0 },
    ],
    results: [
      { key: 'Intr', label: 'Curent nominal trafo', unit: 'A', tex: 'I_n = \\dfrac{S\\cdot 1000}{\\sqrt{3}\\,U}',
        calc: (v) => (v.Strafo * 1000) / (SQRT3 * v.U), dec: 0 },
      { key: 'Icctr', label: 'Icc din transformator', unit: 'kA', tex: 'I_{cc} = \\dfrac{I_n}{u_k/100}',
        calc: (v, r) => (v.uk ? r.Intr / (v.uk / 100) / 1000 : null), dec: 2 },
      { key: 'Imot', label: 'Contributie motoare', unit: 'kA', tex: 'I_{mot} \\approx 6\\,I_{nM},\\; I_{nM}=\\dfrac{P_{mot}\\cdot 1000}{\\sqrt{3}\\,U\\cos\\varphi\\,\\eta}',
        calc: (v) => { const InM = (v.Pmot * 1000) / (SQRT3 * v.U * 0.8); return (6 * InM) / 1000 }, dec: 2 },
      { key: 'Icctot', label: 'Icc total la bara', unit: 'kA', tex: 'I_{cc,tot} = I_{cc,trafo}+I_{motoare}',
        calc: (v, r) => r.Icctr + r.Imot, dec: 2 },
    ],
  },
  {
    id: 'ieee519',
    family: 'comun',
    tier: 3,
    title: 'IEEE 519 — THD la racord (PCC)',
    subtitle: 'Limita TDD din raportul Isc/IL',
    note: 'Drive 6-puls ~30-40% THD, cu reactor ~30%. Daca depasirea > 0 → reactor/filtru/AFE.',
    fields: [
      { key: 'IccPCC', label: 'Curent scurtcircuit la PCC', unit: 'A', default: 17000, step: 500, min: 1 },
      { key: 'Iload', label: 'Curent sarcina max', unit: 'A', default: 200, step: 10, min: 1 },
      { key: 'THDest', label: 'THD curent estimat', unit: '%', default: 35, step: 1, min: 0 },
    ],
    results: [
      { key: 'ratio', label: 'Raport Isc/IL', unit: '', tex: 'I_{sc}/I_L',
        calc: (v) => (v.Iload ? v.IccPCC / v.Iload : null), dec: 0 },
      { key: 'TDD', label: 'Limita TDD admisa', unit: '%', tex: '\\text{IEEE 519 Tab.2}',
        calc: (v, r) => { const x = r.ratio; return x < 20 ? 5 : x < 50 ? 8 : x < 100 ? 12 : x < 1000 ? 15 : 20 }, dec: 0 },
      { key: 'depasire', label: 'Depasire fata de limita', unit: '%', tex: 'THD_{est} - TDD',
        calc: (v, r) => v.THDest - r.TDD, dec: 1 },
    ],
  },
  {
    id: 'rezonanta-cond',
    family: 'comun',
    tier: 3,
    title: 'Rezonanta cu baterie condensatoare',
    subtitle: 'Ordinul de rezonanta paralela',
    note: 'Daca h_rez ≈ 5 sau 7 → risc de ardere condensatoare. Solutie: reactor de detunare (p=7%, ~189 Hz).',
    fields: [
      { key: 'Ssc', label: 'Putere scurtcircuit', unit: 'MVA', default: 17, step: 0.5, min: 0.1 },
      { key: 'Qc', label: 'Putere baterie', unit: 'Mvar', default: 0.5, step: 0.05, min: 0.001 },
      { key: 'f1', label: 'Frecventa retea', unit: 'Hz', default: 50, step: 1, min: 1 },
    ],
    results: [
      { key: 'hrez', label: 'Ordin de rezonanta', unit: '', tex: 'h_{rez} = \\sqrt{S_{sc}/Q_c}',
        calc: (v) => (v.Qc ? Math.sqrt(v.Ssc / v.Qc) : null), dec: 2 },
      { key: 'frez', label: 'Frecventa de rezonanta', unit: 'Hz', tex: 'f_{rez} = h_{rez}\\,f_1',
        calc: (v, r) => r.hrez * v.f1, dec: 0 },
    ],
  },
  {
    id: 'transformator',
    family: 'transformator',
    tier: 2,
    title: 'Transformator — dimensionare',
    subtitle: 'Putere kVA, rezerva si raport trafo/motor pe tip de pornire',
    note: 'Marimea ceruta de SARCINA: $S_{tr} \\ge S_{sarc}\\cdot k_{rez}$. Marimea ceruta de PORNIRE (sa tii caderea de tensiune sub limita): $S_{tr} \\ge k_{por}\\,S_{motor}\\,u_k/\\Delta U_{max}$. Alegi cea mai mare. Factor pornire $k_{por}$ (×S motor): DOL ~6, stea-triunghi ~2-3, softstarter ~3, VFD ~1.',
    params: 'IEC 60076-1 (putere nominala) + IEC 61378-1 (transformatoare pentru convertizoare). La sarcini neliniare vezi factorul K.',
    fields: [
      { key: 'Psarc', label: 'Putere ceruta (suma)', unit: 'kW', default: 200, step: 10, min: 0 },
      { key: 'cosphi', label: 'Factor de putere sarcina', unit: '', default: 0.85, step: 0.01, min: 0.1 },
      { key: 'ku', label: 'Factor de simultaneitate', unit: '', default: 0.85, step: 0.05, min: 0.1 },
      { key: 'krez', label: 'Factor de rezerva', unit: '', default: 1.2, step: 0.05, min: 1 },
      { key: 'Pmot1', label: 'Cel mai mare motor', unit: 'kW', default: 55, step: 5, min: 0 },
      { key: 'kpor', label: 'Factor pornire (×S motor)', unit: '', default: 6, step: 0.5, min: 1 },
      { key: 'uk', label: 'Tensiune de scurtcircuit', unit: '%', default: 6, step: 0.5, min: 0.1 },
      { key: 'dUmax', label: 'Cadere de tensiune admisa', unit: '%', default: 10, step: 1, min: 1 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
    ],
    results: [
      { key: 'Ssarc', label: 'Putere aparenta sarcina', unit: 'kVA', tex: 'S_{sarc} = \\dfrac{P\\,k_u}{\\cos\\varphi}',
        calc: (v) => (v.cosphi ? (v.Psarc * v.ku) / v.cosphi : null), dec: 0 },
      { key: 'Strec', label: 'Trafo din sarcina (cu rezerva)', unit: 'kVA', tex: 'S_{tr,sarc} = S_{sarc}\\,k_{rez}',
        calc: (v, r) => (r.Ssarc != null ? r.Ssarc * v.krez : null), dec: 0 },
      { key: 'Spor', label: 'Trafo din conditia de pornire', unit: 'kVA', tex: 'S_{tr,por} = k_{por}\\dfrac{P_{mot}}{\\cos\\varphi}\\dfrac{u_k}{\\Delta U_{max}}',
        calc: (v) => (v.cosphi && v.dUmax ? v.kpor * (v.Pmot1 / v.cosphi) * (v.uk / v.dUmax) : null), dec: 0 },
      { key: 'Strafo', label: 'Putere trafo recomandata', unit: 'kVA', tex: 'S_{tr} = \\max(S_{tr,sarc},\\,S_{tr,por})',
        calc: (v, r) => Math.max(r.Strec || 0, r.Spor || 0), dec: 0 },
      { key: 'ratioTM', label: 'Raport trafo / sarcina', unit: '×', tex: 'S_{tr}/P',
        calc: (v, r) => (v.Psarc ? r.Strafo / v.Psarc : null), dec: 2 },
      { key: 'Intr', label: 'Curent nominal trafo', unit: 'A', tex: 'I_n = \\dfrac{S_{tr}\\cdot 1000}{\\sqrt{3}\\,U}',
        calc: (v, r) => (r.Strafo * 1000) / (SQRT3 * v.U), dec: 0 },
    ],
  },
  {
    id: 'trafo-grupa-conexiuni',
    family: 'transformator',
    tier: 2,
    title: 'Grupa de conexiuni (vector group)',
    subtitle: 'Defazaj primar-secundar, conexiuni, functionare in paralel',
    note: 'Litera mare = primar (D = triunghi, Y = stea), litera mica = secundar (d/y), n = neutru scos, cifra = indicele orar (×30° defazaj). Uzual la JT: $Dyn11$ (secundar in stea cu neutru, secundarul intarzie 330° = avans 30°). Functionare in PARALEL: aceeasi grupa orara, acelasi raport de transformare si $u_k$ apropiat (±10%).',
    params: 'IEC 60076-1 (marcarea bornelor & grupe de conexiuni). Dyn11 = standard pentru distributie JT.',
    fields: [
      { key: 'clock', label: 'Indice orar (0-11)', unit: '', default: 11, step: 1, min: 0 },
    ],
    results: [
      { key: 'defazaj', label: 'Intarziere secundar fata de primar', unit: '°', tex: '\\Delta\\varphi = \\text{ora}\\times 30°',
        calc: (v) => (v.clock % 12) * 30, dec: 0 },
    ],
  },
  {
    id: 'trafo-12pulse',
    family: 'transformator',
    tier: 3,
    title: 'Transformator cu dubla infasurare (12 pulsuri)',
    subtitle: 'Anularea armonicilor 5 si 7, THD redus',
    note: 'Doua secundare defazate 30° (ex. $Dy11 + Dd0$) alimenteaza doua punti de 6 pulsuri -> sistem de 12 pulsuri. Armonicile 5 si 7 (si 17, 19) se anuleaza reciproc; raman caracteristice $h = 12k \\pm 1$ (11, 13, 23, 25...). THD scade de la ~30% (6 pulsuri) la ~13-14% (model teoretic 1/h; in practica putin mai mic datorita comutatiei).',
    params: 'IEC 61378-1 (transformatoare pentru convertizoare) + IEC 61000-2-4 (niveluri compatibilitate in instalatii industriale). Anulare reala ~85-95% (dezechilibre de impedanta).',
    charts: [(v) => {
      const c = v.canc / 100
      const H = [5, 7, 11, 13, 17, 19, 23, 25]
      const A = { 5: 20, 7: 14.29, 11: 9.09, 13: 7.69, 17: 5.88, 19: 5.26, 23: 4.35, 25: 4.0 }
      const cancel = (h) => h === 5 || h === 7 || h === 17 || h === 19
      return {
        xLabel: 'Ordin armonica h', yLabel: 'Amplitudine [% din I1]',
        series: [
          { label: '6 pulsuri', color: COL.c, dash: true, points: H.map((h) => ({ x: h, y: A[h] })) },
          { label: '12 pulsuri', color: COL.a, points: H.map((h) => ({ x: h, y: cancel(h) ? A[h] * (1 - c) : A[h] })) },
        ],
      }
    }],
    fields: [
      { key: 'canc', label: 'Grad de anulare 5/7', unit: '%', default: 90, step: 1, min: 0 },
    ],
    results: [
      { key: 'THD6', label: 'THD curent 6 pulsuri (referinta)', unit: '%', tex: 'THD_6 = \\sqrt{\\textstyle\\sum (I_h/I_1)^2}',
        calc: () => Math.sqrt([20, 14.29, 9.09, 7.69, 5.88, 5.26, 4.35, 4.0].reduce((s, a) => s + a * a, 0)), dec: 1 },
      { key: 'THD12', label: 'THD curent 12 pulsuri', unit: '%', tex: 'THD_{12}\\ (5,7,17,19\\text{ anulate})',
        calc: (v) => {
          const c = v.canc / 100
          const cancelled = [20, 14.29, 5.88, 5.26], remain = [9.09, 7.69, 4.35, 4.0]
          let s = 0
          for (const a of cancelled) s += (a * (1 - c)) ** 2
          for (const a of remain) s += a * a
          return Math.sqrt(s)
        }, dec: 1 },
      { key: 'reducere', label: 'Reducere THD', unit: '%', tex: '\\left(1 - THD_{12}/THD_6\\right)\\cdot 100',
        calc: (v, r) => (r.THD6 ? (1 - r.THD12 / r.THD6) * 100 : null), dec: 0 },
    ],
  },
  {
    id: 'trafo-scurtcircuit',
    family: 'transformator',
    tier: 3,
    title: 'Scurtcircuit la transformator',
    subtitle: 'Icc secundar, curent de varf, solicitare termica',
    note: 'Curentul de scurtcircuit secundar e limitat de $u_k$: $I_{cc} = I_n/u_k$. Varful dinamic $i_p = \\kappa\\sqrt{2}\\,I_{cc}$ ($\\kappa \\approx 1.8$ la JT) solicita mecanic barele; energia $I^2t$ (in $kA^2 s$) solicita termic conductoarele — formula simpla $I_{cc}^2 t_k$ e conservatoare (metoda exacta IEC 60909: $I_{th}=I_{cc}\\sqrt{m+n}$). Inrush la cuplare ~8-12×$I_n$. Disjunctor: $I_{cu} \\ge I_{cc}$.',
    params: 'IEC 60909-0 (curenti de scurtcircuit) + IEC 60076-5 (tinuta la scurtcircuit).',
    fields: [
      { key: 'Strafo', label: 'Putere transformator', unit: 'kVA', default: 630, step: 10, min: 1 },
      { key: 'uk', label: 'Tensiune de scurtcircuit', unit: '%', default: 6, step: 0.5, min: 0.1 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'kappa', label: 'Factor de varf κ', unit: '', default: 1.8, step: 0.05, min: 1 },
      { key: 'tk', label: 'Durata scurtcircuit', unit: 's', default: 1, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'Intr', label: 'Curent nominal trafo', unit: 'A', tex: 'I_n = \\dfrac{S\\cdot 1000}{\\sqrt{3}\\,U}',
        calc: (v) => (v.Strafo * 1000) / (SQRT3 * v.U), dec: 0 },
      { key: 'Iccsec', label: 'Icc secundar (permanent)', unit: 'kA', tex: 'I_{cc} = \\dfrac{I_n}{u_k/100}',
        calc: (v, r) => (v.uk ? r.Intr / (v.uk / 100) / 1000 : null), dec: 1 },
      { key: 'ipk', label: 'Curent de varf dinamic', unit: 'kA', tex: 'i_p = \\kappa\\sqrt{2}\\,I_{cc}',
        calc: (v, r) => (r.Iccsec != null ? v.kappa * Math.SQRT2 * r.Iccsec : null), dec: 1 },
      { key: 'I2t', label: 'Energie termica (I²t)', unit: 'kA²s', tex: 'I^2t = I_{cc}^2\\,t_k',
        calc: (v, r) => (r.Iccsec != null ? r.Iccsec ** 2 * v.tk : null), dec: 1 },
      { key: 'Iinrush', label: 'Curent inrush (varf)', unit: 'A', tex: 'i_{inrush} \\approx 10\\,I_n',
        calc: (v, r) => 10 * r.Intr, dec: 0 },
    ],
  },
  {
    id: 'incarcare-trafo',
    family: 'transformator',
    tier: 3,
    title: 'Incarcarea transformatorului',
    subtitle: 'Suprasarcina vs temperatura, hot-spot, imbatranire izolatie',
    note: 'Punctul cald (hot-spot) $\\theta_h = \\theta_a + \\Delta\\theta_o + \\Delta\\theta_h$. Rata de imbatranire relativa $V = 2^{(\\theta_h-98)/6}$ (hartie normala, referinta 98°C): $V=1$ la 98°C, se dubleaza la fiecare +6°C. Limite hot-spot: 98°C durata normala, 120°C sarcina ciclica, 140°C avarie.',
    params: 'IEC 60076-7 (ghid de incarcare trafo in ulei). x=0,8 (ulei), y=1,6 (infasurare) la ONAN.',
    fields: [
      { key: 'tha', label: 'Temperatura ambianta', unit: '°C', default: 40, step: 1, min: -30 },
      { key: 'K', label: 'Factor de incarcare (S/Sn)', unit: 'pu', default: 1.0, step: 0.05, min: 0 },
      { key: 'tor', label: 'Cresterea uleiului la nominal', unit: 'K', default: 55, step: 1, min: 1 },
      { key: 'gr', label: 'Gradient hot-spot la nominal', unit: 'K', default: 21, step: 1, min: 1 },
      { key: 'R', label: 'Raport pierderi (sc/gol)', unit: '', default: 6, step: 0.5, min: 1 },
    ],
    results: [
      { key: 'dto', label: 'Cresterea uleiului la sarcina', unit: 'K', tex: '\\Delta\\theta_o = \\Delta\\theta_{o,r}\\left(\\dfrac{1+R K^2}{1+R}\\right)^{0.8}',
        calc: (v) => v.tor * ((1 + v.R * v.K ** 2) / (1 + v.R)) ** 0.8, dec: 1 },
      { key: 'dth', label: 'Gradient hot-spot la sarcina', unit: 'K', tex: '\\Delta\\theta_h = g_r\\,K^{1.6}',
        calc: (v) => v.gr * v.K ** 1.6, dec: 1 },
      { key: 'thh', label: 'Temperatura hot-spot', unit: '°C', tex: '\\theta_h = \\theta_a + \\Delta\\theta_o + \\Delta\\theta_h',
        calc: (v, r) => v.tha + r.dto + r.dth, dec: 1 },
      { key: 'V', label: 'Rata de imbatranire relativa', unit: '×', tex: 'V = 2^{(\\theta_h-98)/6}',
        calc: (v, r) => 2 ** ((r.thh - 98) / 6), dec: 2 },
    ],
  },
  {
    id: 'ploturi',
    family: 'transformator',
    tier: 2,
    title: 'Reglaj de tensiune (ploturi / tap changer)',
    subtitle: 'Domeniu de reglaj, tensiune per plot',
    note: 'Ploturi pe infasurarea de IT: compenseaza variatia tensiunii retelei. Off-load (fara sarcina, uzual $\\pm2\\times2{,}5\\%$) sau OLTC (sub sarcina). Plotul nominal = pozitia centrala.',
    params: 'IEC 60076-21 (regulatoare de tensiune pas cu pas) + IEC 60076-1.',
    fields: [
      { key: 'Un', label: 'Tensiune nominala', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'pas', label: 'Pas de reglaj per plot', unit: '%', default: 2.5, step: 0.5, min: 0.1 },
      { key: 'ntr', label: 'Numar plots (fiecare parte)', unit: '', default: 2, step: 1, min: 1 },
    ],
    results: [
      { key: 'Umax', label: 'Tensiune plot maxim', unit: 'V', tex: 'U_{max} = U_n(1 + n\\cdot pas)',
        calc: (v) => v.Un * (1 + (v.ntr * v.pas) / 100), dec: 0 },
      { key: 'Umin', label: 'Tensiune plot minim', unit: 'V', tex: 'U_{min} = U_n(1 - n\\cdot pas)',
        calc: (v) => v.Un * (1 - (v.ntr * v.pas) / 100), dec: 0 },
      { key: 'Upas', label: 'Tensiune per plot', unit: 'V', tex: 'U_{pas} = U_n\\cdot pas',
        calc: (v) => (v.Un * v.pas) / 100, dec: 1 },
      { key: 'dom', label: 'Domeniu de reglaj', unit: '%', tex: '\\pm n\\cdot pas',
        calc: (v) => v.ntr * v.pas, dec: 1 },
    ],
  },
  {
    id: 'sil-pl',
    family: 'comun',
    tier: 3,
    title: 'Siguranta functionala (SIL / PL)',
    subtitle: 'Nivel de integritate din PFH; mapare SIL-PL-Categorie',
    note: 'PFH = probabilitatea unui defect periculos pe ora. Mapare orientativa: $10^{-6}..10^{-5}$ = SIL1 / PLb-c; $10^{-7}..10^{-6}$ = SIL2 / PLd; $10^{-8}..10^{-7}$ = SIL3 / PLe. STO la drive este uzual **SIL2 / PLd / Categoria 3**. PL depinde si de Categorie (B/1/2/3/4), MTTFd si DC (ISO 13849-1).',
    params: 'IEC 62061 (SIL la masini) + ISO 13849-1 (PL) + IEC 61800-5-2 (STO/SS1 la drive).',
    fields: [
      { key: 'PFHd', label: 'PFH (defect periculos / ora)', unit: '1/h', default: 1e-7, step: 1e-8, min: 0 },
    ],
    results: [
      { key: 'SIL', label: 'Nivel SIL (1-3)', unit: '', tex: '\\text{din PFH (IEC 62061)}',
        calc: (v) => { const p = v.PFHd; if (p < 1e-7) return 3; if (p < 1e-6) return 2; if (p < 1e-5) return 1; return 0 }, dec: 0 },
      { key: 'PLidx', label: 'Nivel PL (a=1 .. e=5)', unit: '', tex: '\\text{din PFH (ISO 13849-1)}',
        calc: (v) => { const p = v.PFHd; if (p < 1e-7) return 5; if (p < 1e-6) return 4; if (p < 3e-6) return 3; if (p < 1e-5) return 2; return 1 }, dec: 0 },
    ],
  },
  {
    id: 'vibratii',
    family: 'comun',
    tier: 3,
    title: 'Vibratii mecanice (severitate)',
    subtitle: 'Limite de viteza (mm/s RMS) pe inaltimea de ax',
    note: 'Severitatea = viteza eficace (RMS) a vibratiei. Grad A = standard, Grad B = special (cuplaje de precizie, masini-unelte). Masoara la turatie nominala, pe lagar/carcasa, in 3 directii. Limite (suspensie libera): H 56-132 → A 1,6 / B 0,7; 132-280 → A 2,2 / B 1,1; >280 → A 3,5 / B 1,8 mm/s.',
    params: 'IEC 60034-14 (vibratii mecanice — masuri si limite). ISO 20816 pe sistemul complet montat.',
    fields: [
      { key: 'H', label: 'Inaltime de ax', unit: 'mm', default: 132, step: 1, min: 56 },
      { key: 'vmas', label: 'Viteza masurata (RMS)', unit: 'mm/s', default: 1.5, step: 0.1, min: 0 },
    ],
    results: [
      { key: 'limA', label: 'Limita grad A', unit: 'mm/s', tex: '\\text{IEC 60034-14}',
        calc: (v) => (v.H <= 132 ? 1.6 : v.H <= 280 ? 2.2 : 3.5), dec: 1 },
      { key: 'limB', label: 'Limita grad B', unit: 'mm/s', tex: '\\text{IEC 60034-14}',
        calc: (v) => (v.H <= 132 ? 0.7 : v.H <= 280 ? 1.1 : 1.8), dec: 1 },
      { key: 'marjaA', label: 'Marja fata de grad A', unit: 'mm/s', tex: 'lim_A - v_{mas}',
        calc: (v, r) => r.limA - v.vmas, dec: 1 },
    ],
  },
  {
    id: 'grade-ip',
    family: 'comun',
    tier: 2,
    title: 'Grade de protectie (cod IP)',
    subtitle: 'IP XY — protectie la corpuri solide / apa',
    note: 'IP = Ingress Protection. Prima cifra (solide): 0 fara, 1 ≥50mm, 2 ≥12,5mm (deget), 3 ≥2,5mm, 4 ≥1mm, 5 praf partial, 6 etans la praf. A doua cifra (apa): 0 fara, 1 picaturi vertical, 2 picaturi 15°, 3 ploaie 60°, 4 stropi din orice directie, 5 jet, 6 jet puternic, 7 imersie 1m, 8 imersie continua. Uzual motoare: IP54/IP55 (interior industrial), IP23 (deschis racit), IP66 (exterior / spalare cu jet).',
    params: 'IEC 60034-5 (grade de protectie IP pentru masini electrice rotative).',
    fields: [],
    results: [],
  },
  {
    id: 'dip-pornire',
    family: 'comun',
    tier: 3,
    title: 'Cadere de tensiune la pornire',
    subtitle: 'Dip pe bara la pornirea motorului',
    note: 'Limita uzuala ΔU ≤ 10-15% (IEEE 141). Peste → softstarter / VFD / stea-triunghi.',
    fields: [
      { key: 'Iporn', label: 'Curent de pornire', unit: 'A', default: 168, step: 5, min: 0 },
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'Sccbus', label: 'Putere scurtcircuit bara', unit: 'kVA', default: 2000, step: 100, min: 1 },
    ],
    results: [
      { key: 'Sporn', label: 'Putere aparenta pornire', unit: 'kVA', tex: 'S_{p} = \\sqrt{3}\\,U I_{p}/1000',
        calc: (v) => (SQRT3 * v.U * v.Iporn) / 1000, dec: 1 },
      { key: 'dU', label: 'Cadere de tensiune', unit: '%', tex: '\\Delta U = \\dfrac{S_p}{S_p+S_{cc}}\\cdot 100',
        calc: (v, r) => (r.Sporn / (r.Sporn + v.Sccbus)) * 100, dec: 2 },
    ],
  },

  {
    id: 'protectie-motor',
    family: 'comun',
    tier: 3,
    title: 'Protectie motor (releu termic)',
    subtitle: 'Reglaj Ie, clasa de declansare, timp la pornire',
    note: 'Releu/protectie termica IEC 60947-4-1. Clasa (10/20/30) = timpul MAXIM de declansare la 7,2·Ie din stare CALDA (banda, nu valoare exacta): clasa 10 → 4-10 s, clasa 20 → 6-20 s, clasa 30 → 9-30 s. Curba afisata e model $I^2t$ orientativ ($t\\propto 1/((I/I_e)^2-1)$), valid pt curenti mari (pornire); din rece declansarea e mai lenta. Regleaza $I_e\\approx I_n$ (sau curentul de serviciu). La pornire, timpul de declansare la curentul de pornire trebuie sa depaseasca timpul de pornire (rezerva > 1), altfel declanseaza intempestiv.',
    params: 'IEC 60947-4-1 (relee de suprasarcina, clase de declansare); model I^2t orientativ.',
    fields: [
      { key: 'In', label: 'Curent nominal motor', unit: 'A', default: 28, step: 1, min: 0.1 },
      { key: 'Ie', label: 'Reglaj releu Ie', unit: 'A', default: 28, step: 1, min: 0.1 },
      { key: 'kstart', label: 'Curent de pornire', unit: 'xIn', default: 6, step: 0.5, min: 1 },
      { key: 'tstart', label: 'Timp de pornire', unit: 's', default: 5, step: 0.5, min: 0.1 },
      { key: 'clasa', label: 'Clasa de declansare (10/20/30)', unit: '', default: 10, step: 10, min: 5 },
    ],
    charts: [(v) => ({
      xLabel: 'I / I_e', yLabel: 'Timp de declansare [s]',
      series: [10, 20, 30].map((cl, i) => ({ label: 'Clasa ' + cl, color: [COL.a, COL.b, COL.c][i], points: curve(2, 10, (x) => (cl * 50.84) / (x * x - 1)) })),
    })],
    results: [
      { key: 'ttrip_start', label: 'Timp declansare la pornire', unit: 's', tex: 't = \\dfrac{\\mathrm{clasa}\\cdot 50{,}84}{(k_p I_n/I_e)^2-1}',
        calc: (v) => { const x = (v.kstart * v.In) / v.Ie; return x > 1 ? (v.clasa * 50.84) / (x * x - 1) : null }, dec: 1 },
      { key: 'rezerva', label: 'Rezerva la pornire (>1 OK)', unit: '', tex: 't_{trip}/t_{pornire}',
        calc: (v, r) => (r.ttrip_start && v.tstart > 0 ? r.ttrip_start / v.tstart : null), dec: 2 },
      { key: 'Tpmax', label: 'Timp max la 7.2·Ie (clasa, cald)', unit: 's', tex: 'T_p \\le \\mathrm{clasa}',
        calc: (v) => v.clasa, dec: 0 },
    ],
  },
  {
    id: 'pe-defect',
    family: 'comun',
    tier: 3,
    title: 'Conductor PE & curent de defect',
    subtitle: 'Sectiune PE, bucla de defect, timp de deconectare',
    note: 'IEC 60364-4-41 (protectie la soc) + 60364-5-54 (conductor PE). Conditia de deconectare automata: $Z_s\\cdot I_a \\le U_0$ — impedanta buclei de defect ori curentul de declansare al protectiei (in timpul cerut) sub tensiunea fata de pamant. Timp de deconectare cerut (TN, 230 V): 0,4 s pt circuite finale ≤32 A, 5 s pt distributie. Sectiune PE (acelasi material ca faza): $S\\le16\\to S_{PE}=S$; $16<S\\le35\\to16$; $S>35\\to S/2$. Curentul de defect prezumat $I_{def}=U_0/Z_s$ (modul de impedanta).',
    params: 'IEC 60364-4-41 / 60364-5-54 (instalatii JT, schema TN); NP I7-2011.',
    fields: [
      { key: 'U0', label: 'Tensiune faza-pamant', unit: 'V', default: 230, step: 5, min: 1 },
      { key: 'Zs', label: 'Impedanta buclei de defect', unit: 'Ω', default: 0.8, step: 0.05, min: 0.01 },
      { key: 'Ia', label: 'Curent de declansare protectie', unit: 'A', default: 250, step: 10, min: 1 },
      { key: 'Sfaza', label: 'Sectiune conductor faza', unit: 'mm²', default: 16, step: 1, min: 1 },
    ],
    results: [
      { key: 'Idefect', label: 'Curent de defect prezumat', unit: 'A', tex: 'I_{def} = U_0/Z_s',
        calc: (v) => v.U0 / v.Zs, dec: 0 },
      { key: 'Zsmax', label: 'Impedanta max admisa a buclei', unit: 'Ω', tex: 'Z_{s,max} = U_0/I_a',
        calc: (v) => v.U0 / v.Ia, dec: 3 },
      { key: 'SPE', label: 'Sectiune conductor de protectie', unit: 'mm²', tex: 'S_{PE}: S{\\le}16{:}S,\\ 16{<}S{\\le}35{:}16,\\ S{>}35{:}S/2',
        calc: (v) => (v.Sfaza <= 16 ? v.Sfaza : v.Sfaza <= 35 ? 16 : v.Sfaza / 2), dec: 1 },
      { key: 'margin', label: 'Marja deconectare (>=1 OK)', unit: '', tex: 'Z_{s,max}/Z_s',
        calc: (v, r) => (v.Zs > 0 ? r.Zsmax / v.Zs : null), dec: 2 },
    ],
  },
  {
    id: 'lcc',
    family: 'comun',
    tier: 3,
    title: 'Cost pe ciclu de viata (LCC)',
    subtitle: 'Capital + energie actualizata; payback A vs B',
    note: 'Cost pe ciclu de viata = capital (CAPEX) + costul energiei actualizat pe $N$ ani. Factor de actualizare al anuitatii $PV_f=(1-(1+r)^{-n})/r$ (la $r=0$ → $n$). Compara doua solutii: A (referinta, ex motor IE2 / vana) vs B (ex IE3-IE4 / VFD). Puterea utila la ax = $P\\cdot incarc$; impartirea la randament da puterea absorbita din retea (de aceea randamentul mai mare scade consumul). Payback simplu (neactualizat) = diferenta de capital / economia anuala de operare; nu se afiseaza daca B nu se justifica.',
    params: 'Analiza LCC (capital + energie actualizata); payback simplu neactualizat.',
    fields: [
      { key: 'P', label: 'Putere', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'ore', label: 'Ore de functionare', unit: 'h/an', default: 4000, step: 100, min: 0 },
      { key: 'incarc', label: 'Incarcare medie', unit: '%', default: 80, step: 5, min: 0 },
      { key: 'etaA', label: 'Randament solutia A', unit: '%', default: 88, step: 0.5, min: 1 },
      { key: 'etaB', label: 'Randament solutia B', unit: '%', default: 92, step: 0.5, min: 1 },
      { key: 'pret', label: 'Pret energie', unit: 'lei/kWh', default: 0.8, step: 0.05, min: 0 },
      { key: 'capexA', label: 'Cost initial A (CAPEX)', unit: 'lei', default: 5000, step: 500, min: 0 },
      { key: 'capexB', label: 'Cost initial B (CAPEX)', unit: 'lei', default: 12000, step: 500, min: 0 },
      { key: 'ani', label: 'Durata de analiza', unit: 'ani', default: 15, step: 1, min: 1 },
      { key: 'rata', label: 'Rata de actualizare', unit: '%', default: 5, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'costA', label: 'Cost energie/an — A', unit: 'lei/an', tex: '\\tfrac{P\\,incarc}{\\eta_A}\\,ore\\cdot pret',
        calc: (v) => ((v.P * v.incarc / 100) / (v.etaA / 100)) * v.ore * v.pret, dec: 0 },
      { key: 'costB', label: 'Cost energie/an — B', unit: 'lei/an', tex: '\\tfrac{P\\,incarc}{\\eta_B}\\,ore\\cdot pret',
        calc: (v) => ((v.P * v.incarc / 100) / (v.etaB / 100)) * v.ore * v.pret, dec: 0 },
      { key: 'LCCA', label: 'LCC solutia A', unit: 'lei', tex: '\\mathrm{CAPEX}_A + cost_A\\,PV_f',
        calc: (v, r) => { const rr = v.rata / 100; const pv = rr > 0 ? (1 - Math.pow(1 + rr, -v.ani)) / rr : v.ani; return v.capexA + r.costA * pv }, dec: 0 },
      { key: 'LCCB', label: 'LCC solutia B', unit: 'lei', tex: '\\mathrm{CAPEX}_B + cost_B\\,PV_f',
        calc: (v, r) => { const rr = v.rata / 100; const pv = rr > 0 ? (1 - Math.pow(1 + rr, -v.ani)) / rr : v.ani; return v.capexB + r.costB * pv }, dec: 0 },
      { key: 'economie', label: 'Economie pe viata (A − B)', unit: 'lei', tex: '\\mathrm{LCC}_A - \\mathrm{LCC}_B',
        calc: (v, r) => r.LCCA - r.LCCB, dec: 0 },
      { key: 'payback', label: 'Payback simplu B vs A', unit: 'ani', tex: '\\dfrac{\\mathrm{CAPEX}_B-\\mathrm{CAPEX}_A}{cost_A-cost_B}',
        calc: (v, r) => { const dcap = v.capexB - v.capexA; const dcost = r.costA - r.costB; return (dcap > 0 && dcost > 0) ? dcap / dcost : null }, dec: 1 },
    ],
  },
  {
    id: 'cuplaj',
    family: 'comun',
    tier: 3,
    title: 'Dimensionare cuplaj + factor de serviciu',
    subtitle: 'Cuplu de dimensionare si de varf',
    note: 'Cuplu nominal $M_n=9550\\,P/n$ (P in kW, n in rpm). Cuplul de dimensionare al cuplajului = $M_n\\cdot SF$ (factor de serviciu: sarcina uniforma 1,0-1,25; soc moderat 1,5-1,75; soc greu ≥2,0). Cuplul de varf = $M_n\\cdot k_{varf}$ (pornire/soc; din fisa motorului sau limita de cuplu a VFD ~1,5-2; la DOL cuplul tranzitoriu poate depasi). Alege cuplaj cu $T_n\\ge M_{dim}$ si $T_{max}\\ge M_{varf}$. $SF$ si $k_{varf}$ NU se cumuleaza.',
    params: 'Dimensionare cuplaj dupa factor de serviciu (uzanta producatori: KTR/Rexnord etc.).',
    fields: [
      { key: 'P', label: 'Putere', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 1450, step: 10, min: 1 },
      { key: 'SF', label: 'Factor de serviciu', unit: '', default: 1.5, step: 0.05, min: 1 },
      { key: 'kpeak', label: 'Cuplu de varf', unit: 'xMn', default: 2.5, step: 0.1, min: 1 },
    ],
    results: [
      { key: 'Mn', label: 'Cuplu nominal', unit: 'Nm', tex: 'M_n = 9550\\,P/n',
        calc: (v) => (9550 * v.P) / v.n, dec: 1 },
      { key: 'Mdim', label: 'Cuplu de dimensionare (×SF)', unit: 'Nm', tex: 'M_{dim} = M_n\\cdot SF',
        calc: (v, r) => r.Mn * v.SF, dec: 1 },
      { key: 'Mvarf', label: 'Cuplu de varf', unit: 'Nm', tex: 'M_{varf} = M_n\\cdot k_{varf}',
        calc: (v, r) => r.Mn * v.kpeak, dec: 1 },
    ],
  },
  // ===================================== P4: VFD & ELECTRONICA DE PUTERE
  {
    id: 'moduri-control',
    family: 'comun',
    tier: 2,
    title: 'Moduri de control (scalar / vector / FOC / DTC)',
    subtitle: 'Ce mod alegi: acuratete, cuplu la 0, banda',
    note: 'Scalar (V/f): acuratete turatie ±1-3% (±0,5% cu compensare de alunecare), fara cuplu controlat la 0 turatii (doar cuplu de smulgere din boost), fara feedback, simplu, ieftin, mai multe motoare pe un drive → pompe, ventilatoare. · Vector sensorless (SVC): ±0,1-0,5%, cuplu bun la turatie joasa dar limitat exact la 0 turatii sustinut (estimatorul de flux pierde observabilitatea la frecventa statorica ~0), fara encoder → cuplu constant, dinamica medie. · FOC cu encoder (control orientat pe camp, regleaza $i_d/i_q$): ±0,01% din nominal, cuplu PLIN la 0 turatii, banda mare → servo, pozitionare, ridicare, extrudere. · DTC (Direct Torque Control, ABB): control direct al cuplului si fluxului prin comparatoare cu histereza + tabela de comutatie (frecventa de comutatie variabila, fara modulator PWM clasic), raspuns de cuplu ~1-2 ms, ±0,1-0,5% sensorless (mai bun cu encoder) → laminoare, macarale, sarcini cu socuri. · Regula: pompe/vent → scalar; cuplu constant fara encoder → vector sensorless; cuplu la 0 turatii / precizie → FOC cu encoder; raspuns de cuplu foarte rapid → DTC.',
    params: 'Cifre orientative de catalog (ABB/Siemens); acuratetea = % din turatia nominala.',
    fields: [],
    results: [],
  },
  {
    id: 'control-vf',
    family: 'comun',
    tier: 3,
    title: 'Control V/f (scalar)',
    subtitle: 'Curba V/f, boost IR, compensare alunecare',
    note: 'Scalar V/f: tensiunea creste cu frecventa pastrand fluxul ~ constant ($U/f$ = const). V/f liniar pt cuplu constant; V/f patratic pt pompe/ventilatoare ($M\\sim n^2$). Boost-ul (IR comp) ridica tensiunea la frecvente joase ca sa compenseze caderea pe $R_s$ si sa dea cuplu de pornire. La $f$ mic, fluxul aproximativ poate depasi 100% (supraexcitare → risc de saturatie/supracurent). Compensarea de alunecare adauga $\\Delta f$ la referinta ca sa tina turatia sub sarcina.',
    params: 'V/f scalar (ABB/Siemens/Danfoss); flux aproximativ neglijeaza caderea IR.',
    fields: [
      { key: 'Un', label: 'Tensiune nominala motor', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'fn', label: 'Frecventa nominala (de baza)', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'fop', label: 'Frecventa de lucru', unit: 'Hz', default: 25, step: 1, min: 0.5 },
      { key: 'boost', label: 'Boost de tensiune la 0 Hz (IR)', unit: '%', default: 5, step: 0.5, min: 0, max: 30 },
      { key: 'tip', label: 'Caracteristica (0=liniar, 1=patratic)', unit: '', default: 0, step: 1, min: 0, max: 1 },
      { key: 'sn', label: 'Alunecare nominala', unit: '%', default: 3, step: 0.5, min: 0 },
      { key: 'Mload', label: 'Cuplu de sarcina', unit: '%', default: 100, step: 5, min: 0 },
    ],
    charts: [(v) => { const Ub = (v.boost / 100) * v.Un; return {
      xLabel: 'Frecventa [Hz]', yLabel: 'Tensiune [V]',
      series: [
        { label: 'V/f liniar', color: COL.a, points: curve(0, v.fn, (f) => Ub + (v.Un - Ub) * (f / v.fn)) },
        { label: 'V/f patratic', color: COL.b, points: curve(0, v.fn, (f) => Ub + (v.Un - Ub) * (f / v.fn) ** 2) },
      ],
    }; }],
    results: [
      { key: 'Uf', label: 'Tensiune la frecventa de lucru', unit: 'V', tex: 'U(f) = U_b + (U_n - U_b)(f/f_n)^{p}',
        calc: (v) => { const Ub = (v.boost / 100) * v.Un; const p = v.tip >= 1 ? 2 : 1; return Ub + (v.Un - Ub) * Math.pow(v.fop / v.fn, p) }, dec: 1 },
      { key: 'VfRatio', label: 'Raport V/f', unit: 'V/Hz', tex: 'U(f)/f',
        calc: (v, r) => (v.fop > 0 ? r.Uf / v.fop : null), dec: 2 },
      { key: 'flux', label: 'Flux relativ (aprox, fara IR)', unit: '%', tex: '\\dfrac{U(f)/f}{U_n/f_n}\\cdot100',
        calc: (v, r) => (v.fop > 0 ? ((r.Uf / v.fop) / (v.Un / v.fn)) * 100 : null), dec: 0 },
      { key: 'dfslip', label: 'Compensare alunecare (Δf)', unit: 'Hz', tex: '\\Delta f = s_n f_n (M/M_n)',
        calc: (v) => (v.sn / 100) * v.fn * (v.Mload / 100), dec: 2 },
    ],
  },
  {
    id: 'modulatie-busdc',
    family: 'comun',
    tier: 3,
    title: 'Modulatie & utilizare bus DC',
    subtitle: 'Tensiune max de iesire, indice de modulatie, rezerva',
    note: 'Redresor cu diode (6 pulsuri): $U_{dc}\\approx1{,}35\\,U_{retea}$ (la gol; sub sarcina ~1,30-1,32). Cu SVPWM (injectie de armonica 3) tensiunea max de iesire linie-linie RMS = $U_{dc}/\\sqrt2\\approx0{,}707\\,U_{dc}$ (cu PWM sinusoidal pur doar $0{,}612\\,U_{dc}$). Daca $U_{out,max}<U_n$ → indice de modulatie $m>1$ (supramodulatie) si motorul intra in slabire de camp deja sub frecventa nominala. In plus se mai pierd 2-5% pe caderi IGBT / timp mort.',
    params: 'SVPWM in regiune liniara; Udc ideal redresor diode 6 pulsuri = 1,35*Uretea.',
    fields: [
      { key: 'Uretea', label: 'Tensiune retea (alimentare)', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'Un', label: 'Tensiune nominala motor', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'fn', label: 'Frecventa nominala motor', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'kdc', label: 'Factor redresor (1.35 diode, ~1.45 AFE)', unit: '', default: 1.35, step: 0.01, min: 1 },
    ],
    results: [
      { key: 'Udc', label: 'Tensiune bus DC', unit: 'V', tex: 'U_{dc} = k\\,U_{retea}',
        calc: (v) => v.kdc * v.Uretea, dec: 0 },
      { key: 'Uoutmax', label: 'Tensiune max iesire (SVPWM, L-L RMS)', unit: 'V', tex: 'U_{out,max} = U_{dc}/\\sqrt2',
        calc: (v, r) => r.Udc / Math.SQRT2, dec: 0 },
      { key: 'm', label: 'Indice modulatie pt Un (>1 = deficit)', unit: '', tex: 'm = U_n/U_{out,max}',
        calc: (v, r) => v.Un / r.Uoutmax, dec: 3 },
      { key: 'rezerva', label: 'Rezerva de tensiune', unit: '%', tex: '\\dfrac{U_{out,max}-U_n}{U_n}\\cdot100',
        calc: (v, r) => ((r.Uoutmax - v.Un) / v.Un) * 100, dec: 1 },
      { key: 'ffw', label: 'Debut slabire de camp', unit: 'Hz', tex: 'f_{fw} = f_n\\,U_{out,max}/U_n',
        calc: (v, r) => (v.fn * r.Uoutmax) / v.Un, dec: 1 },
    ],
  },
  {
    id: 'ripple-pwm',
    family: 'comun',
    tier: 3,
    title: 'Ripple de curent PWM',
    subtitle: 'Ondulatia de curent din comutatie',
    note: 'Ondulatia (varf-varf) de curent introdusa de PWM, pe inductanta de scapari a motorului. Aproximare medie (duty 50%): $\\Delta I_{pp}\\approx U_{dc}/(8 L_\\sigma f_{sw})$; varful real unipolar poate ajunge la $U_{dc}/(4 L_\\sigma f_{sw})$. Ripple mare → pierderi suplimentare, incalzire si zgomot acustic → creste $f_{sw}$ sau adauga reactor de motor (du/dt). ATENTIE: $L_\\sigma$ = inductanta de SCAPARI pe faza ($L_{\\sigma s}+L_{\\sigma r}$), NU inductanta totala/sincrona (care include magnetizarea, mult mai mare) — pt ~15 kW $L_\\sigma$ ~ 2-5 mH.',
    params: 'Aproximare ripple PWM; L = inductanta de scapari pe faza (nu cea totala).',
    fields: [
      { key: 'Udc', label: 'Tensiune bus DC', unit: 'V', default: 540, step: 10, min: 1 },
      { key: 'L', label: 'Inductanta de scapari pe faza (Lσ)', unit: 'mH', default: 3, step: 0.5, min: 0.1 },
      { key: 'fsw', label: 'Frecventa de comutatie', unit: 'kHz', default: 4, step: 0.5, min: 0.5 },
      { key: 'In', label: 'Curent nominal motor', unit: 'A', default: 28, step: 1, min: 0 },
    ],
    charts: [(v) => ({
      xLabel: 'f_{sw} [kHz]', yLabel: 'Ripple varf-varf [A]',
      series: [{ label: 'ΔIpp (mediu)', color: COL.a, points: curve(1, 16, (fs) => v.Udc / (8 * v.L * fs)) }],
    })],
    results: [
      { key: 'dIpp', label: 'Ripple curent (varf-varf, mediu)', unit: 'A', tex: '\\Delta I_{pp}\\approx\\dfrac{U_{dc}}{8 L_\\sigma f_{sw}}',
        calc: (v) => v.Udc / (8 * v.L * v.fsw), dec: 2 },
      { key: 'dImax', label: 'Ripple varf (worst-case unipolar)', unit: 'A', tex: '\\Delta I_{max}\\approx\\dfrac{U_{dc}}{4 L_\\sigma f_{sw}}',
        calc: (v) => v.Udc / (4 * v.L * v.fsw), dec: 2 },
      { key: 'dIpct', label: 'Ripple din In', unit: '%', tex: '\\Delta I_{pp}/I_n\\cdot100',
        calc: (v, r) => (v.In > 0 ? (r.dIpp / v.In) * 100 : null), dec: 1 },
    ],
  },
  {
    id: 'comutatie',
    family: 'comun',
    tier: 3,
    title: 'Pierderi convertizor vs frecventa comutatie',
    subtitle: 'Pierderi de comutatie + conductie',
    note: 'Esw din datasheet IGBT (E_on+E_off la conditii de referinta). Cresterea f_sw → mai multe pierderi.',
    fields: [
      { key: 'Udc', label: 'Tensiune DC bus', unit: 'V', default: 540, step: 10, min: 0 },
      { key: 'I', label: 'Curent de iesire', unit: 'A', default: 28, step: 1, min: 0 },
      { key: 'fsw', label: 'Frecventa de comutatie', unit: 'kHz', default: 4, step: 0.5, min: 0.5 },
      { key: 'Esw', label: 'Energie comutatie', unit: 'mJ', default: 5, step: 0.5, min: 0 },
      { key: 'Uce0', label: 'Cadere conductie Uce0', unit: 'V', default: 1.5, step: 0.1, min: 0 },
    ],
    charts: [(v) => ({
      xLabel: 'Frecventa comutatie [kHz]', yLabel: 'Pierderi [W]',
      series: [
        { label: 'P comutatie', color: COL.c, points: curve(0.5, 16, (f) => 6 * v.Esw * f) },
        { label: 'P total', color: COL.a, points: curve(0.5, 16, (f) => 6 * v.Esw * f + 6 * v.Uce0 * 0.45 * v.I) },
      ],
      markers: [{ x: v.fsw, y: 6 * v.Esw * v.fsw + 6 * v.Uce0 * 0.45 * v.I, label: 'f_sw curent', color: COL.op }],
    })],
    results: [
      { key: 'Psw', label: 'Pierderi de comutatie', unit: 'W', tex: 'P_{sw} = 6\\,E_{sw}\\,f_{sw}',
        calc: (v) => 6 * v.Esw * v.fsw, dec: 0 },
      { key: 'Pcond', label: 'Pierderi de conductie', unit: 'W', tex: 'P_{cond} = 6\\,U_{ce0}\\,(0.45 I)',
        calc: (v) => 6 * v.Uce0 * 0.45 * v.I, dec: 0 },
      { key: 'Ptot', label: 'Pierderi totale', unit: 'W', tex: 'P_{tot} = P_{sw}+P_{cond}',
        calc: (v, r) => r.Psw + r.Pcond, dec: 0 },
    ],
  },
  {
    id: 'unda-reflectata',
    family: 'comun',
    tier: 3,
    title: 'Unda reflectata (lungime cablu motor)',
    subtitle: 'dv/dt: lungime critica si supratensiune la borne',
    note: 'Peste L_crit: pana la 2·U_dc la motor → filtru du/dt / motor inverter-duty. v≈150 m/µs cablu ecranat.',
    fields: [
      { key: 'tr', label: 'Timp de crestere (rise)', unit: 'µs', default: 0.1, step: 0.05, min: 0.01 },
      { key: 'vw', label: 'Viteza undei', unit: 'm/µs', default: 150, step: 10, min: 1 },
      { key: 'Udc', label: 'Tensiune DC bus', unit: 'V', default: 540, step: 10, min: 0 },
      { key: 'L', label: 'Lungime cablu', unit: 'm', default: 30, step: 5, min: 0 },
    ],
    charts: [(v) => {
      const Lc = (v.vw * v.tr) / 2
      const Upk = (L) => v.Udc * (1 + Math.min(1, L / Lc))
      return {
        xLabel: 'Lungime cablu [m]', yLabel: 'Varf tensiune motor [V]',
        series: [{ label: 'U_pk(L)', color: COL.a, points: curve(0, Lc * 2.5, Upk) }],
        markers: [{ x: v.L, y: Upk(v.L), label: 'cablu actual', color: COL.op }],
      }
    }],
    results: [
      { key: 'Lcrit', label: 'Lungime critica', unit: 'm', tex: 'L_{crit} = \\dfrac{v\\,t_r}{2}',
        calc: (v) => (v.vw * v.tr) / 2, dec: 1 },
      { key: 'Lsafe', label: 'Lungime sigura (λ/10)', unit: 'm', tex: 'L_{safe} = \\dfrac{v\\,t_r}{10}',
        calc: (v) => (v.vw * v.tr) / 10, dec: 1 },
      { key: 'Upk', label: 'Varf tensiune la motor', unit: 'V', tex: 'U_{pk} \\approx 2\\,U_{dc}',
        calc: (v) => v.Udc * (1 + Math.min(1, v.L / ((v.vw * v.tr) / 2))), dec: 0 },
    ],
  },
  {
    id: 'ride-through',
    family: 'comun',
    tier: 3,
    title: 'Ride-through DC bus',
    subtitle: 'Autonomie la microintreruperi',
    note: 'Cat tine convertizorul la gol de tensiune inainte de fault undervoltage. Prag U_dc2 ≈ 0.65·U_dc.',
    fields: [
      { key: 'Cdc', label: 'Capacitate DC bus', unit: 'µF', default: 2000, step: 100, min: 1 },
      { key: 'Udc1', label: 'Tensiune DC initiala', unit: 'V', default: 540, step: 10, min: 0 },
      { key: 'Udc2', label: 'Prag undervoltage', unit: 'V', default: 380, step: 10, min: 0 },
      { key: 'Psarc', label: 'Putere sarcina', unit: 'kW', default: 15, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'Edisp', label: 'Energie disponibila', unit: 'J', tex: 'E = \\tfrac{1}{2} C(U_{dc1}^2 - U_{dc2}^2)',
        calc: (v) => 0.5 * v.Cdc * 1e-6 * (v.Udc1 ** 2 - v.Udc2 ** 2), dec: 1 },
      { key: 'tride', label: 'Timp de sustinere', unit: 'ms', tex: 't = \\dfrac{E}{P_{sarcina}}',
        calc: (v, r) => (v.Psarc ? (r.Edisp / (v.Psarc * 1000)) * 1000 : null), dec: 1 },
    ],
  },
  {
    id: 'curenti-rulment',
    family: 'comun',
    tier: 3,
    title: 'Curenti de rulment (mod comun)',
    subtitle: 'Risc EDM la rulmenti',
    note: 'U_ax peste ~5-15 V → descarcari EDM. Masuri: rulment izolat, inel de masa, cablu simetric, filtru CM.',
    fields: [
      { key: 'Udc', label: 'Tensiune DC bus', unit: 'V', default: 540, step: 10, min: 0 },
      { key: 'BVR', label: 'Raport tensiune ax (BVR)', unit: '', default: 0.05, step: 0.01, min: 0 },
    ],
    results: [
      { key: 'Ucm', label: 'Tensiune de mod comun', unit: 'V', tex: 'U_{cm} \\approx U_{dc}/2',
        calc: (v) => v.Udc / 2, dec: 0 },
      { key: 'Uax', label: 'Tensiune pe ax', unit: 'V', tex: 'U_{ax} = BVR\\cdot U_{cm}',
        calc: (v, r) => v.BVR * r.Ucm, dec: 1 },
    ],
  },

  // ===================================== P5: SISTEME MECANICE & SARCINI
  {
    id: 'surub-bile',
    family: 'comun',
    tier: 3,
    title: 'Surub cu bile (forta → cuplu)',
    subtitle: 'Axa liniara de pozitionare',
    note: 'Actionare: ÷η. Coborare/back-drive: ×η (atentie axe verticale → frana daca η>~0.5).',
    fields: [
      { key: 'F', label: 'Forta liniara', unit: 'N', default: 5000, step: 100, min: 0 },
      { key: 'pas', label: 'Pas surub', unit: 'mm/rot', default: 10, step: 1, min: 0.1 },
      { key: 'eta', label: 'Randament surub', unit: '%', default: 90, step: 1, min: 1 },
      { key: 'm', label: 'Masa deplasata', unit: 'kg', default: 500, step: 10, min: 0 },
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 1500, step: 10, min: 0 },
    ],
    results: [
      { key: 'Tmotor', label: 'Cuplu motor (actionare)', unit: 'Nm', tex: 'M = \\dfrac{F\\,p}{2\\pi\\,\\eta}',
        calc: (v) => (v.F * (v.pas / 1000)) / (2 * Math.PI * (v.eta / 100)), dec: 2 },
      { key: 'Tback', label: 'Cuplu coborare (back-drive)', unit: 'Nm', tex: 'M = \\dfrac{F\\,p\\,\\eta}{2\\pi}',
        calc: (v) => (v.F * (v.pas / 1000) * (v.eta / 100)) / (2 * Math.PI), dec: 2 },
      { key: 'v', label: 'Viteza liniara', unit: 'm/s', tex: 'v = \\dfrac{p\\,n}{60}',
        calc: (v) => ((v.pas / 1000) * v.n) / 60, dec: 3 },
      { key: 'Jlin', label: 'Inertie liniara la ax', unit: 'kg·m²', tex: 'J = m\\left(\\dfrac{p}{2\\pi}\\right)^2',
        calc: (v) => v.m * ((v.pas / 1000) / (2 * Math.PI)) ** 2, dec: 6 },
    ],
  },
  {
    id: 'liniar-raza',
    family: 'comun',
    tier: 3,
    title: 'Curea / cremaliera (forta → cuplu)',
    subtitle: 'Transmisie liniara prin raza',
    note: 'Inertia reflectata m·r² e mare → critica la tuning (raport de inertie).',
    fields: [
      { key: 'F', label: 'Forta tangentiala', unit: 'N', default: 2000, step: 50, min: 0 },
      { key: 'D', label: 'Diametru roata/pinion', unit: 'm', default: 0.2, step: 0.01, min: 0.001 },
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 1500, step: 10, min: 0 },
      { key: 'm', label: 'Masa deplasata', unit: 'kg', default: 300, step: 10, min: 0 },
    ],
    results: [
      { key: 'T', label: 'Cuplu la ax', unit: 'Nm', tex: 'M = F\\,D/2',
        calc: (v) => (v.F * v.D) / 2, dec: 1 },
      { key: 'v', label: 'Viteza liniara', unit: 'm/s', tex: 'v = \\dfrac{\\pi D n}{60}',
        calc: (v) => (Math.PI * v.D * v.n) / 60, dec: 2 },
      { key: 'J', label: 'Inertie la ax', unit: 'kg·m²', tex: 'J = m\\,(D/2)^2',
        calc: (v) => v.m * (v.D / 2) ** 2, dec: 4 },
    ],
  },
  {
    id: 'macara',
    family: 'comun',
    tier: 3,
    title: 'Mecanism de ridicare (macara)',
    subtitle: 'Cuplu ridicare / coborare / mentinere',
    note: 'La ridicare η lucreaza contra (÷η); la coborare motorul e generator (×η) → chopper/rezistor sau 4Q.',
    fields: [
      { key: 'm', label: 'Masa ridicata', unit: 'kg', default: 1000, step: 50, min: 0 },
      { key: 'v', label: 'Viteza ridicare', unit: 'm/s', default: 0.5, step: 0.1, min: 0 },
      { key: 'r', label: 'Raza tambur', unit: 'm', default: 0.25, step: 0.05, min: 0.01 },
      { key: 'eta', label: 'Randament mecanism', unit: '%', default: 90, step: 1, min: 1 },
    ],
    results: [
      { key: 'Prid', label: 'Putere de ridicare', unit: 'kW', tex: 'P = \\dfrac{m g v}{\\eta}',
        calc: (v) => (v.m * 9.81 * v.v) / (v.eta / 100) / 1000, dec: 2 },
      { key: 'Trid', label: 'Cuplu de ridicare', unit: 'Nm', tex: 'M = \\dfrac{m g r}{\\eta}',
        calc: (v) => (v.m * 9.81 * v.r) / (v.eta / 100), dec: 0 },
      { key: 'Tcob', label: 'Cuplu de coborare', unit: 'Nm', tex: 'M = m g r\\,\\eta',
        calc: (v) => v.m * 9.81 * v.r * (v.eta / 100), dec: 0 },
      { key: 'Tment', label: 'Cuplu de mentinere', unit: 'Nm', tex: 'M = m g r',
        calc: (v) => v.m * 9.81 * v.r, dec: 0 },
    ],
  },
  {
    id: 'transportor',
    family: 'comun',
    tier: 3,
    title: 'Transportor cu banda',
    subtitle: 'Forta de tractiune si putere',
    note: 'Model simplificat (frecare + panta). Pentru banda inclinata adauga componenta de ridicare.',
    fields: [
      { key: 'mtot', label: 'Masa totala (banda+sarcina)', unit: 'kg', default: 2000, step: 50, min: 0 },
      { key: 'mu', label: 'Coeficient de frecare', unit: '', default: 0.04, step: 0.01, min: 0 },
      { key: 'beta', label: 'Unghi de inclinare', unit: '°', default: 10, step: 1, min: 0 },
      { key: 'v', label: 'Viteza banda', unit: 'm/s', default: 1.5, step: 0.1, min: 0 },
      { key: 'eta', label: 'Randament', unit: '%', default: 90, step: 1, min: 1 },
      { key: 'D', label: 'Diametru tambur', unit: 'm', default: 0.4, step: 0.05, min: 0.01 },
    ],
    results: [
      { key: 'Ffrec', label: 'Forta de frecare', unit: 'N', tex: 'F_f = \\mu\\,m g\\cos\\beta',
        calc: (v) => v.mu * v.mtot * 9.81 * Math.cos(rad(v.beta)), dec: 0 },
      { key: 'Fpanta', label: 'Forta de panta', unit: 'N', tex: 'F_p = m g\\sin\\beta',
        calc: (v) => v.mtot * 9.81 * Math.sin(rad(v.beta)), dec: 0 },
      { key: 'Ftract', label: 'Forta de tractiune', unit: 'N', tex: 'F = F_f + F_p',
        calc: (v, r) => r.Ffrec + r.Fpanta, dec: 0 },
      { key: 'P', label: 'Putere ceruta', unit: 'kW', tex: 'P = \\dfrac{F\\,v}{\\eta}',
        calc: (v, r) => (r.Ftract * v.v) / (v.eta / 100) / 1000, dec: 2 },
      { key: 'Ttamb', label: 'Cuplu la tambur', unit: 'Nm', tex: 'M = F\\,D/2',
        calc: (v, r) => (r.Ftract * v.D) / 2, dec: 0 },
    ],
  },
  {
    id: 'winder',
    family: 'comun',
    tier: 3,
    title: 'Infasurare / derulare (winder)',
    subtitle: 'Cuplu si turatie vs diametru (putere constanta)',
    note: 'Cuplu maxim la diametru plin, turatie maxima la diametru gol → motor cu zona de camp slabit.',
    fields: [
      { key: 'F', label: 'Forta de tractiune', unit: 'N', default: 500, step: 10, min: 0 },
      { key: 'dgol', label: 'Diametru gol', unit: 'm', default: 0.1, step: 0.01, min: 0.001 },
      { key: 'dplin', label: 'Diametru plin', unit: 'm', default: 0.5, step: 0.05, min: 0.001 },
      { key: 'v', label: 'Viteza material', unit: 'm/s', default: 5, step: 0.5, min: 0 },
    ],
    charts: [(v) => ({
      xLabel: 'Diametru d [m]', yLabel: 'Cuplu M [Nm]',
      series: [{ label: 'T(d) = F·d/2', color: COL.a, points: curve(v.dgol, v.dplin, (d) => (v.F * d) / 2) }],
      markers: [{ x: v.dplin, y: (v.F * v.dplin) / 2, label: 'plin (T max)', color: COL.op }],
    })],
    results: [
      { key: 'Tplin', label: 'Cuplu la diametru plin', unit: 'Nm', tex: 'M = F\\,d_{plin}/2',
        calc: (v) => (v.F * v.dplin) / 2, dec: 1 },
      { key: 'Tgol', label: 'Cuplu la diametru gol', unit: 'Nm', tex: 'M = F\\,d_{gol}/2',
        calc: (v) => (v.F * v.dgol) / 2, dec: 1 },
      { key: 'ngol', label: 'Turatie la diametru gol', unit: 'rpm', tex: 'n = \\dfrac{60 v}{\\pi d_{gol}}',
        calc: (v) => (60 * v.v) / (Math.PI * v.dgol), dec: 0 },
      { key: 'nplin', label: 'Turatie la diametru plin', unit: 'rpm', tex: 'n = \\dfrac{60 v}{\\pi d_{plin}}',
        calc: (v) => (60 * v.v) / (Math.PI * v.dplin), dec: 0 },
      { key: 'P', label: 'Putere (constanta)', unit: 'kW', tex: 'P = F\\,v',
        calc: (v) => (v.F * v.v) / 1000, dec: 2 },
      { key: 'ratio', label: 'Raport diametre (= raport turatii)', unit: '×', tex: 'd_{plin}/d_{gol}',
        calc: (v) => (v.dgol ? v.dplin / v.dgol : null), dec: 1 },
    ],
  },
  {
    id: 'frecare',
    family: 'comun',
    tier: 3,
    title: 'Cuplu de frecare & desprindere',
    subtitle: 'Breakaway (stiction) vs cuplu de mers',
    note: 'Cuplul de desprindere (frecare statica) > cuplul de mers — cauza de fault de suprasarcina la pornire.',
    fields: [
      { key: 'm', label: 'Masa / sarcina normala', unit: 'kg', default: 200, step: 10, min: 0 },
      { key: 'mud', label: 'Frecare dinamica', unit: '', default: 0.15, step: 0.01, min: 0 },
      { key: 'ratio', label: 'Raport static/dinamic', unit: '', default: 1.5, step: 0.1, min: 1 },
      { key: 'r', label: 'Raza de aplicare', unit: 'm', default: 0.1, step: 0.01, min: 0 },
    ],
    results: [
      { key: 'N', label: 'Forta normala', unit: 'N', tex: 'N = m\\,g',
        calc: (v) => v.m * 9.81, dec: 0 },
      { key: 'Trun', label: 'Cuplu de mers', unit: 'Nm', tex: 'M_{run} = \\mu_d N r',
        calc: (v, r) => v.mud * r.N * v.r, dec: 2 },
      { key: 'Tbreak', label: 'Cuplu de desprindere', unit: 'Nm', tex: 'M_{break} = k\\,M_{run}',
        calc: (v, r) => v.ratio * r.Trun, dec: 2 },
    ],
  },

  // ===================================== P6: SERVO/PMSM & CONTROL
  {
    id: 'acordare-pi',
    family: 'servo',
    tier: 3,
    title: 'Acordare bucle PI (curent + turatie)',
    subtitle: 'Modulus & symmetric optimum',
    note: 'Bucla curent: modulus optimum. Bucla turatie: symmetric optimum (a=4 → suprareglaj ~8%). Valori de pornire.',
    fields: [
      { key: 'L', label: 'Inductanta', unit: 'mH', default: 8, step: 0.5, min: 0 },
      { key: 'R', label: 'Rezistenta', unit: 'Ω', default: 1.5, step: 0.1, min: 0.001 },
      { key: 'J', label: 'Inertie totala', unit: 'kg·m²', default: 0.0005, step: 0.0001, min: 0 },
      { key: 'Kt', label: 'Constanta de cuplu', unit: 'Nm/A', default: 1.2, step: 0.1, min: 0.01 },
      { key: 'Tsum', label: 'Constanta mica (PWM+filtru)', unit: 'ms', default: 0.5, step: 0.1, min: 0.01 },
    ],
    results: [
      { key: 'Kpi', label: 'Kp bucla curent', unit: 'V/A', tex: 'K_{p,i} = \\dfrac{L}{2 T_{sum}}',
        calc: (v) => (v.L / 1000) / (2 * v.Tsum / 1000), dec: 2 },
      { key: 'Kii', label: 'Ki bucla curent', unit: '1/s', tex: 'K_{i,i} = \\dfrac{R}{2 T_{sum}}',
        calc: (v) => v.R / (2 * v.Tsum / 1000), dec: 0 },
      { key: 'wci', label: 'Banda bucla curent', unit: 'rad/s', tex: '\\omega_{ci} = \\dfrac{1}{2 T_{sum}}',
        calc: (v) => 1 / (2 * v.Tsum / 1000), dec: 0 },
      { key: 'Kpn', label: 'Kp bucla turatie', unit: '', tex: 'K_{p,n} = \\dfrac{J}{a K_t T_{sn}}',
        calc: (v) => { const Tsn = 2 * v.Tsum / 1000; return v.J / (4 * v.Kt * Tsn) }, dec: 3 },
      { key: 'Tn', label: 'Tn bucla turatie', unit: 'ms', tex: 'T_n = a^2 T_{sn}',
        calc: (v) => { const Tsn = 2 * v.Tsum / 1000; return 16 * Tsn * 1000 }, dec: 1 },
      { key: 'wcn', label: 'Banda bucla turatie', unit: 'rad/s', tex: '\\omega_{cn} = \\dfrac{1}{a T_{sn}}',
        calc: (v) => { const Tsn = 2 * v.Tsum / 1000; return 1 / (4 * Tsn) }, dec: 0 },
    ],
  },
  {
    id: 'raspuns-ord2',
    family: 'servo',
    tier: 3,
    title: 'Raspuns bucla (ordin 2)',
    subtitle: 'Suprareglaj, timp de stabilizare, banda',
    note: 'Traduce cerinta procesului (suprareglaj/timp) in ζ, ω_n si banda buclei.',
    fields: [
      { key: 'zeta', label: 'Factor de amortizare', unit: '', default: 0.7, step: 0.05, min: 0.05 },
      { key: 'wn', label: 'Pulsatie naturala', unit: 'rad/s', default: 100, step: 5, min: 1 },
    ],
    results: [
      { key: 'Mp', label: 'Suprareglaj', unit: '%', tex: 'M_p = e^{-\\pi\\zeta/\\sqrt{1-\\zeta^2}}\\cdot 100',
        calc: (v) => (v.zeta < 1 ? Math.exp((-Math.PI * v.zeta) / Math.sqrt(1 - v.zeta ** 2)) * 100 : 0), dec: 1 },
      { key: 'ts', label: 'Timp de stabilizare (2%)', unit: 'ms', tex: 't_s = \\dfrac{4}{\\zeta\\omega_n}',
        calc: (v) => (4 / (v.zeta * v.wn)) * 1000, dec: 1 },
      { key: 'tp', label: 'Timp pana la varf', unit: 'ms', tex: 't_p = \\dfrac{\\pi}{\\omega_n\\sqrt{1-\\zeta^2}}',
        calc: (v) => (v.zeta < 1 ? (Math.PI / (v.wn * Math.sqrt(1 - v.zeta ** 2))) * 1000 : null), dec: 1 },
      { key: 'wBW', label: 'Banda de frecventa', unit: 'rad/s', tex: '\\omega_{BW} = \\omega_n\\sqrt{1-2\\zeta^2+\\sqrt{4\\zeta^4-4\\zeta^2+2}}',
        calc: (v) => v.wn * Math.sqrt(1 - 2 * v.zeta ** 2 + Math.sqrt(4 * v.zeta ** 4 - 4 * v.zeta ** 2 + 2)), dec: 0 },
    ],
  },
  {
    id: 'pmsm-camp-slabit',
    family: 'servo',
    tier: 3,
    title: 'PMSM in slabire de camp',
    subtitle: 'Turatie de baza, curent caracteristic',
    note: 'Daca $I_{ch} < I_{max}$ → gama de putere constanta extinsa (slabire prin $I_d<0$). $U_{max} \\approx U_{dc}/\\sqrt{3}$ (SVM). Peste $n_{baza}$: cuplu $\\propto 1/n$ la putere constanta.',
    charts: [
      (v) => {
        if (!v.psim || !v.ppp) return null
        const Vmax = v.Udc / SQRT3
        const Ld = v.Lq / 1000
        const we = Vmax / Math.sqrt(v.psim ** 2 + (Ld * v.Imax) ** 2)
        const nb = ((we / v.ppp) * 60) / (2 * Math.PI)
        if (!(nb > 0)) return null
        const Mbase = 1.5 * v.ppp * v.psim * v.Imax
        const nmax = nb * 3
        const M = (n) => (n <= nb ? Mbase : (Mbase * nb) / n)
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M [Nm]',
          series: [{ label: 'M (constant → ∝1/n in slabire)', color: COL.a, points: curve(0, nmax, M) }],
          markers: [{ x: Math.round(nb), y: Mbase, label: 'n baza', color: COL.op }],
        }
      },
    ],
    fields: [
      { key: 'Udc', label: 'Tensiune DC bus', unit: 'V', default: 540, step: 10, min: 0 },
      { key: 'ppp', label: 'Perechi de poli', unit: '', default: 4, step: 1, min: 1 },
      { key: 'psim', label: 'Flux magneti permanenti', unit: 'Wb', default: 0.1, step: 0.01, min: 0.001 },
      { key: 'Lq', label: 'Inductanta Lq', unit: 'mH', default: 8, step: 0.5, min: 0.1 },
      { key: 'Imax', label: 'Curent maxim', unit: 'A', default: 10, step: 1, min: 0 },
    ],
    results: [
      { key: 'Vmax', label: 'Tensiune maxima', unit: 'V', tex: 'U_{max} = U_{dc}/\\sqrt{3}',
        calc: (v) => v.Udc / SQRT3, dec: 1 },
      { key: 'nbaza', label: 'Turatie de baza', unit: 'rpm', tex: 'n_{baza}: \\omega_e=\\dfrac{U_{max}}{\\sqrt{\\psi_m^2+(L_q I_{max})^2}}',
        calc: (v, r) => { const we = r.Vmax / Math.sqrt(v.psim ** 2 + ((v.Lq / 1000) * v.Imax) ** 2); return (we / v.ppp) * 60 / (2 * Math.PI) }, dec: 0 },
      { key: 'Ich', label: 'Curent caracteristic', unit: 'A', tex: 'I_{ch} = \\psi_m/L_d',
        calc: (v) => v.psim / (v.Lq / 1000), dec: 1 },
    ],
  },
  {
    id: 'profil-miscare',
    family: 'servo',
    tier: 3,
    title: 'Profil de miscare (trapezoidal vs S-curve)',
    subtitle: 'Acceleratie de varf si jerk',
    note: 'S-curve (jerk limitat) reduce socul si varful de cuplu vs trapezoidal, la cost de timp putin mai mare.',
    fields: [
      { key: 's', label: 'Distanta de deplasare', unit: 'u', default: 1, step: 0.1, min: 0 },
      { key: 't', label: 'Timp de deplasare', unit: 's', default: 1, step: 0.1, min: 0.01 },
      { key: 'frac', label: 'Fractie de accelerare', unit: '%', default: 33, step: 1, min: 1 },
    ],
    results: [
      { key: 'vmax', label: 'Viteza maxima', unit: 'u/s', tex: 'v_{max} = \\dfrac{s}{t - t_{acc}}',
        calc: (v) => { const ta = (v.frac / 100) * v.t; return v.s / (v.t - ta) }, dec: 3 },
      { key: 'atrap', label: 'Acceleratie trapezoidal', unit: 'u/s²', tex: 'a = v_{max}/t_{acc}',
        calc: (v, r) => { const ta = (v.frac / 100) * v.t; return r.vmax / ta }, dec: 2 },
      { key: 'ascurve', label: 'Acceleratie de varf S-curve', unit: 'u/s²', tex: 'a_{pk} \\approx 2\\,a_{trap}',
        calc: (v, r) => 2 * r.atrap, dec: 2 },
      { key: 'jerk', label: 'Jerk', unit: 'u/s³', tex: 'j = \\dfrac{4 v_{max}}{t_{acc}^2}',
        calc: (v, r) => { const ta = (v.frac / 100) * v.t; return (4 * r.vmax) / ta ** 2 }, dec: 1 },
    ],
  },

  // ===================================== P7: SINCRON & C.C. AVANSAT
  {
    id: 'sincron-poli-aparenti',
    family: 'sincron',
    tier: 3,
    title: 'Sincron cu poli aparenti',
    subtitle: 'Putere de excitatie + cuplu de reluctanta',
    note: 'Xd ≠ Xq → cuplu suplimentar de reluctanta; pull-out la δ < 90°. Valabil si la IPM.',
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 0 },
      { key: 'E', label: 'T.e.m. (excitatie)', unit: 'V', default: 420, step: 10, min: 0 },
      { key: 'Xd', label: 'Reactanta axa d', unit: 'Ω', default: 2.5, step: 0.1, min: 0.01 },
      { key: 'Xq', label: 'Reactanta axa q', unit: 'Ω', default: 1.5, step: 0.1, min: 0.01 },
      { key: 'delta', label: 'Unghi de sarcina', unit: '°', default: 30, step: 1, min: 0 },
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', default: 1500, step: 10, min: 1 },
    ],
    charts: [(v) => {
      const Pex = (d) => (v.U * v.E * Math.sin(rad(d))) / v.Xd / 1000
      const Prel = (d) => ((v.U ** 2 / 2) * (1 / v.Xq - 1 / v.Xd) * Math.sin(2 * rad(d))) / 1000
      return {
        xLabel: 'Unghi de sarcina δ [°]', yLabel: 'Putere P [kW]',
        series: [
          { label: 'P excitatie', color: COL.a, points: curve(0, 180, Pex) },
          { label: 'P reluctanta', color: COL.b, dash: true, points: curve(0, 180, Prel) },
          { label: 'P total', color: COL.c, points: curve(0, 180, (d) => Pex(d) + Prel(d)) },
        ],
        markers: [{ x: v.delta, y: Pex(v.delta) + Prel(v.delta), label: 'δ curent', color: COL.op }],
      }
    }],
    results: [
      { key: 'Pex', label: 'Putere de excitatie', unit: 'kW', tex: 'P_e = \\dfrac{U E\\sin\\delta}{X_d}',
        calc: (v) => (v.U * v.E * Math.sin(rad(v.delta))) / v.Xd / 1000, dec: 2 },
      { key: 'Prel', label: 'Putere de reluctanta', unit: 'kW', tex: 'P_r = \\dfrac{U^2}{2}\\left(\\dfrac{1}{X_q}-\\dfrac{1}{X_d}\\right)\\sin 2\\delta',
        calc: (v) => ((v.U ** 2 / 2) * (1 / v.Xq - 1 / v.Xd) * Math.sin(2 * rad(v.delta))) / 1000, dec: 2 },
      { key: 'Ptot', label: 'Putere totala', unit: 'kW', tex: 'P = P_e + P_r',
        calc: (v, r) => r.Pex + r.Prel, dec: 2 },
      { key: 'M', label: 'Cuplu', unit: 'Nm', tex: 'M = P/\\omega_s',
        calc: (v, r) => (r.Ptot * 1000) / omega(v.ns), dec: 1 },
    ],
  },
  {
    id: 'synrm',
    family: 'sincron',
    tier: 3,
    title: 'SynRM / IPM — cuplu de reluctanta',
    subtitle: 'Cuplu si raport de salienta (MTPA la 45°)',
    note: 'Motoare IE4/IE5 fara V/f clasic. M creste cu raportul de salienta Ld/Lq.',
    fields: [
      { key: 'ppp', label: 'Perechi de poli', unit: '', default: 2, step: 1, min: 1 },
      { key: 'Ld', label: 'Inductanta Ld', unit: 'H', default: 0.2, step: 0.01, min: 0.001 },
      { key: 'Lq', label: 'Inductanta Lq', unit: 'H', default: 0.05, step: 0.01, min: 0.001 },
      { key: 'I', label: 'Curent', unit: 'A', default: 10, step: 1, min: 0 },
    ],
    results: [
      { key: 'M', label: 'Cuplu (MTPA, 45°)', unit: 'Nm', tex: 'M = \\tfrac{3}{4}\\,p\\,(L_d-L_q)\\,I^2',
        calc: (v) => 0.75 * v.ppp * (v.Ld - v.Lq) * v.I ** 2, dec: 1 },
      { key: 'salient', label: 'Raport de salienta', unit: '×', tex: '\\xi = L_d/L_q',
        calc: (v) => (v.Lq ? v.Ld / v.Lq : null), dec: 2 },
    ],
  },
  {
    id: 'cc-serie',
    family: 'cc',
    tier: 3,
    title: 'Motor c.c. serie',
    subtitle: 'M ~ Ia², n ~ 1/Ia (tractiune)',
    note: 'Cuplu mare de pornire; pericol de ambalare la gol (n → ∞ cand Ia → 0). Constante de model.',
    fields: [
      { key: 'U', label: 'Tensiune', unit: 'V', default: 440, step: 10, min: 0 },
      { key: 'Rt', label: 'Rezistenta totala (indus+exc)', unit: 'Ω', default: 0.3, step: 0.05, min: 0.001 },
      { key: 'kt', label: 'Constanta cuplu', unit: 'Nm/A²', default: 0.03, step: 0.005, min: 0 },
      { key: 'c', label: 'Constanta tensiune', unit: 'V/(rpm·A)', default: 0.005, step: 0.001, min: 0.0001 },
      { key: 'Ia', label: 'Curent indus (punct)', unit: 'A', default: 80, step: 5, min: 1 },
    ],
    charts: [(v) => ({
      xLabel: 'Curent indus Ia [A]', yLabel: 'Turatie n [rpm]',
      series: [{ label: 'n(Ia) ~ 1/Ia', color: COL.a, points: curve(v.Ia * 0.3, v.Ia * 1.5, (Ia) => (v.U - Ia * v.Rt) / (v.c * Ia)) }],
      markers: [{ x: v.Ia, y: (v.U - v.Ia * v.Rt) / (v.c * v.Ia), label: 'punct', color: COL.op }],
    })],
    results: [
      { key: 'M', label: 'Cuplu', unit: 'Nm', tex: 'M = k_t\\,I_a^2',
        calc: (v) => v.kt * v.Ia ** 2, dec: 1 },
      { key: 'E', label: 'T.c.e.m.', unit: 'V', tex: 'E = U - I_a R_t',
        calc: (v) => v.U - v.Ia * v.Rt, dec: 1 },
      { key: 'n', label: 'Turatie', unit: 'rpm', tex: 'n = \\dfrac{U - I_a R_t}{c\\,I_a}',
        calc: (v) => (v.c && v.Ia ? (v.U - v.Ia * v.Rt) / (v.c * v.Ia) : null), dec: 0 },
    ],
  },
  {
    id: 'cc-randament',
    family: 'cc',
    tier: 3,
    title: 'Motor c.c. — randament & pierderi',
    subtitle: 'Bilant de putere (separat excitat)',
    fields: [
      { key: 'U', label: 'Tensiune indus', unit: 'V', default: 440, step: 10, min: 0 },
      { key: 'Ia', label: 'Curent indus', unit: 'A', default: 80, step: 1, min: 0 },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', default: 0.15, step: 0.01, min: 0 },
      { key: 'Uf', label: 'Tensiune excitatie', unit: 'V', default: 220, step: 10, min: 0 },
      { key: 'If', label: 'Curent excitatie', unit: 'A', default: 2, step: 0.1, min: 0 },
      { key: 'Prot', label: 'Pierderi de rotatie', unit: 'W', default: 800, step: 50, min: 0 },
    ],
    results: [
      { key: 'Pin', label: 'Putere absorbita', unit: 'W', tex: 'P_{in} = U I_a + U_f I_f',
        calc: (v) => v.U * v.Ia + v.Uf * v.If, dec: 0 },
      { key: 'Pem', label: 'Putere electromagnetica', unit: 'W', tex: 'P_{em} = (U - I_a R_a) I_a',
        calc: (v) => (v.U - v.Ia * v.Ra) * v.Ia, dec: 0 },
      { key: 'Pax', label: 'Putere la arbore', unit: 'W', tex: 'P_{ax} = P_{em} - P_{rot}',
        calc: (v, r) => r.Pem - v.Prot, dec: 0 },
      { key: 'eta', label: 'Randament', unit: '%', tex: '\\eta = P_{ax}/P_{in}\\cdot 100',
        calc: (v, r) => (r.Pin ? (r.Pax / r.Pin) * 100 : null), dec: 1 },
    ],
  },

  // ===================================== P8: TERMIC & MOTOR (extinderi)
  {
    id: 'motor-termic',
    family: 'asincron',
    tier: 3,
    title: 'Model termic motor (I²t)',
    subtitle: 'Timp pana la limita la suprasarcina + racire',
    note: 'Model exponential cu o constanta de timp termica. theta=100% = limita nominala.',
    fields: [
      { key: 'I', label: 'Curent', unit: 'A', default: 33, step: 1, min: 0 },
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 1 },
      { key: 'tau', label: 'Constanta de timp termica', unit: 's', default: 1800, step: 60, min: 1 },
    ],
    results: [
      { key: 'thetaf', label: 'Temperatura finala', unit: '× nom', tex: '\\theta_\\infty = (I/I_n)^2',
        calc: (v) => (v.In ? (v.I / v.In) ** 2 : null), dec: 3 },
      { key: 'tlim', label: 'Timp pana la limita', unit: 's', tex: 't = \\tau\\ln\\dfrac{x^2}{x^2-1}',
        calc: (v, r) => (r.thetaf > 1 ? v.tau * Math.log(r.thetaf / (r.thetaf - 1)) : null), dec: 0 },
      { key: 'tracire', label: 'Timp racire la 50%', unit: 's', tex: 't = \\tau\\ln 2',
        calc: (v) => v.tau * Math.LN2, dec: 0 },
    ],
  },
  {
    id: 'clase-ie',
    family: 'asincron',
    tier: 3,
    title: 'Clase de randament IE & economie',
    subtitle: 'Compara pierderi + payback motor premium',
    note: 'IE1...IE5 (IEC 60034-30). Economia justifica costul suplimentar al motorului eficient.',
    fields: [
      { key: 'Pn', label: 'Putere nominala', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'etalow', label: 'Randament clasa joasa', unit: '%', default: 89.6, step: 0.1, min: 1 },
      { key: 'etahigh', label: 'Randament clasa superioara', unit: '%', default: 92.1, step: 0.1, min: 1 },
      { key: 'ore', label: 'Ore functionare', unit: 'h/an', default: 6000, step: 100, min: 0 },
      { key: 'pret', label: 'Pret energie', unit: 'lei/kWh', default: 0.8, step: 0.05, min: 0 },
      { key: 'dpret', label: 'Diferenta de pret motor', unit: 'lei', default: 800, step: 50, min: 0 },
    ],
    results: [
      { key: 'losslow', label: 'Pierderi clasa joasa', unit: 'kW', tex: 'P_{loss} = P_n(1/\\eta - 1)',
        calc: (v) => v.Pn * (1 / (v.etalow / 100) - 1), dec: 3 },
      { key: 'losshigh', label: 'Pierderi clasa superioara', unit: 'kW', tex: 'P_{loss} = P_n(1/\\eta - 1)',
        calc: (v) => v.Pn * (1 / (v.etahigh / 100) - 1), dec: 3 },
      { key: 'Wecon', label: 'Economie anuala', unit: 'kWh/an', tex: 'W = (P_n/\\eta_j - P_n/\\eta_s)\\,ore',
        calc: (v) => (v.Pn / (v.etalow / 100) - v.Pn / (v.etahigh / 100)) * v.ore, dec: 0 },
      { key: 'Cecon', label: 'Economie in bani', unit: 'lei/an', tex: 'C = W\\cdot pret',
        calc: (v, r) => r.Wecon * v.pret, dec: 0 },
      { key: 'payback', label: 'Recuperare investitie', unit: 'ani', tex: 'T = \\Delta pret / C',
        calc: (v, r) => (r.Cecon > 0 ? v.dpret / r.Cecon : null), dec: 2 },
    ],
  },
  {
    id: 'derating-vfd-motor',
    family: 'asincron',
    tier: 3,
    title: 'Derating motor pe VFD (autoventilatie)',
    subtitle: 'Curent admisibil la turatie redusa',
    note: 'Autoventilat: racire scade cu turatia. Sarcina patratica OK; cuplu constant la f mica → ventilatie fortata.',
    fields: [
      { key: 'fn', label: 'Frecventa nominala', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'f', label: 'Frecventa de lucru', unit: 'Hz', default: 25, step: 1, min: 0 },
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 0 },
    ],
    charts: [(v) => ({
      xLabel: 'Frecventa f [Hz]', yLabel: 'Curent admisibil [A]',
      series: [
        { label: 'Autoventilat', color: COL.a, points: curve(0, v.fn, (f) => v.In * Math.min(1, 0.55 + 0.45 * (f / v.fn))) },
        { label: 'Ventilatie fortata', color: COL.b, dash: true, points: curve(0, v.fn, () => v.In) },
      ],
      markers: [{ x: v.f, y: v.In * Math.min(1, 0.55 + 0.45 * (v.f / v.fn)), label: 'f curent', color: COL.op }],
    })],
    results: [
      { key: 'kself', label: 'Factor autoventilatie', unit: '×', tex: 'k \\approx 0.55 + 0.45\\,f/f_n',
        calc: (v) => Math.min(1, 0.55 + 0.45 * (v.f / v.fn)), dec: 3 },
      { key: 'Iself', label: 'Curent admisibil (autovent.)', unit: 'A', tex: 'I = I_n\\,k',
        calc: (v, r) => v.In * r.kself, dec: 1 },
      { key: 'Iforced', label: 'Curent admisibil (fortat)', unit: 'A', tex: 'I = I_n',
        calc: (v) => v.In, dec: 1 },
    ],
  },

  // ============================================ LOT 3: COMPLETARI
  // --- asincron ---
  {
    id: 'cosphi-sarcina',
    family: 'asincron',
    tier: 3,
    title: 'Factor de putere vs sarcina',
    subtitle: 'cos φ scade puternic la sarcini partiale',
    note: 'Curentul de magnetizare e ~constant; la sarcina mica componenta activa scade → cos φ se prabuseste.',
    fields: [
      { key: 'cosphin', label: 'Factor de putere nominal', unit: '', default: 0.85, step: 0.01, min: 0.1 },
      { key: 'In', label: 'Curent nominal', unit: 'A', default: 28, step: 1, min: 0 },
    ],
    charts: [(v) => {
      const sinp = Math.sqrt(Math.max(0, 1 - v.cosphin ** 2))
      const Imag = v.In * sinp
      const cosx = (x) => { const Ia = x * v.In * v.cosphin; return Ia / Math.sqrt(Ia ** 2 + Imag ** 2) }
      return {
        xLabel: 'Sarcina [% din nominal]', yLabel: 'cos φ',
        series: [{ label: 'cos φ(sarcina)', color: COL.a, points: curve(10, 110, (xp) => cosx(xp / 100)) }],
        markers: [{ x: 100, y: cosx(1), label: 'nominal', color: COL.op }],
      }
    }],
    results: [
      { key: 'Igol', label: 'Curent de magnetizare (≈ I_n·sin φ_n)', unit: 'A', tex: 'I_0 \\approx I_n\\sin\\varphi_n',
        calc: (v) => v.In * Math.sqrt(Math.max(0, 1 - v.cosphin ** 2)), dec: 2 },
      { key: 'cosphi50', label: 'cos φ la 50% sarcina', unit: '', tex: '\\cos\\varphi = \\dfrac{I_a}{\\sqrt{I_a^2+I_0^2}}',
        calc: (v, r) => { const Ia = 0.5 * v.In * v.cosphin; return Ia / Math.sqrt(Ia ** 2 + r.Igol ** 2) }, dec: 3 },
      { key: 'cosphi25', label: 'cos φ la 25% sarcina', unit: '', tex: '\\cos\\varphi(0.25)',
        calc: (v, r) => { const Ia = 0.25 * v.In * v.cosphin; return Ia / Math.sqrt(Ia ** 2 + r.Igol ** 2) }, dec: 3 },
    ],
  },
  {
    id: 'derating-armonici-motor',
    family: 'asincron',
    tier: 3,
    title: 'Derating motor la armonici (HVF)',
    subtitle: 'Pierdere de putere admisibila pe retea poluata',
    note: 'HVF = Harmonic Voltage Factor (NEMA MG-1 Part 30). Tensiuni armonice in % din fundamentala.',
    fields: [
      { key: 'V5', label: 'Armonica 5', unit: '%', default: 8, step: 0.5, min: 0 },
      { key: 'V7', label: 'Armonica 7', unit: '%', default: 5, step: 0.5, min: 0 },
      { key: 'V11', label: 'Armonica 11', unit: '%', default: 3, step: 0.5, min: 0 },
      { key: 'V13', label: 'Armonica 13', unit: '%', default: 2, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'HVF', label: 'Harmonic Voltage Factor', unit: '', tex: 'HVF = \\sqrt{\\sum U_n^2/n}',
        calc: (v) => Math.sqrt((v.V5 / 100) ** 2 / 5 + (v.V7 / 100) ** 2 / 7 + (v.V11 / 100) ** 2 / 11 + (v.V13 / 100) ** 2 / 13), dec: 4 },
      { key: 'df', label: 'Factor de derating', unit: '%', tex: '\\text{NEMA MG-1 Fig.30-1}',
        calc: (v, r) => { const h = r.HVF; const p = [[0, 1], [0.03, 1], [0.05, 0.975], [0.07, 0.94], [0.09, 0.90], [0.10, 0.85], [0.11, 0.80], [0.115, 0.75]]; if (h <= p[0][0]) return 100; for (let i = 1; i < p.length; i++) { if (h <= p[i][0]) { const a = p[i - 1], b = p[i]; return (a[1] + (b[1] - a[1]) * (h - a[0]) / (b[0] - a[0])) * 100 } } return 75 }, dec: 1 },
    ],
  },
  {
    id: 'regimuri-s',
    family: 'asincron',
    tier: 3,
    title: 'Regimuri de functionare S1-S10',
    subtitle: 'Derating de putere si echivalent termic pe tip de serviciu',
    note: 'IEC 60034-1 §4.2. CDF = factor de durata ciclica (numaratorul difera per tip). $S1$ continuu — referinta $P_{S1}$. $S2$ scurt ("S2 60 min", prin TIMP): $P_{S2}$ din capacitatea termica intr-un $t_P<\\tau$. $S3$ intermitent, repaus DECONECTAT, $CDF=\\Delta t_P/T_C$: $P_{S3}=P_{S1}/\\sqrt{CDF}$. $S4$ cu pornire ($CDF=(\\Delta t_D+\\Delta t_P)/T_C$) si $S5$ +franare ($CDF=(\\Delta t_D+\\Delta t_P+\\Delta t_F)/T_C$): caldura de pornire/franare domina → vezi "Porniri pe ora". $S6$ cu MERS IN GOL intre sarcini (nu repaus), racire mai slaba ca S3: $P_{S6}=P_{S1}/\\sqrt{CDF+(1-CDF)k_0}$, $k_0=$ pierderi gol/nominal. $S7$ pornire+sarcina+franare fara repaus ($CDF=1$) → "Porniri pe ora". $S8$ sarcini/turatii multiple (CDF per treapta): echivalent termic $P_{ech}$ pe trepte. $S9$ non-periodic, suprasarcini fata de $P_{ref}$ → "Model termic motor". $S10$ sarcini discrete → "Durata de viata termica".',
    fields: [
      { key: 'Ps1', label: 'Putere nominala S1 (continuu)', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'DC', label: 'Factor de durata ciclica CDF (S3/S6)', unit: '%', default: 40, step: 5, min: 1, max: 100 },
      { key: 'tP', label: 'Durata la sarcina (S2)', unit: 'min', default: 30, step: 5, min: 1 },
      { key: 'tau', label: 'Constanta termica', unit: 'min', default: 45, step: 5, min: 1 },
      { key: 'k0', label: 'Raport pierderi mers in gol (S6)', unit: '', default: 0.25, step: 0.05, min: 0, max: 1 },
      { key: 'Pload', label: 'Sarcina in faza de lucru (S6/S8)', unit: 'kW', default: 18, step: 0.5, min: 0 },
      { key: 'tload', label: 'Durata faza de lucru / ciclu', unit: 's', default: 60, step: 5, min: 1 },
      { key: 'tpauza', label: 'Durata pauza / ciclu', unit: 's', default: 90, step: 5, min: 0 },
      { key: 'kp', label: 'Factor racire in pauza (S6/S8)', unit: '', default: 0.5, step: 0.05, min: 0, max: 1 },
    ],
    charts: [(v) => ({
      xLabel: 'CDF [%]', yLabel: 'Putere admisibila [kW]',
      series: [
        { label: 'S3 (repaus deconectat)', color: COL.a, points: curve(10, 100, (dc) => v.Ps1 / Math.sqrt(dc / 100)) },
        { label: 'S6 (mers in gol)', color: COL.b, points: curve(10, 100, (dc) => v.Ps1 / Math.sqrt(dc / 100 + (1 - dc / 100) * v.k0)) },
        { label: 'S1 (nominal)', color: COL.c, dash: true, points: curve(10, 100, () => v.Ps1) },
      ],
    })],
    results: [
      { key: 'PS2', label: 'Putere admisibila S2 (scurt)', unit: 'kW', tex: 'P_{S2} = \\dfrac{P_{S1}}{\\sqrt{1-e^{-t_P/\\tau}}}',
        calc: (v) => v.Ps1 / Math.sqrt(1 - Math.exp(-v.tP / v.tau)), dec: 2 },
      { key: 'PS3', label: 'Putere admisibila S3 (repaus deconectat)', unit: 'kW', tex: 'P_{S3} = \\dfrac{P_{S1}}{\\sqrt{\\mathrm{DC}}}',
        calc: (v) => v.Ps1 / Math.sqrt(v.DC / 100), dec: 2 },
      { key: 'PS6', label: 'Putere admisibila S6 (mers in gol)', unit: 'kW', tex: 'P_{S6} = \\dfrac{P_{S1}}{\\sqrt{\\mathrm{DC}+(1-\\mathrm{DC})\\,k_0}}',
        calc: (v) => v.Ps1 / Math.sqrt(v.DC / 100 + (1 - v.DC / 100) * v.k0), dec: 2 },
      { key: 'Pech', label: 'Echivalent termic pe ciclu (S6/S8)', unit: 'kW', tex: 'P_{ech} = \\sqrt{\\dfrac{P_{load}^2\\,t_{load}}{t_{load}+k_p\\,t_{pauza}}}',
        calc: (v) => Math.sqrt((v.Pload * v.Pload * v.tload) / (v.tload + v.kp * v.tpauza)), dec: 2 },
      { key: 'marja', label: 'Rezerva termica (Ps1/Pech, ≥1 OK)', unit: '', tex: '\\mathrm{rez} = P_{S1}/P_{ech}',
        calc: (v, r) => (r.Pech > 0 ? v.Ps1 / r.Pech : null), dec: 2 },
      { key: 'CDFcalc', label: 'CDF din durate (S3/S6)', unit: '%', tex: '\\mathrm{CDF} = \\dfrac{t_{load}}{t_{load}+t_{pauza}}',
        calc: (v) => (100 * v.tload) / (v.tload + v.tpauza), dec: 1 },
    ],
  },
  {
    id: 'viata-termica-s10',
    family: 'asincron',
    tier: 3,
    title: 'Durata de viata termica (regim S10)',
    subtitle: 'Viata relativa a izolatiei la sarcini discrete',
    note: 'IEC 60034-1 S10 + Annex A. Sarcini discrete $p_i$ (relative la $P_{ref}$ din S1), fiecare pana la echilibru termic; $p=0$ = repaus ("r"). Imbatranirea izolatiei se dubleaza la fiecare $+H$ grade (regula Montsinger ~10K, IEC 60085). Incalzirea ~ $p^2$, deci excesul fata de referinta e $(p^2-1)\\Delta\\Theta_{ref}$. $\\mathrm{TL}$ = durata de viata relativa la S1 ($\\mathrm{TL}\\ge1$ OK). $\\Delta\\Theta_{ref}$ = cresterea de temperatura la referinta (clasa B~80, F~105, H~125 K). Exemplu IEC: $\\mathrm{TL}\\approx0{,}6$.',
    fields: [
      { key: 'dTref', label: 'Crestere temperatura la referinta S1', unit: 'K', default: 80, step: 5, min: 1 },
      { key: 'H', label: 'Interval de injumatatire a vietii', unit: 'K', default: 10, step: 1, min: 1 },
      { key: 'p1', label: 'Sarcina relativa treapta 1', unit: '', default: 1.1, step: 0.05, min: 0 },
      { key: 'f1', label: 'Fractia de timp treapta 1', unit: '%', default: 40, step: 5, min: 0 },
      { key: 'p2', label: 'Sarcina relativa treapta 2', unit: '', default: 1.0, step: 0.05, min: 0 },
      { key: 'f2', label: 'Fractia de timp treapta 2', unit: '%', default: 30, step: 5, min: 0 },
      { key: 'p3', label: 'Sarcina relativa treapta 3', unit: '', default: 0.9, step: 0.05, min: 0 },
      { key: 'f3', label: 'Fractia de timp treapta 3', unit: '%', default: 20, step: 5, min: 0 },
      { key: 'p4', label: 'Sarcina relativa treapta 4 (0=repaus)', unit: '', default: 0, step: 0.05, min: 0 },
      { key: 'f4', label: 'Fractia de timp treapta 4', unit: '%', default: 10, step: 5, min: 0 },
    ],
    results: [
      { key: 'AR', label: 'Rata medie de imbatranire', unit: '', tex: '\\mathrm{AR} = \\sum f_i\\,2^{(p_i^2-1)\\Delta\\Theta_{ref}/H}',
        calc: (v) => [[v.p1, v.f1], [v.p2, v.f2], [v.p3, v.f3], [v.p4, v.f4]].reduce((s, seg) => s + (seg[1] / 100) * Math.pow(2, ((seg[0] * seg[0] - 1) * v.dTref) / v.H), 0), dec: 3 },
      { key: 'TL', label: 'Durata de viata termica relativa (≥1 OK)', unit: '', tex: '\\mathrm{TL} = 1/\\mathrm{AR}',
        calc: (v, r) => (r.AR > 0 ? 1 / r.AR : null), dec: 2 },
    ],
  },
  {
    id: 'porniri-ora',
    family: 'asincron',
    tier: 3,
    title: 'Porniri pe ora & energie de pornire',
    subtitle: 'Verificare regim de porniri dese',
    note: 'E_start ≈ energie disipata in rotor pe o pornire in gol (= energia cinetica). Compara cu bugetul termic (catalog z0).',
    fields: [
      { key: 'J', label: 'Inertie totala', unit: 'kg·m²', default: 0.5, step: 0.1, min: 0 },
      { key: 'ns', label: 'Turatie sincrona', unit: 'rpm', default: 1500, step: 10, min: 1 },
      { key: 'Macc', label: 'Cuplu de accelerare', unit: 'Nm', default: 100, step: 5, min: 0 },
      { key: 'Mload', label: 'Cuplu rezistent', unit: 'Nm', default: 40, step: 5, min: 0 },
      { key: 'Ebudget', label: 'Buget termic pornire', unit: 'kJ/h', default: 200, step: 10, min: 0 },
    ],
    results: [
      { key: 'Estart', label: 'Energie pe pornire', unit: 'J', tex: 'E \\approx \\tfrac{1}{2}J\\,\\omega_s^2',
        calc: (v) => 0.5 * v.J * omega(v.ns) ** 2, dec: 0 },
      { key: 'tstart', label: 'Timp de pornire', unit: 's', tex: 't = \\dfrac{J\\,\\omega_s}{M_{acc}-M_{load}}',
        calc: (v) => { const dm = v.Macc - v.Mload; return dm > 0 ? (v.J * omega(v.ns)) / dm : null }, dec: 2 },
      { key: 'nrh', label: 'Porniri admisibile/ora', unit: '1/h', tex: 'n = E_{buget}/E_{start}',
        calc: (v, r) => (r.Estart ? (v.Ebudget * 1000) / r.Estart : null), dec: 0 },
    ],
  },

  // --- pompe & ventilatoare ---
  {
    id: 'economie-profil',
    family: 'pompe',
    tier: 3,
    title: 'Economie pe profil de sarcina',
    subtitle: 'VFD vs strangulare (vana), ponderat pe ore',
    note: 'Economia onesta pe profil real de debit (nu un singur punct). Strangulare ≈ putere cvasi-constanta.',
    fields: [
      { key: 'Pvana', label: 'Putere cu vana (100%)', unit: 'kW', default: 15, step: 0.5, min: 0 },
      { key: 'q1', label: 'Debit 1', unit: '%', default: 100, step: 5, min: 0 },
      { key: 'h1', label: 'Ore la debit 1', unit: 'h/an', default: 1000, step: 100, min: 0 },
      { key: 'q2', label: 'Debit 2', unit: '%', default: 75, step: 5, min: 0 },
      { key: 'h2', label: 'Ore la debit 2', unit: 'h/an', default: 3000, step: 100, min: 0 },
      { key: 'q3', label: 'Debit 3', unit: '%', default: 50, step: 5, min: 0 },
      { key: 'h3', label: 'Ore la debit 3', unit: 'h/an', default: 4000, step: 100, min: 0 },
      { key: 'pret', label: 'Pret energie', unit: 'lei/kWh', default: 0.8, step: 0.05, min: 0 },
    ],
    charts: [(v) => ({
      xLabel: 'Debit [%]', yLabel: 'Putere [kW]',
      series: [
        { label: 'VFD (cubic)', color: COL.a, points: curve(0, 100, (q) => v.Pvana * (q / 100) ** 3) },
        { label: 'Strangulare (vana)', color: COL.b, dash: true, points: curve(0, 100, (q) => v.Pvana * (0.4 + 0.6 * (q / 100))) },
        { label: 'By-pass', color: COL.c, dash: true, points: curve(0, 100, () => v.Pvana) },
      ],
    })],
    results: [
      { key: 'Evfd', label: 'Energie cu VFD', unit: 'kWh/an', tex: '\\sum P_{vfd}(q_i)\\,h_i',
        calc: (v) => v.Pvana * ((v.q1 / 100) ** 3 * v.h1 + (v.q2 / 100) ** 3 * v.h2 + (v.q3 / 100) ** 3 * v.h3), dec: 0 },
      { key: 'Evana', label: 'Energie cu strangulare', unit: 'kWh/an', tex: '\\sum P_{vana}(q_i)\\,h_i',
        calc: (v) => v.Pvana * ((0.4 + 0.6 * v.q1 / 100) * v.h1 + (0.4 + 0.6 * v.q2 / 100) * v.h2 + (0.4 + 0.6 * v.q3 / 100) * v.h3), dec: 0 },
      { key: 'Wsav', label: 'Economie anuala', unit: 'kWh/an', tex: 'W = E_{vana} - E_{vfd}',
        calc: (v, r) => r.Evana - r.Evfd, dec: 0 },
      { key: 'Csav', label: 'Economie in bani', unit: 'lei/an', tex: 'C = W\\cdot pret',
        calc: (v, r) => r.Wsav * v.pret, dec: 0 },
    ],
  },
  {
    id: 'randament-pompa',
    family: 'pompe',
    tier: 3,
    title: 'Randament pompa vs debit (BEP)',
    subtitle: 'Putere la arbore reala departe de BEP',
    note: 'η maxim la BEP, scade spre debite mici/mari. La VFD pe debit mic → putere ceruta subestimata cu η constant.',
    fields: [
      { key: 'rho', label: 'Densitate', unit: 'kg/m³', default: 1000, step: 10, min: 1 },
      { key: 'Q', label: 'Debit de lucru', unit: 'm³/h', default: 70, step: 5, min: 0 },
      { key: 'H', label: 'Inaltime', unit: 'm', default: 25, step: 1, min: 0 },
      { key: 'QBEP', label: 'Debit la BEP', unit: 'm³/h', default: 100, step: 5, min: 1 },
      { key: 'etaBEP', label: 'Randament la BEP', unit: '%', default: 78, step: 1, min: 1 },
      { key: 'c', label: 'Curbura η(Q)', unit: '', default: 0.7, step: 0.1, min: 0 },
    ],
    charts: [(v) => ({
      xLabel: 'Debit Q [m³/h]', yLabel: 'Randament η [%]',
      series: [{ label: 'η(Q)', color: COL.a, points: curve(0.2 * v.QBEP, 1.3 * v.QBEP, (Q) => v.etaBEP * (1 - v.c * (Q / v.QBEP - 1) ** 2)) }],
      markers: [{ x: v.Q, y: v.etaBEP * (1 - v.c * (v.Q / v.QBEP - 1) ** 2), label: 'lucru', color: COL.op }],
    })],
    results: [
      { key: 'etaQ', label: 'Randament la debitul de lucru', unit: '%', tex: '\\eta(Q) = \\eta_{BEP}[1-c(Q/Q_{BEP}-1)^2]',
        calc: (v) => v.etaBEP * (1 - v.c * (v.Q / v.QBEP - 1) ** 2), dec: 1 },
      { key: 'Parb', label: 'Putere la arbore', unit: 'kW', tex: 'P = \\dfrac{\\rho g Q H}{1000\\,\\eta(Q)}',
        calc: (v, r) => (r.etaQ > 0 ? (v.rho * 9.81 * (v.Q / 3600) * v.H) / 1000 / (r.etaQ / 100) : null), dec: 2 },
    ],
  },
  {
    id: 'debit-minim',
    family: 'pompe',
    tier: 3,
    title: 'Debit minim stabil (MCSF)',
    subtitle: 'Sub care apare recirculare/instabilitate',
    note: 'Q_min ≈ 10-25% din Q_BEP (functie de tip/turatie specifica). Sub el: incalzire, vibratii, deteriorare.',
    fields: [
      { key: 'QBEP', label: 'Debit la BEP', unit: 'm³/h', default: 100, step: 5, min: 0 },
      { key: 'Qop', label: 'Debit de lucru (min)', unit: 'm³/h', default: 40, step: 5, min: 0 },
    ],
    results: [
      { key: 'Qmin10', label: 'Debit minim (10% BEP)', unit: 'm³/h', tex: '0.10\\,Q_{BEP}',
        calc: (v) => 0.1 * v.QBEP, dec: 1 },
      { key: 'Qmin25', label: 'Debit minim (25% BEP)', unit: 'm³/h', tex: '0.25\\,Q_{BEP}',
        calc: (v) => 0.25 * v.QBEP, dec: 1 },
      { key: 'marja', label: 'Marja fata de 15% BEP', unit: 'm³/h', tex: 'Q_{op} - 0.15\\,Q_{BEP}',
        calc: (v) => v.Qop - 0.15 * v.QBEP, dec: 1 },
    ],
  },
  {
    id: 'trimming-rotor',
    family: 'pompe',
    tier: 3,
    title: 'Trimming rotor (taiere diametru)',
    subtitle: 'Echivalent cu reducere de turatie',
    note: 'Legi de diametru (acelasi rotor): Q~D, H~D², P~D³. Util la decizia trim vs overspeed pe VFD.',
    fields: [
      { key: 'D1', label: 'Diametru initial', unit: 'mm', default: 200, step: 5, min: 1 },
      { key: 'D2', label: 'Diametru taiat', unit: 'mm', default: 180, step: 5, min: 1 },
      { key: 'Q1', label: 'Debit la D1', unit: 'm³/h', default: 100, step: 5, min: 0 },
      { key: 'H1', label: 'Inaltime la D1', unit: 'm', default: 32, step: 1, min: 0 },
      { key: 'P1', label: 'Putere la D1', unit: 'kW', default: 15, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'Q2', label: 'Debit la D2', unit: 'm³/h', tex: 'Q_2 = Q_1(D_2/D_1)',
        calc: (v) => (v.D1 ? v.Q1 * (v.D2 / v.D1) : null), dec: 1 },
      { key: 'H2', label: 'Inaltime la D2', unit: 'm', tex: 'H_2 = H_1(D_2/D_1)^2',
        calc: (v) => (v.D1 ? v.H1 * (v.D2 / v.D1) ** 2 : null), dec: 2 },
      { key: 'P2', label: 'Putere la D2', unit: 'kW', tex: 'P_2 = P_1(D_2/D_1)^3',
        calc: (v) => (v.D1 ? v.P1 * (v.D2 / v.D1) ** 3 : null), dec: 2 },
    ],
  },

  // --- comune ---
  {
    id: 'compresor-volant',
    family: 'comun',
    tier: 3,
    title: 'Compresor cu piston — volant (GD²)',
    subtitle: 'Inertie pt. limitarea pulsatiei de turatie',
    note: 'Cuplu pulsatoriu → trip-uri VFD/vibratii. Coef. neuniformitate Cs ~0.02-0.05.',
    fields: [
      { key: 'dE', label: 'Energie fluctuanta/ciclu', unit: 'J', default: 2000, step: 100, min: 0 },
      { key: 'Cs', label: 'Coef. neuniformitate', unit: '', default: 0.03, step: 0.005, min: 0.001 },
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 500, step: 10, min: 1 },
    ],
    results: [
      { key: 'omega', label: 'Viteza unghiulara', unit: 'rad/s', tex: '\\omega = 2\\pi n/60',
        calc: (v) => omega(v.n), dec: 2 },
      { key: 'Jreq', label: 'Inertie volant necesara', unit: 'kg·m²', tex: 'J = \\dfrac{\\Delta E}{C_s\\,\\omega^2}',
        calc: (v, r) => (v.Cs && r.omega ? v.dE / (v.Cs * r.omega ** 2) : null), dec: 1 },
      { key: 'GD2', label: 'GD² echivalent', unit: 'kg·m²', tex: 'GD^2 = 4 J',
        calc: (v, r) => (r.Jreq != null ? 4 * r.Jreq : null), dec: 1 },
    ],
  },
  {
    id: 'reactor-detunare',
    family: 'comun',
    tier: 3,
    title: 'Reactor de detunare (baterie cond.)',
    subtitle: 'Frecventa de acord si tensiunea condensatoarelor',
    note: 'p=7% (≈189 Hz, sub h5) uzual. Condensatoarele vad o tensiune mai mare → alege-le la tensiune superioara.',
    fields: [
      { key: 'p', label: 'Factor de detunare', unit: '%', default: 7, step: 0.5, min: 0.1 },
      { key: 'f1', label: 'Frecventa retea', unit: 'Hz', default: 50, step: 1, min: 1 },
      { key: 'Un', label: 'Tensiune retea', unit: 'V', default: 400, step: 10, min: 1 },
    ],
    results: [
      { key: 'facord', label: 'Frecventa de acord', unit: 'Hz', tex: 'f = \\dfrac{f_1}{\\sqrt{p/100}}',
        calc: (v) => v.f1 / Math.sqrt(v.p / 100), dec: 0 },
      { key: 'UC', label: 'Tensiune condensatoare', unit: 'V', tex: 'U_C = \\dfrac{U_n}{1-p/100}',
        calc: (v) => v.Un / (1 - v.p / 100), dec: 0 },
    ],
  },
  {
    id: 'factor-k',
    family: 'transformator',
    tier: 3,
    title: 'Factor K transformator (sarcini neliniare)',
    subtitle: 'Supradimensionare pt. armonici (drive-uri)',
    note: 'K mare → pierderi turbionare mari. Alege transformator K-rated (K-4/K-13/K-20) sau deratuieste.',
    fields: [
      { key: 'I5', label: 'Armonica 5', unit: '%', default: 30, step: 1, min: 0 },
      { key: 'I7', label: 'Armonica 7', unit: '%', default: 15, step: 1, min: 0 },
      { key: 'I11', label: 'Armonica 11', unit: '%', default: 9, step: 1, min: 0 },
      { key: 'I13', label: 'Armonica 13', unit: '%', default: 8, step: 1, min: 0 },
    ],
    results: [
      { key: 'K', label: 'Factor K', unit: '', tex: 'K = 1 + \\sum (I_h/I_1)^2 h^2',
        calc: (v) => 1 + (v.I5 / 100) ** 2 * 25 + (v.I7 / 100) ** 2 * 49 + (v.I11 / 100) ** 2 * 121 + (v.I13 / 100) ** 2 * 169, dec: 2 },
    ],
  },
  {
    id: 'factor-putere-vfd',
    family: 'comun',
    tier: 3,
    title: 'Factor de putere front-end VFD',
    subtitle: 'PF real din DPF si THD (punte de diode)',
    note: 'PF (total) ≠ DPF (deplasare). Puntea de diode are DPF ~0.95-0.98 dar PF scazut din cauza THD.',
    fields: [
      { key: 'THD', label: 'THD curent', unit: '%', default: 35, step: 1, min: 0 },
      { key: 'DPF', label: 'Factor deplasare (cos φ1)', unit: '', default: 0.98, step: 0.01, min: 0 },
    ],
    results: [
      { key: 'mu', label: 'Factor de distorsiune', unit: '', tex: '\\mu = \\dfrac{1}{\\sqrt{1+THD^2}}',
        calc: (v) => 1 / Math.sqrt(1 + (v.THD / 100) ** 2), dec: 3 },
      { key: 'PF', label: 'Factor de putere total', unit: '', tex: 'PF = \\mu\\cdot DPF',
        calc: (v, r) => r.mu * v.DPF, dec: 3 },
      { key: 'IsI1', label: 'Curent total / fundamental', unit: '×', tex: 'I_s/I_1 = \\sqrt{1+THD^2}',
        calc: (v) => Math.sqrt(1 + (v.THD / 100) ** 2), dec: 3 },
    ],
  },
  {
    id: 'comparatie-frontend',
    family: 'comun',
    tier: 3,
    title: 'Comparatie front-end (6/12-puls/AFE)',
    subtitle: 'THD tipic vs limita TDD (IEEE 519)',
    note: 'Marja negativa = sub limita (OK). 6-puls ~35%, 12-puls ~11%, AFE ~4% THD tipic.',
    fields: [
      { key: 'ratio', label: 'Raport Isc/IL la PCC', unit: '', default: 85, step: 5, min: 1 },
    ],
    results: [
      { key: 'TDD', label: 'Limita TDD admisa', unit: '%', tex: '\\text{IEEE 519 Tab.2}',
        calc: (v) => { const x = v.ratio; return x < 20 ? 5 : x < 50 ? 8 : x < 100 ? 12 : x < 1000 ? 15 : 20 }, dec: 0 },
      { key: 'm6', label: 'Marja 6-puls (~35%)', unit: '%', tex: '35 - TDD',
        calc: (v, r) => 35 - r.TDD, dec: 0 },
      { key: 'm12', label: 'Marja 12-puls (~11%)', unit: '%', tex: '11 - TDD',
        calc: (v, r) => 11 - r.TDD, dec: 0 },
      { key: 'mafe', label: 'Marja AFE (~4%)', unit: '%', tex: '4 - TDD',
        calc: (v, r) => 4 - r.TDD, dec: 0 },
    ],
  },
  {
    id: 'filtru-iesire',
    family: 'comun',
    tier: 3,
    title: 'Filtru de iesire (du/dt / sinus)',
    subtitle: 'Frecventa de taiere LC',
    note: 'Conditie: f_iesire_max < f_c < f_sw (uzual f_c ≈ f_sw/3...f_sw/5).',
    fields: [
      { key: 'Lf', label: 'Inductanta filtru', unit: 'mH', default: 1, step: 0.1, min: 0.01 },
      { key: 'Cf', label: 'Capacitate filtru', unit: 'µF', default: 10, step: 1, min: 0.1 },
      { key: 'foutmax', label: 'Frecventa iesire max', unit: 'Hz', default: 50, step: 5, min: 1 },
      { key: 'fsw', label: 'Frecventa comutatie', unit: 'kHz', default: 4, step: 0.5, min: 0.5 },
    ],
    results: [
      { key: 'fc', label: 'Frecventa de taiere', unit: 'Hz', tex: 'f_c = \\dfrac{1}{2\\pi\\sqrt{L_f C_f}}',
        calc: (v) => 1 / (2 * Math.PI * Math.sqrt((v.Lf / 1000) * (v.Cf / 1e6))), dec: 0 },
      { key: 'rapfsw', label: 'Raport f_sw / f_c', unit: '×', tex: 'f_{sw}/f_c \\;(3..5)',
        calc: (v, r) => (r.fc ? (v.fsw * 1000) / r.fc : null), dec: 2 },
      { key: 'rapfout', label: 'Raport f_c / f_iesire', unit: '×', tex: 'f_c/f_{out}',
        calc: (v, r) => (v.foutmax ? r.fc / v.foutmax : null), dec: 1 },
    ],
  },
  {
    id: 'kinetic-buffer',
    family: 'comun',
    tier: 3,
    title: 'Kinetic buffering (sustinere din inertie)',
    subtitle: 'Autonomie la microintreruperi din energia cinetica',
    note: 'La inertie mare (ventilatoare) buffering-ul cinetic da autonomie mult > decat condensatorul DC.',
    fields: [
      { key: 'J', label: 'Inertie totala', unit: 'kg·m²', default: 5, step: 0.5, min: 0 },
      { key: 'n', label: 'Turatie', unit: 'rpm', default: 1450, step: 10, min: 0 },
      { key: 'drop', label: 'Scadere turatie permisa', unit: '%', default: 20, step: 1, min: 0 },
      { key: 'Pload', label: 'Putere sarcina', unit: 'kW', default: 15, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'Ekin', label: 'Energie cinetica disponibila', unit: 'J', tex: 'E = \\tfrac{1}{2}J(\\omega_1^2-\\omega_2^2)',
        calc: (v) => { const w1 = omega(v.n); const w2 = w1 * (1 - v.drop / 100); return 0.5 * v.J * (w1 ** 2 - w2 ** 2) }, dec: 0 },
      { key: 'tbuf', label: 'Timp de sustinere', unit: 's', tex: 't = E/P_{sarcina}',
        calc: (v, r) => (v.Pload ? r.Ekin / (v.Pload * 1000) : null), dec: 2 },
    ],
  },
  {
    id: 'contragreutate',
    family: 'comun',
    tier: 3,
    title: 'Contragreutate (ascensor/macara)',
    subtitle: 'Cuplu net cu echilibrare',
    note: 'Echilibrare optima m_cg = m_cabina + ~0.4-0.5·m_sarcina. Semnul F_net se inverseaza cu incarcarea.',
    fields: [
      { key: 'mcabina', label: 'Masa cabina', unit: 'kg', default: 800, step: 50, min: 0 },
      { key: 'msarcina', label: 'Masa sarcina', unit: 'kg', default: 600, step: 50, min: 0 },
      { key: 'mcg', label: 'Masa contragreutate', unit: 'kg', default: 1100, step: 50, min: 0 },
      { key: 'r', label: 'Raza roata/tambur', unit: 'm', default: 0.3, step: 0.05, min: 0.01 },
      { key: 'eta', label: 'Randament', unit: '%', default: 90, step: 1, min: 1 },
    ],
    results: [
      { key: 'Fnet', label: 'Forta neta', unit: 'N', tex: 'F = (m_{cab}+m_{sarc}-m_{cg})g',
        calc: (v) => (v.mcabina + v.msarcina - v.mcg) * 9.81, dec: 0 },
      { key: 'Tmotor', label: 'Cuplu la motor', unit: 'Nm', tex: 'M = F\\,r/\\eta',
        calc: (v, r) => (r.Fnet * v.r) / (v.eta / 100), dec: 0 },
      { key: 'comp', label: 'Grad de compensare', unit: '%', tex: '\\dfrac{m_{cg}}{m_{cab}+m_{sarc}}\\cdot 100',
        calc: (v) => (v.mcg / (v.mcabina + v.msarcina)) * 100, dec: 1 },
    ],
  },
  {
    id: 'taper',
    family: 'comun',
    tier: 3,
    title: 'Control tensiune cu taper (winder)',
    subtitle: 'Scaderea programata a tensiunii spre diametru plin',
    note: 'Taper reduce tensiunea spre rola plina ca sa nu se striveasca straturile interioare.',
    fields: [
      { key: 'Fset', label: 'Tensiune de referinta', unit: 'N', default: 500, step: 10, min: 0 },
      { key: 'taper', label: 'Taper', unit: '%', default: 30, step: 5, min: 0 },
      { key: 'dgol', label: 'Diametru gol', unit: 'm', default: 0.1, step: 0.01, min: 0.001 },
      { key: 'dplin', label: 'Diametru plin', unit: 'm', default: 0.5, step: 0.05, min: 0.001 },
      { key: 'd', label: 'Diametru curent', unit: 'm', default: 0.5, step: 0.05, min: 0.001 },
    ],
    charts: [(v) => {
      const ft = (d) => { const frac = (d - v.dgol) / (v.dplin - v.dgol); return v.Fset * (1 - (v.taper / 100) * frac) }
      return {
        xLabel: 'Diametru d [m]', yLabel: 'Cuplu M [Nm]',
        series: [{ label: 'T(d) cu taper', color: COL.a, points: curve(v.dgol, v.dplin, (d) => (ft(d) * d) / 2) }],
        markers: [{ x: v.d, y: (ft(v.d) * v.d) / 2, label: 'curent', color: COL.op }],
      }
    }],
    results: [
      { key: 'Ftaper', label: 'Tensiune cu taper (la d)', unit: 'N', tex: 'F = F_{set}[1-taper\\cdot\\frac{d-d_{gol}}{d_{plin}-d_{gol}}]',
        calc: (v) => { const frac = (v.d - v.dgol) / (v.dplin - v.dgol); return v.Fset * (1 - (v.taper / 100) * frac) }, dec: 0 },
      { key: 'T', label: 'Cuplu (la d)', unit: 'Nm', tex: 'M = F(d)\\,d/2',
        calc: (v, r) => (r.Ftaper * v.d) / 2, dec: 1 },
    ],
  },

  // --- servo / c.c. ---
  {
    id: 'ipmsm-mtpa',
    family: 'servo',
    tier: 3,
    title: 'IPMSM — cuplu cu reluctanta',
    subtitle: 'Aport reluctanta (Id<0) peste cuplul de magneti',
    note: 'La IPM (Lq>Ld) cu Id<0, termenul de reluctanta adauga cuplu (MTPA) → motor mai mic / curent mai mic.',
    fields: [
      { key: 'ppp', label: 'Perechi de poli', unit: '', default: 4, step: 1, min: 1 },
      { key: 'psim', label: 'Flux magneti permanenti', unit: 'Wb', default: 0.1, step: 0.01, min: 0 },
      { key: 'Ld', label: 'Inductanta Ld', unit: 'mH', default: 8, step: 0.5, min: 0 },
      { key: 'Lq', label: 'Inductanta Lq', unit: 'mH', default: 12, step: 0.5, min: 0 },
      { key: 'Id', label: 'Curent axa d (negativ)', unit: 'A', default: -5, step: 1 },
      { key: 'Iq', label: 'Curent axa q', unit: 'A', default: 8, step: 1, min: 0 },
    ],
    results: [
      { key: 'Mpm', label: 'Cuplu de magneti', unit: 'Nm', tex: 'M_{pm} = \\tfrac{3}{2}p\\,\\psi_m I_q',
        calc: (v) => 1.5 * v.ppp * v.psim * v.Iq, dec: 2 },
      { key: 'Mrel', label: 'Cuplu de reluctanta', unit: 'Nm', tex: 'M_{rel} = \\tfrac{3}{2}p(L_d-L_q)I_d I_q',
        calc: (v) => 1.5 * v.ppp * ((v.Ld - v.Lq) / 1000) * v.Id * v.Iq, dec: 2 },
      { key: 'M', label: 'Cuplu total', unit: 'Nm', tex: 'M = M_{pm} + M_{rel}',
        calc: (v, r) => r.Mpm + r.Mrel, dec: 2 },
    ],
  },
  {
    id: 'suprasarcina-servo',
    family: 'servo',
    tier: 3,
    title: 'Suprasarcina servo (I²t)',
    subtitle: 'Timp admisibil la cuplu de varf',
    note: 'Verifica daca varful de cuplu din profil se incadreaza in fereastra termica a servo/driveului.',
    fields: [
      { key: 'Mvarf', label: 'Cuplu de varf cerut', unit: 'Nm', default: 9, step: 0.5, min: 0 },
      { key: 'Mcont', label: 'Cuplu continuu motor', unit: 'Nm', default: 4, step: 0.5, min: 0.1 },
      { key: 'tau', label: 'Constanta termica', unit: 's', default: 2, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'x', label: 'Raport varf/continuu', unit: '×', tex: 'x = M_{varf}/M_{cont}',
        calc: (v) => (v.Mcont ? v.Mvarf / v.Mcont : null), dec: 2 },
      { key: 'tOL', label: 'Timp admisibil la varf', unit: 's', tex: 't = \\tau\\ln\\dfrac{x^2}{x^2-1}',
        calc: (v, r) => (r.x > 1 ? v.tau * Math.log(r.x ** 2 / (r.x ** 2 - 1)) : null), dec: 2 },
    ],
  },
  {
    id: 'cc-pornire-trepte',
    family: 'cc',
    tier: 3,
    title: 'Rezistente de pornire in trepte (c.c.)',
    subtitle: 'Numar de trepte si valori (progresie geometrica)',
    note: 'Starter rezistiv c.c. (instalatii vechi). Pe fiecare treapta curentul scade de la Imax la Imin.',
    fields: [
      { key: 'U', label: 'Tensiune', unit: 'V', default: 440, step: 10, min: 0 },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', default: 0.15, step: 0.01, min: 0.001 },
      { key: 'Imax', label: 'Curent maxim', unit: 'A', default: 200, step: 10, min: 1 },
      { key: 'Imin', label: 'Curent la trecere', unit: 'A', default: 120, step: 10, min: 1 },
    ],
    results: [
      { key: 'Rtot', label: 'Rezistenta totala pornire', unit: 'Ω', tex: 'R = U/I_{max}',
        calc: (v) => (v.Imax ? v.U / v.Imax : null), dec: 2 },
      { key: 'ratio', label: 'Raport pe treapta', unit: '×', tex: '\\gamma = I_{max}/I_{min}',
        calc: (v) => (v.Imin ? v.Imax / v.Imin : null), dec: 3 },
      { key: 'nsteps', label: 'Numar de trepte', unit: '', tex: 'n = \\lceil\\ln(R/R_a)/\\ln\\gamma\\rceil',
        calc: (v, r) => (r.ratio > 1 && r.Rtot && v.Ra ? Math.ceil(Math.log(r.Rtot / v.Ra) / Math.log(r.ratio)) : null), dec: 0 },
    ],
  },
  {
    id: 'cc-excitatii',
    family: 'cc',
    tier: 2,
    title: 'Motor c.c. — tipuri de excitatie (recunoastere retrofit)',
    subtitle: 'Comparatie n(M): separat / sunt / serie / compus / PMDC',
    note: 'Card de orientare la retrofit: identifica tipul de excitatie inainte de a alege convertorul. (1) SEPARAT EXCITAT: caracteristica dura, cadere liniara mica ($n = n_0 - kM$, ~3-5%); cuplu de pornire bun, controlabil din $I_a$; mers in gol stabil; reglaj excelent (indus + camp independent); slabire de camp 2:1...4:1 prin reducerea $I_f$; aplicatii laminoare, masini-unelte, infasurare (winder); RETROFIT: tinta ideala pentru DCS880 / SINAMICS DCM in 4 cadrane — convertor indus + convertor de camp separat. (2) SUNT / DERIVATIE ($I_f$ din $U_a$): practic identica cu separat excitat la $U$ fix, cadere putin mai mare (~5-8%); pornire si mers in gol stabile; slabire de camp posibila; aplicatii ventilatoare, pompe, masini-unelte vechi; RETROFIT: se conduce ca separat excitat — campul se MUTA pe iesirea de camp dedicata a drive-ului, altfel slabirea de camp si limitarea $E$ nu functioneaza. (3) SERIE ($I_f = I_a$): caracteristica MOALE, foarte cazatoare $n \\propto 1/\\sqrt{M}$ (in zona nesaturata); cuplu de pornire foarte mare ($M \\propto I_a^2$); PERICOL DE AMBALARE LA GOL ($n \\to \\infty$ cand $M \\to 0$); aplicatii tractiune, demaroare, macarale vechi; RETROFIT: dificil — un drive standard cu camp separat NU reproduce serie; se pastreaza conexiunea serie si se conduce doar pe indus, OBLIGATORIU cu sarcina minima/cuplaj permanent si supraviteza configurata, sau se reproiecteaza ca separat excitat. (4) COMPUS CUMULATIV (serie + sunt, fluxuri in acelasi sens): intre sunt si serie — cuplu de pornire mare DAR fara ambalare la gol (campul sunt limiteaza $n$); cadere moderata (~10-25%); aplicatii prese, foarfece, laminoare cu soc; RETROFIT: campul sunt pe iesirea de camp, infasurarea serie ramane in indus; verifica polaritatea ca sa ramana cumulativ. (5) COMPUS DIFERENTIAL (serie opus sunt): caracteristica aproape orizontala sau URCATOARE cu sarcina, INSTABILA, rar folosita; RETROFIT: se reconfigureaza ca separat/sunt (se elimina sau se inverseaza infasurarea serie). (6) MAGNET PERMANENT (PMDC): flux fix din magneti, fara $I_f$; cadere doar din $R_a$ (~3-6%); reglaj NUMAI prin tensiune de indus; FARA slabire de camp -> turatie max plafonata; aplicatii servo mici; RETROFIT: convertor pe indus FARA convertor de camp; atentie la demagnetizare la curent de varf si la lipsa zonei de putere constanta.',
    params: 'DCS880: convertor camp / FEX, mod EMF&camp 28.17, turatie baza 99.14, supraviteza 30.16 · SINAMICS DCM: mod camp p50080 (1=intern), EMF p50115, supraviteza p50272 — la retrofit serie/diferential se reconfigureaza obligatoriu pe excitatie separata',
    charts: [(v) => ({
      xLabel: 'Cuplu M [× M_n]', yLabel: 'Turatie n [× n_n]',
      series: [
        { label: 'Separat excitat', color: COL.a, points: curve(0, 2, (M) => 1.05 - 0.05 * M) },
        { label: 'Magnet permanent (PMDC)', color: 'var(--chart-1)', dash: true, points: curve(0, 2, (M) => 1.06 - 0.06 * M) },
        { label: 'Sunt (derivatie)', color: COL.b, points: curve(0, 2, (M) => 1.08 - 0.08 * M) },
        { label: 'Compus cumulativ', color: 'var(--chart-2)', points: curve(0, 2, (M) => 1.20 - 0.20 * M) },
        { label: 'Compus diferential (instabil)', color: 'var(--chart-3)', dash: true, points: curve(0, 2, (M) => 0.95 + 0.07 * M) },
        { label: 'Serie (ambalare la gol)', color: COL.c, points: curve(0.05, 2, (M) => (M > 0 ? 1 / Math.sqrt(M) : null)) },
      ],
    })],
    fields: [
      { key: 'xload', label: 'Fractie de sarcina (M/Mₙ)', unit: '×', default: 0.25, step: 0.05, min: 0.01 },
      { key: 'dropSunt', label: 'Cadere turatie sunt/sep la Mₙ', unit: '%', default: 6, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'nSerie', label: 'Turatie motor serie (× nₙ, nesaturat)', unit: '×', tex: '\\dfrac{n}{n_n} \\approx \\dfrac{1}{\\sqrt{M/M_n}}',
        calc: (v) => (v.xload > 0 ? 1 / Math.sqrt(v.xload) : null), dec: 2 },
      { key: 'nSep', label: 'Turatie sep/sunt (× nₙ)', unit: '×', tex: '\\dfrac{n}{n_n} = 1 + \\dfrac{d}{100}\\left(1 - \\dfrac{M}{M_n}\\right)',
        calc: (v) => 1 + (v.dropSunt / 100) * (1 - v.xload), dec: 3 },
      { key: 'regSep', label: 'Reglaj de turatie sep/sunt', unit: '%', tex: '\\delta = \\dfrac{n_0 - n_n}{n_n}\\cdot 100 = d',
        calc: (v) => v.dropSunt, dec: 1 },
    ],
  },
  {
    id: 'cc-camp',
    family: 'cc',
    tier: 3,
    title: 'Circuit de excitatie (camp) c.c.',
    subtitle: 'Curent de camp, constanta de timp, fortare si economie',
    note: 'Excitatie separata: $I_f = U_f/R_f$, $P_f = U_f I_f = U_f^2/R_f$ (la regim stationar campul e pur rezistiv). Constanta de timp a infasurarii de camp $\\tau_f = L_f/R_f$ poate ajunge la ordinul secundelor, deci fluxul se schimba lent. Stabilizare normala in $\\approx 3\\tau_f$. Fortarea aplica tranzitoriu o tensiune marita $U_{forc} = k_{forc}\\,U_f$: curentul tinde catre $k_{forc} I_f$ dar e limitat la $I_f$, deci atinge tinta in $t_{forc} = \\tau_f\\ln\\dfrac{k_{forc}}{k_{forc}-1}$ (de cateva ori mai rapid). La stationare cu motor oprit se reduce $I_f$ (economie de camp, $r_{ec}$) ca sa se limiteze incalzirea: pierderile scad cu $r_{ec}^2$. ATENTIE: nu se slabeste campul sub minimul de magnetizare cat timp masina trebuie sa dezvolte cuplu.',
    params: 'DCS880 FEX (field exciter): mod camp 28.10, EMF/field control 28.17, fortare camp 28.14, reducere la oprire 28.18 · Siemens DCM: p50080 (mod), p50100 (I_f nominal), curba magnetizare p50105 · Inversare de camp pentru 4Q cand indusul e nereversibil. Retrofit: masoara R_f la cald si verifica L_f din manual ca sa setezi corect bucla de camp.',
    charts: [(v) => {
      if (!v.Rf || !v.Lf) return null
      const If = v.Uf / v.Rf, tau = v.Lf / v.Rf
      const tmax = Math.max(3.2 * tau, 0.1)
      const cu = (t) => Math.min(If, v.kforc * If * (1 - Math.exp(-t / tau)))
      const fara = (t) => If * (1 - Math.exp(-t / tau))
      const tf = v.kforc > 1 ? tau * Math.log(v.kforc / (v.kforc - 1)) : null
      return {
        xLabel: 'Timp t [s]', yLabel: 'Curent de camp I_f [A]',
        series: [
          { label: 'cu fortare (' + v.kforc + '×)', color: COL.a, points: curve(0, tmax, cu) },
          { label: 'fara fortare', color: COL.b, dash: true, points: curve(0, tmax, fara) },
        ],
        markers: tf != null && tf <= tmax ? [{ x: tf, y: If, label: 'fortare atinge I_f', color: COL.op }] : [],
      }
    }],
    fields: [
      { key: 'Uf', label: 'Tensiune de camp', unit: 'V', default: 310, step: 5, min: 0 },
      { key: 'Rf', label: 'Rezistenta camp', unit: 'Ω', default: 35, step: 1, min: 0.1 },
      { key: 'Lf', label: 'Inductanta camp', unit: 'H', default: 12, step: 0.5, min: 0.01 },
      { key: 'kforc', label: 'Factor de fortare (boost)', unit: '×', default: 2, step: 0.1, min: 1.05 },
      { key: 'rec', label: 'Reducere camp la oprire', unit: '×', default: 0.5, step: 0.05, min: 0.05 },
    ],
    results: [
      { key: 'If', label: 'Curent de camp', unit: 'A', tex: 'I_f = \\dfrac{U_f}{R_f}',
        calc: (v) => (v.Rf ? v.Uf / v.Rf : null), dec: 2 },
      { key: 'Pf', label: 'Pierderi de camp', unit: 'W', tex: 'P_f = U_f I_f = \\dfrac{U_f^2}{R_f}',
        calc: (v) => (v.Rf ? (v.Uf * v.Uf) / v.Rf : null), dec: 0 },
      { key: 'tauf', label: 'Constanta de timp de camp', unit: 's', tex: '\\tau_f = \\dfrac{L_f}{R_f}',
        calc: (v) => (v.Rf ? v.Lf / v.Rf : null), dec: 2 },
      { key: 'tset', label: 'Stabilizare fara fortare (≈3τ)', unit: 's', tex: 't_{stab} \\approx 3\\,\\tau_f',
        calc: (v) => (v.Rf ? (3 * v.Lf) / v.Rf : null), dec: 2 },
      { key: 'tforc', label: 'Stabilizare cu fortare', unit: 's', tex: 't_{forc} = \\tau_f\\ln\\dfrac{k_{forc}}{k_{forc}-1}',
        calc: (v) => (v.Rf && v.kforc > 1 ? (v.Lf / v.Rf) * Math.log(v.kforc / (v.kforc - 1)) : null), dec: 2 },
      { key: 'Pec', label: 'Pierderi la oprire (economie)', unit: 'W', tex: 'P_{ec} = r_{ec}^2\\,P_f',
        calc: (v) => (v.Rf ? v.rec * v.rec * (v.Uf * v.Uf) / v.Rf : null), dec: 0 },
    ],
  },
  {
    id: 'cc-comutatie',
    family: 'cc',
    tier: 3,
    title: 'Motor c.c. — comutatie & reactia indusului',
    subtitle: 'Viteza periferica colector si limita de slabire de camp',
    note: 'Viteza periferica a colectorului $v=\\pi D n_{max}/60$ trebuie limitata la $\\approx 30$–$40$ m/s (lamele, perii, scantei). Raportul de slabire de camp $n_{max}/n_{baza}$ este limitat de comutatie: tipic $\\approx 3{:}1$ fara masuri, pana la $4{:}1\\dots6{:}1$ cu infasurare de compensare. Polii auxiliari (de comutatie) genereaza o t.e.m. de comutatie care anuleaza tensiunea de reactanta (t.e.m. de autoinductie a bobinei in scurtcircuit sub perii) si compenseaza reactia indusului in zona neutra; infasurarea de compensare anuleaza distorsiunea fluxului sub talpa polara. Depasirea limitelor → scantei la perii, arc inelar (flashover), uzura colector.',
    params: 'DCS880: turatie max 30.12, turatie baza 99.14, EMF/field mode 28.17 · Siemens DCM: p50081 (n_max), p50115 (n_baza/field weakening)',
    charts: [
      (v) => {
        const nm = Math.max(v.nmax, v.nbaza * 1.05)
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Viteza periferica v [m/s]',
          series: [
            { label: 'v = πDn/60', color: COL.a, points: curve(0, nm, (n) => (Math.PI * (v.D / 1000) * n) / 60) },
            { label: 'limita 40 m/s', color: COL.c, dash: true, points: curve(0, nm, () => 40) },
            { label: 'limita 30 m/s', color: COL.b, dash: true, points: curve(0, nm, () => 30) },
          ],
          markers: [{ x: v.nmax, y: (Math.PI * (v.D / 1000) * v.nmax) / 60, label: 'n max', color: COL.op }],
        }
      },
      (v) => {
        if (!v.nbaza) return null
        const nm = Math.max(v.nmax, v.nbaza * 1.05)
        const M = (n) => (n <= v.nbaza ? 1 : v.nbaza / n)
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu relativ M/M_n',
          series: [{ label: 'M disponibil (∝1/n in slabire)', color: COL.a, points: curve(0, nm, M) }],
          markers: [{ x: v.nbaza, y: 1, label: 'n baza', color: COL.op }, { x: v.nmax, y: v.nbaza / v.nmax, label: 'n max', color: COL.c }],
        }
      },
    ],
    fields: [
      { key: 'D', label: 'Diametru colector', unit: 'mm', default: 250, step: 5, min: 1 },
      { key: 'nbaza', label: 'Turatie de baza', unit: 'rpm', default: 1500, step: 10, min: 1 },
      { key: 'nmax', label: 'Turatie maxima', unit: 'rpm', default: 3000, step: 10, min: 1 },
    ],
    results: [
      { key: 'vperif', label: 'Viteza periferica colector', unit: 'm/s', tex: 'v = \\dfrac{\\pi D\\,n_{max}}{60}',
        calc: (v) => (Math.PI * (v.D / 1000) * v.nmax) / 60, dec: 1 },
      { key: 'ratio', label: 'Raport slabire de camp', unit: ':1', tex: 'k = \\dfrac{n_{max}}{n_{baza}}',
        calc: (v) => (v.nbaza ? v.nmax / v.nbaza : null), dec: 2 },
      { key: 'Dmax', label: 'Diametru colector max (la 40 m/s)', unit: 'mm', tex: 'D_{max} = \\dfrac{60\\cdot 40}{\\pi\\,n_{max}}\\cdot 10^{3}',
        calc: (v) => (v.nmax ? ((60 * 40) / (Math.PI * v.nmax)) * 1000 : null), dec: 0 },
    ],
  },
  {
    id: 'cc-factor-forma',
    family: 'cc',
    tier: 3,
    title: 'Factor de forma curent c.c. (ondulatie tiristoare)',
    subtitle: 'kf = Irms/Imed, incalzire ~ kf², conductie intrerupta',
    note: 'Motorul c.c. alimentat de la redresor cu tiristoare vede un curent ondulat: factorul de forma $k_f = I_{rms}/I_{med} \\ge 1$ (ideal 1.0 la curent perfect neted). Pierderile in indus cresc cu $k_f^2$, deci curentul mediu admis se derateaza la $I_{med,max} = I_n/k_f$ pentru a pastra incalzirea nominala. Puntea pe 12 pulsuri injumatateste aproximativ ondulatia fata de 6 pulsuri; bobina de netezire (mareste $L_a$) reduce $k_f$. La sarcina mica / turatie joasa apare conductie intrerupta care creste $k_f$ si modifica amplificarea buclei de curent (foloseste $k_f$ real masurat, nu cel de placa). Motorul trebuie ales/deratat pentru alimentare de la convertor (factor de forma — IEC 60034-1), tipic la retrofit cu actionare veche.',
    params: 'DCS880: bobina de netezire L_a (4Q); Siemens DCM: p50078 (numar pulsuri 6/12), date placuta motor pt curent admis',
    charts: [(v) => ({
      xLabel: 'Factor de forma k_f', yLabel: 'Factor pierderi k_f^2',
      series: [{ label: 'k_f² (incalzire relativa)', color: COL.a, points: curve(1, 1.6, (kf) => kf * kf) }],
      markers: [{ x: v.kf, y: v.kf * v.kf, label: 'punct lucru', color: COL.op }],
    })],
    fields: [
      { key: 'Imed', label: 'Curent mediu indus', unit: 'A', default: 80, step: 5, min: 0 },
      { key: 'kf', label: 'Factor de forma', unit: '', default: 1.1, step: 0.01, min: 1 },
      { key: 'In', label: 'Curent nominal motor', unit: 'A', default: 100, step: 5, min: 1 },
      { key: 'kf6', label: 'Factor de forma 6 pulsuri', unit: '', default: 1.1, step: 0.01, min: 1 },
    ],
    results: [
      { key: 'Irms', label: 'Curent termic echivalent (rms)', unit: 'A', tex: 'I_{rms} = k_f\\,I_{med}',
        calc: (v) => v.kf * v.Imed, dec: 1 },
      { key: 'floss', label: 'Factor pierderi suplimentare indus', unit: '×', tex: 'f = k_f^2',
        calc: (v) => v.kf * v.kf, dec: 3 },
      { key: 'ripple', label: 'Factor de ondulatie', unit: '', tex: 'RF = \\sqrt{k_f^2 - 1}',
        calc: (v) => (v.kf >= 1 ? Math.sqrt(v.kf * v.kf - 1) : null), dec: 3 },
      { key: 'Imedmax', label: 'Curent mediu admis (deratat)', unit: 'A', tex: 'I_{med,max} = I_n/k_f',
        calc: (v) => (v.kf > 0 ? v.In / v.kf : null), dec: 1 },
      { key: 'kf12', label: 'Factor de forma estimat 12 pulsuri', unit: '', tex: 'k_{f,12} \\approx \\sqrt{1 + \\tfrac14(k_{f,6}^2-1)}',
        calc: (v) => (v.kf6 >= 1 ? Math.sqrt(1 + 0.25 * (v.kf6 * v.kf6 - 1)) : null), dec: 3 },
    ],
  },
  {
    id: 'cc-franare',
    family: 'cc',
    tier: 3,
    title: 'Motor c.c. — franare (dinamica / recuperativa)',
    subtitle: 'Franare reostatica pe R_b, recuperare 4 cadrane, plugging',
    note: 'La franare dinamica indusul se deconecteaza de la convertor si se inchide pe rezistorul $R_b$: masina lucreaza ca generator, $I_b = E/(R_a+R_b)$ se inverseaza fata de regimul de motor, deci $M_b = k\\Phi I_b$ devine cuplu de franare. Alege $R_b \\geq E/I_{max}-R_a$ ca varful de curent la comutare sa nu depaseasca $I_{max}$. Pe masura ce turatia scade, $E \\propto n$ scade, deci $I_b$ si $M_b$ scad liniar cu $n$ si se anuleaza la $n=0$ — franarea dinamica e slaba la turatie mica (eventual frana mecanica de tinere). Convertor 1Q (o punte) NU poate recupera energia in retea, necesita rezistor de franare; convertor 4Q (dubla punte antiparalel sau inversare de camp) recupereaza energia in retea (cadranele II/IV). Plugging (inversarea tensiunii pe indus la turatie nenula) da $I=(U+E)/(R_a+R_b)$, foarte dur — uzual evitat. Retrofit: daca driveul vechi e 1Q, un rezistor de franare ofera doar disipare; recuperarea in retea cere upgrade la 4Q.',
    params: 'DCS880: tip punte 2Q/4Q, Ra 27.32, limita curent 30.12 · Siemens DCM: 1Q/4Q tip punte, p50110 (Ra), p50100 (I_nom)',
    charts: [
      (v) => {
        const Rt = v.Ra + v.Rb
        if (!(Rt > 0)) return null
        const Ibf = (nn) => (v.kPhi * (2 * Math.PI * nn) / 60) / Rt
        const Mbf = (nn) => v.kPhi * Ibf(nn)
        const nmax = Math.max(v.n, 1)
        return {
          xLabel: 'Turatie n [rpm]', yLabel: 'Cuplu M_b [Nm] / Curent I_b [A]',
          series: [
            { label: 'Cuplu franare M_b', color: COL.a, points: curve(0, nmax, Mbf) },
            { label: 'Curent franare I_b', color: COL.b, dash: true, points: curve(0, nmax, Ibf) },
          ],
        }
      },
      (v) => {
        const E = (v.kPhi * (2 * Math.PI * v.n)) / 60
        const rbmin = v.Imax > 0 ? Math.max(0, E / v.Imax - v.Ra) : 0
        const rmax = Math.max(rbmin * 3, v.Rb * 2, 1)
        const Ibf = (rb) => { const dd = v.Ra + rb; return dd > 0 ? E / dd : null }
        return {
          xLabel: 'Rezistenta de franare R_b [Ω]', yLabel: 'Curent initial I_b [A]',
          series: [
            { label: 'I_b(R_b)', color: COL.a, points: curve(0.01, rmax, Ibf) },
            { label: 'I_max', color: COL.c, dash: true, points: curve(0.01, rmax, () => v.Imax) },
          ],
        }
      },
    ],
    fields: [
      { key: 'n', label: 'Turatie initiala', unit: 'rpm', default: 1500, step: 10, min: 0 },
      { key: 'kPhi', label: 'Constanta masinii (k·Φ)', unit: 'V·s/rad', default: 2.6, step: 0.1, min: 0.01 },
      { key: 'Ra', label: 'Rezistenta indus', unit: 'Ω', default: 0.15, step: 0.01, min: 0 },
      { key: 'Rb', label: 'Rezistenta de franare', unit: 'Ω', default: 2.5, step: 0.1, min: 0 },
      { key: 'Imax', label: 'Curent max admis', unit: 'A', default: 160, step: 5, min: 1 },
    ],
    results: [
      { key: 'E', label: 'T.c.e.m. la turatia initiala', unit: 'V', tex: 'E = k\\Phi\\,\\omega = k\\Phi\\dfrac{2\\pi n}{60}',
        calc: (v) => (v.kPhi * (2 * Math.PI * v.n)) / 60, dec: 1 },
      { key: 'Ib', label: 'Curent initial de franare', unit: 'A', tex: 'I_b = \\dfrac{E}{R_a + R_b}',
        calc: (v, r) => ((v.Ra + v.Rb) > 0 ? r.E / (v.Ra + v.Rb) : null), dec: 1 },
      { key: 'Mb', label: 'Cuplu initial de franare', unit: 'Nm', tex: 'M_b = k\\Phi\\,I_b',
        calc: (v, r) => (r.Ib == null ? null : v.kPhi * r.Ib), dec: 1 },
      { key: 'Rbmin', label: 'R_b minim pt. I ≤ I_max', unit: 'Ω', tex: 'R_{b,min} = \\max\\!\\left(0,\\;\\dfrac{E}{I_{max}} - R_a\\right)',
        calc: (v, r) => (v.Imax > 0 ? Math.max(0, r.E / v.Imax - v.Ra) : null), dec: 3 },
      { key: 'Pb0', label: 'Putere disipata initial in R_b', unit: 'kW', tex: 'P_{R_b} = I_b^2 R_b',
        calc: (v, r) => (r.Ib == null ? null : (r.Ib * r.Ib * v.Rb) / 1000), dec: 2 },
    ],
  },

  // --- sincron ---
  {
    id: 'vcurves',
    family: 'sincron',
    tier: 3,
    title: 'Sincron — curbele in V',
    subtitle: 'Curent stator vs excitatie la putere constanta',
    note: 'Ia minim la cos φ=1. Subexcitat → inductiv; supraexcitat → capacitiv (compensator sincron).',
    fields: [
      { key: 'U', label: 'Tensiune linie', unit: 'V', default: 400, step: 10, min: 1 },
      { key: 'P', label: 'Putere', unit: 'kW', default: 50, step: 5, min: 0 },
      { key: 'Xs', label: 'Reactanta sincrona', unit: 'Ω', default: 2.5, step: 0.1, min: 0.01 },
    ],
    charts: [(v) => {
      const Pw = v.P * 1000
      const k = (Pw * v.Xs) / v.U
      const Ia = (E) => { if (E < k) return null; const sind = k / E; const cosd = Math.sqrt(Math.max(0, 1 - sind ** 2)); const Q = (v.U * E * cosd - v.U ** 2) / v.Xs; return Math.sqrt(Pw ** 2 + Q ** 2) / (SQRT3 * v.U) }
      const Eu = Math.sqrt(v.U ** 2 + k ** 2)
      return {
        xLabel: 'T.e.m. de excitatie E [V]', yLabel: 'Curent stator Ia [A]',
        series: [{ label: 'Ia(E) la P const', color: COL.a, points: curve(k * 1.05, Eu * 1.8, Ia).filter((p) => p.y != null) }],
        markers: [{ x: Eu, y: Pw / (SQRT3 * v.U), label: 'cos φ=1', color: COL.op }],
      }
    }],
    results: [
      { key: 'Eunit', label: 'T.e.m. la cos φ=1', unit: 'V', tex: 'E = \\sqrt{U^2 + (P X_s/U)^2}',
        calc: (v) => Math.sqrt(v.U ** 2 + ((v.P * 1000 * v.Xs) / v.U) ** 2), dec: 1 },
      { key: 'Iamin', label: 'Curent stator minim', unit: 'A', tex: 'I_{a,min} = \\dfrac{P}{\\sqrt{3}\\,U}',
        calc: (v) => (v.P * 1000) / (SQRT3 * v.U), dec: 1 },
    ],
  },
  // ===================================== ADAUGIRI PIF (verificare 2026, surse IEC/EN): teste & dimensionari de teren
  {
    id: 'izolatie',
    family: 'comun',
    tier: 2,
    title: 'Rezistenta de izolatie & PI',
    subtitle: 'Megohmmetru — primul test inainte de energizare',
    note: 'DECONECTEAZA convertizorul inainte de masurare (tensiunea de test distruge IGBT-urile). PI>=2 bun, 1-2 suspect, <1 necesita uscare. La rece valorile sunt mai mari (corectie ~dublare la fiecare 10K). Test obligatoriu la PIF inainte de prima energizare.',
    params: 'Megohmmetru 500/1000 V (JT)',
    fields: [
      { key: 'Un', label: 'Tensiune nominala', unit: 'kV', default: 0.4, step: 0.1, min: 0.1 },
      { key: 'Riso1', label: 'R izolatie la 1 min', unit: 'MΩ', default: 200, step: 10, min: 0 },
      { key: 'Riso10', label: 'R izolatie la 10 min', unit: 'MΩ', default: 500, step: 10, min: 0 },
      { key: 'Riso30', label: 'R izolatie la 30 s', unit: 'MΩ', default: 150, step: 10, min: 0 },
      { key: 'Riso60', label: 'R izolatie la 60 s', unit: 'MΩ', default: 220, step: 10, min: 0 },
    ],
    results: [
      { key: 'IRmin', label: 'IR minim admis (40°C)', unit: 'MΩ', tex: 'IR_{min} = U_n[\\mathrm{kV}] + 1',
        calc: (v) => v.Un + 1, dec: 1 },
      { key: 'PI', label: 'Indice de polarizare', unit: '', tex: 'PI = \\dfrac{R_{10\\,min}}{R_{1\\,min}}',
        calc: (v) => (v.Riso1 ? v.Riso10 / v.Riso1 : null), dec: 2 },
      { key: 'DAR', label: 'Raport absorbtie dielectrica', unit: '', tex: 'DAR = \\dfrac{R_{60s}}{R_{30s}}',
        calc: (v) => (v.Riso30 ? v.Riso60 / v.Riso30 : null), dec: 2 },
    ],
  },
  {
    id: 'run-up',
    family: 'comun',
    tier: 2,
    title: 'Timp de pornire vs timp termic',
    subtitle: 'Demaraj < timp admis la rotor blocat',
    note: 'Conditie PIF: t_pornire < timpul admis la rotor blocat (la rece SI la cald). Altfel motorul se arde la pornire sau protectia declanseaza pe demaraj. Seteaza clasa de declansare a releului termic peste curba de pornire.',
    fields: [
      { key: 'J', label: 'Inertie totala (la ax motor)', unit: 'kg·m²', default: 2, step: 0.1, min: 0 },
      { key: 'nnom', label: 'Turatie nominala', unit: 'rpm', default: 1480, step: 10, min: 1 },
      { key: 'Macc', label: 'Cuplu mediu de accelerare net', unit: 'Nm', default: 80, step: 5, min: 0.1 },
      { key: 'tstall', label: 'Timp admis rotor blocat (cald)', unit: 's', default: 10, step: 1, min: 0.1 },
    ],
    results: [
      { key: 'wn', label: 'Viteza unghiulara nominala', unit: 'rad/s', tex: '\\omega_n = \\dfrac{2\\pi n_{nom}}{60}',
        calc: (v) => (2 * Math.PI * v.nnom) / 60, dec: 1 },
      { key: 'tstart', label: 'Timp de pornire', unit: 's', tex: 't_{start} = \\dfrac{J\\,\\omega_n}{M_{acc}}',
        calc: (v) => (v.Macc ? (v.J * ((2 * Math.PI * v.nnom) / 60)) / v.Macc : null), dec: 2 },
      { key: 'marjat', label: 'Marja (t_stall - t_start)', unit: 's', tex: 't_{stall} - t_{start}',
        calc: (v) => v.tstall - (v.Macc ? (v.J * ((2 * Math.PI * v.nnom) / 60)) / v.Macc : 0), dec: 2 },
    ],
  },
  {
    id: 'franare-rezistenta',
    family: 'comun',
    tier: 3,
    title: 'Rezistenta de franare (dimensionare)',
    subtitle: 'Energie regenerativa la decelerare → evita trip OV DC',
    note: 'La decelerare/coborare motorul devine generator si bus-ul DC urca. Daca apare trip OVERVOLTAGE, ai nevoie de rezistenta de franare. Prag chopper ~780 V (retea 400 V). R intre R_min al drive-ului si R_max calculat.',
    fields: [
      { key: 'J', label: 'Inertie totala', unit: 'kg·m²', default: 5, step: 0.5, min: 0 },
      { key: 'n1', label: 'Turatie initiala', unit: 'rpm', default: 1480, step: 10, min: 0 },
      { key: 'n2', label: 'Turatie finala', unit: 'rpm', default: 0, step: 10, min: 0 },
      { key: 'tdec', label: 'Timp de decelerare', unit: 's', default: 5, step: 0.5, min: 0.1 },
      { key: 'Uchop', label: 'Prag chopper DC', unit: 'V', default: 780, step: 10, min: 1 },
      { key: 'DC', label: 'Durata de conectare', unit: '%', default: 20, step: 5, min: 1 },
    ],
    results: [
      { key: 'Ebr', label: 'Energie de franat', unit: 'kJ', tex: 'E = \\tfrac{1}{2}J(\\omega_1^2 - \\omega_2^2)',
        calc: (v) => (0.5 * v.J * (((2 * Math.PI * v.n1) / 60) ** 2 - ((2 * Math.PI * v.n2) / 60) ** 2)) / 1000, dec: 2 },
      { key: 'Ppk', label: 'Putere de varf de franare', unit: 'kW', tex: 'P_{peak} = E/t_{dec}',
        calc: (v, r) => (v.tdec ? r.Ebr / v.tdec : null), dec: 2 },
      { key: 'Rmax', label: 'Rezistenta maxima', unit: 'Ω', tex: 'R_{max} = \\dfrac{U_{chop}^2}{P_{peak}}',
        calc: (v, r) => (r.Ppk ? (v.Uchop ** 2) / (r.Ppk * 1000) : null), dec: 1 },
      { key: 'Pmed', label: 'Putere medie rezistenta', unit: 'kW', tex: 'P_{med} = P_{peak}\\cdot \\tfrac{DC}{100}',
        calc: (v, r) => (r.Ppk ? r.Ppk * (v.DC / 100) : null), dec: 2 },
    ],
  },
  {
    id: 'encoder-offset',
    family: 'servo',
    tier: 3,
    title: 'Offset comutatie encoder/resolver',
    subtitle: 'Alinierea unghiului electric la axa magnetica (phasing)',
    note: 'Pas obligatoriu la PIF servo/PMSM: ruleaza autophasing-ul drive-ului (ABB autophasing; Siemens pole position p1990/p1980). Eroare de aliniere => cuplu redus, supracurent, motor care fuge sau fault la enable.',
    fields: [
      { key: 'ppp', label: 'Perechi de poli', unit: '', default: 4, step: 1, min: 1 },
      { key: 'dthmec', label: 'Eroare aliniere (mecanic)', unit: '°', default: 1, step: 0.5, min: 0 },
      { key: 'Mmax', label: 'Cuplu maxim (aliniat)', unit: 'Nm', default: 10, step: 0.5, min: 0 },
    ],
    results: [
      { key: 'dthel', label: 'Eroare unghi electric', unit: '°', tex: '\\Delta\\theta_{el} = p\\,\\Delta\\theta_{mec}',
        calc: (v) => v.ppp * v.dthmec, dec: 1 },
      { key: 'Mprod', label: 'Cuplu produs', unit: 'Nm', tex: 'M = M_{max}\\cos(\\Delta\\theta_{el})',
        calc: (v) => v.Mmax * Math.cos(rad(v.ppp * v.dthmec)), dec: 2 },
      { key: 'pierdcup', label: 'Pierdere de cuplu', unit: '%', tex: '(1-\\cos\\Delta\\theta_{el})\\cdot 100',
        calc: (v) => (1 - Math.cos(rad(v.ppp * v.dthmec))) * 100, dec: 1 },
    ],
  },
  {
    id: 'notch-rezonanta',
    family: 'servo',
    tier: 3,
    title: 'Rezonanta mecanica & filtru notch',
    subtitle: 'Sistem cu 2 inertii (cuplaj elastic)',
    note: 'Vibratie/oscilatie la o anumita turatie = rezonanta torsionala a cuplajului. Pune un filtru notch la f_rez ca sa cresti banda buclei de viteza. K_tor = rigiditatea torsionala a cuplajului.',
    fields: [
      { key: 'Ktor', label: 'Rigiditate torsionala cuplaj', unit: 'Nm/rad', default: 5000, step: 100, min: 1 },
      { key: 'Jmot', label: 'Inertie motor', unit: 'kg·m²', default: 0.01, step: 0.001, min: 0.0001 },
      { key: 'Jsarc', label: 'Inertie sarcina', unit: 'kg·m²', default: 0.05, step: 0.001, min: 0.0001 },
    ],
    results: [
      { key: 'frez', label: 'Frecventa de rezonanta', unit: 'Hz', tex: 'f_{rez} = \\dfrac{1}{2\\pi}\\sqrt{K_{tor}\\left(\\dfrac{1}{J_{mot}}+\\dfrac{1}{J_{sarc}}\\right)}',
        calc: (v) => (1 / (2 * Math.PI)) * Math.sqrt(v.Ktor * (1 / v.Jmot + 1 / v.Jsarc)), dec: 1 },
      { key: 'fanti', label: 'Frecventa de antirezonanta', unit: 'Hz', tex: 'f_{ar} = \\dfrac{1}{2\\pi}\\sqrt{K_{tor}/J_{sarc}}',
        calc: (v) => (1 / (2 * Math.PI)) * Math.sqrt(v.Ktor / v.Jsarc), dec: 1 },
    ],
  },
  {
    id: 'sto-ss1',
    family: 'comun',
    tier: 3,
    title: 'STO / SS1 (oprire de siguranta)',
    subtitle: 'Validare functie de siguranta la PIF',
    note: 'STO = oprire cat.0 (cuplu taiat imediat, necontrolat). SS1 = rampa controlata, apoi STO (cat.1). Validare functionala documentata ceruta de evaluarea de risc. Verifica daca rampa SS1 opreste in zona sigura inainte de STO.',
    fields: [
      { key: 'n', label: 'Turatie la declansare', unit: 'rpm', default: 1500, step: 10, min: 0 },
      { key: 'tdec', label: 'Timp rampa SS1', unit: 's', default: 2, step: 0.1, min: 0.01 },
      { key: 'i', label: 'Raport transmisie', unit: ':1', default: 1, step: 1, min: 0.01 },
      { key: 'pas', label: 'Avans pe rotatie (liniar)', unit: 'mm/rot', default: 0, step: 1, min: 0 },
    ],
    results: [
      { key: 'Nrot', label: 'Rotatii motor pana la oprire', unit: 'rot', tex: 'N = \\tfrac{1}{2}\\dfrac{n}{60}\\,t_{dec}',
        calc: (v) => 0.5 * (v.n / 60) * v.tdec, dec: 2 },
      { key: 'unghiopr', label: 'Unghi la iesire', unit: '°', tex: '\\theta = 360\\,N/i',
        calc: (v) => (v.i ? (360 * (0.5 * (v.n / 60) * v.tdec)) / v.i : null), dec: 0 },
      { key: 'distopr', label: 'Distanta liniara de oprire', unit: 'mm', tex: 's = N\\,p_{as}/i',
        calc: (v) => (v.i ? ((0.5 * (v.n / 60) * v.tdec) * v.pas) / v.i : null), dec: 1 },
    ],
  },
  {
    id: 'lovitura-berbec',
    family: 'pompe',
    tier: 3,
    title: 'Lovitura de berbec (Joukowsky)',
    subtitle: 'Supra-presiune la oprirea pompei',
    note: 'Seteaza rampa de oprire a drive-ului mai mare decat timpul critic 2L/a, ca sa eviti supra-presiunea care sparge conducte/garnituri. Inchidere brusca (t < Tc) = soc maxim (Joukowsky).',
    fields: [
      { key: 'L', label: 'Lungime conducta', unit: 'm', default: 500, step: 10, min: 1 },
      { key: 'dvf', label: 'Variatie viteza fluid', unit: 'm/s', default: 2, step: 0.1, min: 0 },
      { key: 'aund', label: 'Viteza undei de presiune', unit: 'm/s', default: 1200, step: 50, min: 1 },
      { key: 'rho', label: 'Densitate fluid', unit: 'kg/m³', default: 1000, step: 10, min: 1 },
      { key: 'tinch', label: 'Timp de oprire/inchidere', unit: 's', default: 3, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'Tcrit', label: 'Timp critic', unit: 's', tex: 'T_c = \\dfrac{2L}{a}',
        calc: (v) => (v.aund ? (2 * v.L) / v.aund : null), dec: 2 },
      { key: 'dPmax', label: 'Soc presiune (inchidere brusca)', unit: 'bar', tex: '\\Delta p = \\rho\\,a\\,\\Delta v',
        calc: (v) => (v.rho * v.aund * v.dvf) / 1e5, dec: 1 },
      { key: 'dPreal', label: 'Soc presiune (la timpul setat)', unit: 'bar', tex: '\\Delta p \\approx \\rho L\\Delta v/t\\;(t>T_c)',
        calc: (v) => { const Tc = (2 * v.L) / v.aund; const dp = v.tinch > Tc ? (v.rho * v.L * v.dvf) / v.tinch : v.rho * v.aund * v.dvf; return dp / 1e5 }, dec: 1 },
    ],
  },
  {
    id: 'pid-drive',
    family: 'pompe',
    tier: 3,
    title: 'Acordare PID drive (presiune/debit)',
    subtitle: 'Valori de start Ziegler-Nichols (regulator intern)',
    note: 'Regulatorul intern al drive-ului (ABB built-in PID / Siemens technology controller). Cresti castigul pana la oscilatie sustinuta (K_u, T_u), apoi aplici valorile de start si reglezi fin. Adauga prag sleep/wake pentru economie.',
    fields: [
      { key: 'Ku', label: 'Castig critic (la oscilatie)', unit: '', default: 4, step: 0.1, min: 0.01 },
      { key: 'Tu', label: 'Perioada de oscilatie', unit: 's', default: 6, step: 0.5, min: 0.1 },
    ],
    results: [
      { key: 'KpPI', label: 'Kp (regulator PI)', unit: '', tex: 'K_p = 0.45\\,K_u', calc: (v) => 0.45 * v.Ku, dec: 2 },
      { key: 'TiPI', label: 'Ti (regulator PI)', unit: 's', tex: 'T_i = 0.83\\,T_u', calc: (v) => 0.83 * v.Tu, dec: 2 },
      { key: 'KpPID', label: 'Kp (regulator PID)', unit: '', tex: 'K_p = 0.6\\,K_u', calc: (v) => 0.6 * v.Ku, dec: 2 },
      { key: 'TiPID', label: 'Ti (regulator PID)', unit: 's', tex: 'T_i = 0.5\\,T_u', calc: (v) => 0.5 * v.Tu, dec: 2 },
      { key: 'TdPID', label: 'Td (regulator PID)', unit: 's', tex: 'T_d = 0.125\\,T_u', calc: (v) => 0.125 * v.Tu, dec: 2 },
    ],
  },
  {
    id: 'retea-emc',
    family: 'comun',
    tier: 3,
    title: 'Retea IT/TN & filtru EMC',
    subtitle: 'Decizie la PIF — scoaterea surubului EMC/MOV',
    note: 'Pe retea IT (neutru izolat) sau corner-grounded: SCOATE surubul filtrului EMC intern + varistorul (MOV) inainte de energizare — altfel primul defect de pamant arde filtrul si poate distruge drive-ul. Pe TN-S / TN-C-S: lasa filtrul EMC activ (conformitate EMC C1-C3). Confirma tipul retelei cu beneficiarul si manualul drive-ului (ABB ACS580/880 sectiunea "IT / corner-grounded"; Siemens SINAMICS G120).',
    params: 'IEC 60364 (TN/TT/IT) + IEC/EN 61800-3 (categorii EMC C1-C4)',
    fields: [],
    results: [],
  },
]

// Familiile care au cel putin un modul (pentru tab-uri).
export function visibleFamilies() {
  return FAMILIES.filter((fam) => MODULES.some((m) => m.family === fam.id))
}

// Calculeaza toate rezultatele unui modul din valorile date.
export function computeModule(mod, rawValues) {
  const v = {}
  for (const f of mod.fields) {
    const num = Number(rawValues?.[f.key])
    v[f.key] = Number.isFinite(num) ? num : 0
  }
  const r = {}
  for (const res of mod.results) {
    let out = null
    try {
      out = res.calc(v, r)
    } catch (_) {
      out = null
    }
    r[res.key] = Number.isFinite(out) ? out : null
  }
  return r
}

// Descriere scurta per grafic (ce demonstreaza + la ce sa fii atent). Array per modul, in ordinea graficelor.
export const CHART_DESC = {
  'cuplu': [{ ce: 'Caracteristica cuplu-turatie a motorului asincron (pornire Mₚ, maxim Mₘₐₓ, zero la sincronism) peste cuplul rezistent al sarcinii (pompa ~n²).', atentie: 'Motorul accelereaza doar daca M motor > M sarcina pe tot parcursul; punctul de functionare e la intersectie. Atentie la cuplul minim de demaraj la sarcini grele.' }],
  'cc-excitatii': [{ ce: 'Caracteristicile turatie-cuplu n(M) normalizate (× nominal) pe tip de excitatie; toate trec prin punctul nominal (1,1).', atentie: 'Seria se ambaleaza la gol (M→0 ⇒ n→∞); compusul diferential urca cu sarcina (instabil). Sep/sunt/PMDC sunt dure (cadere mica). Curbele sunt idealizate (nesaturat).' }],
  'cc-camp': [{ ce: 'Raspunsul la treapta al curentului de camp I_f(t): cu fortare (tensiune marita, limitata la I_f) atinge tinta mult mai rapid decat raspunsul L/R normal.', atentie: 'Campul e lent (τ_f=L_f/R_f, poate fi de ordinul secundelor); fara fortare, slabirea de camp si inversarea intarzie. Markerul = momentul atingerii I_f.' }],
  'cc-comutatie': [
    { ce: 'Viteza periferica a colectorului v=πDn/60 vs turatie, cu liniile-limita 30 si 40 m/s.', atentie: 'Peste ~40 m/s apar scantei/uzura/flashover. Markerul = nmax; daca depaseste limita, reduce nmax sau diametrul colectorului.' },
    { ce: 'Cuplul relativ M/M_n: constant pana la nbaza, apoi ∝1/n in slabire de camp (putere constanta).', atentie: 'Raportul nmax/nbaza e limitat de comutatie (~3:1, pana la ~6:1 cu infasurare de compensare), nu de termica. La nmax cuplul scade la nbaza/nmax.' },
  ],
  'cc-factor-forma': [{ ce: 'Factorul de pierderi suplimentare in indus k_f² in functie de factorul de forma k_f, cu punctul de lucru marcat.', atentie: 'Incalzirea creste patratic: k_f=1.2 ⇒ +44% pierderi Joule fata de curent neted. Derateaza curentul mediu admis (I_n/k_f) sau adauga bobina de netezire.' }],
  'cc-franare': [
    { ce: 'Cuplul si curentul de franare dinamica vs turatie: scad liniar cu n (E∝n) si se anuleaza la n=0.', atentie: 'Franarea dinamica e slaba la turatie mica → pentru oprire/tinere fina e nevoie de frana mecanica.' },
    { ce: 'Curentul initial de franare I_b in functie de rezistorul R_b (hiperbolic); linia I_max indica R_b minim acceptabil.', atentie: 'R_b prea mic → varf de curent peste I_max la comutare. Alege R_b ≥ R_b,min. Convertor 1Q: doar disipare; 4Q: recuperare in retea.' },
  ],
  'asincron-camp-slabit': [
    { ce: 'Cuplul disponibil: constant pana la turatia de baza, apoi ∝1/n (putere constanta); cuplul de rasturnare scade ∝1/n².', atentie: 'Peste turatia critica ncp cuplul de rasturnare ajunge sub cel cerut → motorul se rastoarna. Nu cere cuplu nominal in slabire.' },
    { ce: 'Puterea creste pana la turatia de baza, apoi ramane ~constanta in zona de slabire de camp.', atentie: 'Zona de putere constanta e limitata; verifica nmax fata de ncp.' },
  ],
  'sarcina-afinitate': [
    { ce: 'Legea afinitatii: puterea scade cu cubul turatiei (P∝n³) la pompe/ventilatoare.', atentie: 'Economia vine din exponentul 3: −20% turatie ≈ −50% putere. Valabil doar cu inaltime statica mica.' },
    { ce: 'Locusul punctelor de functionare la turatie variabila urmeaza o parabola H∝Q² prin origine.', atentie: 'Cu inaltime statica (H₀>0) curba reala NU trece prin origine → economia e mai mica decat cubica.' },
  ],
  'pornire': [{ ce: 'Curentul absorbit in timpul pornirii pt DOL, softstart si VFD vs turatie.', atentie: 'DOL trage ~6×Iₙ (soc pe retea, cadere de tensiune); VFD limiteaza curentul aproape de nominal. Verifica dip-ul pe bara.' }],
  'vfd': [{ ce: 'Caracteristica V/f: tensiunea creste liniar cu frecventa pana la fₙ, apoi ramane constanta (slabire de camp).', atentie: 'Peste fₙ tensiunea nu mai creste → fluxul si cuplul maxim scad. Boost-ul la f mic poate satura motorul.' }],
  'cc-baza': [{ ce: 'Caracteristica mecanica n(M) a motorului c.c. cu excitatie separata: usor descrescatoare (caderea pe Rₐ).', atentie: 'Panta data de Rₐ; la sarcina mare turatia scade. Motor c.c. rigid la flux constant.' }],
  'cc-reglaj': [
    { ce: 'Cuplul disponibil: constant pana la turatia de baza, apoi ∝1/n in slabire de camp.', atentie: 'In slabire cuplul scade; nu depasi turatia unde cuplul cerut > cel disponibil.' },
    { ce: 'Puterea creste pana la baza, apoi ramane constanta in slabire de camp.', atentie: 'Comutatia mecanica limiteaza turatia maxima; verifica si la colector.' },
  ],
  'pmsm-model': [{ ce: 'Anvelopa de cuplu a servomotorului PMSM: cuplu de varf (~3×) si continuu, constante pana la turatia de baza, apoi ∝1/n.', atentie: 'Cuplul de varf e disponibil doar scurt (termic). Verifica RMS pe ciclu, nu doar varful.' }],
  'sincron-putere': [{ ce: 'Puterea sincrona P=U·E·sinδ/Xₛ vs unghiul de sarcina: maxima la δ=90° (cuplu de desprindere).', atentie: 'Functionare stabila doar pe ramura crescatoare (δ<90°). Peste 90° motorul pierde sincronismul.' }],
  'motor-echivalent': [
    { ce: 'Caracteristica reala cuplu-turatie din schema echivalenta Thevenin: pornire, rasturnare la sₘₐₓ, zero la sincronism.', atentie: 'Cuplul de pornire si Mₘₐₓ depind de R₂/X₂; rotor cu R₂ mare → pornire buna dar randament slab.' },
    { ce: 'Curentul rotoric scade de la valoarea de pornire (mare) spre zero la sincronism.', atentie: 'Curentul de pornire mare = solicitare termica; conteaza la porniri dese.' },
  ],
  'randament-sarcina': [{ ce: 'Randamentul vs sarcina: maxim acolo unde pierderile variabile (Cu) = pierderile constante (Fe+mecanice), apoi scade.', atentie: 'Sub ~40% sarcina randamentul se prabuseste → motorul supradimensionat e ineficient. Optimul e la xₒₚₜ.' }],
  'pompa-sistem': [{ ce: 'Curba sistemului (statica + frecare ∝Q²) intersectata cu curba pompei la turatie nominala si la cea ceruta; punctul de functionare e la intersectie.', atentie: 'Cu inaltime statica, scaderea turatiei muta punctul pe curba sistem — nu cobori sub debitul minim al pompei.' }],
  'trafo-12pulse': [{ ce: 'Spectrul armonic 6 vs 12 pulsuri: la 12 pulsuri armonicile 5,7,17,19 se anuleaza, raman doar 11,13,23,25.', atentie: 'Anularea e perfecta doar cu incarcare echilibrata pe cele doua punti si defazaj exact de 30°.' }],
  'protectie-motor': [{ ce: 'Curba inversa de declansare a releului termic (timpul scade cu curentul) pt clasele 10/20/30.', atentie: 'Curentul de pornire trebuie sa cada sub curba (timp de declansare > timp de pornire), altfel declanseaza la fiecare pornire. Clasa mai mare = porniri mai lungi.' }],
  'control-vf': [{ ce: 'Caracteristica V/f liniara (cuplu constant) vs patratica (pompe/ventilatoare); boost-ul ridica tensiunea la f mic.', atentie: 'V/f patratic reduce fluxul si pierderile la sarcini partiale, dar da cuplu mai mic la pornire.' }],
  'ripple-pwm': [{ ce: 'Ondulatia de curent scade hiperbolic cu frecventa de comutatie (ΔI∝1/f_sw).', atentie: 'f_sw mai mare = ripple mic dar pierderi de comutatie mari. Inductanta de scapari mica → ripple mare; ia in calcul un reactor de motor.' }],
  'comutatie': [{ ce: 'Pierderile de comutatie cresc liniar cu f_sw, cele de conductie raman constante; totalul e suma lor.', atentie: 'Cresterea f_sw reduce ripple/zgomot dar incalzeste invertorul — exista un optim. Conductia nu depinde de f_sw.' }],
  'unda-reflectata': [{ ce: 'Varful de tensiune la bornele motorului creste cu lungimea cablului si se satureaza la ~2×U_dc peste lungimea critica.', atentie: 'Peste Lcrit ai supratensiune dubla pe izolatie → imbatranire/strapungere. Sub Lsafe esti sigur; altfel filtru du/dt.' }],
  'winder': [{ ce: 'La putere constanta, cuplul creste liniar cu diametrul rolei (T=F·d/2) iar turatia scade ∝1/d.', atentie: 'Raportul cuplu/turatie de la gol la plin = raportul diametrelor; verifica sa incapa in plaja motorului/drive-ului.' }],
  'pmsm-camp-slabit': [{ ce: 'Cuplu constant pana la turatia de baza (limita de tensiune), apoi ∝1/n in slabire de camp prin injectie de I_d.', atentie: 'Turatia de baza scade daca bus-ul DC e mic. Curentul caracteristic Ich=ψm/Lq arata cat de bine slabeste campul.' }],
  'sincron-poli-aparenti': [{ ce: 'Puterea totala = excitatie (sinδ) + reluctanta (sin2δ); cuplul de reluctanta deplaseaza maximul sub δ=90°.', atentie: 'Componenta de reluctanta devine negativa peste 90°; desprinderea (maximul total) e la δ<90°, mai devreme ca la poli plini.' }],
  'cc-serie': [{ ce: 'Caracteristica de tractiune a motorului c.c. serie: turatia scade hiperbolic cu curentul (n∝1/Iₐ), cuplu mare la pornire.', atentie: 'La sarcina mica (Iₐ mic) turatia fuge periculos → nu lasa motorul serie fara sarcina.' }],
  'derating-vfd-motor': [{ ce: 'Curentul admisibil al motorului autoventilat scade la turatii mici (racire slaba); cu ventilatie fortata ramane la nominal.', atentie: 'La turatii joase si cuplu nominal motorul autoventilat se supraincalzeste — derating sau ventilator separat.' }],
  'cosphi-sarcina': [{ ce: 'Factorul de putere scade puternic la sarcini partiale fiindca curentul de magnetizare (~constant) domina componenta activa.', atentie: 'Motor supradimensionat = cos φ mic = pierderi/penalizari pe retea. La 50% sarcina cos φ poate cadea sub 0,65.' }],
  'regimuri-s': [{ ce: 'Puterea admisibila creste cand factorul de durata ciclica scade: S3 (repaus deconectat) > S6 (mers in gol) > S1 (continuu).', atentie: 'S6 da uprating mai mic ca S3 (motorul nu se raceste in gol). Aproximatia 1/√CDF e valida cand ciclul nu e mult mai scurt ca constanta termica.' }],
  'economie-profil': [{ ce: 'Puterea vs debit: VFD (lege cubica) vs strangulare (vana, ~constant) vs by-pass; economia = aria dintre curbe.', atentie: 'Economia reala se calculeaza ponderat pe orele la fiecare debit, nu intr-un punct. Strangularea risipeste cel mai mult.' }],
  'randament-pompa': [{ ce: 'Randamentul pompei e maxim la debitul BEP si scade parabolic de ambele parti.', atentie: 'Departe de BEP scad randamentul si durata de viata (vibratii, cavitatie). Tine punctul de functionare aproape de BEP.' }],
  'taper': [{ ce: 'Cu taper, tensiunea de infasurare scade programat spre diametru plin, deci cuplul creste mai lent decat fara taper.', atentie: 'Taper-ul previne strivirea straturilor interioare la rola plina; prea mult taper = infasurare moale.' }],
  'vcurves': [{ ce: 'Curba in V: curentul de stator e minim la factor de putere unitar si creste la sub/supra-excitatie.', atentie: 'Sub-excitat absorbi reactiv (risc de instabilitate); supra-excitat furnizezi reactiv (curent mare). Minimul = fp unitar.' }],
}

// Marker de punct de functionare per grafic: (v, r) -> [{x,y,label,color}] (r = rezultatele cardului).
const _mk = (x, y, label) => [{ x, y, label: label || 'punct lucru', color: COL.op }]
export const CHART_MARK = {
  'asincron-camp-slabit': [(v, r) => _mk(v.nbaza, r.Mn, 'baza'), (v, r) => _mk(v.nbaza, r.Pdisp, 'baza')],
  'sarcina-afinitate': [(v, r) => _mk(v.n2, r.P2, 'punct'), null],
  'vfd': [(v, r) => _mk(v.f, r.Uies, 'f lucru')],
  'cc-baza': [(v, r) => _mk(r.M, r.n, 'nominal')],
  'cc-reglaj': [(v, r) => _mk(v.ndorit, r.Mdisp, 'n dorit'), (v, r) => _mk(v.ndorit, r.Pconst, 'n dorit')],
  'sincron-putere': [(v, r) => _mk(v.delta, r.P, 'delta lucru')],
  'motor-echivalent': [(v, r) => _mk(v.n, r.M, 'punct'), (v, r) => _mk(v.n, r.I2, 'punct')],
  'pompa-sistem': [(v, r) => _mk(v.Qtarget, r.Hreq, 'punct lucru')],
  'protectie-motor': [(v, r) => _mk((v.kstart * v.In) / v.Ie, r.ttrip_start, 'pornire')],
  'control-vf': [(v, r) => _mk(v.fop, r.Uf, 'f lucru')],
  'ripple-pwm': [(v, r) => _mk(v.fsw, r.dIpp, 'fsw')],
  'comutatie': [(v, r) => _mk(v.fsw, r.Ptot, 'fsw')],
  'unda-reflectata': [(v, r) => _mk(v.L, r.Upk, 'cablu')],
  'winder': [(v, r) => _mk(v.dplin, r.Tplin, 'plin')],
  'pmsm-camp-slabit': [(v, r) => _mk(r.nbaza, 1.5 * v.ppp * v.psim * v.Imax, 'baza')],
  'sincron-poli-aparenti': [(v, r) => _mk(v.delta, r.Ptot, 'delta lucru')],
  'cc-serie': [(v, r) => _mk(v.Ia, r.n, 'nominal')],
  'derating-vfd-motor': [(v, r) => _mk(v.f, r.Iself, 'f lucru')],
  'regimuri-s': [(v, r) => _mk(v.DC, r.PS3, 'CDF')],
  'randament-pompa': [(v, r) => _mk(v.Q, r.etaQ, 'Q lucru')],
  'taper': [(v, r) => _mk(v.d, r.T, 'd')],
  'vcurves': [(v, r) => _mk(r.Eunit, r.Iamin, 'fp=1')],
}
// Zone (regimuri) per grafic: (v, r) -> [{x0,x1,label,color}] (benzi verticale hasurate).
// Culori semantice teme-constiente (se adapteaza light/dark via CSS vars).
const _zg = 'var(--success)', _zb = 'var(--info)', _zy = 'var(--warning)', _zo = 'var(--danger)'
const _z = (x0, x1, label, color) => ({ x0, x1, label, color })
export const CHART_ZONE = {
  'asincron-camp-slabit': [
    (v, r) => [_z(0, v.nbaza, 'cuplu constant', _zg), _z(v.nbaza, r.ncp, 'slabire de camp', _zb)],
    (v, r) => [_z(0, v.nbaza, 'cuplu constant', _zg), _z(v.nbaza, r.ncp, 'slabire de camp', _zb)],
  ],
  'cc-reglaj': [
    (v) => [_z(0, v.nbaza, 'cuplu constant', _zg), _z(v.nbaza, v.ndorit, 'slabire de camp', _zb)],
    (v) => [_z(0, v.nbaza, 'cuplu constant', _zg), _z(v.nbaza, v.ndorit, 'slabire de camp', _zb)],
  ],
  'cc-comutatie': [
    null,
    (v) => [_z(0, v.nbaza, 'cuplu constant', _zg), _z(v.nbaza, Math.max(v.nmax, v.nbaza * 1.05), 'slabire de camp', _zb)],
  ],
  'pmsm-camp-slabit': [(v, r) => [_z(0, r.nbaza, 'cuplu constant', _zg), _z(r.nbaza, r.nbaza * 3, 'putere constanta', _zb)]],
  'pmsm-model': [(v) => [_z(0, v.n, 'cuplu constant', _zg), _z(v.n, v.n * 3, 'putere constanta', _zb)]],
  'vfd': [(v) => [_z(0, v.fn, 'V/f liniar', _zg), _z(v.fn, v.fn * 2, 'slabire de camp', _zb)]],
  'unda-reflectata': [(v, r) => [_z(0, r.Lsafe, 'sigur', _zg), _z(r.Lsafe, r.Lcrit, 'atentie', _zy), _z(r.Lcrit, Math.max(v.L, r.Lcrit * 2.5), 'supratensiune', _zo)]],
}

// Construieste graficele unui modul din valorile date (returneaza [] daca nu are).
export function computeCharts(mod, rawValues) {
  if (!mod.charts) return []
  const v = {}
  for (const f of mod.fields) {
    const num = Number(rawValues?.[f.key])
    v[f.key] = Number.isFinite(num) ? num : 0
  }
  const r = computeModule(mod, rawValues)
  const out = []
  let ci = 0
  for (const builder of mod.charts) {
    try {
      const c = builder(v)
      if (c && (c.series || []).some((s) => (s.points || []).length > 1)) {
        const dd = (CHART_DESC[mod.id] || [])[ci]
        if (dd) c.desc = dd
        const mkfn = (CHART_MARK[mod.id] || [])[ci]
        if (mkfn && !(c.markers && c.markers.length)) { try { const mks = mkfn(v, r); if (mks) c.markers = mks.filter((m) => Number.isFinite(m.x) && Number.isFinite(m.y)) } catch (_) {} }
        const zfn = (CHART_ZONE[mod.id] || [])[ci]
        if (zfn) { try { const zs = zfn(v, r); if (zs) c.zones = zs.filter((z) => Number.isFinite(z.x0) && Number.isFinite(z.x1) && z.x1 > z.x0) } catch (_) {} }
        out.push(c)
      }
    } catch (_) {
      // ignora graficul daca formula esueaza
    }
    ci++
  }
  return out
}

// Formatare numerica in stil RO (mono in UI).
export function fmtNum(x, dec) {
  if (x == null || !Number.isFinite(x)) return '—'
  const a = Math.abs(x)
  let d = dec
  if (d == null) d = a >= 1000 ? 0 : a >= 100 ? 1 : a >= 10 ? 2 : 3
  return x.toLocaleString('ro-RO', { minimumFractionDigits: d, maximumFractionDigits: d })
}

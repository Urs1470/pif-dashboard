# Audit Parametri — Rezultate complete
**Data:** 18 mai 2026
**Sursă:** scripts/audit_reports/*.json (rulare ~00:30-00:58)
**Script:** audit_pdf.py --all (NU s-a putut rula pe laptop — s-a blocat)

---

## SINAMICS G120
- PDF: SINAMICS_G120_List_Manual.pdf
- DB count: 1,390 | PDF count: **1,518**
- În DB nu-s în PDF: 849
- În PDF nu-s în DB: 977
- Name mismatch: 99
- Page fix needed: 540

---

## SINAMICS G130/G150
- PDF: SINAMICS_G130_G150_List_Manual.pdf
- DB count: 2,592 | PDF count: **2,170**
- În DB nu-s în PDF: 1,383
- În PDF nu-s în DB: 961
- Name mismatch: 430
- Page fix needed: 1,209

---

## ACS580
- PDF: ACS580_Firmware_Manual.pdf
- DB count: 1,337 | PDF count: **1,268**
- În DB nu-s în PDF: 75
- În PDF nu-s în DB: 6
- Name mismatch: 554
- Page fix needed: 472

---

## ACS880
- PDF: ACS880_Primary_Firmware_Manual.pdf
- DB count: 1,709 | PDF count: **1,659**
- În DB nu-s în PDF: 529
- În PDF nu-s în DB: 479
- Name mismatch: 1,177
- Page fix needed: 1,180

---

## Danfoss VLT FC302
- PDF: Danfoss_VLT_FC302_Programming_Guide.pdf
- DB count: 1,300 | PDF count: **1,260**
- În DB nu-s în PDF: 43
- În PDF nu-s în DB: 3
- Name mismatch: 7
- Page fix needed: 1,252

---

## Lenze i550
- PDF: Lenze_i550_Manual.pdf
- DB count: 2,503 | PDF count: **1,622**
- În DB nu-s în PDF: 959
- În PDF nu-s în DB: 78
- Name mismatch: 251
- Page fix needed: 1,544

---

## Lenze i950
- PDF: Lenze_i950_Manual.pdf
- DB count: 452 | PDF count: **1,665**
- În DB nu-s în PDF: 25
- În PDF nu-s în DB: 1,238
- Name mismatch: 172
- Page fix needed: 427

---

## Observații
- **ACS580/ACS880**: name mismatch mare (554/1,177) — denumiri parametri diferite în PDF vs DB
- **Lenze i950**: DB are doar 452, PDF are 1,665 — **1,238 parametri noi** de adăugat în DB
- **Danfoss FC302**: cel mai curat — doar 7 name mismatch
- **G120**: db_count 1,390 vs pdf_count 1,518 — aproape de ce a scos parserul rescris
- **Page fix needed** mare la toate — problema de parsing pe pagini

---

## De făcut
Scriptul `audit_pdf.py --all` NU a fost rulat pe acest laptop (s-a blocat aseară + azi).
Pe alt dispozitiv cu resurse:
```bash
cd /home/ion-ursu/Projects/pif-dashboard
git pull
python scripts/audit_pdf.py --all
```

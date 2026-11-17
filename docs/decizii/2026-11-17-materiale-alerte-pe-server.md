# Alertele materialelor se calculează pe server, la `PUT /api/materiale` (2026-11-17)

> Ion a cerut ca taskurile și scripturile să stea pe o platformă centralizată, cu laptop-server-ul drept creier și PC-ul
> de job doar pentru ce nu se poate altfel. Brieful a avut cinci etape; asta e etapa 2. Ion: „Da, etapa 2. Fă toate
> etapele, nu mai sta după mine.”

## De ce

Până azi, colectorul de pe PC-ul de job (Knowledge `tools/materiale-colector.ps1`) aduna datele și calcula singur
alertele: comanda pe mail fără LM, CT fără LM, contract fără linii de pontaj, livrări după startul perioadei sau cu cel
mult o săptămână înainte. Apoi crea taskurile prin `POST /api/proiecte/<id>/tasks`. Regulile stăteau deci pe PC, în
PowerShell, iar o schimbare de regulă cerea PC-ul de job. Aproape toate datele de care au nevoie regulile vin deja în
snapshot; perioadele, colectorul le lua tot de aici (`/api/calendar`).

## Ce s-a ales

- `blueprints/materiale_alerte.py` are regulile, cu textele, titlurile și id-urile de task ale colectorului, caracter
  cu caracter. Id-ul e SHA-1 pe `pif-materiale|<proiect>|<tip>|<ref>`, în forma UUID, deci un task creat deja de PC
  nu se dublează și unul bifat de Ion rămâne bifat.
- La `PUT /api/materiale`, cu `sursa.alerte = "server"`, serverul calculează alertele, marcajele `fata_de_start` și
  câmpurile `perioada`, `dupa_start`, `aproape_start` din `rezumat`, le scrie în snapshot (deci `GET` și Torqa arată la
  fel), apoi creează taskurile direct în bază (același INSERT ca `create_task`). Răspunsul are în plus `alerte` și
  `taskuri: {noi, existente, sarite}`.
- Fără flag, serverul păstrează alertele trimise de colector, ca înainte: deploy-ul nu schimbă nimic până nu trece
  colectorul pe noul mod.
- „Azi” e ziua din `generat`, ora PC-ului, nu ceasul serverului. Perioada e următoarea din `implementari` care n-a
  trecut, inclusiv una în curs (aceeași condiție ca la colector, prin `/api/calendar`); tabela doar se citește.
- Colectorul trimite două câmpuri noi: `contract_data` și `linii_contract` pe proiect (pentru `fara_linii_pontaj`) și
  `sursa.utilizator` (contul din E100 cu care se compară `creat_de` la „LM creat de mine”).
- Rămân pe PC: interogările (E100, BC, Outlook) și taskurile pentru proiectele fără cod în E100, care cer o căutare în
  E100.

## Verificat (17.11)

- Pe payload-ul colectat azi la 14:01, fără alertele lui: Python dă exact cele două alerte ale PowerShell-ului (26_337
  `livrare_aproape_start`, 26_287 `comanda_fara_lm`), cu același tip, `ref`, `din` și text; marcajele celor 15
  materiale și rezumatul ies identice; id-urile de task coincid cu `New-StableId` rulat în PowerShell.
- `teste/test_materiale_alerte.py`: regulile, cazurile care le acoperă, weekendul, scadențele, PUT-ul cu și fără flag,
  taskul bifat care nu se dublează, proiectul șters, „azi” din `generat`. `python scripts/verifica.py` trece.

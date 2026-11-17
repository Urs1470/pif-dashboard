# Mail Tasks judecă pe server: PC-ul urcă doar loturi de mail la `/api/mail/lot` (2026-11-17)

> Etapa 3 a centralizării (laptop-server-ul face logica, PC-ul de job doar extrage ce nu se poate altfel). Ion: „Fă toate
> etapele, nu mai sta după mine.” La întrebarea dacă mailurile de firmă pot sta pe laptopul de acasă n-a răspuns separat;
> de aceea un lot stă pe server doar până îl procesează Mail Tasks, iar ce rămâne după rulare nu are corpul mailurilor.

## De ce

Mail Tasks (Knowledge `tools/mail-tasks.py`) rula tot pe PC-ul de job: exportul Outlook (COM, doar acolo), filtrul,
Claude și scrierea taskurilor, cu registrul mailurilor văzute tot pe PC. Doar exportul cere PC-ul. Restul cerea un PC
pornit și logat chiar și pentru o schimbare de regulă sau de prompt.

## Ce s-a ales

- `blueprints/mail_lot.py`, pe fișiere (tiparul materialelor, fără schemă):
  - `PUT /api/mail/lot` primește exportul Outlook așa cum îl scrie `export-outlook.ps1` (`meta`, `mails`);
  - `GET /api/mail/lot` dă starea (`ultima_rulare` reușită, `ultimul_lot`) și loturile în așteptare, fără conținut;
  - `GET /api/mail/lot/<id>` dă lotul; `POST /api/mail/lot/<id>/gata` îl șterge și scrie rezultatul.
    `ultima_rulare` avansează doar la cod 0, ca la registrul de pe PC: cu erori, exportul următor reia mailurile.
- Un lot uitat mai mult de 7 zile se șterge la următorul PUT.
- Tokenul de dispozitiv nu atinge `/api/mail/` (`utils.DEVICE_TOKEN_DENIED`): Torqa n-are ce citi acolo.
- PC-ul: `mail-tasks.py trimite` (din `mail-tasks.ps1`, L–V la 08:00 și 14:00) cere fereastra de la server, exportă și
  urcă. Serverul: `mail-tasks.py server`, din timerul de utilizator `mail-tasks-server.timer` (la 5 minute), rulează pe
  fiecare lot filtrul, Claude (`claude -p` de pe laptop) și aplicarea pe `127.0.0.1:5000`, cu registrul în
  `~/.local/state/mail-tasks/`. După rulare șterge exportul, promptul și răspunsul brut; rămân raportul, decizia și
  contextul (referințe, fără corpuri).

## Verificat (17.11)

- `teste/test_mail_lot.py`: drumul întreg, fereastra care nu avansează cu erori, dispozitivul refuzat pe toate cele
  patru rute, exportul stricat fără scriere, `gata` cu corp greșit, lotul uitat șters. `python scripts/verifica.py` trece.

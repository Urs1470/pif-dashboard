# 2026-08-07 — Cheia VAPID: RAW, nu PEM

- **2026-08-07 (2) — Cheia VAPID: RAW, nu PEM. „Trimite test" pica de la asta.**
  Prima versiune salva cheia privata ca PKCS8 PEM. `py_vapid.from_string` face
  `b64urldecode` pe TOT sirul si cere fix 32 de octeti — deci ORICE PEM (si
  PKCS8, si SEC1) da `ValueError: Could not deserialize key data`. Semnarea
  crapa INAINTE de orice apel spre Google, deci butonul pica fara sa spuna de ce.
  Se stocheaza acum scalarul brut in base64url; o cheie veche in PEM se
  CONVERTESTE la citire (`_chei_vapid`), nu se regenereaza — perechea ramane
  aceeasi, deci abonamentele deja facute pe telefon continua sa mearga.
  **De ce n-a prins-o suita:** cele 16 verificari existente injectau un expeditor
  fals (`trimite=...`), deci nu atingeau NICIODATA `webpush`. Proba noua trimite
  spre un host mort cu un abonament fals dar VALID criptografic si cere ca
  esecul sa fie de RETEA — orice picare mai devreme inseamna ca lantul
  cheie->criptare->semnare e rupt. `push_last_error` poarta acum motivul real
  (tip + mesaj), nu „N notificari nu au putut fi trimise": fara SSH, mesajul din
  modal e singurul diagnostic.

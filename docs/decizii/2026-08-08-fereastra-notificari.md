# Fereastra de notificări: patru reglaje, aceleași de pe orice dispozitiv (14b, 2026-08-08)

Nu se face pagină de Setări. Singurele reglaje sunt cele patru ale notificărilor și trăiesc
în fereastra clopoțelului din `/tasks`, vizibil doar în sfera Personal.

- **Nu mai sunt ascunse pe web.** Erau gardate pe `esteNativ()` cu motivul „pe web nu există
  canalul local pe care să-l regleze" — dar cele patru nu sunt ale canalului, sunt ale
  REGULII, iar regula o citește și planificatorul de pe server. Deci ora la care sună
  telefonul se putea schimba doar de pe telefon, deși setarea era comună. Acum se arată
  oriunde există ceva de programat (nativ mereu; pe web când există măcar un dispozitiv
  abonat — de pe PC reglezi ce sună pe telefon).
- **Comutatorul „scadente" chiar comută ceva.** `check_and_send_daily` trimitea DOAR taskurile
  fără termen (`if setari['faraTermen']`); motivul `scadent` exista doar pe telefon
  (`lib/notificari.js`). Adăugat `taskuri_scadente()` + `_de_notificat()` în `push.py`. Cu el
  a trebuit și **al doilea buton din payload** (`a2`): pe un task scadent azi, „Azi" ar scrie
  data pe care o are deja — service worker-ul îl avea scris în cod. Rezerva rămâne „Azi",
  pentru notificările vechi din coadă. `VERSION` bumpat la `v100`.
- **Salvarea confirmă cu numărul** („Salvat — 4 notificări programate"): pe telefon din
  reprogramarea locală, pe web din `programate`, întors acum de `PUT /api/push/setari`.
- **Proba stă la stânga, departe de „Salvează"**: una verifică lanțul acum, cealaltă schimbă
  ce se întâmplă mâine. „Nu mai trimite pe dispozitivul ăsta" a coborât lângă numărul de
  dispozitive — e despre ACEST aparat, nu despre regulă, deci n-are ce căuta al treilea verb
  în bara de jos.
- Regula „cel puțin un fel pornit" e **scrisă în fereastră**, nu descoperită dintr-o eroare
  după ce ai apăsat Salvează.

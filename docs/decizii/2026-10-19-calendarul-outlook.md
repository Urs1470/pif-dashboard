# 2026-10-19 Calendarul Outlook al lui Ion ajunge în Torqa printr-un snapshot-fișier

Torqa arată în Calendar și evenimentele din Outlook-ul de job, lângă perioadele de implementare
și taskuri. Aprobat de Ion pe 2026-10-19.

- **Cum ajunge acolo.** Un script de pe PC-ul de job citește calendarul prin **COM** (Outlook
  clasic, deja instalat și autentificat) și urcă la 15 minute un snapshot al ferestrei
  (~10 săptămâni) cu `PUT /api/outlook/calendar`. Torqa îl citește prin cheia nouă `outlook` din
  `GET /api/calendar`.
- **De ce COM și nu Microsoft Graph / EWS.** Graph cere o aplicație înregistrată în tenant-ul
  Electroglobal, adică consimțământ de administrator pe care Ion nu-l are și pe care nu-l cerem
  pentru un calendar personal. COM rulează cu sesiunea lui, fără secrete noi pe server și fără
  nimic de aprobat de IT. Costul: merge doar cât PC-ul de job e pornit și Outlook e deschis; în
  rest Torqa arată ultimul snapshot, cu `generatedAt` ca să se vadă cât e de vechi.
- **De ce fișier și nu tabelă.** Snapshot-ul se reface singur în 15 minute, deci nu are nimic de
  păstrat: `uploads/outlook/calendar.json`, rescris întreg și atomic (fișier temporar +
  `os.replace`, ca `current` din Torqa web). Fără tabelă nouă, fără migrare, fără `app_settings`,
  **nu intră în backup** și restore-ul nu-l atinge (la o restaurare apare din nou în cel mult 15
  minute). O tabelă ar fi fost schimbare de schemă și ar fi intrat în backup cu date efemere ale
  altcuiva (titlurile ședințelor).
- **Scrierea.** `login_required` (sesiune sau `PIF_API_TOKEN`); prefixul `/api/outlook/` e în
  `DEVICE_TOKEN_DENIED`: un telefon pierdut nu scrie calendarul. Un token de dispozitiv primește 401
  (ca la celelalte rute interzise lui, garda e în `_check_api_token`), nu 403. Corp maxim 1 MB (413),
  maxim 2000 de evenimente; orice abatere de la contract dă 400 cu câmpul și indexul evenimentului și
  lasă snapshot-ul vechi neatins. Câmpurile necunoscute se ignoră și nu se scriu. O cerere repetată
  lasă același fișier.
- **Citirea.** `outlook` e `null` fără snapshot sau cu fișier corupt (warning în log, nu 500), altfel
  `{generatedAt, events}` cu evenimentele care ating fereastra cererii `[start, start+zile)`.
  Suprapunerea e pe data locală din string (primele 10 caractere, fără conversie de fus): ziua
  evenimentului e cea văzută de Ion. Toată ziua: `start < sfârșit și end > început` (end exclusiv);
  cu oră: `data(start) < sfârșit și data(end) >= început`. Cheia e aditivă; restul răspunsului
  `/api/calendar` nu s-a schimbat, iar APK-ul instalat o ignoră.
- **Confidențialitate.** `isPrivate` și `busy` ajung în Torqa ca atare; ce afișează cu ele e treaba
  clientului. Titlurile nu se loghează.
- **Cod:** `blueprints/outlook.py`, `blueprints/admin.py` (`calendar_view`), `utils.py`
  (`DEVICE_TOKEN_DENIED`), teste în `teste/test_outlook.py`.

# 2026-08-07 — Notificari push: O NOTIFICARE PER TASK, cu „Facut"/„Azi" pe ea

- **2026-08-07 — Notificari push: O NOTIFICARE PER TASK, cu „Facut"/„Azi" pe ea.**
  Ion: „nu rezumat, trebuie sa apara taskul propriu-zis, separat per notificare,
  trebuie sa pot bifa taskul direct din notificare". Regula: task PERSONAL,
  deschis, FARA termen, `created_at` mai vechi de 2 zile -> in fiecare
  dimineata la 08:00 o notificare proprie, cu titlul lui si doua actiuni —
  exact cele doua iesiri din situatie („nu l-am facut SAU nu i-am pus termen").
  Web Push/VAPID prin `pywebpush` (import GARDAT: deploy-ul doar logheaza un
  pip esuat, iar aplicatia trebuie sa porneasca oricum).
  **Cum poate SW-ul sa bifeze:** nu poate citi cookie-uri, deci n-are token
  CSRF. Fiecare notificare poarta un TOKEN HMAC-SHA256 (SECRET_KEY) legat de UN
  task, 48h; `POST /api/push/action` nu cere sesiune (tokenul E autentificarea)
  si e prima intrare din `csrf._EXEMPT_ENDPOINTS` (mecanism care exista de mult,
  dar era gol). Payload-ul push e criptat end-to-end, deci tokenul nu circula in clar.
  **Capcane prinse:** (1) `created_at` e ISO LOCAL naiv, iar `date('now')` in
  SQLite e UTC — comparatia trebuie sa fie `date('now','localtime','-2 days')`,
  altfel un task creat seara aluneca o zi. (2) CLAIM INAINTE DE TRIMITERE
  (upsert conditional pe `push_daily_last`, `rowcount==1`): 2 workeri × bucla la
  5 min ar trimite de mai multe ori; o dublura zilnica erodeaza increderea
  definitiv, o zi pierduta la crash se vindeca maine. (3) `tag: pif-task-<id>` —
  notificarea de maine o INLOCUIESTE pe cea de azi, nu se stivuiesc sapte copii.
  (4) Iconitele din manifest erau SVG inline (`data:`) — `showNotification` nu
  le randeaza sigur pe Android; s-au comis PNG-uri reale rasterizate din
  favicon.svg + ruta `/icon-<size>.png`.
  Planificatorul porneste din blocul lazy de startup (per worker; dedup-ul e in
  baza) si e catch-up — „a trecut ora 8 si n-am trimis azi?", nu tick exact,
  fiindca serviciul reporneste la fiecare deploy. `CHEI_PROTEJATE` din admin.py
  s-a generalizat la `('google_', 'push_')` in cele trei situri de backup/restore.
  SW: **VERSION v98 -> v99** (obligatoriu la orice atingere a fisierului).
  iOS: butoanele de actiune nu exista; acolo atingerea deschide taskul focusat,
  si doar din PWA instalata (16.4+) — scris in modal.

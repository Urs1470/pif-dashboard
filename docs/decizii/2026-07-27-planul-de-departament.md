# Planul de departament (`/departament`) (2026-07-27)

Planul intregii echipe sta intr-o aplicatie externa (`app.projectplan-powerpoint.com`) si e
**incorporat** in SPA, nu importat — e o plansa, nu o structura cu API. Linkul de partajare
contine cheia de acces in fragment (dupa `#`), deci nu ajunge la serverul lor prin cererea
HTTP. Se tine in `app_settings` prin `GET/PUT /api/settings/plan-departament`, **niciodata
in cod sau in `wiki/`** (care e urmarit de git). Domeniul apare in doua locuri care trebuie
sa ramana sincronizate: `utils.PLAN_DEPT_HOST` (validare pe server) si `frame-src` din CSP
(`app.py`).

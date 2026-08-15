# 2026-07-03 — Șters complet backend Checklist PIF + Template-uri + Hermes AI

- **2026-07-03 — Șters complet backend Checklist PIF + Template-uri + Hermes AI** (SW v71):
  cod mort — backend complet fără niciun UI în SPA (confirmat zero referințe în frontend). Ion a
  ales ștergerea (peste #168, care le păstra „pentru Hermes viitor" — Hermes însuși e acum șters).
  **Șters:** `blueprints/assistant.py` (838L, tot Hermes + tools + memorie); rutele checklist
  (`/api/proiecte/<id>/checklist*` + `checklist-categorii`) și `/api/templates` +
  `init_default_templates()` din projects.py; `_pdf_section_checklist` + secțiunea checklist din
  export PDF (admin.py); ramura checklist din global_search; cele 4 tabele din backup/restore + din
  `VALID_TABLES` (utils.py). **Migration v22→v23** face `DROP TABLE IF EXISTS` pe `checklist_pif`,
  `checklist_categorii`, `project_templates`, `assistant_memory` + indexurile lor (SCHEMA_VERSION 23).
  `migrate_v4_to_v5` gardat pe existența `checklist_pif` (skip pe DB nou — altfel `ALTER TABLE
  checklist_pif` pica). Migrațiile istorice v1→v2 (creează `project_templates`) rămân — pe DB nou
  rulează apoi v23 le dă drop; NU re-adăuga aceste tabele în `init_db`. Restore ignoră silențios
  checklist/template/assistant din backup-uri vechi. Schema: 14→10 tabele. Snapshot/debrief nu mai
  au chei checklist. `app_settings` + `task_subtasks` PĂSTRATE (alte features). `scripts/llm_enrich*`
  (MiniMax pt enrich parametri) fără legătură cu Hermes — păstrat.

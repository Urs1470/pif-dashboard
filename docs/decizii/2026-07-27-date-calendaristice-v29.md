# Date calendaristice (v29, 2026-07-27)

**Nu stocam niciodata o data pe care nu o putem citi.** `utils.norm_date()`, chemata din
`get_json_or_400()` — palnia unica a tuturor scrierilor JSON — accepta ISO si formatele
romanesti (`23.02.2026`, `5/3/2026`), respinge cu 400 orice altceva, si lasa neatinse
valorile care incep deja cu ISO (ca sa nu ciunteasca timestampurile). Migrarea v29 a
normalizat ce intrase inainte de paza: `23.02.2026` pe un proiect, `02.07.2026` pe un task.

`/api/calendar` intoarce `probleme[]` cu orice data pe care SQLite nu o poate interpreta,
iar Calendarul o arata ca un KPI rosu. Motivul: o data necitibila nu se aseaza pe nicio zi,
deci randul disparea din calendar **fara niciun semn** — iar o absenta tacuta te invata sa
nu te bazezi pe restul.

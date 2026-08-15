# 2026-08-07 — `scripts/test_suite.py` crapa pe Windows inainte de orice test

- **2026-08-07 — `scripts/test_suite.py` crapa pe Windows inainte de orice test.**
  `Path.read_text()` fara `encoding` cade pe cp1252, iar `google_calendar.py` are
  ghilimele romanesti in comentarii: `UnicodeDecodeError` in analiza statica, deci
  ZERO teste rulate. Cele trei citiri au acum `encoding='utf-8'`.

# R-GQE-004

**R-GQE-004** — The `component_context` view MUST return one row per
  component, just its `Purpose` section's text, reading under the data
  contract `SPEC_GUIDELINES.md` §3.4 (`Purpose` is `component.md`'s
  first section, dependent-safe by construction since `D34`):

```sql
CREATE OR REPLACE VIEW component_context AS
SELECT
  id AS component_id,
  regexp_extract(body, '##\s*Purpose\s*\n(.*?)\n##', 1, 's') AS purpose
FROM component_docs;
```

  The `'s'` (DOTALL) flag MUST be present — without it, `.` does not
  match newlines, so a multi-line `Purpose` section silently extracts
  to an empty string instead of erroring (`D43`). Depends on
  `R-GQE-003`'s `component_docs` view, not raw files directly.

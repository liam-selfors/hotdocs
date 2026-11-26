# R-GQE-005

**R-GQE-005** — The `component_provenance` view MUST return one row per
  component, read directly from `provenance-writer`'s already-written
  manifests (`D29`):

```sql
CREATE OR REPLACE VIEW component_provenance AS
SELECT
  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
    AS component_id,
  *
FROM read_json('{repo_root}/verification/*/.provenance.json', filename:=true);
```

  `{repo_root}` substitution is the same as `R-GQE-001`. `read_json`
  (unlike `read_text`) genuinely supports `filename:=true`.

  **MUST degrade to an empty, correctly-shaped view — never an error —
  when no `.provenance.json` files exist yet** (`D13`): `read_json`
  raises on a glob matching zero files, unlike `read_text`, and a new
  project has no manifests yet. `load_views` (`R-GQE-007`) MUST check for at least one
  matching file first and fall back to an explicitly-typed empty
  `SELECT ... WHERE false` (`SPEC_GUIDELINES.md` §7's field list) when
  none exists, so a query naming any of this view's columns still
  succeeds, just returns zero rows.

  **A real consumer dependency, not an optional extra:** once a
  real `.provenance.json` exists, `read_json`'s auto-detection types
  `generated_at` as `TIMESTAMP WITH TIME ZONE` (it looks like an
  ISO-8601 timestamp), and materializing that type requires the `pytz`
  package. Any caller that actually queries this view against real
  provenance data MUST have `pytz` installed. Never pin columns via
  `read_json`'s `columns`: that drops the passthrough fields this view's
  `SELECT *` preserves.

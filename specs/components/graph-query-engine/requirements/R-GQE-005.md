# R-GQE-005

**R-GQE-005** — The `component_provenance` view MUST return one row per
  component, read directly from `provenance-writer`'s already-written
  manifests, reading under the data contract `SPEC_GUIDELINES.md` §7
  (the `.provenance.json` schema, including `provenance_hit` — `D29`):

```sql
CREATE OR REPLACE VIEW component_provenance AS
SELECT
  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
    AS component_id,
  *
FROM read_json('{repo_root}/verification/*/.provenance.json', filename:=true);
```

  `{repo_root}` substitution is the same as `R-GQE-001`. `read_json`
  (unlike `read_text`) genuinely supports `filename:=true` — confirmed
  by running this view, not assumed.

  **MUST degrade to an empty, correctly-shaped view — never an error —
  when no `.provenance.json` files exist yet** (`D13`): `read_json`
  raises on a glob matching zero files, unlike `read_text`, and "no
  component has ever been cold-regenerated through a real pipeline" is
  this corpus's own actual, expected state today, not a fixture
  artifact. `load_views` (`R-GQE-007`) MUST check for at least one
  matching file first and fall back to an explicitly-typed empty
  `SELECT ... WHERE false` (`SPEC_GUIDELINES.md` §7's field list) when
  none exists, so a query naming any of this view's columns still
  succeeds, just returns zero rows.

  **A real consumer dependency, not an optional extra:** once a
  real `.provenance.json` exists, `read_json`'s auto-detection types
  `generated_at` as `TIMESTAMP WITH TIME ZONE` (it looks like an
  ISO-8601 timestamp), and materializing that type requires the `pytz`
  package. Any caller that actually queries this view against real
  provenance data MUST have `pytz` installed — confirmed by hand that
  pinning `generated_at`'s type via `read_json`'s `columns` parameter
  isn't a clean alternative, since `columns` forces a closed schema
  (the same intersection-only behavior `R-GQE-002`'s rewrite already
  found), which would drop every other passthrough field this view's
  `SELECT *` otherwise preserves.

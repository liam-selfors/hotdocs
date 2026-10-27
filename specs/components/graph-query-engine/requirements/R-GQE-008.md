# R-GQE-008

**R-GQE-008** — The `decision_lineage` view MUST return one row per
  decision record (`D88`), reading `id`/`title`/`status`/
  `last_ratified_commit`/`supersedes` via `read_text` + regex over
  `specs/decisions/*.md` — never `read_yaml_frontmatter`'s struct
  auto-detection, which (`R-GQE-002`'s own documented lesson, `D44`)
  silently drops a column absent from every file in the glob at once,
  true of `supersedes` in most of this corpus today:

```sql
CREATE OR REPLACE VIEW decision_lineage AS
SELECT
  regexp_extract(content, 'id:\s*(\S+)', 1) AS id,
  regexp_extract(content, 'title:\s*(.+)', 1) AS title,
  regexp_extract(content, 'status:\s*(\S+)', 1) AS status,
  NULLIF(regexp_extract(content, 'last_ratified_commit:\s*(\S+)', 1), '') AS last_ratified_commit,
  NULLIF(regexp_extract(content, 'supersedes:\s*(\S+)', 1), '') AS supersedes
FROM read_text('{repo_root}/specs/decisions/*.md');
```

  A dedicated view, not an extension of the existing `nodes`/`edges`
  shared views — `last_ratified_commit`/`supersedes` have no
  equivalent column on any other `kind` those views carry, and
  extending their shape risks every existing consumer
  (`impact-analyzer`, `spec-bundle-assembler`, `spec-linter`'s other
  rules, `corpus-graph-builder`) for a fact only decision records
  need. `R-LINT-029` MUST query this view for its `supersedes`/
  `deprecated` consistency check, the same "query the shared view,
  never re-implement the scan" discipline `R-LINT-021` already
  established for traceability.

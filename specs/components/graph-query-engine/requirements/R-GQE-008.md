# R-GQE-008

**R-GQE-008** — The `decision_lineage` view MUST return one row per
  decision record: `id` and `last_ratified_commit` only (`D74`) —
  `status`/`supersedes`/`builds_on` live in `nodes`/`edges` directly,
  the single canonical home for anything graph-shaped;
  `last_ratified_commit` has no equivalent column there and stays
  here, the one fact only decision records carry:

```sql
CREATE OR REPLACE VIEW decision_lineage AS
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1) AS id,
  NULLIF(regexp_extract(fm, '(?m)^last_ratified_commit:\s*(\S+)', 1), '') AS last_ratified_commit
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d
WHERE fm != '';
```

  `R-LINT-029`/`030` MUST query `nodes`/`edges` for `status`/
  `supersedes`/`builds_on`, and this view only for
  `last_ratified_commit` when a temporal comparison is actually
  needed (`decision-drift-detector`'s own job, not spec-linter's).

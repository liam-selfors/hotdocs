# R-GQE-008

**R-GQE-008** — The `decision_lineage` view MUST return one row per
  decision record: `id` and `last_ratified_commit` only (`D74`):

```sql
CREATE OR REPLACE VIEW decision_lineage AS
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1) AS id,
  NULLIF(regexp_extract(fm, '(?m)^last_ratified_commit:\s*(\S+)', 1), '') AS last_ratified_commit
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d
WHERE fm != '';
```

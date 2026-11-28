# R-GQE-001

**R-GQE-001** — The `nodes` view MUST return one row per spec id across
  eight kinds (`component`, `capability`, `var`, `decision`,
  `guarantee`, `requirement`, `acceptance`, `capability_scenario`).
  `decision` rows may use `read_yaml_frontmatter` despite `D13`'s
  sparse-column gotcha: `id`/`title`/`status` are required on every
  decision record (`R-GQE-002` reads the sparse `supersedes`/`builds_on`
  via `read_text` + regex):

```sql
CREATE OR REPLACE VIEW nodes AS
SELECT id, title, status, 'component' AS kind, NULL AS owner_component_id
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true)
UNION ALL
SELECT id, title, status, 'capability', NULL
FROM read_yaml_frontmatter('{repo_root}/specs/product/*.md', filename:=true)
UNION ALL
SELECT id, title, status, 'var', NULL
FROM read_yaml_frontmatter('{repo_root}/specs/vars/*.md', filename:=true)
UNION ALL
SELECT id, title, status, 'decision', NULL
FROM read_yaml_frontmatter('{repo_root}/specs/decisions/*.md', filename:=true)
UNION ALL
SELECT
  regexp_extract(filename, '(G-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'guarantee',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/interface/guarantees/', 1)
FROM read_text('{repo_root}/specs/components/*/interface/guarantees/*.md')
UNION ALL
SELECT
  regexp_extract(filename, '(R-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'requirement',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/requirements/', 1)
FROM read_text('{repo_root}/specs/components/*/requirements/*.md')
UNION ALL
SELECT
  regexp_extract(filename, '(AC-[A-Za-z0-9-]+)\.md$', 1), NULL, NULL, 'acceptance',
  'comp-' || regexp_extract(filename, 'specs/components/([^/]+)/acceptance/', 1)
FROM read_text('{repo_root}/specs/components/*/acceptance/*.md')
UNION ALL
SELECT UNNEST(regexp_extract_all(content, '### (CS-[A-Za-z0-9-]+)', 1)), NULL, NULL, 'capability_scenario', NULL
FROM read_text('{repo_root}/specs/product/*.md');
```

  `{repo_root}` MUST be substituted with the caller's absolute repo
  root before execution (`R-GQE-007`) — this view's SQL is not valid on
  its own. `read_text` MUST NOT be called with `filename:=true` — it
  has no such parameter and errors if given one; it already
  returns `filename` unconditionally. `owner_component_id` MUST be
  `NULL` for `capability_scenario` rows.

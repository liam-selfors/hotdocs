# R-GQE-001

**R-GQE-001** — The `nodes` view MUST return one row per spec id across
  seven kinds (`component`, `capability`, `var`, `guarantee`,
  `requirement`, `acceptance`, `capability_scenario`), reading under the
  data contracts `SPEC_GUIDELINES.md` §2 (frontmatter: `component`/
  `capability`/`var` kinds) and §3.4/D15 (unit-file-per-id: `guarantee`/
  `requirement`/`acceptance` kinds carry no frontmatter, identity is the
  filename) and §5 (capability scenarios are `### CS-...` headings
  inside a product capability file, not a file of their own):

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
  has no such parameter and errors if given one (`D43`); it already
  returns `filename` unconditionally. `owner_component_id` MUST be
  `NULL` for `capability_scenario` rows — their parent is a capability,
  not a component; the `covers` edge (`R-GQE-002`) carries that
  relationship instead.

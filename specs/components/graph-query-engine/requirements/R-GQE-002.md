# R-GQE-002

**R-GQE-002** — The `edges` view MUST return one row per
  `(source_id, target_id, edge_type)`, reading under the data contracts
  `SPEC_GUIDELINES.md` §2 (`depends_on`/`realizes`/`uses_var`/
  `depends_on_guarantees`/`builds_on` as list-valued frontmatter
  fields, `supersedes` as scalar-valued) and §5 (`Covers:` as a
  body-text tag, never frontmatter — one per `component-acceptance`
  file per D1, one per capability scenario heading in a product
  file):

```sql
CREATE OR REPLACE VIEW edges AS
SELECT
  regexp_extract(content, 'id:\s*(\S+)', 1) AS source_id,
  UNNEST(list_filter(list_transform(
    string_split(regexp_extract(content, 'depends_on:\s*\[([^\]]*)\]', 1), ','),
    lambda x: trim(x)
  ), lambda x: x != '')) AS target_id,
  'depends_on' AS edge_type
FROM read_text('{repo_root}/specs/components/*/component.md')
UNION ALL
SELECT
  regexp_extract(content, 'id:\s*(\S+)', 1),
  UNNEST(list_filter(list_transform(
    string_split(regexp_extract(content, 'realizes:\s*\[([^\]]*)\]', 1), ','),
    lambda x: trim(x)
  ), lambda x: x != '')),
  'realizes'
FROM read_text('{repo_root}/specs/components/*/component.md')
UNION ALL
SELECT
  regexp_extract(content, 'id:\s*(\S+)', 1),
  UNNEST(list_filter(list_transform(
    string_split(regexp_extract(content, 'uses_var:\s*\[([^\]]*)\]', 1), ','),
    lambda x: trim(x)
  ), lambda x: x != '')),
  'uses_var'
FROM read_text('{repo_root}/specs/components/*/component.md')
UNION ALL
SELECT
  regexp_extract(content, 'id:\s*(\S+)', 1),
  UNNEST(list_filter(list_transform(
    string_split(regexp_extract(content, 'depends_on_guarantees:\s*\[([^\]]*)\]', 1), ','),
    lambda x: trim(x)
  ), lambda x: x != '')),
  'depends_on_guarantees'
FROM read_text('{repo_root}/specs/components/*/component.md')
UNION ALL
SELECT
  regexp_extract(filename, '(AC-[A-Za-z0-9-]+)\.md$', 1),
  regexp_extract(content, 'Covers:\s*(\S+)', 1), 'covers'
FROM read_text('{repo_root}/specs/components/*/acceptance/*.md')
UNION ALL
SELECT m['cs_id'], m['target'], 'covers'
FROM (
  SELECT UNNEST(regexp_extract_all(
    content, '### (CS-[A-Za-z0-9-]+)\s*\nCovers:\s*(\S+)', ['cs_id', 'target']
  )) AS m
  FROM read_text('{repo_root}/specs/product/*.md')
)
UNION ALL
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1),
  regexp_extract(fm, '(?m)^supersedes:\s*(\S+)', 1),
  'supersedes'
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d
WHERE regexp_extract(fm, '(?m)^supersedes:\s*(\S+)', 1) != ''
UNION ALL
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1),
  UNNEST(list_filter(list_transform(
    string_split(regexp_extract(fm, '(?m)^builds_on:\s*\[([^\]]*)\]', 1), ','),
    lambda x: trim(x)
  ), lambda x: x != '')),
  'builds_on'
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d;
```

  `{repo_root}` substitution and the `read_text` `filename:=true`
  prohibition are the same as `R-GQE-001`. The four `depends_on`/
  `realizes`/`uses_var`/`depends_on_guarantees` arms MUST read
  `component.md` via `read_text` and extract each field with a regex
  over the flow-style `key: [a, b]` syntax `SPEC_GUIDELINES.md` §2
  requires (confirmed via corpus-wide grep: never YAML block-list
  style) — NOT via `read_yaml_frontmatter`'s struct-column
  auto-detection, which silently DROPS a declared column from its
  result schema (a bind-time "column not found" error at the call
  site, not a null value) when that key is absent from every file in
  the glob at once (`D13`) — true of `uses_var`/`depends_on_guarantees`
  in sparse corpora such as `graph-query-engine`'s own test fixtures,
  where no component happens to use either field. The same reasoning
  governs `supersedes`/`builds_on`'s two new arms (`D74`): neither is
  present on more than a handful of decision records today, so
  `read_yaml_frontmatter` would silently drop either column outright.

  The decision arms MUST read only a record's frontmatter block, never
  its whole text: a decision's prose can quote a field, and matching
  anywhere turned `D137`'s quoted `supersedes: [D17]` into a
  `supersedes` edge that no decision declares (`D176`). Each arm
  extracts the block (`regexp_extract(content, '^---\n(.*?)\n---\n', 1,
  's')`) first, then matches each field at a line start within it.

# R-GQE-002

**R-GQE-002** — The `edges` view MUST return one row per
  `(source_id, target_id, edge_type)`, reading under the data contracts
  `SPEC_GUIDELINES.md` §2 (`depends_on`/`realizes`/`uses_var`/
  `depends_on_guarantees` as list-valued frontmatter fields) and §5
  (`Covers:` as a body-text tag, never frontmatter — one per
  `component-acceptance` file per D15, one per capability scenario
  heading in a product file):

```sql
CREATE OR REPLACE VIEW edges AS
SELECT id AS source_id, UNNEST(depends_on) AS target_id, 'depends_on' AS edge_type
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md')
UNION ALL
SELECT id, UNNEST(realizes), 'realizes'
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md')
UNION ALL
SELECT id, UNNEST(uses_var), 'uses_var'
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md')
UNION ALL
SELECT id, UNNEST(depends_on_guarantees), 'depends_on_guarantees'
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md')
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
);
```

  `{repo_root}` substitution and the `read_text` `filename:=true`
  prohibition are the same as `R-GQE-001`.

-- Generated per specs/components/graph-query-engine/requirements/R-GQE-001..006.
-- {repo_root} is substituted with an absolute path by load_views() before
-- execution (R-GQE-007) -- this file is not valid SQL on its own.

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

---

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
);

---

CREATE OR REPLACE VIEW component_docs AS
SELECT fm.*, t.content AS body
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true) fm
JOIN read_text('{repo_root}/specs/components/*/component.md') t USING (filename);

---

CREATE OR REPLACE VIEW component_context AS
SELECT
  id AS component_id,
  regexp_extract(body, '##\s*Purpose\s*\n(.*?)\n##', 1, 's') AS purpose
FROM component_docs;

---

CREATE OR REPLACE VIEW component_provenance AS
SELECT
  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
    AS component_id,
  *
FROM read_json('{repo_root}/verification/*/.provenance.json', filename:=true);

---

CREATE OR REPLACE VIEW component_size AS
SELECT
  regexp_extract(filename, 'specs/components/([^/]+)/', 1) AS component_id,
  sum(len(list_filter(
    regexp_split_to_array(
      trim(regexp_replace(content, '^---\n.*?\n---\n', '', 's')),
      '\s+'
    ),
    lambda x: x != ''
  ))) AS word_count
FROM read_text('{repo_root}/specs/components/*/**/*.md')
GROUP BY 1;

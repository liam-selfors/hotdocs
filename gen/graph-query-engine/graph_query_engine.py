"""Graph Query Engine: the eight shared DuckDB views over the spec corpus."""

import re
from pathlib import Path

import duckdb

_EMPTY_FRONTMATTER = (
    "(SELECT NULL::VARCHAR AS id, NULL::VARCHAR AS title, "
    "NULL::VARCHAR AS status, NULL::VARCHAR AS filename WHERE false)"
)

_YAML_CALL = re.compile(r"read_yaml_frontmatter\('([^']*)', filename:=true\)")

_NODES = r"""
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
"""

_EDGES = r"""
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
"""

_COMPONENT_DOCS = r"""
CREATE OR REPLACE VIEW component_docs AS
SELECT fm.*, t.content AS body
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true) fm
JOIN read_text('{repo_root}/specs/components/*/component.md') t USING (filename);
"""

_COMPONENT_CONTEXT = r"""
CREATE OR REPLACE VIEW component_context AS
SELECT
  id AS component_id,
  regexp_extract(body, '##\s*Purpose\s*\n(.*?)\n##', 1, 's') AS purpose
FROM component_docs;
"""

_PROVENANCE_GLOB = "{repo_root}/verification/*/.provenance.json"

_COMPONENT_PROVENANCE = r"""
CREATE OR REPLACE VIEW component_provenance AS
SELECT
  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
    AS component_id,
  *
FROM read_json('{repo_root}/verification/*/.provenance.json', filename:=true);
"""

_COMPONENT_PROVENANCE_EMPTY = r"""
CREATE OR REPLACE VIEW component_provenance AS
SELECT
  NULL::VARCHAR AS component_id,
  NULL::VARCHAR AS spec_bundle_hash,
  NULL::TIMESTAMPTZ AS generated_at,
  NULL::STRUCT(result VARCHAR) AS verification_report,
  NULL::STRUCT(result VARCHAR) AS license_scan,
  NULL::STRUCT(result VARCHAR) AS secret_scan,
  NULL::BOOLEAN AS provenance_hit,
  NULL::VARCHAR AS filename
WHERE false;
"""

_COMPONENT_SIZE = r"""
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
WHERE NOT ends_with(filename, '/testing.md')
GROUP BY 1;
"""

_DECISION_LINEAGE = r"""
CREATE OR REPLACE VIEW decision_lineage AS
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1) AS id,
  NULLIF(regexp_extract(fm, '(?m)^last_ratified_commit:\s*(\S+)', 1), '') AS last_ratified_commit
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d
WHERE fm != '';
"""

_BUNDLE_SIZE = r"""
CREATE OR REPLACE VIEW bundle_size AS
WITH docs AS (
  SELECT
    regexp_extract(filename, 'specs/components/([^/]+)/', 1) AS c,
    regexp_extract(filename, 'specs/components/[^/]+/(.*)$', 1) AS rel,
    content,
    regexp_replace(content, '^---\n.*?\n---\n', '', 's') AS body
  FROM read_text('{repo_root}/specs/components/*/**/*.md')
),
counted AS (
  SELECT c, rel, content,
    CASE WHEN rel = 'component.md'
      THEN array_to_string(list_filter(regexp_split_to_array(body, '\n## '),
             lambda s: NOT regexp_matches(s, '^(Rationale|Open questions|Change log)\s*\n')), ' ')
      ELSE body END AS text,
    CASE WHEN rel = 'component.md'
      THEN coalesce(list_filter(regexp_split_to_array(body, '\n## '),
             lambda s: regexp_matches(s, '^Purpose\n'))[1], '')
      ELSE '' END AS purpose
  FROM docs
),
w AS (
  SELECT c, rel, content,
    len(list_filter(regexp_split_to_array(trim(text), '\s+'), lambda x: x != '')) AS words,
    len(list_filter(regexp_split_to_array(trim(purpose), '\s+'), lambda x: x != '')) AS purpose_words
  FROM counted
),
own AS (
  SELECT c,
    sum(words) FILTER (WHERE rel = 'component.md' OR rel = 'constraints.md'
      OR starts_with(rel, 'requirements/') OR starts_with(rel, 'interface/')) AS spec_words,
    sum(words) FILTER (WHERE starts_with(rel, 'interface/')) AS interface_words,
    coalesce(sum(words) FILTER (WHERE rel = 'testing.md'), 0) AS testing_words,
    sum(purpose_words) AS purpose_words
  FROM w GROUP BY c
),
arch AS (
  SELECT
    CASE WHEN ends_with(filename, '/SPEC_GUIDELINES.md') THEN 'SPEC_GUIDELINES.md'
      ELSE regexp_extract(filename, '(specs/architecture/[^/]+\.md)$', 1) END AS path,
    len(list_filter(regexp_split_to_array(trim(regexp_replace(content, '^---\n.*?\n---\n', '', 's')), '\s+'),
      lambda x: x != '')) AS words
  FROM read_text(['{repo_root}/specs/architecture/*.md', '{repo_root}/SPEC_GUIDELINES.md'])
),
impl AS (
  SELECT d.c, coalesce(sum(a.words), 0) AS words
  FROM (SELECT c, unnest(regexp_extract_all(
          regexp_extract(content, '(?m)^Implements:(.*)$', 1), '`([^`]+)`', 1)) AS path
        FROM w WHERE rel = 'interface/library.md') d
  JOIN arch a ON a.path = d.path
  GROUP BY d.c
),
deps AS (
  SELECT c, regexp_replace(trim(dep), '^comp-', '') AS dep
  FROM (SELECT c, unnest(string_split(
          regexp_extract(content, '(?m)^depends_on:\s*\[(.*?)\]', 1), ',')) AS dep
        FROM w WHERE rel = 'component.md')
  WHERE trim(dep) != ''
),
dep_words AS (
  SELECT deps.c, sum(o.interface_words) AS interface_words, sum(o.purpose_words) AS purpose_words
  FROM deps JOIN own o ON o.c = deps.dep
  GROUP BY deps.c
),
criteria AS (
  SELECT a.c, a.words + coalesce(r.words, 0) AS words
  FROM (SELECT c, words, regexp_extract(content, '(?m)^Covers:\s*(\S+)', 1) AS covers
        FROM w WHERE starts_with(rel, 'acceptance/')) a
  LEFT JOIN w r ON r.c = a.c AND r.rel = 'requirements/' || a.covers || '.md'
)
SELECT
  o.c AS component_id,
  o.spec_words + coalesce(i.words, 0) + coalesce(dw.interface_words, 0)
    + coalesce(dw.purpose_words, 0) AS generator_words,
  CASE WHEN max(cr.words) IS NULL THEN 0
    ELSE max(cr.words) + coalesce(o.interface_words, 0) + coalesce(i.words, 0)
      + coalesce(dw.interface_words, 0) + o.testing_words END AS criterion_words_max
FROM own o
LEFT JOIN impl i ON i.c = o.c
LEFT JOIN dep_words dw ON dw.c = o.c
LEFT JOIN criteria cr ON cr.c = o.c
WHERE o.spec_words IS NOT NULL
GROUP BY o.c, o.spec_words, o.interface_words, o.testing_words, i.words, dw.interface_words, dw.purpose_words;
"""


def _has_match(con, pattern):
    return con.execute("SELECT count(*) FROM glob(?)", [pattern]).fetchone()[0] > 0


def _prepare(con, sql, root):
    sql = sql.replace("{repo_root}", root)

    def _sub(m):
        if _has_match(con, m.group(1)):
            return m.group(0)
        return _EMPTY_FRONTMATTER

    return _YAML_CALL.sub(_sub, sql)


def load_views(con: duckdb.DuckDBPyConnection, repo_root: Path) -> None:
    root = str(repo_root)
    if _has_match(con, _PROVENANCE_GLOB.replace("{repo_root}", root)):
        provenance = _COMPONENT_PROVENANCE
    else:
        provenance = _COMPONENT_PROVENANCE_EMPTY
    for sql in (
        _NODES,
        _EDGES,
        _COMPONENT_DOCS,
        _COMPONENT_CONTEXT,
        provenance,
        _COMPONENT_SIZE,
        _DECISION_LINEAGE,
        _BUNDLE_SIZE,
    ):
        con.execute(_prepare(con, sql, root))

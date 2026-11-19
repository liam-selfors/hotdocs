"""Graph Query Engine: the seven shared DuckDB views over a spec corpus.

`load_views(con, repo_root)` creates `nodes`, `edges`, `component_docs`,
`component_context`, `component_provenance`, `component_size` and
`decision_lineage` on `con`. The SQL below keeps a `{repo_root}`
placeholder that is substituted only at call time.

The `yaml` community extension must already be installed and loaded on
`con` (`INSTALL yaml FROM community` then `LOAD yaml`).
"""

import glob
import os
import re
from pathlib import Path

PLACEHOLDER = "{repo_root}"

NODES_SQL = r"""
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

EDGES_SQL = r"""
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

COMPONENT_DOCS_SQL = r"""
CREATE OR REPLACE VIEW component_docs AS
SELECT fm.*, t.content AS body
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true) fm
JOIN read_text('{repo_root}/specs/components/*/component.md') t USING (filename);
"""

COMPONENT_CONTEXT_SQL = r"""
CREATE OR REPLACE VIEW component_context AS
SELECT
  id AS component_id,
  regexp_extract(body, '##\s*Purpose\s*\n(.*?)\n##', 1, 's') AS purpose
FROM component_docs;
"""

COMPONENT_PROVENANCE_SQL = r"""
CREATE OR REPLACE VIEW component_provenance AS
SELECT
  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
    AS component_id,
  *
FROM read_json('{repo_root}/verification/*/.provenance.json', filename:=true);
"""

COMPONENT_PROVENANCE_EMPTY_SQL = r"""
CREATE OR REPLACE VIEW component_provenance AS
SELECT
  NULL::VARCHAR AS component_id,
  NULL::VARCHAR AS spec_bundle_hash,
  NULL::TIMESTAMP WITH TIME ZONE AS generated_at,
  NULL::STRUCT(status VARCHAR) AS verification_report,
  NULL::STRUCT(status VARCHAR) AS license_scan,
  NULL::STRUCT(status VARCHAR) AS secret_scan,
  NULL::BOOLEAN AS provenance_hit,
  NULL::VARCHAR AS filename
WHERE false;
"""

COMPONENT_SIZE_SQL = r"""
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

DECISION_LINEAGE_SQL = r"""
CREATE OR REPLACE VIEW decision_lineage AS
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1) AS id,
  NULLIF(regexp_extract(fm, '(?m)^last_ratified_commit:\s*(\S+)', 1), '') AS last_ratified_commit
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d
WHERE fm != '';
"""

PROVENANCE_GLOB = "verification/*/.provenance.json"

_YAML_CALL = re.compile(
    r"read_yaml_frontmatter\('\{repo_root\}/([^']*)', filename:=true\)"
)

_EMPTY_FRONTMATTER = (
    "(SELECT NULL::VARCHAR AS id, NULL::VARCHAR AS title, "
    "NULL::VARCHAR AS status, NULL::VARCHAR AS filename WHERE false)"
)


def _has_match(root, pattern):
    return len(glob.glob(os.path.join(root, pattern))) > 0


def _guard_yaml(sql, root):
    def repl(match):
        if _has_match(root, match.group(1)):
            return match.group(0)
        return _EMPTY_FRONTMATTER

    return _YAML_CALL.sub(repl, sql)


def _render(sql, root):
    return _guard_yaml(sql, root).replace(PLACEHOLDER, root)


def load_views(con, repo_root):
    root = str(Path(repo_root))
    if _has_match(root, PROVENANCE_GLOB):
        provenance_sql = COMPONENT_PROVENANCE_SQL
    else:
        provenance_sql = COMPONENT_PROVENANCE_EMPTY_SQL
    for sql in (
        NODES_SQL,
        EDGES_SQL,
        COMPONENT_DOCS_SQL,
        COMPONENT_CONTEXT_SQL,
        provenance_sql,
        COMPONENT_SIZE_SQL,
        DECISION_LINEAGE_SQL,
    ):
        con.execute(_render(sql, root))

"""Graph Query Engine: the seven shared DuckDB views over the spec corpus.

`load_views(con, repo_root)` creates (or replaces) `nodes`, `edges`,
`component_docs`, `component_context`, `component_provenance`,
`component_size` and `decision_lineage` on a DuckDB connection.

The caller must already have run `INSTALL yaml FROM community` and
`LOAD yaml` on `con`; this module does not install or load extensions.

The SQL below carries a `{repo_root}` placeholder that is substituted only
at `load_views()` call time, never at generation time.
"""

import glob
import re
from pathlib import Path

REPO_ROOT_PLACEHOLDER = "{repo_root}"

NODES_SQL = r"""CREATE OR REPLACE VIEW nodes AS
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

EDGES_SQL = r"""CREATE OR REPLACE VIEW edges AS
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

COMPONENT_DOCS_SQL = r"""CREATE OR REPLACE VIEW component_docs AS
SELECT fm.*, t.content AS body
FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true) fm
JOIN read_text('{repo_root}/specs/components/*/component.md') t USING (filename);
"""

COMPONENT_CONTEXT_SQL = r"""CREATE OR REPLACE VIEW component_context AS
SELECT
  id AS component_id,
  regexp_extract(body, '##\s*Purpose\s*\n(.*?)\n##', 1, 's') AS purpose
FROM component_docs;
"""

COMPONENT_PROVENANCE_SQL = r"""CREATE OR REPLACE VIEW component_provenance AS
SELECT
  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\.provenance\.json$', 1)
    AS component_id,
  *
FROM read_json('{repo_root}/verification/*/.provenance.json', filename:=true);
"""

COMPONENT_SIZE_SQL = r"""CREATE OR REPLACE VIEW component_size AS
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
"""

DECISION_LINEAGE_SQL = r"""CREATE OR REPLACE VIEW decision_lineage AS
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1) AS id,
  NULLIF(regexp_extract(fm, '(?m)^last_ratified_commit:\s*(\S+)', 1), '') AS last_ratified_commit
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d
WHERE fm != '';
"""

# Dependency order: component_context selects from component_docs.
VIEW_SQL = [
    ("nodes", NODES_SQL),
    ("edges", EDGES_SQL),
    ("component_docs", COMPONENT_DOCS_SQL),
    ("component_context", COMPONENT_CONTEXT_SQL),
    ("component_provenance", COMPONENT_PROVENANCE_SQL),
    ("component_size", COMPONENT_SIZE_SQL),
    ("decision_lineage", DECISION_LINEAGE_SQL),
]

# Typed, always-empty stand-in for a read_yaml_frontmatter call whose glob
# matches zero files (R-GQE-007).
EMPTY_FRONTMATTER_RELATION = (
    "(SELECT CAST(NULL AS VARCHAR) AS id, "
    "CAST(NULL AS VARCHAR) AS title, "
    "CAST(NULL AS VARCHAR) AS status, "
    "CAST(NULL AS VARCHAR) AS filename "
    "WHERE false)"
)

# Typed, always-empty stand-in for the read_json call when no
# .provenance.json manifest exists yet (R-GQE-005).
EMPTY_PROVENANCE_RELATION = (
    "(SELECT CAST(NULL AS VARCHAR) AS filename, "
    "CAST(NULL AS VARCHAR) AS spec_bundle_hash, "
    "CAST(NULL AS TIMESTAMP WITH TIME ZONE) AS generated_at, "
    "CAST(NULL AS STRUCT(status VARCHAR)) AS verification_report, "
    "CAST(NULL AS STRUCT(status VARCHAR)) AS license_scan, "
    "CAST(NULL AS STRUCT(status VARCHAR)) AS secret_scan, "
    "CAST(NULL AS BOOLEAN) AS provenance_hit "
    "WHERE false)"
)

_YAML_CALL_RE = re.compile(r"read_yaml_frontmatter\('([^']*)', filename:=true\)")
_JSON_CALL_RE = re.compile(r"read_json\('([^']*)', filename:=true\)")


def _replace_empty_globs(sql, call_re, empty_relation):
    def _sub(match):
        if glob.glob(match.group(1)):
            return match.group(0)
        return empty_relation

    return call_re.sub(_sub, sql)


def render_view_sql(sql, repo_root):
    """Substitute repo_root and swap zero-match calls for empty relations."""
    rendered = sql.replace(REPO_ROOT_PLACEHOLDER, str(repo_root))
    rendered = _replace_empty_globs(rendered, _YAML_CALL_RE, EMPTY_FRONTMATTER_RELATION)
    rendered = _replace_empty_globs(rendered, _JSON_CALL_RE, EMPTY_PROVENANCE_RELATION)
    return rendered


def load_views(con, repo_root: Path) -> None:
    """Create (or replace) all seven views on `con`, scoped to `repo_root`.

    Any error raised by a view's CREATE statement propagates to the caller.
    """
    for _name, sql in VIEW_SQL:
        con.execute(render_view_sql(sql, repo_root))
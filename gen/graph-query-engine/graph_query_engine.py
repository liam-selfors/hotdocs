"""Shared DuckDB view definitions for the spec corpus (specs/architecture/graph-query-engine.md).

The CREATE VIEW SQL bodies below are reproduced from the component's own
requirements (R-GQE-001..008); only the {repo_root} substitution and the
zero-match-glob fallbacks around read_yaml_frontmatter/read_json call sites
(R-GQE-007) are this module's own logic.
"""

from __future__ import annotations

import os

import duckdb


def _sql_quote(value: str) -> str:
    return value.replace("'", "''")


def _glob_has_matches(con: duckdb.DuckDBPyConnection, pattern_escaped: str) -> bool:
    row = con.execute(f"SELECT count(*) FROM glob('{pattern_escaped}')").fetchone()
    return bool(row[0])


_NODES_YAML_BRANCHES = [
    (
        "component",
        "specs/components/*/component.md",
        "SELECT id, title, status, 'component' AS kind, NULL AS owner_component_id\n"
        "FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true)",
    ),
    (
        "capability",
        "specs/product/*.md",
        "SELECT id, title, status, 'capability', NULL\n"
        "FROM read_yaml_frontmatter('{repo_root}/specs/product/*.md', filename:=true)",
    ),
    (
        "var",
        "specs/vars/*.md",
        "SELECT id, title, status, 'var', NULL\n"
        "FROM read_yaml_frontmatter('{repo_root}/specs/vars/*.md', filename:=true)",
    ),
    (
        "decision",
        "specs/decisions/*.md",
        "SELECT id, title, status, 'decision', NULL\n"
        "FROM read_yaml_frontmatter('{repo_root}/specs/decisions/*.md', filename:=true)",
    ),
]

_NODES_READTEXT_SQL = r"""
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
FROM read_text('{repo_root}/specs/product/*.md')
""".strip()

_EDGES_SQL = r"""
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
""".strip()

_COMPONENT_DOCS_REAL_SQL = (
    "CREATE OR REPLACE VIEW component_docs AS\n"
    "SELECT fm.*, t.content AS body\n"
    "FROM read_yaml_frontmatter('{repo_root}/specs/components/*/component.md', filename:=true) fm\n"
    "JOIN read_text('{repo_root}/specs/components/*/component.md') t USING (filename);"
)

_COMPONENT_DOCS_EMPTY_SQL = (
    "CREATE OR REPLACE VIEW component_docs AS\n"
    "SELECT NULL::VARCHAR AS id, NULL::VARCHAR AS title, NULL::VARCHAR AS status, "
    "NULL::VARCHAR AS body WHERE FALSE;"
)

_COMPONENT_CONTEXT_SQL = r"""
CREATE OR REPLACE VIEW component_context AS
SELECT
  id AS component_id,
  regexp_extract(body, '##\s*Purpose\s*\n(.*?)\n##', 1, 's') AS purpose
FROM component_docs;
""".strip()

_COMPONENT_PROVENANCE_REAL_SQL = (
    "CREATE OR REPLACE VIEW component_provenance AS\n"
    "SELECT\n"
    "  'comp-' || regexp_extract(filename, 'verification/([^/]+)/\\.provenance\\.json$', 1)\n"
    "    AS component_id,\n"
    "  *\n"
    "FROM read_json('{repo_root}/verification/*/.provenance.json', filename:=true);"
)

_COMPONENT_PROVENANCE_EMPTY_SQL = (
    "CREATE OR REPLACE VIEW component_provenance AS\n"
    "SELECT\n"
    "  NULL::VARCHAR AS component_id,\n"
    "  NULL::VARCHAR AS spec_bundle_hash,\n"
    "  NULL::TIMESTAMP WITH TIME ZONE AS generated_at,\n"
    "  NULL::JSON AS verification_report,\n"
    "  NULL::JSON AS license_scan,\n"
    "  NULL::JSON AS secret_scan,\n"
    "  NULL::BOOLEAN AS provenance_hit\n"
    "WHERE FALSE;"
)

_COMPONENT_SIZE_SQL = r"""
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
""".strip()

_DECISION_LINEAGE_SQL = r"""
CREATE OR REPLACE VIEW decision_lineage AS
SELECT
  regexp_extract(fm, '(?m)^id:\s*(\S+)', 1) AS id,
  NULLIF(regexp_extract(fm, '(?m)^last_ratified_commit:\s*(\S+)', 1), '') AS last_ratified_commit
FROM (SELECT regexp_extract(content, '^---\n(.*?)\n---\n', 1, 's') AS fm
  FROM read_text('{repo_root}/specs/decisions/*.md')) AS d
WHERE fm != '';
""".strip()


def _build_nodes_sql(con: duckdb.DuckDBPyConnection, root_escaped: str) -> str:
    branches = []
    for kind, rel_pattern, real_sql in _NODES_YAML_BRANCHES:
        pattern_escaped = f"{root_escaped}/{rel_pattern}"
        if _glob_has_matches(con, pattern_escaped):
            branches.append(real_sql.replace("{repo_root}", root_escaped))
        else:
            branches.append(
                "SELECT NULL::VARCHAR AS id, NULL::VARCHAR AS title, NULL::VARCHAR AS status, "
                f"'{kind}' AS kind, NULL::VARCHAR AS owner_component_id WHERE FALSE"
            )
    branches.append(_NODES_READTEXT_SQL.replace("{repo_root}", root_escaped))
    return "CREATE OR REPLACE VIEW nodes AS\n" + "\nUNION ALL\n".join(branches) + ";"


def _build_component_docs_sql(con: duckdb.DuckDBPyConnection, root_escaped: str) -> str:
    pattern_escaped = f"{root_escaped}/specs/components/*/component.md"
    if _glob_has_matches(con, pattern_escaped):
        return _COMPONENT_DOCS_REAL_SQL.replace("{repo_root}", root_escaped)
    return _COMPONENT_DOCS_EMPTY_SQL


def _build_component_provenance_sql(con: duckdb.DuckDBPyConnection, root_escaped: str) -> str:
    pattern_escaped = f"{root_escaped}/verification/*/.provenance.json"
    if _glob_has_matches(con, pattern_escaped):
        return _COMPONENT_PROVENANCE_REAL_SQL.replace("{repo_root}", root_escaped)
    return _COMPONENT_PROVENANCE_EMPTY_SQL


def load_views(con: duckdb.DuckDBPyConnection, repo_root: os.PathLike | str) -> None:
    root_escaped = _sql_quote(os.fspath(repo_root))

    con.execute(_build_nodes_sql(con, root_escaped))
    con.execute(_EDGES_SQL.replace("{repo_root}", root_escaped))
    con.execute(_build_component_docs_sql(con, root_escaped))
    con.execute(_COMPONENT_CONTEXT_SQL)
    con.execute(_build_component_provenance_sql(con, root_escaped))
    con.execute(_COMPONENT_SIZE_SQL.replace("{repo_root}", root_escaped))
    con.execute(_DECISION_LINEAGE_SQL.replace("{repo_root}", root_escaped))
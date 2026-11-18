# hotdocs-criterion: sha256:5908af2bd458bf9e5cba755ecf625e8c67a5f7857db0a52c49301665ea80429a
"""AC-GQE-003: component_docs returns one row per component, with
frontmatter fields joined to the component.md full raw text.

Uses the fixture corpus from specs/architecture/graph-query-engine-fixture.md,
written under a temporary repo_root.
"""

import json
from pathlib import Path

import duckdb
import pytest

import graph_query_engine


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _build_fixture(repo_root):
    _write(
        repo_root,
        "specs/components/foo/component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: [comp-bar]\n"
        "realizes: [P-X]\n"
        "uses_var: [VAR-X]\n"
        "depends_on_guarantees: [G-BAR-001]\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "one two three\n",
    )
    _write(
        repo_root,
        "specs/components/bar/component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-X]\n"
        "---\n"
        "\n"
        "# Bar\n",
    )
    _write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    _write(
        repo_root,
        "specs/components/foo/requirements/R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    _write(
        repo_root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        repo_root,
        "specs/components/foo/interface/guarantees/G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        repo_root,
        "specs/product/x.md",
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "### CS-X-001\n"
        "Covers: P-X\n"
        "\n"
        "### CS-X-002\n"
        "Covers: P-X\n",
    )
    _write(
        repo_root,
        "specs/vars/x.md",
        "---\n"
        "id: VAR-X\n"
        "title: V\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# V\n",
    )
    _write(
        repo_root,
        "specs/decisions/D1.md",
        "---\n"
        "id: D1\n"
        "title: One\n"
        "status: ratified\n"
        "owners: [team]\n"
        "last_ratified_commit: 0000000\n"
        "---\n"
        "\n"
        "# D1\n",
    )
    _write(
        repo_root,
        "specs/decisions/D2.md",
        "---\n"
        "id: D2\n"
        "title: Two\n"
        "status: draft\n"
        "owners: [team]\n"
        "supersedes: D1\n"
        "builds_on: [D1]\n"
        "---\n"
        "\n"
        "# D2\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")


def _as_list(value):
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except ValueError:
            return [value]
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
        return [str(parsed)]
    return value


@pytest.fixture
def con(tmp_path):
    _build_fixture(tmp_path)
    connection = duckdb.connect()
    connection.execute("INSTALL yaml FROM community")
    connection.execute("LOAD yaml")
    graph_query_engine.load_views(connection, tmp_path)
    yield connection
    connection.close()


def test_ac_gqe_003_component_docs(con):
    cur = con.execute("SELECT * FROM component_docs")
    rows = cur.fetchall()
    columns = [d[0] for d in cur.description]
    records = [dict(zip(columns, row)) for row in rows]

    assert len(records) == 2

    foo_rows = [r for r in records if r.get("id") == "comp-foo"]
    assert len(foo_rows) == 1
    foo = foo_rows[0]

    assert foo["title"] == "Foo"
    assert _as_list(foo["depends_on"]) == ["comp-bar"]
    assert isinstance(foo["body"], str)
    assert "one two three" in foo["body"]
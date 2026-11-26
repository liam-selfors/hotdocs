# hotdocs-criterion: sha256:4435af359d1c30ea1a6e96ef28183e042fdd04fcf9e3a247672c62e9cdc87d30
import json
from pathlib import Path

import pytest

import graph_query_engine

duckdb = pytest.importorskip("duckdb")


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _build_fixture(root):
    _write(
        root,
        "specs/components/foo/component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "depends_on: [comp-bar]\n"
        + "realizes: [P-X]\n"
        + "uses_var: [VAR-X]\n"
        + "depends_on_guarantees: [G-BAR-001]\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "one two three\n",
    )
    _write(
        root,
        "specs/components/bar/component.md",
        "---\n"
        + "id: comp-bar\n"
        + "title: Bar\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "realizes: [P-X]\n"
        + "---\n"
        + "\n"
        + "# Bar\n",
    )
    _write(
        root,
        "specs/components/foo/requirements/R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    _write(
        root,
        "specs/components/foo/requirements/R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    _write(
        root,
        "specs/components/foo/acceptance/AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        root,
        "specs/components/foo/interface/guarantees/G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        root,
        "specs/product/x.md",
        "---\n"
        + "id: P-X\n"
        + "title: X\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# X\n"
        + "\n"
        + "### CS-X-001\n"
        + "Covers: P-X\n"
        + "\n"
        + "### CS-X-002\n"
        + "Covers: P-X\n",
    )
    _write(
        root,
        "specs/vars/x.md",
        "---\n"
        + "id: VAR-X\n"
        + "title: V\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "\n"
        + "# V\n",
    )
    _write(
        root,
        "specs/decisions/D1.md",
        "---\n"
        + "id: D1\n"
        + "title: One\n"
        + "status: ratified\n"
        + "owners: [team]\n"
        + "last_ratified_commit: 0000000\n"
        + "---\n"
        + "\n"
        + "# D1\n",
    )
    _write(
        root,
        "specs/decisions/D2.md",
        "---\n"
        + "id: D2\n"
        + "title: Two\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "supersedes: D1\n"
        + "builds_on: [D1]\n"
        + "---\n"
        + "\n"
        + "# D2\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(root, d + "/README.md", "# Readme\n\nNotes.\n")


def _connect():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip("yaml community extension unavailable: " + repr(exc))
    return con


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
    return list(value)


def test_ac_gqe_003_component_docs(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)

        cur = con.execute("SELECT * FROM component_docs")
        columns = [d[0] for d in cur.description]
        rows = [dict(zip(columns, r)) for r in cur.fetchall()]
    finally:
        con.close()

    assert len(rows) == 2

    foo_rows = [r for r in rows if r.get("id") == "comp-foo"]
    assert len(foo_rows) == 1
    foo = foo_rows[0]

    assert foo["title"] == "Foo"
    assert _as_list(foo["depends_on"]) == ["comp-bar"]
    assert foo["body"] is not None
    assert "one two three" in foo["body"]
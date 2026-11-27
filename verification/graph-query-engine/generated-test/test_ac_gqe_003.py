# hotdocs-criterion: sha256:2342aa536eaeae5a53216f168191a6519d02a9fc51f44e439ebc3740be630b82
import json
from pathlib import Path

import duckdb

import graph_query_engine


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _build_fixture(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "components" / "foo" / "component.md",
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
        specs / "components" / "bar" / "component.md",
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
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n" + "\n" + "foo MUST work.\n",
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n" + "\n" + "foo MUST stop.\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n" + "\n" + "Covers: R-FOO-001\n" + "Kind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n" + "\n" + "foo never fails.\n",
    )
    _write(
        specs / "product" / "x.md",
        "---\n"
        + "id: P-X\n"
        + "title: X\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "# X\n"
        + "\n"
        + "### CS-X-001\n"
        + "Covers: P-X\n"
        + "\n"
        + "### CS-X-002\n"
        + "Covers: P-X\n",
    )
    _write(
        specs / "vars" / "x.md",
        "---\n"
        + "id: VAR-X\n"
        + "title: V\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "---\n"
        + "# V\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        + "id: D1\n"
        + "title: One\n"
        + "status: ratified\n"
        + "owners: [team]\n"
        + "---\n"
        + "# D1\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        "---\n"
        + "id: D2\n"
        + "title: Two\n"
        + "status: draft\n"
        + "owners: [team]\n"
        + "supersedes: D1\n"
        + "builds_on: [D1]\n"
        + "---\n"
        + "# D2\n",
    )
    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n" + "\n" + "Notes.\n")


def _normalize_list(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value]
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except ValueError:
            pass
        if text.startswith("[") and text.endswith("]"):
            inner = text[1:-1]
            return [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
        return [text]
    return list(value)


def test_ac_gqe_003_component_docs(tmp_path):
    repo_root = Path(tmp_path)
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        cur = con.execute("SELECT * FROM component_docs")
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    finally:
        pass

    try:
        assert len(rows) == 2, "expected 2 component_docs rows, got " + repr(rows)

        records = [dict(zip(columns, row)) for row in rows]
        for needed in ("id", "title", "depends_on", "body"):
            assert needed in columns, "missing column " + repr(needed) + " in " + repr(columns)

        foo_rows = [r for r in records if r["id"] == "comp-foo"]
        assert len(foo_rows) == 1, "expected one comp-foo row, got " + repr(records)
        foo = foo_rows[0]

        assert foo["title"] == "Foo"
        assert _normalize_list(foo["depends_on"]) == ["comp-bar"]
        assert isinstance(foo["body"], str)
        assert "one two three" in foo["body"]
    finally:
        con.close()
# hotdocs-criterion: sha256:fbf24ec1b9ae463d6a864c00c47991b26aab5274a44d225639f74aa0337db20a
import graph_query_engine

from pathlib import Path

import duckdb


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _frontmatter(lines):
    return "---\n" + "\n".join(lines) + "\n---\n"


def _build_corpus(repo_root):
    specs = repo_root / "specs"

    _write(
        specs / "components" / "foo" / "component.md",
        _frontmatter([
            "id: comp-foo",
            "title: Foo",
            "status: draft",
            "owners: [team]",
            "sealed: true",
            "source_path: legacy/foo/",
            "depends_on: [comp-bar]",
            "realizes: [P-X]",
            "uses_var: [VAR-X]",
            "depends_on_guarantees: [G-BAR-001]",
        ])
        + "\n# Foo\n\none two three\n",
    )
    _write(
        specs / "components" / "bar" / "component.md",
        _frontmatter([
            "id: comp-bar",
            "title: Bar",
            "status: draft",
            "owners: [team]",
            "sealed: true",
            "source_path: legacy/bar/",
            "realizes: [P-X]",
        ])
        + "\n# Bar\n",
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\nfoo MUST work.\n",
    )
    _write(
        specs / "components" / "foo" / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\nfoo MUST stop.\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: generated-test\n",
    )
    _write(
        specs / "components" / "foo" / "interface" / "guarantees" / "G-FOO-001.md",
        "# G-FOO-001\n\nfoo never fails.\n",
    )
    _write(
        specs / "product" / "x.md",
        _frontmatter([
            "id: P-X",
            "title: X",
            "status: draft",
            "owners: [team]",
        ])
        + "\n# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        specs / "vars" / "x.md",
        _frontmatter([
            "id: VAR-X",
            "title: V",
            "status: draft",
            "owners: [team]",
        ])
        + "\n# V\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        _frontmatter([
            "id: D1",
            "title: One",
            "status: ratified",
            "owners: [team]",
            "last_ratified_commit: 0000000",
        ])
        + "\n# D1\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        _frontmatter([
            "id: D2",
            "title: Two",
            "status: draft",
            "owners: [team]",
        ])
        + "\n# D2\n",
    )
    # D3: prose quotes both fields (inline and at a line start), but the
    # frontmatter declares neither.
    _write(
        specs / "decisions" / "D3.md",
        _frontmatter([
            "id: D3",
            "title: Three",
            "status: draft",
            "owners: [team]",
        ])
        + "\n# D3\n\n"
        + "An earlier draft of this record proposed `supersedes: D1` and "
        + "`builds_on: [D2]`, but neither was adopted.\n\n"
        + "The rejected frontmatter read:\n\n"
        + "supersedes: D1\n"
        + "builds_on: [D2]\n",
    )
    # D4: frontmatter declares builds_on: [D1, D2].
    _write(
        specs / "decisions" / "D4.md",
        _frontmatter([
            "id: D4",
            "title: Four",
            "status: draft",
            "owners: [team]",
            "builds_on: [D1, D2]",
        ])
        + "\n# D4\n",
    )

    for sub in ("product", "vars", "decisions"):
        _write(specs / sub / "README.md", "# Readme\n\nNotes.\n")


def _edge_rows(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)
        rows = con.execute(
            "SELECT source_id, target_id, edge_type FROM edges"
        ).fetchall()
    finally:
        con.close()
    return [tuple(r) for r in rows]


def test_prose_quoted_fields_produce_no_decision_edges(tmp_path):
    edge_rows = _edge_rows(tmp_path)
    offending = [
        r
        for r in edge_rows
        if r[0] == "D3" and r[2] in ("supersedes", "builds_on")
    ]
    assert offending == []


def test_declared_builds_on_list_yields_exactly_one_row_per_entry(tmp_path):
    edge_rows = _edge_rows(tmp_path)
    builds_on_rows = sorted(
        r for r in edge_rows if r[0] == "D4" and r[2] == "builds_on"
    )
    assert builds_on_rows == [
        ("D4", "D1", "builds_on"),
        ("D4", "D2", "builds_on"),
    ]
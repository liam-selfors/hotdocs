# hotdocs-criterion: sha256:a77a7de37e7f35b16b360ebaa421a99d8c4751a28999068527c4540ea9a9202c
from pathlib import Path

import duckdb

import graph_query_engine


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _fm(lines):
    return "---\n" + "".join(line + "\n" for line in lines) + "---\n"


def _build_fixture(repo_root):
    _write(
        repo_root,
        "specs/components/foo/component.md",
        _fm([
            "id: comp-foo",
            "title: Foo",
            "status: draft",
            "owners: [team]",
            "depends_on: [comp-bar]",
            "realizes: [P-X]",
            "uses_var: [VAR-X]",
            "depends_on_guarantees: [G-BAR-001]",
        ])
        + "\n# Foo\n\none two three\n",
    )
    _write(
        repo_root,
        "specs/components/bar/component.md",
        _fm([
            "id: comp-bar",
            "title: Bar",
            "status: draft",
            "owners: [team]",
            "realizes: [P-X]",
        ])
        + "\n# Bar\n",
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
        _fm(["id: P-X", "title: X", "status: draft", "owners: [team]"])
        + "# X\n\n### CS-X-001\nCovers: P-X\n\n### CS-X-002\nCovers: P-X\n",
    )
    _write(
        repo_root,
        "specs/vars/x.md",
        _fm(["id: VAR-X", "title: V", "status: draft", "owners: [team]"])
        + "# V\n",
    )
    _write(
        repo_root,
        "specs/decisions/D1.md",
        _fm([
            "id: D1",
            "title: One",
            "status: ratified",
            "owners: [team]",
            "last_ratified_commit: 0000000",
        ])
        + "# D1\n",
    )
    _write(
        repo_root,
        "specs/decisions/D2.md",
        _fm([
            "id: D2",
            "title: Two",
            "status: draft",
            "owners: [team]",
            "supersedes: D1",
            "builds_on: [D1]",
        ])
        + "# D2\n",
    )
    for d in ("specs/product", "specs/vars", "specs/decisions"):
        _write(repo_root, d + "/README.md", "# Readme\n\nNotes.\n")


def test_ac_gqe_006_component_size_word_counts(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
        graph_query_engine.load_views(con, repo_root)

        rows = con.execute(
            "SELECT component_id, word_count FROM component_size"
        ).fetchall()
    finally:
        con.close()

    ids = [r[0] for r in rows]
    assert len(ids) == len(set(ids)), rows
    sizes = {r[0]: r[1] for r in rows}
    assert set(sizes) == {"foo", "bar"}, rows
    assert sizes["foo"] == 26
    assert sizes["bar"] == 2
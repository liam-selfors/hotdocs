"""AC-GQE-007: load_views is idempotent on the same DuckDB connection.

Given a DuckDB connection with load_views already called once,
When load_views is called again on the same connection,
Then it succeeds without error and every view still returns the same
results as the first call.
"""

import graph_query_engine

from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")


VIEWS = [
    "nodes",
    "edges",
    "component_docs",
    "component_context",
    "component_provenance",
    "component_size",
    "decision_lineage",
]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    # One sealed component with a requirement, its acceptance criterion,
    # an interface section and constraints.
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo Component\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "uses_var: [VAR-FOO-PATH]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo Component\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does one small thing for testing purposes.\n"
        "It spans two lines of purpose text.\n"
        "\n"
        "## Notes\n"
        "\n"
        "Some additional prose that is not part of the purpose.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — MUST return a greeting when called.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a caller\n"
        "When foo is called\n"
        "Then it returns a greeting\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo() -> str\n"
        "```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # One var declaration.
    _write(
        specs / "vars" / "VAR-FOO-PATH.md",
        "---\n"
        "id: VAR-FOO-PATH\n"
        "title: Foo path\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# VAR-FOO-PATH\n"
        "\n"
        "A path used by foo.\n",
    )

    # Two decisions, one ratified (with last_ratified_commit), one draft.
    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: ratified\n"
        "owners: [team-a]\n"
        "last_ratified_commit: abc1234\n"
        "---\n"
        "\n"
        "# D1\n"
        "\n"
        "The first decision.\n",
    )
    _write(
        specs / "decisions" / "D2.md",
        "---\n"
        "id: D2\n"
        "title: Second decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "supersedes: [D1]\n"
        "---\n"
        "\n"
        "# D2\n"
        "\n"
        "The second decision.\n",
    )

    # Product dir present but empty is a legitimate state; create it anyway.
    (specs / "product").mkdir(parents=True, exist_ok=True)


def _connect():
    con = duckdb.connect()
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # pragma: no cover - environment dependent
        con.close()
        pytest.skip(f"DuckDB community 'yaml' extension unavailable: {exc}")
    return con


def _snapshot(con):
    snap = {}
    for view in VIEWS:
        cur = con.execute(f"SELECT * FROM {view}")
        columns = [d[0] for d in cur.description]
        rows = [tuple(r) for r in cur.fetchall()]
        rows_sorted = sorted(rows, key=repr)
        snap[view] = (columns, rows_sorted)
    return snap


def test_load_views_twice_on_same_connection_is_idempotent(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    _build_corpus(repo_root)

    con = _connect()
    try:
        # Given: load_views already called once.
        graph_query_engine.load_views(con, repo_root)
        first = _snapshot(con)

        # Sanity: the fixture actually produced data somewhere, so the
        # comparison below is not vacuously over empty results.
        assert any(rows for _, rows in first.values()), (
            "expected at least one view to return rows for a non-empty corpus"
        )

        # When: load_views is called again on the same connection.
        # Then: it succeeds without error ...
        graph_query_engine.load_views(con, repo_root)

        # ... and every view still returns the same results.
        second = _snapshot(con)
        for view in VIEWS:
            first_cols, first_rows = first[view]
            second_cols, second_rows = second[view]
            assert second_cols == first_cols, (
                f"view {view!r} columns changed after second load_views: "
                f"{first_cols!r} -> {second_cols!r}"
            )
            assert second_rows == first_rows, (
                f"view {view!r} results changed after second load_views:\n"
                f"first={first_rows!r}\nsecond={second_rows!r}"
            )
    finally:
        con.close()


def test_load_views_twice_on_sparse_corpus_is_idempotent(tmp_path):
    # A corpus with no component, var, product or decision files at all
    # is a legitimate state; calling load_views twice must still succeed
    # and every view must return the same (empty) results both times.
    repo_root = (tmp_path / "sparse").resolve()
    (repo_root / "specs" / "components").mkdir(parents=True)

    con = _connect()
    try:
        graph_query_engine.load_views(con, repo_root)
        first = _snapshot(con)

        graph_query_engine.load_views(con, repo_root)
        second = _snapshot(con)

        for view in VIEWS:
            assert second[view] == first[view], (
                f"view {view!r} results changed after second load_views: "
                f"{first[view]!r} -> {second[view]!r}"
            )
    finally:
        con.close()
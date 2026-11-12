import textwrap
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

import graph_query_engine


VIEW_NAMES = [
    "nodes",
    "edges",
    "component_docs",
    "component_context",
    "component_provenance",
    "component_size",
    "decision_lineage",
]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    _write(
        comp_dir / "component.md",
        """
        ---
        id: comp-widget-maker
        title: Widget Maker
        status: draft
        owners: [alice]
        depends_on: []
        sealed: true
        source_path: legacy/widget_maker.py
        ---

        # Widget Maker

        ## Purpose

        Makes widgets out of spare parts,
        one widget at a time.

        ## Notes

        Nothing else to say here.
        """,
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        """
        # R-WIDGET-001

        **R-WIDGET-001** — MUST make a widget.
        """,
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        """
        # AC-WIDGET-001

        Covers: R-WIDGET-001
        Kind: generated-test

        ```gherkin
        Given spare parts
        When make is called
        Then a widget is returned
        ```
        """,
    )
    _write(
        comp_dir / "interface" / "library.md",
        """
        # Library

        ```
        make() -> Widget
        ```
        """,
    )
    _write(
        comp_dir / "constraints.md",
        """
        # Constraints

        None.
        """,
    )
    _write(
        repo_root / "specs" / "vars" / "VAR-WIDGET-SIZE.md",
        """
        ---
        id: VAR-WIDGET-SIZE
        title: Widget size
        status: draft
        owners: [alice]
        ---

        # VAR-WIDGET-SIZE

        The size of a widget.
        """,
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        """
        ---
        id: D1
        title: Make widgets
        status: draft
        owners: [alice]
        ---

        # D1

        We decided to make widgets.
        """,
    )
    _write(
        repo_root / "specs" / "product" / "P-WIDGETS.md",
        """
        ---
        id: P-WIDGETS
        title: Widgets
        status: draft
        owners: [alice]
        ---

        # P-WIDGETS

        Users get widgets.
        """,
    )


def _connect():
    con = duckdb.connect(":memory:")
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # environment cannot provide the extension
        con.close()
        pytest.skip(f"yaml community extension unavailable: {exc!r}")
    return con


def _snapshot(con):
    snap = {}
    for view in VIEW_NAMES:
        cur = con.execute(f"SELECT * FROM {view}")
        columns = [d[0] for d in (cur.description or [])]
        rows = cur.fetchall()
        snap[view] = (columns, sorted(repr(r) for r in rows))
    return snap


def test_ac_gqe_007_load_views_is_idempotent(tmp_path):
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir(parents=True)
    _build_corpus(repo_root)

    con = _connect()
    try:
        first_result = graph_query_engine.load_views(con, repo_root)
        assert first_result is None
        first = _snapshot(con)

        # Sanity: the fixture is non-trivial, so equality below is meaningful.
        assert len(first["nodes"][1]) > 0, "nodes view unexpectedly empty"

        # Second call on the same connection must not raise.
        second_result = graph_query_engine.load_views(con, repo_root)
        assert second_result is None
        second = _snapshot(con)

        for view in VIEW_NAMES:
            first_cols, first_rows = first[view]
            second_cols, second_rows = second[view]
            assert second_cols == first_cols, (
                f"view {view!r} columns changed after second load_views call: "
                f"{first_cols!r} -> {second_cols!r}"
            )
            assert second_rows == first_rows, (
                f"view {view!r} results changed after second load_views call"
            )
    finally:
        con.close()
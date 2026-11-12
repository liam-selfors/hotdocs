import textwrap
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")

import graph_query_engine


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    # One component, sealed, with every list-valued edge field present but empty
    # (flow style), so no component-sourced edges exist.
    _write(
        repo_root / "specs" / "components" / "widget" / "component.md",
        """
        ---
        id: comp-widget
        title: Widget
        status: draft
        owners: [alice]
        depends_on: []
        realizes: []
        uses_var: []
        depends_on_guarantees: []
        sealed: true
        source_path: legacy/widget
        ---

        # Widget

        ## Purpose

        A synthetic component used only as a test fixture.
        """,
    )

    # D1 supersedes D2 via a scalar (never a list) frontmatter line.
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        """
        ---
        id: D1
        title: Decision One
        status: draft
        owners: [alice]
        supersedes: D2
        ---

        # D1

        Supersedes D2.
        """,
    )

    # D2 is deprecated.
    _write(
        repo_root / "specs" / "decisions" / "D2.md",
        """
        ---
        id: D2
        title: Decision Two
        status: deprecated
        owners: [alice]
        ---

        # D2

        Deprecated in favor of D1.
        """,
    )


def _connect_with_yaml():
    con = duckdb.connect(":memory:")
    try:
        con.execute("INSTALL yaml FROM community")
        con.execute("LOAD yaml")
    except Exception as exc:  # environment lacks the community extension
        con.close()
        pytest.skip(f"DuckDB community 'yaml' extension unavailable: {exc}")
    return con


def test_ac_gqe_009_decision_nodes_and_scalar_supersedes_edge(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir(parents=True)
    _build_fixture(repo_root)

    con = _connect_with_yaml()
    try:
        result = graph_query_engine.load_views(con, repo_root)
        assert result is None

        node_rows = con.execute(
            "SELECT id, title, status, kind, owner_component_id FROM nodes"
        ).fetchall()

        decision_rows = {}
        for row in node_rows:
            node_id = None if row[0] is None else str(row[0])
            if node_id in ("D1", "D2"):
                assert node_id not in decision_rows, (
                    f"duplicate nodes row for {node_id}: {node_rows!r}"
                )
                decision_rows[node_id] = row

        assert set(decision_rows) == {"D1", "D2"}, (
            f"expected a nodes row for each of D1 and D2, got {node_rows!r}"
        )

        for node_id, row in decision_rows.items():
            _, title, status, kind, owner = row
            assert kind == "decision", f"{node_id} kind was {kind!r}"
            assert owner is None, f"{node_id} owner_component_id was {owner!r}"

        assert decision_rows["D1"][1] == "Decision One"
        assert decision_rows["D2"][1] == "Decision Two"
        assert decision_rows["D2"][2] == "deprecated"

        # The component itself is also present as a node.
        component_kinds = [
            row[3] for row in node_rows if row[0] is not None and str(row[0]) == "comp-widget"
        ]
        assert component_kinds == ["component"], (
            f"expected exactly one component node for comp-widget, got {node_rows!r}"
        )

        edge_rows = con.execute(
            "SELECT source_id, target_id, edge_type FROM edges"
        ).fetchall()
        normalized_edges = [
            tuple(None if v is None else str(v) for v in row) for row in edge_rows
        ]
        assert normalized_edges == [("D1", "D2", "supersedes")], (
            f"edges must contain exactly (D1, D2, 'supersedes'), got {normalized_edges!r}"
        )
    finally:
        con.close()
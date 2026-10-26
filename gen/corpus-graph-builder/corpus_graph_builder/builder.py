"""Core graph-assembly logic for corpus-graph-builder.

Implements:

- R-GRAPH-001/002: node/edge construction, built from the shared
  `nodes`/`edges` views `graph-query-engine` provides (R-GRAPH-009),
  not a third, independently-written construction step.
- R-GRAPH-003: per-component-node verification/provenance/size/sealed/
  pinned-override annotations, computed as joins against
  `component_provenance` and `component_size` (also shared views,
  R-GRAPH-009) plus the component's own `.overrides.json`.
- R-GRAPH-004/005: corpus-wide orphan-capability/-component/-var rate
  aggregates, computed against the same shared views.
- R-GRAPH-006: output always targets `verification/corpus-graph.json`.
- R-GRAPH-008: deterministic, byte-identical serialization for the same
  corpus/provenance/verification state.

Per `constraints.md`: pure graph assembly over already-computed data —
no network access, no model calls. This module only reads what
`graph-query-engine`'s views, `provenance-writer`'s manifests, and
`verifier-orchestrator`'s reports have already produced; it never
recomputes any of it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

# `graph-query-engine`'s own public library surface
# (`load_views(con, repo_root) -> None`), named in `specs/architecture/
# graph-query-engine.md`'s "Query surface" section. R-GRAPH-009 requires
# this component build its graph from those shared views rather than
# writing its own frontmatter parsing / globbing.
from graph_query_engine import load_views

# The component-level word-count cap `component_size.word_count` (shared
# with `spec-linter`'s `rule_size_caps`, R-LINT-012, D42) is checked
# against (D2). Not redefined/recomputed from scratch here — this value
# is only ever compared against, never used to re-derive the count
# itself.
COMPONENT_SIZE_CAP_WORDS = 4000

OUTPUT_RELATIVE_PATH = "verification/corpus-graph.json"

_NODE_KINDS = ("component", "capability", "var")
_EDGE_KINDS = ("depends_on", "realizes", "uses_var")


@dataclass
class CorpusGraph:
    """Matches `interface/data/CorpusGraph.md`'s JSON shape exactly."""

    nodes: dict[str, dict[str, Any]]
    edges: list[dict[str, str]]
    aggregates: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self) -> bytes:
        """Byte-identical serialization for the same logical content.

        R-GRAPH-008 / constraints.md require the same corpus +
        provenance + verification state to always produce the same
        file, byte for byte. Sorted keys, a fixed separator style, and
        a single trailing newline make the serialization itself
        deterministic given deterministic input data (which the
        ordered SQL below also guarantees).
        """

        text = json.dumps(
            self.to_dict(),
            sort_keys=True,
            indent=2,
            ensure_ascii=True,
            default=_json_default,
        )
        return (text + "\n").encode("utf-8")


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    con = _connect(repo_root)
    try:
        base_nodes = _fetch_base_nodes(con)
        base_edges = _fetch_base_edges(con)
        provenance_by_component = _fetch_rows_keyed(con, "component_provenance", "component_id")
        size_by_component = _fetch_rows_keyed(con, "component_size", "component_id")
        docs_by_component = _fetch_rows_keyed(con, "component_docs", "id")

        nodes: dict[str, dict[str, Any]] = {}
        for node_id, kind in base_nodes:
            if kind == "component":
                bare_id = node_id[len("comp-"):] if node_id.startswith("comp-") else node_id
                nodes[node_id] = _annotate_component(
                    component_id=node_id,
                    provenance_row=provenance_by_component.get(node_id),
                    size_row=size_by_component.get(bare_id),
                    docs_row=docs_by_component.get(node_id),
                    repo_root=repo_root,
                )
            else:
                nodes[node_id] = {"type": kind}

        edges = [
            {"from": source_id, "to": target_id, "kind": edge_type}
            for source_id, target_id, edge_type in base_edges
        ]

        aggregates = {
            "orphan_capability_rate": _orphan_rate(con, kind="capability", incoming_edge_type="realizes"),
            "orphan_component_rate": _orphan_component_rate(con),
            "orphan_var_rate": _orphan_rate(con, kind="var", incoming_edge_type="uses_var"),
        }

        return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)
    finally:
        con.close()


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    """Writes to exactly `verification/corpus-graph.json` (R-GRAPH-006)."""

    output_path = Path(repo_root) / OUTPUT_RELATIVE_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(graph.to_json_bytes())
    return output_path


# --- connection / views -----------------------------------------------------


def _connect(repo_root: Path) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(database=":memory:")
    _ensure_yaml_extension(con)
    # Creates (or replaces) nodes/edges/component_docs/component_context/
    # component_provenance/component_size on `con`, scoped to this repo's
    # spec corpus — this component does not parse frontmatter or glob
    # spec files itself (R-GRAPH-009).
    load_views(con, repo_root)
    return con


def _ensure_yaml_extension(con: duckdb.DuckDBPyConnection) -> None:
    # `graph-query-engine.load_views` requires the `yaml` community
    # extension be installed and loaded before it is called; it does not
    # install it itself. If it is already installed/cached locally, the
    # INSTALL is a harmless no-op even with no network reachable.
    try:
        con.execute("INSTALL yaml FROM community")
    except duckdb.Error:
        pass
    con.execute("LOAD yaml")


# --- fetch helpers -----------------------------------------------------------


def _fetch_base_nodes(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str]]:
    placeholders = ", ".join("?" for _ in _NODE_KINDS)
    rows = con.execute(
        f"""
        SELECT id, kind
        FROM nodes
        WHERE kind IN ({placeholders})
        ORDER BY id
        """,
        list(_NODE_KINDS),
    ).fetchall()
    return [(row[0], row[1]) for row in rows]


def _fetch_base_edges(con: duckdb.DuckDBPyConnection) -> list[tuple[str, str, str]]:
    placeholders = ", ".join("?" for _ in _EDGE_KINDS)
    rows = con.execute(
        f"""
        SELECT source_id, target_id, edge_type
        FROM edges
        WHERE edge_type IN ({placeholders})
        ORDER BY source_id, target_id, edge_type
        """,
        list(_EDGE_KINDS),
    ).fetchall()
    return [(row[0], row[1], row[2]) for row in rows]


def _fetch_rows_keyed(
    con: duckdb.DuckDBPyConnection, view_name: str, key_column: str
) -> dict[str, dict[str, Any]]:
    cursor = con.execute(f"SELECT * FROM {view_name} ORDER BY {key_column}")
    columns = [d[0] for d in cursor.description]
    result: dict[str, dict[str, Any]] = {}
    for row in cursor.fetchall():
        record = dict(zip(columns, row))
        key = record.pop(key_column)
        result[key] = record
    return result


# --- per-component annotation (R-GRAPH-003) ----------------------------------


def _annotate_component(
    component_id: str,
    provenance_row: dict[str, Any] | None,
    size_row: dict[str, Any] | None,
    docs_row: dict[str, Any] | None,
    repo_root: Path,
) -> dict[str, Any]:
    provenance_fields = dict(provenance_row) if provenance_row else {}
    verification_report = provenance_fields.pop("verification_report", None)

    word_count = size_row.get("word_count") if size_row else None
    if word_count is None:
        size_status = "unknown"
    elif word_count <= COMPONENT_SIZE_CAP_WORDS:
        size_status = "ok"
    else:
        size_status = "over"

    sealed = bool(docs_row.get("sealed")) if docs_row and docs_row.get("sealed") else False

    return {
        "type": "component",
        "verification": verification_report,
        "provenance": provenance_fields,
        "size_status": size_status,
        "sealed": sealed,
        "pinned_overrides": _read_pinned_overrides(component_id, repo_root),
    }


def _read_pinned_overrides(component_id: str, repo_root: Path) -> list[Any]:
    overrides_path = Path(repo_root) / "gen" / component_id / ".overrides.json"
    if not overrides_path.exists():
        return []
    try:
        data = json.loads(overrides_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        files = data.get("files")
        if isinstance(files, list):
            return files
        return [data]
    return []


# --- orphan aggregates (R-GRAPH-004/005) -------------------------------------


def _orphan_rate(con: duckdb.DuckDBPyConnection, kind: str, incoming_edge_type: str) -> float:
    """Orphan rate for a node kind never targeted by `incoming_edge_type`.

    A capability (`P-id`) with no incoming `realizes` edge is never
    realized by any component — orphaned (D8). A var with no incoming
    `uses_var` edge is never consumed by any component — orphaned (D12).
    """

    row = con.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE NOT EXISTS (
                    SELECT 1 FROM edges e
                    WHERE e.target_id = n.id AND e.edge_type = ?
                )
            ) AS orphan_count,
            COUNT(*) AS total_count
        FROM nodes n
        WHERE n.kind = ?
        """,
        [incoming_edge_type, kind],
    ).fetchone()
    orphan_count, total_count = row
    if not total_count:
        return 0.0
    return orphan_count / total_count


def _orphan_component_rate(con: duckdb.DuckDBPyConnection) -> float:
    """Orphan rate for components reachable from nothing in the graph.

    A component is orphaned (D8) if nothing depends on it AND it does
    not itself realize any capability — i.e. it is disconnected from
    both the dependency graph and the capability graph.
    """

    row = con.execute(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE NOT EXISTS (
                    SELECT 1 FROM edges e
                    WHERE e.target_id = n.id AND e.edge_type = 'depends_on'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM edges e
                    WHERE e.source_id = n.id AND e.edge_type = 'realizes'
                )
            ) AS orphan_count,
            COUNT(*) AS total_count
        FROM nodes n
        WHERE n.kind = 'component'
        """
    ).fetchone()
    orphan_count, total_count = row
    if not total_count:
        return 0.0
    return orphan_count / total_count

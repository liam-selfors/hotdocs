"""Corpus Graph Builder: builds verification/corpus-graph.json."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph", "main"]

SIZE_CAP = 4000
EDGE_KINDS = ("depends_on", "realizes", "uses_var")
NODE_KINDS = ("component", "capability", "var")


@dataclass
class CorpusGraph:
    nodes: dict = field(default_factory=dict)
    edges: list = field(default_factory=list)
    aggregates: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self) -> bytes:
        text = json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
        return (text + "\n").encode("utf-8")


def _tool_root(repo_root: Path) -> Path:
    here = Path(__file__).resolve()
    return next((p.parent for p in here.parents if p.name == "gen"), repo_root)


def _load_graph_query_engine(repo_root: Path):
    module_dir = repo_root / "gen" / "graph-query-engine"
    if not module_dir.is_dir():
        module_dir = _tool_root(repo_root) / "gen" / "graph-query-engine"
    path = module_dir / "graph_query_engine.py"
    spec = importlib.util.spec_from_file_location("graph_query_engine", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["graph_query_engine"] = module
    spec.loader.exec_module(module)
    return module


def _rows_as_dicts(con, sql: str) -> list:
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _component_node(repo_root: Path, slug: str, sizes: dict, doc: dict) -> dict:
    verification = None
    provenance = None
    manifest = repo_root / "verification" / slug / ".provenance.json"
    if manifest.is_file():
        with manifest.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        verification = data.get("verification_report")
        provenance = {k: v for k, v in data.items() if k != "verification_report"}

    if slug in sizes:
        size_status = "ok" if sizes[slug] <= SIZE_CAP else "over"
    else:
        size_status = "unknown"

    pinned_overrides = []
    overrides_path = repo_root / "gen" / slug / ".overrides.json"
    if overrides_path.is_file():
        with overrides_path.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, list):
            pinned_overrides = loaded

    sealed = doc.get("sealed") in (True, "true")
    owners = list(doc.get("owners") or [])

    comp_dir = repo_root / "specs" / "components" / slug
    documents = {
        p.relative_to(comp_dir).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(comp_dir.rglob("*.md"))
    }
    documents = dict(sorted(documents.items()))

    return {
        "type": "component",
        "verification": verification,
        "provenance": provenance,
        "size_status": size_status,
        "sealed": sealed,
        "pinned_overrides": pinned_overrides,
        "owners": owners,
        "documents": documents,
    }


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    gqe = _load_graph_query_engine(repo_root)
    con = duckdb.connect(":memory:")
    try:
        try:
            con.execute("INSTALL yaml FROM community")
        except Exception:
            pass
        con.execute("LOAD yaml")
        gqe.load_views(con, repo_root)

        node_rows = con.execute(
            "SELECT id, kind FROM nodes WHERE kind IN ('component', 'capability', 'var')"
        ).fetchall()
        edge_rows = con.execute(
            "SELECT source_id, target_id, edge_type FROM edges "
            "WHERE edge_type IN ('depends_on', 'realizes', 'uses_var')"
        ).fetchall()
        sizes = {
            row[0]: row[1]
            for row in con.execute(
                "SELECT component_id, word_count FROM component_size"
            ).fetchall()
        }
        docs = {row["id"]: row for row in _rows_as_dicts(con, "SELECT * FROM component_docs")}
    finally:
        con.close()

    edges = sorted(
        {"from": str(s), "to": str(t), "kind": str(k)} for s, t, k in edge_rows
    ) if False else sorted(
        ({"from": str(s), "to": str(t), "kind": str(k)} for s, t, k in edge_rows),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    capabilities = sorted(str(i) for i, k in node_rows if k == "capability")
    variables = sorted(str(i) for i, k in node_rows if k == "var")
    components = sorted(str(i) for i, k in node_rows if k == "component")

    nodes = {}
    for cap in capabilities:
        nodes[cap] = {"type": "capability"}
    for var in variables:
        nodes[var] = {"type": "var"}
    for comp in components:
        slug = comp[len("comp-"):] if comp.startswith("comp-") else comp
        nodes[comp] = _component_node(repo_root, slug, sizes, docs.get(comp, {}))

    realized = {e["to"] for e in edges if e["kind"] == "realizes"}
    used_vars = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depended_on = {e["to"] for e in edges if e["kind"] == "depends_on"}
    realizers = {e["from"] for e in edges if e["kind"] == "realizes"}

    orphan_caps = sum(1 for c in capabilities if c not in realized)
    orphan_vars = sum(1 for v in variables if v not in used_vars)
    orphan_comps = sum(
        1 for c in components if c not in depended_on and c not in realizers
    )

    aggregates = {
        "orphan_capability_rate": _rate(orphan_caps, len(capabilities)),
        "orphan_component_rate": _rate(orphan_comps, len(components)),
        "orphan_var_rate": _rate(orphan_vars, len(variables)),
    }

    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    out_dir = Path(repo_root) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "corpus-graph.json"
    path.write_bytes(graph.to_json_bytes())
    return path


from .cli import main  # noqa: E402

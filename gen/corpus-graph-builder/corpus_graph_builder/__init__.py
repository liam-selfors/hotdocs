"""Corpus Graph Builder: builds verification/corpus-graph.json."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

SIZE_CAP = 4000
EDGE_KINDS = ("depends_on", "realizes", "uses_var")
NODE_KINDS = ("component", "capability", "var")

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph", "main"]


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


def _tool_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return here.parent


def _load_graph_query_engine(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / "graph-query-engine"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "graph-query-engine"
    name = "graph_query_engine"
    spec = importlib.util.spec_from_file_location(name, dep_dir / "graph_query_engine.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _connect(repo_root: Path):
    gqe = _load_graph_query_engine(repo_root)
    con = duckdb.connect(":memory:")
    try:
        con.execute("INSTALL yaml FROM community")
    except Exception:
        pass
    con.execute("LOAD yaml")
    gqe.load_views(con, Path(repo_root))
    return con


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _component_docs(con) -> dict:
    cur = con.execute("SELECT * FROM component_docs")
    columns = [d[0] for d in cur.description]
    return {row["id"]: row for row in (dict(zip(columns, r)) for r in cur.fetchall())}


def _component_node(repo_root: Path, cid: str, doc: dict, sizes: dict) -> dict:
    slug = cid.removeprefix("comp-")

    verification = None
    provenance = None
    manifest_path = repo_root / "verification" / slug / ".provenance.json"
    if manifest_path.is_file():
        with manifest_path.open("r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        verification = manifest.get("verification_report")
        provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

    if slug not in sizes:
        size_status = "unknown"
    elif sizes[slug] > SIZE_CAP:
        size_status = "over"
    else:
        size_status = "ok"

    overrides = []
    overrides_path = repo_root / "gen" / slug / ".overrides.json"
    if overrides_path.is_file():
        with overrides_path.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, list):
            overrides = loaded

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
        "sealed": str(doc.get("sealed")).lower() == "true",
        "pinned_overrides": overrides,
        "owners": [str(o) for o in (doc.get("owners") or [])],
        "documents": documents,
    }


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    con = _connect(repo_root)
    try:
        node_rows = con.execute(
            "SELECT id, kind FROM nodes WHERE kind IN ('component', 'capability', 'var')"
        ).fetchall()
        edge_rows = con.execute(
            "SELECT DISTINCT source_id, target_id, edge_type FROM edges "
            "WHERE edge_type IN ('depends_on', 'realizes', 'uses_var')"
        ).fetchall()
        sizes = {
            str(cid): int(wc)
            for cid, wc in con.execute(
                "SELECT component_id, word_count FROM component_size"
            ).fetchall()
        }
        docs = _component_docs(con)
    finally:
        con.close()

    edges = sorted(
        ({"from": str(s), "to": str(t), "kind": str(k)} for s, t, k in edge_rows),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    components = sorted(str(i) for i, k in node_rows if k == "component")
    capabilities = sorted(str(i) for i, k in node_rows if k == "capability")
    vars_ = sorted(str(i) for i, k in node_rows if k == "var")

    nodes: dict = {}
    for cap in capabilities:
        nodes[cap] = {"type": "capability"}
    for var in vars_:
        nodes[var] = {"type": "var"}
    for cid in components:
        nodes[cid] = _component_node(repo_root, cid, docs.get(cid, {}), sizes)

    realized = {e["to"] for e in edges if e["kind"] == "realizes"}
    used_vars = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depended_on = {e["to"] for e in edges if e["kind"] == "depends_on"}
    realizers = {e["from"] for e in edges if e["kind"] == "realizes"}

    orphan_caps = sum(1 for c in capabilities if c not in realized)
    orphan_vars = sum(1 for v in vars_ if v not in used_vars)
    orphan_comps = sum(
        1 for c in components if c not in depended_on and c not in realizers
    )

    aggregates = {
        "orphan_capability_rate": _rate(orphan_caps, len(capabilities)),
        "orphan_component_rate": _rate(orphan_comps, len(components)),
        "orphan_var_rate": _rate(orphan_vars, len(vars_)),
    }

    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    out_dir = Path(repo_root) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "corpus-graph.json"
    path.write_bytes(graph.to_json_bytes())
    return path


from .cli import main  # noqa: E402

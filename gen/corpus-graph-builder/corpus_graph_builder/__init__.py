"""Corpus Graph Builder: builds verification/corpus-graph.json."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph"]

_NODE_KINDS = ("component", "capability", "var")
_EDGE_KINDS = ("depends_on", "realizes", "uses_var")
_SIZE_CAP = 4000
_DEP_SLUG = "graph-query-engine"
_DEP_MODULE = "graph_query_engine"


@dataclass
class CorpusGraph:
    nodes: dict
    edges: list
    aggregates: dict

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
    return next(parent.parent for parent in here.parents if parent.name == "gen")


def _load_graph_query_engine(repo_root: Path):
    dep_dir = repo_root / "gen" / _DEP_SLUG
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / _DEP_SLUG
    path = dep_dir / f"{_DEP_MODULE}.py"
    spec = importlib.util.spec_from_file_location(_DEP_MODULE, str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[_DEP_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return count / total


def _component_node(repo_root: Path, comp_id: str, doc_row: dict, sizes: dict) -> dict:
    slug = comp_id[len("comp-"):]

    manifest_path = repo_root / "verification" / slug / ".provenance.json"
    verification = None
    provenance = None
    if manifest_path.is_file():
        with manifest_path.open("r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        verification = manifest.get("verification_report")
        provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

    word_count = sizes.get(slug)
    if word_count is None:
        size_status = "unknown"
    elif word_count <= _SIZE_CAP:
        size_status = "ok"
    else:
        size_status = "over"

    overrides_path = repo_root / "gen" / slug / ".overrides.json"
    pinned_overrides = []
    if overrides_path.is_file():
        loaded = json.loads(overrides_path.read_text(encoding="utf-8"))
        if isinstance(loaded, list):
            pinned_overrides = loaded

    comp_dir = repo_root / "specs" / "components" / slug
    documents = {}
    for doc_path in sorted(comp_dir.rglob("*.md"), key=lambda p: p.relative_to(comp_dir).as_posix()):
        documents[doc_path.relative_to(comp_dir).as_posix()] = doc_path.read_text(encoding="utf-8")

    return {
        "type": "component",
        "verification": verification,
        "provenance": provenance,
        "size_status": size_status,
        "sealed": doc_row.get("sealed") is True,
        "pinned_overrides": pinned_overrides,
        "owners": list(doc_row.get("owners") or []),
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
            str(cid): int(wc)
            for cid, wc in con.execute(
                "SELECT component_id, word_count FROM component_size"
            ).fetchall()
        }
        cur = con.execute("SELECT * FROM component_docs")
        columns = [d[0] for d in cur.description]
        docs = {}
        for row in cur.fetchall():
            row_dict = dict(zip(columns, row))
            docs[row_dict["id"]] = row_dict
    finally:
        con.close()

    edges = sorted(
        (
            {"from": str(src), "to": str(dst), "kind": str(kind)}
            for src, dst, kind in edge_rows
        ),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    nodes = {}
    for node_id, kind in node_rows:
        node_id = str(node_id)
        if kind == "component":
            nodes[node_id] = _component_node(repo_root, node_id, docs.get(node_id, {}), sizes)
        else:
            nodes[node_id] = {"type": str(kind)}

    realized = {e["to"] for e in edges if e["kind"] == "realizes"}
    used_vars = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depended_on = {e["to"] for e in edges if e["kind"] == "depends_on"}
    realizers = {e["from"] for e in edges if e["kind"] == "realizes"}

    capabilities = [n for n, v in nodes.items() if v["type"] == "capability"]
    variables = [n for n, v in nodes.items() if v["type"] == "var"]
    components = [n for n, v in nodes.items() if v["type"] == "component"]

    aggregates = {
        "orphan_capability_rate": _rate(
            sum(1 for c in capabilities if c not in realized), len(capabilities)
        ),
        "orphan_component_rate": _rate(
            sum(1 for c in components if c not in depended_on and c not in realizers),
            len(components),
        ),
        "orphan_var_rate": _rate(
            sum(1 for v in variables if v not in used_vars), len(variables)
        ),
    }

    return CorpusGraph(
        nodes={k: nodes[k] for k in sorted(nodes)},
        edges=edges,
        aggregates=aggregates,
    )


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    out_dir = Path(repo_root) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "corpus-graph.json"
    path.write_bytes(graph.to_json_bytes())
    return path

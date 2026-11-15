"""Corpus Graph Builder: builds verification/corpus-graph.json."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph"]

_EDGE_KINDS = ("depends_on", "realizes", "uses_var")
_NODE_KINDS = ("component", "capability", "var")
_SIZE_CAP = 4000


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


def _dep_dir(repo_root: Path, rel: str) -> Path:
    candidate = Path(repo_root) / rel
    if candidate.is_dir():
        return candidate
    gen_dir = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
    return gen_dir.parent / rel


def _load_module(directory: Path, name: str):
    flat = directory / f"{name}.py"
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(name, flat)
    else:
        pkg = directory / name
        spec = importlib.util.spec_from_file_location(
            name, pkg / "__init__.py", submodule_search_locations=[str(pkg)]
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return count / total


def _read_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _component_node(repo_root: Path, cid: str, doc: dict, sizes: dict) -> dict:
    slug = cid[len("comp-"):]

    verification = None
    provenance = None
    manifest_path = repo_root / "verification" / slug / ".provenance.json"
    if manifest_path.is_file():
        manifest = _read_json(manifest_path)
        verification = manifest.get("verification_report")
        provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

    if slug in sizes:
        size_status = "ok" if sizes[slug] <= _SIZE_CAP else "over"
    else:
        size_status = "unknown"

    pinned = []
    overrides_path = repo_root / "gen" / slug / ".overrides.json"
    if overrides_path.is_file():
        data = _read_json(overrides_path)
        if isinstance(data, list):
            pinned = data

    comp_dir = repo_root / "specs" / "components" / slug
    documents = {}
    for path in sorted(comp_dir.rglob("*.md")):
        rel = path.relative_to(comp_dir).as_posix()
        documents[rel] = path.read_text(encoding="utf-8")
    documents = {k: documents[k] for k in sorted(documents)}

    return {
        "type": "component",
        "verification": verification,
        "provenance": provenance,
        "size_status": size_status,
        "sealed": bool(doc.get("sealed") or False),
        "pinned_overrides": pinned,
        "owners": list(doc.get("owners") or []),
        "documents": documents,
    }


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    gqe = _load_module(_dep_dir(repo_root, "gen/graph-query-engine"), "graph_query_engine")

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
            str(cid): wc
            for cid, wc in con.execute(
                "SELECT component_id, word_count FROM component_size"
            ).fetchall()
        }
        cur = con.execute("SELECT * FROM component_docs")
        cols = [d[0] for d in cur.description]
        docs = {}
        for row in cur.fetchall():
            rec = dict(zip(cols, row))
            docs[str(rec["id"])] = rec
    finally:
        con.close()

    edges = sorted(
        (
            {"from": str(src), "to": str(dst), "kind": str(kind)}
            for src, dst, kind in edge_rows
        ),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    components = sorted(str(i) for i, k in node_rows if k == "component")
    capabilities = sorted(str(i) for i, k in node_rows if k == "capability")
    vars_ = sorted(str(i) for i, k in node_rows if k == "var")

    nodes = {}
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

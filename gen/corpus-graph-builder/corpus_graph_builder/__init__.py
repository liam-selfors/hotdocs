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


def _tool_root() -> Path:
    return next(p.parent for p in Path(__file__).resolve().parents if p.name == "gen")


def _load_graph_query_engine(repo_root: Path):
    gqe_dir = repo_root / "gen" / "graph-query-engine"
    if not gqe_dir.is_dir():
        gqe_dir = _tool_root() / "gen" / "graph-query-engine"
    name = "graph_query_engine"
    spec = importlib.util.spec_from_file_location(name, gqe_dir / "graph_query_engine.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(text: str) -> dict:
    fm = {}
    for line in text.splitlines()[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            fm[key.strip()] = value.strip()
    return fm


def _parse_list(value: str) -> list:
    inner = value.strip()[1:-1]
    return [s.strip() for s in inner.split(",") if s.strip()]


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _component_node(repo_root: Path, slug: str, sizes: dict) -> dict:
    comp_dir = repo_root / "specs" / "components" / slug
    documents = {}
    for path in sorted(comp_dir.rglob("*.md")):
        documents[path.relative_to(comp_dir).as_posix()] = path.read_text(encoding="utf-8")
    documents = dict(sorted(documents.items()))

    fm = _frontmatter(documents.get("component.md", ""))
    sealed = fm.get("sealed", "false").lower() == "true"
    owners = _parse_list(fm["owners"]) if "owners" in fm else []

    verification = None
    provenance = None
    manifest_path = repo_root / "verification" / slug / ".provenance.json"
    if manifest_path.is_file():
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        verification = manifest.get("verification_report")
        provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

    overrides = []
    overrides_path = repo_root / "gen" / slug / ".overrides.json"
    if overrides_path.is_file():
        with open(overrides_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, list):
            overrides = loaded

    words = sizes.get(slug)
    if words is None:
        size_status = "unknown"
    elif words <= SIZE_CAP:
        size_status = "ok"
    else:
        size_status = "over"

    return {
        "type": "component",
        "verification": verification,
        "provenance": provenance,
        "size_status": size_status,
        "sealed": sealed,
        "pinned_overrides": overrides,
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
        size_rows = con.execute(
            "SELECT component_id, word_count FROM component_size"
        ).fetchall()
    finally:
        con.close()

    sizes = {str(cid): int(wc) for cid, wc in size_rows if wc is not None}

    edges = sorted(
        ({"from": str(s), "to": str(t), "kind": str(k)} for s, t, k in edge_rows),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    components = sorted(str(i) for i, k in node_rows if k == "component")
    capabilities = sorted(str(i) for i, k in node_rows if k == "capability")
    variables = sorted(str(i) for i, k in node_rows if k == "var")

    nodes = {}
    for cap in capabilities:
        nodes[cap] = {"type": "capability"}
    for var in variables:
        nodes[var] = {"type": "var"}
    for comp in components:
        nodes[comp] = _component_node(repo_root, comp[len("comp-"):], sizes)

    realized = {e["to"] for e in edges if e["kind"] == "realizes"}
    used_vars = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depended = {e["to"] for e in edges if e["kind"] == "depends_on"}
    realizers = {e["from"] for e in edges if e["kind"] == "realizes"}

    orphan_caps = sum(1 for c in capabilities if c not in realized)
    orphan_vars = sum(1 for v in variables if v not in used_vars)
    orphan_comps = sum(
        1 for c in components if c not in depended and c not in realizers
    )

    aggregates = {
        "orphan_capability_rate": _rate(orphan_caps, len(capabilities)),
        "orphan_component_rate": _rate(orphan_comps, len(components)),
        "orphan_var_rate": _rate(orphan_vars, len(variables)),
    }

    return CorpusGraph(nodes=dict(sorted(nodes.items())), edges=edges, aggregates=aggregates)


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    out_dir = Path(repo_root) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "corpus-graph.json"
    path.write_bytes(graph.to_json_bytes())
    return path


from .cli import main  # noqa: E402

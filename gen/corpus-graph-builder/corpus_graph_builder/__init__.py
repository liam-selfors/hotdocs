"""Build verification/corpus-graph.json from the spec corpus."""

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
OUTPUT_REL = Path("verification") / "corpus-graph.json"


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
    dep_dir = repo_root / "gen" / "graph-query-engine"
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / "graph-query-engine"
    path = dep_dir / "graph_query_engine.py"
    name = "graph_query_engine"
    spec = importlib.util.spec_from_file_location(name, str(path))
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
    load_views = gqe["load_views"] if isinstance(gqe, dict) else getattr(gqe, "load_views")
    load_views(con, repo_root)
    return con


def _frontmatter(text: str) -> dict:
    lines = text.splitlines()
    result = {}
    if not lines or lines[0].strip() != "---":
        return result
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = value.strip()
    return result


def _parse_list(value: str) -> list:
    inner = value.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1]
    items = [item.strip().strip("\"'") for item in inner.split(",")]
    return [item for item in items if item]


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _component_node(repo_root: Path, comp_id: str, sizes: dict) -> dict:
    slug = comp_id[len("comp-"):] if comp_id.startswith("comp-") else comp_id
    spec_dir = repo_root / "specs" / "components" / slug

    documents = {}
    if spec_dir.is_dir():
        for doc in sorted(spec_dir.rglob("*.md")):
            if doc.is_file():
                rel = doc.relative_to(spec_dir).as_posix()
                documents[rel] = doc.read_text(encoding="utf-8")
    documents = dict(sorted(documents.items()))

    fm = _frontmatter(documents.get("component.md", ""))
    sealed = fm.get("sealed", "false").strip("\"'").lower() == "true"
    owners = _parse_list(fm["owners"]) if "owners" in fm else []

    verification = None
    provenance = None
    manifest_path = repo_root / "verification" / slug / ".provenance.json"
    if manifest_path.is_file():
        with manifest_path.open(encoding="utf-8") as fh:
            manifest = json.load(fh)
        verification = manifest.get("verification_report")
        provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

    pinned = []
    overrides_path = repo_root / "gen" / slug / ".overrides.json"
    if overrides_path.is_file():
        with overrides_path.open(encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, list):
            pinned = loaded

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
        "pinned_overrides": pinned,
        "owners": owners,
        "documents": documents,
    }


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    con = _connect(repo_root)
    try:
        node_rows = con.execute(
            "SELECT DISTINCT id, kind FROM nodes "
            "WHERE kind IN ('component', 'capability', 'var')"
        ).fetchall()
        edge_rows = con.execute(
            "SELECT DISTINCT source_id, target_id, edge_type FROM edges "
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

    capabilities = sorted(str(i) for i, k in node_rows if k == "capability")
    variables = sorted(str(i) for i, k in node_rows if k == "var")
    components = sorted(str(i) for i, k in node_rows if k == "component")

    nodes = {}
    for cap in capabilities:
        nodes[cap] = {"type": "capability"}
    for var in variables:
        nodes[var] = {"type": "var"}
    for comp in components:
        nodes[comp] = _component_node(repo_root, comp, sizes)

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
    out = Path(repo_root) / OUTPUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(graph.to_json_bytes())
    return out


from .cli import main  # noqa: E402

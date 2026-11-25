"""Corpus Graph Builder: builds verification/corpus-graph.json."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

_GQE_SLUG = "graph-query-engine"
_GQE_MODULE = "graph_query_engine"
_SIZE_CAP = 4000
_EDGE_KINDS = ("depends_on", "realizes", "uses_var")
_NODE_KINDS = ("component", "capability", "var")


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
    return next(p for p in here.parents if p.name == "gen").parent


def _load_gqe(repo_root: Path):
    dep_dir = repo_root / "gen" / _GQE_SLUG
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / _GQE_SLUG
    spec = importlib.util.spec_from_file_location(
        _GQE_MODULE, str(dep_dir / (_GQE_MODULE + ".py"))
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_GQE_MODULE] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter(text: str) -> dict:
    lines = text.splitlines()
    result = {}
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, _, value = line.partition(":")
                result[key.strip()] = value.strip()
    return result


def _flow_list(value: str) -> list:
    inner = value.strip()[1:-1]
    return [s.strip().strip("\"'") for s in inner.split(",") if s.strip()]


def _rate(count: int, total: int) -> float:
    return float(count) / float(total) if total else 0.0


def _component_node(repo_root: Path, slug: str, sizes: dict) -> dict:
    comp_dir = repo_root / "specs" / "components" / slug
    fm = _frontmatter((comp_dir / "component.md").read_text(encoding="utf-8"))

    verification = None
    provenance = None
    manifest_path = repo_root / "verification" / slug / ".provenance.json"
    if manifest_path.is_file():
        with manifest_path.open("r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        verification = manifest.get("verification_report")
        provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

    count = sizes.get(slug)
    if count is None:
        size_status = "unknown"
    elif count <= _SIZE_CAP:
        size_status = "ok"
    else:
        size_status = "over"

    pinned = []
    overrides_path = repo_root / "gen" / slug / ".overrides.json"
    if overrides_path.is_file():
        with overrides_path.open("r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, list):
            pinned = loaded

    owners = _flow_list(fm["owners"]) if "owners" in fm else []

    documents = {}
    for path in sorted(comp_dir.rglob("*.md"), key=lambda p: p.relative_to(comp_dir).as_posix()):
        documents[path.relative_to(comp_dir).as_posix()] = path.read_text(encoding="utf-8")

    return {
        "type": "component",
        "verification": verification,
        "provenance": provenance,
        "size_status": size_status,
        "sealed": fm.get("sealed") == "true",
        "pinned_overrides": pinned,
        "owners": owners,
        "documents": documents,
    }


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    gqe = _load_gqe(repo_root)
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

    sizes = {str(cid): wc for cid, wc in size_rows}

    edges = sorted(
        ({"from": str(s), "to": str(t), "kind": str(k)} for s, t, k in edge_rows),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    nodes = {}
    capabilities = []
    variables = []
    components = []
    for node_id, kind in sorted((str(i), str(k)) for i, k in node_rows):
        if kind == "component":
            components.append(node_id)
            slug = node_id[len("comp-"):] if node_id.startswith("comp-") else node_id
            nodes[node_id] = _component_node(repo_root, slug, sizes)
        else:
            if kind == "capability":
                capabilities.append(node_id)
            else:
                variables.append(node_id)
            nodes[node_id] = {"type": kind}

    realized = {e["to"] for e in edges if e["kind"] == "realizes"}
    used_vars = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depended_on = {e["to"] for e in edges if e["kind"] == "depends_on"}
    realizers = {e["from"] for e in edges if e["kind"] == "realizes"}

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

    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    out_dir = Path(repo_root) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "corpus-graph.json"
    out_path.write_bytes(graph.to_json_bytes())
    return out_path


from .cli import main  # noqa: E402

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph", "main"]

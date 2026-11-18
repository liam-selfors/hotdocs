"""Corpus Graph Builder: builds verification/corpus-graph.json."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph"]

_NODE_KINDS = ("capability", "component", "var")
_EDGE_KINDS = ("depends_on", "realizes", "uses_var")
_SIZE_CAP = 4000
_GQE_SLUG = "graph-query-engine"
_GQE_MODULE = "graph_query_engine"


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
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return Path(__file__).resolve().parent


def _load_graph_query_engine(repo_root: Path):
    dep_dir = Path(repo_root) / "gen" / _GQE_SLUG
    if not dep_dir.is_dir():
        dep_dir = _tool_root() / "gen" / _GQE_SLUG
    flat = dep_dir / (_GQE_MODULE + ".py")
    if flat.is_file():
        spec = importlib.util.spec_from_file_location(_GQE_MODULE, flat)
    else:
        spec = importlib.util.spec_from_file_location(
            _GQE_MODULE,
            dep_dir / _GQE_MODULE / "__init__.py",
            submodule_search_locations=[str(dep_dir / _GQE_MODULE)],
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[_GQE_MODULE] = module
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
    load_views(con, Path(repo_root))
    return con


def _frontmatter(text: str) -> dict:
    lines = text.splitlines()
    result: dict = {}
    if not lines or lines[0].strip() != "---":
        return result
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def _parse_list(value: str) -> list:
    inner = value.strip()[1:-1]
    items = []
    for part in inner.split(","):
        item = part.strip().strip("\"'")
        if item:
            items.append(item)
    return items


def _documents(comp_dir: Path) -> dict:
    docs = {}
    for path in sorted(comp_dir.rglob("*.md")):
        if path.is_file():
            docs[path.relative_to(comp_dir).as_posix()] = path.read_text(encoding="utf-8")
    return dict(sorted(docs.items()))


def _rate(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return count / total


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    con = _connect(repo_root)
    try:
        node_rows = con.execute(
            "SELECT id, kind FROM nodes WHERE kind IN ('capability', 'component', 'var')"
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

    sizes = {str(cid): int(wc) for cid, wc in size_rows}

    edges = sorted(
        (
            {"from": str(src), "to": str(dst), "kind": str(kind)}
            for src, dst, kind in edge_rows
        ),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    nodes: dict = {}
    for node_id, kind in sorted((str(i), str(k)) for i, k in node_rows):
        if kind != "component":
            nodes[node_id] = {"type": kind}
            continue
        slug = node_id[len("comp-"):] if node_id.startswith("comp-") else node_id
        comp_dir = repo_root / "specs" / "components" / slug
        component_md = comp_dir / "component.md"
        fm = _frontmatter(component_md.read_text(encoding="utf-8")) if component_md.is_file() else {}

        manifest_path = repo_root / "verification" / slug / ".provenance.json"
        verification = None
        provenance = None
        if manifest_path.is_file():
            with manifest_path.open("r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            verification = manifest.get("verification_report")
            provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

        if slug in sizes:
            size_status = "ok" if sizes[slug] <= _SIZE_CAP else "over"
        else:
            size_status = "unknown"

        overrides_path = repo_root / "gen" / slug / ".overrides.json"
        pinned = []
        if overrides_path.is_file():
            with overrides_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                pinned = loaded

        owners = _parse_list(fm["owners"]) if "owners" in fm else []

        nodes[node_id] = {
            "type": "component",
            "verification": verification,
            "provenance": provenance,
            "size_status": size_status,
            "sealed": fm.get("sealed", "false") == "true",
            "pinned_overrides": pinned,
            "owners": owners,
            "documents": _documents(comp_dir) if comp_dir.is_dir() else {},
        }

    realized = {e["to"] for e in edges if e["kind"] == "realizes"}
    used_vars = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depended_on = {e["to"] for e in edges if e["kind"] == "depends_on"}
    realizers = {e["from"] for e in edges if e["kind"] == "realizes"}

    capabilities = [i for i, n in nodes.items() if n["type"] == "capability"]
    vars_ = [i for i, n in nodes.items() if n["type"] == "var"]
    components = [i for i, n in nodes.items() if n["type"] == "component"]

    aggregates = {
        "orphan_capability_rate": _rate(
            sum(1 for c in capabilities if c not in realized), len(capabilities)
        ),
        "orphan_component_rate": _rate(
            sum(1 for c in components if c not in depended_on and c not in realizers),
            len(components),
        ),
        "orphan_var_rate": _rate(
            sum(1 for v in vars_ if v not in used_vars), len(vars_)
        ),
    }

    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    out_dir = Path(repo_root) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "corpus-graph.json"
    out_path.write_bytes(graph.to_json_bytes())
    return out_path

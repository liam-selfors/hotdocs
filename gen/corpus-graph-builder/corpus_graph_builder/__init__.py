"""Builds verification/corpus-graph.json from the spec corpus (R-GRAPH-*)."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

SIZE_CAP = 4000
_NODE_KINDS = ("component", "capability", "var")
_EDGE_KINDS = ("depends_on", "realizes", "uses_var")
_OUTPUT = Path("verification") / "corpus-graph.json"


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


def _load_graph_query_engine(repo_root: Path):
    directory = Path(repo_root) / "gen" / "graph-query-engine"
    if not directory.is_dir():
        directory = _tool_root() / "gen" / "graph-query-engine"
    spec = importlib.util.spec_from_file_location(
        "graph_query_engine", str(directory / "graph_query_engine.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["graph_query_engine"] = module
    spec.loader.exec_module(module)
    return module


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _rows(con, sql: str) -> list:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def _documents(component_dir: Path) -> dict:
    docs = {}
    for path in sorted(component_dir.rglob("*.md")):
        docs[path.relative_to(component_dir).as_posix()] = path.read_text(encoding="utf-8")
    return dict(sorted(docs.items()))


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    gqe = _load_graph_query_engine(repo_root)
    con = duckdb.connect(":memory:")
    try:
        con.execute("INSTALL yaml FROM community")
    except Exception:
        pass
    con.execute("LOAD yaml")
    _get(gqe, "load_views")(con, repo_root)

    node_rows = con.execute(
        "SELECT id, kind FROM nodes WHERE kind IN ('component', 'capability', 'var')"
    ).fetchall()
    edge_rows = con.execute(
        "SELECT source_id, target_id, edge_type FROM edges "
        "WHERE edge_type IN ('depends_on', 'realizes', 'uses_var')"
    ).fetchall()
    sizes = {
        str(cid): int(words)
        for cid, words in con.execute(
            "SELECT component_id, word_count FROM component_size"
        ).fetchall()
    }
    docs_by_id = {str(r["id"]): r for r in _rows(con, "SELECT * FROM component_docs")}
    con.close()

    edges = sorted(
        ({"from": str(s), "to": str(t), "kind": str(k)} for s, t, k in edge_rows),
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )

    nodes: dict = {}
    for node_id, kind in node_rows:
        node_id = str(node_id)
        kind = str(kind)
        if kind != "component":
            nodes[node_id] = {"type": kind}
            continue
        slug = node_id[len("comp-"):]
        manifest_path = repo_root / "verification" / slug / ".provenance.json"
        verification = None
        provenance = None
        if manifest_path.is_file():
            with open(manifest_path, encoding="utf-8") as fh:
                manifest = json.load(fh)
            verification = manifest.get("verification_report")
            provenance = {k: v for k, v in manifest.items() if k != "verification_report"}
        words = sizes.get(slug)
        if words is None:
            size_status = "unknown"
        elif words <= SIZE_CAP:
            size_status = "ok"
        else:
            size_status = "over"
        overrides_path = repo_root / "gen" / slug / ".overrides.json"
        pinned = []
        if overrides_path.is_file():
            with open(overrides_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, list):
                pinned = loaded
        frontmatter = docs_by_id.get(node_id, {})
        owners = frontmatter.get("owners")
        nodes[node_id] = {
            "type": "component",
            "verification": verification,
            "provenance": provenance,
            "size_status": size_status,
            "sealed": frontmatter.get("sealed") is True,
            "pinned_overrides": pinned,
            "owners": [str(o) for o in owners] if owners is not None else [],
            "documents": _documents(repo_root / "specs" / "components" / slug),
        }

    def ids_of(kind):
        return [i for i, n in nodes.items() if n["type"] == kind]

    realized = {e["to"] for e in edges if e["kind"] == "realizes"}
    used_vars = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depended = {e["to"] for e in edges if e["kind"] == "depends_on"}
    realizing = {e["from"] for e in edges if e["kind"] == "realizes"}

    capabilities = ids_of("capability")
    vars_ = ids_of("var")
    components = ids_of("component")

    aggregates = {
        "orphan_capability_rate": _rate(
            sum(1 for c in capabilities if c not in realized), len(capabilities)
        ),
        "orphan_component_rate": _rate(
            sum(1 for c in components if c not in depended and c not in realizing),
            len(components),
        ),
        "orphan_var_rate": _rate(sum(1 for v in vars_ if v not in used_vars), len(vars_)),
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    path = Path(repo_root) / _OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(graph.to_json_bytes())
    return path


from .cli import main  # noqa: E402

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph", "main"]

"""Corpus Graph Builder: builds verification/corpus-graph.json."""

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import duckdb

__all__ = ["CorpusGraph", "build_corpus_graph", "write_corpus_graph"]

_NODE_KINDS = ("capability", "component", "var")
_EDGE_KINDS = ("depends_on", "realizes", "uses_var")
_SIZE_CAP = 4000


@dataclass
class CorpusGraph:
    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self):
        text = json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
        return (text + "\n").encode("utf-8")


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent


def _load_graph_query_engine(repo_root):
    module_dir = repo_root / "gen" / "graph-query-engine"
    if not module_dir.is_dir():
        module_dir = _tool_root() / "gen" / "graph-query-engine"
    spec = importlib.util.spec_from_file_location(
        "graph_query_engine", str(module_dir / "graph_query_engine.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["graph_query_engine"] = module
    spec.loader.exec_module(module)
    return module


def _sealed(repo_root, slug):
    path = repo_root / "specs" / "components" / slug / "component.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        if key.strip() == "sealed":
            return value.strip() == "true"
    return False


def _manifest(repo_root, slug):
    path = repo_root / "verification" / slug / ".provenance.json"
    if not path.is_file():
        return None, None
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    verification = data.get("verification_report")
    provenance = {k: v for k, v in data.items() if k != "verification_report"}
    return verification, provenance


def _overrides(repo_root, slug):
    path = repo_root / "gen" / slug / ".overrides.json"
    if not path.is_file():
        return []
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, list):
        return data
    return []


def _rate(count, total):
    if total == 0:
        return 0.0
    return count / total


def build_corpus_graph(repo_root):
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

    sizes = {str(cid): wc for cid, wc in size_rows}

    edge_set = sorted({(str(s), str(t), str(k)) for s, t, k in edge_rows})
    edges = [{"from": s, "to": t, "kind": k} for s, t, k in edge_set]

    nodes = {}
    capabilities = []
    components = []
    variables = []
    for node_id, kind in sorted((str(i), str(k)) for i, k in node_rows):
        if kind == "component":
            slug = node_id[len("comp-"):]
            verification, provenance = _manifest(repo_root, slug)
            if slug in sizes:
                size_status = "ok" if sizes[slug] <= _SIZE_CAP else "over"
            else:
                size_status = "unknown"
            nodes[node_id] = {
                "type": "component",
                "verification": verification,
                "provenance": provenance,
                "size_status": size_status,
                "sealed": _sealed(repo_root, slug),
                "pinned_overrides": _overrides(repo_root, slug),
            }
            components.append(node_id)
        elif kind == "capability":
            nodes[node_id] = {"type": "capability"}
            capabilities.append(node_id)
        else:
            nodes[node_id] = {"type": "var"}
            variables.append(node_id)

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


def write_corpus_graph(graph, repo_root):
    out_dir = Path(repo_root) / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "corpus-graph.json"
    path.write_bytes(graph.to_json_bytes())
    return path

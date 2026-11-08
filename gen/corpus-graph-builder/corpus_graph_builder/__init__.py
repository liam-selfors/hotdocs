"""Builds verification/corpus-graph.json from the corpus + provenance state."""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any


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
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    raise RuntimeError("could not locate tool root above corpus_graph_builder")


def _load_module_from_dir(base: Path, module_name: str) -> ModuleType | None:
    flat = base / f"{module_name}.py"
    pkg_init = base / module_name / "__init__.py"
    if flat.is_file():
        path = flat
        submodule_search_locations = None
    elif pkg_init.is_file():
        path = pkg_init
        submodule_search_locations = [str(path.parent)]
    else:
        return None

    spec = importlib.util.spec_from_file_location(
        module_name, path, submodule_search_locations=submodule_search_locations
    )
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _resolve_dependency_dir(repo_root: Path, dep_dir_name: str) -> Path:
    candidate = repo_root / "gen" / dep_dir_name
    if candidate.is_dir():
        return candidate
    return _tool_root() / "gen" / dep_dir_name


def _load_graph_query_engine(repo_root: Path) -> ModuleType:
    base = _resolve_dependency_dir(repo_root, "graph-query-engine")
    module = _load_module_from_dir(base, "graph_query_engine")
    if module is None:
        raise ImportError(f"graph_query_engine not found under {base}")
    return module


def _read_json_file(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_corpus_graph(repo_root: Path) -> CorpusGraph:
    repo_root = Path(repo_root)
    gqe = _load_graph_query_engine(repo_root)

    import duckdb

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
        size_map = {row[0]: row[1] for row in size_rows}

        docs_result = con.execute("SELECT * FROM component_docs")
        doc_cols = [d[0] for d in docs_result.description]
        docs_rows = docs_result.fetchall()
        sealed_map: dict[str, bool] = {}
        for row in docs_rows:
            row_dict = dict(zip(doc_cols, row))
            comp_id = row_dict.get("id")
            if comp_id is None:
                continue
            sealed_map[comp_id] = bool(row_dict.get("sealed")) if row_dict.get("sealed") else False
    finally:
        con.close()

    nodes: dict = {}
    for node_id, kind in node_rows:
        if kind == "capability":
            nodes[node_id] = {"type": "capability"}
        elif kind == "var":
            nodes[node_id] = {"type": "var"}
        elif kind == "component":
            slug = node_id[len("comp-"):] if node_id.startswith("comp-") else node_id

            manifest_path = repo_root / "verification" / slug / ".provenance.json"
            verification = None
            provenance = None
            if manifest_path.is_file():
                manifest = _read_json_file(manifest_path)
                if not isinstance(manifest, dict):
                    manifest = {}
                verification = manifest.get("verification_report")
                provenance = {k: v for k, v in manifest.items() if k != "verification_report"}

            word_count = size_map.get(slug)
            if word_count is None:
                size_status = "unknown"
            elif word_count <= 4000:
                size_status = "ok"
            else:
                size_status = "over"

            sealed = sealed_map.get(node_id, False)

            pinned_overrides: list = []
            overrides_path = repo_root / "gen" / slug / ".overrides.json"
            if overrides_path.is_file():
                try:
                    data = _read_json_file(overrides_path)
                except (json.JSONDecodeError, OSError):
                    data = None
                if isinstance(data, list):
                    pinned_overrides = data

            nodes[node_id] = {
                "type": "component",
                "verification": verification,
                "provenance": provenance,
                "size_status": size_status,
                "sealed": sealed,
                "pinned_overrides": pinned_overrides,
            }

    edges = [
        {"from": source_id, "to": target_id, "kind": edge_type}
        for source_id, target_id, edge_type in edge_rows
    ]
    edges.sort(key=lambda e: (e["from"], e["to"], e["kind"]))

    capability_ids = {node_id for node_id, kind in node_rows if kind == "capability"}
    var_ids = {node_id for node_id, kind in node_rows if kind == "var"}
    component_ids = {node_id for node_id, kind in node_rows if kind == "component"}

    realizes_targets = {e["to"] for e in edges if e["kind"] == "realizes"}
    realizes_sources = {e["from"] for e in edges if e["kind"] == "realizes"}
    uses_var_targets = {e["to"] for e in edges if e["kind"] == "uses_var"}
    depends_on_targets = {e["to"] for e in edges if e["kind"] == "depends_on"}

    orphan_capabilities = sum(1 for c in capability_ids if c not in realizes_targets)
    orphan_capability_rate = (
        orphan_capabilities / len(capability_ids) if capability_ids else 0.0
    )

    orphan_vars = sum(1 for v in var_ids if v not in uses_var_targets)
    orphan_var_rate = orphan_vars / len(var_ids) if var_ids else 0.0

    orphan_components = sum(
        1
        for c in component_ids
        if c not in depends_on_targets and c not in realizes_sources
    )
    orphan_component_rate = (
        orphan_components / len(component_ids) if component_ids else 0.0
    )

    aggregates = {
        "orphan_capability_rate": orphan_capability_rate,
        "orphan_component_rate": orphan_component_rate,
        "orphan_var_rate": orphan_var_rate,
    }

    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def write_corpus_graph(graph: CorpusGraph, repo_root: Path) -> Path:
    repo_root = Path(repo_root)
    out_dir = repo_root / "verification"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "corpus-graph.json"
    out_path.write_bytes(graph.to_json_bytes())
    return out_path
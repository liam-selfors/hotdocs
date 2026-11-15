"""AC-DOCS-001: a corpus graph with three nodes and two edges renders a DAG
view holding three node elements and two edge elements."""

import docs_site_renderer

import json
import re
from dataclasses import dataclass, field as dc_field
from html.parser import HTMLParser
from pathlib import Path


NODE_IDS = ["comp-alphaqz", "comp-betaqz", "P-GAMMAQZ"]
EDGES = [
    {"from": "comp-alphaqz", "to": "P-GAMMAQZ", "kind": "realizes"},
    {"from": "comp-alphaqz", "to": "comp-betaqz", "kind": "depends_on"},
]


@dataclass
class CorpusGraph:
    """Matches corpus-graph-builder's documented CorpusGraph shape."""

    nodes: dict
    edges: list
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _component_node(slug_id, text):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "unknown",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["docs-team"],
        "documents": {"component.md": text},
    }


def _build_graph():
    nodes = {
        "comp-alphaqz": _component_node("comp-alphaqz", "# Alpha\n\nAlpha component.\n"),
        "comp-betaqz": _component_node("comp-betaqz", "# Beta\n\nBeta component.\n"),
        "P-GAMMAQZ": {"type": "capability"},
    }
    edges = sorted(EDGES, key=lambda e: (e["from"], e["to"], e["kind"]))
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, {k: (v or "") for k, v in attrs}))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def _refs(value, node_id):
    return re.search(r"(?<![A-Za-z0-9-])" + re.escape(node_id) + r"(?![A-Za-z0-9-])", value) is not None


def _ids_in(value):
    return {nid for nid in NODE_IDS if _refs(value, nid)}


FROM_ATTRS = ("data-from", "data-source", "data-src")
TO_ATTRS = ("data-to", "data-target", "data-dst")
NODE_ID_ATTRS = ("data-id", "data-node", "data-node-id", "id")
NODE_CLASSES = {"node", "dag-node", "graph-node"}
EDGE_CLASSES = {"edge", "dag-edge", "graph-edge"}


def _is_edge_by_attrs(attrs):
    frm = next((attrs[a] for a in FROM_ATTRS if a in attrs), None)
    to = next((attrs[a] for a in TO_ATTRS if a in attrs), None)
    return frm is not None and to is not None, frm, to


def _strategies(elements):
    """Yield (node_count, edge_count) under several plausible markup conventions."""
    results = []

    # 1. Class-based: one element per node/edge carrying a node/edge class.
    nc = ec = 0
    for _tag, attrs in elements:
        classes = set(attrs.get("class", "").split())
        if classes & EDGE_CLASSES:
            ec += 1
        elif classes & NODE_CLASSES:
            nc += 1
    results.append(("class", nc, ec))

    # 2. Data-attribute based: edges carry from/to, nodes carry an id.
    nc = ec = 0
    for _tag, attrs in elements:
        is_edge, frm, to = _is_edge_by_attrs(attrs)
        if is_edge:
            if _ids_in(frm) and _ids_in(to):
                ec += 1
            continue
        for a in NODE_ID_ATTRS:
            v = attrs.get(a)
            if v is None:
                continue
            if v in NODE_IDS or (v.startswith("node-") and v[len("node-"):] in NODE_IDS):
                nc += 1
                break
    results.append(("data-attrs", nc, ec))

    # 3. Link-based nodes (one link per node to its detail page) with
    #    attribute-based edges.
    nc = ec = 0
    for tag, attrs in elements:
        is_edge, frm, to = _is_edge_by_attrs(attrs)
        if is_edge:
            if _ids_in(frm) and _ids_in(to):
                ec += 1
            continue
        if tag == "a" and len(_ids_in(attrs.get("href", ""))) == 1:
            nc += 1
    results.append(("links", nc, ec))

    return results


def test_ac_docs_001_dag_view_has_three_nodes_and_two_edges(tmp_path):
    graph = _build_graph()
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2

    # Given: a corpus-graph.json with three nodes and two edges.
    repo_root = tmp_path / "repo"
    (repo_root / "verification").mkdir(parents=True)
    graph_path = repo_root / "verification" / "corpus-graph.json"
    graph_path.write_bytes(graph.to_json_bytes())
    loaded = json.loads(graph_path.read_text(encoding="utf-8"))
    assert len(loaded["nodes"]) == 3 and len(loaded["edges"]) == 2

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    # When: render_docs_site runs.
    result = docs_site_renderer.render_docs_site(graph, out_dir)
    assert result is None

    html_files = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".html", ".htm"))
    assert html_files, "render_docs_site wrote no HTML pages to out_dir"

    # Locate the DAG view: a page referencing every node id; prefer index.html.
    candidates = []
    for p in html_files:
        text = p.read_text(encoding="utf-8", errors="replace")
        if all(_refs(text, nid) for nid in NODE_IDS):
            candidates.append((p, text))
    assert candidates, "no rendered page references all three graph nodes"
    candidates.sort(key=lambda pt: (pt[0].name.lower() not in ("index.html", "index.htm"), len(pt[0].parts), str(pt[0])))

    # Then: the DAG view contains three node elements and two edge elements.
    observations = []
    for path, text in candidates:
        parser = _Collector()
        parser.feed(text)
        parser.close()
        for name, nc, ec in _strategies(parser.elements):
            observations.append((str(path.relative_to(out_dir)), name, nc, ec))
            if nc == 3 and ec == 2:
                return

    raise AssertionError(
        "no rendered page's DAG view holds exactly 3 node elements and 2 edge "
        "elements; observed (page, convention, nodes, edges): %r" % (observations,)
    )
# hotdocs-criterion: sha256:b577e82c6db247db3e9eaf82106ecd2804a55f9b8067dc65491effe74be97008
"""AC-DOCS-001: a corpus graph with three nodes and two edges renders a DAG
view in index.html holding three node elements and two edge elements."""

import json
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


class FakeCorpusGraph:
    """Duck-typed stand-in for corpus-graph-builder's CorpusGraph dataclass:
    attributes `nodes`, `edges`, `aggregates`, plus `to_dict()` and
    `to_json_bytes()` as its interface documents them."""

    def __init__(self, nodes, edges, aggregates):
        self.nodes = nodes
        self.edges = edges
        self.aggregates = aggregates

    def to_dict(self):
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
            + "\n"
        ).encode("utf-8")

    def __getitem__(self, key):
        return self.to_dict()[key]


def _graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-alpha": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": "---\nid: comp-alpha\ntitle: Alpha\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Alpha\n",
            },
        },
        "VAR-ALPHA": {"type": "var"},
    }
    edges = [
        {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
        {"from": "comp-alpha", "to": "VAR-ALPHA", "kind": "uses_var"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return FakeCorpusGraph(nodes, edges, aggregates)


class _ListCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ul_stack = []
        self.items = []  # (ul id, classes, attrs)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "ul":
            self.ul_stack.append(attrs.get("id"))
        elif tag == "li":
            parent = self.ul_stack[-1] if self.ul_stack else None
            classes = (attrs.get("class") or "").split()
            self.items.append((parent, classes, attrs))

    def handle_endtag(self, tag):
        if tag == "ul" and self.ul_stack:
            self.ul_stack.pop()


def test_dag_view_has_three_nodes_and_two_edges(tmp_path):
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(_graph(), out_dir)

    index = Path(out_dir) / "index.html"
    assert index.is_file()
    collector = _ListCollector()
    collector.feed(index.read_text(encoding="utf-8"))
    collector.close()

    node_items = [
        attrs for parent, classes, attrs in collector.items
        if parent == "nodes" and "node" in classes
    ]
    edge_items = [
        attrs for parent, classes, attrs in collector.items
        if parent == "edges" and "edge" in classes
    ]

    assert len(node_items) == 3
    assert len(edge_items) == 2

    assert [(a.get("data-id"), a.get("data-type")) for a in node_items] == sorted(
        [
            ("P-ALPHA", "capability"),
            ("comp-alpha", "component"),
            ("VAR-ALPHA", "var"),
        ]
    )
    assert [
        (a.get("data-from"), a.get("data-to"), a.get("data-kind")) for a in edge_items
    ] == [
        ("comp-alpha", "P-ALPHA", "realizes"),
        ("comp-alpha", "VAR-ALPHA", "uses_var"),
    ]

    # No other node/edge list items anywhere on the page.
    all_nodes = [1 for _, classes, _a in collector.items if "node" in classes]
    all_edges = [1 for _, classes, _a in collector.items if "edge" in classes]
    assert len(all_nodes) == 3
    assert len(all_edges) == 2
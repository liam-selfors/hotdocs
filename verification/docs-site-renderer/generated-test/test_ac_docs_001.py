# hotdocs-criterion: sha256:76b7ab96e152a76965e69967e68d704777a9f76ff85dd58e8699234b6eb090f3
"""AC-DOCS-001: a corpus graph with three nodes and two edges renders a DAG
view holding three node elements and two edge elements (R-DOCS-001)."""

import dataclasses
import json
from pathlib import Path

import docs_site_renderer


@dataclasses.dataclass
class FakeCorpusGraph:
    """Same attribute shape as corpus-graph-builder's CorpusGraph dataclass."""

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
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
            + "\n"
        ).encode("utf-8")


def _three_node_two_edge_graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-beta": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {},
        },
        "VAR-GAMMA": {"type": "var"},
    }
    edges = [
        {"from": "comp-beta", "to": "P-ALPHA", "kind": "realizes"},
        {"from": "comp-beta", "to": "VAR-GAMMA", "kind": "uses_var"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return FakeCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def test_ac_docs_001_dag_view_has_three_nodes_and_two_edges(tmp_path, browser):
    graph = _three_node_two_edge_graph()
    out_dir = tmp_path / "site"

    docs_site_renderer.render_docs_site(graph, out_dir)

    index = out_dir / "index.html"
    assert index.is_file()

    page = browser.open(index)

    assert page.find(css="#nodes .node").count() == 3
    assert page.find(css="#edges .edge").count() == 2

    for node_id, node_type in (
        ("P-ALPHA", "capability"),
        ("comp-beta", "component"),
        ("VAR-GAMMA", "var"),
    ):
        selector = (
            '#nodes li.node[data-id="' + node_id + '"][data-type="' + node_type + '"]'
        )
        assert page.find(css=selector).count() == 1, selector

    for frm, to, kind in (
        ("comp-beta", "P-ALPHA", "realizes"),
        ("comp-beta", "VAR-GAMMA", "uses_var"),
    ):
        selector = (
            '#edges li.edge[data-from="'
            + frm
            + '"][data-to="'
            + to
            + '"][data-kind="'
            + kind
            + '"]'
        )
        assert page.find(css=selector).count() == 1, selector

    assert page.find(css="svg#dag").count() == 1
    assert page.console_errors() == []
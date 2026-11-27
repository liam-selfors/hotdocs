# hotdocs-criterion: sha256:1529e1c2adab9cfdde0afac4d9e486ac9983e9cb6b71b8afd35a247b73ae128c
"""AC-DOCS-001: a corpus graph with three nodes and two edges renders a DAG
view holding three node elements and two edge elements (R-DOCS-001)."""

import json
from dataclasses import dataclass, field as dc_field
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


@dataclass
class CorpusGraph:
    """Same shape as corpus-graph-builder's documented CorpusGraph."""

    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

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


def make_graph():
    nodes = {
        "P-X": {"type": "capability"},
        "VAR-Y": {"type": "var"},
        "comp-a": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": "---\nid: comp-a\ntitle: A\nstatus: draft\n"
                "owners: [pipeline-team]\n---\n\n# A\n",
            },
        },
    }
    edges = [
        {"from": "comp-a", "to": "P-X", "kind": "realizes"},
        {"from": "comp-a", "to": "VAR-Y", "kind": "uses_var"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


class DagParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ul_stack = []
        self.nodes = []
        self.edges = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "ul":
            self.ul_stack.append(a.get("id"))
        elif tag == "li":
            classes = (a.get("class") or "").split()
            inside = self.ul_stack[-1] if self.ul_stack else None
            if inside == "nodes" and "node" in classes:
                self.nodes.append((a.get("data-id"), a.get("data-type")))
            if inside == "edges" and "edge" in classes:
                self.edges.append(
                    (a.get("data-from"), a.get("data-to"), a.get("data-kind"))
                )

    def handle_endtag(self, tag):
        if tag == "ul" and self.ul_stack:
            self.ul_stack.pop()


def render(tmp_path):
    out_dir = tmp_path
    docs_site_renderer.render_docs_site(make_graph(), out_dir)
    index = out_dir / "index.html"
    assert index.is_file()
    return index


def test_dag_view_has_three_nodes_and_two_edges(tmp_path):
    index = render(tmp_path)
    parser = DagParser()
    parser.feed(index.read_text(encoding="utf-8"))
    parser.close()

    assert len(parser.nodes) == 3
    assert len(parser.edges) == 2
    assert parser.nodes == [
        ("P-X", "capability"),
        ("VAR-Y", "var"),
        ("comp-a", "component"),
    ]
    assert parser.edges == [
        ("comp-a", "P-X", "realizes"),
        ("comp-a", "VAR-Y", "uses_var"),
    ]


def test_dag_view_counts_in_browser(tmp_path, browser):
    index = render(tmp_path)
    page = browser.open(index)
    assert page.find(css="#nodes .node").count() == 3
    assert page.find(css="#edges .edge").count() == 2
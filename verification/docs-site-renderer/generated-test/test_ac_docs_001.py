# hotdocs-criterion: sha256:28a8efb40db58c6ab430fdff6d4853522493d53e866186b969e525bc8d3fff11
import docs_site_renderer

import dataclasses
import json
from html.parser import HTMLParser
from pathlib import Path


@dataclasses.dataclass
class StandInCorpusGraph:
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


class DagParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ul_stack = []
        self.node_items = []
        self.edge_items = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "ul":
            self.ul_stack.append(attrs.get("id"))
            return
        if tag == "li" and self.ul_stack:
            classes = (attrs.get("class") or "").split()
            current = self.ul_stack[-1]
            if current == "nodes" and "node" in classes:
                self.node_items.append(attrs)
            elif current == "edges" and "edge" in classes:
                self.edge_items.append(attrs)

    def handle_endtag(self, tag):
        if tag == "ul" and self.ul_stack:
            self.ul_stack.pop()


def make_graph():
    nodes = {
        "P-ZERO-EDIT": {"type": "capability"},
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {"component.md": "# Foo\n"},
        },
        "VAR-FOO-URL": {"type": "var"},
    }
    edges = [
        {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return StandInCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def test_ac_docs_001_dag_view_has_three_nodes_and_two_edges(tmp_path):
    graph = make_graph()
    out_dir = tmp_path / "site"
    out_dir.mkdir()

    docs_site_renderer.render_docs_site(graph, out_dir)

    index = Path(out_dir) / "index.html"
    assert index.is_file()
    html_text = index.read_text(encoding="utf-8")

    parser = DagParser()
    parser.feed(html_text)
    parser.close()

    assert len(parser.node_items) == 3
    assert len(parser.edge_items) == 2

    assert [item.get("data-id") for item in parser.node_items] == sorted(
        ["P-ZERO-EDIT", "comp-foo", "VAR-FOO-URL"]
    )
    assert [
        (item.get("data-from"), item.get("data-to"), item.get("data-kind"))
        for item in parser.edge_items
    ] == [
        ("comp-foo", "P-ZERO-EDIT", "realizes"),
        ("comp-foo", "VAR-FOO-URL", "uses_var"),
    ]
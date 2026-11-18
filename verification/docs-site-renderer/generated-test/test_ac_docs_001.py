# hotdocs-criterion: sha256:d80361d3ad408411bbabfa7c7e3375afc88980f27e09626ddaf769954abe7e8a
"""AC-DOCS-001: the DAG view holds three node elements and two edge elements
for a corpus graph with three nodes and two edges."""

import json
from dataclasses import dataclass, field as dc_field
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


NODE_IDS = ["comp-alpha", "P-BETA-CAP", "VAR-GAMMA-URL"]
EXPECTED_EDGES = {
    frozenset(("comp-alpha", "P-BETA-CAP")),
    frozenset(("comp-alpha", "VAR-GAMMA-URL")),
}

VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}
SKIP_TAGS = {"script", "style", "template", "noscript"}


@dataclass
class FakeCorpusGraph:
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

    def __getitem__(self, key):
        return self.to_dict()[key]


def make_graph():
    nodes = {
        "comp-alpha": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["docs-team"],
            "documents": {
                "component.md": "---\nid: comp-alpha\ntitle: Alpha\nstatus: draft\n---\n\n# Alpha\n\nA component.\n",
            },
        },
        "P-BETA-CAP": {"type": "capability"},
        "VAR-GAMMA-URL": {"type": "var"},
    }
    edges = [
        {"from": "comp-alpha", "to": "P-BETA-CAP", "kind": "realizes"},
        {"from": "comp-alpha", "to": "VAR-GAMMA-URL", "kind": "uses_var"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return FakeCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def ids_in(text):
    return {nid for nid in NODE_IDS if nid in text}


class ElementCollector(HTMLParser):
    """Collects, per element, its attribute values plus its own direct text
    (excluding script/style content)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.elements = []
        self.skip_depth = 0

    def _finish(self, entry):
        self.elements.append(entry)

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self.skip_depth += 1
            self.stack.append({"tag": tag, "text": [], "attrs": [], "skip": True})
            return
        attr_text = [v for _, v in attrs if v]
        entry = {"tag": tag, "text": [], "attrs": attr_text, "skip": False}
        if tag in VOID_TAGS:
            self._finish(entry)
            return
        self.stack.append(entry)

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        attr_text = [v for _, v in attrs if v]
        self._finish({"tag": tag, "text": [], "attrs": attr_text, "skip": False})

    def handle_endtag(self, tag):
        tag = tag.lower()
        if not any(e["tag"] == tag for e in self.stack):
            return
        while self.stack:
            entry = self.stack.pop()
            if entry["skip"]:
                self.skip_depth -= 1
            else:
                self._finish(entry)
            if entry["tag"] == tag:
                break

    def handle_data(self, data):
        if self.skip_depth > 0 or not self.stack:
            return
        self.stack[-1]["text"].append(data)

    def close(self):
        super().close()
        while self.stack:
            entry = self.stack.pop()
            if not entry["skip"]:
                self._finish(entry)


def analyse_page(html_text):
    parser = ElementCollector()
    parser.feed(html_text)
    parser.close()
    node_ids = set()
    edge_pairs = set()
    for entry in parser.elements:
        blob = " ".join(entry["attrs"]) + " " + "".join(entry["text"])
        found = ids_in(blob)
        if len(found) == 1:
            node_ids |= found
        elif len(found) == 2:
            edge_pairs.add(frozenset(found))
    return node_ids, edge_pairs


def test_ac_docs_001_dag_view_has_three_nodes_and_two_edges(tmp_path):
    graph = make_graph()
    out_dir = tmp_path / "site"

    result = docs_site_renderer.render_docs_site(graph, out_dir)
    assert result is None

    assert out_dir.is_dir(), "render_docs_site did not create the output directory"
    pages = sorted(
        p for p in out_dir.rglob("*") if p.is_file() and p.suffix.lower() in (".html", ".htm")
    )
    assert pages, "no HTML pages were rendered"

    summaries = []
    matching = []
    for page in pages:
        text = page.read_text(encoding="utf-8", errors="replace")
        node_ids, edge_pairs = analyse_page(text)
        summaries.append((str(page.relative_to(out_dir)), sorted(node_ids),
                          sorted(sorted(p) for p in edge_pairs)))
        if node_ids == set(NODE_IDS) and edge_pairs == EXPECTED_EDGES:
            matching.append(page)

    assert matching, (
        "no rendered page is a DAG view holding exactly the three node elements "
        "and the two edge elements; per-page findings: " + repr(summaries)
    )
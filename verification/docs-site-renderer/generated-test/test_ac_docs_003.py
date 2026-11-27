# hotdocs-criterion: sha256:52893afaeb4966aee811418bcc97f7c8d3244a137883b369e473fb1945a1f4b4
"""AC-DOCS-003: the corpus-health dashboard displays corpus-graph.json's
aggregates values exactly (R-DOCS-003)."""

import json
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


AGGREGATES = {
    "orphan_capability_rate": 0.375,
    "orphan_component_rate": 0.625,
    "orphan_var_rate": 0.125,
}


class FakeCorpusGraph:
    """Duck-typed stand-in carrying CorpusGraph's documented attributes."""

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


def make_graph():
    nodes = {
        "P-HEALTH-DEMO": {"type": "capability"},
        "comp-alpha": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": "---\nid: comp-alpha\ntitle: Alpha\nstatus: draft\nowners: [pipeline-team]\n---\n\n# Alpha\n",
            },
        },
        "comp-beta": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": True,
            "pinned_overrides": [],
            "owners": [],
            "documents": {},
        },
        "VAR-DEMO-URL": {"type": "var"},
    }
    edges = [
        {"from": "comp-alpha", "to": "VAR-DEMO-URL", "kind": "uses_var"},
        {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
    ]
    return FakeCorpusGraph(nodes, edges, dict(AGGREGATES))


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("style", "script") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def visible_text(html_text):
    parser = _VisibleText()
    parser.feed(html_text)
    parser.close()
    return " ".join(parser.parts)


def test_dashboard_displays_exact_aggregate_values(tmp_path):
    out_dir = tmp_path / "site"
    graph = make_graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    pages = sorted(out_dir.rglob("*.html"))
    assert pages, "render_docs_site wrote no HTML pages"

    expected = [repr(v) for v in AGGREGATES.values()]

    dashboard_pages = []
    for page in pages:
        text = visible_text(page.read_text(encoding="utf-8"))
        if all(value in text for value in expected):
            dashboard_pages.append(page)

    assert dashboard_pages, (
        "no rendered page shows all aggregate values "
        + repr(expected)
        + " as visible text; pages: "
        + repr([str(p.relative_to(out_dir)) for p in pages])
    )
# hotdocs-criterion: sha256:4619ba6abc075a3407ef66f503fa223b2025a889e7a81ea59151c38df9d047b7
"""AC-DOCS-003: the dashboard view displays corpus-graph.json's aggregates exactly."""

import dataclasses
import json
from pathlib import Path

import docs_site_renderer


@dataclasses.dataclass
class CorpusGraph:
    """Stand-in matching corpus-graph-builder's documented CorpusGraph shape."""

    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {"component.md": "# comp-foo\n\nA component.\n"},
        },
        "VAR-FOO-URL": {"type": "var"},
    }
    edges = []
    aggregates = {
        "orphan_capability_rate": 0.25,
        "orphan_component_rate": 0.5,
        "orphan_var_rate": 0.125,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def test_ac_docs_003_dashboard_displays_exact_aggregate_values(tmp_path, browser):
    graph = _graph()
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(graph, out_dir)

    expected = [repr(v) for v in graph.aggregates.values()]  # "0.25", "0.5", "0.125"

    pages = sorted(out_dir.rglob("*.html"))
    assert pages, "render_docs_site wrote no HTML pages"

    shown = {}
    for page_path in pages:
        page = browser.open(page_path)
        text = page.find(css="body").text()
        shown[page_path] = (text, page.console_errors())

    dashboards = [
        p for p, (text, _errors) in shown.items() if all(v in text for v in expected)
    ]
    assert dashboards, (
        "no rendered page displays every aggregate value "
        + repr(expected)
        + "; pages: "
        + repr([str(p.relative_to(out_dir)) for p in pages])
    )
    for p in dashboards:
        assert shown[p][1] == []
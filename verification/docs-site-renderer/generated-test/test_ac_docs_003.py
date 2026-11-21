# hotdocs-criterion: sha256:d9e1b8ccb752110ca4d8e5dcff89d49c411e904eeb388e0f124f97a293a44a54
import json
import re
from pathlib import Path

import docs_site_renderer


class FakeCorpusGraph:
    """Stand-in matching CorpusGraph's documented shape: attributes
    nodes/edges/aggregates, to_dict() and to_json_bytes()."""

    def __init__(self, nodes, edges, aggregates):
        self.nodes = nodes
        self.edges = edges
        self.aggregates = aggregates

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)


AGGREGATES = {
    "orphan_capability_rate": 0.375,
    "orphan_component_rate": 0.625,
    "orphan_var_rate": 0.875,
}


def _graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-alpha": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {"component.md": "# Alpha\n\nAlpha component.\n"},
        },
        "comp-beta": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {"component.md": "# Beta\n"},
        },
        "VAR-ALPHA-URL": {"type": "var"},
    }
    edges = [
        {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
        {"from": "comp-alpha", "to": "VAR-ALPHA-URL", "kind": "uses_var"},
        {"from": "comp-beta", "to": "comp-alpha", "kind": "depends_on"},
    ]
    return FakeCorpusGraph(nodes, edges, dict(AGGREGATES))


def _contains_number(text, value):
    pattern = r"(?<![\d.])" + re.escape(repr(value)) + r"(?![\d])"
    return re.search(pattern, text) is not None


def test_ac_docs_003_dashboard_displays_exact_aggregate_values(tmp_path):
    out_dir = tmp_path / "site"
    graph = _graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    assert out_dir.is_dir()
    pages = sorted(p for p in out_dir.rglob("*") if p.is_file() and p.suffix in (".html", ".htm"))
    assert pages, "render_docs_site wrote no HTML pages"

    dashboard_pages = []
    for page in pages:
        text = page.read_text(encoding="utf-8")
        if all(_contains_number(text, v) for v in AGGREGATES.values()):
            dashboard_pages.append(page)

    assert dashboard_pages, (
        "no rendered page displays all aggregate values "
        + repr(sorted(AGGREGATES.values()))
    )
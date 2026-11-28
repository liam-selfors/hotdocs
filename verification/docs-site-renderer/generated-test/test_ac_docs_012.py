# hotdocs-criterion: sha256:bef49ba74c5cfdac7084c5ad35056a4e2d337b7f75c2ee7062431a8636b9d720
"""AC-DOCS-012: typing in the DAG view's search field hides non-matching nodes;
clearing it shows every node again (R-DOCS-009)."""

from dataclasses import dataclass, field as dc_field
import json

import docs_site_renderer


@dataclass
class CorpusGraph:
    """Stand-in with the documented CorpusGraph shape (interface/data/CorpusGraph.md)."""

    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _component_node(slug):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "unknown",
        "sealed": False,
        "pinned_overrides": [],
        "owners": [],
        "documents": {"component.md": "# " + slug + "\n"},
    }


def _graph():
    return CorpusGraph(
        nodes={
            "P-ALPHA": {"type": "capability"},
            "comp-alpha": _component_node("comp-alpha"),
            "comp-beta": _component_node("comp-beta"),
        },
        edges=[
            {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
            {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
        ],
        aggregates={
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    )


def _read(value):
    return value() if callable(value) else value


def _visible(page, node_id):
    el = page.find(css='li.node[data-id="' + node_id + '"]')
    return bool(_read(el.visible))


IDS = ["comp-alpha", "comp-beta", "P-ALPHA"]


def test_ac_docs_012_search_filters_nodes(browser, tmp_path):
    docs_site_renderer.render_docs_site(_graph(), tmp_path)

    page = browser.open(tmp_path / "index.html")
    assert _read(page.find(css="li.node").count) == 3

    search = page.find(css="#search")
    search.fill("beta")
    assert {i: _visible(page, i) for i in IDS} == {
        "comp-alpha": False,
        "comp-beta": True,
        "P-ALPHA": False,
    }

    search.fill("")
    assert {i: _visible(page, i) for i in IDS} == {
        "comp-alpha": True,
        "comp-beta": True,
        "P-ALPHA": True,
    }

    assert page.console_errors() == []
    assert page.blocked_requests() == []
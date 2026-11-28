# hotdocs-criterion: sha256:34698f4b3e8914b4b263d1893c8449f6ce4f9d8cf474201c23b1e724ecabd066
"""AC-DOCS-012 (covers R-DOCS-009): the DAG view's search field filters nodes."""

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
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "aggregates": self.aggregates,
        }

    def to_json_bytes(self):
        text = json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
        return (text + "\n").encode("utf-8")


def _component_node(component_id):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {
            "component.md": "# " + component_id + "\n\nA test component.\n",
        },
    }


def _build_graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-alpha": _component_node("comp-alpha"),
        "comp-beta": _component_node("comp-beta"),
    }
    edges = sorted(
        [
            {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
            {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
        ],
        key=lambda e: (e["from"], e["to"], e["kind"]),
    )
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.5,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def _value(obj, name):
    attr = getattr(obj, name)
    return attr() if callable(attr) else attr


def _node_item(page, node_id):
    return page.find(css='li.node[data-id="' + node_id + '"]')


NODE_IDS = ["comp-alpha", "comp-beta", "P-ALPHA"]


def test_ac_docs_012_search_filters_nodes(browser, tmp_path):
    out_dir = tmp_path
    docs_site_renderer.render_docs_site(_build_graph(), out_dir)

    index = Path(out_dir) / "index.html"
    assert index.is_file()

    page = browser.open(index)

    assert _value(page.find(css="li.node"), "count") == 3

    search = page.find(css="#search")
    search.fill("beta")

    visible = {node_id: bool(_value(_node_item(page, node_id), "visible")) for node_id in NODE_IDS}
    assert visible == {"comp-alpha": False, "comp-beta": True, "P-ALPHA": False}

    search.fill("")

    visible = {node_id: bool(_value(_node_item(page, node_id), "visible")) for node_id in NODE_IDS}
    assert visible == {"comp-alpha": True, "comp-beta": True, "P-ALPHA": True}

    assert page.console_errors() == []
    assert page.blocked_requests() == []
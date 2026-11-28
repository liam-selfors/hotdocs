# hotdocs-criterion: sha256:e18fcebdca6eb1ce6e74398f22c5f24524b9b24fce1d92fbe5c96c72247e22c6
import re
from dataclasses import dataclass, field as dc_field
import json

import docs_site_renderer


@dataclass
class StandInCorpusGraph:
    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


def _component_node(slug):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "unknown",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {"component.md": "# " + slug + "\n\nA component.\n"},
    }


def _build_graph():
    nodes = {}
    nodes["P-ALPHA"] = {"type": "capability"}
    nodes["P-BETA"] = {"type": "capability"}
    nodes["comp-alpha"] = _component_node("comp-alpha")
    nodes["comp-beta"] = _component_node("comp-beta")
    nodes["VAR-X"] = {"type": "var"}
    edges = [
        {"from": "comp-alpha", "to": "P-BETA", "kind": "depends_on"},
        {"from": "comp-beta", "to": "P-ALPHA", "kind": "realizes"},
        {"from": "comp-beta", "to": "VAR-X", "kind": "uses_var"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.5,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return StandInCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


_RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def _parse_rgb(value):
    m = _RGB.search(value or "")
    assert m is not None, "not an rgb() value: " + repr(value)
    return tuple(int(g) for g in m.groups())


def _channel(v):
    c = v / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb):
    r, g, b = (_channel(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return round((lighter + 0.05) / (darker + 0.05), 2)


EDGE_SELECTORS = [
    "svg#dag line.edge-depends-on",
    "svg#dag line.edge-realizes",
    "svg#dag line.edge-other",
]


def _check_page(page):
    assert page.find(css="svg#dag line").count() == 3

    background = _parse_rgb(page.find(css="body").style("background-color"))

    strokes = []
    for selector in EDGE_SELECTORS:
        line = page.find(css=selector)
        assert line.count() == 1, selector
        assert line.attribute("stroke") is None, selector
        stroke = _parse_rgb(line.style("stroke"))
        strokes.append(stroke)
        ratio = _contrast(stroke, background)
        assert ratio >= 3, selector + " contrast " + repr(ratio)

    assert len(set(strokes)) == 3, repr(strokes)
    assert page.console_errors() == []


def test_ac_docs_015_edge_classes_colour_lines_with_contrast(browser, tmp_path):
    out_dir = tmp_path / "site"
    out_dir.mkdir()
    graph = _build_graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    index = out_dir / "index.html"
    assert index.is_file()

    light = browser.open(index)
    _check_page(light)

    dark = browser.open(index, color_scheme="dark")
    _check_page(dark)
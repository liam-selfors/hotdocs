# hotdocs-criterion: sha256:6de7d9de68cb40dd8ced1020e0ba862703097bfae2d9d7d42919c0c9459d9b55
"""AC-DOCS-011: index.html inlines static/app.js exactly once as the page's
only <script type="module"> element, followed by init(document); it holds the
search field, the empty DAG svg and one li.node per node sorted by id; no
other page carries a script."""

import dataclasses
import json
from html.parser import HTMLParser
from pathlib import Path

import docs_site_renderer


@dataclasses.dataclass
class CorpusGraph:
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


def _graph():
    nodes = {
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {"component.md": "# Foo\n\nThe foo component.\n"},
        },
        "P-FOO": {"type": "capability"},
    }
    edges = [{"from": "comp-foo", "to": "P-FOO", "kind": "realizes"}]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def _asset_text():
    init_file = Path(docs_site_renderer.__file__).resolve()
    asset = init_file.parent.parent / "static" / "app.js"
    return asset.read_text(encoding="utf-8")


def test_ac_docs_011(tmp_path):
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(_graph(), out_dir)

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    # Exactly one script element, and it is <script type="module">.
    assert html.count("<script") == 1
    opening = '<script type="module">'
    assert html.count(opening) == 1
    start = html.index(opening) + len(opening)
    end = html.index("</script>", start)
    script_text = html[start:end]

    asset_text = _asset_text()
    assert script_text == asset_text + "\ninit(document);\n"

    # Structural elements.
    collector = _Collector()
    collector.feed(html)
    collector.close()
    elements = collector.elements

    assert any(attrs.get("id") == "search" for _tag, attrs in elements)
    assert any(
        tag == "svg" and attrs.get("id") == "dag" for tag, attrs in elements
    )

    node_ids = [
        attrs.get("data-id")
        for tag, attrs in elements
        if tag == "li" and "node" in (attrs.get("class") or "").split()
    ]
    assert node_ids == ["P-FOO", "comp-foo"]

    # No other page carries a script.
    others = [p for p in out_dir.rglob("*.html") if p.resolve() != index.resolve()]
    assert others, "expected detail and dashboard pages besides index.html"
    for page in others:
        text = page.read_text(encoding="utf-8")
        assert "<script" not in text, str(page)
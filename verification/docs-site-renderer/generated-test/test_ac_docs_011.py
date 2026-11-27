# hotdocs-criterion: sha256:168e92cb861227108467d341a28af4d613934a35693ef7bb6c52eec7a81518cb
"""AC-DOCS-011 (covers R-DOCS-001): index.html inlines static/app.js exactly
once as <script type="module"> + asset text + "\\ninit(document);\\n", holds
#search, svg#dag and one li.node per node sorted by id, and no other page
carries a script."""

from dataclasses import dataclass, field as dc_field
from html.parser import HTMLParser
from pathlib import Path
import json

import docs_site_renderer


@dataclass
class CorpusGraph:
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


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def _graph():
    nodes = {
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {},
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


def test_ac_docs_011_index_inlines_app_js_once(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    docs_site_renderer.render_docs_site(_graph(), out_dir)

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")

    # Exactly one "<script", and it is <script type="module">.
    assert html.count("<script") == 1
    open_tag = '<script type="module">'
    start = html.find("<script")
    assert html[start:start + len(open_tag)] == open_tag

    # Element text is exactly the asset's text + "\ninit(document);\n".
    asset_path = (
        Path(docs_site_renderer.__file__).parent.parent / "static" / "app.js"
    )
    asset_text = asset_path.read_text(encoding="utf-8")
    body_start = start + len(open_tag)
    body_end = html.find("</script>", body_start)
    assert body_end != -1
    assert html[body_start:body_end] == asset_text + "\ninit(document);\n"

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

    # No other .html file under out_dir carries a script.
    index_resolved = index.resolve()
    for page in out_dir.rglob("*.html"):
        if page.resolve() == index_resolved:
            continue
        assert "<script" not in page.read_text(encoding="utf-8"), str(page)
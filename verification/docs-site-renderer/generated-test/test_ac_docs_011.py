# hotdocs-criterion: sha256:800c13abc2ae0c0a018891fa3a01ace5fdc76eea8f099c755cac4c86952ed722
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


class _TagCollector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag.lower(), dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag.lower(), dict(attrs)))


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
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(_graph(), out_dir)

    index_path = out_dir / "index.html"
    assert index_path.is_file()
    html = index_path.read_text(encoding="utf-8")

    # Exactly one "<script", as <script type="module">.
    assert html.count("<script") == 1
    start = html.index("<script")
    opening = '<script type="module">'
    assert html[start:].startswith(opening)
    body_start = start + len(opening)
    end = html.find("</script>", body_start)
    assert end != -1
    script_text = html[body_start:end]

    asset_path = (
        Path(docs_site_renderer.__file__).resolve().parent.parent
        / "static"
        / "app.js"
    )
    asset_text = asset_path.read_text(encoding="utf-8")
    assert script_text == asset_text + "\ninit(document);\n"

    # Structural elements.
    collector = _TagCollector()
    collector.feed(html)
    collector.close()
    tags = collector.tags

    assert any(attrs.get("id") == "search" for _, attrs in tags)
    assert any(tag == "svg" and attrs.get("id") == "dag" for tag, attrs in tags)

    node_items = [
        attrs
        for tag, attrs in tags
        if tag == "li" and "node" in (attrs.get("class") or "").split()
    ]
    assert [attrs.get("data-id") for attrs in node_items] == ["P-FOO", "comp-foo"]

    # No other page carries a script.
    other_pages = [
        p for p in out_dir.rglob("*.html") if p.resolve() != index_path.resolve()
    ]
    for page in other_pages:
        assert "<script" not in page.read_text(encoding="utf-8"), str(page)
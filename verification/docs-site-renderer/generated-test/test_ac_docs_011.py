# hotdocs-criterion: sha256:dec5151bd8d7ef3c84d13c0787e17e20ab5444297f10d4c3e079d820d11df8cb
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


def make_graph():
    nodes = {
        "P-FOO": {"type": "capability"},
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": "---\nid: comp-foo\ntitle: Foo\nstatus: draft\n"
                "owners: [pipeline-team]\n---\n\n# Foo\n",
            },
        },
    }
    edges = [{"from": "comp-foo", "to": "P-FOO", "kind": "realizes"}]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


class Collector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.starts = []

    def handle_starttag(self, tag, attrs):
        self.starts.append((tag, dict(attrs)))

    def handle_startendtag(self, tag, attrs):
        self.starts.append((tag, dict(attrs)))


def test_ac_docs_011(tmp_path):
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(make_graph(), out_dir)

    index = out_dir / "index.html"
    assert index.is_file()
    page = index.read_text(encoding="utf-8")

    asset = (
        Path(docs_site_renderer.__file__).resolve().parent.parent
        / "static"
        / "app.js"
    )
    a_text = asset.read_text(encoding="utf-8")

    assert page.count("<script") == 1
    opener = '<script type="module">'
    assert page.count(opener) == 1
    start = page.index(opener) + len(opener)
    end = page.index("</script>", start)
    assert page[start:end] == a_text + "\ninit(document);\n"

    collector = Collector()
    collector.feed(page)
    collector.close()
    starts = collector.starts

    assert any(attrs.get("id") == "search" for _tag, attrs in starts)
    assert any(tag == "svg" and attrs.get("id") == "dag" for tag, attrs in starts)

    node_ids = [
        attrs.get("data-id")
        for tag, attrs in starts
        if tag == "li" and "node" in (attrs.get("class") or "").split()
    ]
    assert node_ids == ["P-FOO", "comp-foo"]

    for html_file in out_dir.rglob("*.html"):
        if html_file.resolve() == index.resolve():
            continue
        text = html_file.read_text(encoding="utf-8")
        assert "<script" not in text, str(html_file)
# hotdocs-criterion: sha256:a5745e7cb5bc07343a4b8772ec2177928dcb295cdf67491dc146808dd15f38e1
"""AC-DOCS-008: detail views HTML-escape document text and tolerate null/empty fields."""

import dataclasses
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import docs_site_renderer


RAW = "<script>alert(1)</script>"
DOC_TEXT = "<script>alert(1)</script> & more"


@dataclasses.dataclass
class FakeCorpusGraph:
    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


class _NodeLinkParser(HTMLParser):
    """Collects, for each `#nodes .node` list item, the href of its first `a`."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = {}
        self._current_id = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "li" and "node" in classes and attrs.get("data-id") is not None:
            self._current_id = attrs.get("data-id")
            return
        if tag == "a" and self._current_id is not None:
            href = attrs.get("href")
            if href is not None and self._current_id not in self.links:
                self.links[self._current_id] = href

    def handle_endtag(self, tag):
        if tag == "li":
            self._current_id = None


def _component_node(documents, verification, provenance, owners):
    return {
        "type": "component",
        "verification": verification,
        "provenance": provenance,
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": owners,
        "documents": documents,
    }


def _detail_page(out_dir, index_text, node_id):
    parser = _NodeLinkParser()
    parser.feed(index_text)
    parser.close()
    assert node_id in parser.links, "no detail link for " + node_id + " in index.html"
    href = parser.links[node_id]
    path_part = unquote(urlsplit(href).path)
    page = (Path(out_dir) / path_part).resolve()
    if page.is_dir():
        page = page / "index.html"
    assert page.is_file(), "detail page for " + node_id + " not found at " + str(page)
    return page


def test_ac_docs_008_escaping_and_null_fields(tmp_path):
    first_id = "comp-alpha"
    second_id = "comp-beta"
    nodes = {
        first_id: _component_node(
            documents={"component.md": DOC_TEXT},
            verification=None,
            provenance=None,
            owners=["pipeline-team"],
        ),
        second_id: _component_node(
            documents={"component.md": "# Beta\n\nPlain text.\n"},
            verification=None,
            provenance=None,
            owners=[],
        ),
    }
    edges = [{"from": first_id, "to": second_id, "kind": "depends_on"}]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    graph = FakeCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)

    out_dir = tmp_path / "site"
    # Must not raise, including for the second node's null/empty fields.
    docs_site_renderer.render_docs_site(graph, out_dir)

    index = out_dir / "index.html"
    assert index.is_file()
    index_text = index.read_text(encoding="utf-8")

    first_page = _detail_page(out_dir, index_text, first_id)
    first_text = first_page.read_text(encoding="utf-8")
    assert "&lt;script&gt;" in first_text
    assert "&amp; more" in first_text
    assert RAW not in first_text

    second_page = _detail_page(out_dir, index_text, second_id)
    assert second_page != first_page
    second_text = second_page.read_text(encoding="utf-8")
    assert second_text.strip() != ""
    assert second_id in second_text
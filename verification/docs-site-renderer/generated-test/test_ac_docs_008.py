# hotdocs-criterion: sha256:87aeb15e62726e914e0ee6171e2485e51d1feef4b038b742566c42d0d26796bd
"""AC-DOCS-008: document text is HTML-escaped in a detail view, and a
component node with null verification/provenance and empty owners renders
without error."""

import dataclasses
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import docs_site_renderer


XSS_TEXT = "<script>alert(1)</script> & more"
RAW_SCRIPT = "<script>alert(1)</script>"


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
    """Collects, for each `#nodes .node` list item, its data-id and the
    href of the first `a` inside it."""

    def __init__(self):
        super().__init__()
        self.links = {}
        self._stack = []  # list of (tag, node_id or None)
        self._current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "li" and "node" in classes and attrs.get("data-id") is not None:
            self._current = attrs.get("data-id")
            self._stack.append((tag, self._current))
            return
        if tag == "a" and self._current is not None and self._current not in self.links:
            href = attrs.get("href")
            if href is not None:
                self.links[self._current] = href

    def handle_endtag(self, tag):
        if tag == "li" and self._stack:
            self._stack.pop()
            self._current = self._stack[-1][1] if self._stack else None


def _detail_page(out_dir, node_id):
    index = out_dir / "index.html"
    assert index.is_file(), "index.html was not written"
    parser = _NodeLinkParser()
    parser.feed(index.read_text(encoding="utf-8"))
    assert node_id in parser.links, "no detail link found for " + repr(node_id)
    href = parser.links[node_id]
    path_part = unquote(urlsplit(href).path)
    if path_part == "":
        target = index
    else:
        target = (index.parent / path_part).resolve()
    assert target.is_file(), "detail page " + repr(str(target)) + " does not exist"
    return target.read_text(encoding="utf-8")


def _graph():
    nodes = {
        "comp-xss": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": XSS_TEXT,
                "requirements/R-XSS-001.md": "# R-XSS-001\n\n" + XSS_TEXT + "\n",
            },
        },
        "comp-bare": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {"component.md": "# Bare\n\nNothing else.\n"},
        },
    }
    edges = []
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 1.0,
        "orphan_var_rate": 0.0,
    }
    return FakeCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def test_ac_docs_008_escapes_document_text_and_renders_null_fields(tmp_path):
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(_graph(), out_dir)

    first = _detail_page(out_dir, "comp-xss")
    assert "&lt;script&gt;" in first
    assert "&amp; more" in first
    assert RAW_SCRIPT not in first

    second = _detail_page(out_dir, "comp-bare")
    assert second.strip() != ""
    assert RAW_SCRIPT not in second
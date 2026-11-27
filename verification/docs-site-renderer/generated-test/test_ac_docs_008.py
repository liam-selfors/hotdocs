# hotdocs-criterion: sha256:995e56aee22978226260b99e33a9cd01729ab42bbf4e00003cc2423df00defc7
import json
from dataclasses import dataclass, field as dc_field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote

import docs_site_renderer


RAW_SCRIPT = "<script>alert(1)</script>"
DOC_TEXT = RAW_SCRIPT + " & more"

VOID_TAGS = (
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
)


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


class NodeLinkParser(HTMLParser):
    """Collects, for each `.node` item with `data-id`, the href of the `a` inside it."""

    def __init__(self):
        super().__init__()
        self.links = {}
        self._stack = []  # entries: (tag, node_id or None)
        self._current_node = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        node_id = None
        if "node" in classes and attrs.get("data-id") is not None:
            node_id = attrs.get("data-id")
            self._current_node = node_id
        if tag == "a" and self._current_node is not None:
            href = attrs.get("href")
            if href is not None and self._current_node not in self.links:
                self.links[self._current_node] = href
        if tag not in VOID_TAGS:
            self._stack.append((tag, node_id))

    def handle_startendtag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "a" and self._current_node is not None:
            href = attrs_dict.get("href")
            if href is not None and self._current_node not in self.links:
                self.links[self._current_node] = href

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if not any(t == tag for t, _ in self._stack):
            return
        while self._stack:
            t, _nid = self._stack.pop()
            if t == tag:
                break
        self._current_node = None
        for _t, nid in reversed(self._stack):
            if nid is not None:
                self._current_node = nid
                break


def _component_node(documents, verification, provenance, owners):
    return {
        "type": "component",
        "verification": verification,
        "provenance": provenance,
        "size_status": "unknown",
        "sealed": False,
        "pinned_overrides": [],
        "owners": owners,
        "documents": documents,
    }


def _detail_page(out_dir, index_text, node_id):
    parser = NodeLinkParser()
    parser.feed(index_text)
    parser.close()
    assert node_id in parser.links, "no detail link for " + node_id
    href = parser.links[node_id]
    parts = urlsplit(href)
    path_part = unquote(parts.path)
    if path_part == "":
        target = out_dir / "index.html"
    else:
        target = (out_dir / path_part).resolve()
    if target.is_dir():
        target = target / "index.html"
    assert target.is_file(), "detail page missing: " + str(target)
    return target.read_text(encoding="utf-8")


def test_ac_docs_008(tmp_path):
    graph = CorpusGraph(
        nodes={
            "comp-alpha": _component_node(
                documents={"component.md": DOC_TEXT},
                verification=None,
                provenance=None,
                owners=["pipeline-team"],
            ),
            "comp-beta": _component_node(
                documents={"component.md": "Beta component text."},
                verification=None,
                provenance=None,
                owners=[],
            ),
        },
        edges=[],
        aggregates={
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    )

    out_dir = tmp_path / "site"
    out_dir.mkdir()

    # Must render without raising, including for the null/empty second node.
    docs_site_renderer.render_docs_site(graph, out_dir)

    index = out_dir / "index.html"
    assert index.is_file()
    index_text = index.read_text(encoding="utf-8")

    alpha_text = _detail_page(out_dir, index_text, "comp-alpha")
    assert "&lt;script&gt;" in alpha_text
    assert "&amp; more" in alpha_text
    assert RAW_SCRIPT not in alpha_text

    beta_text = _detail_page(out_dir, index_text, "comp-beta")
    assert beta_text.strip() != ""
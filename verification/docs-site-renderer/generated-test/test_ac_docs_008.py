# hotdocs-criterion: sha256:6e9162afd94ee40faa6f31c50d567f5f482d7f2dab350cf1ee0096a2d405020b
import importlib.util
import sys
from dataclasses import dataclass, field as dc_field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import json

import docs_site_renderer


RAW = "<script>alert(1)</script>"
DOC_TEXT = RAW + " & more"


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class _StandInCorpusGraph:
    nodes: dict = dc_field(default_factory=dict)
    edges: list = dc_field(default_factory=list)
    aggregates: dict = dc_field(default_factory=dict)

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _make_graph(nodes, edges, aggregates):
    try:
        gen = next(
            p for p in Path(docs_site_renderer.__file__).resolve().parents if p.name == "gen"
        )
        base = gen / "corpus-graph-builder"
        flat = base / "corpus_graph_builder.py"
        path = flat if flat.is_file() else base / "corpus_graph_builder" / "__init__.py"
        module = load_module(path, "corpus_graph_builder")
        return module.CorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)
    except Exception:
        return _StandInCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


class _NodeLinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.links = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "li":
            classes = (a.get("class") or "").split()
            if "node" in classes and a.get("data-id") is not None:
                self.stack.append(a.get("data-id"))
            else:
                self.stack.append(None)
        elif tag == "a" and a.get("href"):
            current = next((s for s in reversed(self.stack) if s is not None), None)
            if current is not None and current not in self.links:
                self.links[current] = a.get("href")

    def handle_endtag(self, tag):
        if tag == "li" and self.stack:
            self.stack.pop()


def _detail_page_text(out_dir, node_id):
    index = out_dir / "index.html"
    candidates = []
    if index.is_file():
        parser = _NodeLinkParser()
        parser.feed(index.read_text(encoding="utf-8"))
        href = parser.links.get(node_id)
        if href:
            parts = urlsplit(href)
            rel = unquote(parts.path)
            if rel:
                target = (out_dir / rel.lstrip("/")) if not rel.startswith("/") else (out_dir / rel.lstrip("/"))
                if rel.endswith("/") or target.is_dir():
                    target = target / "index.html"
                candidates.append(target)
    for p in sorted(out_dir.rglob("*.html")):
        if p.name == "index.html" and p.parent == out_dir:
            continue
        if node_id in str(p.relative_to(out_dir)):
            candidates.append(p)
    for c in candidates:
        if c.is_file():
            return c.read_text(encoding="utf-8")
    raise AssertionError("no detail page found for " + node_id)


def test_ac_docs_008_escapes_content_and_tolerates_null_fields(tmp_path):
    nodes = {
        "comp-alpha": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {"component.md": DOC_TEXT},
        },
        "comp-beta": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {"component.md": "Beta component text."},
        },
    }
    edges = []
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    graph = _make_graph(nodes, edges, aggregates)
    out_dir = tmp_path / "site"

    result = docs_site_renderer.render_docs_site(graph, out_dir)
    assert result is None

    alpha = _detail_page_text(out_dir, "comp-alpha")
    assert "&lt;script&gt;" in alpha
    assert "&amp; more" in alpha
    assert RAW not in alpha

    for p in out_dir.rglob("*"):
        if p.is_file():
            text = p.read_bytes().decode("utf-8", errors="replace")
            assert RAW not in text, str(p)

    beta = _detail_page_text(out_dir, "comp-beta")
    assert isinstance(beta, str)
    assert len(beta) > 0
# hotdocs-criterion: sha256:2a046ac34cddc4fbf827975e9477a16afe43450c0855925e0b7f88229edcfb6d
import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import docs_site_renderer


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@dataclasses.dataclass
class _FallbackCorpusGraph:
    nodes: dict
    edges: list
    aggregates: dict

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _corpus_graph_class():
    try:
        gen = next(
            p for p in Path(docs_site_renderer.__file__).resolve().parents if p.name == "gen"
        )
    except StopIteration:
        return _FallbackCorpusGraph
    base = gen / "corpus-graph-builder"
    flat = base / "corpus_graph_builder.py"
    pkg = base / "corpus_graph_builder" / "__init__.py"
    path = flat if flat.is_file() else pkg
    if not path.is_file():
        return _FallbackCorpusGraph
    try:
        module = load_module(path, "corpus_graph_builder")
        cls = getattr(module, "CorpusGraph")
        return cls
    except Exception:
        return _FallbackCorpusGraph


def _component_node(slug_id):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {
            "component.md": "---\nid: " + slug_id + "\ntitle: T\nstatus: draft\n---\n\n# " + slug_id + "\n",
        },
    }


def _build_graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-alpha": _component_node("comp-alpha"),
        "comp-beta": _component_node("comp-beta"),
    }
    edges = [
        {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
        {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    cls = _corpus_graph_class()
    try:
        return cls(nodes=nodes, edges=edges, aggregates=aggregates)
    except Exception:
        return _FallbackCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def _visible(element):
    v = element.visible
    if callable(v):
        v = v()
    return bool(v)


def _count(element):
    c = element.count
    if callable(c):
        c = c()
    return c


IDS = ["comp-alpha", "comp-beta", "P-ALPHA"]


def _node(page, node_id):
    return page.find(css='li.node[data-id="' + node_id + '"]')


def test_ac_docs_012_search_filters_nodes(browser, tmp_path):
    graph = _build_graph()
    out_dir = tmp_path
    docs_site_renderer.render_docs_site(graph, out_dir)

    index = out_dir / "index.html"
    assert index.is_file()

    page = browser.open(index)

    assert _count(page.find(css="li.node")) == 3

    search = page.find(css="#search")
    search.fill("beta")

    assert _visible(_node(page, "comp-beta")) is True
    assert _visible(_node(page, "comp-alpha")) is False
    assert _visible(_node(page, "P-ALPHA")) is False

    search.fill("")

    for node_id in IDS:
        assert _visible(_node(page, node_id)) is True, node_id

    assert page.console_errors() == []
    assert page.blocked_requests() == []
# hotdocs-criterion: sha256:912617cce8b0464c2f86cd1e7cbbc8b0b3bef45d60ee3124ec1e799ea3b343bf
"""AC-DOCS-003: the dashboard view displays corpus-graph.json's aggregates exactly.

Given corpus-graph.json's aggregates field with known metric values
When render_docs_site runs
Then the dashboard view displays those exact values
"""

import dataclasses
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@dataclasses.dataclass
class _CorpusGraph:
    """Same shape as corpus-graph-builder's documented CorpusGraph."""

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
    """Use the real CorpusGraph dataclass when it can be found, else the same shape."""
    try:
        gen = next(
            p for p in Path(docs_site_renderer.__file__).resolve().parents if p.name == "gen"
        )
    except StopIteration:
        return _CorpusGraph
    base = gen / "corpus-graph-builder"
    flat = base / "corpus_graph_builder.py"
    pkg = base / "corpus_graph_builder" / "__init__.py"
    path = flat if flat.is_file() else pkg
    if not path.is_file():
        return _CorpusGraph
    try:
        module = load_module(path, "corpus_graph_builder")
        cls = getattr(module, "CorpusGraph")
        cls(nodes={}, edges=[], aggregates={})
        return cls
    except Exception:
        return _CorpusGraph


KNOWN_AGGREGATES = {
    "orphan_capability_rate": 0.125,
    "orphan_component_rate": 0.375,
    "orphan_var_rate": 0.625,
}


def _graph():
    nodes = {
        "P-DASH-CAP": {"type": "capability"},
        "comp-dash-alpha": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": "# Dash alpha\n\nA component.\n",
            },
        },
        "comp-dash-beta": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": True,
            "pinned_overrides": [],
            "owners": [],
            "documents": {},
        },
        "VAR-DASH-URL": {"type": "var"},
    }
    edges = [
        {"from": "comp-dash-alpha", "to": "P-DASH-CAP", "kind": "realizes"},
        {"from": "comp-dash-alpha", "to": "VAR-DASH-URL", "kind": "uses_var"},
        {"from": "comp-dash-alpha", "to": "comp-dash-beta", "kind": "depends_on"},
    ]
    cls = _corpus_graph_class()
    return cls(nodes=nodes, edges=edges, aggregates=dict(KNOWN_AGGREGATES))


def _visible_text(markup):
    markup = re.sub(r"(?is)<script\b.*?</script>", " ", markup)
    markup = re.sub(r"(?is)<style\b.*?</style>", " ", markup)
    markup = re.sub(r"(?s)<[^>]*>", " ", markup)
    return html.unescape(markup)


def test_dashboard_displays_exact_aggregate_values(tmp_path):
    out_dir = tmp_path / "site"
    graph = _graph()

    result = docs_site_renderer.render_docs_site(graph, out_dir)
    assert result is None

    pages = sorted(p for p in out_dir.rglob("*.html") if p.is_file())
    assert pages, "render_docs_site wrote no HTML pages"

    texts = {p: _visible_text(p.read_text(encoding="utf-8")) for p in pages}

    def shows(text, value):
        token = repr(value)  # e.g. "0.125"
        return re.search(r"(?<![0-9.])" + re.escape(token) + r"(?![0-9])", text) is not None

    dashboard_pages = [
        p for p, text in texts.items()
        if all(shows(text, v) for v in KNOWN_AGGREGATES.values())
    ]
    missing = {
        name: value
        for name, value in KNOWN_AGGREGATES.items()
        if not any(shows(text, value) for text in texts.values())
    }
    assert not missing, "aggregate values not displayed anywhere: " + repr(missing)
    assert dashboard_pages, (
        "no single page (the dashboard view) displays every aggregate value "
        + repr(KNOWN_AGGREGATES)
    )
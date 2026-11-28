# hotdocs-criterion: sha256:9068f34b0ab3ced225c0145f0050a85865bd1aa3d70d81e9e80b8396ad727859
import dataclasses
import importlib.util
import re
import sys
from pathlib import Path

import docs_site_renderer


def load_module(path, module_name, package_dir=None):
    if package_dir is not None:
        spec = importlib.util.spec_from_file_location(
            module_name, path, submodule_search_locations=[str(package_dir)]
        )
    else:
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
    try:
        if flat.is_file():
            module = load_module(flat, "corpus_graph_builder")
        elif pkg.is_file():
            module = load_module(pkg, "corpus_graph_builder", package_dir=pkg.parent)
        else:
            return _FallbackCorpusGraph
        return getattr(module, "CorpusGraph", _FallbackCorpusGraph)
    except Exception:
        return _FallbackCorpusGraph


def _component(size_status, slug):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": size_status,
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {"component.md": "# " + slug + "\n\nA component.\n"},
    }


def _build_graph():
    cls = _corpus_graph_class()
    nodes = {
        "comp-alpha": _component("ok", "comp-alpha"),
        "comp-beta": _component("over", "comp-beta"),
        "P-ALPHA": {"type": "capability"},
    }
    edges = [
        {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
        {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
    ]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    try:
        return cls(nodes=nodes, edges=edges, aggregates=aggregates)
    except TypeError:
        return _FallbackCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def test_ac_docs_013_every_page_has_one_style_element_in_head_and_no_other_css(tmp_path):
    out_dir = tmp_path / "site"
    graph = _build_graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    html_files = sorted(p for p in out_dir.rglob("*.html") if p.is_file())
    rel = {p.relative_to(out_dir).as_posix() for p in html_files}
    for expected in (
        "index.html",
        "dashboard.html",
        "nodes/comp-alpha.html",
        "nodes/comp-beta.html",
        "nodes/P-ALPHA.html",
    ):
        assert expected in rel, (expected, sorted(rel))

    for path in html_files:
        text = path.read_text(encoding="utf-8")
        name = path.relative_to(out_dir).as_posix()

        assert text.count("<style") == 1, name

        head_match = re.search(r"<head[\s>]", text)
        assert head_match is not None, name
        head_pos = head_match.start()
        head_end = text.find("</head>")
        assert head_end != -1, name
        style_pos = text.find("<style")
        assert head_pos < style_pos < head_end, name

        style_close = text.find("</style>", style_pos)
        assert style_close != -1, name
        assert style_close < head_end, name
        element_text = text[style_pos:style_close]
        assert ".tone-ok" in element_text, name
        assert "--color-bg" in element_text, name

        assert " style=" not in text, name
        assert "<link" not in text, name
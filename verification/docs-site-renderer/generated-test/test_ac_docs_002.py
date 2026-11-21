# hotdocs-criterion: sha256:88b746db66fc4bedaafaa4927721b10feff393b3aeaf116685cd0fa15f613f8f
import dataclasses
import html
import importlib.util
import json
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
    try:
        if flat.is_file():
            module = load_module(flat, "corpus_graph_builder")
        elif pkg.is_file():
            spec = importlib.util.spec_from_file_location(
                "corpus_graph_builder", pkg, submodule_search_locations=[str(pkg.parent)]
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["corpus_graph_builder"] = module
            spec.loader.exec_module(module)
        else:
            return _FallbackCorpusGraph
        cls = getattr(module, "CorpusGraph", None)
        if cls is None:
            return _FallbackCorpusGraph
        cls(nodes={}, edges=[], aggregates={})
        return cls
    except Exception:
        return _FallbackCorpusGraph


COMP_ID = "comp-zqmark"
OTHER_ID = "comp-plainother"

DOC_COMPONENT = "Component body docmarkalpha91 text"
DOC_REQ = "Requirement body reqdocmarkbeta92 text"
DOC_IFACE = "Interface body ifacemarkgamma93 text"
DOC_ACC = "Acceptance body accmarkdelta94 text"
DOC_CONSTRAINTS = "Constraints body consmarkeps95 text"

REQ_ID = "R-ZQMARK-777"
REQ_STATUS = "reqstatusmark31"
CRIT_ID = "AC-ZQMARK-888"
CRIT_KIND = "generated-test"
CRIT_RESULT = "critresultmark42"

MODEL = "anthropic:modelpinmark-q9"
PROMPT_VERSION = "promptvermark-v53"
GENERATED_AT = "2031-04-05T06:07:08Z"

SIZE_STATUS = "over"
PINNED = "src/pinnedmark_file64.py"
OWNER = "ownermark-team75"


def _component_node(sealed):
    return {
        "type": "component",
        "verification": {
            "criteria": [
                {"id": CRIT_ID, "kind": CRIT_KIND, "result": CRIT_RESULT, "covers": [REQ_ID]}
            ],
            "requirement_results": {REQ_ID: REQ_STATUS},
        },
        "provenance": {
            "model": MODEL,
            "prompt_version": PROMPT_VERSION,
            "generated_at": GENERATED_AT,
        },
        "size_status": SIZE_STATUS,
        "sealed": sealed,
        "pinned_overrides": [PINNED],
        "owners": [OWNER],
        "documents": {
            "acceptance/AC-ZQMARK-888.md": DOC_ACC,
            "component.md": DOC_COMPONENT,
            "constraints.md": DOC_CONSTRAINTS,
            "interface/library.md": DOC_IFACE,
            "requirements/R-ZQMARK-777.md": DOC_REQ,
        },
    }


def _graph(sealed):
    cls = _corpus_graph_class()
    nodes = {
        COMP_ID: _component_node(sealed),
        OTHER_ID: {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": [],
            "documents": {"component.md": "Plain other component"},
        },
    }
    edges = [{"from": COMP_ID, "to": OTHER_ID, "kind": "depends_on"}]
    aggregates = {
        "orphan_capability_rate": 0.0,
        "orphan_component_rate": 0.0,
        "orphan_var_rate": 0.0,
    }
    return cls(nodes=nodes, edges=edges, aggregates=aggregates)


def _detail_page(out_dir):
    pages = []
    for p in sorted(Path(out_dir).rglob("*.html")):
        text = html.unescape(p.read_text(encoding="utf-8"))
        if "docmarkalpha91" in text and p.name != "index.html":
            pages.append(text)
    if not pages:
        for p in sorted(Path(out_dir).rglob("*.html")):
            text = html.unescape(p.read_text(encoding="utf-8"))
            if "docmarkalpha91" in text:
                pages.append(text)
    assert pages, "no detail page containing the component's documents was rendered"
    return pages[0]


def test_ac_docs_002_detail_view_shows_every_field(tmp_path):
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(_graph(True), out_dir)
    page = _detail_page(out_dir)

    expected = [
        COMP_ID,
        "docmarkalpha91",
        "reqdocmarkbeta92",
        "ifacemarkgamma93",
        "accmarkdelta94",
        "consmarkeps95",
        REQ_ID,
        REQ_STATUS,
        CRIT_ID,
        CRIT_KIND,
        CRIT_RESULT,
        MODEL,
        PROMPT_VERSION,
        GENERATED_AT,
        SIZE_STATUS,
        PINNED,
        OWNER,
    ]
    missing = [v for v in expected if v not in page]
    assert not missing, "detail view lacks values: " + repr(missing)


def test_ac_docs_002_detail_view_reflects_sealed(tmp_path):
    out_sealed = tmp_path / "sealed"
    out_unsealed = tmp_path / "unsealed"
    docs_site_renderer.render_docs_site(_graph(True), out_sealed)
    docs_site_renderer.render_docs_site(_graph(False), out_unsealed)
    sealed_page = _detail_page(out_sealed)
    unsealed_page = _detail_page(out_unsealed)
    assert sealed_page != unsealed_page, "sealed status is not shown in the detail view"
import docs_site_renderer

import dataclasses
import importlib.util
import json
import sys
from pathlib import Path

import pytest


# Distinctive, exactly-representable metric values so their textual form is
# unambiguous (str(0.4375) == "0.4375").
KNOWN_AGGREGATES = {
    "orphan_capability_rate": 0.4375,
    "orphan_component_rate": 0.1875,
    "orphan_var_rate": 0.8125,
}


def _tool_root():
    here = Path(docs_site_renderer.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_from_path(module_name, path, package_dir=None):
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


def _real_corpus_graph_class():
    root = _tool_root()
    if root is None:
        return None
    base = root / "gen" / "corpus-graph-builder"
    flat = base / "corpus_graph_builder.py"
    pkg = base / "corpus_graph_builder" / "__init__.py"
    try:
        if flat.is_file():
            mod = _load_from_path("corpus_graph_builder", flat)
        elif pkg.is_file():
            mod = _load_from_path("corpus_graph_builder", pkg, pkg.parent)
        else:
            return None
    except Exception:
        return None
    return getattr(mod, "CorpusGraph", None)


@dataclasses.dataclass
class _FallbackCorpusGraph:
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

    def __getitem__(self, key):
        return self.to_dict()[key]

    def get(self, key, default=None):
        return self.to_dict().get(key, default)


def _make_graph(nodes, edges, aggregates):
    cls = _real_corpus_graph_class()
    if cls is not None:
        try:
            return cls(nodes=nodes, edges=edges, aggregates=aggregates)
        except Exception:
            pass
    return _FallbackCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def _graph_fixture():
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-ZERO-EDIT]\n"
        "uses_var: [VAR-FOO-URL]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n"
    )
    nodes = {
        "P-ZERO-EDIT": {"type": "capability"},
        "P-LONELY": {"type": "capability"},
        "comp-foo": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {
                "component.md": component_md,
                "requirements/R-FOO-001.md": "**R-FOO-001** - MUST foo.\n",
            },
        },
        "VAR-FOO-URL": {"type": "var"},
    }
    edges = [
        {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
    ]
    return _make_graph(nodes, edges, dict(KNOWN_AGGREGATES))


def _accepted_renderings(value):
    forms = {repr(value), str(value)}
    # Also accept the same exact value rendered as a percentage.
    forms.add(f"{value * 100:g}%")
    return forms


def _read_text_files(out_dir):
    texts = {}
    for path in out_dir.rglob("*"):
        if path.is_file():
            try:
                texts[path] = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
    return texts


def test_ac_docs_003_dashboard_displays_exact_aggregate_values(tmp_path):
    graph = _graph_fixture()
    out_dir = tmp_path / "dist" / "docs-site"
    out_dir.mkdir(parents=True)

    result = docs_site_renderer.render_docs_site(graph, out_dir)
    assert result is None

    texts = _read_text_files(out_dir)
    assert texts, "render_docs_site wrote no readable files to out_dir"

    def shows_all(text):
        return all(
            any(form in text for form in _accepted_renderings(v))
            for v in KNOWN_AGGREGATES.values()
        )

    html_pages = {p: t for p, t in texts.items() if p.suffix.lower() in (".html", ".htm")}
    assert html_pages, "render_docs_site wrote no HTML pages"

    dashboard_pages = [p for p, t in html_pages.items() if shows_all(t)]
    assert dashboard_pages, (
        "no rendered page displays all of the aggregates' exact values "
        f"{KNOWN_AGGREGATES!r}; pages: {sorted(str(p.relative_to(out_dir)) for p in html_pages)}"
    )

    # Each metric's exact value is present on the dashboard page.
    page_text = html_pages[dashboard_pages[0]]
    for name, value in KNOWN_AGGREGATES.items():
        assert any(form in page_text for form in _accepted_renderings(value)), (
            f"dashboard does not display {name}={value!r}"
        )
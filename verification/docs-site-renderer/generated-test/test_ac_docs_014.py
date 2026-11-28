# hotdocs-criterion: sha256:22470018b0fc202812a58cb69b87387920a82e36b82f266e965fe8e59e67b323
import importlib.util
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


class _DuckCorpusGraph:
    def __init__(self, nodes, edges, aggregates):
        self.nodes = nodes
        self.edges = edges
        self.aggregates = aggregates

    def to_dict(self):
        return {"nodes": self.nodes, "edges": self.edges, "aggregates": self.aggregates}

    def to_json_bytes(self):
        import json

        return (
            json.dumps(self.to_dict(), sort_keys=True, indent=2, ensure_ascii=True) + "\n"
        ).encode("utf-8")


def _component_node(slug_id, size_status):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": size_status,
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {
            "component.md": "# " + slug_id + "\n\nA test component.\n",
        },
    }


def _make_graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-alpha": _component_node("comp-alpha", "ok"),
        "comp-beta": _component_node("comp-beta", "over"),
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
    cls = None
    try:
        gen = next(
            p for p in Path(docs_site_renderer.__file__).resolve().parents if p.name == "gen"
        )
        base = gen / "corpus-graph-builder"
        flat = base / "corpus_graph_builder.py"
        pkg = base / "corpus_graph_builder" / "__init__.py"
        path = flat if flat.is_file() else pkg
        if path.is_file():
            mod = load_module(path, "corpus_graph_builder")
            cls = getattr(mod, "CorpusGraph", None)
    except Exception:
        cls = None
    if cls is not None:
        try:
            return cls(nodes=nodes, edges=edges, aggregates=aggregates)
        except Exception:
            pass
    return _DuckCorpusGraph(nodes, edges, aggregates)


_RGB = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")


def _parse_rgb(value):
    m = _RGB.search(value)
    assert m is not None, "not an rgb() colour: " + repr(value)
    return tuple(int(m.group(i)) for i in (1, 2, 3))


def _luminance(rgb):
    chans = []
    for v in rgb:
        c = v / 255
        if c <= 0.04045:
            c = c / 12.92
        else:
            c = ((c + 0.055) / 1.055) ** 2.4
        chans.append(c)
    r, g, b = chans
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la = _luminance(a)
    lb = _luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def _classes(element):
    return (element.attribute("class") or "").split()


def test_ac_docs_014_size_tone_and_contrast(browser, tmp_path):
    graph = _make_graph()
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(graph, out_dir)

    alpha_path = out_dir / "nodes" / "comp-alpha.html"
    beta_path = out_dir / "nodes" / "comp-beta.html"
    assert alpha_path.is_file()
    assert beta_path.is_file()

    backgrounds = {}
    for scheme in ("light", "dark"):
        border_colors = {}
        for name, path, tone in (
            ("comp-alpha", alpha_path, "tone-ok"),
            ("comp-beta", beta_path, "tone-fail"),
        ):
            if scheme == "dark":
                page = browser.open(path, color_scheme="dark")
            else:
                page = browser.open(path)

            size = page.find(css="span.size")
            assert size.count() == 1, name + " " + scheme
            assert tone in _classes(size), name + " " + scheme
            border_colors[name] = size.style("border-left-color")

            body = page.find(css="body")
            fg = _parse_rgb(body.style("color"))
            bg_value = body.style("background-color")
            bg = _parse_rgb(bg_value)
            assert _contrast(fg, bg) >= 4.5, (name, scheme, fg, bg)
            backgrounds[(name, scheme)] = bg_value

            assert page.console_errors() == [], name + " " + scheme

        assert border_colors["comp-alpha"] != border_colors["comp-beta"], scheme

    for name in ("comp-alpha", "comp-beta"):
        assert backgrounds[(name, "light")] != backgrounds[(name, "dark")], name
# hotdocs-criterion: sha256:260d5e1b19ee542921fd7c66fab3b806294a6dc749b680a5de4b2d813a41c953
import dataclasses
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
class _LocalCorpusGraph:
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


def _corpus_graph_class():
    try:
        gen = next(
            p
            for p in Path(docs_site_renderer.__file__).resolve().parents
            if p.name == "gen"
        )
        base = gen / "corpus-graph-builder"
        flat = base / "corpus_graph_builder.py"
        pkg = base / "corpus_graph_builder" / "__init__.py"
        path = flat if flat.is_file() else pkg
        if not path.is_file():
            return _LocalCorpusGraph
        module = load_module(path, "corpus_graph_builder")
        cls = getattr(module, "CorpusGraph", None)
        return cls if cls is not None else _LocalCorpusGraph
    except Exception:
        return _LocalCorpusGraph


def _component_node(slug, size_status):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": size_status,
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {
            "component.md": "---\nid: comp-" + slug + "\ntitle: " + slug
            + "\nstatus: draft\nowners: [pipeline-team]\n---\n\n# " + slug + "\n",
        },
    }


def _build_graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-alpha": _component_node("alpha", "ok"),
        "comp-beta": _component_node("beta", "over"),
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
        return _LocalCorpusGraph(nodes=nodes, edges=edges, aggregates=aggregates)


def _rgb(value):
    nums = re.findall(r"[-+]?\d*\.?\d+", value)
    assert len(nums) >= 3, "not an rgb() colour: " + repr(value)
    return tuple(float(n) for n in nums[:3])


def _luminance(rgb):
    chans = []
    for v in rgb:
        c = v / 255
        c = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        chans.append(c)
    r, g, b = chans
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    la = _luminance(_rgb(a))
    lb = _luminance(_rgb(b))
    lighter, darker = max(la, lb), min(la, lb)
    return round((lighter + 0.05) / (darker + 0.05), 2)


def test_ac_docs_014(browser, tmp_path):
    graph = _build_graph()
    out_dir = tmp_path / "site"
    docs_site_renderer.render_docs_site(graph, out_dir)

    alpha_path = out_dir / "nodes" / "comp-alpha.html"
    beta_path = out_dir / "nodes" / "comp-beta.html"
    assert alpha_path.is_file()
    assert beta_path.is_file()

    backgrounds = {}
    for scheme in (None, "dark"):
        if scheme is None:
            alpha = browser.open(alpha_path)
        else:
            alpha = browser.open(alpha_path, color_scheme="dark")
        alpha_span = alpha.find(css="span.size")
        assert alpha_span.count() == 1
        alpha_classes = (alpha_span.attribute("class") or "").split()
        assert "size" in alpha_classes
        assert "tone-ok" in alpha_classes
        alpha_border = alpha_span.style("border-left-color")
        alpha_body = alpha.find(css="body")
        alpha_color = alpha_body.style("color")
        alpha_bg = alpha_body.style("background-color")
        assert _contrast(alpha_color, alpha_bg) >= 4.5
        assert alpha.console_errors() == []

        if scheme is None:
            beta = browser.open(beta_path)
        else:
            beta = browser.open(beta_path, color_scheme="dark")
        beta_span = beta.find(css="span.size")
        assert beta_span.count() == 1
        beta_classes = (beta_span.attribute("class") or "").split()
        assert "size" in beta_classes
        assert "tone-fail" in beta_classes
        beta_border = beta_span.style("border-left-color")
        beta_body = beta.find(css="body")
        beta_color = beta_body.style("color")
        beta_bg = beta_body.style("background-color")
        assert _contrast(beta_color, beta_bg) >= 4.5
        assert beta.console_errors() == []

        assert alpha_border != beta_border

        backgrounds[(scheme, "alpha")] = alpha_bg
        backgrounds[(scheme, "beta")] = beta_bg

    assert backgrounds[(None, "alpha")] != backgrounds[("dark", "alpha")]
    assert backgrounds[(None, "beta")] != backgrounds[("dark", "beta")]
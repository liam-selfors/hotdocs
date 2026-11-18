# hotdocs-criterion: sha256:49ad848df13a6562ed2acade428307a75f5a5bc628a9ce92e9ae323dd5410fde
import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import docs_site_renderer


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


AGGREGATES = {
    "orphan_capability_rate": 0.125,
    "orphan_component_rate": 0.375,
    "orphan_var_rate": 0.625,
}


def _graph():
    nodes = {
        "P-ALPHA": {"type": "capability"},
        "comp-alpha": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": True,
            "pinned_overrides": [],
            "owners": ["docs-team"],
            "documents": {
                "component.md": "---\nid: comp-alpha\ntitle: Alpha\nstatus: draft\n---\nAlpha body.\n",
            },
        },
        "comp-beta": {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "unknown",
            "sealed": True,
            "pinned_overrides": [],
            "owners": [],
            "documents": {},
        },
        "VAR-ALPHA-URL": {"type": "var"},
    }
    edges = [
        {"from": "comp-alpha", "to": "P-ALPHA", "kind": "realizes"},
        {"from": "comp-alpha", "to": "VAR-ALPHA-URL", "kind": "uses_var"},
        {"from": "comp-beta", "to": "comp-alpha", "kind": "depends_on"},
    ]
    return CorpusGraph(nodes=nodes, edges=edges, aggregates=dict(AGGREGATES))


def _candidates(value):
    pct = value * 100
    forms = {
        repr(value),
        str(value),
        "{:g}%".format(pct),
        "{:.1f}%".format(pct),
        "{:.2f}%".format(pct),
        "{:g} %".format(pct),
        "{:.1f} %".format(pct),
        "{:.2f} %".format(pct),
    }
    return forms


def _read_all(out_dir):
    texts = {}
    for p in Path(out_dir).rglob("*"):
        if p.is_file():
            try:
                texts[p] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    return texts


def test_dashboard_displays_exact_aggregate_values(tmp_path):
    out_dir = tmp_path / "site"
    graph = _graph()

    docs_site_renderer.render_docs_site(graph, out_dir)

    assert out_dir.is_dir(), "render_docs_site did not create the output directory"
    texts = _read_all(out_dir)
    assert texts, "render_docs_site wrote no files"

    # Prefer the page(s) named as the dashboard / health view if present.
    dashboard = {
        p: t
        for p, t in texts.items()
        if any(w in p.name.lower() for w in ("dashboard", "health", "metrics"))
    }
    if not dashboard:
        # Otherwise, the dashboard is whichever rendered page carries the metrics.
        dashboard = {
            p: t
            for p, t in texts.items()
            if any(
                any(c in t for c in _candidates(v)) for v in AGGREGATES.values()
            )
        }
    assert dashboard, "no dashboard view found in rendered output"

    combined = "\n".join(dashboard.values())
    for name, value in AGGREGATES.items():
        forms = _candidates(value)
        assert any(f in combined for f in forms), (
            "dashboard does not display aggregate "
            + repr(name)
            + " with value "
            + repr(value)
            + "; looked for any of "
            + repr(sorted(forms))
        )
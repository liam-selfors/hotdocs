import dataclasses
import json
from pathlib import Path

import docs_site_renderer


# Known aggregate values. The graph below is built so that recomputing the
# documented orphan rates from nodes/edges gives these same values. A renderer
# that recomputes them instead of reading `aggregates` still has to show them.
#   capabilities: 8 total, 3 with an incoming `realizes` edge   -> 5/8 = 0.625
#   vars:         8 total, 1 with an incoming `uses_var` edge   -> 7/8 = 0.875
#   components:   8 total, 3 with neither an incoming
#                 `depends_on` nor an outgoing `realizes` edge  -> 3/8 = 0.375
KNOWN_AGGREGATES = {
    "orphan_capability_rate": 0.625,
    "orphan_component_rate": 0.375,
    "orphan_var_rate": 0.875,
}


@dataclasses.dataclass
class FakeCorpusGraph:
    """Matches corpus-graph-builder's documented CorpusGraph shape: a dataclass
    with `nodes`, `edges`, `aggregates`, a `to_dict()` and `to_json_bytes()`.
    It also supports item access, so either access style works."""

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


def _component_node(slug):
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["team-x"],
        "documents": {
            "component.md": (
                "---\n"
                f"id: comp-{slug}\n"
                f"title: Component {slug}\n"
                "status: draft\n"
                "owners: [team-x]\n"
                "---\n"
                f"# Component {slug}\n"
            ),
        },
    }


def _build_graph():
    nodes = {}
    for i in range(1, 9):
        nodes[f"P-C{i}"] = {"type": "capability"}
        nodes[f"VAR-V{i}"] = {"type": "var"}
        nodes[f"comp-k{i}"] = _component_node(f"k{i}")

    edges = [
        {"from": "comp-k1", "to": "P-C1", "kind": "realizes"},
        {"from": "comp-k2", "to": "P-C2", "kind": "realizes"},
        {"from": "comp-k3", "to": "P-C3", "kind": "realizes"},
        {"from": "comp-k4", "to": "comp-k5", "kind": "depends_on"},
        {"from": "comp-k6", "to": "comp-k4", "kind": "depends_on"},
        {"from": "comp-k7", "to": "VAR-V1", "kind": "uses_var"},
    ]
    edges.sort(key=lambda e: (e["from"], e["to"], e["kind"]))

    return FakeCorpusGraph(
        nodes=nodes, edges=edges, aggregates=dict(KNOWN_AGGREGATES)
    )


def _rendered_texts(out_dir: Path):
    texts = {}
    for path in sorted(out_dir.rglob("*")):
        if path.is_file():
            texts[path] = path.read_bytes().decode("utf-8", errors="replace")
    return texts


def test_ac_docs_003_dashboard_displays_exact_aggregate_values(tmp_path):
    graph = _build_graph()
    out_dir = tmp_path / "site"
    out_dir.mkdir(parents=True, exist_ok=True)

    result = docs_site_renderer.render_docs_site(graph, out_dir)
    assert result is None

    texts = _rendered_texts(out_dir)
    assert texts, "render_docs_site wrote no files to out_dir"

    expected_strings = [str(v) for v in KNOWN_AGGREGATES.values()]

    # The dashboard view is some rendered page that shows every known value.
    dashboard_candidates = [
        path
        for path, text in texts.items()
        if all(s in text for s in expected_strings)
    ]

    if not dashboard_candidates:
        missing_report = {
            str(path.relative_to(out_dir)): [
                s for s in expected_strings if s not in text
            ]
            for path, text in texts.items()
        }
        raise AssertionError(
            "No rendered page displays all known aggregate values "
            f"{KNOWN_AGGREGATES!r}; missing per file: {missing_report!r}"
        )

    # Prefer a page that is clearly the dashboard / health view, if one exists.
    named = [
        p
        for p in texts
        if any(w in p.name.lower() for w in ("dashboard", "health", "metrics"))
    ]
    if named:
        assert any(p in dashboard_candidates for p in named), (
            "The dashboard page "
            f"{[str(p.relative_to(out_dir)) for p in named]!r} does not display "
            f"all known aggregate values {KNOWN_AGGREGATES!r}"
        )
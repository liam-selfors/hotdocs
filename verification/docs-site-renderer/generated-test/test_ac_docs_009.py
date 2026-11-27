# hotdocs-criterion: sha256:7ac3cdd0af1ebb9077a743b99403030844ad577725c0950f508921bd0b355741
"""AC-DOCS-009 (covers R-DOCS-008): layoutGraph lays out the DAG by type column."""

import copy

import docs_site_renderer  # noqa: F401  (module under test; the asset is its own file)


def _node(id_, x, y, label_x, label_y):
    return {"id": id_, "x": x, "y": y, "labelX": label_x, "labelY": label_y}


def _edge(index, frm, to, x1, y1, x2, y2, color):
    return {
        "index": index,
        "from": frm,
        "to": to,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "color": color,
    }


def test_layout_graph_full_example(asset_runner):
    run = asset_runner("static/app.js")
    nodes = [
        {"id": "P-A", "type": "capability"},
        {"id": "VAR-X", "type": "var"},
        {"id": "comp-a", "type": "component"},
        {"id": "P-B", "type": "capability"},
        {"id": "comp-b", "type": "component"},
        {"id": "comp-c", "type": "component"},
        {"id": "zz", "type": "glossary"},
    ]
    edges = [
        {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
        {"from": "comp-a", "to": "P-A", "kind": "realizes"},
        {"from": "comp-b", "to": "VAR-X", "kind": "uses_var"},
        {"from": "comp-c", "to": "gone", "kind": "depends_on"},
        {"from": "gone", "to": "comp-c", "kind": "realizes"},
        {"from": "zz", "to": "P-B", "kind": "mentions"},
    ]
    nodes_before = copy.deepcopy(nodes)
    edges_before = copy.deepcopy(edges)

    result = run("layoutGraph", [nodes, edges])

    expected = {
        "width": 1100,
        "height": 180,
        "nodes": [
            _node("P-A", 120, 30, 132, 34),
            _node("VAR-X", 640, 30, 652, 34),
            _node("comp-a", 380, 30, 392, 34),
            _node("P-B", 120, 70, 132, 74),
            _node("comp-b", 380, 70, 392, 74),
            _node("comp-c", 380, 110, 392, 114),
            _node("zz", 900, 30, 912, 34),
        ],
        "edges": [
            _edge(0, "comp-a", "comp-b", 380, 30, 380, 70, "#1565c0"),
            _edge(1, "comp-a", "P-A", 380, 30, 120, 30, "#2e7d32"),
            _edge(2, "comp-b", "VAR-X", 380, 70, 640, 30, "#ef6c00"),
            _edge(5, "zz", "P-B", 900, 30, 120, 70, "#ef6c00"),
        ],
    }
    assert result == expected
    # The test's own inputs are untouched (they are serialized to the runner).
    assert nodes == nodes_before
    assert edges == edges_before


def test_layout_graph_empty(asset_runner):
    run = asset_runner("static/app.js")
    result = run("layoutGraph", [[], []])
    assert result == {"width": 1100, "height": 100, "nodes": [], "edges": []}


def test_layout_graph_single_var_self_loop(asset_runner):
    run = asset_runner("static/app.js")
    result = run(
        "layoutGraph",
        [
            [{"id": "v", "type": "var"}],
            [{"from": "v", "to": "v", "kind": "realizes"}],
        ],
    )
    assert result == {
        "width": 1100,
        "height": 100,
        "nodes": [_node("v", 640, 30, 652, 34)],
        "edges": [_edge(0, "v", "v", 640, 30, 640, 30, "#2e7d32")],
    }
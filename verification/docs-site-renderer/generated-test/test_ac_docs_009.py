# hotdocs-criterion: sha256:60346a41d7bc0cb67348a2c35fc7a5661612d8a32159b68361c9aaa332ce15e6
import docs_site_renderer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(value, keys):
    return {k: field(value, k) for k in keys}


NODE_KEYS = ["id", "x", "y", "labelX", "labelY"]
EDGE_KEYS = ["index", "from", "to", "x1", "y1", "x2", "y2", "color"]
TOP_KEYS = ["width", "height", "nodes", "edges"]


def normalize(result):
    if isinstance(result, dict):
        assert sorted(result.keys()) == sorted(TOP_KEYS)
    nodes = field(result, "nodes")
    edges = field(result, "edges")
    norm_nodes = []
    for n in nodes:
        if isinstance(n, dict):
            assert sorted(n.keys()) == sorted(NODE_KEYS)
        norm_nodes.append(as_plain(n, NODE_KEYS))
    norm_edges = []
    for e in edges:
        if isinstance(e, dict):
            assert sorted(e.keys()) == sorted(EDGE_KEYS)
        norm_edges.append(as_plain(e, EDGE_KEYS))
    return {
        "width": field(result, "width"),
        "height": field(result, "height"),
        "nodes": norm_nodes,
        "edges": norm_edges,
    }


def node(id_, x, y, lx, ly):
    return {"id": id_, "x": x, "y": y, "labelX": lx, "labelY": ly}


def edge(index, frm, to, x1, y1, x2, y2, color):
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


def test_layout_graph_columns_rows_edges_and_height(asset_runner):
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
    result = run("layoutGraph", [nodes, edges])
    expected = {
        "width": 1100,
        "height": 180,
        "nodes": [
            node("P-A", 120, 30, 132, 34),
            node("VAR-X", 640, 30, 652, 34),
            node("comp-a", 380, 30, 392, 34),
            node("P-B", 120, 70, 132, 74),
            node("comp-b", 380, 70, 392, 74),
            node("comp-c", 380, 110, 392, 114),
            node("zz", 900, 30, 912, 34),
        ],
        "edges": [
            edge(0, "comp-a", "comp-b", 380, 30, 380, 70, "#1565c0"),
            edge(1, "comp-a", "P-A", 380, 30, 120, 30, "#2e7d32"),
            edge(2, "comp-b", "VAR-X", 380, 70, 640, 30, "#ef6c00"),
            edge(5, "zz", "P-B", 900, 30, 120, 70, "#ef6c00"),
        ],
    }
    assert normalize(result) == expected
    if isinstance(result, dict):
        assert result == expected


def test_layout_graph_empty(asset_runner):
    run = asset_runner("static/app.js")
    result = run("layoutGraph", [[], []])
    expected = {"width": 1100, "height": 100, "nodes": [], "edges": []}
    assert normalize(result) == expected
    if isinstance(result, dict):
        assert result == expected


def test_layout_graph_single_var_self_edge(asset_runner):
    run = asset_runner("static/app.js")
    result = run(
        "layoutGraph",
        [
            [{"id": "v", "type": "var"}],
            [{"from": "v", "to": "v", "kind": "realizes"}],
        ],
    )
    expected = {
        "width": 1100,
        "height": 100,
        "nodes": [node("v", 640, 30, 652, 34)],
        "edges": [edge(0, "v", "v", 640, 30, 640, 30, "#2e7d32")],
    }
    assert normalize(result) == expected
    if isinstance(result, dict):
        assert result == expected
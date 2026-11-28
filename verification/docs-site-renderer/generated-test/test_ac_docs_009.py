# hotdocs-criterion: sha256:6fd64c20a7b6010ee27cee5a73c336ce5af867427ddf12b895d559662db4a3c1
import docs_site_renderer  # noqa: F401  (module under test, per the test spec)


ASSET = "static/app.js"


def _node(id_, x, y, label_x, label_y):
    return {"id": id_, "x": x, "y": y, "labelX": label_x, "labelY": label_y}


def _edge(index, from_, to, x1, y1, x2, y2, cls):
    return {
        "index": index,
        "from": from_,
        "to": to,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "class": cls,
    }


def test_layout_graph_columns_rows_edges_and_height(asset_runner):
    run = asset_runner(ASSET)
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
            _node("P-A", 120, 30, 132, 34),
            _node("VAR-X", 640, 30, 652, 34),
            _node("comp-a", 380, 30, 392, 34),
            _node("P-B", 120, 70, 132, 74),
            _node("comp-b", 380, 70, 392, 74),
            _node("comp-c", 380, 110, 392, 114),
            _node("zz", 900, 30, 912, 34),
        ],
        "edges": [
            _edge(0, "comp-a", "comp-b", 380, 30, 380, 70, "edge-depends-on"),
            _edge(1, "comp-a", "P-A", 380, 30, 120, 30, "edge-realizes"),
            _edge(2, "comp-b", "VAR-X", 380, 70, 640, 30, "edge-other"),
            _edge(5, "zz", "P-B", 900, 30, 120, 70, "edge-other"),
        ],
    }
    assert result == expected


def test_layout_graph_empty(asset_runner):
    run = asset_runner(ASSET)

    result = run("layoutGraph", [[], []])

    assert result == {"width": 1100, "height": 100, "nodes": [], "edges": []}


def test_layout_graph_single_var_self_edge(asset_runner):
    run = asset_runner(ASSET)

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
        "nodes": [{"id": "v", "x": 640, "y": 30, "labelX": 652, "labelY": 34}],
        "edges": [
            {
                "index": 0,
                "from": "v",
                "to": "v",
                "x1": 640,
                "y1": 30,
                "x2": 640,
                "y2": 30,
                "class": "edge-realizes",
            }
        ],
    }
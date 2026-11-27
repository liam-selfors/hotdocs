# hotdocs-criterion: sha256:278817e7c6cf0f966be99921732484b7113dfc6e8a52c2e0d7a4aa449a793d07
import copy

import pytest

import docs_site_renderer  # noqa: F401  (module under test must be importable)


NODES = [
    {"id": "comp-Alpha", "type": "component"},
    {"id": "comp-beta", "type": "component"},
    {"id": "P-ALPHA-CAP", "type": "capability"},
]

EDGES = [
    {"from": "comp-Alpha", "to": "comp-beta", "kind": "depends_on"},
    {"from": "comp-Alpha", "to": "P-ALPHA-CAP", "kind": "realizes"},
    {"from": "comp-beta", "to": "missing", "kind": "depends_on"},
]


CASES = [
    ("ALPHA", (False, True, False), [True, False, True]),
    ("comp-", (False, False, True), [False, True, True]),
    ("", (False, False, False), [False, False, True]),
    ("zzz", (True, True, True), [True, True, True]),
    ("component", (True, True, True), [True, True, True]),
    (" alpha", (True, True, True), [True, True, True]),
]


@pytest.mark.parametrize(
    "query, hidden_nodes, hidden_edges",
    CASES,
    ids=["ALPHA", "comp-", "empty", "zzz", "component", "space-alpha"],
)
def test_filter_graph_table(asset_runner, query, hidden_nodes, hidden_edges):
    run = asset_runner("static/app.js")
    nodes = copy.deepcopy(NODES)
    edges = copy.deepcopy(EDGES)

    result = run("filterGraph", [nodes, edges, query])

    expected = {
        "hiddenNodes": {
            "comp-Alpha": hidden_nodes[0],
            "comp-beta": hidden_nodes[1],
            "P-ALPHA-CAP": hidden_nodes[2],
        },
        "hiddenEdges": hidden_edges,
    }
    assert result == expected


def test_filter_graph_empty_inputs(asset_runner):
    run = asset_runner("static/app.js")

    result = run("filterGraph", [[], [], "a"])

    assert result == {"hiddenNodes": {}, "hiddenEdges": []}
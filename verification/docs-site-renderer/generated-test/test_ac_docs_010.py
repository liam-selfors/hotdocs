# hotdocs-criterion: sha256:f6c76b619be8aeefad5171ab44afd5a9138df18a2518e5fecfd672938f86e68f
"""AC-DOCS-010 (covers R-DOCS-009): filterGraph decides which nodes and edges are hidden."""

import copy

import pytest

import docs_site_renderer  # noqa: F401  (module under test)


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
    ("ALPHA", False, True, False, [True, False, True]),
    ("comp-", False, False, True, [False, True, True]),
    ("", False, False, False, [False, False, True]),
    ("zzz", True, True, True, [True, True, True]),
    ("component", True, True, True, [True, True, True]),
    (" alpha", True, True, True, [True, True, True]),
]


@pytest.mark.parametrize(
    "query, h_alpha, h_beta, h_cap, expected_edges",
    CASES,
    ids=[repr(c[0]) for c in CASES],
)
def test_filter_graph_table(asset_runner, query, h_alpha, h_beta, h_cap, expected_edges):
    run = asset_runner("static/app.js")
    nodes = copy.deepcopy(NODES)
    edges = copy.deepcopy(EDGES)

    result = run("filterGraph", [nodes, edges, query])

    expected = {
        "hiddenNodes": {
            "comp-Alpha": h_alpha,
            "comp-beta": h_beta,
            "P-ALPHA-CAP": h_cap,
        },
        "hiddenEdges": expected_edges,
    }
    assert result == expected
    assert set(result["hiddenNodes"].keys()) == {"comp-Alpha", "comp-beta", "P-ALPHA-CAP"}
    for value in result["hiddenNodes"].values():
        assert value is True or value is False
    for value in result["hiddenEdges"]:
        assert value is True or value is False


def test_filter_graph_empty_inputs(asset_runner):
    run = asset_runner("static/app.js")

    result = run("filterGraph", [[], [], "a"])

    assert result == {"hiddenNodes": {}, "hiddenEdges": []}
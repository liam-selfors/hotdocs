# hotdocs-criterion: sha256:6499ed352543d0830c0a53f7a81f1c048b8bf7e7d11d2a73eece0f583a1c2b60
"""AC-DOCS-010: filterGraph hides nodes whose id lacks the query (case-insensitive,
untrimmed, id only) and edges with a hidden or missing end."""

import copy

import pytest

import docs_site_renderer  # noqa: F401  (module under test, imported as required)


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


@pytest.mark.parametrize(
    "query, h_alpha, h_beta, h_cap, hidden_edges",
    [
        ("ALPHA", False, True, False, [True, False, True]),
        ("comp-", False, False, True, [False, True, True]),
        ("", False, False, False, [False, False, True]),
        ("zzz", True, True, True, [True, True, True]),
        ("component", True, True, True, [True, True, True]),
        (" alpha", True, True, True, [True, True, True]),
    ],
)
def test_filter_graph_table(asset_runner, query, h_alpha, h_beta, h_cap, hidden_edges):
    run = asset_runner("static/app.js")
    nodes = copy.deepcopy(NODES)
    edges = copy.deepcopy(EDGES)

    result = run("filterGraph", [nodes, edges, query])

    assert result == {
        "hiddenNodes": {
            "comp-Alpha": h_alpha,
            "comp-beta": h_beta,
            "P-ALPHA-CAP": h_cap,
        },
        "hiddenEdges": hidden_edges,
    }
    assert set(result["hiddenNodes"].keys()) == {"comp-Alpha", "comp-beta", "P-ALPHA-CAP"}


def test_filter_graph_empty(asset_runner):
    run = asset_runner("static/app.js")

    result = run("filterGraph", [[], [], "a"])

    assert result == {"hiddenNodes": {}, "hiddenEdges": []}
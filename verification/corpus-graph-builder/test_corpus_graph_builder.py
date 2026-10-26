"""One test per AC-GRAPH-* criterion in
specs/components/corpus-graph-builder/acceptance/.

AC-GRAPH-007 ("runs on every merge to main") is a CI-cadence requirement,
not a property of build_corpus_graph() itself — nothing in this repo
drives a real CI pipeline to test against, so it has no corresponding
unit test here, the same way other components' build-cadence criteria
aren't unit-tested. See BOOTSTRAP.md.
"""

import json

from conftest import build, write_component, write_product, write_var, write_provenance


def test_ac_graph_001_node_count_by_kind(corpus_root):
    write_component(corpus_root, "bar")
    write_component(corpus_root, "baz")
    write_product(corpus_root, "P-TWO")
    graph = build(corpus_root)
    assert len(graph.nodes) == 6
    kinds = [v.get("type") for v in graph.nodes.values()]
    assert kinds.count("component") == 3
    assert kinds.count("capability") == 2
    assert kinds.count("var") == 1


def test_ac_graph_002_edge_construction(corpus_root):
    write_component(corpus_root, "bar")
    # Rewrite comp-foo to also depend_on comp-bar, keeping its existing
    # realizes/uses_var from the baseline.
    write_component(corpus_root, "foo", depends_on=["comp-bar"], realizes=["P-ONE"], uses_var=["VAR-ONE"])
    graph = build(corpus_root)
    foo_edges = {(e["to"], e["kind"]) for e in graph.edges if e["from"] == "comp-foo"}
    assert ("comp-bar", "depends_on") in foo_edges
    assert ("P-ONE", "realizes") in foo_edges
    assert ("VAR-ONE", "uses_var") in foo_edges
    assert len(foo_edges) == 3


def test_ac_graph_003_component_annotations(corpus_root):
    write_provenance(
        corpus_root, "foo",
        verification_report={"component_id": "comp-foo", "overall": "pass"},
    )
    graph = build(corpus_root)
    foo = graph.nodes["comp-foo"]
    assert foo["verification"] == {"component_id": "comp-foo", "overall": "pass"}
    assert "provenance" in foo and foo["provenance"].get("spec_bundle_hash") == "sha256:deadbeef"
    assert foo["size_status"] in ("ok", "warn", "fail", "unknown", "over")
    assert foo["sealed"] is False


def test_ac_graph_004_orphan_capability_rate(corpus_root):
    write_product(corpus_root, "P-TWO")  # nothing realizes P-TWO
    graph = build(corpus_root)
    assert graph.aggregates["orphan_capability_rate"] == 0.5


def test_ac_graph_005_orphan_var_rate(corpus_root):
    write_var(corpus_root, "VAR-TWO")  # nothing uses VAR-TWO
    graph = build(corpus_root)
    assert graph.aggregates["orphan_var_rate"] == 0.5


def test_ac_graph_006_single_output_location(corpus_root):
    graph = build(corpus_root)
    out_path = corpus_graph_builder_write(corpus_root, graph)
    assert out_path == corpus_root / "verification" / "corpus-graph.json"
    other_candidates = list((corpus_root / "verification").glob("*.json"))
    assert other_candidates == [out_path]


def test_ac_graph_008_deterministic_bytes(corpus_root):
    first = build(corpus_root).to_json_bytes()
    second = build(corpus_root).to_json_bytes()
    assert first == second


def test_ac_graph_009_license_scan_via_provenance_view(corpus_root):
    write_provenance(
        corpus_root, "foo",
        license_scan={"flagged": True, "findings": ["GPL-3.0 in a transitive dep"]},
    )
    graph = build(corpus_root)
    foo = graph.nodes["comp-foo"]
    assert foo["provenance"]["license_scan"]["flagged"] is True


def corpus_graph_builder_write(root, graph):
    import corpus_graph_builder
    return corpus_graph_builder.write_corpus_graph(graph, root)

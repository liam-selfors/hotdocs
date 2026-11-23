# hotdocs-criterion: sha256:95cf25d63018433c902dc92031e3d83ea797cfb1cde391fbc642715648c190d7
"""AC-GRAPH-004: corpus-wide orphan-capability and orphan-component rates."""

from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug, depends_on, realizes, sealed):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: Component " + slug,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: [" + ", ".join(depends_on) + "]",
        "realizes: [" + ", ".join(realizes) + "]",
        "uses_var: []",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: legacy/" + slug + "/")
    else:
        lines.append("sealed: false")
    lines.append("---")
    lines.append("")
    lines.append("# Component " + slug)
    lines.append("")
    lines.append("## Purpose")
    lines.append("")
    lines.append("A small fixture component named " + slug + ".")
    lines.append("")
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "\n".join(lines),
    )


def _capability(repo_root, name):
    upper = name.upper()
    lines = [
        "---",
        "id: P-" + upper,
        "title: Capability " + upper,
        "status: draft",
        "owners: [pipeline-team]",
        "---",
        "",
        "# Capability " + upper,
        "",
        "A fixture capability.",
        "",
    ]
    _write(repo_root / "specs" / "product" / (name + ".md"), "\n".join(lines))


def _aggregates(graph):
    return field(graph, "aggregates")


def test_orphan_rates_with_mixed_linkage(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _capability(repo_root, "one")
    _capability(repo_root, "two")
    _component(repo_root, "a", [], ["P-ONE"], sealed=False)
    _component(repo_root, "b", [], [], sealed=True)
    _component(repo_root, "c", ["comp-b"], [], sealed=True)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = _aggregates(graph)

    cap_rate = field(aggregates, "orphan_capability_rate")
    comp_rate = field(aggregates, "orphan_component_rate")

    assert isinstance(cap_rate, float)
    assert isinstance(comp_rate, float)
    assert cap_rate == pytest.approx(0.5)
    assert comp_rate == pytest.approx(1.0 / 3.0)

    # The aggregate values are also present in the serialized shape.
    as_dict = graph.to_dict()
    assert as_dict["aggregates"]["orphan_capability_rate"] == pytest.approx(0.5)
    assert as_dict["aggregates"]["orphan_component_rate"] == pytest.approx(1.0 / 3.0)


def test_orphan_capability_rate_zero_with_no_capabilities(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "specs" / "product").mkdir(parents=True)
    _component(repo_root, "solo", [], [], sealed=True)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = _aggregates(graph)

    cap_rate = field(aggregates, "orphan_capability_rate")
    assert isinstance(cap_rate, float)
    assert cap_rate == 0.0
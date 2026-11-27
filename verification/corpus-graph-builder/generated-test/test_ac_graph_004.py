# hotdocs-criterion: sha256:2a6b5ae9c6dc3a4cfe22a7f4db404698c2577782da0af45e605729c6fa51aa4e
"""AC-GRAPH-004: corpus-wide orphan-capability and orphan-component rates."""

from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _list(items):
    return "[" + ", ".join(items) + "]"


def write_component(repo_root, slug, depends_on=(), realizes=(), uses_var=(), sealed=False):
    comp_dir = Path(repo_root) / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "id: " + "comp-" + slug,
        "title: " + "Component " + slug,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: " + _list(depends_on),
        "realizes: " + _list(realizes),
        "uses_var: " + _list(uses_var),
        "sealed: " + ("true" if sealed else "false"),
    ]
    if sealed:
        lines.append("source_path: " + "legacy/" + slug + "/")
    lines += [
        "---",
        "",
        "# Component " + slug,
        "",
        "## Purpose",
        "",
        "A fixture component named " + slug + ".",
        "",
    ]
    (comp_dir / "component.md").write_text("\n".join(lines), encoding="utf-8")


def write_capability(repo_root, name):
    product_dir = Path(repo_root) / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    cap_id = "P-" + name.upper()
    lines = [
        "---",
        "id: " + cap_id,
        "title: " + "Capability " + name,
        "status: draft",
        "owners: [pipeline-team]",
        "---",
        "",
        "# Capability " + name,
        "",
        "A fixture capability.",
        "",
    ]
    (product_dir / (name + ".md")).write_text("\n".join(lines), encoding="utf-8")


def test_orphan_rates_are_computed_aggregates(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_capability(repo_root, "one")
    write_capability(repo_root, "two")
    write_capability(repo_root, "three")

    write_component(repo_root, "a", realizes=["P-ONE"])
    write_component(repo_root, "b")
    write_component(repo_root, "c", depends_on=["comp-b"])
    write_component(repo_root, "d")

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")

    assert field(aggregates, "orphan_capability_rate") == pytest.approx(2 / 3)
    assert field(aggregates, "orphan_component_rate") == pytest.approx(0.5)


def test_orphan_capability_rate_is_zero_with_no_capabilities(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    write_component(repo_root, "solo", sealed=True)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")

    rate = field(aggregates, "orphan_capability_rate")
    assert rate == 0.0
    assert isinstance(rate, float)
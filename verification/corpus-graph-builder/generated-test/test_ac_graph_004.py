import corpus_graph_builder

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _flow(items):
    return "[" + ", ".join(items) + "]"


def _write_component(repo_root: Path, slug: str, depends_on=(), realizes=(), uses_var=()):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {slug}\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        f"depends_on: {_flow(depends_on)}\n"
        f"realizes: {_flow(realizes)}\n"
        f"uses_var: {_flow(uses_var)}\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        "\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"A small synthetic fixture component named {slug}.\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _write_capability(repo_root: Path, name: str):
    prod_dir = repo_root / "specs" / "product"
    prod_dir.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        f"id: P-{name.upper()}\n"
        f"title: Capability {name}\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        f"# P-{name.upper()}\n"
        "\n"
        "A synthetic fixture capability.\n"
    )
    (prod_dir / f"{name.lower()}.md").write_text(text, encoding="utf-8")


def test_orphan_rates_computed_for_mixed_corpus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_capability(repo_root, "one")
    _write_capability(repo_root, "two")
    _write_component(repo_root, "a", realizes=["P-ONE"])
    _write_component(repo_root, "b")
    _write_component(repo_root, "c", depends_on=["comp-b"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")

    cap_rate = field(aggregates, "orphan_capability_rate")
    comp_rate = field(aggregates, "orphan_component_rate")

    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert isinstance(comp_rate, (int, float)) and not isinstance(comp_rate, bool)
    assert cap_rate == pytest.approx(0.5)
    assert comp_rate == pytest.approx(1 / 3)

    # The same computed values appear in the serialized shape.
    as_dict = graph.to_dict()
    assert as_dict["aggregates"]["orphan_capability_rate"] == pytest.approx(0.5)
    assert as_dict["aggregates"]["orphan_component_rate"] == pytest.approx(1 / 3)


def test_orphan_capability_rate_zero_with_no_capabilities(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_component(repo_root, "solo")

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")

    cap_rate = field(aggregates, "orphan_capability_rate")
    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert cap_rate == 0.0

    as_dict = graph.to_dict()
    assert as_dict["aggregates"]["orphan_capability_rate"] == 0.0
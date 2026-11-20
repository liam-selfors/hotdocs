# hotdocs-criterion: sha256:60a850872e2ba3299f72340f8119350286f54b1d79ba0ef5effe2b0c64033d34
import corpus_graph_builder

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo_root, slug, depends_on=(), realizes=(), uses_var=()):
    text = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: [" + ", ".join(depends_on) + "]\n"
        + "realizes: [" + ", ".join(realizes) + "]\n"
        + "uses_var: [" + ", ".join(uses_var) + "]\n"
        + "sealed: false\n"
        + "---\n"
        + "\n"
        + "# Component " + slug + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A fixture component named " + slug + ".\n"
    )
    write(repo_root / "specs" / "components" / slug / "component.md", text)


def write_capability(repo_root, name):
    upper = name.upper()
    text = (
        "---\n"
        + "id: P-" + upper + "\n"
        + "title: Capability " + upper + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# Capability " + upper + "\n"
        + "\n"
        + "A fixture capability.\n"
    )
    write(repo_root / "specs" / "product" / (name + ".md"), text)


def test_orphan_rates_computed_from_relations(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_capability(repo_root, "one")
    write_capability(repo_root, "two")
    write_component(repo_root, "a", realizes=["P-ONE"])
    write_component(repo_root, "b")
    write_component(repo_root, "c", depends_on=["comp-b"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")

    cap_rate = field(aggregates, "orphan_capability_rate")
    comp_rate = field(aggregates, "orphan_component_rate")

    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert isinstance(comp_rate, (int, float)) and not isinstance(comp_rate, bool)
    assert cap_rate == pytest.approx(0.5)
    assert comp_rate == pytest.approx(1.0 / 3.0)

    # The aggregates are also present in the serialized dict form.
    as_dict = graph.to_dict()
    dict_aggregates = as_dict["aggregates"]
    assert dict_aggregates["orphan_capability_rate"] == pytest.approx(0.5)
    assert dict_aggregates["orphan_component_rate"] == pytest.approx(1.0 / 3.0)


def test_orphan_capability_rate_zero_with_no_capabilities(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(repo_root, "solo")

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")

    cap_rate = field(aggregates, "orphan_capability_rate")
    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert cap_rate == 0.0

    as_dict = graph.to_dict()
    assert as_dict["aggregates"]["orphan_capability_rate"] == 0.0
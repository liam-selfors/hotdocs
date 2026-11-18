# hotdocs-criterion: sha256:b42090f1e4bd502fa45cf3dd8aaa1bd32746e7538368c44749a68bfc7f88f00a
from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _flow(items):
    return "[" + ", ".join(items) + "]"


def _component(repo_root, slug, depends_on=(), realizes=(), uses_var=()):
    text = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: " + _flow(list(depends_on)) + "\n"
        + "realizes: " + _flow(list(realizes)) + "\n"
        + "uses_var: " + _flow(list(uses_var)) + "\n"
        + "sealed: false\n"
        + "---\n"
        + "\n"
        + "# Component " + slug + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A test fixture component named " + slug + ".\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", text)


def _capability(repo_root, name):
    text = (
        "---\n"
        + "id: P-" + name + "\n"
        + "title: Capability " + name + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# Capability " + name + "\n"
        + "\n"
        + "A test fixture capability.\n"
    )
    _write(repo_root / "specs" / "product" / (name.lower() + ".md"), text)


def _aggregates(graph):
    return field(graph, "aggregates")


def test_orphan_rates_computed_corpus_wide(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "specs" / "vars").mkdir(parents=True)

    _capability(repo_root, "ONE")
    _capability(repo_root, "TWO")
    _component(repo_root, "a", realizes=["P-ONE"])
    _component(repo_root, "b")
    _component(repo_root, "c", depends_on=["comp-b"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = _aggregates(graph)

    cap_rate = field(aggregates, "orphan_capability_rate")
    comp_rate = field(aggregates, "orphan_component_rate")

    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert isinstance(comp_rate, (int, float)) and not isinstance(comp_rate, bool)
    assert cap_rate == pytest.approx(0.5)
    assert comp_rate == pytest.approx(1.0 / 3.0)


def test_orphan_capability_rate_zero_with_no_capabilities(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "specs" / "product").mkdir(parents=True)
    (repo_root / "specs" / "vars").mkdir(parents=True)

    _component(repo_root, "solo")

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = _aggregates(graph)

    cap_rate = field(aggregates, "orphan_capability_rate")
    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert cap_rate == 0.0
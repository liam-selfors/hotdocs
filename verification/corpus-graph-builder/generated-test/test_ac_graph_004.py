import corpus_graph_builder

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _flow(items):
    return "[" + ", ".join(items) + "]"


def _component(repo_root: Path, slug: str, depends_on=(), realizes=(), uses_var=()):
    text = (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {slug}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"depends_on: {_flow(depends_on)}\n"
        f"realizes: {_flow(realizes)}\n"
        f"uses_var: {_flow(uses_var)}\n"
        "sealed: false\n"
        "---\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Synthetic fixture component {slug} for orphan-rate aggregation.\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", text)


def _capability(repo_root: Path, name: str):
    upper = name.upper()
    text = (
        "---\n"
        f"id: P-{upper}\n"
        f"title: Capability {upper}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        f"# P-{upper}\n"
        "\n"
        f"Synthetic capability {upper}.\n"
    )
    _write(repo_root / "specs" / "product" / f"{name}.md", text)


def _aggregates(graph):
    return field(graph, "aggregates")


def test_orphan_rates_computed_corpus_wide(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _capability(repo_root, "one")
    _capability(repo_root, "two")
    _component(repo_root, "a", realizes=["P-ONE"])
    _component(repo_root, "b")
    _component(repo_root, "c", depends_on=["comp-b"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = _aggregates(graph)
    cap_rate = field(aggregates, "orphan_capability_rate")
    comp_rate = field(aggregates, "orphan_component_rate")

    # Actual computed numeric values, not per-node flags.
    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert isinstance(comp_rate, (int, float)) and not isinstance(comp_rate, bool)

    # P-TWO has no incoming realizes edge: 1 of 2 capabilities orphaned.
    assert cap_rate == pytest.approx(0.5)
    # Only comp-c has neither an incoming depends_on nor an outgoing realizes.
    assert comp_rate == pytest.approx(1 / 3)

    # The serialized form carries the same aggregate values.
    as_dict = graph.to_dict()
    dict_aggs = field(as_dict, "aggregates")
    assert field(dict_aggs, "orphan_capability_rate") == pytest.approx(0.5)
    assert field(dict_aggs, "orphan_component_rate") == pytest.approx(1 / 3)

    # build_corpus_graph writes nothing.
    assert not (repo_root / "verification" / "corpus-graph.json").exists()


def test_orphan_capability_rate_zero_with_no_capabilities(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _component(repo_root, "solo")

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = _aggregates(graph)
    cap_rate = field(aggregates, "orphan_capability_rate")

    assert isinstance(cap_rate, (int, float)) and not isinstance(cap_rate, bool)
    assert cap_rate == 0.0

    as_dict = graph.to_dict()
    assert field(field(as_dict, "aggregates"), "orphan_capability_rate") == 0.0
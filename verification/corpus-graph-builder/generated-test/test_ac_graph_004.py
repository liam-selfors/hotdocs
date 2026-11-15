import corpus_graph_builder

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str, depends_on=(), realizes=(), uses_var=()):
    def flow(items):
        return "[" + ", ".join(items) + "]"

    upper = slug.upper()
    _write(
        repo_root / "specs" / "components" / slug / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {upper}\n"
        "status: draft\n"
        f"owners: [team-{slug}]\n"
        f"depends_on: {flow(depends_on)}\n"
        f"realizes: {flow(realizes)}\n"
        f"uses_var: {flow(uses_var)}\n"
        "sealed: false\n"
        "---\n"
        "\n"
        f"# Component {upper}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Does the work of component {slug}.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "requirements" / f"R-{upper}-001.md",
        f"**R-{upper}-001** — The component MUST do its work.\n",
    )
    _write(
        repo_root / "specs" / "components" / slug / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the component exists\n"
        "When it runs\n"
        "Then it does its work\n"
        "```\n",
    )


def _capability(repo_root: Path, name: str):
    _write(
        repo_root / "specs" / "product" / f"{name.lower()}.md",
        "---\n"
        f"id: P-{name.upper()}\n"
        f"title: Capability {name}\n"
        "status: draft\n"
        "owners: [product-team]\n"
        "---\n"
        "\n"
        f"# Capability {name}\n"
        "\n"
        "A capability.\n",
    )


def _aggregates(graph):
    return field(graph, "aggregates")


def test_orphan_rates_computed_for_mixed_corpus(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

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
    assert comp_rate == pytest.approx(1 / 3)

    # The serialized form carries the same computed values.
    as_dict = graph.to_dict()
    assert as_dict["aggregates"]["orphan_capability_rate"] == pytest.approx(0.5)
    assert as_dict["aggregates"]["orphan_component_rate"] == pytest.approx(1 / 3)


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
    assert as_dict["aggregates"]["orphan_capability_rate"] == 0.0
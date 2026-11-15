"""AC-GRAPH-005: the corpus graph's aggregates include the orphan-var rate.

Covers: R-GRAPH-005
"""

from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, uses_var: list[str]) -> None:
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    uses = "[" + ", ".join(uses_var) + "]"
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {slug}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        f"uses_var: {uses}\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        "\n"
        f"# Component {slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small synthetic component used as a graph fixture.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n"
        "\n"
        f"**R-{upper}-001** — The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )


def _write_var(repo_root: Path, var_id: str) -> None:
    _write(
        repo_root / "specs" / "vars" / f"{var_id}.md",
        "---\n"
        f"id: {var_id}\n"
        f"title: {var_id}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        f"# {var_id}\n"
        "\n"
        "A synthetic var declaration.\n",
    )


def test_orphan_var_rate_is_half_when_one_of_two_vars_is_used(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_var(repo_root, "VAR-ONE")
    _write_var(repo_root, "VAR-TWO")
    _write_component(repo_root, "a", ["VAR-ONE"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")
    assert isinstance(rate, float)
    assert rate == pytest.approx(0.5)

    # The same value is exposed through the serialized shape.
    as_dict = graph.to_dict()
    assert as_dict["aggregates"]["orphan_var_rate"] == pytest.approx(0.5)


def test_orphan_var_rate_is_zero_with_no_vars_directory(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "a", [])
    assert not (repo_root / "specs" / "vars").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")
    assert isinstance(rate, float)
    assert rate == 0.0

    as_dict = graph.to_dict()
    assert as_dict["aggregates"]["orphan_var_rate"] == 0.0
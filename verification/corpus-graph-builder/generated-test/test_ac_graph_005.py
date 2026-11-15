"""AC-GRAPH-005: the corpus graph carries orphan_var_rate as a computed aggregate."""

from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root: Path, slug: str, uses_var: list[str]) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    uses = ", ".join(uses_var)
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {slug.upper()}\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        f"uses_var: [{uses}]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        "\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A synthetic fixture component.\n",
    )
    req_id = f"R-{slug.upper()}-001"
    ac_id = f"AC-{slug.upper()}-001"
    _write(
        comp_dir / "requirements" / f"{req_id}.md",
        f"**{req_id}** — The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"{ac_id}.md",
        f"# {ac_id}\n"
        "\n"
        f"Covers: {req_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )


def _write_var(repo_root: Path, name: str) -> None:
    _write(
        repo_root / "specs" / "vars" / f"{name.lower()}.md",
        "---\n"
        f"id: VAR-{name}\n"
        f"title: Var {name}\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        f"# VAR-{name}\n"
        "\n"
        "A synthetic fixture var.\n",
    )


def _orphan_var_rate(graph):
    aggregates = field(graph, "aggregates")
    return field(aggregates, "orphan_var_rate")


def test_orphan_var_rate_is_half_when_one_of_two_vars_used(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_var(repo_root, "ONE")
    _write_var(repo_root, "TWO")
    _write_component(repo_root, "a", ["VAR-ONE"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    rate = _orphan_var_rate(graph)
    assert isinstance(rate, (int, float)) and not isinstance(rate, bool)
    assert rate == pytest.approx(0.5)


def test_orphan_var_rate_is_zero_with_no_vars_directory(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "a", [])
    assert not (repo_root / "specs" / "vars").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    rate = _orphan_var_rate(graph)
    assert isinstance(rate, (int, float)) and not isinstance(rate, bool)
    assert rate == pytest.approx(0.0)
import corpus_graph_builder

from pathlib import Path

import pytest


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
        f"title: Fixture component {slug}\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        f"uses_var: [{uses}]\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used to exercise the corpus graph.\n",
    )
    upper = slug.upper()
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"**R-{upper}-001** — The component MUST exist as a fixture.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the fixture component\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )


def _write_var(repo_root: Path, var_id: str) -> None:
    _write(
        repo_root / "specs" / "vars" / f"{var_id}.md",
        "---\n"
        f"id: {var_id}\n"
        f"title: Fixture var {var_id}\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "---\n"
        f"# {var_id}\n"
        "\n"
        "A fixture variable declaration.\n",
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
    assert rate == pytest.approx(0.5)


def test_orphan_var_rate_is_zero_with_no_vars_directory(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "a", [])
    assert not (repo_root / "specs" / "vars").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")
    assert rate == pytest.approx(0.0)
    assert float(rate) == 0.0
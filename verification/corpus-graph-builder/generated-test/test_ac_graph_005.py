# hotdocs-criterion: sha256:fa1e8be7ea1e64e65c4b11a64736965c447f0acf8ead6a28fa0c3bf652d75406
from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_component(repo_root, slug, uses_var):
    text = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug.upper() + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: [" + ", ".join(uses_var) + "]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# Component " + slug.upper() + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A fixture component used to test the orphan-var rate.\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", text)


def _write_var(repo_root, var_id):
    text = (
        "---\n"
        + "id: " + var_id + "\n"
        + "title: Var " + var_id + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# " + var_id + "\n"
        + "\n"
        + "A fixture var declaration.\n"
    )
    _write(repo_root / "specs" / "vars" / (var_id + ".md"), text)


def test_orphan_var_rate_two_of_three(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for var_id in ["VAR-ONE", "VAR-TWO", "VAR-THREE"]:
        _write_var(repo_root, var_id)
    _write_component(repo_root, "a", ["VAR-ONE"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")
    assert rate == pytest.approx(2 / 3)


def test_orphan_var_rate_zero_without_vars_directory(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_component(repo_root, "a", [])
    assert not (repo_root / "specs" / "vars").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")
    assert rate == 0.0
    assert isinstance(rate, float)
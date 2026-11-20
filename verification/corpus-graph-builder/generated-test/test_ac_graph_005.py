# hotdocs-criterion: sha256:f3af5488bdd34d38c05437560bd446f16a5675a04188761602dfcb9601234c93
import corpus_graph_builder

from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_component(repo_root, slug, uses_var):
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
        + "A fixture component.\n"
    )
    write(repo_root / "specs" / "components" / slug / "component.md", text)


def write_var(repo_root, var_id):
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
        + "A fixture var.\n"
    )
    write(repo_root / "specs" / "vars" / (var_id + ".md"), text)


def test_orphan_var_rate_half_when_one_of_two_vars_unused(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_var(repo_root, "VAR-ONE")
    write_var(repo_root, "VAR-TWO")
    write_component(repo_root, "a", ["VAR-ONE"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")

    assert isinstance(rate, float)
    assert rate == pytest.approx(0.5)


def test_orphan_var_rate_zero_without_vars_directory(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(repo_root, "a", [])
    assert not (repo_root / "specs" / "vars").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")

    assert isinstance(rate, float)
    assert rate == 0.0


def test_orphan_var_rate_in_serialized_graph(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_var(repo_root, "VAR-ONE")
    write_var(repo_root, "VAR-TWO")
    write_component(repo_root, "a", ["VAR-ONE"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    data = graph.to_dict()

    assert data["aggregates"]["orphan_var_rate"] == pytest.approx(0.5)
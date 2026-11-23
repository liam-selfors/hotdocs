# hotdocs-criterion: sha256:7c0d157e5a3bb918ec14b9f01eec3c4f7d4ad5580957a23fc1e2dcbdf2ee4f49
from pathlib import Path

import pytest

import corpus_graph_builder


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
        + "A fixture component used to test orphan-var aggregates.\n"
    )
    write(repo_root / "specs" / "components" / slug / "component.md", text)


def write_var(repo_root, name):
    text = (
        "---\n"
        + "id: VAR-" + name + "\n"
        + "title: Var " + name + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n"
        + "\n"
        + "# VAR-" + name + "\n"
        + "\n"
        + "A fixture var declaration.\n"
    )
    write(repo_root / "specs" / "vars" / (name + ".md"), text)


def orphan_var_rate(graph):
    aggregates = field(graph, "aggregates")
    return field(aggregates, "orphan_var_rate")


def test_orphan_var_rate_is_half_with_one_of_two_vars_used(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_var(repo_root, "ONE")
    write_var(repo_root, "TWO")
    write_component(repo_root, "a", ["VAR-ONE"])

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    rate = orphan_var_rate(graph)
    assert isinstance(rate, (int, float)) and not isinstance(rate, bool)
    assert rate == pytest.approx(0.5)


def test_orphan_var_rate_is_zero_without_vars_directory(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component(repo_root, "a", [])
    assert not (repo_root / "specs" / "vars").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    rate = orphan_var_rate(graph)
    assert isinstance(rate, (int, float)) and not isinstance(rate, bool)
    assert rate == 0.0
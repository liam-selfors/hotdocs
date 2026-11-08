import pathlib

import pytest

import corpus_graph_builder


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_orphan_var_rate_half_when_one_of_two_vars_unused(tmp_path):
    repo_root = tmp_path / "corpus"

    _write(
        repo_root / "specs" / "vars" / "one.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "A test var.\n",
    )
    _write(
        repo_root / "specs" / "vars" / "two.md",
        "---\n"
        "id: VAR-TWO\n"
        "title: Var Two\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "Another test var.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/comp-a/\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: [VAR-ONE]\n"
        "---\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Exercises a single var dependency.\n",
    )

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = _field(graph, "aggregates")
    orphan_var_rate = _field(aggregates, "orphan_var_rate")

    assert orphan_var_rate == 0.5


def test_orphan_var_rate_zero_when_no_vars_directory(tmp_path):
    repo_root = tmp_path / "corpus_no_vars"
    repo_root.mkdir(parents=True)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    aggregates = _field(graph, "aggregates")
    orphan_var_rate = _field(aggregates, "orphan_var_rate")

    assert orphan_var_rate == 0.0
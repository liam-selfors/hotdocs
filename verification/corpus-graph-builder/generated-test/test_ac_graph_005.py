# hotdocs-criterion: sha256:be54039464f819b1c3f01efba10f1b550e78f887bccae22329081d121f390070
from pathlib import Path

import pytest

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, uses_var):
    return (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug + "\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: [" + ", ".join(uses_var) + "]\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# comp-" + slug + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A test fixture component.\n"
    )


def var_md(var_id):
    return (
        "---\n"
        + "id: " + var_id + "\n"
        + "title: " + var_id + " title\n"
        + "status: draft\n"
        + "owners: [test-team]\n"
        + "---\n"
        + "\n"
        + "# " + var_id + "\n"
        + "\n"
        + "A test fixture var.\n"
    )


def test_orphan_var_rate_half_when_one_of_two_vars_used(tmp_path):
    repo_root = tmp_path / "repo"
    write(repo_root / "specs" / "vars" / "VAR-ONE.md", var_md("VAR-ONE"))
    write(repo_root / "specs" / "vars" / "VAR-TWO.md", var_md("VAR-TWO"))
    write(
        repo_root / "specs" / "components" / "a" / "component.md",
        component_md("a", ["VAR-ONE"]),
    )

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")

    assert rate == pytest.approx(0.5)


def test_orphan_var_rate_zero_with_no_vars_directory(tmp_path):
    repo_root = tmp_path / "repo"
    write(
        repo_root / "specs" / "components" / "a" / "component.md",
        component_md("a", []),
    )
    assert not (repo_root / "specs" / "vars").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    aggregates = field(graph, "aggregates")
    rate = field(aggregates, "orphan_var_rate")

    assert rate == 0.0
import corpus_loader

from pathlib import Path

import duckdb
import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a small demo thing used by the fixture.\n",
    )

    _write(
        specs / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: Demo decision\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# D1 — Demo decision\n"
        "\n"
        "A placeholder decision for the fixture.\n",
    )

    _write(
        specs / "vars" / "VAR-WIDGET-PATH.md",
        "---\n"
        "id: VAR-WIDGET-PATH\n"
        "title: Widget path\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "\n"
        "# VAR-WIDGET-PATH\n"
        "\n"
        "A placeholder variable declaration.\n",
    )

    comp = specs / "components" / "widget"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides a widget for the fixture corpus.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n",
    )
    _write(
        comp / "requirements" / "R-WIDGET-001.md",
        "**R-WIDGET-001** — `make_widget()` MUST return a widget.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When make_widget() runs\n"
        "Then it returns a widget\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget() -> Widget\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def test_ac_corpus_002_graph_is_duckdb_with_one_component_node(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)

    graph = field(corpus, "graph")
    assert graph is not None
    assert isinstance(graph, duckdb.DuckDBPyConnection)

    row = graph.execute(
        "SELECT count(*) FROM nodes WHERE kind = 'component'"
    ).fetchone()
    assert row is not None
    assert row[0] == 1
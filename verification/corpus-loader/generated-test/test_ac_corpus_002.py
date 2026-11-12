"""AC-CORPUS-002: load_corpus(repo_root).graph is a DuckDB connection whose
`nodes` view (from graph-query-engine's load_views) reports exactly one
component for a single-component corpus."""

from pathlib import Path

import duckdb
import pytest

import corpus_loader


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_single_component_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — the single thing this fixture corpus describes.\n",
    )

    comp_dir = specs / "components" / "widget"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Produces widgets for the fixture corpus.\n",
    )
    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — `make_widget()` MUST return a widget.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When make_widget() runs\n"
        "Then a widget is returned\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget() -> Widget\n"
        "```\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "- None beyond the standard library.\n",
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _build_single_component_corpus(root)
    return root


def test_graph_is_duckdb_connection_with_one_component_node(repo_root):
    corpus = corpus_loader.load_corpus(repo_root)
    assert corpus is not None

    graph = _field(corpus, "graph")
    assert graph is not None, "Corpus.graph must never be None"
    assert isinstance(graph, duckdb.DuckDBPyConnection), (
        f"Corpus.graph must be a DuckDB connection, got {type(graph)!r}"
    )

    row = graph.execute(
        "SELECT count(*) FROM nodes WHERE kind = 'component'"
    ).fetchone()
    assert row is not None
    assert row[0] == 1, f"expected exactly 1 component node, got {row[0]}"


def test_graph_component_node_is_the_fixture_component(repo_root):
    corpus = corpus_loader.load_corpus(repo_root)
    graph = _field(corpus, "graph")
    assert isinstance(graph, duckdb.DuckDBPyConnection)

    rows = graph.execute(
        "SELECT id FROM nodes WHERE kind = 'component'"
    ).fetchall()
    assert [r[0] for r in rows] == ["comp-widget"]
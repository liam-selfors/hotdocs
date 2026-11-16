"""AC-CORPUS-002 (covers R-CORPUS-002).

Given a small synthetic corpus with exactly one component,
When load_corpus(repo_root) runs,
Then corpus.graph is a DuckDB connection, and
  "SELECT count(*) FROM nodes WHERE kind = 'component'" on it returns 1.
"""

from pathlib import Path

import duckdb

import corpus_loader


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** — a small synthetic thing used only by this test.\n",
    )

    comp_dir = specs / "components" / "widget"

    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/widget\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A synthetic component used only as a test fixture.\n",
    )

    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — `widget()` MUST return the integer 1.\n",
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
        "When widget() runs\n"
        "Then it returns 1\n"
        "```\n",
    )

    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "widget() -> int\n"
        "```\n"
        "\n"
        "Returns 1.\n",
    )

    _write(
        comp_dir / "constraints.md",
        "# Constraints\n"
        "\n"
        "None beyond the requirements.\n",
    )


def test_ac_corpus_002_graph_is_duckdb_connection_with_one_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)

    graph = _field(corpus, "graph")
    assert graph is not None, "corpus.graph must never be None"
    assert isinstance(graph, duckdb.DuckDBPyConnection), (
        f"corpus.graph must be a DuckDB connection, got {type(graph)!r}"
    )

    try:
        row = graph.execute(
            "SELECT count(*) FROM nodes WHERE kind = 'component'"
        ).fetchone()
        assert row is not None
        assert row[0] == 1, f"expected exactly 1 component node, got {row[0]}"
    finally:
        try:
            graph.close()
        except Exception:
            pass
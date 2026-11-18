# hotdocs-criterion: sha256:85ee80d0c296973bcdf40e75ed8e76498d5a614d8cf53ed46e8b467aa24e4b65
from pathlib import Path

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n"
        + "- **Widget** — a small fixture thing used only in tests.\n",
    )
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [alice]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Foo is a fixture component that does one small thing.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n"
        + "**R-FOO-001** — `foo()` MUST return the string `foo`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\n"
        + "Covers: R-FOO-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given nothing\n"
        + "When foo() runs\n"
        + "Then it returns \"foo\"\n"
        + "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n"
        + "```\n"
        + "foo() -> str\n"
        + "```\n\n"
        + "Returns `foo`.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n\n"
        + "None.\n",
    )


def test_ac_corpus_002_graph_is_duckdb_connection_with_one_component(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)

    graph = field(corpus, "graph")
    assert graph is not None

    import duckdb

    assert isinstance(graph, duckdb.DuckDBPyConnection)

    row = graph.execute(
        "SELECT count(*) FROM nodes WHERE kind = 'component'"
    ).fetchone()
    assert row is not None
    assert row[0] == 1
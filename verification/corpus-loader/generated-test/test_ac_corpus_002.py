# hotdocs-criterion: sha256:ebd3f75a500270a63a1a1508adea17d4ae3f1a072281092030cb5bcf3e286ee8
from pathlib import Path

import duckdb

import corpus_loader


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    specs = repo_root / "specs"
    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo does a small fixture thing.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo` MUST return a value.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When foo runs\n"
        "Then it returns a value\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo() -> int\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a fixture term.\n",
    )


def test_ac_corpus_002(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    corpus = corpus_loader.load_corpus(repo_root)
    graph = field(corpus, "graph")

    assert graph is not None
    assert isinstance(graph, duckdb.DuckDBPyConnection)

    row = graph.execute(
        "SELECT count(*) FROM nodes WHERE kind = 'component'"
    ).fetchone()
    assert row is not None
    assert row[0] == 1
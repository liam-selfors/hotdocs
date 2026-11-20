# hotdocs-criterion: sha256:7876396b7b927595e6c08d5f815520632a3c9b30dab1c57268c2b20c5ee4c4d7
from pathlib import Path

import corpus_graph_builder


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "\n"
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "**R-A-001** — Component A MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "Given comp-a\n"
        "Then it exists\n",
    )


def _snapshot(repo_root):
    snap = {}
    for p in sorted(repo_root.rglob("*")):
        if p.is_file():
            snap[p.relative_to(repo_root).as_posix()] = p.read_bytes()
    return snap


def test_ac_graph_006_only_output_file_is_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    before = _snapshot(repo_root)
    assert before, "fixture corpus should contain files"

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = _snapshot(repo_root)
    assert after_build == before, "build_corpus_graph must not add or change any file"

    result = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected = repo_root / "verification" / "corpus-graph.json"
    assert Path(result).resolve() == expected.resolve()
    assert expected.is_file()

    after_write = _snapshot(repo_root)

    added = sorted(set(after_write) - set(before))
    removed = sorted(set(before) - set(after_write))
    changed = sorted(
        k for k in set(before) & set(after_write) if before[k] != after_write[k]
    )

    assert removed == []
    assert changed == []
    assert added == ["verification/corpus-graph.json"]
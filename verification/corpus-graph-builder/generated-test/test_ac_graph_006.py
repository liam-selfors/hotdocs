from pathlib import Path

import corpus_graph_builder


def _write_fixture(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "a"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "# Component A\n\n"
        "## Purpose\n\n"
        "A fixture component for testing.\n",
        encoding="utf-8",
    )


def _snapshot(repo_root: Path) -> dict:
    snap = {}
    for p in repo_root.rglob("*"):
        if p.is_file():
            snap[p.relative_to(repo_root)] = p.read_bytes()
    return snap


def test_build_writes_nothing_and_write_targets_exact_output_path(tmp_path):
    repo_root = tmp_path
    _write_fixture(repo_root)

    before = _snapshot(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = _snapshot(repo_root)
    assert after_build == before, "build_corpus_graph must not add or change any file"

    result_path = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected_path = repo_root / "verification" / "corpus-graph.json"
    assert result_path == expected_path

    after_write = _snapshot(repo_root)

    new_paths = set(after_write) - set(after_build)
    removed_paths = set(after_build) - set(after_write)
    changed_paths = {
        rel
        for rel in after_build
        if rel in after_write and after_write[rel] != after_build[rel]
    }

    assert removed_paths == set()
    assert changed_paths == set()
    assert new_paths == {Path("verification") / "corpus-graph.json"}
    assert expected_path.is_file()
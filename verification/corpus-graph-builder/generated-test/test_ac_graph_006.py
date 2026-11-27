# hotdocs-criterion: sha256:24dd1bce934e6da87cd62a5efcbc94026f60b4c7127ec9f1ed3b0fd3ff1e1864
from pathlib import Path

import corpus_graph_builder


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    component_md = (
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
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
        "A small fixture component.\n"
    )
    _write(repo_root / "specs" / "components" / "a" / "component.md", component_md)


def _snapshot(repo_root):
    snap = {}
    for p in repo_root.rglob("*"):
        if p.is_file():
            rel = p.relative_to(repo_root).as_posix()
            snap[rel] = p.read_bytes()
    return snap


def _diff(before, after):
    added = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {k for k in set(before) & set(after) if before[k] != after[k]}
    return added, removed, changed


def test_ac_graph_006(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    before = _snapshot(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = _snapshot(repo_root)
    added, removed, changed = _diff(before, after_build)
    assert added == set(), "build_corpus_graph added files: " + repr(sorted(added))
    assert removed == set(), "build_corpus_graph removed files: " + repr(sorted(removed))
    assert changed == set(), "build_corpus_graph changed files: " + repr(sorted(changed))

    result = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected = repo_root / "verification" / "corpus-graph.json"
    assert Path(result).resolve() == expected.resolve()
    assert expected.is_file()

    after_write = _snapshot(repo_root)
    added, removed, changed = _diff(after_build, after_write)
    assert removed == set(), "write_corpus_graph removed files: " + repr(sorted(removed))
    assert added | changed == {"verification/corpus-graph.json"}, (
        "files added or changed: " + repr(sorted(added | changed))
    )
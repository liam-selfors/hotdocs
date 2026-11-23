# hotdocs-criterion: sha256:466c0948440f638c6cb6ebd371502d4082bb55c2eaf0a5d657aac5a36cceb0a2
from pathlib import Path

import corpus_graph_builder


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(
        comp_dir / "component.md",
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
        "A small fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "**R-A-001** — Component A MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does one thing\n"
        "```\n",
    )


def _snapshot(repo_root):
    result = {}
    for p in sorted(repo_root.rglob("*")):
        if p.is_file():
            result[p.relative_to(repo_root).as_posix()] = p.read_bytes()
    return result


def _changed(before, after):
    changed = set()
    for key, data in after.items():
        if key not in before or before[key] != data:
            changed.add(key)
    return changed


def test_ac_graph_006_only_corpus_graph_json_is_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    before = _snapshot(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = _snapshot(repo_root)
    assert _changed(before, after_build) == set(), (
        "build_corpus_graph added or changed files: "
        + repr(sorted(_changed(before, after_build)))
    )

    returned = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected = repo_root / "verification" / "corpus-graph.json"
    assert Path(returned).resolve() == expected.resolve()
    assert expected.is_file()

    after_write = _snapshot(repo_root)
    assert _changed(after_build, after_write) == {"verification/corpus-graph.json"}, (
        "write_corpus_graph added or changed files: "
        + repr(sorted(_changed(after_build, after_write)))
    )
import os
from pathlib import Path

import corpus_graph_builder


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _make_corpus(repo_root: Path) -> None:
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


def _snapshot(repo_root: Path) -> dict:
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(repo_root).as_posix()
            snap[rel] = p.read_bytes()
    return snap


def _changed(before: dict, after: dict) -> set:
    changed = set()
    for rel, data in after.items():
        if rel not in before or before[rel] != data:
            changed.add(rel)
    for rel in before:
        if rel not in after:
            changed.add(rel)
    return changed


def test_ac_graph_006_only_corpus_graph_json_written(tmp_path, monkeypatch):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)
    monkeypatch.chdir(repo_root)

    before = _snapshot(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = _snapshot(repo_root)
    assert _changed(before, after_build) == set(), (
        "build_corpus_graph added or changed files: "
        f"{sorted(_changed(before, after_build))}"
    )

    result = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected = repo_root / "verification" / "corpus-graph.json"
    assert Path(result) == expected

    after_write = _snapshot(repo_root)
    assert _changed(after_build, after_write) == {"verification/corpus-graph.json"}
    assert expected.is_file()
import os
from pathlib import Path

import corpus_graph_builder


def _snapshot(root: Path) -> dict:
    """Map every file under root (relative path, '/' separators) to its bytes."""
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(root).as_posix()
            snap[rel] = full.read_bytes()
    return snap


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
        "A small fixture component used to check which files get written.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "**R-A-001** — Component A MUST exist as a fixture.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a fixture\n"
        "When it is read\n"
        "Then it exists\n"
        "```\n",
    )


def _diff(before: dict, after: dict) -> set:
    changed = set()
    for rel, data in after.items():
        if rel not in before or before[rel] != data:
            changed.add(rel)
    for rel in before:
        if rel not in after:
            changed.add(rel)
    return changed


def test_build_writes_nothing_and_write_writes_only_corpus_graph_json(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)

    before_build = _snapshot(repo_root)
    assert before_build, "fixture should contain files"

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = _snapshot(repo_root)
    assert _diff(before_build, after_build) == set(), (
        "build_corpus_graph must not add or change any file, but changed: "
        f"{sorted(_diff(before_build, after_build))}"
    )

    returned = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected_path = repo_root / "verification" / "corpus-graph.json"
    assert Path(returned) == expected_path

    after_write = _snapshot(repo_root)
    changed = _diff(after_build, after_write)
    assert changed == {"verification/corpus-graph.json"}, (
        f"expected only verification/corpus-graph.json to be added/changed, got {sorted(changed)}"
    )
    assert expected_path.is_file()
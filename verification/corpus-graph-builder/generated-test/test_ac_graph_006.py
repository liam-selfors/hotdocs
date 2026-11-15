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
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used to check which files get written.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "# R-A-001\n"
        "\n"
        "**R-A-001** — Component A MUST exist.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given component A\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "noop() -> None\n"
        "```\n",
    )
    _write(repo_root / "legacy" / "a" / "a.py", "def noop():\n    return None\n")


def _snapshot(repo_root: Path) -> dict:
    snap = {}
    for dirpath, _dirnames, filenames in os.walk(repo_root):
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(repo_root).as_posix()
            st = p.stat()
            snap[rel] = (p.read_bytes(), st.st_mtime_ns, st.st_size)
    return snap


def _diff(before: dict, after: dict) -> set:
    changed = set()
    for rel in set(before) | set(after):
        if rel not in before or rel not in after:
            changed.add(rel)
        elif before[rel] != after[rel]:
            changed.add(rel)
    return changed


def test_ac_graph_006_only_corpus_graph_json_is_written(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir()
    _make_corpus(repo_root)

    before = _snapshot(repo_root)
    assert before, "fixture should contain files"

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = _snapshot(repo_root)
    changed_by_build = _diff(before, after_build)
    assert changed_by_build == set(), (
        f"build_corpus_graph must write nothing, but changed: {sorted(changed_by_build)}"
    )

    result = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected = repo_root / "verification" / "corpus-graph.json"
    assert result is not None
    assert Path(result) == expected or Path(result).resolve() == expected.resolve(), (
        f"write_corpus_graph returned {result!r}, expected {expected!r}"
    )
    assert expected.is_file()

    after_write = _snapshot(repo_root)
    changed_by_write = _diff(after_build, after_write)
    assert changed_by_write == {"verification/corpus-graph.json"}, (
        f"only verification/corpus-graph.json may be added or changed, "
        f"got: {sorted(changed_by_write)}"
    )
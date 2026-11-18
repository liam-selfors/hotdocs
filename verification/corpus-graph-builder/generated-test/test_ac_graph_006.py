# hotdocs-criterion: sha256:88b33cb2adef2963b230cb8e35a8c4babf30c01ab67c69e95f468d46cb20de8a
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    component_md = (
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
        "A tiny fixture component.\n"
    )
    write(repo_root / "specs" / "components" / "a" / "component.md", component_md)
    write(
        repo_root / "specs" / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n\n**R-A-001** - Component A MUST exist.\n",
    )
    write(
        repo_root / "specs" / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\nCovers: R-A-001\nKind: llm-judge\n\nComponent A exists.\n",
    )


def snapshot(repo_root):
    result = {}
    for p in sorted(repo_root.rglob("*")):
        if p.is_file():
            result[p.relative_to(repo_root).as_posix()] = p.read_bytes()
    return result


def changed_files(before, after):
    changed = set()
    for key, data in after.items():
        if key not in before or before[key] != data:
            changed.add(key)
    for key in before:
        if key not in after:
            changed.add(key)
    return changed


def test_only_verification_corpus_graph_json_is_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    before = snapshot(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    after_build = snapshot(repo_root)
    assert changed_files(before, after_build) == set(), (
        "build_corpus_graph must write nothing"
    )

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes

    returned = corpus_graph_builder.write_corpus_graph(graph, repo_root)

    expected = repo_root / "verification" / "corpus-graph.json"
    assert Path(returned).resolve() == expected.resolve()
    assert expected.is_file()

    after_write = snapshot(repo_root)
    assert changed_files(after_build, after_write) == {
        "verification/corpus-graph.json"
    }
    assert changed_files(before, after_write) == {"verification/corpus-graph.json"}
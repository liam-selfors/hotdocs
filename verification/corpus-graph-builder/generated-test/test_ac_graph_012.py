# hotdocs-criterion: sha256:46f707d3fc088c32830f44d545601a71f40098d627dfe591370f1f0c4b8de2ff
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    component_md = (
        "---\n"
        + "id: comp-a\n"
        + "title: Component A\n"
        + "status: draft\n"
        + "owners: [" + "\u00e9quipe" + "]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/a/\n"
        + "---\n"
        + "\n"
        + "# Component A\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A fixture component owned by a team with a non-ASCII name.\n"
    )
    _write(repo_root / "specs" / "components" / "a" / "component.md", component_md)
    _write(
        repo_root / "specs" / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n\n**R-A-001** \u2014 Component A MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\nCovers: R-A-001\nKind: llm-judge\n\nComponent A exists.\n",
    )


def test_ac_graph_012_to_json_bytes_is_ascii_escaped_sorted_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    # Sanity: the owners value round-trips into the graph's dict form.
    as_dict = graph.to_dict()
    nodes = field(as_dict, "nodes")
    assert "comp-a" in nodes
    assert field(nodes["comp-a"], "owners") == ["\u00e9quipe"]

    data = graph.to_json_bytes()
    assert isinstance(data, bytes)

    expected = (
        json.dumps(graph.to_dict(), sort_keys=True, indent=2, ensure_ascii=True)
        + "\n"
    ).encode("utf-8")
    assert data == expected

    assert b"\\u00e9quipe" in data
    assert "\u00e9".encode("utf-8") not in data
    # Every byte is ASCII, so no raw "é" in any encoding is present.
    data.decode("ascii")
    assert "\u00e9" not in data.decode("utf-8")

    # Determinism: building again from the same inputs yields identical bytes.
    again = corpus_graph_builder.build_corpus_graph(repo_root).to_json_bytes()
    assert again == data
# hotdocs-criterion: sha256:7538f7c67765be34dccc00e6748e0f69c0b8232553532e5e4cbd819fd3b6e362
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug):
    return (
        "---\n"
        "id: comp-" + slug + "\n"
        "title: Component " + slug.upper() + "\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/" + slug + "/\n"
        "---\n"
        "\n"
        "# Component " + slug.upper() + "\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component named " + slug + ".\n"
    )


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "components" / "a" / "component.md", _component_md("a"))
    _write(repo_root / "specs" / "components" / "b" / "component.md", _component_md("b"))
    manifest = {
        "generated_at": "2026-11-08T00:19:53Z",
        "verification_report": {"overall": "pass"},
    }
    _write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest, indent=2) + "\n",
    )


def test_corpus_graph_is_deterministic_and_keeps_generated_at_string(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph1 = corpus_graph_builder.build_corpus_graph(repo_root)
    graph2 = corpus_graph_builder.build_corpus_graph(repo_root)

    bytes1 = graph1.to_json_bytes()
    bytes2 = graph2.to_json_bytes()
    assert isinstance(bytes1, bytes)
    assert isinstance(bytes2, bytes)
    assert bytes1 == bytes2

    expected_path = repo_root / "verification" / "corpus-graph.json"

    written1 = corpus_graph_builder.write_corpus_graph(graph1, repo_root)
    assert Path(written1).resolve() == expected_path.resolve()
    file_bytes1 = Path(written1).read_bytes()

    written2 = corpus_graph_builder.write_corpus_graph(graph2, repo_root)
    assert Path(written2).resolve() == expected_path.resolve()
    file_bytes2 = Path(written2).read_bytes()

    assert file_bytes1 == bytes1
    assert file_bytes2 == bytes1
    assert file_bytes1 == file_bytes2

    for raw in (bytes1, bytes2, file_bytes1, file_bytes2):
        data = json.loads(raw.decode("utf-8"))
        nodes = data["nodes"]
        assert "comp-a" in nodes
        assert "comp-b" in nodes
        node_a = nodes["comp-a"]
        provenance = node_a["provenance"]
        assert isinstance(provenance, dict)
        assert provenance["generated_at"] == "2026-11-08T00:19:53Z"
        assert isinstance(provenance["generated_at"], str)
        assert node_a["verification"] == {"overall": "pass"}
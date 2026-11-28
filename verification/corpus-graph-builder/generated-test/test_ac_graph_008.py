# hotdocs-criterion: sha256:1a96d00c2293909c7ce13a9bd910d22df10a7040f21a016fef654e1026b9b11f
import json
from pathlib import Path

import corpus_graph_builder


GENERATED_AT = "2026-11-08T00:19:53Z"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _as_bytes(data):
    if isinstance(data, str):
        return data.encode("utf-8")
    return bytes(data)


def _write_component(repo_root, slug):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    text = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + slug.upper() + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# Component " + slug.upper() + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component named " + slug + ".\n"
    )
    (comp_dir / "component.md").write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write_component(repo_root, "a")
    _write_component(repo_root, "b")
    manifest_dir = repo_root / "verification" / "a"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "generated_at": GENERATED_AT,
        "verification_report": {"overall": "pass"},
    }
    (manifest_dir / ".provenance.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def test_ac_graph_008_deterministic_bytes_and_plain_json_generated_at(tmp_path):
    repo_root = Path(tmp_path)
    _build_fixture(repo_root)

    graph1 = corpus_graph_builder.build_corpus_graph(repo_root)
    graph2 = corpus_graph_builder.build_corpus_graph(repo_root)

    bytes1 = _as_bytes(graph1.to_json_bytes())
    bytes2 = _as_bytes(graph2.to_json_bytes())
    assert bytes1 == bytes2

    path1 = corpus_graph_builder.write_corpus_graph(graph1, repo_root)
    written1 = Path(path1).read_bytes()
    path2 = corpus_graph_builder.write_corpus_graph(graph2, repo_root)
    written2 = Path(path2).read_bytes()

    expected_path = repo_root / "verification" / "corpus-graph.json"
    assert Path(path1).resolve() == expected_path.resolve()
    assert Path(path2).resolve() == expected_path.resolve()

    assert written1 == bytes1
    assert written2 == bytes1

    for data in (bytes1, bytes2, written1, written2):
        doc = json.loads(data.decode("utf-8"))
        nodes = doc["nodes"]
        assert "comp-a" in nodes
        assert "comp-b" in nodes
        node_a = nodes["comp-a"]
        provenance = node_a["provenance"]
        assert isinstance(provenance, dict)
        assert provenance["generated_at"] == GENERATED_AT
        assert isinstance(provenance["generated_at"], str)
        assert node_a["verification"] == {"overall": "pass"}
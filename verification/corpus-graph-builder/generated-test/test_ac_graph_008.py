# hotdocs-criterion: sha256:8c35e49719cf1358ba749f52db5ce8e94c43c494504aa29b22ef67b57d9c49c0
import json
from pathlib import Path

import corpus_graph_builder


def _component_md(slug):
    return (
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
        + "A small fixture component.\n"
    )


def _build_fixture(repo_root):
    for slug in ("a", "b"):
        d = repo_root / "specs" / "components" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "component.md").write_text(_component_md(slug), encoding="utf-8")
    manifest = {
        "generated_at": "2026-11-08T00:19:53Z",
        "verification_report": {"overall": "pass"},
    }
    vdir = repo_root / "verification" / "a"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")


def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_graph_008_deterministic_bytes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph1 = corpus_graph_builder.build_corpus_graph(repo_root)
    graph2 = corpus_graph_builder.build_corpus_graph(repo_root)

    bytes1 = graph1.to_json_bytes()
    bytes2 = graph2.to_json_bytes()
    assert isinstance(bytes1, bytes)
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

    for data in (bytes1, written1, written2):
        loaded = json.loads(data)
        node = loaded["nodes"]["comp-a"]
        provenance = node["provenance"]
        assert provenance["generated_at"] == "2026-11-08T00:19:53Z"
        assert isinstance(provenance["generated_at"], str)
        assert node["verification"] == {"overall": "pass"}
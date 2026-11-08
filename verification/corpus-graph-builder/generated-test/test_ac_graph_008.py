import json
from pathlib import Path

import corpus_graph_builder


def _write_component(repo_root, slug, title):
    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        f"id: comp-{slug}\n"
        f"title: {title}\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        f"source_path: fake-source/{slug}/\n"
        "---\n\n"
        f"# {title}\n\n"
        "## Purpose\n\n"
        f"Fixture component {slug}.\n",
        encoding="utf-8",
    )


def test_build_and_write_corpus_graph_are_deterministic(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    _write_component(repo_root, "a", "Component A")
    _write_component(repo_root, "b", "Component B")

    verification_a_dir = repo_root / "verification" / "a"
    verification_a_dir.mkdir(parents=True, exist_ok=True)
    provenance_content = {
        "generated_at": "2026-11-08T00:19:53Z",
        "verification_report": {"overall": "pass"},
    }
    (verification_a_dir / ".provenance.json").write_text(
        json.dumps(provenance_content), encoding="utf-8"
    )

    graph1 = corpus_graph_builder.build_corpus_graph(repo_root)
    graph2 = corpus_graph_builder.build_corpus_graph(repo_root)

    bytes1 = graph1.to_json_bytes()
    bytes2 = graph2.to_json_bytes()
    assert bytes1 == bytes2

    path1 = corpus_graph_builder.write_corpus_graph(graph1, repo_root)
    written1 = Path(path1).read_bytes()

    path2 = corpus_graph_builder.write_corpus_graph(graph2, repo_root)
    written2 = Path(path2).read_bytes()

    assert written1 == bytes1
    assert written2 == bytes1
    assert written1 == written2

    decoded1 = json.loads(written1)
    decoded2 = json.loads(written2)

    comp_a_node1 = decoded1["nodes"]["comp-a"]
    comp_a_node2 = decoded2["nodes"]["comp-a"]

    provenance1 = comp_a_node1["provenance"]
    provenance2 = comp_a_node2["provenance"]

    assert provenance1["generated_at"] == "2026-11-08T00:19:53Z"
    assert provenance2["generated_at"] == "2026-11-08T00:19:53Z"
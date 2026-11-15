import json
from pathlib import Path

import corpus_graph_builder


GENERATED_AT = "2026-11-08T00:19:53Z"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str, depends_on: str, owner: str) -> None:
    base = repo_root / "specs" / "components" / slug
    upper = slug.upper()
    _write(
        base / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {upper}\n"
        "status: draft\n"
        f"owners: [{owner}]\n"
        f"depends_on: [{depends_on}]\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Component {upper} exists for a determinism fixture.\n",
    )
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"**R-{upper}-001** — Component {upper} MUST do its one thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        f"Given component {upper}\n"
        "When it runs\n"
        "Then it does its one thing\n"
        "```\n",
    )


def _build_fixture(repo_root: Path) -> None:
    _component(repo_root, "a", "", "team-a")
    _component(repo_root, "b", "comp-a", "team-b")
    manifest = {
        "generated_at": GENERATED_AT,
        "verification_report": {"overall": "pass"},
    }
    _write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest, indent=2) + "\n",
    )


def test_ac_graph_008_graph_is_deterministic_and_plain_json(tmp_path):
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

    path1 = corpus_graph_builder.write_corpus_graph(graph1, repo_root)
    written1 = Path(path1).read_bytes()
    path2 = corpus_graph_builder.write_corpus_graph(graph2, repo_root)
    written2 = Path(path2).read_bytes()

    expected_path = repo_root / "verification" / "corpus-graph.json"
    assert Path(path1).resolve() == expected_path.resolve()
    assert Path(path2).resolve() == expected_path.resolve()

    assert written1 == bytes1
    assert written2 == bytes1
    assert written1 == written2

    for raw in (bytes1, bytes2, written1, written2):
        data = json.loads(raw.decode("utf-8"))
        node_a = data["nodes"]["comp-a"]
        provenance = node_a["provenance"]
        assert isinstance(provenance, dict)
        assert provenance["generated_at"] == GENERATED_AT
        assert isinstance(provenance["generated_at"], str)
        assert node_a["verification"] == {"overall": "pass"}
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GENERATED_AT = "2026-11-08T00:19:53Z"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str, depends_on: str) -> None:
    upper = slug.upper()
    base = repo_root / "specs" / "components" / slug
    _write(
        base / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {upper}\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        f"depends_on: {depends_on}\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"A small fixture component named {slug}.\n",
    )
    _write(
        base / "requirements" / f"R-{upper}-001.md",
        f"**R-{upper}-001** — The component MUST do one thing.\n",
    )
    _write(
        base / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an input\n"
        "When the component runs\n"
        "Then it does one thing\n"
        "```\n",
    )


def _make_fixture(repo_root: Path) -> None:
    _component(repo_root, "a", "[]")
    _component(repo_root, "b", "[comp-a]")
    manifest = {
        "generated_at": GENERATED_AT,
        "verification_report": {"overall": "pass"},
    }
    _write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest),
    )


def test_ac_graph_008_graph_is_deterministic_and_plain_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _make_fixture(repo_root)

    graph1 = corpus_graph_builder.build_corpus_graph(repo_root)
    graph2 = corpus_graph_builder.build_corpus_graph(repo_root)

    bytes1 = graph1.to_json_bytes()
    bytes2 = graph2.to_json_bytes()
    assert isinstance(bytes1, bytes)
    assert isinstance(bytes2, bytes)
    assert bytes1 == bytes2

    expected_path = repo_root / "verification" / "corpus-graph.json"

    path1 = corpus_graph_builder.write_corpus_graph(graph1, repo_root)
    assert Path(path1) == expected_path
    written1 = Path(path1).read_bytes()

    path2 = corpus_graph_builder.write_corpus_graph(graph2, repo_root)
    assert Path(path2) == expected_path
    written2 = Path(path2).read_bytes()

    assert written1 == bytes1
    assert written2 == bytes1
    assert written1 == written2

    for raw in (bytes1, bytes2, written1, written2):
        loaded = json.loads(raw)
        node = loaded["nodes"]["comp-a"]
        provenance = node["provenance"]
        assert isinstance(provenance, dict)
        assert isinstance(provenance["generated_at"], str)
        assert provenance["generated_at"] == GENERATED_AT
        assert node["verification"] == {"overall": "pass"}
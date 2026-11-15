import json
from pathlib import Path

import corpus_graph_builder


GENERATED_AT = "2026-11-08T00:19:53Z"


def _component_md(slug, depends_on):
    deps = "[" + ", ".join(depends_on) + "]"
    return (
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {slug.upper()}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"depends_on: {deps}\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        f"source_path: legacy/{slug}/\n"
        "---\n"
        "\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"A small synthetic component named {slug} used as a test fixture.\n"
    )


def _write_component(repo_root, slug, depends_on):
    upper = slug.upper()
    comp_dir = repo_root / "specs" / "components" / slug
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
        _component_md(slug, depends_on), encoding="utf-8"
    )
    (comp_dir / "requirements" / f"R-{upper}-001.md").write_text(
        f"**R-{upper}-001** — The component MUST do one small thing.\n",
        encoding="utf-8",
    )
    (comp_dir / "acceptance" / f"AC-{upper}-001.md").write_text(
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an input\n"
        "When the component runs\n"
        "Then it does the small thing\n"
        "```\n",
        encoding="utf-8",
    )


def _build_fixture(repo_root):
    _write_component(repo_root, "a", [])
    _write_component(repo_root, "b", ["comp-a"])
    manifest_dir = repo_root / "verification" / "a"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / ".provenance.json").write_text(
        json.dumps(
            {
                "generated_at": GENERATED_AT,
                "verification_report": {"overall": "pass"},
            }
        ),
        encoding="utf-8",
    )


def test_ac_graph_008_graph_is_deterministic_and_plain_json(tmp_path):
    repo_root = Path(tmp_path)
    _build_fixture(repo_root)

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
        data = json.loads(raw.decode("utf-8"))
        node = data["nodes"]["comp-a"]
        provenance = node["provenance"]
        assert isinstance(provenance["generated_at"], str)
        assert provenance["generated_at"] == GENERATED_AT
        assert node["verification"] == {"overall": "pass"}
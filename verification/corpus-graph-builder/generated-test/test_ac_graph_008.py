# hotdocs-criterion: sha256:800869d5f7f6154bc666ffceb732fbef6bea09c33d0e9ca86a612449e638f5a7
import json
from pathlib import Path

import corpus_graph_builder


GENERATED_AT = "2026-11-08T00:19:53Z"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root, slug, upper):
    base = repo_root / "specs" / "components" / slug
    text = (
        "---\n"
        + "id: comp-" + slug + "\n"
        + "title: Component " + upper + "\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "sealed: true\n"
        + "source_path: legacy/" + slug + "/\n"
        + "---\n"
        + "\n"
        + "# Component " + upper + "\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "A small fixture component named " + slug + ".\n"
    )
    _write(base / "component.md", text)
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (req_id + ".md"),
        "**" + req_id + "** — The component MUST exist.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: llm-judge\n\n"
        + "The component exists.\n",
    )


def _build_fixture(repo_root):
    _component(repo_root, "a", "A")
    _component(repo_root, "b", "B")
    manifest = {
        "generated_at": GENERATED_AT,
        "verification_report": {"overall": "pass"},
    }
    _write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest),
    )


def test_graph_is_deterministic_and_plain_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph1 = corpus_graph_builder.build_corpus_graph(repo_root)
    graph2 = corpus_graph_builder.build_corpus_graph(repo_root)

    bytes1 = graph1.to_json_bytes()
    bytes2 = graph2.to_json_bytes()
    assert isinstance(bytes1, bytes)
    assert bytes1 == bytes2

    out1 = corpus_graph_builder.write_corpus_graph(graph1, repo_root)
    written1 = Path(out1).read_bytes()
    out2 = corpus_graph_builder.write_corpus_graph(graph2, repo_root)
    written2 = Path(out2).read_bytes()

    expected_path = repo_root / "verification" / "corpus-graph.json"
    assert Path(out1).resolve() == expected_path.resolve()
    assert Path(out2).resolve() == expected_path.resolve()

    assert written1 == bytes1
    assert written2 == bytes1
    assert written1 == written2

    for raw in (bytes1, written1, written2):
        data = json.loads(raw)
        node = data["nodes"]["comp-a"]
        provenance = node["provenance"]
        assert provenance["generated_at"] == GENERATED_AT
        assert isinstance(provenance["generated_at"], str)
        assert node["verification"] == {"overall": "pass"}
# hotdocs-criterion: sha256:9483dc3393b016ac8651e8b8b403210d5639fa92f4b02020d6e4c1e63cc03fe5
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _component_md(slug, sealed, body):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: Component " + slug,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "realizes: []",
        "uses_var: []",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: legacy/" + slug + "/")
    else:
        lines.append("sealed: false")
    lines.append("---")
    return "\n".join(lines) + "\n" + body + "\n"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comps = repo_root / "specs" / "components"
    _write(
        comps / "a" / "component.md",
        _component_md("a", True, "# Component a\n\n## Purpose\n\nA small component."),
    )
    _write(
        comps / "b" / "component.md",
        _component_md("b", False, "# Component b\n\n## Purpose\n\nAnother small component."),
    )
    big_body = " ".join(["word"] * 4001)
    _write(comps / "big" / "component.md", _component_md("big", True, big_body))

    _write(repo_root / "gen" / "a" / ".overrides.json", json.dumps(["x.py"]))

    manifest = {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
        "verification_report": {"component_id": "comp-a", "overall": "pass"},
    }
    _write(repo_root / "verification" / "a" / ".provenance.json", json.dumps(manifest))


def _check_nodes(nodes):
    a = nodes["comp-a"]
    assert field(a, "verification") == {"component_id": "comp-a", "overall": "pass"}
    assert field(a, "provenance") == {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
    }
    assert field(a, "size_status") == "ok"
    assert field(a, "sealed") is True
    assert list(field(a, "pinned_overrides")) == ["x.py"]

    b = nodes["comp-b"]
    assert field(b, "verification") is None
    assert field(b, "provenance") is None
    assert field(b, "sealed") is False
    assert list(field(b, "pinned_overrides")) == []

    big = nodes["comp-big"]
    assert field(big, "size_status") == "over"


def test_ac_graph_003_component_node_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    _check_nodes(nodes)

    data = graph.to_json_bytes()
    assert isinstance(data, (bytes, bytearray))
    parsed = json.loads(data.decode("utf-8"))
    _check_nodes(parsed["nodes"])

    # build_corpus_graph writes nothing
    assert not (repo_root / "verification" / "corpus-graph.json").exists()
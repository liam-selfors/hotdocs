# hotdocs-criterion: sha256:6069b1613cf22cd75c45db3fd835eb8f53c9a9593c3139f3fbef971428a24928
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md(slug, sealed, body):
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


def build_fixture(repo_root):
    comps = repo_root / "specs" / "components"

    write(
        comps / "a" / "component.md",
        component_md("a", True, "# Component a\n\n## Purpose\n\nA small component."),
    )
    write(repo_root / "gen" / "a" / ".overrides.json", json.dumps(["x.py"]))
    manifest = {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
        "verification_report": {"component_id": "comp-a", "overall": "pass"},
    }
    write(repo_root / "verification" / "a" / ".provenance.json", json.dumps(manifest))

    write(
        comps / "b" / "component.md",
        component_md("b", False, "# Component b\n\n## Purpose\n\nAnother small component."),
    )

    big_body = " ".join(["word"] * 4001)
    write(comps / "big" / "component.md", component_md("big", True, big_body))


def test_ac_graph_003_component_node_fields(tmp_path):
    repo_root = Path(tmp_path)
    build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    nodes = field(graph, "nodes")

    node_a = nodes["comp-a"]
    assert field(node_a, "verification") == {"component_id": "comp-a", "overall": "pass"}
    assert field(node_a, "provenance") == {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
    }
    assert field(node_a, "size_status") == "ok"
    assert field(node_a, "sealed") is True
    assert list(field(node_a, "pinned_overrides")) == ["x.py"]

    node_b = nodes["comp-b"]
    assert field(node_b, "verification") is None
    assert field(node_b, "provenance") is None
    assert field(node_b, "sealed") is False
    assert list(field(node_b, "pinned_overrides")) == []

    node_big = nodes["comp-big"]
    assert field(node_big, "size_status") == "over"

    data = graph.to_json_bytes()
    assert isinstance(data, bytes)
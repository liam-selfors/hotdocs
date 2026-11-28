# hotdocs-criterion: sha256:939f87b6e850c20b4e1fa3bf25b746382241b0d9c7a15d26fa136bafefe4d42c
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
        "sealed: " + ("true" if sealed else "false"),
    ]
    if sealed:
        lines.append("source_path: legacy/" + slug + "/")
    lines.append("---")
    return "\n".join(lines) + "\n" + body + "\n"


def build_fixture(repo_root):
    comps = repo_root / "specs" / "components"

    write(
        comps / "a" / "component.md",
        component_md("a", True, "# A\n\n## Purpose\n\nA small component."),
    )
    write(repo_root / "gen" / "a" / ".overrides.json", json.dumps(["x.py"]))
    manifest = {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
        "verification_report": {"component_id": "comp-a", "overall": "pass"},
    }
    write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest),
    )

    write(
        comps / "b" / "component.md",
        component_md("b", False, "# B\n\n## Purpose\n\nAnother small component."),
    )

    big_body = " ".join(["word"] * 4001)
    write(comps / "big" / "component.md", component_md("big", True, big_body))


def test_ac_graph_003(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    nodes = field(graph, "nodes")

    a = nodes["comp-a"]
    assert field(a, "verification") == {"component_id": "comp-a", "overall": "pass"}
    assert field(a, "provenance") == {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
    }
    assert field(a, "size_status") == "ok"
    assert field(a, "sealed") is True
    assert field(a, "pinned_overrides") == ["x.py"]

    b = nodes["comp-b"]
    assert field(b, "verification") is None
    assert field(b, "provenance") is None
    assert field(b, "sealed") is False
    assert field(b, "pinned_overrides") == []

    big = nodes["comp-big"]
    assert field(big, "size_status") == "over"

    data = graph.to_json_bytes()
    assert isinstance(data, bytes)
    parsed = json.loads(data.decode("utf-8"))
    assert parsed["nodes"]["comp-a"]["verification"] == {
        "component_id": "comp-a",
        "overall": "pass",
    }
    assert parsed["nodes"]["comp-b"]["provenance"] is None
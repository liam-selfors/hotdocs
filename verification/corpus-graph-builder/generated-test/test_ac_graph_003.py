# hotdocs-criterion: sha256:a2d9c5bcab8ff694445f1b4cc250f6de81b6fccc95393590323fe22d5a03eed2
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
        "title: " + slug.capitalize() + " component",
        "status: draft",
        "owners: [team-" + slug + "]",
        "sealed: " + ("true" if sealed else "false"),
    ]
    if sealed:
        lines.append("source_path: legacy/" + slug + "/")
    lines += [
        "depends_on: []",
        "realizes: []",
        "uses_var: []",
        "---",
    ]
    return "\n".join(lines) + "\n" + body


def build_fixture(repo_root):
    comps = repo_root / "specs" / "components"
    write(
        comps / "a" / "component.md",
        component_md("a", True, "# A\n\n## Purpose\n\nA small component.\n"),
    )
    write(
        comps / "b" / "component.md",
        component_md("b", False, "# B\n\n## Purpose\n\nAnother small component.\n"),
    )
    write(
        comps / "big" / "component.md",
        component_md("big", True, " ".join(["word"] * 4001) + "\n"),
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


def test_ac_graph_003_component_node_fields(tmp_path):
    repo_root = tmp_path
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
    assert list(field(a, "pinned_overrides")) == ["x.py"]

    b = nodes["comp-b"]
    assert field(b, "verification") is None
    assert field(b, "provenance") is None
    assert field(b, "sealed") is False
    assert list(field(b, "pinned_overrides")) == []

    big = nodes["comp-big"]
    assert field(big, "size_status") == "over"

    data = graph.to_json_bytes()
    assert isinstance(data, (bytes, bytearray))
    parsed = json.loads(data.decode("utf-8"))
    assert parsed["nodes"]["comp-a"]["verification"] == {
        "component_id": "comp-a",
        "overall": "pass",
    }

    # build_corpus_graph writes nothing
    assert not (repo_root / "verification" / "corpus-graph.json").exists()
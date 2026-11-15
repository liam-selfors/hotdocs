import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug: str, sealed: bool, body: str) -> str:
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: Component {slug}",
        "status: draft",
        "owners: [team-x]",
        "depends_on: []",
        "realizes: []",
        "uses_var: []",
        f"sealed: {'true' if sealed else 'false'}",
    ]
    if sealed:
        lines.append(f"source_path: legacy/{slug}/")
    lines.append("---")
    return "\n".join(lines) + "\n" + body + "\n"


def _build_fixture(repo_root: Path) -> None:
    # comp-a: sealed, with overrides and a provenance manifest
    _write(
        repo_root / "specs" / "components" / "a" / "component.md",
        _component_md("a", True, "# Purpose\n\nA small component.\n"),
    )
    _write(
        repo_root / "gen" / "a" / ".overrides.json",
        json.dumps(["x.py"]),
    )
    _write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(
            {
                "spec_bundle_hash": "sha256:abc",
                "generated_at": "2026-11-08T00:19:53Z",
                "verification_report": {
                    "component_id": "comp-a",
                    "overall": "pass",
                },
            }
        ),
    )

    # comp-b: unsealed, no manifest, no overrides
    _write(
        repo_root / "specs" / "components" / "b" / "component.md",
        _component_md("b", False, "# Purpose\n\nAnother small component.\n"),
    )

    # comp-big: body is the word "word" 4001 times
    _write(
        repo_root / "specs" / "components" / "big" / "component.md",
        _component_md("big", True, " ".join(["word"] * 4001)),
    )


def _node(nodes, node_id):
    if isinstance(nodes, dict):
        return nodes[node_id]
    for n in nodes:
        try:
            nid = field(n, "id")
        except (KeyError, AttributeError):
            continue
        if nid == node_id:
            return n
    raise KeyError(node_id)


def test_ac_graph_003_component_node_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    nodes = field(graph, "nodes")

    # comp-a
    a = _node(nodes, "comp-a")
    assert field(a, "verification") == {"component_id": "comp-a", "overall": "pass"}
    assert field(a, "provenance") == {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
    }
    assert field(a, "size_status") == "ok"
    assert field(a, "sealed") is True
    assert list(field(a, "pinned_overrides")) == ["x.py"]

    # comp-b
    b = _node(nodes, "comp-b")
    assert field(b, "verification") is None
    assert field(b, "provenance") is None
    assert field(b, "sealed") is False
    assert list(field(b, "pinned_overrides")) == []

    # comp-big
    big = _node(nodes, "comp-big")
    assert field(big, "size_status") == "over"

    # to_json_bytes() does not raise
    data = graph.to_json_bytes()
    assert isinstance(data, (bytes, bytearray))
    parsed = json.loads(data.decode("utf-8"))
    assert "comp-a" in parsed["nodes"]
    assert parsed["nodes"]["comp-a"]["verification"] == {
        "component_id": "comp-a",
        "overall": "pass",
    }
    assert parsed["nodes"]["comp-b"]["verification"] is None
    assert parsed["nodes"]["comp-b"]["provenance"] is None
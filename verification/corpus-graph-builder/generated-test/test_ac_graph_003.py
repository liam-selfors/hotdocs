import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, sealed, body, realizes="[]", source_path=None):
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: Component {slug}",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        f"realizes: {realizes}",
        "uses_var: []",
        f"sealed: {'true' if sealed else 'false'}",
    ]
    if source_path is not None:
        lines.append(f"source_path: {source_path}")
    lines.append("---")
    return "\n".join(lines) + "\n" + body + "\n"


def _build_fixture(repo_root: Path) -> None:
    # comp-a: sealed, with pinned overrides and a provenance manifest.
    _write(
        repo_root / "specs" / "components" / "a" / "component.md",
        _component_md(
            "a",
            True,
            "# comp-a\n\n## Purpose\n\nA small sealed fixture component.\n",
            source_path="legacy/a/",
        ),
    )
    _write(repo_root / "gen" / "a" / ".overrides.json", json.dumps(["x.py"]))
    manifest = {
        "spec_bundle_hash": "sha256:abc",
        "generated_at": "2026-11-08T00:19:53Z",
        "verification_report": {"component_id": "comp-a", "overall": "pass"},
    }
    _write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest),
    )

    # comp-b: unsealed, no manifest, no overrides.
    _write(
        repo_root / "specs" / "components" / "b" / "component.md",
        _component_md(
            "b",
            False,
            "# comp-b\n\n## Purpose\n\nAn unsealed fixture component.\n",
            realizes="[P-BETA]",
        ),
    )
    _write(
        repo_root / "specs" / "product" / "beta.md",
        "---\nid: P-BETA\ntitle: Beta capability\nstatus: draft\n"
        "owners: [pipeline-team]\n---\n# P-BETA\n\nA capability.\n",
    )

    # comp-big: component.md body is the word "word" 4001 times.
    big_body = " ".join(["word"] * 4001)
    _write(
        repo_root / "specs" / "components" / "big" / "component.md",
        _component_md("big", True, big_body, source_path="legacy/big/"),
    )


def test_ac_graph_003_component_node_fields(tmp_path):
    repo_root = tmp_path
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    nodes = field(graph, "nodes")

    assert "comp-a" in nodes
    assert "comp-b" in nodes
    assert "comp-big" in nodes

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

    # to_json_bytes() does not raise, and yields valid JSON.
    data = graph.to_json_bytes()
    assert isinstance(data, (bytes, bytearray))
    parsed = json.loads(data.decode("utf-8"))
    assert parsed["nodes"]["comp-a"]["verification"] == {
        "component_id": "comp-a",
        "overall": "pass",
    }
    assert parsed["nodes"]["comp-b"]["verification"] is None
    assert parsed["nodes"]["comp-big"]["size_status"] == "over"
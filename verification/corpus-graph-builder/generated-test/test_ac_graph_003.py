import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, sealed, body, depends_on="[]", realizes="[]", uses_var="[]"):
    lines = [
        "---",
        f"id: comp-{slug}",
        f"title: Component {slug.upper()}",
        "status: draft",
        "owners: [team-a]",
        f"depends_on: {depends_on}",
        f"realizes: {realizes}",
        f"uses_var: {uses_var}",
        f"sealed: {'true' if sealed else 'false'}",
    ]
    if sealed:
        lines.append(f"source_path: legacy/{slug}/")
    lines.append("---")
    return "\n".join(lines) + "\n" + body


def _build_fixture(repo_root: Path) -> None:
    specs = repo_root / "specs"

    # Capability, var and decision so every view has files to read.
    _write(
        specs / "product" / "x.md",
        "---\nid: P-X\ntitle: Capability X\nstatus: draft\nowners: [team-a]\n---\n"
        "# Capability X\n\nA capability.\n",
    )
    _write(
        specs / "vars" / "y.md",
        "---\nid: VAR-Y\ntitle: Var Y\nstatus: draft\nowners: [team-a]\n---\n"
        "# Var Y\n\nA var.\n",
    )
    _write(
        specs / "decisions" / "D1.md",
        "---\nid: D1\ntitle: Decision one\nstatus: draft\nowners: [team-a]\n---\n"
        "# D1\n\nA decision.\n",
    )

    # comp-a: sealed, small body, with a requirement and its criterion.
    _write(
        specs / "components" / "a" / "component.md",
        _component_md(
            "a",
            sealed=True,
            body="# Component A\n\n## Purpose\n\nA small sealed component.\n",
        ),
    )
    _write(
        specs / "components" / "a" / "requirements" / "R-A-001.md",
        "**R-A-001** — The component MUST do a thing.\n",
    )
    _write(
        specs / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\nCovers: R-A-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a thing\nWhen it runs\nThen it works\n```\n",
    )

    # comp-b: unsealed, no manifest, no overrides.
    _write(
        specs / "components" / "b" / "component.md",
        _component_md(
            "b",
            sealed=False,
            body="# Component B\n\n## Purpose\n\nA small component.\n",
            realizes="[P-X]",
            uses_var="[VAR-Y]",
        ),
    )

    # comp-big: body is the word "word" 4001 times.
    _write(
        specs / "components" / "big" / "component.md",
        _component_md(
            "big",
            sealed=False,
            body=" ".join(["word"] * 4001) + "\n",
        ),
    )

    # comp-a's pinned overrides and provenance manifest.
    _write(repo_root / "gen" / "a" / ".overrides.json", json.dumps(["x.py"]))
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


def test_component_nodes_carry_verification_provenance_size_sealed_overrides(tmp_path):
    repo_root = tmp_path
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")

    node_a = nodes["comp-a"]
    assert field(node_a, "verification") == {
        "component_id": "comp-a",
        "overall": "pass",
    }
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
    assert isinstance(data, (bytes, bytearray))
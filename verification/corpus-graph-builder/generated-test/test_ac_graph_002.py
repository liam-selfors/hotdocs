# hotdocs-criterion: sha256:cf3b1da8b2e90ded3d9400019fa3d7ff85570372fcc494da06640da96209d04b
"""AC-GRAPH-002: one edge per depends_on / realizes / uses_var relationship,
sorted by from, then to, then kind."""

from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, depends_on, realizes, uses_var, sealed, source_path=None):
    lines = [
        "---",
        "id: comp-" + slug,
        "title: Component " + slug,
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: [" + ", ".join(depends_on) + "]",
        "realizes: [" + ", ".join(realizes) + "]",
        "uses_var: [" + ", ".join(uses_var) + "]",
        "sealed: " + ("true" if sealed else "false"),
    ]
    if source_path is not None:
        lines.append("source_path: " + source_path)
    lines += [
        "---",
        "",
        "# comp-" + slug,
        "",
        "## Purpose",
        "",
        "Test fixture component " + slug + ".",
        "",
    ]
    return "\n".join(lines)


def _build_fixture(repo_root):
    specs = repo_root / "specs"

    # comp-a: depends_on [comp-b], realizes [P-ONE], uses_var [VAR-ONE]
    a_dir = specs / "components" / "a"
    _write(
        a_dir / "component.md",
        _component_md("a", ["comp-b"], ["P-ONE"], ["VAR-ONE"], sealed=False),
    )
    _write(
        a_dir / "requirements" / "R-A-001.md",
        "**R-A-001** — Component a MUST do its thing.\n",
    )
    _write(
        a_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\nCovers: R-A-001\nKind: generated-test\n\n"
        "Component a does its thing.\n",
    )

    # comp-b: no relationships
    b_dir = specs / "components" / "b"
    _write(
        b_dir / "component.md",
        _component_md("b", [], [], [], sealed=True, source_path="legacy/b/"),
    )
    _write(
        b_dir / "requirements" / "R-B-001.md",
        "**R-B-001** — Component b MUST do its thing.\n",
    )
    _write(
        b_dir / "acceptance" / "AC-B-001.md",
        "# AC-B-001\n\nCovers: R-B-001\nKind: generated-test\n\n"
        "Component b does its thing.\n",
    )

    # capability P-ONE
    _write(
        specs / "product" / "one.md",
        "\n".join([
            "---",
            "id: P-ONE",
            "title: Capability one",
            "status: draft",
            "owners: [pipeline-team]",
            "---",
            "",
            "# P-ONE",
            "",
            "A capability.",
            "",
        ]),
    )

    # var VAR-ONE
    _write(
        specs / "vars" / "VAR-ONE.md",
        "\n".join([
            "---",
            "id: VAR-ONE",
            "title: Var one",
            "status: draft",
            "owners: [pipeline-team]",
            "---",
            "",
            "# VAR-ONE",
            "",
            "A var.",
            "",
        ]),
    )


def test_edges_are_exactly_declared_relationships_sorted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    edges = field(graph, "edges")

    actual = [
        {
            "from": field(e, "from"),
            "to": field(e, "to"),
            "kind": field(e, "kind"),
        }
        for e in list(edges)
    ]

    expected = [
        {"from": "comp-a", "to": "P-ONE", "kind": "realizes"},
        {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
        {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
    ]

    assert actual == expected
    assert actual == sorted(actual, key=lambda e: (e["from"], e["to"], e["kind"]))

    # The serialized form carries the same edges, in the same order.
    as_dict = graph.to_dict()
    assert [
        {"from": e["from"], "to": e["to"], "kind": e["kind"]}
        for e in as_dict["edges"]
    ] == expected
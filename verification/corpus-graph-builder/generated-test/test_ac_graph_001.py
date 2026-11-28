# hotdocs-criterion: sha256:a6541193b12018f3fb20a1725c6871863f8c0584188cd2f2b251c15cd41b20d7
"""AC-GRAPH-001: the graph holds one node per capability, component and var."""

from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def frontmatter(pairs):
    lines = ["---"]
    for key, value in pairs:
        lines.append(key + ": " + value)
    lines.append("---")
    return "\n".join(lines) + "\n"


def build_fixture(repo_root):
    specs = repo_root / "specs"

    # Capabilities
    write(
        specs / "product" / "one.md",
        frontmatter([
            ("id", "P-ONE"),
            ("title", "Capability One"),
            ("status", "draft"),
            ("owners", "[pipeline-team]"),
        ])
        + "\n# Capability One\n\nThe first capability.\n",
    )
    write(
        specs / "product" / "two.md",
        frontmatter([
            ("id", "P-TWO"),
            ("title", "Capability Two"),
            ("status", "draft"),
            ("owners", "[pipeline-team]"),
        ])
        + "\n# Capability Two\n\nThe second capability.\n",
    )

    # Components, no relations
    for slug in ["a", "b", "c"]:
        write(
            specs / "components" / slug / "component.md",
            frontmatter([
                ("id", "comp-" + slug),
                ("title", "Component " + slug.upper()),
                ("status", "draft"),
                ("owners", "[pipeline-team]"),
                ("depends_on", "[]"),
                ("realizes", "[]"),
                ("uses_var", "[]"),
                ("sealed", "true"),
                ("source_path", "legacy/" + slug + "/"),
            ])
            + "\n# Component " + slug.upper() + "\n\n## Purpose\n\n"
            + "A fixture component.\n",
        )

    # Requirement for comp-a, with its matching criterion
    write(
        specs / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n\n**R-A-001** — The component MUST exist.\n",
    )
    write(
        specs / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n\nCovers: R-A-001\nKind: llm-judge\n\n"
        "The component exists.\n",
    )

    # Var
    write(
        specs / "vars" / "VAR-ONE.md",
        frontmatter([
            ("id", "VAR-ONE"),
            ("title", "Var One"),
            ("status", "draft"),
            ("owners", "[pipeline-team]"),
        ])
        + "\n# Var One\n\nA fixture var.\n",
    )

    # Decision
    write(
        specs / "decisions" / "D1.md",
        frontmatter([
            ("id", "D1"),
            ("title", "Decision One"),
            ("status", "draft"),
            ("owners", "[pipeline-team]"),
        ])
        + "\n# Decision One\n\nA fixture decision.\n",
    )


def test_ac_graph_001_nodes_are_capabilities_components_and_vars(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)
    nodes = field(graph, "nodes")

    assert set(nodes.keys()) == {
        "P-ONE",
        "P-TWO",
        "comp-a",
        "comp-b",
        "comp-c",
        "VAR-ONE",
    }

    assert field(nodes["P-ONE"], "type") == "capability"
    assert field(nodes["P-TWO"], "type") == "capability"
    assert field(nodes["comp-a"], "type") == "component"
    assert field(nodes["comp-b"], "type") == "component"
    assert field(nodes["comp-c"], "type") == "component"
    assert field(nodes["VAR-ONE"], "type") == "var"
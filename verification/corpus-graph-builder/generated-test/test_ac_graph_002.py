import corpus_graph_builder

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo_root: Path, slug: str, frontmatter_lists: str, sealed_lines: str) -> None:
    comp_dir = repo_root / "specs" / "components" / slug
    upper = slug.upper()
    _write(
        comp_dir / "component.md",
        "---\n"
        f"id: comp-{slug}\n"
        f"title: Component {upper}\n"
        "status: draft\n"
        "owners: [test-team]\n"
        f"{frontmatter_lists}"
        f"{sealed_lines}"
        "---\n"
        "\n"
        f"# comp-{slug}\n"
        "\n"
        "## Purpose\n"
        "\n"
        f"Fixture component {slug} for corpus graph edge tests.\n",
    )
    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"**R-{upper}-001** — The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n"
        "\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does one thing\n"
        "```\n",
    )


def _build_fixture(repo_root: Path) -> None:
    _component(
        repo_root,
        "a",
        "depends_on: [comp-b]\n"
        "realizes: [P-ONE]\n"
        "uses_var: [VAR-ONE]\n",
        "sealed: false\n",
    )
    _component(
        repo_root,
        "b",
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n",
        "sealed: true\n"
        "source_path: legacy/b/\n",
    )
    _write(
        repo_root / "specs" / "product" / "one.md",
        "---\n"
        "id: P-ONE\n"
        "title: Capability One\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# P-ONE\n"
        "\n"
        "A fixture capability.\n",
    )
    _write(
        repo_root / "specs" / "vars" / "one.md",
        "---\n"
        "id: VAR-ONE\n"
        "title: Var One\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# VAR-ONE\n"
        "\n"
        "A fixture var.\n",
    )


def _normalize_edge(edge):
    return {
        "from": field(edge, "from"),
        "to": field(edge, "to"),
        "kind": field(edge, "kind"),
    }


def test_edges_one_per_declared_relationship_sorted(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    expected = [
        {"from": "comp-a", "to": "P-ONE", "kind": "realizes"},
        {"from": "comp-a", "to": "VAR-ONE", "kind": "uses_var"},
        {"from": "comp-a", "to": "comp-b", "kind": "depends_on"},
    ]

    edges = [_normalize_edge(e) for e in field(graph, "edges")]
    assert edges == expected

    # The same holds for the serialized dict form.
    as_dict = graph.to_dict()
    dict_edges = [_normalize_edge(e) for e in as_dict["edges"]]
    assert dict_edges == expected

    # Explicitly confirm the ordering is by from, then to, then kind.
    keys = [(e["from"], e["to"], e["kind"]) for e in edges]
    assert keys == sorted(keys)

    # build_corpus_graph writes nothing.
    assert not (repo_root / "verification" / "corpus-graph.json").exists()
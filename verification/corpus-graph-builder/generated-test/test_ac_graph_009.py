import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> dict:
    # Component comp-a (sealed, so no realizes/capability linkage needed).
    _write(
        repo_root / "specs" / "components" / "a" / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/a/\n"
        "---\n"
        "\n"
        "# Component A\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used to exercise the corpus graph.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "requirements" / "R-A-001.md",
        "# R-A-001\n\n**R-A-001** — Component A MUST exist.\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given component A\n"
        "When it is inspected\n"
        "Then it exists\n"
        "```\n",
    )
    _write(
        repo_root / "specs" / "components" / "a" / "interface" / "guarantees" / "G-A-001.md",
        "# G-A-001\n\n**G-A-001** — Component A is present.\n",
    )
    # Other frontmatter-bearing kinds, so every view has files to read.
    _write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget\n",
    )
    _write(
        repo_root / "specs" / "vars" / "VAR-THING.md",
        "---\n"
        "id: VAR-THING\n"
        "title: Thing\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# VAR-THING\n",
    )
    _write(
        repo_root / "specs" / "decisions" / "D1.md",
        "---\n"
        "id: D1\n"
        "title: First decision\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# D1\n",
    )

    manifest = {
        "license_scan": {"blocked": True, "findings": ["GPL-3.0 in x.c"]},
        "verification_report": {"overall": "pass"},
    }
    manifest_path = repo_root / "verification" / "a" / ".provenance.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def test_provenance_license_scan_is_the_manifest_files_own_json(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    # Precondition from the Given: no gen/license-scanner/ under repo_root.
    assert not (repo_root / "gen" / "license-scanner").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes
    node = nodes["comp-a"]

    provenance = field(node, "provenance")
    assert provenance is not None
    license_scan = field(provenance, "license_scan")

    expected = {"blocked": True, "findings": ["GPL-3.0 in x.c"]}
    assert license_scan == expected
    # Exactly the file's JSON: a real dict with a real bool and a real list,
    # not a typed-view rendering of it.
    assert isinstance(license_scan, dict)
    assert set(license_scan.keys()) == {"blocked", "findings"}
    assert license_scan["blocked"] is True
    assert isinstance(license_scan["findings"], list)
    assert license_scan["findings"] == ["GPL-3.0 in x.c"]

    # build_corpus_graph writes nothing.
    assert not (repo_root / "verification" / "corpus-graph.json").exists()
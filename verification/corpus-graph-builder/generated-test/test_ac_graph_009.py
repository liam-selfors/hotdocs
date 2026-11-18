# hotdocs-criterion: sha256:f652a4288e295b21ed57a0d308b0150dd2a6b8dcae2d71e695c0e96995ff9b22
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "a"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-a\n"
        "title: Component A\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
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
        "A small fixture component.\n",
    )
    _write(
        comp_dir / "requirements" / "R-A-001.md",
        "# R-A-001\n"
        "\n"
        "**R-A-001** - The component MUST do one thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-A-001.md",
        "# AC-A-001\n"
        "\n"
        "Covers: R-A-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it does one thing\n"
        "```\n",
    )

    manifest = {
        "license_scan": {"blocked": True, "findings": ["GPL-3.0 in x.c"]},
        "verification_report": {"overall": "pass"},
    }
    _write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest, indent=2) + "\n",
    )


def test_ac_graph_009_license_scan_read_verbatim_from_manifest(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    assert not (repo_root / "gen" / "license-scanner").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    assert "comp-a" in nodes
    node = nodes["comp-a"]

    provenance = field(node, "provenance")
    assert provenance is not None
    license_scan = (
        provenance["license_scan"]
        if isinstance(provenance, dict)
        else getattr(provenance, "license_scan")
    )
    assert license_scan == {"blocked": True, "findings": ["GPL-3.0 in x.c"]}
    assert type(license_scan) is dict
    assert type(license_scan["blocked"]) is bool
    assert license_scan["findings"] == ["GPL-3.0 in x.c"]
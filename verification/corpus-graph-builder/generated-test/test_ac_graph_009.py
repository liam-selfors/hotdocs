# hotdocs-criterion: sha256:807cd99f3060c75d45e1d7c6c80c11a21cccdb793e62dfa3402cafbf6625f1f0
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    component_md = (
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
        "A fixture component for the corpus graph.\n"
    )
    write(repo_root / "specs" / "components" / "a" / "component.md", component_md)

    manifest = {
        "license_scan": {"blocked": True, "findings": ["GPL-3.0 in x.c"]},
        "verification_report": {"overall": "pass"},
    }
    write(
        repo_root / "verification" / "a" / ".provenance.json",
        json.dumps(manifest, indent=2) + "\n",
    )


def test_ac_graph_009_provenance_license_scan_read_from_manifest_file(tmp_path):
    repo_root = tmp_path
    build_fixture(repo_root)

    assert not (repo_root / "gen" / "license-scanner").exists()

    graph = corpus_graph_builder.build_corpus_graph(repo_root)

    nodes = field(graph, "nodes")
    node = nodes["comp-a"]
    provenance = field(node, "provenance")
    assert provenance is not None
    license_scan = provenance["license_scan"] if isinstance(provenance, dict) else getattr(provenance, "license_scan")

    assert license_scan == {"blocked": True, "findings": ["GPL-3.0 in x.c"]}
    assert isinstance(license_scan, dict)
    assert set(license_scan.keys()) == {"blocked", "findings"}
    assert license_scan["blocked"] is True
    assert license_scan["findings"] == ["GPL-3.0 in x.c"]

    # The serialized form carries the file's own JSON as well.
    as_dict = graph.to_dict()
    assert as_dict["nodes"]["comp-a"]["provenance"]["license_scan"] == {
        "blocked": True,
        "findings": ["GPL-3.0 in x.c"],
    }
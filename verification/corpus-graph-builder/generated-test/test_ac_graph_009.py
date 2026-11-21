# hotdocs-criterion: sha256:71389f5947be89aa9590f28f43fc37280f83ceb3d8a233dd0da625d2d22fa560
import json
from pathlib import Path

import corpus_graph_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
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
    "A fixture component used to check provenance pass-through.\n"
)


def _build_fixture(repo_root: Path) -> dict:
    comp_dir = repo_root / "specs" / "components" / "a"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    manifest = {
        "license_scan": {"blocked": True, "findings": ["GPL-3.0 in x.c"]},
        "verification_report": {"overall": "pass"},
    }
    ver_dir = repo_root / "verification" / "a"
    ver_dir.mkdir(parents=True)
    (ver_dir / ".provenance.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


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
    license_scan = field(provenance, "license_scan")
    assert license_scan == {"blocked": True, "findings": ["GPL-3.0 in x.c"]}
    assert isinstance(license_scan, dict)
    assert license_scan["blocked"] is True
    assert license_scan["findings"] == ["GPL-3.0 in x.c"]
    assert set(license_scan.keys()) == {"blocked", "findings"}
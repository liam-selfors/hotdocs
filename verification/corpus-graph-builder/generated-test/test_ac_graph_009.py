import json
import tempfile
from pathlib import Path

import corpus_graph_builder


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def test_ac_graph_009_provenance_license_scan_passthrough():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        comp_dir = repo_root / "specs" / "components" / "a"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(
            "---\n"
            "id: comp-a\n"
            "title: Comp A\n"
            "status: ratified\n"
            "owners: [alice]\n"
            "sealed: true\n"
            "source_path: legacy/a/\n"
            "depends_on: []\n"
            "realizes: []\n"
            "uses_var: []\n"
            "last_ratified_commit: abc123\n"
            "---\n"
            "\n"
            "# Comp A\n"
            "\n"
            "## Purpose\n"
            "\n"
            "A synthetic component fixture for AC-GRAPH-009.\n",
            encoding="utf-8",
        )

        verification_dir = repo_root / "verification" / "a"
        verification_dir.mkdir(parents=True)
        provenance_manifest = {
            "license_scan": {
                "blocked": True,
                "findings": ["GPL-3.0 in x.c"],
            },
            "verification_report": {"overall": "pass"},
        }
        (verification_dir / ".provenance.json").write_text(
            json.dumps(provenance_manifest), encoding="utf-8"
        )

        # Deliberately no gen/license-scanner/ anywhere under repo_root.

        graph = corpus_graph_builder.build_corpus_graph(repo_root)

        nodes = _field(graph, "nodes")
        comp_a_node = _field(nodes, "comp-a")
        provenance = _field(comp_a_node, "provenance")
        license_scan = _field(provenance, "license_scan")

        assert license_scan == {
            "blocked": True,
            "findings": ["GPL-3.0 in x.c"],
        }
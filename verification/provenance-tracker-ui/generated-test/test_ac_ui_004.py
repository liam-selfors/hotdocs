import json
import os
import textwrap
from pathlib import Path

import pytest

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER_SOURCE = textwrap.dedent(
    """
    def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
        return {
            "scope": "whole-corpus" if changed_ids is None else "blast-radius",
            "ready": False,
            "components": {
                "comp-foo": {
                    "hit": True,
                    "verification_report": {
                        "component_id": "comp-foo",
                        "criteria": [],
                        "requirement_results": {},
                        "interface_drift": False,
                        "mutation_score": 1.0,
                        "overall": "pass",
                    },
                    "license_scan": {"blocked": False},
                    "secret_scan": {"flagged": False},
                },
                "comp-bar": {
                    "hit": False,
                    "verification_report": None,
                    "license_scan": None,
                    "secret_scan": None,
                },
            },
            "capabilities": {
                "P-ZERO-EDIT": {
                    "hit": True,
                    "capability_scenario_report": {
                        "P-ZERO-EDIT": {"overall": "pass", "scenarios": []}
                    },
                },
            },
            "not_ready_reasons": ["comp-bar: no provenance for current spec state"],
        }


    def last_requirement_failures(component_id, repo_root):
        return []
    """
)


def _field(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _snapshot_tree(root: Path):
    snap = {}
    if not root.exists():
        return snap
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for filename in filenames:
            p = Path(dirpath) / filename
            snap[p] = (p.stat().st_size, p.read_bytes())
    return snap


def test_ac_ui_004_edges_and_single_write(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    gen_dir = repo_root / "gen" / "provenance-tracker"
    gen_dir.mkdir(parents=True)
    (gen_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER_SOURCE)

    verification_dir = repo_root / "verification"
    verification_dir.mkdir(parents=True)
    corpus_graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
            },
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
        },
        "edges": [
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    (verification_dir / "corpus-graph.json").write_text(json.dumps(corpus_graph))

    out_dir = repo_root / ".hotdocs" / "ui"

    before = _snapshot_tree(repo_root)

    snapshot = provenance_tracker_ui.render_tracker_ui(
        out_dir=out_dir, repo_root=repo_root
    )

    after = _snapshot_tree(repo_root)

    edges = _field(snapshot, "edges")
    assert edges is not None
    edge_tuples = {
        (_field(e, "from"), _field(e, "to"), _field(e, "kind")) for e in edges
    }

    assert edge_tuples == {
        ("comp-foo", "comp-bar", "depends_on"),
        ("comp-foo", "P-ZERO-EDIT", "realizes"),
    }
    assert ("comp-foo", "VAR-FOO-URL", "uses_var") not in edge_tuples

    before_paths = set(before)
    after_paths = set(after)

    removed = before_paths - after_paths
    added = after_paths - before_paths
    changed = {
        p for p in (before_paths & after_paths) if before[p] != after[p]
    }

    assert removed == set()
    assert changed == set()
    assert added == {out_dir / "index.html"}
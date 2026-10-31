import json
from pathlib import Path

import provenance_tracker_ui


FAKE_PROVENANCE_TRACKER_SOURCE = '''
def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    return {
        "scope": "whole-corpus",
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
                "capability_scenario_report": {"overall": "pass"},
            },
        },
        "not_ready_reasons": ["comp-bar: missing provenance"],
    }


def last_requirement_failures(component_id, repo_root):
    return []
'''


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _snapshot_tree(*roots):
    state = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_dir():
                continue
            if "__pycache__" in path.parts:
                continue
            resolved = str(path.resolve())
            stat = path.stat()
            state[resolved] = (stat.st_size, stat.st_mtime_ns)
    return state


def test_tracker_ui_edges_filtered_and_only_index_html_written(tmp_path):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "out"
    repo_root.mkdir()
    out_dir.mkdir()

    verification_dir = repo_root / "verification"
    verification_dir.mkdir()
    corpus_graph = {
        "nodes": {
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
            },
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
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

    tracker_dir = repo_root / "gen" / "provenance-tracker"
    tracker_dir.mkdir(parents=True)
    (tracker_dir / "provenance_tracker.py").write_text(FAKE_PROVENANCE_TRACKER_SOURCE)

    before = _snapshot_tree(repo_root, out_dir)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir=out_dir, repo_root=repo_root)

    after = _snapshot_tree(repo_root, out_dir)

    edges = _get(snapshot, "edges")
    edge_tuples = {
        (_get(edge, "from"), _get(edge, "to"), _get(edge, "kind"))
        for edge in edges
    }
    expected_edges = {
        ("comp-foo", "comp-bar", "depends_on"),
        ("comp-foo", "P-ZERO-EDIT", "realizes"),
    }
    assert edge_tuples == expected_edges
    assert ("comp-foo", "VAR-FOO-URL", "uses_var") not in edge_tuples

    index_html = out_dir / "index.html"
    added = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {p for p in (set(after) & set(before)) if after[p] != before[p]}
    all_diffs = added | removed | changed

    assert all_diffs == {str(index_html.resolve())}
    assert index_html.is_file()
    assert index_html.stat().st_size > 0
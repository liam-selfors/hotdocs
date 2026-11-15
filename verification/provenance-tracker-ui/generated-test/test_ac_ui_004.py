import hashlib
import json
import os
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def edge_triple(edge):
    if isinstance(edge, dict):
        return (edge["from"], edge["to"], edge["kind"])
    src = getattr(edge, "from", None)
    if src is None:
        src = getattr(edge, "from_")
    return (src, getattr(edge, "to"), getattr(edge, "kind"))


FAKE_TRACKER = '''
import json
from pathlib import Path

_LOG = Path(__LOG_PATH__)


def _log(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({"fn": "check_readiness", "changed_ids": changed_ids, "model": model, "seed": seed})
    passing_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": passing_report,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
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
            }
        },
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state \\u2014 run hotdocs generate comp-bar"
        ],
    }


def last_requirement_failures(component_id, repo_root):
    _log({"fn": "last_requirement_failures", "component_id": component_id})
    return []
'''


def _build_repo(repo_root: Path, log_path: Path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER.replace("__LOG_PATH__", repr(str(log_path))), encoding="utf-8"
    )

    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "unknown",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
            {"from": "comp-foo", "to": "VAR-FOO-URL", "kind": "uses_var"},
            {"from": "comp-foo", "to": "comp-bar", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    ver = repo_root / "verification"
    ver.mkdir(parents=True)
    (ver / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def _snapshot_tree(root: Path):
    files = {}
    dirs = set()
    if not root.exists():
        return files, dirs
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        dp = Path(dirpath)
        for d in dirnames:
            dirs.add(str((dp / d).relative_to(root)))
        for name in filenames:
            p = dp / name
            st = p.stat()
            files[str(p.relative_to(root))] = (
                st.st_mtime_ns,
                st.st_size,
                hashlib.sha256(p.read_bytes()).hexdigest(),
            )
    return files, dirs


def _changed(before, after):
    changed = set()
    for k, v in after.items():
        if k not in before or before[k] != v:
            changed.add(k)
    for k in before:
        if k not in after:
            changed.add(k)
    return changed


def test_ac_ui_004_edges_and_writes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_log.jsonl"

    _build_repo(repo_root, log_path)

    repo_files_before, repo_dirs_before = _snapshot_tree(repo_root)
    out_files_before, _ = _snapshot_tree(out_dir)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake tracker was actually used.
    assert log_path.exists()
    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert sum(1 for c in calls if c["fn"] == "check_readiness") == 1

    # Nodes are exactly the report's keys.
    node_ids = sorted(field(n, "id") for n in field(snapshot, "nodes"))
    assert node_ids == ["P-ZERO-EDIT", "comp-bar", "comp-foo"]

    # Edges: exactly depends_on and realizes, never uses_var to VAR-FOO-URL.
    edges = sorted(edge_triple(e) for e in field(snapshot, "edges"))
    assert edges == sorted([
        ("comp-foo", "comp-bar", "depends_on"),
        ("comp-foo", "P-ZERO-EDIT", "realizes"),
    ])
    assert all(e[2] != "uses_var" for e in edges)
    assert all(e[1] != "VAR-FOO-URL" for e in edges)

    # Writes: only out_dir/index.html anywhere under repo_root or out_dir.
    repo_files_after, repo_dirs_after = _snapshot_tree(repo_root)
    out_files_after, _ = _snapshot_tree(out_dir)

    assert _changed(repo_files_before, repo_files_after) == set()
    assert repo_dirs_after == repo_dirs_before
    assert _changed(out_files_before, out_files_after) == {"index.html"}
    assert (out_dir / "index.html").is_file()
import hashlib
import json
import os
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_TEMPLATE = '''
import json
from pathlib import Path

_LOG = Path({log_path!r})


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log({{"fn": "check_readiness", "changed_ids": changed_ids, "model": model, "seed": seed}})
    return {{
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": {{
            "comp-foo": {{
                "hit": True,
                "verification_report": {{
                    "component_id": "comp-foo",
                    "criteria": [],
                    "requirement_results": {{"R-FOO-001": "pass"}},
                    "interface_drift": False,
                    "mutation_score": 0.9,
                    "overall": "pass",
                }},
                "license_scan": {{"blocked": False, "findings": []}},
                "secret_scan": {{"flagged": False, "findings": []}},
            }},
            "comp-bar": {{
                "hit": True,
                "verification_report": {{
                    "component_id": "comp-bar",
                    "criteria": [],
                    "requirement_results": {{"R-BAR-001": "pass", "R-BAR-002": "fail"}},
                    "interface_drift": False,
                    "mutation_score": 0.5,
                    "overall": "fail",
                }},
                "license_scan": {{"blocked": False, "findings": []}},
                "secret_scan": {{"flagged": False, "findings": []}},
            }},
        }},
        "capabilities": {{
            "P-ZERO-EDIT": {{
                "hit": True,
                "capability_scenario_report": {{
                    "P-ZERO-EDIT": {{"overall": "pass", "scenarios": []}}
                }},
            }},
        }},
        "not_ready_reasons": ["comp-bar: verification failed"],
    }}


def last_requirement_failures(component_id, repo_root):
    _log({{"fn": "last_requirement_failures", "component_id": component_id}})
    if component_id == "comp-bar":
        return ["R-BAR-002"]
    return []
'''


def _snapshot_files(*roots):
    state = {}
    for root in roots:
        root = Path(root)
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            if "__pycache__" in Path(dirpath).parts:
                continue
            for name in filenames:
                p = Path(dirpath) / name
                st = p.stat()
                digest = hashlib.sha256(p.read_bytes()).hexdigest()
                state[str(p.resolve())] = (st.st_mtime_ns, st.st_size, digest)
    return state


def test_ac_ui_004_edges_filtered_and_only_index_html_written(tmp_path):
    repo_root = tmp_path / "repo"
    out_dir = tmp_path / "out"
    log_path = tmp_path / "calls.log"
    repo_root.mkdir()
    out_dir.mkdir()

    # Fake provenance-tracker, flat-module shape.
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    (fake_dir / "provenance_tracker.py").write_text(
        FAKE_TRACKER_TEMPLATE.format(log_path=str(log_path)), encoding="utf-8"
    )

    # Committed topology.
    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
            "comp-bar": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": False,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-foo": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
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
    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    before = _snapshot_files(repo_root, out_dir)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    after = _snapshot_files(repo_root, out_dir)

    # The faked provenance-tracker was the one used.
    assert log_path.exists(), "faked provenance-tracker was never invoked"
    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert sum(1 for c in calls if c["fn"] == "check_readiness") == 1

    # Edges: exactly depends_on and realizes, never the uses_var edge.
    edges = field(snapshot, "edges")
    edge_tuples = [
        (field(e, "from"), field(e, "to"), field(e, "kind")) for e in edges
    ]
    assert len(edge_tuples) == 2, edge_tuples
    assert set(edge_tuples) == {
        ("comp-foo", "comp-bar", "depends_on"),
        ("comp-foo", "P-ZERO-EDIT", "realizes"),
    }
    assert not any(t[2] == "uses_var" or t[1] == "VAR-FOO-URL" for t in edge_tuples)

    # Only out_dir/index.html created or changed (ignoring __pycache__).
    index_path = str((out_dir / "index.html").resolve())
    created = set(after) - set(before)
    removed = set(before) - set(after)
    changed = {p for p in set(before) & set(after) if before[p] != after[p]}
    touched = created | removed | changed
    assert touched == {index_path}, (
        f"created={sorted(created)} removed={sorted(removed)} changed={sorted(changed)}"
    )
    assert (out_dir / "index.html").is_file()
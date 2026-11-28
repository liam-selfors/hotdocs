# hotdocs-criterion: sha256:ba2c1658d86b78f60fca08ce4182b0f639578e8dc6107b7bded1ad1bfbf86a7a
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _edge_field(edge, name):
    if isinstance(edge, dict):
        return edge[name]
    if hasattr(edge, name):
        return getattr(edge, name)
    return getattr(edge, name + "_")


SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "pass",
}

REPORT = {
    "scope": "whole-corpus",
    "ready": False,
    "components": {
        "comp-foo": {
            "hit": True,
            "reason": None,
            "verification_report": VERIFICATION_REPORT,
            "license_scan": {"blocked": False},
            "secret_scan": SECRET_SCAN,
        },
        "comp-bar": {
            "hit": False,
            "reason": "no manifest",
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
    "secret_scan": SECRET_SCAN,
    "not_ready_reasons": [
        "comp-bar: no provenance for current spec state \u2014 run hotdocs generate comp-bar"
    ],
}

CORPUS_GRAPH = {
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
        "orphan_component_rate": 0.5,
        "orphan_var_rate": 0.0,
    },
}


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "import copy\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(REPORT) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


def _snapshot(root):
    result = {}
    if not root.exists():
        return result
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if "__pycache__" in rel.parts:
            continue
        if path.is_file():
            result[rel.as_posix()] = path.read_bytes()
    return result


def test_ac_ui_004_edges_and_only_index_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake-log.txt"

    _write_fake_tracker(repo_root, log_path)
    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(CORPUS_GRAPH, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    before_repo = _snapshot(repo_root)
    before_out = _snapshot(out_dir)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake tracker was actually used.
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("check_readiness") == 1

    # Edges: exactly depends_on and realizes, never the uses_var edge.
    edges = field(snapshot, "edges")
    got = sorted(
        (_edge_field(e, "from"), _edge_field(e, "to"), _edge_field(e, "kind"))
        for e in edges
    )
    assert got == sorted(
        [
            ("comp-foo", "comp-bar", "depends_on"),
            ("comp-foo", "P-ZERO-EDIT", "realizes"),
        ]
    )
    assert len(edges) == 2
    for e in edges:
        assert _edge_field(e, "to") != "VAR-FOO-URL"
        assert _edge_field(e, "kind") != "uses_var"

    # Nothing under repo_root created or changed (ignoring __pycache__).
    after_repo = _snapshot(repo_root)
    assert after_repo == before_repo

    # Under out_dir, only index.html is created or changed.
    after_out = _snapshot(out_dir)
    changed = sorted(
        k for k in set(before_out) | set(after_out)
        if before_out.get(k) != after_out.get(k)
    )
    assert changed == ["index.html"]
    assert sorted(after_out) == ["index.html"]
    assert (out_dir / "index.html").is_file()
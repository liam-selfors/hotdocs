# hotdocs-criterion: sha256:6f6d97f06cd8c7902dab267a46ad15692a9875f6b699731cc7a8d3258c75e7f9
import hashlib
import json
import os
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _snapshot(root):
    """Map every file under root (skipping __pycache__) to (sha256, size, mtime_ns)."""
    result = {}
    root = Path(root)
    if not root.exists():
        return result
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            p = Path(dirpath) / name
            st = p.stat()
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            result[str(p.resolve())] = (digest, st.st_size, st.st_mtime_ns)
    return result


def _verification_report():
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.92,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:00",
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "drivers": [],
        "overall": "pass",
    }


def _secret_scan():
    return {
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


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(),
                "license_scan": {"blocked": False},
                "secret_scan": _secret_scan(),
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
        "secret_scan": _secret_scan(),
        "not_ready_reasons": [
            "comp-bar: no provenance for current spec state \u2014 run hotdocs generate comp-bar"
        ],
    }


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _corpus_graph():
    return {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "VAR-FOO-URL": {"type": "var"},
            "comp-bar": _component_node(),
            "comp-foo": _component_node(),
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


def _write_fake_tracker(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "LOG = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + component_id)\n"
        "    return []\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


def test_ac_ui_004_edges_filtered_and_only_index_html_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake-calls.log"

    _write_fake_tracker(repo_root, log_path)

    verification_dir = repo_root / "verification"
    verification_dir.mkdir()
    (verification_dir / "corpus-graph.json").write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    before_repo = _snapshot(repo_root)
    before_out = _snapshot(out_dir)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The faked provenance-tracker was actually used.
    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    # Edges: exactly depends_on and realizes, never the uses_var edge.
    edges = field(snapshot, "edges")
    got = sorted(
        (field(e, "from"), field(e, "to"), field(e, "kind")) for e in edges
    )
    expected = sorted(
        [
            ("comp-foo", "comp-bar", "depends_on"),
            ("comp-foo", "P-ZERO-EDIT", "realizes"),
        ]
    )
    assert got == expected
    assert len(edges) == 2
    assert all(field(e, "kind") != "uses_var" for e in edges)
    assert all(field(e, "to") != "VAR-FOO-URL" for e in edges)

    # Writes: only out_dir/index.html is created or changed.
    after_repo = _snapshot(repo_root)
    after_out = _snapshot(out_dir)

    before = dict(before_repo)
    before.update(before_out)
    after = dict(after_repo)
    after.update(after_out)

    changed = sorted(
        path
        for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    )
    index_html = str((out_dir / "index.html").resolve())
    assert changed == [index_html]
    assert index_html in after
    assert index_html not in before
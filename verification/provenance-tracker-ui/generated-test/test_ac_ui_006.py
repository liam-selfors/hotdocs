# hotdocs-criterion: sha256:e55c82bd595f3caf8853ac407c2e153ce521a80520f694abc924b16db9c539f7
"""AC-UI-006: the rendered index.html needs no server of any kind.

Given a rendered index.html, when it is inspected for anything requiring
a server, then it contains no "fetch(", no "XMLHttpRequest", no
"http://", and no "https://", and the module exposes no serve function
and main treats a "serve" subcommand as a usage error returning 2.
"""

import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_TRACKER_BODY = '''
import json
from pathlib import Path


def _log(line):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


def _verification_report(component_id, overall):
    req_result = "pass" if overall == "pass" else "fail"
    crit_result = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-" + component_id.upper() + "-001",
        "covers": "R-" + component_id.upper() + "-001",
        "kind": "compiled",
        "result": crit_result,
    }
    if crit_result == "fail":
        criterion["failure_detail"] = {"message": "x equals 1 failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {"R-" + component_id.upper() + "-001": req_result},
        "interface_drift": False,
        "mutation_score": 0.9,
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
        "overall": overall,
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


def _hit(component_id, overall):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": False},
        "secret_scan": _secret_scan(),
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    components = {
        "comp-alpha": _hit("comp-alpha", "pass"),
        "comp-beta": _hit("comp-beta", "fail"),
        "comp-gamma": {
            "hit": False,
            "reason": "no manifest",
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
        },
    }
    capabilities = {}
    reasons = [
        "comp-beta: verification failed",
        "comp-gamma: no provenance for current spec state - run hotdocs generate comp-gamma",
    ]
    return {
        "scope": "blast-radius" if changed_ids is not None else "whole-corpus",
        "ready": False,
        "components": components,
        "capabilities": capabilities,
        "secret_scan": _secret_scan(),
        "not_ready_reasons": reasons,
    }


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures " + component_id)
    if component_id == "comp-beta":
        return ["R-COMP-BETA-001"]
    return []
'''


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "tracker_calls.log"

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_TRACKER_BODY
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    graph = {
        "nodes": {
            "comp-alpha": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-beta": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
            "comp-gamma": {
                "type": "component",
                "verification": None,
                "provenance": None,
                "size_status": "ok",
                "sealed": True,
                "pinned_overrides": [],
                "owners": ["pipeline-team"],
                "documents": {},
            },
        },
        "edges": [
            {"from": "comp-alpha", "to": "comp-beta", "kind": "depends_on"},
            {"from": "comp-beta", "to": "comp-gamma", "kind": "depends_on"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    verification = repo_root / "verification"
    verification.mkdir()
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2), encoding="utf-8"
    )
    return repo_root, log_path


def test_rendered_page_needs_no_server(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake dependency was really used.
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    node_ids = [field(n, "id") for n in field(snapshot, "nodes")]
    assert "comp-alpha" in node_ids

    index = out_dir / "index.html"
    assert index.is_file()
    html = index.read_text(encoding="utf-8")
    assert html.strip() != ""

    assert "fetch(" not in html
    assert "XMLHttpRequest" not in html
    assert "http://" not in html
    assert "https://" not in html


def test_module_exposes_no_serve_function():
    assert not hasattr(provenance_tracker_ui, "serve")


def test_main_serve_subcommand_is_usage_error(tmp_path, capsys):
    repo_root, _ = _build_repo(tmp_path)

    code = provenance_tracker_ui.main(["track", "ui", "serve"])
    assert code == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "usage error" in captured.err

    code = provenance_tracker_ui.main(
        ["track", "ui", "serve", "--repo-root=" + str(repo_root)]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
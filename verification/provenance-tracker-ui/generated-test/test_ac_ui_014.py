# hotdocs-criterion: sha256:d08a6ef3e4aff393375987b5d1836f5b2481d3a6b44ae99fec28f711fad73c6e
import json
import re
from pathlib import Path

import provenance_tracker_ui


FAKE_TRACKER_BODY = '''
import json
from pathlib import Path


def _log(line):
    with open(LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


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


def _verification_report(component_id, req_id, passing):
    criterion = {
        "id": "AC-" + req_id[2:],
        "covers": req_id,
        "kind": "compiled",
        "result": "pass" if passing else "fail",
    }
    if not passing:
        criterion["failure_detail"] = {"message": "x equals 1 failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {req_id: "pass" if passing else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": "pass" if passing else "fail",
    }


def _check_result(component_id, req_id, passing):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, req_id, passing),
        "license_scan": {"blocked": False},
        "secret_scan": _secret_scan(),
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {
        "scope": "whole-corpus" if changed_ids is None else "blast-radius",
        "ready": False,
        "components": {
            "comp-foo": _check_result("comp-foo", "R-FOO-001", True),
            "comp-bar": _check_result("comp-bar", "R-BAR-001", False),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-bar: verification failed"],
    }


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures " + component_id)
    if component_id == "comp-bar":
        return ["R-BAR-001"]
    return []
'''


def _corpus_graph():
    def comp_node():
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

    return {
        "nodes": {"comp-bar": comp_node(), "comp-foo": comp_node()},
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    log_path = tmp_path / "fake_tracker.log"
    source = "LOG_PATH = " + repr(str(log_path)) + "\n" + FAKE_TRACKER_BODY
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    verification = repo_root / "verification"
    verification.mkdir(parents=True)
    (verification / "corpus-graph.json").write_text(
        json.dumps(_corpus_graph(), sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return repo_root, log_path


def test_ac_ui_014_single_inline_style_in_head(tmp_path):
    repo_root, log_path = _build_repo(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The faked provenance-tracker was the one consulted.
    assert log_path.is_file()
    assert "check_readiness" in log_path.read_text(encoding="utf-8").splitlines()

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    assert html.count("<style") == 1

    head_match = re.search(r"<head[\s>]", html)
    assert head_match is not None
    head_open = head_match.start()
    head_close = html.find("</head>")
    assert head_close != -1

    style_open = html.index("<style")
    assert head_open < style_open < head_close

    style_close = html.find("</style>", style_open)
    assert style_close != -1
    assert style_close < head_close
    style_text = html[style_open:style_close]
    assert ".tone-fail" in style_text
    assert "--color-bg" in style_text

    assert " style=" not in html
    assert "<link" not in html
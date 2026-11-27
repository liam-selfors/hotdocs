# hotdocs-criterion: sha256:6f4d2712309273f4c46ebb1051de637b723032b56be4004d5ff35094b1433b50
import json
import re
from pathlib import Path

import provenance_tracker_ui


def _verification_report(component_id, overall, req_id, req_result):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-" + component_id[5:].upper() + "-001",
                "covers": req_id,
                "kind": "compiled",
                "result": req_result,
            }
        ],
        "requirement_results": {req_id: req_result},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
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


def _provenance_check_result(component_id, overall, req_id, req_result):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(
            component_id, overall, req_id, req_result
        ),
        "license_scan": {"blocked": False},
        "secret_scan": _secret_scan(),
    }


def _write_fake_tracker(repo_root, log_path):
    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _provenance_check_result(
                "comp-foo", "pass", "R-FOO-001", "pass"
            ),
            "comp-bar": _provenance_check_result(
                "comp-bar", "fail", "R-BAR-001", "fail"
            ),
        },
        "capabilities": {},
        "secret_scan": _secret_scan(),
        "not_ready_reasons": ["comp-bar: verification failed"],
    }
    src = (
        "import copy\n"
        "from pathlib import Path\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(report) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    report = copy.deepcopy(_REPORT)\n"
        "    if changed_ids is not None:\n"
        "        report['scope'] = 'blast-radius'\n"
        "    return report\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise RuntimeError('not used in this test')\n"
    )
    target = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(src, encoding="utf-8")


def _component_node(component_id, overall, req_id, req_result):
    return {
        "type": "component",
        "verification": _verification_report(
            component_id, overall, req_id, req_result
        ),
        "provenance": {"component_id": component_id},
        "size_status": "ok",
        "sealed": True,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "comp-bar": _component_node("comp-bar", "fail", "R-BAR-001", "fail"),
            "comp-foo": _component_node("comp-foo", "pass", "R-FOO-001", "pass"),
        },
        "edges": [],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    path = repo_root / "verification" / "corpus-graph.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(graph, sort_keys=True, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def test_ac_ui_014_single_inline_style_in_head(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "tracker_calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    # The fake ran.
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    html = (out_dir / "index.html").read_text(encoding="utf-8")

    # "<style" occurs exactly once.
    assert html.count("<style") == 1

    head_match = re.search(r"<head[\s>]", html)
    assert head_match is not None, "no <head> element found"
    head_start = head_match.start()
    head_end = html.find("</head>")
    assert head_end != -1, "no </head> found"

    style_start = html.index("<style")
    assert head_start < style_start < head_end

    # The style element's text.
    open_end = html.index(">", style_start)
    close = html.find("</style>", open_end)
    assert close != -1, "no </style> found"
    assert close < head_end
    style_text = html[open_end + 1:close]
    assert ".tone-fail" in style_text
    assert "--color-bg" in style_text

    # No inline style attributes and no <link elements anywhere.
    assert " style=" not in html
    assert "<link" not in html
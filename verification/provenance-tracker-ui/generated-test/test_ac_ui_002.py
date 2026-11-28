# hotdocs-criterion: sha256:90c2ce8efee9ec13b4ac833f9daa9360b459c073dcd0633c7ffc608a982d6698
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    req = "R-" + component_id.upper().replace("COMP-", "") + "-001"
    result = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-" + component_id.upper().replace("COMP-", "") + "-001",
        "covers": req,
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        criterion["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
        "requirement_results": {req: result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def _secret_scan(flagged):
    matches = []
    if flagged:
        matches = [
            {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "gen/zed/config.py", "line": 3}
        ]
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": flagged,
        "matches": matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _license_scan(blocked):
    return {"blocked": blocked, "findings": []}


def _hit(component_id, overall, blocked, flagged):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": _license_scan(blocked),
        "secret_scan": _secret_scan(flagged),
    }


def _verify_report():
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _hit("comp-foo", "pass", False, False),
            "comp-bar": _hit("comp-bar", "fail", False, False),
            "comp-qux": _hit("comp-qux", "pass", True, False),
            "comp-zed": _hit("comp-zed", "pass", False, True),
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "fail", "scenarios": []}
                },
            }
        },
        "secret_scan": _secret_scan(False),
        "not_ready_reasons": [
            "comp-bar: verification failed",
            "comp-qux: license scan blocked",
            "P-ZERO-EDIT: capability scenarios failed",
        ],
    }


def _write_fake_tracker(repo_root, log_path):
    report_json = json.dumps(_verify_report())
    src = (
        "import json\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(report_json) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used')\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )
    d = repo_root / "gen" / "provenance-tracker"
    d.mkdir(parents=True, exist_ok=True)
    (d / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _component_node():
    return {
        "type": "component",
        "verification": None,
        "provenance": None,
        "size_status": "ok",
        "sealed": False,
        "pinned_overrides": [],
        "owners": ["pipeline-team"],
        "documents": {},
    }


def _write_corpus_graph(repo_root):
    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-bar": _component_node(),
            "comp-foo": _component_node(),
            "comp-qux": _component_node(),
            "comp-zed": _component_node(),
        },
        "edges": [
            {"from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes"},
        ],
        "aggregates": {
            "orphan_capability_rate": 0.0,
            "orphan_component_rate": 0.0,
            "orphan_var_rate": 0.0,
        },
    }
    v = repo_root / "verification"
    v.mkdir(parents=True, exist_ok=True)
    (v / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


EXPECTED = {
    "comp-foo": "passing",
    "comp-bar": "failing",
    "comp-qux": "failing",
    "comp-zed": "passing",
    "P-ZERO-EDIT": "failing",
}

STATUSES = ("passing", "failing", "missing", "not-attempted")


def test_ac_ui_002_statuses_map_report_fields(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"
    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    out_dir = tmp_path
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    assert statuses == EXPECTED

    page = browser.open(out_dir / "index.html")
    for node_id, status in statuses.items():
        el = page.find(css='li.node[data-node-id="' + node_id + '"]')
        assert el.count() == 1, node_id
        assert el.attribute("data-status") == status, node_id
        classes = (el.attribute("class") or "").split()
        assert "node" in classes, node_id
        assert "status-" + status in classes, node_id
        for other in STATUSES:
            if other != status:
                assert "status-" + other not in classes, node_id
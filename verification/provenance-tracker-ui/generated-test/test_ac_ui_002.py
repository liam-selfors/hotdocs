# hotdocs-criterion: sha256:94629966a3534cf519f48d4c1d7f0e1590314aadde3a733759d2a2ce10c686ad
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-X-001",
                "covers": "R-X-001",
                "kind": "compiled",
                "result": "pass" if overall == "pass" else "fail",
            }
        ],
        "requirement_results": {"R-X-001": "pass" if overall == "pass" else "fail"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def _license_scan(blocked):
    return {"blocked": blocked, "matches": [], "gate_version": "license_scanner@1.0.0"}


def _secret_scan(flagged):
    matches = []
    if flagged:
        matches = [
            {
                "rule_id": "AWS Access Key",
                "risk_tier": "high",
                "file": "gen/zed/config.py",
                "line": 3,
            }
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
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(json.dumps(_REPORT))\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used by this test')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")


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
    vdir = repo_root / "verification"
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


EXPECTED = {
    "comp-foo": "passing",
    "comp-bar": "failing",
    "comp-qux": "failing",
    "comp-zed": "passing",
    "P-ZERO-EDIT": "failing",
}


def test_ac_ui_002_statuses_map_directly_from_verify_report(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_calls.log"

    _write_fake_tracker(repo_root, log_path)
    _write_corpus_graph(repo_root)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    for node_id, status in EXPECTED.items():
        assert node_id in statuses, node_id
        assert statuses[node_id] == status, (node_id, statuses[node_id])

    index = out_dir / "index.html"
    assert index.is_file()
    page = browser.open(index)

    for node_id, status in EXPECTED.items():
        snap_status = statuses[node_id]
        matching = page.find(
            css='li.node[data-node-id="' + node_id + '"][data-status="'
            + snap_status + '"].status-' + snap_status
        )
        assert matching.count() == 1, (node_id, snap_status)
        any_node = page.find(css='li.node[data-node-id="' + node_id + '"]')
        assert any_node.count() == 1, node_id
        assert any_node.attribute("data-status") == snap_status
        classes = (any_node.attribute("class") or "").split()
        assert "status-" + snap_status in classes
        for other in ("passing", "failing", "missing", "not-attempted"):
            if other != snap_status:
                assert "status-" + other not in classes, (node_id, other)

    assert page.console_errors() == []
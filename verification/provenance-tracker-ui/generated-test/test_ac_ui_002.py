# hotdocs-criterion: sha256:de26857fa344c0cac2033d4b7f0297a192684ee2b93c2c72675409eb60766357
import json
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    rid = "R-" + component_id.upper().replace("COMP-", "") + "-001"
    aid = "AC-" + component_id.upper().replace("COMP-", "") + "-001"
    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": aid,
                "covers": rid,
                "kind": "compiled",
                "result": overall,
            }
        ],
        "requirement_results": {rid: overall},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "drivers": [],
        "overall": overall,
    }


def _secret_scan(flagged):
    matches = []
    if flagged:
        matches = [
            {
                "rule_id": "AWS Access Key",
                "risk_tier": "high",
                "file": "gen/zed/config.py",
                "line": 12,
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


def _license_scan(blocked):
    return {"blocked": blocked, "flagged": blocked, "matches": []}


def _hit(component_id, overall, blocked, secret_flagged):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": _license_scan(blocked),
        "secret_scan": _secret_scan(secret_flagged),
    }


def _build_report():
    components = {
        "comp-foo": _hit("comp-foo", "pass", False, False),
        "comp-bar": _hit("comp-bar", "fail", False, False),
        "comp-qux": _hit("comp-qux", "pass", True, False),
        "comp-zed": _hit("comp-zed", "pass", False, True),
    }
    capabilities = {
        "P-ZERO-EDIT": {
            "hit": True,
            "capability_scenario_report": {
                "P-ZERO-EDIT": {"overall": "fail", "scenarios": []}
            },
        }
    }
    return {
        "scope": "whole-corpus",
        "ready": False,
        "components": components,
        "capabilities": capabilities,
        "secret_scan": None,
        "not_ready_reasons": [
            "comp-bar: verification failed",
            "comp-qux: license scan blocked",
            "P-ZERO-EDIT: capability scenarios failed",
        ],
    }


def _write_fake_tracker(repo_root, report, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "import copy\n"
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
        "    return copy.deepcopy(_REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used by this test')\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(src, encoding="utf-8")


def _write_corpus_graph(repo_root):
    nodes = {"P-ZERO-EDIT": {"type": "capability"}}
    for cid in ["comp-bar", "comp-foo", "comp-qux", "comp-zed"]:
        nodes[cid] = {
            "type": "component",
            "verification": None,
            "provenance": None,
            "size_status": "ok",
            "sealed": False,
            "pinned_overrides": [],
            "owners": ["pipeline-team"],
            "documents": {},
        }
    graph = {
        "nodes": nodes,
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


def test_ac_ui_002_statuses_map_report_fields(tmp_path, browser):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path
    log_path = tmp_path / "fake_calls.log"

    _write_fake_tracker(repo_root, _build_report(), log_path)
    _write_corpus_graph(repo_root)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("check_readiness") == 1

    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    assert statuses == EXPECTED

    index = out_dir / "index.html"
    assert index.is_file()

    page = browser.open(index)
    for node_id, status in EXPECTED.items():
        selector = 'li.node[data-node-id="' + node_id + '"]'
        element = page.find(css=selector)
        assert element.count() == 1, node_id
        assert element.attribute("data-status") == status, node_id
        classes = (element.attribute("class") or "").split()
        assert "status-" + status in classes, (node_id, classes)
        other = [
            c
            for c in classes
            if c.startswith("status-") and c != "status-" + status
        ]
        assert other == [], (node_id, classes)
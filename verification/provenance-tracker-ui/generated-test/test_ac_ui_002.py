# hotdocs-criterion: sha256:a3ab9150f1ef9d2fce7997c9f2a0508ce3c097f7bb903b36a021516424ea14d9
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    result = "pass" if overall == "pass" else "fail"
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-X-001", "covers": "R-X-001", "kind": "compiled", "result": result},
        ],
        "requirement_results": {"R-X-001": result},
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


def _license_scan(blocked):
    return {"blocked": blocked, "matches": [], "notified": False}


def _secret_scan(flagged):
    matches = []
    if flagged:
        matches = [
            {"rule_id": "AWS Access Key", "risk_tier": "high", "file": "gen/zed/config.py", "line": 1}
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
        "secret_scan": None,
        "not_ready_reasons": [
            "comp-bar: verification failed",
            "comp-qux: license scan blocked",
            "P-ZERO-EDIT: capability scenarios failed",
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


def _write_fixture(repo_root, log_path):
    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(_verify_report()) + "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return json.loads(json.dumps(REPORT))\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures ' + str(component_id))\n"
        "    return []\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    raise NotImplementedError('not used in this test')\n"
        "\n"
        "def main(argv=None):\n"
        "    return 2\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

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
    verification = repo_root / "verification"
    verification.mkdir(parents=True)
    (verification / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2), encoding="utf-8"
    )


class _NodeCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = {}

    def handle_starttag(self, tag, attrs):
        attr_map = {}
        for key, value in attrs:
            attr_map[key] = value if value is not None else ""
        if "data-node-id" in attr_map and "data-status" in attr_map:
            classes = attr_map.get("class", "").split()
            self.nodes.setdefault(attr_map["data-node-id"], []).append(
                {"tag": tag, "status": attr_map["data-status"], "classes": classes}
            )

    handle_startendtag = handle_starttag


def test_ac_ui_002_statuses_map_report_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    out_dir = tmp_path / "out"
    log_path = tmp_path / "fake_calls.log"
    _write_fixture(repo_root, log_path)

    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    assert log_path.is_file()
    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    expected = {
        "comp-foo": "passing",
        "comp-bar": "failing",
        "comp-qux": "failing",
        "comp-zed": "passing",
        "P-ZERO-EDIT": "failing",
    }

    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    for node_id, status in expected.items():
        assert statuses.get(node_id) == status, (node_id, statuses)

    html_text = (out_dir / "index.html").read_text(encoding="utf-8")
    collector = _NodeCollector()
    collector.feed(html_text)

    for node_id, status in statuses.items():
        elements = collector.nodes.get(node_id)
        assert elements, "no node element for " + node_id
        li_nodes = [e for e in elements if e["tag"] == "li" and "node" in e["classes"]]
        candidates = li_nodes if li_nodes else elements
        for element in candidates:
            assert element["status"] == status, (node_id, element)
            assert ("status-" + status) in element["classes"], (node_id, element)
            other = [
                c for c in element["classes"]
                if c.startswith("status-") and c != "status-" + status
            ]
            assert other == [], (node_id, element)

    for node_id, status in expected.items():
        assert node_id in collector.nodes
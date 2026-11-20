# hotdocs-criterion: sha256:99c6e93a0bbc28e07e25e1eb70f62f15944f741919e5cdb2516bd0a8998cb1f4
import json
from html.parser import HTMLParser
from pathlib import Path

import provenance_tracker_ui


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _verification_report(component_id, overall):
    result = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-X-001",
        "covers": "R-X-001",
        "kind": "compiled",
        "result": result,
    }
    if result == "fail":
        criterion["failure_detail"] = {"message": "failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": component_id,
        "criteria": [criterion],
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


def _hit(component_id, overall, license_blocked, secret_flagged):
    return {
        "hit": True,
        "reason": None,
        "verification_report": _verification_report(component_id, overall),
        "license_scan": {"blocked": license_blocked, "findings": []},
        "secret_scan": {"flagged": secret_flagged, "findings": []},
    }


class _NodeCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        if "data-node-id" in a and "node" in classes:
            self.nodes.append(
                {
                    "tag": tag,
                    "id": a.get("data-node-id"),
                    "status": a.get("data-status"),
                    "classes": classes,
                }
            )

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)


def test_ac_ui_002_statuses_map_report_fields(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"

    report = {
        "scope": "whole-corpus",
        "ready": False,
        "components": {
            "comp-foo": _hit("comp-foo", "pass", False, False),
            "comp-bar": _hit("comp-bar", "fail", False, False),
            "comp-qux": _hit("comp-qux", "pass", True, False),
        },
        "capabilities": {
            "P-ZERO-EDIT": {
                "hit": True,
                "capability_scenario_report": {
                    "P-ZERO-EDIT": {"overall": "fail", "scenarios": []}
                },
            }
        },
        "not_ready_reasons": [
            "comp-bar: verification failed",
            "comp-qux: license scan blocked",
            "P-ZERO-EDIT: capability scenarios failed",
        ],
    }

    fake_dir = repo_root / "gen" / "provenance-tracker"
    fake_dir.mkdir(parents=True)
    source = (
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
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )
    (fake_dir / "provenance_tracker.py").write_text(source, encoding="utf-8")

    def comp_node():
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

    graph = {
        "nodes": {
            "P-ZERO-EDIT": {"type": "capability"},
            "comp-bar": comp_node(),
            "comp-foo": comp_node(),
            "comp-qux": comp_node(),
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
    (repo_root / "verification").mkdir()
    (repo_root / "verification" / "corpus-graph.json").write_text(
        json.dumps(graph, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    out_dir = tmp_path / "out"
    snapshot = provenance_tracker_ui.render_tracker_ui(out_dir, repo_root)

    calls = log_path.read_text(encoding="utf-8").splitlines()
    assert calls.count("check_readiness") == 1

    expected = {
        "comp-foo": "passing",
        "comp-bar": "failing",
        "comp-qux": "failing",
        "P-ZERO-EDIT": "failing",
    }
    nodes = field(snapshot, "nodes")
    statuses = {field(n, "id"): field(n, "status") for n in nodes}
    assert statuses == expected

    html = (out_dir / "index.html").read_text(encoding="utf-8")
    collector = _NodeCollector()
    collector.feed(html)
    by_id = {}
    for el in collector.nodes:
        by_id.setdefault(el["id"], []).append(el)

    all_statuses = ["passing", "failing", "missing", "not-attempted"]
    for node_id, status in expected.items():
        assert node_id in by_id, "no node element for " + node_id
        assert len(by_id[node_id]) == 1, "multiple node elements for " + node_id
        el = by_id[node_id][0]
        assert el["status"] == status
        assert "status-" + status in el["classes"]
        for other in all_statuses:
            if other != status:
                assert "status-" + other not in el["classes"]
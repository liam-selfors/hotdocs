import os
from pathlib import Path

import pytest

import provenance_tracker


def _get(obj, key):
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _read_log(path: Path):
    if not path.exists():
        return []
    return [line for line in path.read_text().splitlines() if line]


_PROVENANCE_CHECKER_SOURCE = '''
import os

_CALL_LOG = os.path.join(os.path.dirname(__file__), "calls.log")


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    with open(_CALL_LOG, "a") as f:
        f.write(component_id + "\\n")
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {"R-FOO-001": "pass"},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": component_id,
            "gate_version": "license_scanner@1.0.0",
            "similarity_score": 0.0,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@1.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }
'''


_CAP_VERIFIER_ALL_PASS = '''
import os

_CHECK_LOG = os.path.join(os.path.dirname(__file__), "check_calls.log")
_RUN_LOG = os.path.join(os.path.dirname(__file__), "run_calls.log")


def check_capability_provenance(capability_id, repo_root):
    with open(_CHECK_LOG, "a") as f:
        f.write(capability_id + "\\n")
    return {
        "hit": True,
        "capability_scenario_report": {
            capability_id: {
                "overall": "pass",
                "scenarios": [
                    {"id": "CS-TEST-CAP-001", "kind": "compiled", "result": "pass"},
                ],
            }
        },
    }


def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):
    with open(_RUN_LOG, "a") as f:
        f.write(capability_id + "\\n")
    return {
        "hit": True,
        "capability_scenario_report": {
            capability_id: {
                "overall": "pass",
                "scenarios": [
                    {"id": "CS-TEST-CAP-001", "kind": "compiled", "result": "pass"},
                ],
            }
        },
    }
'''


_CAP_VERIFIER_RUN_FAILS = '''
import os

_CHECK_LOG = os.path.join(os.path.dirname(__file__), "check_calls.log")
_RUN_LOG = os.path.join(os.path.dirname(__file__), "run_calls.log")


def check_capability_provenance(capability_id, repo_root):
    with open(_CHECK_LOG, "a") as f:
        f.write(capability_id + "\\n")
    return {
        "hit": True,
        "capability_scenario_report": {
            capability_id: {
                "overall": "pass",
                "scenarios": [
                    {"id": "CS-TEST-CAP-001", "kind": "compiled", "result": "pass"},
                ],
            }
        },
    }


def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):
    with open(_RUN_LOG, "a") as f:
        f.write(capability_id + "\\n")
    return {
        "hit": True,
        "capability_scenario_report": {
            capability_id: {
                "overall": "fail",
                "scenarios": [
                    {
                        "id": "CS-TEST-CAP-001",
                        "kind": "llm-judge",
                        "result": "fail",
                        "rationale": "scenario did not meet the bar",
                    },
                ],
            }
        },
    }
'''


_CAP_VERIFIER_MISS = '''
import os

_CHECK_LOG = os.path.join(os.path.dirname(__file__), "check_calls.log")
_RUN_LOG = os.path.join(os.path.dirname(__file__), "run_calls.log")


def check_capability_provenance(capability_id, repo_root):
    with open(_CHECK_LOG, "a") as f:
        f.write(capability_id + "\\n")
    return {"hit": False, "capability_scenario_report": None}


def run_capability_gates(capability_id, repo_root, judge=None, test_author=None):
    with open(_RUN_LOG, "a") as f:
        f.write(capability_id + "\\n")
    return {
        "hit": True,
        "capability_scenario_report": {
            capability_id: {"overall": "pass", "scenarios": []}
        },
    }
'''


def _build_repo(tmp_path: Path, capability_module_source: str) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo Component\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [P-TEST-CAP]\n"
        "sealed: false\n"
        "---\n"
        "# Foo Component\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "The component MUST do the foo thing.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\n\n"
        "Given foo\nWhen bar\nThen baz\n",
    )

    _write(
        repo_root / "specs" / "product" / "test-cap.md",
        "---\n"
        "id: P-TEST-CAP\n"
        "title: Test Capability\n"
        "status: draft\n"
        "owners: [alice]\n"
        "---\n"
        "# Test Capability\n",
    )

    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        _PROVENANCE_CHECKER_SOURCE,
    )
    _write(
        repo_root / "gen" / "capability-scenario-verifier" / "capability_scenario_verifier.py",
        capability_module_source,
    )

    return repo_root


def test_all_passing_components_and_capabilities_yield_ready_true(tmp_path):
    repo_root = _build_repo(tmp_path, _CAP_VERIFIER_ALL_PASS)

    report = provenance_tracker.check_readiness(repo_root, None, None)

    assert _get(report, "ready") is True
    assert list(_get(report, "not_ready_reasons")) == []

    run_log = _read_log(
        repo_root / "gen" / "capability-scenario-verifier" / "run_calls.log"
    )
    assert "P-TEST-CAP" in run_log


def test_one_failing_capability_blocks_readiness_despite_passing_components(tmp_path):
    repo_root = _build_repo(tmp_path, _CAP_VERIFIER_RUN_FAILS)

    report = provenance_tracker.check_readiness(repo_root, None, None)

    assert _get(report, "ready") is False
    reasons = list(_get(report, "not_ready_reasons"))
    assert any("P-TEST-CAP" in reason for reason in reasons)

    components = _get(report, "components")
    comp_result = components["comp-foo"] if isinstance(components, dict) else getattr(components, "comp-foo")
    comp_hit = _get(comp_result, "hit")
    assert comp_hit is True
    comp_verification = _get(comp_result, "verification_report")
    assert _get(comp_verification, "overall") == "pass"


def test_capability_miss_with_no_model_reports_usage_error(tmp_path):
    repo_root = _build_repo(tmp_path, _CAP_VERIFIER_MISS)

    with pytest.raises(Exception):
        provenance_tracker.check_readiness(repo_root, None, None)

    run_log = _read_log(
        repo_root / "gen" / "capability-scenario-verifier" / "run_calls.log"
    )
    assert run_log == []
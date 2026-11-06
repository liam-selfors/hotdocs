import json

import pytest

import provenance_tracker


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


_PROVENANCE_CHECKER_TEMPLATE = '''
import json

LOG_PATH = __LOG_PATH__


def _log(event):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\\n")


def current_sealed_key(component_id, repo_root):
    _log({"fn": "current_sealed_key", "component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log({"fn": "current_provenance_key", "component_id": component_id})
    return {
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "gate_versions": {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    }


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log({"fn": "check_provenance", "component_id": component_id})
    return {
        "hit": True,
        "verification_report": {
            "component_id": component_id,
            "criteria": [],
            "requirement_results": {},
            "interface_drift": False,
            "mutation_score": 1.0,
            "overall": "pass",
        },
        "license_scan": {
            "component_id": component_id,
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
            "flagged": False,
            "matches": [],
            "allowed": [],
            "unused_allowlist_entries": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        },
    }


def check_sealed_provenance(component_id, repo_root):
    _log({"fn": "check_sealed_provenance", "component_id": component_id})
    return {
        "hit": True,
        "sealed": True,
        "reason": None,
        "verification_report": {"overall": "pass"},
        "license_scan": None,
        "secret_scan": None,
        "owners": ["pipeline-team"],
        "source_hash": "sha256:" + "0" * 64,
        "written_at": "2026-01-01T00:00:00Z",
    }
'''


_CAPABILITY_VERIFIER_TEMPLATE = '''
import json

LOG_PATH = __LOG_PATH__


def _log(event):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(event) + "\\n")


def check_capability_provenance(capability_id, repo_root):
    _log({"fn": "check_capability_provenance", "capability_id": capability_id})
    return {"hit": False, "capability_scenario_report": None}


def run_capability_gates(capability_id, repo_root, model=None, seed=0, llm_backend=None):
    _log({
        "fn": "run_capability_gates",
        "capability_id": capability_id,
        "model": model,
        "seed": seed,
    })
    overall = __OVERALL__
    return {
        "hit": False,
        "capability_scenario_report": {
            capability_id: {
                "overall": overall,
                "scenarios": [
                    {"id": "CS-FOO-001", "kind": "generated-test", "result": overall},
                ],
            }
        },
    }
'''


_COMPONENT_MD = """---
id: comp-foo
title: Foo Component
status: draft
owners: [team-foo]
sealed: false
realizes: [P-FOO]
---

# Foo Component

A fixture component that realizes P-FOO.
"""


_CAPABILITY_MD = """---
id: P-FOO
title: Foo Capability
status: draft
owners: [team-foo]
---

# Foo Capability

### CS-FOO-001

Covers: P-FOO
Kind: generated-test

```gherkin
Given a foo
When it is tested
Then it passes
```
"""


def _build_repo(tmp_path, log_path, overall):
    repo_root = tmp_path / "repo"
    _write(repo_root / "specs" / "components" / "foo" / "component.md", _COMPONENT_MD)
    _write(repo_root / "specs" / "product" / "p-foo.md", _CAPABILITY_MD)

    provenance_checker_src = _PROVENANCE_CHECKER_TEMPLATE.replace(
        "__LOG_PATH__", json.dumps(str(log_path))
    )
    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        provenance_checker_src,
    )

    capability_verifier_src = _CAPABILITY_VERIFIER_TEMPLATE.replace(
        "__LOG_PATH__", json.dumps(str(log_path))
    ).replace("__OVERALL__", json.dumps(overall))
    _write(
        repo_root
        / "gen"
        / "capability-scenario-verifier"
        / "capability_scenario_verifier.py",
        capability_verifier_src,
    )
    return repo_root


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_all_components_and_capabilities_passing_means_ready(tmp_path):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(tmp_path, log_path, overall="pass")

    report = provenance_tracker.check_readiness(
        repo_root, changed_ids=None, model="claude-sonnet-5", seed=0, llm_backend=None,
    )

    assert _get(report, "ready") is True
    assert list(_get(report, "not_ready_reasons")) == []

    components = _get(report, "components")
    foo_result = components["comp-foo"]
    assert _get(foo_result, "hit") is True
    assert _get(_get(foo_result, "verification_report"), "overall") == "pass"

    events = _read_log(log_path)
    assert any(e["fn"] == "check_provenance" and e["component_id"] == "comp-foo" for e in events)
    assert any(e["fn"] == "check_capability_provenance" and e["capability_id"] == "P-FOO" for e in events)
    gate_events = [e for e in events if e["fn"] == "run_capability_gates"]
    assert len(gate_events) == 1
    assert gate_events[0]["capability_id"] == "P-FOO"
    assert gate_events[0]["model"] == "claude-sonnet-5"
    assert gate_events[0]["seed"] == 0


def test_failing_capability_makes_not_ready_despite_passing_components(tmp_path):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(tmp_path, log_path, overall="fail")

    report = provenance_tracker.check_readiness(
        repo_root, changed_ids=None, model="claude-sonnet-5", seed=0, llm_backend=None,
    )

    assert _get(report, "ready") is False
    reasons = list(_get(report, "not_ready_reasons"))
    assert any("P-FOO" in reason for reason in reasons)

    components = _get(report, "components")
    for result in components.values():
        verification_report = _get(result, "verification_report")
        assert _get(verification_report, "overall") == "pass"


def test_capability_miss_with_no_model_raises_without_running_gates(tmp_path):
    log_path = tmp_path / "log.jsonl"
    repo_root = _build_repo(tmp_path, log_path, overall="pass")

    with pytest.raises(ValueError):
        provenance_tracker.check_readiness(
            repo_root, changed_ids=None, model=None, seed=0, llm_backend=None,
        )

    events = _read_log(log_path)
    assert any(e["fn"] == "check_capability_provenance" and e["capability_id"] == "P-FOO" for e in events)
    assert not any(e["fn"] == "run_capability_gates" for e in events)
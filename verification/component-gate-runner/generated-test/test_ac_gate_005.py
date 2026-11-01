import json

import component_gate_runner


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


FOO_COMPONENT_MD = """---
id: comp-foo
title: Foo Fixture
status: draft
owners: [lselfors@gmail.com]
sealed: false
---

# Foo Fixture

Purpose: synthetic fixture component for AC-GATE-005.
"""


def _write_component_fixture(repo_root):
    # sealed: false is required: a sealed component skips
    # provenance-checker entirely, which both scenarios below need.
    _write(repo_root / "specs" / "components" / "foo" / "component.md", FOO_COMPONENT_MD)


PROVENANCE_CHECKER_MISS = '''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        "sha256:" + "a" * 64,
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''


PROVENANCE_CHECKER_HIT = '''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        "sha256:" + "b" * 64,
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@3.1.0",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
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
            "gate_version": "license_scanner@3.1.0",
            "similarity_score": 0.0,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
        },
        "secret_scan": {
            "scope": "full",
            "gate_version": "secret_scanner@2.0.0",
            "flagged": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
        },
    }
'''


SPEC_BUNDLE_ASSEMBLER = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "",
        "interface": "",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
'''


GENERATOR_MODEL_CALL_ERROR = '''
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "connection refused"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


PROVENANCE_TRACKER = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''


LICENSE_SCANNER_LOGGING = '''
import json
import os


def scan(component_id, repo_root):
    log_path = os.environ["AC_GATE_005_CALL_LOG"]
    record = json.dumps({
        "call": "license_scanner.scan",
        "component_id": component_id,
        "repo_root": str(repo_root),
    })
    with open(log_path, "a") as f:
        f.write(record)
        f.write(chr(10))
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@3.1.0",
        "similarity_score": 0.0,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''


SECRET_SCANNER_LOGGING = '''
import json
import os


def scan(repo_root):
    log_path = os.environ["AC_GATE_005_CALL_LOG"]
    record = json.dumps({
        "call": "secret_scanner.scan",
        "repo_root": str(repo_root),
    })
    with open(log_path, "a") as f:
        f.write(record)
        f.write(chr(10))
    return {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''


def test_miss_with_model_call_error_calls_both_scanners(tmp_path, monkeypatch):
    repo_root = tmp_path
    _write_component_fixture(repo_root)
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_MISS)
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER)
    _write(repo_root / "gen" / "generator" / "generator.py", GENERATOR_MODEL_CALL_ERROR)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_LOGGING)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_LOGGING)
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER)

    log_path = tmp_path / "call_log.jsonl"
    monkeypatch.setenv("AC_GATE_005_CALL_LOG", str(log_path))

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, model="fake-model-x",
    )

    assert _get(result, "provenance_hit") is False
    assert _get(result, "block_reason") == "model_call_error"
    assert _get(result, "model_call_error") == {
        "category": "network",
        "message": "connection refused",
    }

    license_scan = _get(result, "license_scan")
    secret_scan = _get(result, "secret_scan")
    assert _get(license_scan, "component_id") == "comp-foo"
    assert _get(license_scan, "gate_version") == "license_scanner@3.1.0"
    assert _get(secret_scan, "gate_version") == "secret_scanner@2.0.0"

    assert log_path.exists()
    records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    calls = {r["call"]: r for r in records}

    assert "license_scanner.scan" in calls
    assert calls["license_scanner.scan"]["component_id"] == "comp-foo"
    assert calls["license_scanner.scan"]["repo_root"] == str(repo_root)

    assert "secret_scanner.scan" in calls
    assert calls["secret_scanner.scan"]["repo_root"] == str(repo_root)


def test_short_circuiting_hit_skips_both_scanners(tmp_path, monkeypatch):
    repo_root = tmp_path
    _write_component_fixture(repo_root)
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_HIT)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_LOGGING)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_LOGGING)

    log_path = tmp_path / "call_log.jsonl"
    monkeypatch.setenv("AC_GATE_005_CALL_LOG", str(log_path))

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, model="fake-model-x",
    )

    assert _get(result, "provenance_hit") is True
    assert _get(result, "blocked") is False

    assert not log_path.exists() or log_path.read_text().strip() == ""
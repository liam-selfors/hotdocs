import json
from pathlib import Path

import component_gate_runner


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_fixture_component(repo_root: Path) -> None:
    component_md = """---
id: comp-widget
title: Widget
status: draft
owners: [fixture-owner]
sealed: false
depends_on: []
---

# Widget

## Purpose

Fixture component used only to exercise run_component_gates's
non-sealed, provenance-miss path for AC-GATE-003a.
"""
    _write(repo_root / "specs" / "components" / "widget" / "component.md", component_md)


def _write_provenance_checker_fake(repo_root: Path) -> None:
    content = '''
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
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
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", content)


def _write_spec_bundle_assembler_fake(repo_root: Path) -> None:
    content = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "fake spec",
        "interface": "fake interface",
        "constraints": "fake constraints",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary",
        "hint_code": None,
    }
'''
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", content)


def _write_generator_fake(repo_root: Path, call_log_path: Path) -> None:
    content = '''
CALL_LOG = {call_log!r}


def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    with open(CALL_LOG, "a") as f:
        f.write("call\\n")
    component_id = bundle["component_id"] if isinstance(bundle, dict) else bundle.component_id
    return {{
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {{"widget.py": "print('hello')"}},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }}
'''.format(call_log=str(call_log_path))
    _write(repo_root / "gen" / "generator" / "generator.py", content)


def _write_verifier_orchestrator_fake(repo_root: Path) -> None:
    content = '''
def verify(component_id, repo_root, judge=None, test_author=None):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-WIDGET-001", "covers": "R-WIDGET-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-WIDGET-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''
    _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", content)


def _write_license_scanner_fake(repo_root: Path) -> None:
    content = '''
def scan(component_id, repo_root):
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


def gate_version(repo_root):
    return "license_scanner@3.1.0"
'''
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", content)


def _write_secret_scanner_fake(repo_root: Path) -> None:
    content = '''
def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@2.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@2.0.0"
'''
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", content)


def _write_provenance_tracker_fake(repo_root: Path) -> None:
    content = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-000000",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", content)


def _write_provenance_writer_fake(repo_root: Path) -> None:
    content = '''
def write_provenance(component_id, inputs, repo_root):
    return None
'''
    _write(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", content)


def test_ac_gate_003a_generator_called_once_on_miss_with_passing_candidate(tmp_path):
    repo_root = tmp_path
    call_log_path = tmp_path / "generator_calls.log"

    _write_fixture_component(repo_root)
    _write_provenance_checker_fake(repo_root)
    _write_spec_bundle_assembler_fake(repo_root)
    _write_generator_fake(repo_root, call_log_path)
    _write_verifier_orchestrator_fake(repo_root)
    _write_license_scanner_fake(repo_root)
    _write_secret_scanner_fake(repo_root)
    _write_provenance_tracker_fake(repo_root)
    _write_provenance_writer_fake(repo_root)

    result = component_gate_runner.run_component_gates(
        component_id="comp-widget",
        repo_root=repo_root,
        model="fake-model",
        seed=0,
    )

    assert call_log_path.exists(), "generator fake was never invoked"
    call_count = call_log_path.read_text().count("call\n")
    assert call_count == 1

    assert _get(result, "blocked") is False
    assert _get(result, "block_reason") is None
    assert _get(result, "model_call_error") is None

    verification = _get(result, "verification")
    assert _get(verification, "overall") == "pass"
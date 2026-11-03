import os
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


_PROVENANCE_CHECKER_SRC = '''
_SPEC_HASH = "sha256:" + "a" * 64
_GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(_SPEC_HASH, dict(_GATE_VERSIONS))


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

_SPEC_BUNDLE_ASSEMBLER_SRC = '''
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "fake spec body",
        "interface": "fake interface body",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
'''

_GENERATOR_SRC = '''
import os


def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    log_path = os.path.join(str(repo_root), "_calls", "generator.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("call\\n")
    component_id = bundle["component_id"] if isinstance(bundle, dict) else bundle.component_id
    spec_bundle_hash = (
        bundle["spec_bundle_hash"] if isinstance(bundle, dict) else bundle.spec_bundle_hash
    )
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print(\\'hi\\')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_VERIFIER_ORCHESTRATOR_SRC = '''
GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''

_LICENSE_SCANNER_SRC = '''
def scan(component_id, repo_root):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "license_scanner@4.0.0"
'''

_SECRET_SCANNER_SRC = '''
def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.0.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@3.0.0+detect-secrets.1.5.0"
'''

_PROVENANCE_TRACKER_SRC = '''
import os


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    log_path = os.path.join(str(repo_root), "_calls", "write_attempt_record.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("call\\n")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''

_PROVENANCE_WRITER_SRC = '''
import os


def write_provenance(component_id, inputs, repo_root):
    log_path = os.path.join(str(repo_root), "_calls", "write_provenance.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("call\\n")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    raise NotImplementedError
'''


def _install_fake_dependencies(repo_root: Path) -> None:
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", _PROVENANCE_CHECKER_SRC)
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _SPEC_BUNDLE_ASSEMBLER_SRC,
    )
    _write(repo_root / "gen" / "generator" / "generator.py", _GENERATOR_SRC)
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        _VERIFIER_ORCHESTRATOR_SRC,
    )
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", _LICENSE_SCANNER_SRC)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", _SECRET_SCANNER_SRC)
    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        _PROVENANCE_TRACKER_SRC,
    )
    _write(
        repo_root / "gen" / "provenance-writer" / "provenance_writer.py",
        _PROVENANCE_WRITER_SRC,
    )


def test_miss_single_generator_call_passing_verification_not_blocked(tmp_path):
    repo_root = tmp_path
    _install_fake_dependencies(repo_root)

    result = component_gate_runner.run_component_gates(
        component_id="comp-foo",
        repo_root=repo_root,
        model="test-model",
        seed=0,
    )

    generator_log = repo_root / "_calls" / "generator.log"
    assert generator_log.exists()
    call_lines = generator_log.read_text(encoding="utf-8").splitlines()
    assert len(call_lines) == 1

    assert _get(result, "blocked") is False
    assert _get(result, "block_reason") is None
    assert _get(result, "model_call_error") is None

    verification = _get(result, "verification")
    assert verification is not None
    assert _get(verification, "overall") == "pass"
"""AC-GATE-003b: generator called exactly once (no retry loop) on a
provenance miss whose sole candidate fails verification; blocked is
True with block_reason "verification_failed"."""

import json
import os
import tempfile
from pathlib import Path

import component_gate_runner


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


PROVENANCE_CHECKER_SRC = '''
class _ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return _ProvenanceKey(
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

SPEC_BUNDLE_ASSEMBLER_SRC = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "glossary text",
        "hint_code": None,
    }
'''

GENERATOR_SRC = '''
import json
import os


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    log_path = os.environ["AC_GATE_003B_GENERATOR_CALL_LOG"]
    with open(log_path, "a") as f:
        f.write(json.dumps({"model": model, "retry_feedback": retry_feedback}) + "\\n")
    return {
        "component_id": "comp-widget",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"widget.py": "# generated candidate"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

VERIFIER_ORCHESTRATOR_SRC = '''
def verify(component_id, repo_root, judge=None, test_author=None):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
             "failure_detail": {"message": "check failed", "expected": True, "actual": False}},
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "overall": "fail",
    }
'''

LICENSE_SCANNER_SRC = '''
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
'''

SECRET_SCANNER_SRC = '''
def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@0.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''

PROVENANCE_TRACKER_SRC = '''
import os


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(attempts_dir, exist_ok=True)
    existing = len(os.listdir(attempts_dir))
    record_path = os.path.join(attempts_dir, "attempt-%d.json" % existing)
    with open(record_path, "w") as f:
        f.write("{}")
    return {
        "attempt_id": "attempt-%d" % existing,
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''

PROVENANCE_WRITER_SRC = '''
def write_provenance(component_id, inputs, repo_root):
    return None
'''


def test_ac_gate_003b_generator_called_once_on_verification_failure():
    with tempfile.TemporaryDirectory() as repo_root_str:
        repo_root = Path(repo_root_str)

        _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_SRC)
        _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER_SRC)
        _write(repo_root / "gen" / "generator" / "generator.py", GENERATOR_SRC)
        _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_ORCHESTRATOR_SRC)
        _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_SRC)
        _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC)
        _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER_SRC)
        _write(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", PROVENANCE_WRITER_SRC)

        call_log_path = repo_root / "generator_calls.jsonl"
        os.environ["AC_GATE_003B_GENERATOR_CALL_LOG"] = str(call_log_path)
        try:
            result = component_gate_runner.run_component_gates(
                "comp-widget", repo_root, "fake-model-1",
            )
        finally:
            del os.environ["AC_GATE_003B_GENERATOR_CALL_LOG"]

        assert call_log_path.exists(), "generator fake was never invoked"
        call_lines = call_log_path.read_text().strip().splitlines()
        assert len(call_lines) == 1, (
            "generator must be called exactly once per non-sealed miss; got %d calls"
            % len(call_lines)
        )
        call_record = json.loads(call_lines[0])
        assert call_record["retry_feedback"] is None

        assert _get(result, "blocked") is True
        assert _get(result, "block_reason") == "verification_failed"
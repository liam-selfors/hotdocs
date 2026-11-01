import json
import os

import pytest

from component_gate_runner import run_component_gates


def field(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def write_fake(repo_root, slug, module_name, content):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(content)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@3.1.0",
    "secret_scanner": "secret_scanner@0.0.0",
}

PROVENANCE_CHECKER_SRC = f"""
def current_provenance_key(component_id, repo_root):
    return {{"spec_bundle_hash": "sha256:k", "gate_versions": {GATE_VERSIONS!r}}}


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {{"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}}
"""

SPEC_BUNDLE_ASSEMBLER_SRC = """
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:k",
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
"""

LICENSE_SCANNER_SRC = """
import json
import os


def scan(component_id, repo_root):
    log_path = os.environ.get("GATE_TEST_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write(json.dumps({"event": "license_scan"}) + "\\n")
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
"""

SECRET_SCANNER_SRC = """
import json
import os


def scan(repo_root):
    log_path = os.environ.get("GATE_TEST_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write(json.dumps({"event": "secret_scan"}) + "\\n")
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
"""

PROVENANCE_WRITER_SRC = """
def write_provenance(component_id, inputs, repo_root):
    return None
"""

WRITE_ATTEMPT_RECORD_LOGGING_SRC = """
import json
import os


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    log_path = os.environ.get("GATE_TEST_LOG")
    if log_path:
        with open(log_path, "a") as f:
            f.write(json.dumps({
                "event": "write_attempt_record",
                "component_id": component_id,
                "generation_result": generation_result,
                "verification_report": verification_report,
                "spec_bundle_hash": spec_bundle_hash,
            }) + "\\n")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
"""

WRITE_ATTEMPT_RECORD_RAISING_SRC = """
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    raise RuntimeError("boom")
"""


def install_common_fakes(repo_root, write_attempt_record_src):
    write_fake(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    write_fake(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
    write_fake(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
    write_fake(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)
    write_fake(repo_root, "provenance-tracker", "provenance_tracker", write_attempt_record_src)


def test_write_attempt_record_called_once_after_both_scans_with_full_args(tmp_path, monkeypatch):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    install_common_fakes(tmp_path, WRITE_ATTEMPT_RECORD_LOGGING_SRC)

    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": "fake-model",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "fail",
    }

    generator_src = f"""
def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    return {generation_result!r}
"""
    verifier_src = f"""
def verify(component_id, repo_root, judge=None, test_author=None):
    return {verification_report!r}
"""
    write_fake(tmp_path, "generator", "generator", generator_src)
    write_fake(tmp_path, "verifier-orchestrator", "verifier_orchestrator", verifier_src)
    write_fake(tmp_path, "provenance-writer", "provenance_writer", PROVENANCE_WRITER_SRC)

    run_component_gates(component_id="comp-foo", repo_root=tmp_path, model="fake-model")

    assert log_path.exists()
    events = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]

    write_events = [e for e in events if e["event"] == "write_attempt_record"]
    assert len(write_events) == 1

    write_index = events.index(write_events[0])
    scan_indices = [i for i, e in enumerate(events) if e["event"] in ("license_scan", "secret_scan")]
    assert len(scan_indices) == 2
    assert write_index > max(scan_indices)

    recorded = write_events[0]
    assert recorded["component_id"] == "comp-foo"
    assert recorded["generation_result"] == generation_result
    assert recorded["verification_report"] == verification_report
    assert recorded["spec_bundle_hash"] == "sha256:k"


def test_write_attempt_record_receives_none_verification_on_model_call_error(tmp_path, monkeypatch):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    install_common_fakes(tmp_path, WRITE_ATTEMPT_RECORD_LOGGING_SRC)

    generator_src = """
def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""
    write_fake(tmp_path, "generator", "generator", generator_src)
    # No verifier-orchestrator fake is installed: files is empty, so verification
    # must never be reached, and no provenance-writer fake either, since step 3
    # produced no files.

    run_component_gates(component_id="comp-foo", repo_root=tmp_path, model="fake-model")

    assert log_path.exists()
    events = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    write_events = [e for e in events if e["event"] == "write_attempt_record"]
    assert len(write_events) == 1
    assert write_events[0]["verification_report"] is None


def test_write_attempt_record_exception_does_not_change_result(tmp_path, monkeypatch):
    log_path = tmp_path / "log.jsonl"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    install_common_fakes(tmp_path, WRITE_ATTEMPT_RECORD_RAISING_SRC)

    generation_result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": "fake-model",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }

    generator_src = f"""
def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    return {generation_result!r}
"""
    verifier_src = f"""
def verify(component_id, repo_root, judge=None, test_author=None):
    return {verification_report!r}
"""
    write_fake(tmp_path, "generator", "generator", generator_src)
    write_fake(tmp_path, "verifier-orchestrator", "verifier_orchestrator", verifier_src)
    write_fake(tmp_path, "provenance-writer", "provenance_writer", PROVENANCE_WRITER_SRC)

    result = run_component_gates(component_id="comp-foo", repo_root=tmp_path, model="fake-model")

    assert field(result, "blocked") is False
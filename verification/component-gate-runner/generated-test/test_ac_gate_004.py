import os
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


_PROVENANCE_CHECKER_SRC = """
import os


class _Key(object):
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("provenance_checker.current_sealed_key\\n")
    return None


def current_provenance_key(component_id, repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("provenance_checker.current_provenance_key\\n")
    return _Key(
        spec_bundle_hash="sha256:" + "0" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@1.0.0",
            "secret_scanner": "secret_scanner@1.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("provenance_checker.check_provenance\\n")
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
"""


_SPEC_BUNDLE_ASSEMBLER_SRC = """
import os


def assemble(component_id, repo_root=None, mode="cold"):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("spec_bundle_assembler.assemble\\n")
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
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


_GENERATOR_ERROR_SRC = """
import os


def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("generator.generate\\n")
    return {
        "component_id": bundle["component_id"],
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "connection refused"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


_GENERATOR_FILES_SRC = """
import os


def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("generator.generate\\n")
    return {
        "component_id": bundle["component_id"],
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"widget.py": "# generated\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


_VERIFIER_ORCHESTRATOR_SRC_TEMPLATE = """
import os

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("verifier_orchestrator.verify\\n")
    return {{
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {{}},
        "interface_drift": False,
        "mutation_score": 0.5,
        "overall": "{overall}",
    }}
"""


_LICENSE_SCANNER_SRC = """
import os


def scan(component_id, repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("license_scanner.scan\\n")
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0-no-reference-corpus",
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
    return "license_scanner@4.0.0-no-reference-corpus"
"""


_SECRET_SCANNER_SRC = """
import os


def scan(repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("secret_scanner.scan\\n")
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
"""


_PROVENANCE_TRACKER_SRC = """
import os
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("provenance_tracker.write_attempt_record\\n")
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-0001.json").write_text("{}")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result if isinstance(generation_result, dict) else {},
        "verification": verification_report,
    }
"""


_PROVENANCE_WRITER_SRC = """
import os


def write_provenance(component_id, inputs, repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("provenance_writer.write_provenance\\n")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    with open(os.environ["GATE_RUNNER_TEST_LOG"], "a") as f:
        f.write("provenance_writer.write_sealed_provenance\\n")
    return None
"""


def _write_common_fakes(repo_root):
    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", _PROVENANCE_CHECKER_SRC)
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", _SPEC_BUNDLE_ASSEMBLER_SRC)
    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", _LICENSE_SCANNER_SRC)
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", _SECRET_SCANNER_SRC)
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", _PROVENANCE_TRACKER_SRC)
    _write(repo_root / "gen" / "provenance-writer" / "provenance_writer.py", _PROVENANCE_WRITER_SRC)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text().splitlines() if line]


def test_model_call_error_blocks_without_calling_verify(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    monkeypatch.setenv("GATE_RUNNER_TEST_LOG", str(log_path))

    _write_common_fakes(repo_root)
    _write(repo_root / "gen" / "generator" / "generator.py", _GENERATOR_ERROR_SRC)
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        _VERIFIER_ORCHESTRATOR_SRC_TEMPLATE.format(overall="fail"),
    )

    result = component_gate_runner.run_component_gates(
        "comp-widget", repo_root, "fake-model-id"
    )

    calls = _read_log(log_path)
    assert "generator.generate" in calls
    assert "verifier_orchestrator.verify" not in calls

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "model_call_error"
    mce = _get(result, "model_call_error")
    assert _get(mce, "category") == "network"
    assert _get(mce, "message") == "connection refused"
    assert _get(result, "verification") is None


def test_verification_failure_sets_block_reason(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "invocations.log"
    monkeypatch.setenv("GATE_RUNNER_TEST_LOG", str(log_path))

    _write_common_fakes(repo_root)
    _write(repo_root / "gen" / "generator" / "generator.py", _GENERATOR_FILES_SRC)
    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        _VERIFIER_ORCHESTRATOR_SRC_TEMPLATE.format(overall="fail"),
    )

    result = component_gate_runner.run_component_gates(
        "comp-widget", repo_root, "fake-model-id"
    )

    calls = _read_log(log_path)
    assert "generator.generate" in calls
    assert "verifier_orchestrator.verify" in calls

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "verification_failed"
    assert _get(result, "model_call_error") is None
    verification = _get(result, "verification")
    assert verification is not None
    assert _get(verification, "overall") == "fail"
"""Tests for AC-GATE-004 (component-gate-runner): block_reason distinguishes
model_call_error (no candidate produced, verify never called) from
verification_failed (a candidate was produced and failed)."""

import os
from pathlib import Path

import pytest

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_module(repo_root, dep_slug, module_name, content):
    path = repo_root / "gen" / dep_slug / (module_name + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


_PROVENANCE_CHECKER_MODULE = """
import os
from dataclasses import dataclass

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class ProvenanceKey:
    spec_bundle_hash: str
    gate_versions: dict


@dataclass
class ProvenanceCheckResult:
    hit: bool
    verification_report: object = None
    license_scan: object = None
    secret_scan: object = None


def current_sealed_key(component_id, repo_root):
    _log("provenance_checker.current_sealed_key")
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance_checker.current_provenance_key")
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("provenance_checker.check_provenance")
    return ProvenanceCheckResult(hit=False)
"""


_SPEC_BUNDLE_ASSEMBLER_MODULE = """
import os
from dataclasses import dataclass, field

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str = ""
    interface: str = ""
    constraints: str = ""
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


def assemble(component_id, repo_root, mode="cold"):
    _log("spec_bundle_assembler.assemble")
    return SpecBundle(component_id=component_id, spec_bundle_hash="sha256:" + "a" * 64)
"""


_LICENSE_SCANNER_MODULE = """
import os
from dataclasses import dataclass, field

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class LicenseScanResult:
    component_id: str
    gate_version: str
    evaluated: bool
    reason: object
    similarity_score: object
    block_threshold: object
    blocked: bool
    matches: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool


def scan(component_id, repo_root):
    _log("license_scanner.scan")
    return LicenseScanResult(
        component_id=component_id,
        gate_version="license_scanner@4.0.0-no-reference-corpus",
        evaluated=False,
        reason="no-reference-corpus",
        similarity_score=None,
        block_threshold=None,
        blocked=False,
        matches=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"
"""


_SECRET_SCANNER_MODULE = """
import os
from dataclasses import dataclass, field

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class SecretScanResult:
    scope: str
    gate_version: str
    flagged: bool
    matches: list
    allowed: list
    unused_allowlist_entries: list
    notified: bool
    notification_delivery_error: object
    cache_hit: bool


def scan(repo_root):
    _log("secret_scanner.scan")
    return SecretScanResult(
        scope="full",
        gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"
"""


_PROVENANCE_TRACKER_MODULE = """
import os
from dataclasses import dataclass

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class AttemptRecord:
    attempt_id: str
    component_id: str
    timestamp: str
    spec_bundle_hash: str
    generation: dict
    verification: object


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("provenance_tracker.write_attempt_record")
    return AttemptRecord(
        attempt_id="2026-01-01T00:00:00Z-abcdef",
        component_id=component_id,
        timestamp="2026-01-01T00:00:00Z",
        spec_bundle_hash=spec_bundle_hash,
        generation={},
        verification=None,
    )
"""


_PROVENANCE_WRITER_MODULE = """
import os

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


def write_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_provenance")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_sealed_provenance")
    return None
"""


_GENERATOR_MODULE_MODEL_CALL_ERROR = """
import os
from dataclasses import dataclass

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict
    model_call_error: object
    refused: object
    retry_feedback: object


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generator.generate")
    return GenerationResult(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        model=model,
        prompt_version="v1",
        cache_hit=False,
        files={},
        model_call_error={"category": "network", "message": "connection refused"},
        refused=None,
        retry_feedback=retry_feedback,
    )
"""


_GENERATOR_MODULE_ONE_FILE = """
import os
from dataclasses import dataclass

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class GenerationResult:
    component_id: str
    spec_bundle_hash: str
    model: str
    prompt_version: str
    cache_hit: bool
    files: dict
    model_call_error: object
    refused: object
    retry_feedback: object


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    _log("generator.generate")
    return GenerationResult(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "a" * 64,
        model=model,
        prompt_version="v1",
        cache_hit=False,
        files={"foo.py": "print(1)\\n"},
        model_call_error=None,
        refused=None,
        retry_feedback=retry_feedback,
    )
"""


_VERIFIER_ORCHESTRATOR_MODULE_LOG_ONLY = """
import os
from dataclasses import dataclass, field

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]
GATE_VERSION = "verifier-orchestrator@2.0.0"


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class VerificationReport:
    component_id: str
    criteria: list = field(default_factory=list)
    requirement_results: dict = field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: object = None
    overall: str = "pass"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier_orchestrator.verify")
    return VerificationReport(component_id=component_id, overall="pass")
"""


_VERIFIER_ORCHESTRATOR_MODULE_FAIL = """
import os
from dataclasses import dataclass, field

LOG_PATH = os.environ["GATE_TEST_LOG_PATH"]
GATE_VERSION = "verifier-orchestrator@2.0.0"


def _log(entry):
    with open(LOG_PATH, "a") as f:
        f.write(entry + "\\n")


@dataclass
class VerificationReport:
    component_id: str
    criteria: list = field(default_factory=list)
    requirement_results: dict = field(default_factory=dict)
    interface_drift: bool = False
    mutation_score: object = None
    overall: str = "fail"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier_orchestrator.verify")
    return VerificationReport(
        component_id=component_id,
        criteria=[
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "assertion failed", "expected": 1, "actual": 2},
            }
        ],
        requirement_results={"R-FOO-001": "fail"},
        interface_drift=False,
        mutation_score=0.5,
        overall="fail",
    )
"""


def _write_common_modules(repo_root):
    _write_module(repo_root, "provenance-checker", "provenance_checker", _PROVENANCE_CHECKER_MODULE)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER_MODULE)
    _write_module(repo_root, "license-scanner", "license_scanner", _LICENSE_SCANNER_MODULE)
    _write_module(repo_root, "secret-scanner", "secret_scanner", _SECRET_SCANNER_MODULE)
    _write_module(repo_root, "provenance-tracker", "provenance_tracker", _PROVENANCE_TRACKER_MODULE)
    _write_module(repo_root, "provenance-writer", "provenance_writer", _PROVENANCE_WRITER_MODULE)


def test_model_call_error_blocks_before_verify_is_called(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG_PATH", str(log_path))

    _write_common_modules(repo_root)
    _write_module(repo_root, "generator", "generator", _GENERATOR_MODULE_MODEL_CALL_ERROR)
    _write_module(
        repo_root, "verifier-orchestrator", "verifier_orchestrator", _VERIFIER_ORCHESTRATOR_MODULE_LOG_ONLY
    )

    result = component_gate_runner.run_component_gates(
        component_id="comp-foo",
        repo_root=repo_root,
        model="claude-sonnet-5",
        seed=0,
        llm_backend=None,
        retry_feedback=None,
    )

    log_lines = log_path.read_text().splitlines() if log_path.exists() else []
    assert "verifier_orchestrator.verify" not in log_lines

    assert _get(result, "block_reason") == "model_call_error"
    assert _get(result, "blocked") is True
    assert _get(result, "verification") is None


def test_verification_failure_sets_block_reason(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG_PATH", str(log_path))

    _write_common_modules(repo_root)
    _write_module(repo_root, "generator", "generator", _GENERATOR_MODULE_ONE_FILE)
    _write_module(
        repo_root, "verifier-orchestrator", "verifier_orchestrator", _VERIFIER_ORCHESTRATOR_MODULE_FAIL
    )

    result = component_gate_runner.run_component_gates(
        component_id="comp-foo",
        repo_root=repo_root,
        model="claude-sonnet-5",
        seed=0,
        llm_backend=None,
        retry_feedback=None,
    )

    log_lines = log_path.read_text().splitlines() if log_path.exists() else []
    assert "verifier_orchestrator.verify" in log_lines

    assert _get(result, "block_reason") == "verification_failed"
    assert _get(result, "model_call_error") is None
    assert _get(result, "blocked") is True
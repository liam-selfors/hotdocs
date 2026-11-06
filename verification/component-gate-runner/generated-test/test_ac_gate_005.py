import json
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_module(repo_root: Path, dep_slug: str, module_name: str, content: str) -> None:
    mod_dir = repo_root / "gen" / dep_slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(content)


_PROVENANCE_CHECKER_MISS = """
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
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
"""


_SPEC_BUNDLE_ASSEMBLER = """
def assemble(component_id, repo_root=None, mode="cold"):
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
"""


_GENERATOR_MODEL_CALL_ERROR = """
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
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
        "files": {},
        "model_call_error": {"category": "rate_limit", "message": "429 from backend"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


_LICENSE_SCANNER_LOGGING = """
import json
import os


def scan(component_id, repo_root):
    log_path = os.environ["CALL_LOG_PATH"]
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "dep": "license_scanner",
            "component_id": component_id,
            "repo_root": str(repo_root),
        }) + "\\n")
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.1,
        "block_threshold": 0.70,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
"""


_SECRET_SCANNER_LOGGING = """
import json
import os


class SecretScanResult:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def to_dict(self):
        return dict(self.__dict__)


def scan(repo_root):
    log_path = os.environ["CALL_LOG_PATH"]
    with open(log_path, "a") as f:
        f.write(json.dumps({
            "dep": "secret_scanner",
            "repo_root": str(repo_root),
        }) + "\\n")
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
"""


_PROVENANCE_TRACKER = """
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
"""


def test_miss_with_model_call_error_invokes_both_scanners(tmp_path, monkeypatch):
    repo_root = tmp_path
    log_path = repo_root / "calls.log"
    monkeypatch.setenv("CALL_LOG_PATH", str(log_path))

    _write_module(repo_root, "provenance-checker", "provenance_checker", _PROVENANCE_CHECKER_MISS)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER)
    _write_module(repo_root, "generator", "generator", _GENERATOR_MODEL_CALL_ERROR)
    _write_module(repo_root, "license-scanner", "license_scanner", _LICENSE_SCANNER_LOGGING)
    _write_module(repo_root, "secret-scanner", "secret_scanner", _SECRET_SCANNER_LOGGING)
    _write_module(repo_root, "provenance-tracker", "provenance_tracker", _PROVENANCE_TRACKER)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "fake-model-1",
    )

    assert log_path.exists()
    records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]

    license_calls = [r for r in records if r["dep"] == "license_scanner"]
    assert len(license_calls) == 1
    assert license_calls[0]["component_id"] == "comp-foo"
    assert license_calls[0]["repo_root"] == str(repo_root)

    secret_calls = [r for r in records if r["dep"] == "secret_scanner"]
    assert len(secret_calls) == 1
    assert secret_calls[0]["repo_root"] == str(repo_root)

    assert _get(result, "provenance_hit") is False
    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "model_call_error"
    assert _get(result, "verification") is None

    model_call_error = _get(result, "model_call_error")
    assert model_call_error is not None
    assert _get(model_call_error, "category") == "rate_limit"

    license_scan = _get(result, "license_scan")
    assert license_scan is not None
    assert _get(license_scan, "gate_version") == "license_scanner@4.0.3+9f2c41ab07de"
    assert _get(license_scan, "similarity_score") == 0.1
    assert _get(license_scan, "blocked") is False

    secret_scan = _get(result, "secret_scan")
    assert secret_scan is not None
    assert _get(secret_scan, "gate_version") == "secret_scanner@3.1.0+detect-secrets.1.5.0"
    assert _get(secret_scan, "flagged") is False


_PROVENANCE_CHECKER_HIT = """
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "b" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
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
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.05,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": True,
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
            "cache_hit": True,
        },
    }
"""


def test_short_circuiting_hit_skips_both_scanners(tmp_path, monkeypatch):
    repo_root = tmp_path
    log_path = repo_root / "calls.log"
    monkeypatch.setenv("CALL_LOG_PATH", str(log_path))

    _write_module(repo_root, "provenance-checker", "provenance_checker", _PROVENANCE_CHECKER_HIT)
    _write_module(repo_root, "license-scanner", "license_scanner", _LICENSE_SCANNER_LOGGING)
    _write_module(repo_root, "secret-scanner", "secret_scanner", _SECRET_SCANNER_LOGGING)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "fake-model-2",
    )

    assert not log_path.exists()

    assert _get(result, "provenance_hit") is True
    assert _get(result, "blocked") is False
    assert _get(result, "block_reason") is None
    assert _get(result, "model_call_error") is None

    verification = _get(result, "verification")
    assert verification is not None
    assert _get(verification, "overall") == "pass"

    license_scan = _get(result, "license_scan")
    assert license_scan is not None
    assert _get(license_scan, "cache_hit") is True

    secret_scan = _get(result, "secret_scan")
    assert secret_scan is not None
    assert _get(secret_scan, "cache_hit") is True
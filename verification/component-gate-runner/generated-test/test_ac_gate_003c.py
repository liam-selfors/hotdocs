import os
import tempfile
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_PROVENANCE_CHECKER_SRC = '''
def current_sealed_key(component_id, repo_root):
    return None


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
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
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

_SPEC_BUNDLE_ASSEMBLER_SRC = '''
class SpecBundle:
    def __init__(self, component_id, spec_bundle_hash):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.spec = ""
        self.interface = ""
        self.constraints = ""
        self.dependency_interfaces = {}
        self.dependency_context = {}
        self.dependency_usage = {}
        self.vars = {}
        self.glossary = ""
        self.hint_code = None


def assemble(component_id, repo_root, mode="cold"):
    return SpecBundle(component_id, "sha256:" + "b" * 64)
'''

_GENERATOR_SRC = '''
import os


def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    log_path = os.environ["GATE_TEST_GENERATOR_LOG"]
    with open(log_path, "a", encoding="utf-8") as f:
        f.write("called\\n")

    component_id = bundle.component_id if hasattr(bundle, "component_id") else bundle["component_id"]
    spec_bundle_hash = (
        bundle.spec_bundle_hash if hasattr(bundle, "spec_bundle_hash") else bundle["spec_bundle_hash"]
    )

    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "timeout", "message": "t"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_LICENSE_SCANNER_SRC = '''
def scan(component_id, repo_root):
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
'''

_SECRET_SCANNER_SRC = '''
def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"
'''

_PROVENANCE_TRACKER_SRC = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "test-attempt",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''


def _write_fake_dependency(repo_root, slug, module_name, source):
    module_dir = Path(repo_root) / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / f"{module_name}.py").write_text(source, encoding="utf-8")


def test_miss_with_model_call_error_blocks_after_exactly_one_generator_call():
    with tempfile.TemporaryDirectory() as repo_root, tempfile.TemporaryDirectory() as log_dir:
        _write_fake_dependency(repo_root, "provenance-checker", "provenance_checker", _PROVENANCE_CHECKER_SRC)
        _write_fake_dependency(
            repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER_SRC
        )
        _write_fake_dependency(repo_root, "generator", "generator", _GENERATOR_SRC)
        _write_fake_dependency(repo_root, "license-scanner", "license_scanner", _LICENSE_SCANNER_SRC)
        _write_fake_dependency(repo_root, "secret-scanner", "secret_scanner", _SECRET_SCANNER_SRC)
        _write_fake_dependency(repo_root, "provenance-tracker", "provenance_tracker", _PROVENANCE_TRACKER_SRC)

        log_path = str(Path(log_dir) / "generator_calls.log")
        old_env = os.environ.get("GATE_TEST_GENERATOR_LOG")
        os.environ["GATE_TEST_GENERATOR_LOG"] = log_path
        try:
            result = component_gate_runner.run_component_gates(
                "comp-foo",
                Path(repo_root),
                model="mock-model",
                seed=0,
                llm_backend=None,
                retry_feedback=None,
            )
        finally:
            if old_env is None:
                os.environ.pop("GATE_TEST_GENERATOR_LOG", None)
            else:
                os.environ["GATE_TEST_GENERATOR_LOG"] = old_env

        assert os.path.exists(log_path), "generator fake was never invoked"
        with open(log_path, "r", encoding="utf-8") as f:
            call_lines = [line for line in f.read().splitlines() if line == "called"]
        assert len(call_lines) == 1, f"expected generator called exactly once, got {len(call_lines)}"

        assert _get(result, "blocked") is True
        assert _get(result, "block_reason") == "model_call_error"
        assert _get(result, "verification") is None

        model_call_error = _get(result, "model_call_error")
        assert model_call_error is not None
        assert _get(model_call_error, "category") == "timeout"
        assert _get(model_call_error, "message") == "t"
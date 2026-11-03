import os
import shutil
import tempfile
import unittest
from pathlib import Path

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


PROVENANCE_CHECKER_SRC = """
class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "0" * 64,
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
"""

SPEC_BUNDLE_ASSEMBLER_SRC = """
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
"""

GENERATOR_SRC = """
import os


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    log_path = os.environ["AC_GATE_003C_GEN_CALL_LOG"]
    with open(log_path, "a") as f:
        f.write("call\\n")
    return {
        "component_id": _get(bundle, "component_id"),
        "spec_bundle_hash": _get(bundle, "spec_bundle_hash"),
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "timeout", "message": "t"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""

LICENSE_SCANNER_SRC = """
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
"""

SECRET_SCANNER_SRC = """
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
"""

PROVENANCE_TRACKER_SRC = """
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


class RunComponentGatesModelCallErrorTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp())
        self._log_dir = Path(tempfile.mkdtemp())
        self.call_log = self._log_dir / "generator_calls.log"
        os.environ["AC_GATE_003C_GEN_CALL_LOG"] = str(self.call_log)

    def tearDown(self):
        shutil.rmtree(self.repo_root, ignore_errors=True)
        shutil.rmtree(self._log_dir, ignore_errors=True)
        os.environ.pop("AC_GATE_003C_GEN_CALL_LOG", None)

    def _write_module(self, slug, module_name, content):
        module_dir = self.repo_root / "gen" / slug
        module_dir.mkdir(parents=True, exist_ok=True)
        (module_dir / (module_name + ".py")).write_text(content)

    def test_model_call_error_blocks_with_single_generator_call(self):
        self._write_module("provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
        self._write_module("spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
        self._write_module("generator", "generator", GENERATOR_SRC)
        self._write_module("license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
        self._write_module("secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)
        self._write_module("provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_SRC)

        result = component_gate_runner.run_component_gates(
            "comp-foo", self.repo_root, model="claude-sonnet-5"
        )

        self.assertTrue(self.call_log.exists())
        calls = [line for line in self.call_log.read_text().splitlines() if line]
        self.assertEqual(len(calls), 1)

        self.assertTrue(_get(result, "blocked"))
        self.assertEqual(_get(result, "block_reason"), "model_call_error")

        error = _get(result, "model_call_error")
        self.assertIsNotNone(error)
        self.assertEqual(_get(error, "category"), "timeout")
        self.assertEqual(_get(error, "message"), "t")

        self.assertIsNone(_get(result, "verification"))


if __name__ == "__main__":
    unittest.main()
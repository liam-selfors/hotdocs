import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import component_gate_runner


def _write_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    module_dir = os.path.join(repo_root, "gen", slug)
    os.makedirs(module_dir, exist_ok=True)
    module_path = os.path.join(module_dir, module_name + ".py")
    with open(module_path, "w") as f:
        f.write(source)


_PROVENANCE_CHECKER_SRC = '''
import types

def current_provenance_key(component_id, repo_root):
    return types.SimpleNamespace(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={"verifier": "v@1"},
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

_GENERATOR_WITH_FILE_SRC = '''
def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print(1)"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_GENERATOR_MODEL_CALL_ERROR_SRC = '''
def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_VERIFIER_ORCHESTRATOR_SRC = '''
import os

GATE_VERSION = "verifier-orchestrator@2.0.0"

def verify(component_id, repo_root, judge=None, test_author=None):
    with open(os.path.join(str(repo_root), "call_log.txt"), "a") as f:
        f.write("verify\\n")
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''

_LICENSE_SCANNER_SRC = '''
import os

def scan(component_id, repo_root):
    with open(os.path.join(str(repo_root), "call_log.txt"), "a") as f:
        f.write("license_scan\\n")
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

_SECRET_SCANNER_SRC = '''
import os

def scan(repo_root):
    with open(os.path.join(str(repo_root), "call_log.txt"), "a") as f:
        f.write("secret_scan\\n")
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

_PROVENANCE_TRACKER_SRC = '''
import os
import json

def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    with open(os.path.join(str(repo_root), "call_log.txt"), "a") as f:
        f.write("write_attempt_record\\n")
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(attempts_dir, exist_ok=True)
    attempt_path = os.path.join(attempts_dir, "attempt-0001.json")
    record = {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
    with open(attempt_path, "w") as f:
        json.dump(record, f)
    return record
'''

_PROVENANCE_WRITER_SRC = '''
import os
import json

def write_provenance(component_id, inputs, repo_root):
    with open(os.path.join(str(repo_root), "call_log.txt"), "a") as f:
        f.write("write_provenance\\n")
    capture_path = os.path.join(str(repo_root), "write_provenance_calls.jsonl")
    with open(capture_path, "a") as f:
        f.write(json.dumps({"component_id": component_id, "inputs": inputs}) + "\\n")
'''


class RunComponentGatesProvenanceWriteTest(unittest.TestCase):
    def setUp(self):
        self._repo_root = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self._repo_root, ignore_errors=True)

    def _call_log(self):
        log_path = os.path.join(self._repo_root, "call_log.txt")
        if not os.path.exists(log_path):
            return []
        with open(log_path) as f:
            return [line.strip() for line in f if line.strip()]

    def _write_provenance_calls(self):
        capture_path = os.path.join(self._repo_root, "write_provenance_calls.jsonl")
        if not os.path.exists(capture_path):
            return []
        with open(capture_path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_miss_with_generated_file_writes_provenance_after_scans_and_attempt_record(self):
        _write_module(self._repo_root, "provenance-checker", _PROVENANCE_CHECKER_SRC)
        _write_module(self._repo_root, "spec-bundle-assembler", _SPEC_BUNDLE_ASSEMBLER_SRC)
        _write_module(self._repo_root, "generator", _GENERATOR_WITH_FILE_SRC)
        _write_module(self._repo_root, "verifier-orchestrator", _VERIFIER_ORCHESTRATOR_SRC)
        _write_module(self._repo_root, "license-scanner", _LICENSE_SCANNER_SRC)
        _write_module(self._repo_root, "secret-scanner", _SECRET_SCANNER_SRC)
        _write_module(self._repo_root, "provenance-tracker", _PROVENANCE_TRACKER_SRC)
        _write_module(self._repo_root, "provenance-writer", _PROVENANCE_WRITER_SRC)

        component_gate_runner.run_component_gates(
            component_id="comp-foo",
            repo_root=Path(self._repo_root),
            model="test-model-v1",
        )

        calls = self._call_log()
        for name in ("verify", "license_scan", "secret_scan", "write_attempt_record", "write_provenance"):
            self.assertIn(name, calls)

        verify_index = calls.index("verify")
        license_scan_index = calls.index("license_scan")
        secret_scan_index = calls.index("secret_scan")
        write_attempt_record_index = calls.index("write_attempt_record")
        write_provenance_index = calls.index("write_provenance")

        self.assertLess(verify_index, write_attempt_record_index)
        self.assertLess(license_scan_index, write_attempt_record_index)
        self.assertLess(secret_scan_index, write_attempt_record_index)
        self.assertLess(write_attempt_record_index, write_provenance_index)

        provenance_calls = self._write_provenance_calls()
        self.assertEqual(len(provenance_calls), 1)
        recorded = provenance_calls[0]
        inputs = recorded["inputs"]

        self.assertEqual(inputs["gate_versions"], {"verifier": "v@1"})
        self.assertEqual(inputs["provenance_hit"], False)
        self.assertEqual(inputs["attempts"], 1)
        self.assertEqual(
            inputs["generation_result"],
            {
                "component_id": "comp-foo",
                "spec_bundle_hash": "sha256:" + "a" * 64,
                "model": "test-model-v1",
                "prompt_version": "v1",
                "cache_hit": False,
                "files": {"foo.py": "print(1)"},
                "model_call_error": None,
                "refused": None,
                "retry_feedback": None,
            },
        )
        self.assertEqual(
            inputs["verification_report"],
            {
                "component_id": "comp-foo",
                "criteria": [],
                "requirement_results": {},
                "interface_drift": False,
                "mutation_score": 1.0,
                "overall": "pass",
            },
        )
        self.assertEqual(
            inputs["license_scan_result"],
            {
                "component_id": "comp-foo",
                "gate_version": "license_scanner@3.1.0",
                "similarity_score": 0.0,
                "block_threshold": 0.70,
                "blocked": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
        )
        self.assertEqual(
            inputs["secret_scan_result"],
            {
                "scope": "full",
                "gate_version": "secret_scanner@2.0.0",
                "flagged": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            },
        )

    def test_model_call_error_never_writes_provenance(self):
        _write_module(self._repo_root, "provenance-checker", _PROVENANCE_CHECKER_SRC)
        _write_module(self._repo_root, "spec-bundle-assembler", _SPEC_BUNDLE_ASSEMBLER_SRC)
        _write_module(self._repo_root, "generator", _GENERATOR_MODEL_CALL_ERROR_SRC)
        _write_module(self._repo_root, "license-scanner", _LICENSE_SCANNER_SRC)
        _write_module(self._repo_root, "secret-scanner", _SECRET_SCANNER_SRC)
        _write_module(self._repo_root, "provenance-tracker", _PROVENANCE_TRACKER_SRC)
        _write_module(self._repo_root, "provenance-writer", _PROVENANCE_WRITER_SRC)

        component_gate_runner.run_component_gates(
            component_id="comp-foo",
            repo_root=Path(self._repo_root),
            model="test-model-v1",
        )

        self.assertEqual(self._write_provenance_calls(), [])
        self.assertNotIn("write_provenance", self._call_log())


if __name__ == "__main__":
    unittest.main()
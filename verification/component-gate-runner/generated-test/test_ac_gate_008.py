import json
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


_LOG_HELPER = r'''
import json
import os


def _log(event, data):
    path = os.environ["AC_GATE_008_LOG"]
    with open(path, "a") as f:
        f.write(json.dumps({"event": event, "data": data}) + "\n")
'''


PROVENANCE_CHECKER_SRC = _LOG_HELPER + r'''
class _Key:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", {"component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", {"component_id": component_id})
    return _Key("sha256:k", {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.0-test",
        "secret_scanner": "secret_scanner@0.0.0",
    })


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", {"component_id": component_id, "spec_bundle_hash": spec_bundle_hash})
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", {"component_id": component_id})
    return {
        "hit": False,
        "sealed": False,
        "reason": "not_sealed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
'''


SPEC_BUNDLE_ASSEMBLER_SRC = _LOG_HELPER + r'''
def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", {"component_id": component_id, "mode": mode})
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:k",
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


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError
'''


GENERATOR_SUCCESS_SRC = _LOG_HELPER + r'''
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        component_id = bundle.get("component_id")
        spec_bundle_hash = bundle.get("spec_bundle_hash")
    else:
        component_id = getattr(bundle, "component_id", None)
        spec_bundle_hash = getattr(bundle, "spec_bundle_hash", None)
    result = {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print(1)"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
    _log("generate_return", result)
    return result
'''


GENERATOR_MODEL_ERROR_SRC = _LOG_HELPER + r'''
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        component_id = bundle.get("component_id")
        spec_bundle_hash = bundle.get("spec_bundle_hash")
    else:
        component_id = getattr(bundle, "component_id", None)
        spec_bundle_hash = getattr(bundle, "spec_bundle_hash", None)
    result = {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
    _log("generate_return", result)
    return result
'''


VERIFIER_ORCHESTRATOR_SRC_TEMPLATE = _LOG_HELPER + r'''
GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    result = {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 0.0,
        "overall": "OVERALL_PLACEHOLDER",
    }
    _log("verify_return", result)
    return result
'''


LICENSE_SCANNER_SRC = _LOG_HELPER + r'''
def gate_version(repo_root):
    return "license_scanner@4.0.0-test"


def scan(component_id, repo_root):
    _log("license_scan", {"component_id": component_id})
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.0-test",
        "evaluated": True,
        "reason": None,
        "similarity_score": 0.0,
        "block_threshold": 0.7,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''


SECRET_SCANNER_SRC = _LOG_HELPER + r'''
def gate_version(repo_root):
    return "secret_scanner@test"


def scan(repo_root):
    _log("secret_scan", {"repo_root": str(repo_root)})
    return {
        "scope": "full",
        "gate_version": "secret_scanner@test",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def scan_files(paths, repo_root=None):
    raise NotImplementedError


def propose(repo_root):
    raise NotImplementedError
'''


PROVENANCE_WRITER_SRC = _LOG_HELPER + r'''
def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", {"component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    raise NotImplementedError
'''


PROVENANCE_TRACKER_NORMAL_SRC = _LOG_HELPER + r'''
import os as _os


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    gen = {}
    for k in ("component_id", "spec_bundle_hash", "model", "prompt_version",
              "cache_hit", "files", "model_call_error", "refused", "retry_feedback"):
        gen[k] = _get(generation_result, k)
    ver = None
    if verification_report is not None:
        ver = {}
        for k in ("component_id", "criteria", "requirement_results",
                  "interface_drift", "mutation_score", "overall"):
            ver[k] = _get(verification_report, k)
    _log("write_attempt_record_call", {
        "component_id": component_id,
        "generation_result": gen,
        "verification_report": ver,
        "spec_bundle_hash": spec_bundle_hash,
    })
    attempts_dir = _os.path.join(str(repo_root), ".hotdocs", "attempts", "foo")
    _os.makedirs(attempts_dir, exist_ok=True)
    with open(_os.path.join(attempts_dir, "attempt-0001.json"), "w") as f:
        f.write("{}")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": gen,
        "verification": ver,
    }


def check_readiness(*args, **kwargs):
    raise NotImplementedError


def last_requirement_failures(component_id, repo_root):
    return []
'''


PROVENANCE_TRACKER_RAISING_SRC = _LOG_HELPER + r'''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record_call", {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
    })
    raise RuntimeError("boom")


def check_readiness(*args, **kwargs):
    raise NotImplementedError


def last_requirement_failures(component_id, repo_root):
    return []
'''


class RunComponentGatesWriteAttemptRecordTest(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(tempfile.mkdtemp(prefix="ac-gate-008-repo-"))
        log_fd, log_path = tempfile.mkstemp(prefix="ac-gate-008-log-")
        os.close(log_fd)
        self.log_path = log_path
        self._old_log_env = os.environ.get("AC_GATE_008_LOG")
        os.environ["AC_GATE_008_LOG"] = self.log_path
        (self.repo_root / ".hotdocs" / "attempts" / "foo").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self._old_log_env is None:
            os.environ.pop("AC_GATE_008_LOG", None)
        else:
            os.environ["AC_GATE_008_LOG"] = self._old_log_env
        shutil.rmtree(self.repo_root, ignore_errors=True)
        try:
            os.remove(self.log_path)
        except OSError:
            pass

    def _write_module(self, slug, module_name, source):
        mod_dir = self.repo_root / "gen" / slug
        mod_dir.mkdir(parents=True, exist_ok=True)
        (mod_dir / (module_name + ".py")).write_text(source)

    def _read_events(self):
        events = []
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(json.loads(line))
        return events

    def _write_common_fakes(self):
        self._write_module("provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
        self._write_module("spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
        self._write_module("license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
        self._write_module("secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)
        self._write_module("provenance-writer", "provenance_writer", PROVENANCE_WRITER_SRC)

    def test_write_attempt_record_called_once_after_scans_with_correct_args(self):
        self._write_common_fakes()
        self._write_module("generator", "generator", GENERATOR_SUCCESS_SRC)
        self._write_module(
            "verifier-orchestrator", "verifier_orchestrator",
            VERIFIER_ORCHESTRATOR_SRC_TEMPLATE.replace("OVERALL_PLACEHOLDER", "fail"),
        )
        self._write_module("provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_NORMAL_SRC)

        component_gate_runner.run_component_gates(
            "comp-foo", self.repo_root, model="fake-model",
        )

        events = self._read_events()
        write_events = [e for e in events if e["event"] == "write_attempt_record_call"]
        self.assertEqual(len(write_events), 1)
        wa = write_events[0]["data"]
        self.assertEqual(wa["component_id"], "comp-foo")
        self.assertEqual(wa["spec_bundle_hash"], "sha256:k")

        generate_returns = [e["data"] for e in events if e["event"] == "generate_return"]
        self.assertEqual(len(generate_returns), 1)
        self.assertEqual(wa["generation_result"], generate_returns[0])

        verify_returns = [e["data"] for e in events if e["event"] == "verify_return"]
        self.assertEqual(len(verify_returns), 1)
        self.assertEqual(wa["verification_report"], verify_returns[0])

        license_indices = [i for i, e in enumerate(events) if e["event"] == "license_scan"]
        secret_indices = [i for i, e in enumerate(events) if e["event"] == "secret_scan"]
        write_index = [i for i, e in enumerate(events) if e["event"] == "write_attempt_record_call"][0]
        self.assertTrue(license_indices)
        self.assertTrue(secret_indices)
        self.assertLess(max(license_indices), write_index)
        self.assertLess(max(secret_indices), write_index)

    def test_model_call_error_write_attempt_record_gets_none_verification(self):
        self._write_common_fakes()
        self._write_module("generator", "generator", GENERATOR_MODEL_ERROR_SRC)
        self._write_module("provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_NORMAL_SRC)

        component_gate_runner.run_component_gates(
            "comp-foo", self.repo_root, model="fake-model",
        )

        events = self._read_events()
        write_events = [e for e in events if e["event"] == "write_attempt_record_call"]
        self.assertEqual(len(write_events), 1)
        wa = write_events[0]["data"]
        self.assertIsNone(wa["verification_report"])

    def test_write_attempt_record_exception_does_not_block_result(self):
        self._write_common_fakes()
        self._write_module("generator", "generator", GENERATOR_SUCCESS_SRC)
        self._write_module(
            "verifier-orchestrator", "verifier_orchestrator",
            VERIFIER_ORCHESTRATOR_SRC_TEMPLATE.replace("OVERALL_PLACEHOLDER", "pass"),
        )
        self._write_module("provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_RAISING_SRC)

        result = component_gate_runner.run_component_gates(
            "comp-foo", self.repo_root, model="fake-model",
        )

        events = self._read_events()
        write_events = [e for e in events if e["event"] == "write_attempt_record_call"]
        self.assertEqual(len(write_events), 1)
        self.assertFalse(_get(result, "blocked"))


if __name__ == "__main__":
    unittest.main()
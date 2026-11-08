import json
import shutil
import tempfile
import unittest
from pathlib import Path

import component_gate_runner


BUNDLE_SENTINEL_MARKER = "bundle-sentinel-ac-gate-002a"


class SentinelBackend:
    marker = "backend-sentinel-ac-gate-002a"


PROVENANCE_CHECKER_SRC = '''\
def current_sealed_key(component_id, repo_root):
    return None


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "1" * 64,
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


SPEC_BUNDLE_ASSEMBLER_SRC = '''\
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "2" * 64,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "glossary text",
        "hint_code": None,
    }
'''


GENERATOR_SRC = '''\
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "2" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# generated\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


VERIFIER_ORCHESTRATOR_SRC = '''\
GATE_VERSION = "verifier-orchestrator@2.0.0"


class _SentinelBundle:
    sentinel_marker = "__BUNDLE_MARKER__"


def verify(component_id, repo_root, judge=None, test_author=None):
    bundle = _SentinelBundle()
    test_author(bundle)

    criterion_bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-003",
        "covers": "R-FOO-003",
        "criterion_text": "Given ... When ... Then ...",
        "requirement_text": "requirement text",
        "interface": "interface text",
        "glossary": "glossary text",
    }
    judge(criterion_bundle)

    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
'''


TEST_AUTHOR_SRC = '''\
import json

LOG_PATH = __LOG_PATH__


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    bundle_marker = getattr(bundle, "sentinel_marker", None)
    backend_marker = getattr(llm_backend, "marker", None)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({
            "bundle_marker": bundle_marker,
            "model": model,
            "seed": seed,
            "backend_marker": backend_marker,
        }) + "\\n")
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-003",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_003.py",
            "content": "# test",
        },
        "model_call_error": None,
    }
'''


LLM_ENDPOINT_SRC = '''\
import json

LOG_PATH = __LOG_PATH__


def complete(prompt, model, *, backend=None, **params):
    backend_marker = getattr(backend, "marker", None)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({
            "model": model,
            "backend_marker": backend_marker,
        }) + "\\n")
    return {
        "text": "ok",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
'''


LICENSE_SCANNER_SRC = '''\
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


SECRET_SCANNER_SRC = '''\
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


PROVENANCE_TRACKER_SRC = '''\
import os


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(attempts_dir, exist_ok=True)
    with open(os.path.join(attempts_dir, "attempt-0001.json"), "w") as f:
        f.write("{}")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''


PROVENANCE_WRITER_SRC = '''\
def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
'''


def _write_module(repo_root, slug, module_name, source):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / (module_name + ".py")).write_text(source)


class ACGate002aRunComponentGatesTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.tmp_dir) / "repo"
        self.repo_root.mkdir()
        log_dir = Path(self.tmp_dir) / "logs"
        log_dir.mkdir()
        self.test_author_log = log_dir / "test_author_calls.jsonl"
        self.llm_endpoint_log = log_dir / "llm_endpoint_calls.jsonl"

        verifier_src = VERIFIER_ORCHESTRATOR_SRC.replace(
            "__BUNDLE_MARKER__", BUNDLE_SENTINEL_MARKER
        )
        test_author_src = TEST_AUTHOR_SRC.replace(
            "__LOG_PATH__", repr(str(self.test_author_log))
        )
        llm_endpoint_src = LLM_ENDPOINT_SRC.replace(
            "__LOG_PATH__", repr(str(self.llm_endpoint_log))
        )

        _write_module(self.repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
        _write_module(self.repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
        _write_module(self.repo_root, "generator", "generator", GENERATOR_SRC)
        _write_module(self.repo_root, "verifier-orchestrator", "verifier_orchestrator", verifier_src)
        _write_module(self.repo_root, "test-author", "test_author", test_author_src)
        _write_module(self.repo_root, "llm-endpoint", "llm_endpoint", llm_endpoint_src)
        _write_module(self.repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
        _write_module(self.repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)
        _write_module(self.repo_root, "provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_SRC)
        _write_module(self.repo_root, "provenance-writer", "provenance_writer", PROVENANCE_WRITER_SRC)

        self.sentinel_backend = SentinelBackend()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_closures_forward_model_seed_and_backend(self):
        component_gate_runner.run_component_gates(
            "comp-foo",
            self.repo_root,
            "m",
            seed=3,
            llm_backend=self.sentinel_backend,
        )

        self.assertTrue(self.test_author_log.exists())
        ta_lines = [
            json.loads(line)
            for line in self.test_author_log.read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(len(ta_lines), 1)
        ta_call = ta_lines[0]
        self.assertEqual(ta_call["bundle_marker"], BUNDLE_SENTINEL_MARKER)
        self.assertEqual(ta_call["model"], "m")
        self.assertEqual(ta_call["seed"], 3)
        self.assertEqual(ta_call["backend_marker"], SentinelBackend.marker)

        self.assertTrue(self.llm_endpoint_log.exists())
        le_lines = [
            json.loads(line)
            for line in self.llm_endpoint_log.read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual(len(le_lines), 1)
        le_call = le_lines[0]
        self.assertEqual(le_call["model"], "m")
        self.assertEqual(le_call["backend_marker"], SentinelBackend.marker)


if __name__ == "__main__":
    unittest.main()
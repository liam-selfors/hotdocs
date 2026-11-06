import json
import os
import tempfile
import unittest
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


SENTINEL_BUNDLE_MARKER = "sentinel-bundle-6f91ab"
SENTINEL_BACKEND = "sentinel-backend-c9d4f1"


PROVENANCE_CHECKER_SOURCE = """
def current_sealed_key(component_id, repo_root):
    return None


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


def check_sealed_provenance(component_id, repo_root):
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
"""


SPEC_BUNDLE_ASSEMBLER_SOURCE = """
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "b" * 64,
        "spec": "spec body",
        "interface": "interface body",
        "constraints": "constraints body",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "glossary body",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root=None):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "criterion text",
        "requirement_text": "requirement text",
        "interface": "interface content",
        "glossary": "glossary content",
    }
"""


GENERATOR_SOURCE = """
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = bundle.get("component_id") if isinstance(bundle, dict) else getattr(bundle, "component_id", None)
    spec_bundle_hash = bundle.get("spec_bundle_hash") if isinstance(bundle, dict) else getattr(bundle, "spec_bundle_hash", None)
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hi')\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


VERIFIER_ORCHESTRATOR_SOURCE = """
GATE_VERSION = "verifier-orchestrator@2.0.0"

_SENTINEL_BUNDLE = {"__sentinel_marker__": "%s"}


def verify(component_id, repo_root, judge=None, test_author=None):
    criterion_bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "Given a thing. When done. Then verified.",
        "requirement_text": "The component MUST do the thing.",
        "interface": "interface content",
        "glossary": "glossary content",
    }
    test_author(_SENTINEL_BUNDLE)
    judge(criterion_bundle)
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }
""" % (SENTINEL_BUNDLE_MARKER,)


LICENSE_SCANNER_SOURCE = """
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


SECRET_SCANNER_SOURCE = """
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
"""


PROVENANCE_TRACKER_SOURCE = """
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-0001.json").write_text("{}")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result if isinstance(generation_result, dict) else {},
        "verification": verification_report if isinstance(verification_report, dict) else verification_report,
    }


def last_requirement_failures(component_id, repo_root):
    return []
"""


PROVENANCE_WRITER_SOURCE = """
def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
"""


TEST_AUTHOR_SOURCE = """
import json
import os


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    log_path = os.environ["GATE_TEST_LOG"]
    record = {
        "event": "author_test",
        "bundle": bundle,
        "model": model,
        "seed": seed,
        "llm_backend": llm_backend,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\\n")
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_001.py",
            "content": "def test_x():\\n    assert True\\n",
        },
        "model_call_error": None,
    }
"""


LLM_ENDPOINT_SOURCE = """
import json
import os


def complete(prompt, model, *, backend=None, **params):
    log_path = os.environ["GATE_TEST_LOG"]
    record = {
        "event": "complete",
        "model": model,
        "backend": backend,
    }
    with open(log_path, "a") as f:
        f.write(json.dumps(record) + "\\n")
    return {
        "text": json.dumps({"result": "pass", "rationale": "ok"}),
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
"""


_FAKE_MODULES = [
    ("provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SOURCE),
    ("spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SOURCE),
    ("generator", "generator", GENERATOR_SOURCE),
    ("verifier-orchestrator", "verifier_orchestrator", VERIFIER_ORCHESTRATOR_SOURCE),
    ("license-scanner", "license_scanner", LICENSE_SCANNER_SOURCE),
    ("secret-scanner", "secret_scanner", SECRET_SCANNER_SOURCE),
    ("provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_SOURCE),
    ("provenance-writer", "provenance_writer", PROVENANCE_WRITER_SOURCE),
    ("test-author", "test_author", TEST_AUTHOR_SOURCE),
    ("llm-endpoint", "llm_endpoint", LLM_ENDPOINT_SOURCE),
]


class RunComponentGatesSentinelWiringTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.log_path = self.repo_root / "call_log.jsonl"
        os.environ["GATE_TEST_LOG"] = str(self.log_path)

        for dep_slug, module_name, source in _FAKE_MODULES:
            mod_dir = self.repo_root / "gen" / dep_slug
            mod_dir.mkdir(parents=True, exist_ok=True)
            (mod_dir / (module_name + ".py")).write_text(source)

    def tearDown(self):
        os.environ.pop("GATE_TEST_LOG", None)
        self._tmpdir.cleanup()

    def _read_log(self):
        records = []
        if self.log_path.exists():
            for line in self.log_path.read_text().splitlines():
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def test_wires_sentinel_bundle_model_seed_and_backend_through(self):
        import component_gate_runner

        result = component_gate_runner.run_component_gates(
            "comp-foo", self.repo_root, "m", seed=3, llm_backend=SENTINEL_BACKEND,
        )

        self.assertEqual(_get(result, "component_id"), "comp-foo")

        records = self._read_log()
        author_records = [r for r in records if r.get("event") == "author_test"]
        complete_records = [r for r in records if r.get("event") == "complete"]

        self.assertEqual(len(author_records), 1)
        author_record = author_records[0]
        self.assertEqual(author_record["bundle"], {"__sentinel_marker__": SENTINEL_BUNDLE_MARKER})
        self.assertEqual(author_record["model"], "m")
        self.assertEqual(author_record["seed"], 3)
        self.assertEqual(author_record["llm_backend"], SENTINEL_BACKEND)

        self.assertEqual(len(complete_records), 1)
        complete_record = complete_records[0]
        self.assertEqual(complete_record["model"], "m")
        self.assertEqual(complete_record["backend"], SENTINEL_BACKEND)


if __name__ == "__main__":
    unittest.main()
import json
import tempfile
import unittest
from pathlib import Path


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_COMMON_HEADER = r'''
import json

LOG_PATH = __LOG_PATH__


def _log(dep, payload):
    record = {"dep": dep}
    record.update(payload)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def _get_field(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

'''

_PROVENANCE_CHECKER_BODY = r'''

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    _log("provenance_checker.current_sealed_key", {"component_id": component_id})
    return None


def current_provenance_key(component_id, repo_root):
    _log("provenance_checker.current_provenance_key", {"component_id": component_id})
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "11" * 32,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log(
        "provenance_checker.check_provenance",
        {"component_id": component_id, "spec_bundle_hash": spec_bundle_hash},
    )
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("provenance_checker.check_sealed_provenance", {"component_id": component_id})
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

_SPEC_BUNDLE_ASSEMBLER_BODY = r'''

def assemble(component_id, repo_root=None, mode="cold"):
    bundle_hash = "sha256:" + "ab" * 32
    bundle = {
        "component_id": component_id,
        "spec_bundle_hash": bundle_hash,
        "spec": "fixture spec text",
        "interface": "fixture interface text",
        "constraints": "fixture constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fixture glossary text",
        "hint_code": None,
    }
    _log(
        "spec_bundle_assembler.assemble",
        {
            "component_id": component_id,
            "mode": mode,
            "spec_bundle_hash": bundle_hash,
        },
    )
    return bundle


def assemble_criterion(component_id, criterion_id, repo_root=None):
    _log(
        "spec_bundle_assembler.assemble_criterion",
        {"component_id": component_id, "criterion_id": criterion_id},
    )
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "fixture criterion text",
        "requirement_text": "fixture requirement text",
        "interface": "fixture interface text",
        "glossary": "fixture glossary text",
    }
'''

_GENERATOR_BODY = r'''

def generate(bundle, model, retry_feedback=None, repo_root=None, llm_backend=None):
    component_id = _get_field(bundle, "component_id")
    bundle_hash = _get_field(bundle, "spec_bundle_hash")
    _log(
        "generator.generate",
        {
            "component_id": component_id,
            "model": model,
            "retry_feedback": retry_feedback,
            "bundle_spec_bundle_hash": bundle_hash,
        },
    )
    return {
        "component_id": component_id,
        "spec_bundle_hash": bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hello from fixture')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

_VERIFIER_ORCHESTRATOR_BODY = r'''

GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verifier_orchestrator.verify", {"component_id": component_id})
    return {
        "component_id": component_id,
        "criteria": [],
        "requirement_results": {},
        "interface_drift": False,
        "mutation_score": 0.9,
        "overall": "pass",
    }
'''

_LICENSE_SCANNER_BODY = r'''

def scan(component_id, repo_root):
    _log("license_scanner.scan", {"component_id": component_id})
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
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


def gate_version(repo_root):
    return "license_scanner@4.0.3+9f2c41ab07de"
'''

_SECRET_SCANNER_BODY = r'''

def scan(repo_root):
    _log("secret_scanner.scan", {})
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

_PROVENANCE_TRACKER_BODY = r'''

def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("provenance_tracker.write_attempt_record", {"component_id": component_id})
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''

_PROVENANCE_WRITER_BODY = r'''

def write_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_provenance", {"component_id": component_id})
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("provenance_writer.write_sealed_provenance", {"component_id": component_id})
    return None
'''

_TEST_AUTHOR_BODY = r'''

def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    _log("test_author.author_test", {"model": model})
    return {
        "component_id": _get_field(bundle, "component_id"),
        "criterion_id": _get_field(bundle, "criterion_id"),
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_001.py",
            "content": "def test_x():\n    assert True\n",
        },
        "model_call_error": None,
    }
'''

_LLM_ENDPOINT_BODY = r'''

def complete(prompt, model, backend=None, **params):
    _log("llm_endpoint.complete", {"model": model})
    return {"text": "ok", "model": model, "backend": "mock", "model_call_error": None}
'''


class AcGate002bTest(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self._tmpdir.name)
        self.log_path = self.repo_root / "invocation_log.jsonl"
        self._write_fixture_component()
        self._write_all_fakes()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_fixture_component(self):
        comp_dir = self.repo_root / "specs" / "components" / "foo"
        comp_dir.mkdir(parents=True)
        (comp_dir / "component.md").write_text(
            "---\n"
            "id: comp-foo\n"
            "title: Foo\n"
            "status: draft\n"
            "owners: [team-foo]\n"
            "---\n"
            "# Foo\n\n"
            "## Purpose\n\n"
            "Fixture component for AC-GATE-002b.\n"
        )

    def _header(self):
        return _COMMON_HEADER.replace("__LOG_PATH__", repr(str(self.log_path)))

    def _write_module(self, slug, module_name, body):
        module_dir = self.repo_root / "gen" / slug
        module_dir.mkdir(parents=True, exist_ok=True)
        source = self._header() + body
        (module_dir / (module_name + ".py")).write_text(source)

    def _write_all_fakes(self):
        self._write_module("provenance-checker", "provenance_checker", _PROVENANCE_CHECKER_BODY)
        self._write_module("spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER_BODY)
        self._write_module("generator", "generator", _GENERATOR_BODY)
        self._write_module("verifier-orchestrator", "verifier_orchestrator", _VERIFIER_ORCHESTRATOR_BODY)
        self._write_module("license-scanner", "license_scanner", _LICENSE_SCANNER_BODY)
        self._write_module("secret-scanner", "secret_scanner", _SECRET_SCANNER_BODY)
        self._write_module("provenance-tracker", "provenance_tracker", _PROVENANCE_TRACKER_BODY)
        self._write_module("provenance-writer", "provenance_writer", _PROVENANCE_WRITER_BODY)
        self._write_module("test-author", "test_author", _TEST_AUTHOR_BODY)
        self._write_module("llm-endpoint", "llm_endpoint", _LLM_ENDPOINT_BODY)

    def _read_log(self):
        entries = []
        if not self.log_path.exists():
            return entries
        with open(self.log_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries

    def test_assemble_generate_verify_order_and_payloads(self):
        import component_gate_runner

        result = component_gate_runner.run_component_gates(
            "comp-foo",
            self.repo_root,
            "m",
            retry_feedback=["R-FOO-002"],
        )
        self.assertIsNotNone(result)

        entries = self._read_log()

        ordered_main_deps = [
            e["dep"]
            for e in entries
            if e["dep"]
            in (
                "spec_bundle_assembler.assemble",
                "generator.generate",
                "verifier_orchestrator.verify",
            )
        ]
        self.assertEqual(
            ordered_main_deps,
            [
                "spec_bundle_assembler.assemble",
                "generator.generate",
                "verifier_orchestrator.verify",
            ],
        )

        assemble_entry = next(e for e in entries if e["dep"] == "spec_bundle_assembler.assemble")
        generate_entry = next(e for e in entries if e["dep"] == "generator.generate")

        self.assertEqual(assemble_entry["mode"], "cold")

        self.assertEqual(generate_entry["model"], "m")
        self.assertEqual(generate_entry["retry_feedback"], ["R-FOO-002"])
        self.assertEqual(
            generate_entry["bundle_spec_bundle_hash"],
            assemble_entry["spec_bundle_hash"],
        )
        self.assertEqual(generate_entry["component_id"], "comp-foo")


if __name__ == "__main__":
    unittest.main()
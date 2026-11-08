import tempfile
import unittest
from pathlib import Path

import component_gate_runner


def _dual_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_component_fixture(repo_root, component_id="comp-foo", slug="foo"):
    comp_dir = repo_root / "specs" / "components" / slug
    _write(comp_dir / "component.md", f"""---
id: {component_id}
title: Foo Component
status: draft
owners: [alice]
sealed: true
source_path: fixtures/{slug}/
---

# {component_id}

## Purpose

Fixture component for AC-GATE-004.
""")
    _write(comp_dir / "requirements" / "R-FOO-001.md", """# R-FOO-001

Foo must do a thing.
""")
    _write(comp_dir / "acceptance" / "AC-FOO-001.md", """# AC-FOO-001

Covers: R-FOO-001
Kind: compiled

```gherkin
Given foo
When bar
Then baz
```
""")


def _write_provenance_checker_fake(repo_root, slug):
    module_path = repo_root / "gen" / "provenance-checker" / "provenance_checker.py"
    _write(module_path, """
def current_sealed_key(component_id, repo_root):
    return None


class _ProvenanceKey:
    spec_bundle_hash = "sha256:" + "a" * 64
    gate_versions = {
        "compiler": "criterion_compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier_orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.0",
        "secret_scanner": "secret_scanner@0.0.0",
    }


def current_provenance_key(component_id, repo_root):
    return _ProvenanceKey()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
""")


def _write_spec_bundle_assembler_fake(repo_root):
    module_path = repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py"
    _write(module_path, """
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "fixture spec",
        "interface": "fixture interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
""")


def _write_generator_fake(repo_root, log_path, files, model_call_error):
    module_path = repo_root / "gen" / "generator" / "generator.py"
    files_repr = repr(files)
    model_call_error_repr = repr(model_call_error)
    log_path_repr = repr(str(log_path))
    _write(module_path, f"""
LOG_PATH = {log_path_repr}


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    with open(LOG_PATH, "a") as f:
        f.write("generator.generate\\n")
    return {{
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {files_repr},
        "model_call_error": {model_call_error_repr},
        "refused": None,
        "retry_feedback": retry_feedback,
    }}
""")


def _write_verifier_orchestrator_fake(repo_root, log_path, overall):
    module_path = repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py"
    overall_repr = repr(overall)
    log_path_repr = repr(str(log_path))
    _write(module_path, f"""
LOG_PATH = {log_path_repr}

GATE_VERSION = "verifier-orchestrator@2.0.0"


class _VerificationReport:
    def __init__(self):
        self.component_id = "comp-foo"
        self.criteria = [
            {{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": {overall_repr!r} if False else ({overall_repr} if False else "fail")}},
        ]
        self.requirement_results = {{"R-FOO-001": "fail"}}
        self.interface_drift = False
        self.mutation_score = 0.5
        self.overall = {overall_repr}

    def to_dict(self):
        return {{
            "component_id": self.component_id,
            "criteria": self.criteria,
            "requirement_results": self.requirement_results,
            "interface_drift": self.interface_drift,
            "mutation_score": self.mutation_score,
            "overall": self.overall,
        }}


def verify(component_id, repo_root, judge=None, test_author=None):
    with open(LOG_PATH, "a") as f:
        f.write("verifier_orchestrator.verify\\n")
    return _VerificationReport()
""")


def _write_license_scanner_fake(repo_root):
    module_path = repo_root / "gen" / "license-scanner" / "license_scanner.py"
    _write(module_path, """
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
""")


def _write_secret_scanner_fake(repo_root):
    module_path = repo_root / "gen" / "secret-scanner" / "secret_scanner.py"
    _write(module_path, """
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
""")


def _write_provenance_tracker_fake(repo_root, log_path):
    module_path = repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py"
    log_path_repr = repr(str(log_path))
    _write(module_path, f"""
LOG_PATH = {log_path_repr}


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    with open(LOG_PATH, "a") as f:
        f.write("provenance_tracker.write_attempt_record\\n")
    return {{
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }}
""")


def _write_provenance_writer_fake(repo_root, log_path):
    module_path = repo_root / "gen" / "provenance-writer" / "provenance_writer.py"
    log_path_repr = repr(str(log_path))
    _write(module_path, f"""
LOG_PATH = {log_path_repr}


def write_provenance(component_id, inputs, repo_root):
    with open(LOG_PATH, "a") as f:
        f.write("provenance_writer.write_provenance\\n")
    return None
""")


class ACGate004Test(unittest.TestCase):
    def test_model_call_error_skips_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            log_path = tmp_path / "invocations.log"
            log_path.write_text("")

            _build_component_fixture(repo_root, component_id="comp-foo", slug="foo")
            _write_provenance_checker_fake(repo_root, "foo")
            _write_spec_bundle_assembler_fake(repo_root)
            _write_generator_fake(
                repo_root,
                log_path,
                files={},
                model_call_error={"category": "network", "message": "connection refused"},
            )
            _write_verifier_orchestrator_fake(repo_root, log_path, overall="pass")
            _write_license_scanner_fake(repo_root)
            _write_secret_scanner_fake(repo_root)
            _write_provenance_tracker_fake(repo_root, log_path)
            _write_provenance_writer_fake(repo_root, log_path)

            result = component_gate_runner.run_component_gates(
                "comp-foo",
                repo_root,
                model="fake-model-1",
                seed=0,
                llm_backend=None,
                retry_feedback=None,
            )

            self.assertEqual(_dual_get(result, "block_reason"), "model_call_error")
            self.assertTrue(_dual_get(result, "blocked"))

            log_contents = log_path.read_text()
            self.assertNotIn("verifier_orchestrator.verify", log_contents)
            self.assertIn("generator.generate", log_contents)

    def test_verification_failure_sets_block_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            log_path = tmp_path / "invocations.log"
            log_path.write_text("")

            _build_component_fixture(repo_root, component_id="comp-foo", slug="foo")
            _write_provenance_checker_fake(repo_root, "foo")
            _write_spec_bundle_assembler_fake(repo_root)
            _write_generator_fake(
                repo_root,
                log_path,
                files={"foo.py": "print('hello')"},
                model_call_error=None,
            )
            _write_verifier_orchestrator_fake(repo_root, log_path, overall="fail")
            _write_license_scanner_fake(repo_root)
            _write_secret_scanner_fake(repo_root)
            _write_provenance_tracker_fake(repo_root, log_path)
            _write_provenance_writer_fake(repo_root, log_path)

            result = component_gate_runner.run_component_gates(
                "comp-foo",
                repo_root,
                model="fake-model-2",
                seed=0,
                llm_backend=None,
                retry_feedback=None,
            )

            self.assertEqual(_dual_get(result, "block_reason"), "verification_failed")
            self.assertIsNone(_dual_get(result, "model_call_error"))
            self.assertTrue(_dual_get(result, "blocked"))

            log_contents = log_path.read_text()
            self.assertIn("verifier_orchestrator.verify", log_contents)


if __name__ == "__main__":
    unittest.main()
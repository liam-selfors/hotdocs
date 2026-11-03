import pathlib
import shutil
import tempfile
import textwrap
import unittest


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _install_fake(repo_root, slug, module_name, source):
    module_dir = repo_root / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / (module_name + ".py")).write_text(source)


LOGGER_SNIPPET = textwrap.dedent('''
    import pathlib as _pathlib


    def _log(repo_root, name, **fields):
        path = _pathlib.Path(repo_root) / "_calls.log"
        with open(path, "a") as f:
            f.write(name + " " + repr(fields) + "\\n")
''')


class RunComponentGatesVerificationFailedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hotdocs-gate-")
        self.repo_root = pathlib.Path(self.tmp)
        self.component_id = "comp-foo"
        self.slug = "foo"
        self._write_fixture_component()
        self._install_fakes()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_fixture_component(self):
        component_md = textwrap.dedent('''\
            ---
            id: comp-foo
            title: Foo
            status: draft
            owners: [test-team]
            sealed: false
            ---

            # Foo

            ## Purpose

            A fixture component for AC-GATE-003b.
            ''')
        _write(self.repo_root / "specs" / "components" / self.slug / "component.md", component_md)

    def _install_fakes(self):
        provenance_checker_src = LOGGER_SNIPPET + textwrap.dedent('''
            def current_sealed_key(component_id, repo_root):
                _log(repo_root, "current_sealed_key")
                return None


            class _Key:
                spec_bundle_hash = "sha256:" + "0" * 64
                gate_versions = {
                    "compiler": "criterion-compiler@1.0.0",
                    "generated_test": "generated_test@1.0.0",
                    "verifier": "verifier-orchestrator@2.0.0",
                    "license_scanner": "license_scanner@3.1.0",
                    "secret_scanner": "secret_scanner@0.0.0",
                }


            def current_provenance_key(component_id, repo_root):
                _log(repo_root, "current_provenance_key")
                return _Key()


            def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
                _log(repo_root, "check_provenance")
                return {
                    "hit": False,
                    "verification_report": None,
                    "license_scan": None,
                    "secret_scan": None,
                }
        ''')
        _install_fake(self.repo_root, "provenance-checker", "provenance_checker", provenance_checker_src)

        assembler_src = LOGGER_SNIPPET + textwrap.dedent('''
            def assemble(component_id, repo_root, mode="cold"):
                _log(repo_root, "assemble")
                return {
                    "component_id": component_id,
                    "spec_bundle_hash": "sha256:" + "0" * 64,
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
        ''')
        _install_fake(self.repo_root, "spec-bundle-assembler", "spec_bundle_assembler", assembler_src)

        generator_src = LOGGER_SNIPPET + textwrap.dedent('''
            def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
                _log(repo_root, "generate", retry_feedback=retry_feedback)
                if isinstance(bundle, dict):
                    component_id = bundle["component_id"]
                else:
                    component_id = bundle.component_id
                return {
                    "component_id": component_id,
                    "spec_bundle_hash": "sha256:" + "0" * 64,
                    "model": model,
                    "prompt_version": "v1",
                    "cache_hit": False,
                    "files": {"foo.py": "# generated\\n"},
                    "model_call_error": None,
                    "refused": None,
                    "retry_feedback": retry_feedback,
                }
        ''')
        _install_fake(self.repo_root, "generator", "generator", generator_src)

        verifier_src = LOGGER_SNIPPET + textwrap.dedent('''
            GATE_VERSION = "verifier-orchestrator@2.0.0"


            def verify(component_id, repo_root, judge=None, test_author=None):
                _log(repo_root, "verify")
                return {
                    "component_id": component_id,
                    "criteria": [
                        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
                        {
                            "id": "AC-FOO-002",
                            "covers": "R-FOO-002",
                            "kind": "compiled",
                            "result": "fail",
                            "failure_detail": {
                                "message": "requirement not satisfied",
                                "expected": True,
                                "actual": False,
                            },
                        },
                    ],
                    "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
                    "interface_drift": False,
                    "mutation_score": 0.5,
                    "overall": "fail",
                }
        ''')
        _install_fake(self.repo_root, "verifier-orchestrator", "verifier_orchestrator", verifier_src)

        license_src = LOGGER_SNIPPET + textwrap.dedent('''
            def gate_version(repo_root):
                return "license_scanner@4.0.0"


            def scan(component_id, repo_root):
                _log(repo_root, "license_scan")
                return {
                    "component_id": component_id,
                    "gate_version": "license_scanner@4.0.0",
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
        ''')
        _install_fake(self.repo_root, "license-scanner", "license_scanner", license_src)

        secret_src = LOGGER_SNIPPET + textwrap.dedent('''
            def gate_version(repo_root):
                return "secret_scanner@3.0.0"


            def scan(repo_root):
                _log(repo_root, "secret_scan")
                return {
                    "scope": "full",
                    "gate_version": "secret_scanner@3.0.0",
                    "flagged": False,
                    "matches": [],
                    "allowed": [],
                    "unused_allowlist_entries": [],
                    "notified": False,
                    "notification_delivery_error": None,
                    "cache_hit": False,
                }
        ''')
        _install_fake(self.repo_root, "secret-scanner", "secret_scanner", secret_src)

        tracker_src = LOGGER_SNIPPET + textwrap.dedent('''
            import json as _json


            def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
                _log(repo_root, "write_attempt_record")
                if component_id.startswith("comp-"):
                    slug = component_id[len("comp-"):]
                else:
                    slug = component_id
                attempts_dir = _pathlib.Path(repo_root) / ".hotdocs" / "attempts" / slug
                attempts_dir.mkdir(parents=True, exist_ok=True)
                record = {
                    "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
                    "component_id": component_id,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "spec_bundle_hash": spec_bundle_hash,
                    "generation": generation_result,
                    "verification": verification_report,
                }
                (attempts_dir / "attempt-0001.json").write_text(_json.dumps(record))
                return record
        ''')
        _install_fake(self.repo_root, "provenance-tracker", "provenance_tracker", tracker_src)

        writer_src = LOGGER_SNIPPET + textwrap.dedent('''
            def write_provenance(component_id, inputs, repo_root):
                _log(repo_root, "write_provenance")


            def write_sealed_provenance(component_id, inputs, repo_root):
                _log(repo_root, "write_sealed_provenance")
        ''')
        _install_fake(self.repo_root, "provenance-writer", "provenance_writer", writer_src)

    def _calls(self):
        log_path = self.repo_root / "_calls.log"
        if not log_path.exists():
            return []
        return log_path.read_text().splitlines()

    def test_verification_failure_blocks_after_single_generator_call(self):
        import component_gate_runner

        result = component_gate_runner.run_component_gates(
            self.component_id,
            self.repo_root,
            model="claude-sonnet-5",
        )

        calls = self._calls()
        generate_calls = [line for line in calls if line.startswith("generate ")]
        self.assertEqual(len(generate_calls), 1)
        self.assertIn("'retry_feedback': None", generate_calls[0])

        self.assertTrue(_get(result, "blocked"))
        self.assertEqual(_get(result, "block_reason"), "verification_failed")


if __name__ == "__main__":
    unittest.main()
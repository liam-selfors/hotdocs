import os
import shutil
import tempfile
import textwrap
from pathlib import Path

import component_gate_runner


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _write_module(repo_root, dependency_slug, module_name, content):
    module_dir = os.path.join(str(repo_root), "gen", dependency_slug)
    os.makedirs(module_dir, exist_ok=True)
    with open(os.path.join(module_dir, module_name + ".py"), "w") as f:
        f.write(content)


def test_ac_gate_003a_generator_called_once_on_miss_with_passing_verification():
    repo_root_dir = tempfile.mkdtemp(prefix="ac-gate-003a-repo-")
    log_dir = tempfile.mkdtemp(prefix="ac-gate-003a-log-")
    log_path = os.path.join(log_dir, "generator_calls.log")

    try:
        repo_root = Path(repo_root_dir)

        provenance_checker_src = textwrap.dedent(
            """
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
        )
        _write_module(repo_root, "provenance-checker", "provenance_checker", provenance_checker_src)

        spec_bundle_assembler_src = textwrap.dedent(
            """
            def assemble(component_id, repo_root=None, mode="cold"):
                return {
                    "component_id": component_id,
                    "spec_bundle_hash": "sha256:" + "0" * 64,
                    "spec": "fake spec",
                    "interface": "fake interface",
                    "constraints": "",
                    "dependency_interfaces": {},
                    "dependency_context": {},
                    "dependency_usage": {},
                    "vars": {},
                    "glossary": "",
                    "hint_code": None,
                }
            """
        )
        _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", spec_bundle_assembler_src)

        generator_src = textwrap.dedent(
            """
            import os

            def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
                log_path = os.environ["AC_GATE_003A_GENERATOR_LOG"]
                with open(log_path, "a") as f:
                    f.write("called\\n")

                if isinstance(bundle, dict):
                    component_id = bundle.get("component_id")
                    spec_bundle_hash = bundle.get("spec_bundle_hash")
                else:
                    component_id = getattr(bundle, "component_id", None)
                    spec_bundle_hash = getattr(bundle, "spec_bundle_hash", None)

                return {
                    "component_id": component_id,
                    "spec_bundle_hash": spec_bundle_hash,
                    "model": model,
                    "prompt_version": "v1",
                    "cache_hit": False,
                    "files": {"foo.py": "# generated content"},
                    "model_call_error": None,
                    "refused": None,
                    "retry_feedback": retry_feedback,
                }
            """
        )
        _write_module(repo_root, "generator", "generator", generator_src)

        verifier_orchestrator_src = textwrap.dedent(
            """
            GATE_VERSION = "verifier-orchestrator@2.0.0"

            def verify(component_id, repo_root, judge=None, test_author=None):
                return {
                    "component_id": component_id,
                    "criteria": [
                        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
                    ],
                    "requirement_results": {"R-FOO-001": "pass"},
                    "interface_drift": False,
                    "mutation_score": 1.0,
                    "overall": "pass",
                }
            """
        )
        _write_module(repo_root, "verifier-orchestrator", "verifier_orchestrator", verifier_orchestrator_src)

        license_scanner_src = textwrap.dedent(
            """
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
        )
        _write_module(repo_root, "license-scanner", "license_scanner", license_scanner_src)

        secret_scanner_src = textwrap.dedent(
            """
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
        )
        _write_module(repo_root, "secret-scanner", "secret_scanner", secret_scanner_src)

        provenance_tracker_src = textwrap.dedent(
            """
            import json
            import os

            def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
                slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
                attempts_dir = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
                os.makedirs(attempts_dir, exist_ok=True)
                attempt_id = "20260101T000000Z-aaaaaa"
                record = {
                    "attempt_id": attempt_id,
                    "component_id": component_id,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "spec_bundle_hash": spec_bundle_hash,
                    "generation": generation_result,
                    "verification": verification_report,
                }
                with open(os.path.join(attempts_dir, attempt_id + ".json"), "w") as f:
                    json.dump(record, f)
                return record

            def last_requirement_failures(component_id, repo_root):
                return []
            """
        )
        _write_module(repo_root, "provenance-tracker", "provenance_tracker", provenance_tracker_src)

        provenance_writer_src = textwrap.dedent(
            """
            def write_provenance(component_id, inputs, repo_root):
                return None

            def write_sealed_provenance(component_id, inputs, repo_root):
                return None
            """
        )
        _write_module(repo_root, "provenance-writer", "provenance_writer", provenance_writer_src)

        os.environ["AC_GATE_003A_GENERATOR_LOG"] = log_path
        try:
            result = component_gate_runner.run_component_gates(
                component_id="comp-foo",
                repo_root=repo_root,
                model="fake-model-1",
                seed=0,
                llm_backend=None,
                retry_feedback=None,
            )
        finally:
            del os.environ["AC_GATE_003A_GENERATOR_LOG"]

        blocked = _get(result, "blocked")
        block_reason = _get(result, "block_reason")
        model_call_error = _get(result, "model_call_error")
        verification = _get(result, "verification")
        overall = _get(verification, "overall")

        assert blocked is False
        assert block_reason is None
        assert model_call_error is None
        assert overall == "pass"

        with open(log_path) as f:
            calls = [line for line in f.read().splitlines() if line.strip()]
        assert len(calls) == 1
    finally:
        shutil.rmtree(repo_root_dir, ignore_errors=True)
        shutil.rmtree(log_dir, ignore_errors=True)
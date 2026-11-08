import json
import textwrap

import component_gate_runner


def _dual_get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _write_fake_module(repo_root, dependency_slug, module_name, source):
    mod_dir = repo_root / "gen" / dependency_slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source)


def test_ac_gate_003b_generator_called_once_on_verification_failure(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    slug = "widget-maker"
    component_id = f"comp-{slug}"

    component_dir = repo_root / "specs" / "components" / slug
    component_dir.mkdir(parents=True)
    (component_dir / "component.md").write_text(
        "---\n"
        f"id: {component_id}\n"
        "title: Widget Maker\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n\n"
        "# Purpose\n\n"
        "A fixture component for AC-GATE-003b.\n"
    )

    generator_log = tmp_path / "generator_calls.jsonl"

    provenance_checker_source = textwrap.dedent(
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
    ).strip() + "\n"
    _write_fake_module(
        repo_root, "provenance-checker", "provenance_checker", provenance_checker_source
    )

    spec_bundle_assembler_source = textwrap.dedent(
        """
        def assemble(component_id, repo_root, mode="cold"):
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
        """
    ).strip() + "\n"
    _write_fake_module(
        repo_root, "spec-bundle-assembler", "spec_bundle_assembler", spec_bundle_assembler_source
    )

    generator_source = (
        textwrap.dedent(
            """
            import json

            LOG_PATH = __LOG_PATH__


            def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
                with open(LOG_PATH, "a") as f:
                    f.write(json.dumps({"retry_feedback": retry_feedback}) + "\\n")
                bundle_component_id = (
                    bundle.get("component_id")
                    if isinstance(bundle, dict)
                    else getattr(bundle, "component_id", None)
                )
                return {
                    "component_id": bundle_component_id,
                    "spec_bundle_hash": "sha256:" + "0" * 64,
                    "model": model,
                    "prompt_version": "v1",
                    "cache_hit": False,
                    "files": {"widget.py": "# generated content"},
                    "model_call_error": None,
                    "refused": None,
                    "retry_feedback": retry_feedback,
                }
            """
        )
        .strip()
        .replace("__LOG_PATH__", repr(str(generator_log)))
        + "\n"
    )
    _write_fake_module(repo_root, "generator", "generator", generator_source)

    verifier_orchestrator_source = textwrap.dedent(
        """
        GATE_VERSION = "verifier-orchestrator@2.0.0"


        def verify(component_id, repo_root, judge=None, test_author=None):
            return {
                "component_id": component_id,
                "criteria": [
                    {
                        "id": "AC-FOO-001",
                        "covers": "R-FOO-001",
                        "kind": "compiled",
                        "result": "pass",
                    },
                    {
                        "id": "AC-FOO-002",
                        "covers": "R-FOO-002",
                        "kind": "compiled",
                        "result": "fail",
                        "failure_detail": {
                            "message": "result.foo equals 1 failed",
                            "expected": 1,
                            "actual": 0,
                        },
                    },
                ],
                "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
                "interface_drift": False,
                "mutation_score": 0.5,
                "overall": "fail",
            }
        """
    ).strip() + "\n"
    _write_fake_module(
        repo_root, "verifier-orchestrator", "verifier_orchestrator", verifier_orchestrator_source
    )

    license_scanner_source = textwrap.dedent(
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
    ).strip() + "\n"
    _write_fake_module(repo_root, "license-scanner", "license_scanner", license_scanner_source)

    secret_scanner_source = textwrap.dedent(
        """
        def scan(repo_root):
            return {
                "scope": "full",
                "gate_version": "secret_scanner@0.0.0",
                "flagged": False,
                "matches": [],
                "allowed": [],
                "unused_allowlist_entries": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }


        def gate_version(repo_root):
            return "secret_scanner@0.0.0"
        """
    ).strip() + "\n"
    _write_fake_module(repo_root, "secret-scanner", "secret_scanner", secret_scanner_source)

    provenance_tracker_source = textwrap.dedent(
        """
        def write_attempt_record(
            component_id, generation_result, verification_report, spec_bundle_hash, repo_root
        ):
            return {
                "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
                "component_id": component_id,
                "timestamp": "2026-01-01T00:00:00Z",
                "spec_bundle_hash": spec_bundle_hash,
                "generation": generation_result,
                "verification": verification_report,
            }
        """
    ).strip() + "\n"
    _write_fake_module(repo_root, "provenance-tracker", "provenance_tracker", provenance_tracker_source)

    provenance_writer_source = textwrap.dedent(
        """
        def write_provenance(component_id, inputs, repo_root):
            return None


        def write_sealed_provenance(component_id, inputs, repo_root):
            return None
        """
    ).strip() + "\n"
    _write_fake_module(repo_root, "provenance-writer", "provenance_writer", provenance_writer_source)

    result = component_gate_runner.run_component_gates(
        component_id,
        repo_root,
        "mock-model",
    )

    assert generator_log.exists(), "generator fake was never invoked"
    calls = [json.loads(line) for line in generator_log.read_text().splitlines() if line.strip()]
    assert len(calls) == 1, f"expected generator to be called exactly once, got {len(calls)}"
    assert calls[0]["retry_feedback"] is None

    blocked = _dual_get(result, "blocked")
    block_reason = _dual_get(result, "block_reason")

    assert blocked is True
    assert block_reason == "verification_failed"
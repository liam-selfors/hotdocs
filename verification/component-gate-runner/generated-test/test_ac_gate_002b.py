import json
import os
import tempfile
import textwrap
from pathlib import Path

import component_gate_runner


def _write_fake(repo_root, slug, module_name, source):
    module_dir = os.path.join(str(repo_root), "gen", slug)
    os.makedirs(module_dir, exist_ok=True)
    path = os.path.join(module_dir, module_name + ".py")
    with open(path, "w") as f:
        f.write(source)


def _write_fixture_component(repo_root):
    comp_dir = os.path.join(str(repo_root), "specs", "components", "foo")
    os.makedirs(os.path.join(comp_dir, "requirements"), exist_ok=True)
    os.makedirs(os.path.join(comp_dir, "acceptance"), exist_ok=True)

    component_md = textwrap.dedent("""\
        ---
        id: comp-foo
        title: Foo Fixture
        status: draft
        owners: [fixture-owner]
        sealed: false
        depends_on: []
        ---

        ## Purpose

        Fixture component for AC-GATE-002b.
        """)
    with open(os.path.join(comp_dir, "component.md"), "w") as f:
        f.write(component_md)

    requirement_md = textwrap.dedent("""\
        # R-FOO-001

        Fixture requirement for AC-GATE-002b.
        """)
    with open(os.path.join(comp_dir, "requirements", "R-FOO-001.md"), "w") as f:
        f.write(requirement_md)

    acceptance_md = textwrap.dedent("""\
        # AC-FOO-001

        Covers: R-FOO-001

        Fixture criterion for AC-GATE-002b.
        """)
    with open(os.path.join(comp_dir, "acceptance", "AC-FOO-001.md"), "w") as f:
        f.write(acceptance_md)


def test_ac_gate_002b_cold_miss_assemble_generate_verify_order():
    repo_root = Path(tempfile.mkdtemp())
    log_fd, log_path = tempfile.mkstemp(suffix=".jsonl")
    os.close(log_fd)

    bundle_marker = "sha256:assembled-bundle-marker-ac-gate-002b"

    _write_fixture_component(repo_root)

    provenance_checker_src = textwrap.dedent("""\
        class ProvenanceKey:
            def __init__(self, spec_bundle_hash, gate_versions):
                self.spec_bundle_hash = spec_bundle_hash
                self.gate_versions = gate_versions


        def current_provenance_key(component_id, repo_root):
            return ProvenanceKey(
                "sha256:unrelated-current-key",
                {
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
        """)

    assembler_src = ("""\
import json

LOG_PATH = __LOG_PATH__


def assemble(component_id, repo_root=None, mode="cold"):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"call": "assemble", "component_id": component_id, "mode": mode}) + "\\n")
    return {
        "component_id": component_id,
        "spec_bundle_hash": __BUNDLE_MARKER__,
        "spec": "fake spec",
        "interface": "fake interface",
        "constraints": "fake constraints",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "fake glossary",
        "hint_code": None,
    }
""").replace("__LOG_PATH__", repr(log_path)).replace("__BUNDLE_MARKER__", repr(bundle_marker))

    generator_src = ("""\
import json

LOG_PATH = __LOG_PATH__


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        bundle_hash = bundle.get("spec_bundle_hash")
    else:
        bundle_hash = getattr(bundle, "spec_bundle_hash", None)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({
            "call": "generate",
            "bundle_hash": bundle_hash,
            "model": model,
            "retry_feedback": retry_feedback,
        }) + "\\n")
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# generated content"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
""").replace("__LOG_PATH__", repr(log_path))

    verifier_src = ("""\
import json

LOG_PATH = __LOG_PATH__


def verify(component_id, repo_root, judge=None, test_author=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"call": "verify", "component_id": component_id}) + "\\n")
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "generated-test", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-002": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
""").replace("__LOG_PATH__", repr(log_path))

    license_scanner_src = textwrap.dedent("""\
        def scan(component_id, repo_root):
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
        """)

    secret_scanner_src = textwrap.dedent("""\
        def scan(repo_root):
            return {
                "scope": "full",
                "gate_version": "secret_scanner@2.0.0",
                "flagged": False,
                "matches": [],
                "notified": False,
                "notification_delivery_error": None,
                "cache_hit": False,
            }
        """)

    provenance_tracker_src = textwrap.dedent("""\
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
        """)

    provenance_writer_src = textwrap.dedent("""\
        def write_provenance(component_id, inputs, repo_root):
            return None
        """)

    _write_fake(repo_root, "provenance-checker", "provenance_checker", provenance_checker_src)
    _write_fake(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", assembler_src)
    _write_fake(repo_root, "generator", "generator", generator_src)
    _write_fake(repo_root, "verifier-orchestrator", "verifier_orchestrator", verifier_src)
    _write_fake(repo_root, "license-scanner", "license_scanner", license_scanner_src)
    _write_fake(repo_root, "secret-scanner", "secret_scanner", secret_scanner_src)
    _write_fake(repo_root, "provenance-tracker", "provenance_tracker", provenance_tracker_src)
    _write_fake(repo_root, "provenance-writer", "provenance_writer", provenance_writer_src)

    try:
        component_gate_runner.run_component_gates(
            "comp-foo", repo_root, "m", retry_feedback=["R-FOO-002"],
        )

        with open(log_path) as f:
            entries = [json.loads(line) for line in f if line.strip()]

        calls = [e["call"] for e in entries]
        assert calls == ["assemble", "generate", "verify"], calls

        assemble_entry = entries[calls.index("assemble")]
        generate_entry = entries[calls.index("generate")]

        assert assemble_entry["mode"] == "cold"
        assert generate_entry["bundle_hash"] == bundle_marker
        assert generate_entry["model"] == "m"
        assert generate_entry["retry_feedback"] == ["R-FOO-002"]
    finally:
        os.remove(log_path)
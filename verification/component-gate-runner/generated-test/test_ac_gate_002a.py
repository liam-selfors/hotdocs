import json
import os
import pathlib
import shutil
import tempfile

import component_gate_runner


PROVENANCE_CHECKER_SRC = """
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
"""


SPEC_BUNDLE_ASSEMBLER_SRC = """
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
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
"""


GENERATOR_SRC = """
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    component_id = bundle["component_id"] if isinstance(bundle, dict) else bundle.component_id
    spec_bundle_hash = bundle["spec_bundle_hash"] if isinstance(bundle, dict) else bundle.spec_bundle_hash
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "# generated content\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


VERIFIER_ORCHESTRATOR_SRC = """
GATE_VERSION = "verifier-orchestrator@2.0.0"

_SENTINEL_BUNDLE_MARKER = "__SENTINEL_BUNDLE_MARKER__"


def verify(component_id, repo_root, judge=None, test_author=None):
    sentinel_bundle = {"sentinel_marker": _SENTINEL_BUNDLE_MARKER}
    if test_author is not None:
        test_author(sentinel_bundle)

    criterion_bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-003",
        "covers": "R-FOO-003",
        "criterion_text": "Given ... When ... Then ...",
        "requirement_text": "fake requirement text",
        "interface": "fake interface",
        "glossary": "fake glossary",
    }
    if judge is not None:
        judge(criterion_bundle)

    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-003", "covers": "R-FOO-003", "kind": "generated-test", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-003": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
"""


LICENSE_SCANNER_SRC = """
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


def gate_version(repo_root):
    return "license_scanner@3.1.0"
"""


SECRET_SCANNER_SRC = """
def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@0.0.0",
        "flagged": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@0.0.0"
"""


PROVENANCE_TRACKER_SRC = """
import os


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = os.path.join(str(repo_root), ".hotdocs", "attempts", slug)
    os.makedirs(attempts_dir, exist_ok=True)
    with open(os.path.join(attempts_dir, "attempt-0001.json"), "w") as f:
        f.write("{}")
    return {
        "attempt_id": "attempt-0001",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
"""


PROVENANCE_WRITER_SRC = """
def write_provenance(component_id, inputs, repo_root):
    return None
"""


TEST_AUTHOR_SRC = """
import json
import os


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    record_path = os.environ["TEST_AUTHOR_RECORD_PATH"]
    record = {
        "bundle_marker": bundle.get("sentinel_marker") if isinstance(bundle, dict) else None,
        "model": model,
        "seed": seed,
        "backend_marker": getattr(llm_backend, "marker", None),
    }
    with open(record_path, "w") as f:
        json.dump(record, f)
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-003",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_003.py",
            "content": "# test code\\n",
        },
        "model_call_error": None,
    }
"""


LLM_ENDPOINT_SRC = """
import json
import os


def complete(prompt, model, *, backend=None, **params):
    record_path = os.environ["LLM_ENDPOINT_RECORD_PATH"]
    record = {
        "model": model,
        "backend_marker": getattr(backend, "marker", None),
    }
    with open(record_path, "w") as f:
        json.dump(record, f)
    return {
        "text": "ok",
        "model": model,
        "backend": "fake-backend",
        "model_call_error": None,
    }
"""


class _SentinelBackend:
    marker = "sentinel-backend-marker-7e862b1d"


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def test_ac_gate_002a_wires_test_author_and_judge_closures_on_miss():
    repo_root_str = tempfile.mkdtemp()
    repo_root = pathlib.Path(repo_root_str)

    sentinel_backend = _SentinelBackend()
    bundle_marker = "sentinel-bundle-marker-7e862b1d"

    test_author_record_path = os.path.join(repo_root_str, "test_author_record.json")
    llm_endpoint_record_path = os.path.join(repo_root_str, "llm_endpoint_record.json")

    old_test_author_env = os.environ.get("TEST_AUTHOR_RECORD_PATH")
    old_llm_endpoint_env = os.environ.get("LLM_ENDPOINT_RECORD_PATH")
    os.environ["TEST_AUTHOR_RECORD_PATH"] = test_author_record_path
    os.environ["LLM_ENDPOINT_RECORD_PATH"] = llm_endpoint_record_path

    try:
        _write(
            os.path.join(repo_root_str, "gen", "provenance-checker", "provenance_checker.py"),
            PROVENANCE_CHECKER_SRC,
        )
        _write(
            os.path.join(repo_root_str, "gen", "spec-bundle-assembler", "spec_bundle_assembler.py"),
            SPEC_BUNDLE_ASSEMBLER_SRC,
        )
        _write(
            os.path.join(repo_root_str, "gen", "generator", "generator.py"),
            GENERATOR_SRC,
        )
        verifier_src = VERIFIER_ORCHESTRATOR_SRC.replace("__SENTINEL_BUNDLE_MARKER__", bundle_marker)
        _write(
            os.path.join(repo_root_str, "gen", "verifier-orchestrator", "verifier_orchestrator.py"),
            verifier_src,
        )
        _write(
            os.path.join(repo_root_str, "gen", "license-scanner", "license_scanner.py"),
            LICENSE_SCANNER_SRC,
        )
        _write(
            os.path.join(repo_root_str, "gen", "secret-scanner", "secret_scanner.py"),
            SECRET_SCANNER_SRC,
        )
        _write(
            os.path.join(repo_root_str, "gen", "provenance-tracker", "provenance_tracker.py"),
            PROVENANCE_TRACKER_SRC,
        )
        _write(
            os.path.join(repo_root_str, "gen", "provenance-writer", "provenance_writer.py"),
            PROVENANCE_WRITER_SRC,
        )
        _write(
            os.path.join(repo_root_str, "gen", "test-author", "test_author.py"),
            TEST_AUTHOR_SRC,
        )
        _write(
            os.path.join(repo_root_str, "gen", "llm-endpoint", "llm_endpoint.py"),
            LLM_ENDPOINT_SRC,
        )

        component_gate_runner.run_component_gates(
            "comp-foo", repo_root, "m", seed=3, llm_backend=sentinel_backend,
        )

        with open(test_author_record_path) as f:
            test_author_record = json.load(f)
        with open(llm_endpoint_record_path) as f:
            llm_endpoint_record = json.load(f)

        assert test_author_record["bundle_marker"] == bundle_marker
        assert test_author_record["model"] == "m"
        assert test_author_record["seed"] == 3
        assert test_author_record["backend_marker"] == sentinel_backend.marker

        assert llm_endpoint_record["model"] == "m"
        assert llm_endpoint_record["backend_marker"] == sentinel_backend.marker
    finally:
        if old_test_author_env is None:
            os.environ.pop("TEST_AUTHOR_RECORD_PATH", None)
        else:
            os.environ["TEST_AUTHOR_RECORD_PATH"] = old_test_author_env
        if old_llm_endpoint_env is None:
            os.environ.pop("LLM_ENDPOINT_RECORD_PATH", None)
        else:
            os.environ["LLM_ENDPOINT_RECORD_PATH"] = old_llm_endpoint_env
        shutil.rmtree(repo_root_str, ignore_errors=True)
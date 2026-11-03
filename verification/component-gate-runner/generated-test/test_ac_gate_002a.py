import json
from pathlib import Path

import component_gate_runner


BUNDLE_MARKER = "AC_GATE_002A_SENTINEL_BUNDLE"


def _write_fake_module(repo_root, slug, module_name, source):
    module_dir = repo_root / "gen" / slug
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / f"{module_name}.py").write_text(source, encoding="utf-8")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


PROVENANCE_CHECKER_SRC = """
def current_sealed_key(component_id, repo_root):
    return None


class _ProvenanceKey:
    def __init__(self):
        self.spec_bundle_hash = "sha256:" + "0" * 64
        self.gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@1.0.0",
            "secret_scanner": "secret_scanner@1.0.0",
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


def check_sealed_provenance(component_id, repo_root):
    raise AssertionError("check_sealed_provenance must not be called for a non-sealed component")
"""


SPEC_BUNDLE_ASSEMBLER_SRC = """
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "1" * 64,
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


GENERATOR_SRC = """
def generate(bundle, model, retry_feedback, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        component_id = bundle["component_id"]
        spec_bundle_hash = bundle["spec_bundle_hash"]
    else:
        component_id = bundle.component_id
        spec_bundle_hash = bundle.spec_bundle_hash
    return {
        "component_id": component_id,
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"generated.py": "# generated"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""


VERIFIER_ORCHESTRATOR_SRC = """
GATE_VERSION = "verifier-orchestrator@2.0.0"

_BUNDLE_MARKER = "AC_GATE_002A_SENTINEL_BUNDLE"


def verify(component_id, repo_root, judge=None, test_author=None):
    sentinel_bundle = {"__sentinel__": _BUNDLE_MARKER}
    test_author(sentinel_bundle)

    criterion_bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "Given/When/Then prose",
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
"""


TEST_AUTHOR_SRC = """
import json
import os


def author_test(bundle, model, seed=0, repo_root=None, llm_backend=None):
    if isinstance(bundle, dict):
        bundle_marker = bundle.get("__sentinel__")
    else:
        bundle_marker = getattr(bundle, "__sentinel__", None)
    backend_marker = getattr(llm_backend, "marker", None)
    log_path = os.environ["GATE_002A_CALL_LOG"]
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "call": "author_test",
            "bundle_marker": bundle_marker,
            "model": model,
            "seed": seed,
            "backend_marker": backend_marker,
        }) + "\\n")
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/foo/generated-test/test_ac_foo_001.py",
            "content": "def test_x():\\n    pass\\n",
        },
        "model_call_error": None,
    }
"""


LLM_ENDPOINT_SRC = """
import json
import os


def complete(prompt, model, *, backend=None, **params):
    backend_marker = getattr(backend, "marker", None)
    log_path = os.environ["GATE_002A_CALL_LOG"]
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "call": "complete",
            "model": model,
            "backend_marker": backend_marker,
        }) + "\\n")
    return {
        "text": "ok",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
"""


LICENSE_SCANNER_SRC = """
def scan(component_id, repo_root):
    return {
        "component_id": component_id,
        "gate_version": "license_scanner@1.0.0",
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
    return "license_scanner@1.0.0"
"""


SECRET_SCANNER_SRC = """
def scan(repo_root):
    return {
        "scope": "full",
        "gate_version": "secret_scanner@1.0.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "secret_scanner@1.0.0"
"""


PROVENANCE_TRACKER_SRC = """
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    return {
        "attempt_id": "2026-01-01T00:00:00Z-test",
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


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
"""


def test_ac_gate_002a(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_002A_CALL_LOG", str(log_path))

    _write_fake_module(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    _write_fake_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_fake_module(repo_root, "generator", "generator", GENERATOR_SRC)
    _write_fake_module(repo_root, "verifier-orchestrator", "verifier_orchestrator", VERIFIER_ORCHESTRATOR_SRC)
    _write_fake_module(repo_root, "test-author", "test_author", TEST_AUTHOR_SRC)
    _write_fake_module(repo_root, "llm-endpoint", "llm_endpoint", LLM_ENDPOINT_SRC)
    _write_fake_module(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
    _write_fake_module(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)
    _write_fake_module(repo_root, "provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_SRC)
    _write_fake_module(repo_root, "provenance-writer", "provenance_writer", PROVENANCE_WRITER_SRC)

    class _SentinelBackend:
        marker = "AC_GATE_002A_SENTINEL_BACKEND"

    sentinel_backend = _SentinelBackend()

    component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", seed=3, llm_backend=sentinel_backend,
    )

    assert log_path.exists()
    entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    author_test_entries = [e for e in entries if e["call"] == "author_test"]
    complete_entries = [e for e in entries if e["call"] == "complete"]

    assert len(author_test_entries) == 1
    author_entry = author_test_entries[0]
    assert author_entry["bundle_marker"] == BUNDLE_MARKER
    assert author_entry["model"] == "m"
    assert author_entry["seed"] == 3
    assert author_entry["backend_marker"] == sentinel_backend.marker

    assert len(complete_entries) == 1
    complete_entry = complete_entries[0]
    assert complete_entry["model"] == "m"
    assert complete_entry["backend_marker"] == sentinel_backend.marker
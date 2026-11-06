import json
from pathlib import Path

import pytest

import component_gate_runner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_module(repo_root: Path, slug: str, module_name: str, source: str) -> None:
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source)


PROVENANCE_CHECKER_SRC = r'''
import json
import os


def current_sealed_key(component_id, repo_root):
    return None


class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_provenance_key(component_id, repo_root):
    return ProvenanceKey(
        spec_bundle_hash="sha256:" + "a" * 64,
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.3+9f2c41ab07de",
            "secret_scanner": "secret_scanner@0.0.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"call": "check_provenance"}) + "\n")
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
'''

SPEC_BUNDLE_ASSEMBLER_SRC = r'''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "spec text",
        "interface": "interface text",
        "constraints": "constraints text",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "glossary text",
        "hint_code": None,
    }
'''

GENERATOR_SRC = r'''
import json
import os


def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):
    with open(os.environ["GATE_TEST_CALL_LOG"], "a") as f:
        f.write(json.dumps({"call": "generate", "retry_feedback": retry_feedback}) + "\n")
    if isinstance(bundle, dict):
        component_id = bundle.get("component_id")
    else:
        component_id = getattr(bundle, "component_id", None)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print(\'hi\')\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''

VERIFIER_ORCHESTRATOR_SRC = r'''
GATE_VERSION = "verifier-orchestrator@2.0.0"


def verify(component_id, repo_root, judge=None, test_author=None):
    return {
        "component_id": component_id,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            {
                "id": "AC-FOO-002",
                "covers": "R-FOO-002",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "boom", "expected": 1, "actual": 2},
            },
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "overall": "fail",
    }
'''

LICENSE_SCANNER_SRC = r'''
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

SECRET_SCANNER_SRC = r'''
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

PROVENANCE_TRACKER_SRC = r'''
import json
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
    (attempts_dir / "2026-01-01T00-00-00Z-abc123.json").write_text(json.dumps(record))
    return record
'''

PROVENANCE_WRITER_SRC = r'''
def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
'''


def test_generator_called_once_with_no_retry_feedback_blocks_on_verification_failure(tmp_path, monkeypatch):
    repo_root = tmp_path
    component_id = "comp-foo"

    call_log = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_CALL_LOG", str(call_log))

    _write_module(repo_root, "provenance-checker", "provenance_checker", PROVENANCE_CHECKER_SRC)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_module(repo_root, "generator", "generator", GENERATOR_SRC)
    _write_module(repo_root, "verifier-orchestrator", "verifier_orchestrator", VERIFIER_ORCHESTRATOR_SRC)
    _write_module(repo_root, "license-scanner", "license_scanner", LICENSE_SCANNER_SRC)
    _write_module(repo_root, "secret-scanner", "secret_scanner", SECRET_SCANNER_SRC)
    _write_module(repo_root, "provenance-tracker", "provenance_tracker", PROVENANCE_TRACKER_SRC)
    _write_module(repo_root, "provenance-writer", "provenance_writer", PROVENANCE_WRITER_SRC)

    result = component_gate_runner.run_component_gates(
        component_id=component_id,
        repo_root=repo_root,
        model="claude-sonnet-5",
        seed=0,
    )

    generate_calls = []
    if call_log.exists():
        for line in call_log.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("call") == "generate":
                generate_calls.append(entry)

    assert len(generate_calls) == 1
    assert generate_calls[0]["retry_feedback"] is None

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "verification_failed"
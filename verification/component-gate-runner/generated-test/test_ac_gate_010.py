import json

import pytest

import component_gate_runner


def _read_jsonl(path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


_PROVENANCE_CHECKER = '''
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
'''


_SPEC_BUNDLE_ASSEMBLER = '''
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "spec": "fixture spec text",
        "interface": "fixture interface text",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }
'''


_GENERATOR = '''
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
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
        "files": {"foo.py": "MARKER_SOURCE\\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
'''


_VERIFIER_ORCHESTRATOR = '''
import json
import os


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def verify(component_id, repo_root, judge=None, test_author=None):
    bundle = {
        "component_id": component_id,
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "MARKER_CRIT",
        "requirement_text": "MARKER_REQ",
        "interface": "MARKER_IFACE",
        "glossary": "",
    }
    outcome = judge(bundle)

    log_path = os.environ.get("HOTDOCS_TEST_JUDGE_LOG")
    if log_path:
        record = {
            "result": _get(outcome, "result"),
            "rationale": _get(outcome, "rationale"),
        }
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\\n")

    result = _get(outcome, "result")
    criterion_result = "pass" if result == "pass" else "fail"

    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": criterion_result,
                "rationale": _get(outcome, "rationale"),
            }
        ],
        "requirement_results": {"R-FOO-001": criterion_result},
        "interface_drift": False,
        "mutation_score": None,
        "overall": criterion_result,
    }
'''


_LICENSE_SCANNER = '''
def scan(component_id, repo_root):
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


def gate_version(repo_root):
    return "license_scanner@4.0.0"
'''


_SECRET_SCANNER = '''
def scan(repo_root):
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


def gate_version(repo_root):
    return "secret_scanner@3.0.0"
'''


_PROVENANCE_TRACKER = '''
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-0001.json").write_text("{}", encoding="utf-8")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-abc123",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result,
        "verification": verification_report,
    }
'''


_PROVENANCE_WRITER = '''
def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
'''


_LLM_ENDPOINT = '''
import json
import os


def complete(prompt, model, *, backend=None, **params):
    log_path = os.environ.get("HOTDOCS_TEST_COMPLETE_LOG")
    if log_path:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"prompt": prompt, "model": model}) + "\\n")

    mode = os.environ.get("HOTDOCS_TEST_COMPLETE_MODE", "pass_fenced")

    if mode == "model_call_error":
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "simulated failure"},
        }
    if mode == "not_json":
        return {
            "text": "not json",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }
    if mode == "bad_result":
        return {
            "text": \'```json\\n{"result": "maybe"}\\n```\',
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return {
        "text": \'```json\\n{"result": "pass", "rationale": "ok"}\\n```\',
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
'''


def _write_module(repo_root, slug, module_name, source):
    mod_dir = repo_root / "gen" / slug
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / f"{module_name}.py").write_text(source, encoding="utf-8")


def _setup_repo(tmp_path):
    repo_root = tmp_path / "repo"
    foo_dir = repo_root / "gen" / "foo"
    foo_dir.mkdir(parents=True)
    (foo_dir / "foo.py").write_text("MARKER_SOURCE\n", encoding="utf-8")

    _write_module(repo_root, "provenance-checker", "provenance_checker", _PROVENANCE_CHECKER)
    _write_module(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER)
    _write_module(repo_root, "generator", "generator", _GENERATOR)
    _write_module(repo_root, "verifier-orchestrator", "verifier_orchestrator", _VERIFIER_ORCHESTRATOR)
    _write_module(repo_root, "license-scanner", "license_scanner", _LICENSE_SCANNER)
    _write_module(repo_root, "secret-scanner", "secret_scanner", _SECRET_SCANNER)
    _write_module(repo_root, "provenance-tracker", "provenance_tracker", _PROVENANCE_TRACKER)
    _write_module(repo_root, "provenance-writer", "provenance_writer", _PROVENANCE_WRITER)
    _write_module(repo_root, "llm-endpoint", "llm_endpoint", _LLM_ENDPOINT)
    return repo_root


def _run_pipeline(tmp_path, monkeypatch, complete_mode):
    repo_root = _setup_repo(tmp_path)
    judge_log = tmp_path / "judge_log.jsonl"
    complete_log = tmp_path / "complete_log.jsonl"
    monkeypatch.setenv("HOTDOCS_TEST_JUDGE_LOG", str(judge_log))
    monkeypatch.setenv("HOTDOCS_TEST_COMPLETE_LOG", str(complete_log))
    monkeypatch.setenv("HOTDOCS_TEST_COMPLETE_MODE", complete_mode)

    component_gate_runner.run_component_gates("comp-foo", repo_root, "mock-model")

    return _read_jsonl(judge_log), _read_jsonl(complete_log)


def test_judge_calls_complete_once_with_markers_and_records_pass(tmp_path, monkeypatch):
    judge_records, complete_records = _run_pipeline(tmp_path, monkeypatch, "pass_fenced")

    assert len(complete_records) == 1
    prompt = complete_records[0]["prompt"]
    for marker in ("MARKER_SOURCE", "MARKER_CRIT", "MARKER_REQ", "MARKER_IFACE"):
        assert marker in prompt

    assert len(judge_records) == 1
    outcome = judge_records[0]
    assert outcome["result"] == "pass"
    assert outcome["rationale"] == "ok"


@pytest.mark.parametrize("complete_mode", ["model_call_error", "not_json", "bad_result"])
def test_judge_unavailable_never_passes(tmp_path, monkeypatch, complete_mode):
    judge_records, _ = _run_pipeline(tmp_path, monkeypatch, complete_mode)

    assert len(judge_records) == 1
    outcome = judge_records[0]
    assert outcome["result"] == "fail"
    assert outcome["rationale"].startswith("judge unavailable")
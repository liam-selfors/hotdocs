import json
import os

import pytest


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_PROVENANCE_CHECKER_SRC = r"""
class _Key:
    def __init__(self):
        self.spec_bundle_hash = "sha256:" + "0" * 64
        self.gate_versions = {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@1.0.0",
            "secret_scanner": "secret_scanner@1.0.0",
        }


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return _Key()


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {
        "hit": False,
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
"""

_SPEC_BUNDLE_ASSEMBLER_SRC = r"""
def assemble(component_id, repo_root, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "spec": "spec text",
        "interface": "iface text",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "glossary text",
        "hint_code": None,
    }
"""

_GENERATOR_SRC = r"""
def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "0" * 64,
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "MARKER_SOURCE\n"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
"""

_VERIFIER_ORCHESTRATOR_SRC = r"""
import json
import os

GATE_VERSION = "verifier-orchestrator@2.0.0"


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

    if isinstance(outcome, dict):
        result = outcome.get("result")
        rationale = outcome.get("rationale")
    else:
        result = getattr(outcome, "result", None)
        rationale = getattr(outcome, "rationale", None)

    with open(os.environ["JUDGE_RECORD_PATH"], "w", encoding="utf-8") as f:
        json.dump({"result": result, "rationale": rationale}, f)

    criterion_result = result if result in ("pass", "fail") else "fail"

    return {
        "component_id": component_id,
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "llm-judge",
                "result": criterion_result,
                "rationale": rationale,
            }
        ],
        "requirement_results": {"R-FOO-001": criterion_result},
        "interface_drift": False,
        "mutation_score": None,
        "overall": criterion_result,
    }
"""

_LICENSE_SCANNER_SRC = r"""
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

_SECRET_SCANNER_SRC = r"""
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

_PROVENANCE_TRACKER_SRC = r"""
from pathlib import Path


def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    attempts_dir = Path(repo_root) / ".hotdocs" / "attempts" / slug
    attempts_dir.mkdir(parents=True, exist_ok=True)
    (attempts_dir / "attempt-0001.json").write_text("{}", encoding="utf-8")

    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": component_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": generation_result if isinstance(generation_result, dict) else {},
        "verification": verification_report if isinstance(verification_report, dict) else None,
    }
"""

_PROVENANCE_WRITER_SRC = r"""
def write_provenance(component_id, inputs, repo_root):
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
"""

_LLM_ENDPOINT_SRC = r"""
import json
import os


def complete(prompt, model, *, backend=None, **params):
    log_path = os.environ["LLM_CALL_LOG"]
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(prompt)
        f.write("\n===CALL-END===\n")

    mode = os.environ.get("LLM_RESPONSE_MODE", "ok")

    if mode == "model_call_error":
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "boom"},
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
            "text": json.dumps({"result": "maybe"}),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return {
        "text": "```json\n" + json.dumps({"result": "pass", "rationale": "ok"}) + "\n```",
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }
"""


def _write_dependency(repo_root, slug_dir, module_name, content):
    path = repo_root / "gen" / slug_dir / (module_name + ".py")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _setup_repo(tmp_path, response_mode):
    repo_root = tmp_path
    call_log = repo_root / "llm_calls.log"
    record_path = repo_root / "judge_outcome.json"

    os.environ["LLM_CALL_LOG"] = str(call_log)
    os.environ["LLM_RESPONSE_MODE"] = response_mode
    os.environ["JUDGE_RECORD_PATH"] = str(record_path)

    (repo_root / "gen" / "foo").mkdir(parents=True)
    (repo_root / "gen" / "foo" / "foo.py").write_text("MARKER_SOURCE\n", encoding="utf-8")

    _write_dependency(repo_root, "provenance-checker", "provenance_checker", _PROVENANCE_CHECKER_SRC)
    _write_dependency(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", _SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_dependency(repo_root, "generator", "generator", _GENERATOR_SRC)
    _write_dependency(repo_root, "verifier-orchestrator", "verifier_orchestrator", _VERIFIER_ORCHESTRATOR_SRC)
    _write_dependency(repo_root, "license-scanner", "license_scanner", _LICENSE_SCANNER_SRC)
    _write_dependency(repo_root, "secret-scanner", "secret_scanner", _SECRET_SCANNER_SRC)
    _write_dependency(repo_root, "provenance-tracker", "provenance_tracker", _PROVENANCE_TRACKER_SRC)
    _write_dependency(repo_root, "provenance-writer", "provenance_writer", _PROVENANCE_WRITER_SRC)
    _write_dependency(repo_root, "llm-endpoint", "llm_endpoint", _LLM_ENDPOINT_SRC)

    return repo_root, call_log, record_path


def _run(tmp_path, response_mode):
    repo_root, call_log, record_path = _setup_repo(tmp_path, response_mode)

    import component_gate_runner

    result = component_gate_runner.run_component_gates(
        "comp-foo",
        repo_root,
        model="mock-model-1",
        seed=0,
        llm_backend=None,
        retry_feedback=None,
    )

    call_log_text = call_log.read_text(encoding="utf-8") if call_log.exists() else ""
    outcome = json.loads(record_path.read_text(encoding="utf-8"))
    return result, call_log_text, outcome


def test_judge_single_complete_call_with_all_markers_and_pass_outcome(tmp_path):
    result, call_log_text, outcome = _run(tmp_path, "ok")

    calls = [c for c in call_log_text.split("===CALL-END===") if c.strip()]
    assert len(calls) == 1

    prompt = calls[0]
    for marker in ("MARKER_SOURCE", "MARKER_CRIT", "MARKER_REQ", "MARKER_IFACE"):
        assert marker in prompt

    assert outcome["result"] == "pass"
    assert outcome["rationale"] == "ok"

    assert _get(result, "component_id") == "comp-foo"
    assert _get(result, "provenance_hit") is False


@pytest.mark.parametrize("response_mode", ["model_call_error", "not_json", "bad_result"])
def test_judge_unavailable_on_bad_response(tmp_path, response_mode):
    result, call_log_text, outcome = _run(tmp_path, response_mode)

    assert outcome["result"] == "fail"
    assert outcome["rationale"].startswith("judge unavailable")

    assert _get(result, "component_id") == "comp-foo"
import json

import component_gate_runner


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


PROVENANCE_CHECKER_SRC = r"""
class _Key:
    def __init__(self, spec_bundle_hash, gate_versions):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions


def current_sealed_key(component_id, repo_root):
    return None


def current_provenance_key(component_id, repo_root):
    return _Key(
        "sha256:k",
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        },
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    return {"hit": False, "verification_report": None, "license_scan": None, "secret_scan": None}
"""

SPEC_BUNDLE_ASSEMBLER_SRC = r"""
def assemble(component_id, repo_root=None, mode="cold"):
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:k",
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
"""

GENERATOR_FILES_SRC = r"""
import json

LOG_PATH = __LOG__


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hello')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": retry_feedback,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "generator", "event": "generate"}) + "\n")
    return result
"""

GENERATOR_ERROR_SRC = r"""
import json

LOG_PATH = __LOG__


def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):
    result = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": model,
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": {"category": "network", "message": "boom"},
        "refused": None,
        "retry_feedback": retry_feedback,
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "generator", "event": "generate"}) + "\n")
    return result
"""

VERIFIER_ORCHESTRATOR_SRC = r"""
import json
from dataclasses import dataclass, asdict

LOG_PATH = __LOG__

GATE_VERSION = "verifier-orchestrator@2.0.0"


@dataclass
class _VerificationReport:
    component_id: str
    criteria: list
    requirement_results: dict
    interface_drift: bool
    mutation_score: object
    overall: str

    def to_dict(self):
        return asdict(self)


def verify(component_id, repo_root, judge=None, test_author=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "verifier_orchestrator", "event": "verify"}) + "\n")
    overall = __OVERALL__
    result_flag = "pass" if overall == "pass" else "fail"
    criterion = {
        "id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "kind": "compiled",
        "result": result_flag,
    }
    if result_flag == "fail":
        criterion["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
    return _VerificationReport(
        component_id=component_id,
        criteria=[criterion],
        requirement_results={"R-FOO-001": result_flag},
        interface_drift=False,
        mutation_score=0.5,
        overall=overall,
    )
"""

LICENSE_SCANNER_SRC = r"""
import json

LOG_PATH = __LOG__


def scan(component_id, repo_root):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "license_scanner", "event": "scan"}) + "\n")
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

SECRET_SCANNER_SRC = r"""
import json

LOG_PATH = __LOG__


def scan(repo_root):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "secret_scanner", "event": "scan"}) + "\n")
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

PROVENANCE_WRITER_SRC = r"""
import json

LOG_PATH = __LOG__


def write_provenance(component_id, inputs, repo_root):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "provenance_writer", "event": "write_provenance"}) + "\n")
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    return None
"""

PROVENANCE_TRACKER_NORMAL_SRC = r"""
import json

LOG_PATH = __LOG__


def _get(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def write_attempt_record(*args, **kwargs):
    params = ["component_id", "generation_result", "verification_report", "spec_bundle_hash", "repo_root"]
    bound = dict(zip(params, args))
    bound.update(kwargs)
    gen = bound.get("generation_result")
    ver = bound.get("verification_report")
    gen_record = None
    if gen is not None:
        gen_record = {
            "component_id": _get(gen, "component_id"),
            "spec_bundle_hash": _get(gen, "spec_bundle_hash"),
            "model": _get(gen, "model"),
            "prompt_version": _get(gen, "prompt_version"),
            "cache_hit": _get(gen, "cache_hit"),
            "files": _get(gen, "files"),
            "model_call_error": _get(gen, "model_call_error"),
            "refused": _get(gen, "refused"),
            "retry_feedback": _get(gen, "retry_feedback"),
        }
    ver_record = None
    if ver is not None:
        ver_record = {
            "component_id": _get(ver, "component_id"),
            "criteria": _get(ver, "criteria"),
            "requirement_results": _get(ver, "requirement_results"),
            "interface_drift": _get(ver, "interface_drift"),
            "mutation_score": _get(ver, "mutation_score"),
            "overall": _get(ver, "overall"),
        }
    record = {
        "component_id": bound.get("component_id"),
        "generation_result": gen_record,
        "verification_report": ver_record,
        "spec_bundle_hash": bound.get("spec_bundle_hash"),
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "provenance_tracker", "event": "write_attempt_record", "record": record}) + "\n")
    return {
        "attempt_id": "2026-01-01T00:00:00Z-aaaaaa",
        "component_id": bound.get("component_id"),
        "timestamp": "2026-01-01T00:00:00Z",
        "spec_bundle_hash": bound.get("spec_bundle_hash"),
        "generation": gen_record,
        "verification": ver_record,
    }
"""

PROVENANCE_TRACKER_RAISE_SRC = r"""
import json

LOG_PATH = __LOG__


def write_attempt_record(*args, **kwargs):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({"dep": "provenance_tracker", "event": "write_attempt_record_raise"}) + "\n")
    raise RuntimeError("boom")
"""


def _build_repo(tmp_path, log_path, *, generation_mode, verify_overall=None, tracker_mode="normal"):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_literal = repr(str(log_path))

    _write(repo_root / "gen" / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_SRC)
    _write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER_SRC)

    if generation_mode == "files":
        generator_src = GENERATOR_FILES_SRC.replace("__LOG__", log_literal)
    else:
        generator_src = GENERATOR_ERROR_SRC.replace("__LOG__", log_literal)
    _write(repo_root / "gen" / "generator" / "generator.py", generator_src)

    if generation_mode == "files":
        overall_literal = repr(verify_overall)
        verifier_src = VERIFIER_ORCHESTRATOR_SRC.replace("__LOG__", log_literal).replace("__OVERALL__", overall_literal)
        _write(repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py", verifier_src)
        _write(
            repo_root / "gen" / "provenance-writer" / "provenance_writer.py",
            PROVENANCE_WRITER_SRC.replace("__LOG__", log_literal),
        )

    _write(repo_root / "gen" / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_SRC.replace("__LOG__", log_literal))
    _write(repo_root / "gen" / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC.replace("__LOG__", log_literal))

    if tracker_mode == "raise":
        tracker_src = PROVENANCE_TRACKER_RAISE_SRC.replace("__LOG__", log_literal)
    else:
        tracker_src = PROVENANCE_TRACKER_NORMAL_SRC.replace("__LOG__", log_literal)
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", tracker_src)

    return repo_root


def test_write_attempt_record_called_once_after_both_scans(tmp_path):
    log_path = tmp_path / "calls.jsonl"
    repo_root = _build_repo(tmp_path, log_path, generation_mode="files", verify_overall="fail")

    component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model:test")

    entries = _read_log(log_path)
    tracker_entries = [e for e in entries if e["dep"] == "provenance_tracker"]
    assert len(tracker_entries) == 1

    license_idx = next(i for i, e in enumerate(entries) if e["dep"] == "license_scanner")
    secret_idx = next(i for i, e in enumerate(entries) if e["dep"] == "secret_scanner")
    tracker_idx = next(i for i, e in enumerate(entries) if e["dep"] == "provenance_tracker")

    assert tracker_idx > license_idx
    assert tracker_idx > secret_idx

    record = tracker_entries[0]["record"]
    assert record["component_id"] == "comp-foo"
    assert record["spec_bundle_hash"] == "sha256:k"
    assert record["generation_result"] == {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": "fake-model:test",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {"foo.py": "print('hello')"},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    assert record["verification_report"] == {
        "component_id": "comp-foo",
        "criteria": [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "compiled",
                "result": "fail",
                "failure_detail": {"message": "x failed", "expected": 1, "actual": 2},
            }
        ],
        "requirement_results": {"R-FOO-001": "fail"},
        "interface_drift": False,
        "mutation_score": 0.5,
        "overall": "fail",
    }


def test_write_attempt_record_receives_none_verification_report_on_model_call_error(tmp_path):
    log_path = tmp_path / "calls.jsonl"
    repo_root = _build_repo(tmp_path, log_path, generation_mode="error")

    component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model:test")

    entries = _read_log(log_path)
    tracker_entries = [e for e in entries if e["dep"] == "provenance_tracker"]
    assert len(tracker_entries) == 1
    record = tracker_entries[0]["record"]
    assert record["verification_report"] is None


def test_write_attempt_record_exception_does_not_change_result(tmp_path):
    log_path = tmp_path / "calls.jsonl"
    repo_root = _build_repo(
        tmp_path, log_path, generation_mode="files", verify_overall="pass", tracker_mode="raise"
    )

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model:test")

    entries = _read_log(log_path)
    raise_entries = [
        e for e in entries if e["dep"] == "provenance_tracker" and e["event"] == "write_attempt_record_raise"
    ]
    assert len(raise_entries) == 1

    blocked = _get(result, "blocked")
    assert blocked is False
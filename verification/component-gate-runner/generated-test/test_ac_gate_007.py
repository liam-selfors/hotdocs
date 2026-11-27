# hotdocs-criterion: sha256:272050e76399f916feec9820ac385cc63e3a4a93450e25963c04286d8e6134cf
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HEADER = '''import json

def _log(name, **kw):
    entry = dict(call=name)
    entry.update(kw)
    with open(LOG, "a") as f:
        f.write(json.dumps(entry, default=repr) + "\\n")

def _g(v, n):
    return v.get(n) if isinstance(v, dict) else getattr(v, n, None)

'''


PROVENANCE_CHECKER = '''
class _Key:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    if not SEALED:
        return None
    return _Key(
        owners=["pipeline-team"],
        source_path="pipeline/foo/",
        source_hash="sha256:k",
        verifier_version="verifier-orchestrator@2.0.0",
    )


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return _Key(
        spec_bundle_hash="sha256:abc",
        spec_bundle_parts={"spec": "sha256:s", "dependency_code": "sha256:d"},
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.0.0+v11",
        },
        assets=[{"kind": "python", "path": ".", "definition_sha256": None,
                 "adapter_sha256": "sha256:a", "versions": {"python": "3.12.4"},
                 "lockfile_sha256": None}],
        drivers=[],
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):
    _log("check_provenance", component_id=component_id)
    return {"hit": False, "reason": "no manifest", "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {"hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None, "secret_scan": None,
            "owners": None, "source_hash": None, "written_at": None}
'''


SPEC_BUNDLE_ASSEMBLER = '''
def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return {"component_id": component_id, "spec_bundle_hash": "sha256:abc",
            "spec": "s", "interface": "i", "constraints": "", "dependency_interfaces": {},
            "dependency_context": {}, "dependency_usage": {}, "vars": {}, "glossary": "",
            "hint_code": None,
            "spec_bundle_parts": {"spec": "sha256:s", "dependency_code": "sha256:d"}}


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id)
    return {"component_id": component_id, "criterion_id": criterion_id, "covers": "R-FOO-001",
            "criterion_text": "", "requirement_text": "", "interface": "", "glossary": "",
            "dependency_interfaces": {}, "testing": ""}
'''


GENERATION_LOOP = '''
RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def make_closures(model, seed, repo_root, llm_backend=None):
    _log("make_closures", model=model)

    def test_author(bundle):
        return {"model_call_error": None, "file": None}

    def judge(bundle):
        return {"result": "pass", "rationale": None}

    return (test_author, judge)


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,
                 on_attempt=None):
    _log("run_attempts", component_id=component_id)
    generation_result = {
        "component_id": component_id, "spec_bundle_hash": "sha256:abc", "model": model,
        "prompt_version": "v12", "cache_hit": False, "files": {"foo.py": "x = 1\\n"},
        "model_call_error": None, "refused": None, "retry_feedback": None, "mode": "single",
        "transcript_sha256": None, "turns": 1, "tool_calls": 0, "isolation": None,
    }
    verification_report = {
        "component_id": component_id,
        "criteria": [{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}],
        "requirement_results": {"R-FOO-001": "pass"}, "interface_drift": False,
        "mutation_score": 0.9, "mutation_error": None, "assets": [], "drivers": [],
        "overall": "pass",
    }
    attempt = {"number": 1, "outcome": "passed", "retry_feedback": [], "error_category": None,
               "surface_ok": True, "overall": "pass", "failed_requirements": [],
               "transcript_sha256": None, "reauthored_tests": []}
    on_attempt(attempt, generation_result, verification_report)
    return {"passed": True, "stop_reason": "passed", "attempts": [attempt],
            "generation_result": generation_result,
            "verification_report": verification_report, "surface_report": None}
'''


PROVENANCE_TRACKER = '''
def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    return {"attempt_id": "2026-10-25T14:32:01Z-a1b2c3", "component_id": component_id,
            "timestamp": "2026-10-25T14:32:01Z", "spec_bundle_hash": spec_bundle_hash,
            "generation": generation_result, "verification": verification_report}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {}, "capabilities": {},
            "secret_scan": None, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures")
    return []
'''


VERIFIER = '''
GATE_VERSION = "verifier-orchestrator@2.0.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return json.loads(REPORT_JSON)
'''


LICENSE = '''
def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    return {"component_id": component_id,
            "gate_version": "license_scanner@4.0.0-no-reference-corpus",
            "evaluated": False, "reason": "no-reference-corpus", "similarity_score": None,
            "block_threshold": None, "blocked": False, "matches": [], "notified": False,
            "notification_delivery_error": None, "cache_hit": False}


def gate_version(repo_root):
    return "license_scanner@4.0.0-no-reference-corpus"
'''


SECRET = '''
def _result():
    return {"scope": "full", "gate_version": "secret_scanner@0.0.0", "flagged": False,
            "matches": [], "allowed": [], "unused_allowlist_entries": [], "notified": False,
            "notification_delivery_error": None, "cache_hit": False}


def scan(repo_root):
    _log("secret_scan")
    return _result()


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    r = _result()
    r["scope"] = "precommit"
    return r


def gate_version(repo_root):
    return "secret_scanner@0.0.0"


def propose(repo_root):
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


WRITER = '''
class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id,
         inputs_component_id=_g(inputs, "component_id"),
         owners=_g(inputs, "owners"),
         source_path=_g(inputs, "source_path"),
         source_hash=_g(inputs, "source_hash"),
         verifier_version=_g(inputs, "verifier_version"),
         verification_report=_g(inputs, "verification_report"))
    return None
'''


def make_report(overall):
    second = {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"}
    if overall == "fail":
        second = {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "fail",
                  "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2},
                  "failure_origin": "implementation"}
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
            second,
        ],
        "requirement_results": {"R-FOO-001": "pass", "R-FOO-002": second["result"]},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "drivers": [],
        "overall": overall,
    }


def write_fake(repo_root, slug, body, extra=""):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(extra + HEADER + body)


def build_repo(tmp_path, sealed, overall="pass"):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    log_line = "LOG = " + repr(str(log)) + "\n"
    write_fake(repo_root, "provenance-checker", PROVENANCE_CHECKER,
               log_line + "SEALED = " + repr(bool(sealed)) + "\n")
    write_fake(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER, log_line)
    write_fake(repo_root, "generation-loop", GENERATION_LOOP, log_line)
    write_fake(repo_root, "provenance-tracker", PROVENANCE_TRACKER, log_line)
    write_fake(repo_root, "verifier-orchestrator", VERIFIER,
               log_line + "REPORT_JSON = " + repr(json.dumps(make_report(overall))) + "\n")
    write_fake(repo_root, "license-scanner", LICENSE, log_line)
    write_fake(repo_root, "secret-scanner", SECRET, log_line)
    write_fake(repo_root, "provenance-writer", WRITER, log_line)
    return repo_root, log


def read_log(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def names(entries):
    return [e["call"] for e in entries]


def assert_sealed_calls(entries, report):
    calls = names(entries)
    for never in ("check_provenance", "current_provenance_key", "assemble", "run_attempts",
                  "write_attempt_record", "write_provenance"):
        assert never not in calls, (never, calls)
    assert calls.count("verify") == 1, calls
    assert calls.count("license_scan") == 1, calls
    assert calls.count("secret_scan") == 1, calls
    assert calls.count("write_sealed_provenance") == 1, calls
    w = calls.index("write_sealed_provenance")
    assert w > calls.index("verify")
    assert w > calls.index("license_scan")
    assert w > calls.index("secret_scan")
    entry = entries[w]
    assert entry["component_id"] == "comp-foo"
    assert entry["inputs_component_id"] == "comp-foo"
    assert entry["owners"] == ["pipeline-team"]
    assert entry["source_path"] == "pipeline/foo/"
    assert entry["source_hash"] == "sha256:k"
    assert entry["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert entry["verification_report"] == report


def test_sealed_component_passing_verify(tmp_path):
    repo_root, log = build_repo(tmp_path, sealed=True, overall="pass")
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    entries = read_log(log)
    assert_sealed_calls(entries, make_report("pass"))
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False


def test_sealed_component_failing_verify(tmp_path):
    repo_root, log = build_repo(tmp_path, sealed=True, overall="fail")
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    entries = read_log(log)
    assert_sealed_calls(entries, make_report("fail"))
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"


def test_non_sealed_component_takes_generation_path(tmp_path):
    repo_root, log = build_repo(tmp_path, sealed=False)
    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = names(read_log(log))
    assert "write_sealed_provenance" not in calls, calls
    assert "make_closures" not in calls, calls
    expected = ["current_provenance_key", "check_provenance", "assemble", "run_attempts",
                "write_attempt_record", "license_scan", "secret_scan", "write_provenance"]
    observed = [c for c in calls if c in expected]
    assert observed == expected, calls
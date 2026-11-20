# hotdocs-criterion: sha256:92f77cddc14efa66a1658fd6627e4339cb078047c6e10263edf025eba5b85947
import json
import sys

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = '''
import json
from pathlib import Path
from types import SimpleNamespace

_ROOT = Path(__file__).resolve().parents[2]


def _scenario():
    p = _ROOT / "fake_scenario.txt"
    return p.read_text().strip() if p.is_file() else "pass"


def _log(fn, **kw):
    with open(_ROOT / "calls.log", "a") as f:
        f.write(json.dumps({"fn": fn, "args": kw}, default=repr) + "\\n")


def _assets():
    return [{"kind": "python", "path": ".", "definition_sha256": None,
             "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
             "lockfile_sha256": None}]


def _report(scn):
    rep = {
        "component_id": "comp-foo",
        "criteria": [{"id": "AC-FOO-001", "covers": "R-FOO-001",
                      "kind": "compiled", "result": "pass"}],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": _assets(),
        "overall": "pass",
    }
    if scn == "test_authoring":
        rep["criteria"] = [{
            "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
            "result": "fail", "failure_origin": "test",
            "failure_detail": {"message": "test authoring failed: network: dropped",
                               "expected": None, "actual": None},
        }]
        rep["requirement_results"] = {"R-FOO-001": "fail"}
        rep["overall"] = "fail"
    elif scn == "set_actual":
        rep["criteria"] = [{
            "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
            "result": "fail", "failure_origin": "implementation",
            "failure_detail": {"message": "result.x equals a,b failed",
                               "expected": ["a", "b"], "actual": {"b", "a"}},
        }]
        rep["requirement_results"] = {"R-FOO-001": "fail"}
        rep["overall"] = "fail"
    elif scn == "mutation":
        rep["overall"] = "fail"
        rep["mutation_score"] = None
        rep["mutation_error"] = "mutation baseline failed in the sandbox: pytest exited 1"
    return rep


def _gen(files, mce=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:abc",
        "model": "m",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": files,
        "model_call_error": mce,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }
'''

PROVENANCE_CHECKER = COMMON + '''

def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return SimpleNamespace(
        spec_bundle_hash="sha256:abc",
        gate_versions={
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@3.5.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@3.1.0",
            "generator": "generator@3.0.0+v1",
        },
        assets=_assets(),
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id)
    return {"hit": False, "reason": "no manifest", "verification_report": None,
            "license_scan": None, "secret_scan": None}


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {"hit": False, "sealed": False, "reason": "not_sealed",
            "verification_report": None, "license_scan": None, "secret_scan": None,
            "owners": None, "source_hash": None, "written_at": None}
'''

SPEC_BUNDLE_ASSEMBLER = COMMON + '''

def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:abc",
        "spec": "spec",
        "interface": "interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def assemble_criterion(component_id, criterion_id, repo_root):
    _log("assemble_criterion", component_id=component_id, criterion_id=criterion_id)
    return {"component_id": component_id, "criterion_id": criterion_id,
            "covers": "R-FOO-001", "criterion_text": "", "requirement_text": "",
            "interface": "", "glossary": "", "dependency_interfaces": {}, "testing": ""}
'''

GENERATION_LOOP = COMMON + '''
RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def _attempt(outcome, error_category=None, surface_ok=True, overall="pass",
             failed_requirements=None):
    return {"number": 1, "outcome": outcome, "retry_feedback": [],
            "error_category": error_category, "surface_ok": surface_ok,
            "overall": overall, "failed_requirements": failed_requirements or [],
            "transcript_sha256": None, "reauthored_tests": []}


def run_attempts(component_id, bundle, repo_root, model, *, mode="single",
                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    _log("run_attempts", component_id=component_id, model=model, seed=seed,
         retry_feedback=retry_feedback, mode=mode, max_attempts=max_attempts)
    scn = _scenario()
    if scn == "model_call_error":
        return {
            "passed": False,
            "stop_reason": "max_attempts",
            "attempts": [_attempt("generation_failed", error_category="empty_response",
                                  surface_ok=None, overall=None)],
            "generation_result": _gen({}, {"category": "empty_response",
                                           "message": "no files"}),
            "verification_report": None,
            "surface_report": None,
        }
    if scn in ("test_authoring", "set_actual", "mutation"):
        return {
            "passed": False,
            "stop_reason": "max_attempts",
            "attempts": [_attempt("verification_failed", overall="fail",
                                  failed_requirements=["R-FOO-001"])],
            "generation_result": _gen({"foo.py": "x = 1\\n"}),
            "verification_report": _report(scn),
            "surface_report": {"ok": True, "findings": []},
        }
    return {
        "passed": True,
        "stop_reason": "passed",
        "attempts": [_attempt("passed")],
        "generation_result": _gen({"foo.py": "x = 1\\n"}),
        "verification_report": _report("pass"),
        "surface_report": {"ok": True, "findings": []},
    }


def make_closures(model, seed, repo_root, llm_backend=None):
    _log("make_closures", model=model, seed=seed)

    def test_author(bundle):
        return {"model_call_error": None, "file": None}

    def judge(bundle):
        return {"result": "pass", "rationale": None}

    return (test_author, judge)
'''

PROVENANCE_TRACKER = COMMON + '''

def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    return {"attempt_id": "2026-01-01T00:00:00Z-a1b2c3", "component_id": component_id,
            "timestamp": "2026-01-01T00:00:00Z", "spec_bundle_hash": spec_bundle_hash,
            "generation": {}, "verification": None}


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures", component_id=component_id)
    return []
'''

VERIFIER_ORCHESTRATOR = COMMON + '''
GATE_VERSION = "verifier-orchestrator@3.5.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return _report(_scenario())
'''

LICENSE_SCANNER = COMMON + '''

def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    if _scenario() == "license":
        return {"component_id": component_id,
                "gate_version": "license_scanner@4.0.0-no-reference-corpus",
                "evaluated": False, "reason": "no-reference-corpus",
                "similarity_score": None, "block_threshold": None, "blocked": False,
                "matches": [], "notified": False, "notification_delivery_error": None,
                "cache_hit": False}
    return {"component_id": component_id,
            "gate_version": "license_scanner@4.0.1+000000000000",
            "evaluated": True, "reason": None, "similarity_score": 0.1,
            "block_threshold": 0.7, "blocked": False, "matches": [],
            "notified": False, "notification_delivery_error": None, "cache_hit": False}


def gate_version(repo_root):
    _log("license_gate_version")
    return "license_scanner@4.0.1+000000000000"
'''

SECRET_SCANNER = COMMON + '''

def scan(repo_root):
    _log("secret_scan")
    return {"scope": "full", "gate_version": "secret_scanner@3.1.0",
            "flagged": False, "matches": [], "allowed": [],
            "unused_allowlist_entries": [], "notified": False,
            "notification_delivery_error": None, "cache_hit": False}


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return {"scope": "precommit", "gate_version": "secret_scanner@3.1.0",
            "flagged": False, "matches": [], "allowed": [],
            "unused_allowlist_entries": [], "notified": False,
            "notification_delivery_error": None, "cache_hit": False}


def gate_version(repo_root):
    _log("secret_gate_version")
    return "secret_scanner@3.1.0"


def propose(repo_root):
    _log("propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''

PROVENANCE_WRITER = COMMON + '''

class InvalidSealedInputError(Exception):
    pass


class MissingInputError(Exception):
    pass


def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER,
}


def build_repo(tmp_path, scenario):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for (slug, module), source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (module + ".py")).write_text(source)
    comp = repo_root / "specs" / "components" / "foo"
    comp.mkdir(parents=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n# Foo\n"
    )
    (repo_root / "fake_scenario.txt").write_text(scenario + "\n")
    return repo_root


def read_calls(repo_root):
    log = repo_root / "calls.log"
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_json_pass_with_retry_feedback(tmp_path, capsys, monkeypatch):
    repo_root = build_repo(tmp_path, "pass")
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002", "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "blocked") is False
    calls = [c for c in read_calls(repo_root) if c["fn"] == "run_attempts"]
    assert len(calls) == 1
    args = calls[0]["args"]
    assert args["model"] == "m"
    assert args["seed"] == 2
    assert args["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_pass_with_separate_flag_values(tmp_path, capsys, monkeypatch):
    repo_root = build_repo(tmp_path, "pass")
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model", "m", "--repo-root", str(repo_root),
        "--format", "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "comp-foo" in out
    assert "passed" in out
    assert "attempt 1: passed" in out


def test_model_call_error_exits_1(tmp_path, capsys, monkeypatch):
    repo_root = build_repo(tmp_path, "model_call_error")
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "model_call_error: empty_response: no files" in out


def test_test_authoring_failed_exits_1(tmp_path, capsys, monkeypatch):
    repo_root = build_repo(tmp_path, "test_authoring")
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "test_authoring_failed" in out
    assert "AC-FOO-001: test authoring failed: network: dropped" in out


def test_json_converts_set_actual(tmp_path, capsys, monkeypatch):
    repo_root = build_repo(tmp_path, "set_actual")
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    verification = field(data, "verification")
    criteria = field(verification, "criteria")
    assert len(criteria) == 1
    detail = field(criteria[0], "failure_detail")
    assert field(detail, "actual") == ["a", "b"]


def test_mutation_error_line(tmp_path, capsys, monkeypatch):
    repo_root = build_repo(tmp_path, "mutation")
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "mutation_error: mutation baseline failed in the sandbox: pytest exited 1" in out


def test_license_not_evaluated_line(tmp_path, capsys, monkeypatch):
    repo_root = build_repo(tmp_path, "license")
    monkeypatch.chdir(repo_root)
    component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert "license_scan not evaluated: no-reference-corpus" in out


USAGE_CASES = [
    ("no_model", lambda r: ["generate", "comp-foo", "--repo-root=" + r]),
    ("unknown_component", lambda r: ["generate", "comp-nope", "--model=m", "--repo-root=" + r]),
    ("bad_seed", lambda r: ["generate", "comp-foo", "--model=m", "--seed=x", "--repo-root=" + r]),
    ("bad_format", lambda r: ["generate", "comp-foo", "--model=m", "--format=bogus", "--repo-root=" + r]),
    ("unknown_arg", lambda r: ["generate", "comp-foo", "--model=m", "--hotdocs-smoke-unknown", "--repo-root=" + r]),
    ("wrong_verb", lambda r: ["build", "comp-foo", "--model=m"]),
    ("model_last", lambda r: ["generate", "comp-foo", "--repo-root=" + r, "--model"]),
]


@pytest.mark.parametrize("name,make_argv", USAGE_CASES, ids=[c[0] for c in USAGE_CASES])
def test_usage_errors(tmp_path, capsys, monkeypatch, name, make_argv):
    repo_root = build_repo(tmp_path, "pass")
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main(make_argv(str(repo_root)))
    captured = capsys.readouterr()
    assert rc == 2
    lines = captured.err.splitlines()
    assert lines, "expected output on stderr"
    assert lines[0].startswith("usage error: ")
    assert read_calls(repo_root) == []
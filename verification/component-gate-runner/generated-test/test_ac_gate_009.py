# hotdocs-criterion: sha256:11537f4fb0551c0b8d2f8dde3b4939410fbdfec6f67f107b266c08b7d9d43f1d
import json
import os
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = '''
import json
import os


def _log(name, **kw):
    path = os.environ.get("HOTDOCS_TEST_LOG")
    if not path:
        return
    entry = {"call": name}
    entry.update(kw)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, default=repr) + "\\n")


class Rec:
    def __init__(self, **kw):
        self._keys = list(kw)
        for k, v in kw.items():
            setattr(self, k, v)

    def to_dict(self):
        out = {}
        for k in self._keys:
            v = getattr(self, k)
            if hasattr(v, "to_dict") and callable(v.to_dict):
                v = v.to_dict()
            out[k] = v
        return out

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)
'''


PROVENANCE_CHECKER = COMMON + '''

class ProvenanceKey:
    def __init__(self, spec_bundle_hash, gate_versions, assets):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_versions = gate_versions
        self.assets = assets


def current_sealed_key(component_id, repo_root):
    _log("current_sealed_key", component_id=component_id)
    return None


def current_provenance_key(component_id, repo_root):
    _log("current_provenance_key", component_id=component_id)
    return ProvenanceKey(
        "sha256:abc123",
        {
            "compiler": "criterion-compiler@1.0.0",
            "generated_test": "generated_test@1.0.0",
            "verifier": "verifier-orchestrator@2.0.0",
            "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
            "secret_scanner": "secret_scanner@0.0.0",
            "generator": "generator@3.0.0+v11",
        },
        [{"kind": "python", "path": ".", "definition_sha256": None,
          "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
          "lockfile_sha256": None}],
    )


def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):
    _log("check_provenance", component_id=component_id)
    return {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }


def check_sealed_provenance(component_id, repo_root):
    _log("check_sealed_provenance", component_id=component_id)
    return {
        "hit": False, "sealed": False, "reason": "not_sealed",
        "verification_report": None, "license_scan": None, "secret_scan": None,
        "owners": None, "source_hash": None, "written_at": None,
    }
'''


SPEC_BUNDLE_ASSEMBLER = COMMON + '''

def assemble(component_id, repo_root, mode="cold"):
    _log("assemble", component_id=component_id, mode=mode)
    return {
        "component_id": component_id,
        "spec_bundle_hash": "sha256:abc123",
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
    _log("assemble_criterion", component_id=component_id)
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-FOO-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
'''


GENERATION_LOOP = COMMON + '''

RETRIED_CATEGORIES = ("truncated_response", "missing_module", "empty_response",
                      "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
                      "missing_asset", "malformed_layout")


def _gen(component_id, files, model_call_error, retry_feedback):
    return Rec(
        component_id=component_id,
        spec_bundle_hash="sha256:abc123",
        model="m",
        prompt_version="v1",
        cache_hit=False,
        files=files,
        model_call_error=model_call_error,
        refused=None,
        retry_feedback=retry_feedback,
        mode="single",
        transcript_sha256=None,
        turns=1,
        tool_calls=0,
        isolation=None,
    )


def _report(component_id, criteria, overall, mutation_score=0.9, mutation_error=None):
    results = {}
    for c in criteria:
        results[c["covers"]] = "pass" if c["result"] == "pass" else "fail"
    return Rec(
        component_id=component_id,
        criteria=criteria,
        requirement_results=results,
        interface_drift=False,
        mutation_score=mutation_score,
        mutation_error=mutation_error,
        assets=[],
        overall=overall,
    )


def _attempt(outcome, error_category=None, surface_ok=True, overall=None, failed=None):
    return {
        "number": 1, "outcome": outcome, "retry_feedback": [],
        "error_category": error_category, "surface_ok": surface_ok,
        "overall": overall, "failed_requirements": failed or [],
        "transcript_sha256": None, "reauthored_tests": [],
    }


def make_closures(model, seed, repo_root, llm_backend=None):
    _log("make_closures", model=model, seed=seed)

    def test_author(bundle):
        return {"model_call_error": None, "file": None}

    def judge(bundle):
        return {"result": "pass", "rationale": None}

    return (test_author, judge)


def run_attempts(component_id, bundle, repo_root, model, *, mode="single", max_attempts=3,
                 retry_feedback=None, seed=0, llm_backend=None,
                 allow_unisolated_exec=False, on_attempt=None):
    _log("run_attempts", component_id=component_id, model=model, seed=seed,
         retry_feedback=retry_feedback, mode=mode, max_attempts=max_attempts)
    ok_surface = Rec(ok=True, findings=[])
    if SCENARIO == "passed":
        gen = _gen(component_id, {"foo.py": "x = 1\\n"}, None, retry_feedback)
        rep = _report(component_id, [{"id": "AC-FOO-001", "covers": "R-FOO-001",
                                      "kind": "compiled", "result": "pass"}], "pass")
        att = _attempt("passed", overall="pass")
        passed, stop, surf = True, "passed", ok_surface
    elif SCENARIO == "model_call_error":
        gen = _gen(component_id, {}, {"category": "empty_response", "message": "no files"},
                   retry_feedback)
        rep = None
        att = _attempt("generation_failed", error_category="empty_response", surface_ok=None)
        passed, stop, surf = False, "max_attempts", None
    elif SCENARIO == "surface_failed":
        gen = _gen(component_id, {"static/a.js": "x"}, None, retry_feedback)
        rep = None
        att = _attempt("surface_failed", surface_ok=False)
        passed, stop = False, "max_attempts"
        surf = Rec(ok=False, findings=[{"kind": "asset_error",
                                        "message": "static/a.js: no interface file"}])
    elif SCENARIO == "test_authoring":
        gen = _gen(component_id, {"foo.py": "x = 1\\n"}, None, retry_feedback)
        rep = _report(component_id, [{
            "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
            "result": "fail", "failure_origin": "test",
            "failure_detail": {"message": "test authoring failed: network: dropped",
                               "expected": None, "actual": None},
        }], "fail")
        att = _attempt("verification_failed", overall="fail")
        passed, stop, surf = False, "max_attempts", ok_surface
    elif SCENARIO == "set_actual":
        gen = _gen(component_id, {"foo.py": "x = 1\\n"}, None, retry_feedback)
        rep = _report(component_id, [{
            "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
            "result": "fail", "failure_origin": "implementation",
            "failure_detail": {"message": "result equals failed",
                               "expected": ["a"], "actual": {"b", "a"}},
        }], "fail")
        att = _attempt("verification_failed", overall="fail", failed=["R-FOO-001"])
        passed, stop, surf = False, "max_attempts", ok_surface
    elif SCENARIO == "mutation_error":
        gen = _gen(component_id, {"foo.py": "x = 1\\n"}, None, retry_feedback)
        rep = _report(component_id, [{
            "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
            "result": "fail", "failure_origin": "implementation",
            "failure_detail": {"message": "m", "expected": 1, "actual": 2},
        }], "fail", mutation_score=None,
            mutation_error="mutation baseline failed in the sandbox: pytest exited 1")
        att = _attempt("verification_failed", overall="fail", failed=["R-FOO-001"])
        passed, stop, surf = False, "max_attempts", ok_surface
    else:
        raise RuntimeError("unknown scenario")
    if on_attempt is not None:
        on_attempt(att, gen, rep)
    return Rec(
        passed=passed,
        stop_reason=stop,
        attempts=[att],
        generation_result=gen,
        verification_report=rep,
        surface_report=surf,
    )
'''


VERIFIER_ORCHESTRATOR = COMMON + '''

GATE_VERSION = "verifier-orchestrator@3.5.0"
DEFAULT_TEST_TIMEOUT = 300.0


def verify(component_id, repo_root, judge=None, test_author=None):
    _log("verify", component_id=component_id)
    return Rec(
        component_id=component_id,
        criteria=[{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
                   "result": "pass"}],
        requirement_results={"R-FOO-001": "pass"},
        interface_drift=False,
        mutation_score=0.9,
        mutation_error=None,
        assets=[],
        overall="pass",
    )


def main(argv=None):
    return 0
'''


PROVENANCE_TRACKER = COMMON + '''

def write_attempt_record(component_id, generation_result, verification_report,
                         spec_bundle_hash, repo_root):
    _log("write_attempt_record", component_id=component_id)
    return {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": component_id,
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": spec_bundle_hash,
        "generation": {},
        "verification": None,
    }


def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):
    _log("check_readiness")
    return {"scope": "whole-corpus", "ready": True, "components": {},
            "capabilities": {}, "not_ready_reasons": []}


def last_requirement_failures(component_id, repo_root):
    _log("last_requirement_failures")
    return []
'''


LICENSE_SCANNER_HEAD = COMMON


LICENSE_SCANNER_BODY = '''

def gate_version(repo_root):
    _log("license_gate_version")
    return "license_scanner@4.0.0-no-reference-corpus"


def scan(component_id, repo_root):
    _log("license_scan", component_id=component_id)
    if EVALUATED:
        return {
            "component_id": component_id,
            "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.1,
            "block_threshold": 0.7,
            "blocked": False,
            "matches": [],
            "notified": False,
            "notification_delivery_error": None,
            "cache_hit": False,
        }
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
'''


SECRET_SCANNER = COMMON + '''

def _result(scope):
    return Rec(
        scope=scope,
        gate_version="secret_scanner@3.1.0+detect-secrets.1.5.0",
        flagged=False,
        matches=[],
        allowed=[],
        unused_allowlist_entries=[],
        notified=False,
        notification_delivery_error=None,
        cache_hit=False,
    )


def scan(repo_root):
    _log("secret_scan")
    return _result("full")


def scan_files(paths, repo_root=None):
    _log("secret_scan_files")
    return _result("precommit")


def gate_version(repo_root):
    _log("secret_gate_version")
    return "secret_scanner@3.1.0+detect-secrets.1.5.0"


def propose(repo_root):
    _log("secret_propose")
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


PROVENANCE_WRITER = COMMON + '''

def write_provenance(component_id, inputs, repo_root):
    _log("write_provenance", component_id=component_id)
    return None


def write_sealed_provenance(component_id, inputs, repo_root):
    _log("write_sealed_provenance", component_id=component_id)
    return None
'''


def write_file(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root, scenario="passed", license_evaluated=True):
    write_file(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n# Foo\n\n## Purpose\n\nA fixture component.\n",
    )
    write_file(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** - Foo MUST work.\n",
    )
    write_file(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n",
    )
    gen = repo_root / "gen"
    write_file(gen / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER)
    write_file(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER)
    write_file(
        gen / "generation-loop" / "generation_loop.py",
        GENERATION_LOOP + "\n\nSCENARIO = " + repr(scenario) + "\n",
    )
    write_file(gen / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_ORCHESTRATOR)
    write_file(gen / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER)
    write_file(
        gen / "license-scanner" / "license_scanner.py",
        LICENSE_SCANNER_HEAD + "\n\nEVALUATED = " + repr(bool(license_evaluated)) + "\n"
        + LICENSE_SCANNER_BODY,
    )
    write_file(gen / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER)
    write_file(gen / "provenance-writer" / "provenance_writer.py", PROVENANCE_WRITER)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def run_text(repo_root, capsys):
    rc = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)]
    )
    out = capsys.readouterr().out
    return rc, out


def test_json_equals_form_and_run_attempts_args(env, capsys):
    repo_root, log_path = env
    build_repo(repo_root, "passed")
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002", "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    doc = json.loads(out)
    assert field(doc, "blocked") is False
    calls = [c for c in read_log(log_path) if c["call"] == "run_attempts"]
    assert len(calls) == 1
    assert calls[0]["model"] == "m"
    assert calls[0]["seed"] == 2
    assert calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_space_separated_form(env, capsys):
    repo_root, log_path = env
    build_repo(repo_root, "passed")
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model", "m", "--repo-root", str(repo_root),
        "--format", "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "comp-foo" in out
    assert "passed" in out
    assert "attempt 1: passed" in out


def test_model_call_error_exit_1(env, capsys):
    repo_root, _ = env
    build_repo(repo_root, "model_call_error")
    rc, out = run_text(repo_root, capsys)
    assert rc == 1
    assert "model_call_error: empty_response: no files" in out


def test_surface_failed_text(env, capsys):
    repo_root, _ = env
    build_repo(repo_root, "surface_failed")
    rc, out = run_text(repo_root, capsys)
    assert rc == 0
    assert "surface_check_failed" in out
    assert "surface: static/a.js: no interface file" in out


def test_test_authoring_failed_exit_1(env, capsys):
    repo_root, _ = env
    build_repo(repo_root, "test_authoring")
    rc, out = run_text(repo_root, capsys)
    assert rc == 1
    assert "test_authoring_failed" in out
    assert "AC-FOO-001: test authoring failed: network: dropped" in out


def test_json_converts_set_actual(env, capsys):
    repo_root, _ = env
    build_repo(repo_root, "set_actual")
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    doc = json.loads(out)
    verification = field(doc, "verification")
    criteria = field(verification, "criteria")
    assert len(criteria) == 1
    assert field(field(criteria[0], "failure_detail"), "actual") == ["a", "b"]


def test_mutation_error_text(env, capsys):
    repo_root, _ = env
    build_repo(repo_root, "mutation_error")
    rc, out = run_text(repo_root, capsys)
    assert rc == 0
    assert "mutation_error: mutation baseline failed in the sandbox: pytest exited 1" in out


def test_license_not_evaluated_text(env, capsys):
    repo_root, _ = env
    build_repo(repo_root, "passed", license_evaluated=False)
    rc, out = run_text(repo_root, capsys)
    assert "license_scan not evaluated: no-reference-corpus" in out


USAGE_CASES = [
    ["generate", "comp-foo"],
    ["generate", "comp-nope", "--model=m"],
    ["generate", "comp-foo", "--model=m", "--seed=x"],
    ["generate", "comp-foo", "--model=m", "--format=bogus"],
    ["generate", "comp-foo", "--model=m", "--hotdocs-smoke-unknown"],
    ["build", "comp-foo", "--model=m"],
    ["generate", "comp-foo", "--model"],
]


@pytest.mark.parametrize("argv", USAGE_CASES)
def test_usage_errors(env, capsys, argv):
    repo_root, log_path = env
    build_repo(repo_root, "passed")
    rc = component_gate_runner.main(list(argv))
    captured = capsys.readouterr()
    assert rc == 2
    lines = captured.err.splitlines()
    assert lines, "expected stderr output"
    assert lines[0].startswith("usage error: ")
    assert read_log(log_path) == []
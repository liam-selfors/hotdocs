# hotdocs-criterion: sha256:b381aa19527f47e308d0b2c25f3593de4efd3065978b50577f145ed3ac4cf0e5
import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# ---------------------------------------------------------------------------
# Fixture building
# ---------------------------------------------------------------------------

HASH = "sha256:" + "a" * 64
PARTS = {"spec": "sha256:" + "b" * 64, "dependency_code": "sha256:" + "c" * 64}
GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@4.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}
ASSETS = [{"kind": "python", "path": ".", "definition_sha256": None,
           "adapter_sha256": "sha256:" + "d" * 64,
           "versions": {"python": "3.12.4"}, "lockfile_sha256": None}]


def gen_result(files=None, model_call_error=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": HASH,
        "model": "m",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": {} if files is None else files,
        "model_call_error": model_call_error,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def ver_report(overall="pass", criteria=None, mutation_score=0.9, mutation_error=None):
    if criteria is None:
        criteria = [{"id": "AC-FOO-001", "covers": "R-FOO-001",
                     "kind": "compiled", "result": "pass"}]
    req = {}
    for c in criteria:
        req[c["covers"]] = "pass" if c["result"] == "pass" else "fail"
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": req,
        "interface_drift": False,
        "mutation_score": mutation_score,
        "mutation_error": mutation_error,
        "assets": ASSETS,
        "drivers": [],
        "overall": overall,
    }


def attempt(outcome, error_category=None, surface_ok=True, overall="pass",
            failed=None):
    return {
        "number": 1,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": [] if failed is None else failed,
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def loop_result(passed, att, generation_result, verification_report,
                surface_report):
    return {
        "passed": passed,
        "stop_reason": "passed" if passed else "max_attempts",
        "attempts": [att],
        "generation_result": generation_result,
        "verification_report": verification_report,
        "surface_report": surface_report,
    }


def passing_loop():
    return loop_result(
        True,
        attempt("passed"),
        gen_result(files={"foo.py": "x = 1\n"}),
        ver_report(),
        {"ok": True, "findings": []},
    )


def license_result(evaluated=True, reason=None):
    return {
        "component_id": "comp-foo",
        "gate_version": ("license_scanner@4.0.0-" + reason) if not evaluated
        else "license_scanner@4.0.3+9f2c41ab07de",
        "evaluated": evaluated,
        "reason": reason,
        "similarity_score": 0.1 if evaluated else None,
        "block_threshold": 0.7 if evaluated else None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def secret_result():
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


def header(log):
    return (
        "import json\n"
        "LOG = " + repr(str(log)) + "\n"
        "def _log(fn, **kw):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'fn': fn, 'args': kw}, default=str) + '\\n')\n"
        "\n"
    )


def write_fake(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


def build_repo(tmp_path, loop=None, verify=None, license_scan=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    if loop is None:
        loop = passing_loop()
    if verify is None:
        verify = ver_report()
    if license_scan is None:
        license_scan = license_result()

    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )

    h = header(log)

    write_fake(repo_root, "provenance-checker", h + (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr(HASH) + "\n"
        "        self.spec_bundle_parts = " + repr(PARTS) + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr(ASSETS) + "\n"
        "        self.drivers = []\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    write_fake(repo_root, "spec-bundle-assembler", h + (
        "def _bundle(component_id):\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': " + repr(HASH) + ",\n"
        "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
        "            'hint_code': None, 'spec_bundle_parts': " + repr(PARTS) + "}\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return _bundle(component_id)\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    write_fake(repo_root, "generation-loop", h + (
        "RESULT = " + repr(loop) + "\n"
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "    'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model, seed=seed,\n"
        "         retry_feedback=retry_feedback, mode=mode, max_attempts=max_attempts)\n"
        "    return RESULT\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))

    write_fake(repo_root, "provenance-tracker", h + (
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id)\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id=component_id)\n"
        "    return []\n"
    ))

    write_fake(repo_root, "verifier-orchestrator", h + (
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "REPORT = " + repr(verify) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return REPORT\n"
    ))

    write_fake(repo_root, "license-scanner", h + (
        "RESULT = " + repr(license_scan) + "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return RESULT\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
    ))

    write_fake(repo_root, "secret-scanner", h + (
        "RESULT = " + repr(secret_result()) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return RESULT\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return dict(RESULT, scope='precommit')\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
        "\n"
        "def propose(repo_root):\n"
        "    _log('propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))

    write_fake(repo_root, "provenance-writer", h + (
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n"
    ))

    return repo_root, log


def read_log(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_json_output_and_flags_reach_run_attempts(tmp_path, capsys):
    repo_root, log = build_repo(tmp_path)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002",
        "--repo-root=" + str(repo_root), "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    assert field(data, "blocked") is False
    calls = [c for c in read_log(log) if c["fn"] == "run_attempts"]
    assert len(calls) == 1
    args = calls[0]["args"]
    assert args["model"] == "m"
    assert args["seed"] == 2
    assert args["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_output_with_space_separated_flags(tmp_path, capsys):
    repo_root, log = build_repo(tmp_path)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model", "m", "--repo-root",
        str(repo_root), "--format", "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "comp-foo" in out
    assert "passed" in out
    assert "attempt 1: passed" in out


def test_model_call_error_exits_1(tmp_path, capsys):
    loop = loop_result(
        False,
        attempt("generation_failed", error_category="empty_response",
                surface_ok=None, overall=None),
        gen_result(model_call_error={"category": "empty_response",
                                     "message": "no files"}),
        None,
        None,
    )
    repo_root, log = build_repo(tmp_path, loop=loop)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "model_call_error: empty_response: no files" in out


def test_surface_failed_prints_findings(tmp_path, capsys):
    loop = loop_result(
        False,
        attempt("surface_failed", surface_ok=False, overall=None),
        gen_result(files={"static/a.js": "console.log(1);\n"}),
        None,
        {"ok": False, "findings": [
            {"kind": "asset_error", "message": "static/a.js: no interface file"}]},
    )
    repo_root, log = build_repo(tmp_path, loop=loop)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "surface_check_failed" in out
    assert "surface: static/a.js: no interface file" in out


def test_test_authoring_failed_exits_1(tmp_path, capsys):
    report = ver_report(overall="fail", criteria=[{
        "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
        "result": "fail", "failure_origin": "test",
        "failure_detail": {"message": "test authoring failed: network: dropped",
                           "expected": None, "actual": None},
    }], mutation_score=None)
    loop = loop_result(
        False,
        attempt("verification_failed", overall="fail", failed=[]),
        gen_result(files={"foo.py": "x = 1\n"}),
        report,
        {"ok": True, "findings": []},
    )
    repo_root, log = build_repo(tmp_path, loop=loop, verify=report)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "test_authoring_failed" in out
    assert "AC-FOO-001: test authoring failed: network: dropped" in out


def test_json_converts_set_actual_to_sorted_list(tmp_path, capsys):
    report = ver_report(overall="fail", criteria=[{
        "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
        "result": "fail", "failure_origin": "implementation",
        "failure_detail": {"message": "result equals set failed",
                           "expected": None, "actual": {"b", "a"}},
    }])
    loop = loop_result(
        False,
        attempt("verification_failed", overall="fail", failed=["R-FOO-001"]),
        gen_result(files={"foo.py": "x = 1\n"}),
        report,
        {"ok": True, "findings": []},
    )
    repo_root, log = build_repo(tmp_path, loop=loop, verify=report)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    data = json.loads(out)
    verification = field(data, "verification")
    criteria = field(verification, "criteria")
    assert criteria[0]["failure_detail"]["actual"] == ["a", "b"]


def test_mutation_error_line(tmp_path, capsys):
    msg = "mutation baseline failed in the sandbox: pytest exited 1"
    report = ver_report(overall="fail", criteria=[{
        "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
        "result": "fail", "failure_origin": "implementation",
        "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2},
    }], mutation_score=None, mutation_error=msg)
    loop = loop_result(
        False,
        attempt("verification_failed", overall="fail", failed=["R-FOO-001"]),
        gen_result(files={"foo.py": "x = 1\n"}),
        report,
        {"ok": True, "findings": []},
    )
    repo_root, log = build_repo(tmp_path, loop=loop, verify=report)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "mutation_error: " + msg in out


def test_license_scan_not_evaluated_line(tmp_path, capsys):
    repo_root, log = build_repo(
        tmp_path,
        license_scan=license_result(evaluated=False, reason="no-reference-corpus"),
    )
    component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert "license_scan not evaluated: no-reference-corpus" in out


USAGE_CASES = [
    ("no_model", lambda r: ["generate", "comp-foo", "--repo-root=" + r]),
    ("unknown_component", lambda r: ["generate", "comp-nope", "--model=m",
                                     "--repo-root=" + r]),
    ("bad_seed", lambda r: ["generate", "comp-foo", "--model=m", "--seed=x",
                            "--repo-root=" + r]),
    ("bad_format", lambda r: ["generate", "comp-foo", "--model=m",
                              "--format=bogus", "--repo-root=" + r]),
    ("unknown_arg", lambda r: ["generate", "comp-foo", "--model=m",
                               "--hotdocs-smoke-unknown", "--repo-root=" + r]),
    ("wrong_first_word", lambda r: ["build", "comp-foo", "--model=m"]),
    ("model_last_no_value", lambda r: ["generate", "comp-foo",
                                       "--repo-root=" + r, "--model"]),
]


@pytest.mark.parametrize("name,make_argv", USAGE_CASES, ids=[c[0] for c in USAGE_CASES])
def test_usage_errors(tmp_path, capsys, monkeypatch, name, make_argv):
    repo_root, log = build_repo(tmp_path)
    monkeypatch.chdir(repo_root)
    rc = component_gate_runner.main(make_argv(str(repo_root)))
    captured = capsys.readouterr()
    assert rc == 2
    lines = captured.err.splitlines()
    assert lines, "expected a usage error on stderr"
    assert lines[0].startswith("usage error: ")
    assert read_log(log) == []
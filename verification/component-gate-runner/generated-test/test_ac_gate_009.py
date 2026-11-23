# hotdocs-criterion: sha256:9613e09792cc8223b14dfdd719386128e884038927a16f040dc71873b7486759
"""AC-GATE-009: main(argv) implements interface/cli.md (R-GATE-009)."""

import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ASSETS = [{"kind": "python", "path": ".", "definition_sha256": None,
           "adapter_sha256": "sha256:" + "b" * 64,
           "versions": {"python": "3.12.4"}, "lockfile_sha256": None}]

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}


def make_report(overall, criteria, mutation_score=0.9, mutation_error=None):
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": {c["covers"]: ("pass" if c["result"] == "pass" else "fail")
                                for c in criteria},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "mutation_error": mutation_error,
        "assets": ASSETS,
        "overall": overall,
    }


PASS_CRITERION = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}


def gen_result(files, model_call_error=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "model": "m",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def attempt(number, outcome, error_category=None, surface_ok=None, overall=None,
            failed_requirements=None):
    return {
        "number": number,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": failed_requirements or [],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def loop_result(passed, attempts, generation_result, verification_report, surface_report=None):
    return {
        "passed": passed,
        "stop_reason": "passed" if passed else "max_attempts",
        "attempts": attempts,
        "generation_result": generation_result,
        "verification_report": verification_report,
        "surface_report": surface_report,
    }


def default_license():
    return {
        "component_id": "comp-foo",
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


def passing_loop():
    return loop_result(True, [attempt(1, "passed", surface_ok=True, overall="pass")],
                       gen_result({"foo.py": "x = 1\n"}),
                       make_report("pass", [PASS_CRITERION]))


def header(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "def _log(name, **data):\n"
        "    data['call'] = name\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(data, default=repr) + '\\n')\n"
    )


def write_module(repo_root, slug, source):
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")


def install_fakes(repo_root, log_path, loop, verify_report=None, license_result=None):
    if verify_report is None:
        verify_report = make_report("pass", [PASS_CRITERION])
    if license_result is None:
        license_result = default_license()
    h = header(log_path)

    write_module(repo_root, "provenance-checker", h + (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr("sha256:" + "a" * 64) + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr(ASSETS) + "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return _Key()\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    write_module(repo_root, "spec-bundle-assembler", h + (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': " + repr("sha256:" + "a" * 64) + ",\n"
        "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {}, 'dependency_usage': {},\n"
        "            'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
        "            'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    write_module(repo_root, "generation-loop", h + (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "LOOP_RESULT = " + repr(loop) + "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model, seed=seed,\n"
        "         retry_feedback=retry_feedback, mode=mode, max_attempts=max_attempts)\n"
        "    return LOOP_RESULT\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))

    write_module(repo_root, "provenance-tracker", h + (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id)\n"
        "    return {'attempt_id': '2026-10-25T14:32:01Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-10-25T14:32:01Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'not_ready_reasons': []}\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id=component_id)\n"
        "    return []\n"
    ))

    write_module(repo_root, "verifier-orchestrator", h + (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "VERIFY_REPORT = " + repr(verify_report) + "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return VERIFY_REPORT\n"
    ))

    write_module(repo_root, "license-scanner", h + (
        "LICENSE_RESULT = " + repr(license_result) + "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return LICENSE_RESULT\n"
        "def gate_version(repo_root):\n"
        "    _log('license_gate_version')\n"
        "    return LICENSE_RESULT['gate_version']\n"
    ))

    write_module(repo_root, "secret-scanner", h + (
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "def _result(scope):\n"
        "    return {'scope': scope, 'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
        "            'flagged': False, 'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
        "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return _result('full')\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return _result('precommit')\n"
        "def gate_version(repo_root):\n"
        "    _log('secret_gate_version')\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "def propose(repo_root):\n"
        "    _log('propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))

    write_module(repo_root, "provenance-writer", h + (
        "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id)\n"
        "    return None\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n"
    ))


def write_component_spec(repo_root):
    d = Path(repo_root) / "specs" / "components" / "foo"
    (d / "requirements").mkdir(parents=True, exist_ok=True)
    (d / "acceptance").mkdir(parents=True, exist_ok=True)
    (d / "interface").mkdir(parents=True, exist_ok=True)
    (d / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
        encoding="utf-8",
    )
    (d / "requirements" / "R-FOO-001.md").write_text(
        "**R-FOO-001** — Foo MUST work.\n", encoding="utf-8")
    (d / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n", encoding="utf-8")
    (d / "interface" / "library.md").write_text("# Library\n\nfoo()\n", encoding="utf-8")


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_component_spec(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.chdir(repo_root)
    return repo_root, log_path


def test_json_output_flags_equals_form(repo, capsys):
    repo_root, log_path = repo
    install_fakes(repo_root, log_path, passing_loop())
    code = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002", "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    assert field(doc, "blocked") is False
    calls = [c for c in read_log(log_path) if c["call"] == "run_attempts"]
    assert len(calls) == 1
    assert calls[0]["model"] == "m"
    assert calls[0]["seed"] == 2
    assert calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_output_next_argument_form(repo, capsys):
    repo_root, log_path = repo
    install_fakes(repo_root, log_path, passing_loop())
    code = component_gate_runner.main([
        "generate", "comp-foo", "--model", "m", "--repo-root", str(repo_root),
        "--format", "text",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "comp-foo" in out
    assert "passed" in out
    assert "attempt 1: passed" in out


def test_model_call_error_text_and_exit_1(repo, capsys):
    repo_root, log_path = repo
    loop = loop_result(
        False,
        [attempt(1, "generation_failed", error_category="empty_response")],
        gen_result({}, {"category": "empty_response", "message": "no files"}),
        None,
    )
    install_fakes(repo_root, log_path, loop)
    code = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert code == 1
    assert "model_call_error: empty_response: no files" in out


def test_surface_failed_text(repo, capsys):
    repo_root, log_path = repo
    surface = {"ok": False, "findings": [
        {"kind": "asset_name_missing", "message": "static/a.js: no interface file"}]}
    loop = loop_result(
        False,
        [attempt(1, "surface_failed", surface_ok=False)],
        gen_result({"foo.py": "x = 1\n"}),
        None,
        surface,
    )
    install_fakes(repo_root, log_path, loop)
    code = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "surface_check_failed" in out
    assert "surface: static/a.js: no interface file" in out


def test_test_authoring_failed_text_and_exit_1(repo, capsys):
    repo_root, log_path = repo
    crit = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
            "result": "fail", "failure_origin": "test",
            "failure_detail": {"message": "test authoring failed: network: dropped",
                               "expected": None, "actual": None}}
    report = make_report("fail", [crit])
    loop = loop_result(
        False,
        [attempt(1, "test_authoring_failed", surface_ok=True, overall="fail")],
        gen_result({"foo.py": "x = 1\n"}),
        report,
        {"ok": True, "findings": []},
    )
    install_fakes(repo_root, log_path, loop, verify_report=report)
    code = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert code == 1
    assert "test_authoring_failed" in out
    assert "AC-FOO-001: test authoring failed: network: dropped" in out


def test_json_converts_set_to_sorted_list(repo, capsys):
    repo_root, log_path = repo
    crit = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
            "result": "fail", "failure_origin": "implementation",
            "failure_detail": {"message": "set equals failed", "expected": ["a"],
                               "actual": {"b", "a"}}}
    report = make_report("fail", [crit])
    loop = loop_result(
        False,
        [attempt(1, "verification_failed", surface_ok=True, overall="fail",
                 failed_requirements=["R-FOO-001"])],
        gen_result({"foo.py": "x = 1\n"}),
        report,
        {"ok": True, "findings": []},
    )
    install_fakes(repo_root, log_path, loop, verify_report=report)
    code = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert code == 0
    doc = json.loads(out)
    verification = field(doc, "verification")
    criteria = field(verification, "criteria")
    assert criteria[0]["failure_detail"]["actual"] == ["a", "b"]


def test_mutation_error_text(repo, capsys):
    repo_root, log_path = repo
    crit = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
            "result": "fail", "failure_origin": "implementation",
            "failure_detail": {"message": "x equals 1 failed", "expected": 1, "actual": 2}}
    report = make_report("fail", [crit], mutation_score=None,
                         mutation_error="mutation baseline failed in the sandbox: pytest exited 1")
    loop = loop_result(
        False,
        [attempt(1, "verification_failed", surface_ok=True, overall="fail",
                 failed_requirements=["R-FOO-001"])],
        gen_result({"foo.py": "x = 1\n"}),
        report,
        {"ok": True, "findings": []},
    )
    install_fakes(repo_root, log_path, loop, verify_report=report)
    code = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "mutation_error: mutation baseline failed in the sandbox: pytest exited 1" in out


def test_license_scan_not_evaluated_text(repo, capsys):
    repo_root, log_path = repo
    lic = {
        "component_id": "comp-foo",
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
    install_fakes(repo_root, log_path, passing_loop(), license_result=lic)
    component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
    ])
    out = capsys.readouterr().out
    assert "license_scan not evaluated: no-reference-corpus" in out


USAGE_CASES = [
    ("no-model", lambda r: ["generate", "comp-foo", "--repo-root=" + r]),
    ("unknown-component", lambda r: ["generate", "comp-nope", "--model=m", "--repo-root=" + r]),
    ("bad-seed", lambda r: ["generate", "comp-foo", "--model=m", "--seed=x", "--repo-root=" + r]),
    ("bad-format", lambda r: ["generate", "comp-foo", "--model=m", "--format=bogus",
                              "--repo-root=" + r]),
    ("unknown-arg", lambda r: ["generate", "comp-foo", "--model=m",
                               "--hotdocs-smoke-unknown", "--repo-root=" + r]),
    ("wrong-first-word", lambda r: ["build", "comp-foo", "--model=m"]),
    ("model-last-no-value", lambda r: ["generate", "comp-foo", "--repo-root=" + r, "--model"]),
]


@pytest.mark.parametrize("name,build_argv", USAGE_CASES, ids=[c[0] for c in USAGE_CASES])
def test_usage_errors(repo, capsys, name, build_argv):
    repo_root, log_path = repo
    install_fakes(repo_root, log_path, passing_loop())
    code = component_gate_runner.main(build_argv(str(repo_root)))
    captured = capsys.readouterr()
    assert code == 2
    lines = captured.err.splitlines()
    assert lines, "expected a usage error on stderr"
    assert lines[0].startswith("usage error: ")
    assert read_log(log_path) == []
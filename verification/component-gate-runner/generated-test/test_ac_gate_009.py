# hotdocs-criterion: sha256:ffac8f26eaba41436545ee70f6fa35c4bcf58248115be6089ba26389101bbba8
import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

LOG_HELPER = (
    "import json\n"
    "def _log(name, payload):\n"
    "    rec = {'call': name}\n"
    "    rec.update(payload)\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps(rec) + '\\n')\n"
)


def make_report(overall, criteria, mutation_score=0.9, mutation_error=None):
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
        "assets": [],
        "overall": overall,
    }


def passing_report():
    return make_report(
        "pass",
        [{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}],
    )


def license_result(evaluated=True, reason=None):
    return {
        "component_id": "comp-foo",
        "gate_version": "license_scanner@4.0.3+9f2c41ab07de"
        if evaluated
        else "license_scanner@4.0.0-" + str(reason),
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


def attempt_entry(outcome, error_category=None, surface_ok=True, overall="pass", failed=None):
    return {
        "number": 1,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": failed or [],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def default_scenario():
    return {
        "passed": True,
        "stop_reason": "passed",
        "attempt": attempt_entry("passed"),
        "files": {"foo.py": "x = 1\n"},
        "model_call_error": None,
        "verification_report": passing_report(),
        "surface_report": {"ok": True, "findings": []},
        "license": license_result(),
    }


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(tmp_path, sc):
    root = tmp_path / "repo"
    root.mkdir()
    log = tmp_path / "calls.log"

    write(
        root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n\n# Foo\n\n## Purpose\n\nA foo.\n",
    )
    write(
        root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — foo MUST work.\n",
    )
    write(
        root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n",
    )

    head = "LOG = " + repr(str(log)) + "\nSC = " + repr(sc) + "\n" + LOG_HELPER

    write(
        root / "gen" / "provenance-checker" / "provenance_checker.py",
        head
        + "class ProvenanceKey:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc'\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = []\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', {})\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', {})\n"
        "    return ProvenanceKey()\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', {})\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', {})\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        head
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', {})\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
        "            'spec': 's', 'interface': 'i', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', {})\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n",
    )

    write(
        root / "gen" / "generation-loop" / "generation_loop.py",
        head
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "    'missing_asset', 'malformed_layout')\n"
        "class AttemptLoopResult:\n"
        "    def __init__(self, passed, stop_reason, attempts, generation_result,\n"
        "                 verification_report, surface_report):\n"
        "        self.passed = passed\n"
        "        self.stop_reason = stop_reason\n"
        "        self.attempts = attempts\n"
        "        self.generation_result = generation_result\n"
        "        self.verification_report = verification_report\n"
        "        self.surface_report = surface_report\n"
        "    def to_dict(self):\n"
        "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
        "                'attempts': self.attempts, 'generation_result': self.generation_result,\n"
        "                'verification_report': self.verification_report,\n"
        "                'surface_report': self.surface_report}\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', {})\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', {'model': model, 'seed': seed,\n"
        "                          'retry_feedback': retry_feedback})\n"
        "    gen = {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
        "           'model': model, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "           'files': SC['files'], 'model_call_error': SC['model_call_error'],\n"
        "           'refused': None, 'retry_feedback': retry_feedback, 'mode': 'single',\n"
        "           'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
        "    attempt = SC['attempt']\n"
        "    if on_attempt is not None:\n"
        "        on_attempt(attempt, gen, SC['verification_report'])\n"
        "    return AttemptLoopResult(SC['passed'], SC['stop_reason'], [attempt], gen,\n"
        "                             SC['verification_report'], SC['surface_report'])\n",
    )

    write(
        root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        head
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', {})\n"
        "    return {'attempt_id': '2026-11-25T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-11-25T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n",
    )

    write(
        root / "gen" / "license-scanner" / "license_scanner.py",
        head
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan', {})\n"
        "    return SC['license']\n"
        "def gate_version(repo_root):\n"
        "    return SC['license']['gate_version']\n",
    )

    write(
        root / "gen" / "secret-scanner" / "secret_scanner.py",
        head
        + "class SecretScanResult:\n"
        "    def __init__(self):\n"
        "        self.scope = 'full'\n"
        "        self.gate_version = 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "        self.flagged = False\n"
        "        self.matches = []\n"
        "        self.allowed = []\n"
        "        self.unused_allowlist_entries = []\n"
        "        self.notified = False\n"
        "        self.notification_delivery_error = None\n"
        "        self.cache_hit = False\n"
        "    def to_dict(self):\n"
        "        return {'scope': self.scope, 'gate_version': self.gate_version,\n"
        "                'flagged': self.flagged, 'matches': self.matches,\n"
        "                'allowed': self.allowed,\n"
        "                'unused_allowlist_entries': self.unused_allowlist_entries,\n"
        "                'notified': self.notified,\n"
        "                'notification_delivery_error': self.notification_delivery_error,\n"
        "                'cache_hit': self.cache_hit}\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan', {})\n"
        "    return SecretScanResult()\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n",
    )

    write(
        root / "gen" / "provenance-writer" / "provenance_writer.py",
        head
        + "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', {})\n"
        "    return None\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', {})\n"
        "    return None\n",
    )

    write(
        root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        head
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', {})\n"
        "    return SC['verification_report']\n",
    )

    return root, log


def read_log(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_json_output_and_run_attempts_arguments(tmp_path, capsys):
    root, log = build_repo(tmp_path, default_scenario())
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--seed=2",
        "--retry-feedback=R-FOO-001,R-FOO-002", "--repo-root=" + str(root),
        "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    doc = json.loads(out)
    assert doc["blocked"] is False
    calls = [c for c in read_log(log) if c["call"] == "run_attempts"]
    assert len(calls) == 1
    assert calls[0]["model"] == "m"
    assert calls[0]["seed"] == 2
    assert calls[0]["retry_feedback"] == ["R-FOO-001", "R-FOO-002"]


def test_text_output_space_separated_flags(tmp_path, capsys):
    root, log = build_repo(tmp_path, default_scenario())
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model", "m", "--repo-root", str(root),
        "--format", "text",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "comp-foo" in out
    assert "passed" in out
    assert "attempt 1: passed" in out


def test_model_call_error_exit_1(tmp_path, capsys):
    sc = default_scenario()
    sc["passed"] = False
    sc["stop_reason"] = "max_attempts"
    sc["attempt"] = attempt_entry("generation_failed", error_category="empty_response",
                                  surface_ok=None, overall=None)
    sc["files"] = {}
    sc["model_call_error"] = {"category": "empty_response", "message": "no files"}
    sc["verification_report"] = None
    sc["surface_report"] = None
    root, log = build_repo(tmp_path, sc)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(root),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "model_call_error: empty_response: no files" in out


def test_surface_failed_text(tmp_path, capsys):
    sc = default_scenario()
    sc["passed"] = False
    sc["stop_reason"] = "max_attempts"
    sc["attempt"] = attempt_entry("surface_failed", surface_ok=False, overall=None)
    sc["files"] = {"foo.py": "x = 1\n"}
    sc["verification_report"] = None
    sc["surface_report"] = {
        "ok": False,
        "findings": [{"kind": "asset_error", "message": "static/a.js: no interface file"}],
    }
    root, log = build_repo(tmp_path, sc)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(root),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "surface_check_failed" in out
    assert "surface: static/a.js: no interface file" in out


def test_test_authoring_failed_exit_1(tmp_path, capsys):
    sc = default_scenario()
    sc["passed"] = False
    sc["stop_reason"] = "max_attempts"
    sc["attempt"] = attempt_entry("verification_failed", overall="fail")
    sc["verification_report"] = make_report("fail", [{
        "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test",
        "result": "fail", "failure_origin": "test",
        "failure_detail": {"message": "test authoring failed: network: dropped",
                           "expected": None, "actual": None},
    }])
    root, log = build_repo(tmp_path, sc)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(root),
    ])
    out = capsys.readouterr().out
    assert rc == 1
    assert "test_authoring_failed" in out
    assert "AC-FOO-001: test authoring failed: network: dropped" in out


def test_json_converts_set_actual(tmp_path, capsys):
    sc = default_scenario()
    sc["passed"] = False
    sc["stop_reason"] = "max_attempts"
    sc["attempt"] = attempt_entry("verification_failed", overall="fail",
                                  failed=["R-FOO-001"])
    sc["verification_report"] = make_report("fail", [{
        "id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
        "result": "fail", "failure_origin": "implementation",
        "failure_detail": {"message": "x failed", "expected": ["a"], "actual": {"b", "a"}},
    }])
    root, log = build_repo(tmp_path, sc)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(root), "--format=json",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    doc = json.loads(out)
    crit = doc["verification"]["criteria"][0]
    assert crit["failure_detail"]["actual"] == ["a", "b"]


def test_mutation_error_text(tmp_path, capsys):
    sc = default_scenario()
    sc["passed"] = False
    sc["stop_reason"] = "max_attempts"
    sc["attempt"] = attempt_entry("verification_failed", overall="fail",
                                  failed=["R-FOO-001"])
    sc["verification_report"] = make_report(
        "fail",
        [{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
          "result": "fail", "failure_origin": "implementation",
          "failure_detail": {"message": "x failed", "expected": 1, "actual": 2}}],
        mutation_score=None,
        mutation_error="mutation baseline failed in the sandbox: pytest exited 1",
    )
    root, log = build_repo(tmp_path, sc)
    rc = component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(root),
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "mutation_error: mutation baseline failed in the sandbox: pytest exited 1" in out


def test_license_not_evaluated_text(tmp_path, capsys):
    sc = default_scenario()
    sc["license"] = license_result(evaluated=False, reason="no-reference-corpus")
    root, log = build_repo(tmp_path, sc)
    component_gate_runner.main([
        "generate", "comp-foo", "--model=m", "--repo-root=" + str(root),
    ])
    out = capsys.readouterr().out
    assert "license_scan not evaluated: no-reference-corpus" in out


USAGE_CASES = [
    lambda r: ["generate", "comp-foo", "--repo-root=" + r],
    lambda r: ["generate", "comp-nope", "--model=m", "--repo-root=" + r],
    lambda r: ["generate", "comp-foo", "--model=m", "--seed=x", "--repo-root=" + r],
    lambda r: ["generate", "comp-foo", "--model=m", "--format=bogus", "--repo-root=" + r],
    lambda r: ["generate", "comp-foo", "--model=m", "--hotdocs-smoke-unknown",
               "--repo-root=" + r],
    lambda r: ["build", "comp-foo", "--model=m", "--repo-root=" + r],
    lambda r: ["generate", "comp-foo", "--repo-root=" + r, "--model"],
]


@pytest.mark.parametrize("make_argv", USAGE_CASES)
def test_usage_errors(tmp_path, capsys, make_argv):
    root, log = build_repo(tmp_path, default_scenario())
    rc = component_gate_runner.main(make_argv(str(root)))
    err = capsys.readouterr().err
    assert rc == 2
    lines = err.splitlines()
    assert lines, "expected stderr output"
    assert lines[0].startswith("usage error: ")
    assert read_log(log) == []
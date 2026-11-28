# hotdocs-criterion: sha256:b61edc2877c2fd82b850328dca145bdfc88a24680662719bdd1f013b66778f31
import json
from pathlib import Path

import pytest

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _log_prelude(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(name, *args, **kwargs):\n"
        "    entry = {'call': name, 'args': [repr(a) for a in args], "
        "'kwargs': dict((k, repr(v)) for k, v in kwargs.items())}\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps(entry) + '\\n')\n"
    )


def _write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


HASH = "sha256:" + "a" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@4.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

SPEC_BUNDLE_PARTS = {"spec": "sha256:" + "b" * 64, "dependency_code": "sha256:" + "c" * 64}

ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:" + "d" * 64,
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]

LICENSE_RESULT = {
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

SECRET_RESULT = {
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


def _generation_result(files=None, model_call_error=None, refused=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": HASH,
        "model": "m1",
        "prompt_version": "v11",
        "cache_hit": False,
        "files": files if files is not None else {},
        "model_call_error": model_call_error,
        "refused": refused,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def _verification_report(criteria):
    req = {}
    for c in criteria:
        prev = req.get(c["covers"])
        if c["result"] == "fail" or prev == "fail":
            req[c["covers"]] = "fail"
        else:
            req[c["covers"]] = "pass"
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": req,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": ASSETS,
        "drivers": [],
        "overall": "fail",
    }


def _fail_criterion(cid, covers, origin):
    return {
        "id": cid,
        "covers": covers,
        "kind": "generated-test",
        "result": "fail",
        "failure_detail": {"message": "assertion failed", "expected": 1, "actual": 2},
        "failure_origin": origin,
    }


def _pass_criterion(cid, covers):
    return {"id": cid, "covers": covers, "kind": "generated-test", "result": "pass"}


def _attempt(outcome, error_category=None, surface_ok=None, overall=None, failed=None):
    return {
        "number": 1,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": failed if failed is not None else [],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def _loop_result(outcome, generation_result, verification_report, surface_report,
                 error_category=None, surface_ok=None, overall=None, failed=None,
                 stop_reason="max_attempts"):
    return {
        "passed": False,
        "stop_reason": stop_reason,
        "attempts": [_attempt(outcome, error_category, surface_ok, overall, failed)],
        "generation_result": generation_result,
        "verification_report": verification_report,
        "surface_report": surface_report,
    }


def _install_fakes(repo_root, log_path, loop_result):
    prelude = _log_prelude(log_path)

    _write_fake(repo_root, "provenance-checker", prelude + (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr(HASH) + "\n"
        "        self.spec_bundle_parts = " + repr(SPEC_BUNDLE_PARTS) + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr(ASSETS) + "\n"
        "        self.drivers = []\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id, repo_root)\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id, repo_root)\n"
        "    return _Key()\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None, "
        "'license_scan': None, 'secret_scan': None}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id, repo_root)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None, "
        "'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": HASH,
        "spec": "spec",
        "interface": "interface",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
        "spec_bundle_parts": SPEC_BUNDLE_PARTS,
    }
    criterion_bundle = {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "",
        "requirement_text": "",
        "interface": "",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
    _write_fake(repo_root, "spec-bundle-assembler", prelude + (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id, repo_root=repo_root, mode=mode)\n"
        "    return " + repr(bundle) + "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id, criterion_id, repo_root)\n"
        "    return " + repr(criterion_bundle) + "\n"
    ))

    _write_fake(repo_root, "generation-loop", prelude + (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response', "
        "'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file', 'missing_asset', 'malformed_layout')\n"
        "RESULT = " + repr(loop_result) + "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3, "
        "retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id, repo_root, model, mode=mode, max_attempts=max_attempts)\n"
        "    return RESULT\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model, seed, repo_root, llm_backend)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))

    _write_fake(repo_root, "provenance-tracker", prelude + (
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id, spec_bundle_hash, repo_root)\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id, "
        "'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash, "
        "'generation': {}, 'verification': None}\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness', repo_root)\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {}, "
        "'secret_scan': None, 'not_ready_reasons': []}\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id, repo_root)\n"
        "    return []\n"
    ))

    sealed_report = _verification_report([_pass_criterion("AC-FOO-001", "R-FOO-001")])
    sealed_report["overall"] = "pass"
    _write_fake(repo_root, "verifier-orchestrator", prelude + (
        "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id, repo_root)\n"
        "    return " + repr(sealed_report) + "\n"
    ))

    _write_fake(repo_root, "license-scanner", prelude + (
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id, repo_root)\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(LICENSE_RESULT["gate_version"]) + "\n"
    ))

    _write_fake(repo_root, "secret-scanner", prelude + (
        "def scan(repo_root):\n"
        "    _log('secret_scan', repo_root)\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files', paths, repo_root)\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(SECRET_RESULT["gate_version"]) + "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))

    _write_fake(repo_root, "provenance-writer", prelude + (
        "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id, repo_root)\n"
        "    return None\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id, repo_root)\n"
        "    return None\n"
    ))


def _calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line)["call"] for line in log_path.read_text().splitlines() if line.strip()]


def _case(outcome):
    if outcome == "generation_failed":
        gen = _generation_result(model_call_error={"category": "network", "message": "boom"})
        return _loop_result(outcome, gen, None, None, error_category="network",
                            stop_reason="not_retried")
    if outcome == "surface_failed":
        gen = _generation_result(files={"foo.py": "x = 1\n"})
        surface = {"ok": False, "findings": [{"kind": "import_error", "message": "cannot import foo"}]}
        return _loop_result(outcome, gen, None, surface, surface_ok=False)
    if outcome == "verification_failed":
        gen = _generation_result(files={"foo.py": "x = 1\n"})
        report = _verification_report([_fail_criterion("AC-FOO-001", "R-FOO-001", "implementation")])
        surface = {"ok": True, "findings": []}
        return _loop_result(outcome, gen, report, surface, surface_ok=True, overall="fail",
                            failed=["R-FOO-001"])
    if outcome == "refused":
        gen = _generation_result(refused="spec forbids generation")
        return _loop_result(outcome, gen, None, None, stop_reason="refused")
    raise AssertionError(outcome)


@pytest.mark.parametrize(
    "outcome,reason",
    [
        ("generation_failed", "model_call_error"),
        ("surface_failed", "surface_check_failed"),
        ("verification_failed", "verification_failed"),
        ("refused", "refused"),
    ],
)
def test_failed_loop_blocks_with_reason_from_last_outcome(tmp_path, outcome, reason):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _install_fakes(repo_root, log_path, _case(outcome))

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")

    assert "run_attempts" in _calls(log_path)
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == reason


def test_verification_failed_with_only_test_origin_failures_is_test_authoring_failed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    gen = _generation_result(files={"foo.py": "x = 1\n"})
    report = _verification_report([
        _fail_criterion("AC-FOO-001", "R-FOO-001", "test"),
        _pass_criterion("AC-FOO-002", "R-FOO-002"),
    ])
    surface = {"ok": True, "findings": []}
    loop = _loop_result("verification_failed", gen, report, surface, surface_ok=True,
                        overall="fail", failed=[])
    _install_fakes(repo_root, log_path, loop)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")

    assert "run_attempts" in _calls(log_path)
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "test_authoring_failed"
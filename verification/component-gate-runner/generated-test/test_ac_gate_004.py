# hotdocs-criterion: sha256:bd113c5030dc86faec2bf1ead2b56e88101942abab6e8af0f6e5367ff6a83fd0
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import os\n"
    "def _log(name):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(name + '\\n')\n"
)


def write_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (module_name + ".py")).write_text(source)


def make_gen(files, model_call_error, refused):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:abc123",
        "model": "m0",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": refused,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def make_report(criteria):
    requirement_results = {}
    for c in criteria:
        requirement_results[c["covers"]] = "fail" if c["result"] == "fail" else "pass"
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": requirement_results,
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:00",
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "overall": "fail",
    }


def failed_criterion(cid, covers, origin):
    return {
        "id": cid,
        "covers": covers,
        "kind": "generated-test",
        "result": "fail",
        "failure_detail": {"message": "check failed", "expected": 1, "actual": 2},
        "failure_origin": origin,
    }


def passed_criterion(cid, covers):
    return {"id": cid, "covers": covers, "kind": "generated-test", "result": "pass"}


def make_attempt(outcome, error_category, surface_ok, overall, failed_requirements):
    return {
        "number": 1,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": failed_requirements,
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def make_loop_result(outcome, stop_reason, generation_result, verification_report,
                     surface_report, attempt):
    return {
        "passed": False,
        "stop_reason": stop_reason,
        "attempts": [attempt],
        "generation_result": generation_result,
        "verification_report": verification_report,
        "surface_report": surface_report,
    }


def scenario(outcome):
    files = {"foo.py": "X = 1\n"}
    impl_report = make_report([failed_criterion("AC-FOO-001", "R-FOO-001", "implementation")])
    if outcome == "generation_failed":
        gen = make_gen({}, {"category": "network", "message": "connection reset"}, None)
        attempt = make_attempt("generation_failed", "network", None, None, [])
        return make_loop_result(outcome, "not_retried", gen, None, None, attempt)
    if outcome == "surface_failed":
        gen = make_gen(files, None, None)
        surface = {"ok": False, "findings": [{"kind": "import_error", "message": "cannot import"}]}
        attempt = make_attempt("surface_failed", None, False, None, [])
        return make_loop_result(outcome, "max_attempts", gen, None, surface, attempt)
    if outcome == "verification_failed":
        gen = make_gen(files, None, None)
        surface = {"ok": True, "findings": []}
        attempt = make_attempt("verification_failed", None, True, "fail", ["R-FOO-001"])
        return make_loop_result(outcome, "max_attempts", gen, impl_report, surface, attempt)
    if outcome == "refused":
        gen = make_gen({}, None, "spec asks for disallowed content")
        attempt = make_attempt("refused", None, None, None, [])
        return make_loop_result(outcome, "refused", gen, None, None, attempt)
    raise AssertionError(outcome)


def build_fakes(repo_root, loop_result):
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@3.5.0",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v1",
    }
    assets = [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": "sha256:00",
            "adapter_sha256": "sha256:00",
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ]
    miss = {
        "hit": False,
        "reason": "no manifest",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
    sealed_miss = {
        "hit": False,
        "sealed": False,
        "reason": "not_sealed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
        "owners": None,
        "source_hash": None,
        "written_at": None,
    }
    write_module(
        repo_root,
        "provenance-checker",
        LOG_HELPER
        + "import types\n"
        + "def current_sealed_key(component_id, repo_root):\n"
        + "    _log('current_sealed_key')\n"
        + "    return None\n"
        + "def current_provenance_key(component_id, repo_root):\n"
        + "    _log('current_provenance_key')\n"
        + "    return types.SimpleNamespace(spec_bundle_hash="
        + repr("sha256:abc123")
        + ", gate_versions="
        + repr(gate_versions)
        + ", assets="
        + repr(assets)
        + ")\n"
        + "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        + "    _log('check_provenance')\n"
        + "    return "
        + repr(miss)
        + "\n"
        + "def check_sealed_provenance(component_id, repo_root):\n"
        + "    _log('check_sealed_provenance')\n"
        + "    return "
        + repr(sealed_miss)
        + "\n",
    )
    bundle = {
        "component_id": "comp-foo",
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
    write_module(
        repo_root,
        "spec-bundle-assembler",
        LOG_HELPER
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        + "    _log('assemble')\n"
        + "    return "
        + repr(bundle)
        + "\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    _log('assemble_criterion')\n"
        + "    raise AssertionError('not expected')\n",
    )
    write_module(
        repo_root,
        "generation-loop",
        LOG_HELPER
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        + "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        + "    'missing_asset', 'malformed_layout')\n"
        + "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        + "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        + "                 allow_unisolated_exec=False, on_attempt=None):\n"
        + "    _log('run_attempts')\n"
        + "    return "
        + repr(loop_result)
        + "\n"
        + "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        + "    _log('make_closures')\n"
        + "    def test_author(bundle):\n"
        + "        return {'model_call_error': None, 'file': None}\n"
        + "    def judge(bundle):\n"
        + "        return {'result': 'pass', 'rationale': None}\n"
        + "    return (test_author, judge)\n",
    )
    attempt_record = {
        "attempt_id": "2026-10-25T14:32:01Z-a1b2c3",
        "component_id": "comp-foo",
        "timestamp": "2026-10-25T14:32:01Z",
        "spec_bundle_hash": "sha256:abc123",
        "generation": {},
        "verification": None,
    }
    write_module(
        repo_root,
        "provenance-tracker",
        LOG_HELPER
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        + "                         spec_bundle_hash, repo_root):\n"
        + "    _log('write_attempt_record')\n"
        + "    return "
        + repr(attempt_record)
        + "\n",
    )
    pass_report = make_report([passed_criterion("AC-FOO-001", "R-FOO-001")])
    pass_report["overall"] = "pass"
    write_module(
        repo_root,
        "verifier-orchestrator",
        LOG_HELPER
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        + "DEFAULT_TEST_TIMEOUT = 300.0\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    _log('verify')\n"
        + "    return "
        + repr(pass_report)
        + "\n",
    )
    license_result = {
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
    write_module(
        repo_root,
        "license-scanner",
        LOG_HELPER
        + "def scan(component_id, repo_root):\n"
        + "    _log('license_scan')\n"
        + "    return "
        + repr(license_result)
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    return "
        + repr(license_result["gate_version"])
        + "\n",
    )
    secret_result = {
        "scope": "full",
        "gate_version": "secret_scanner@0.0.0",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
    write_module(
        repo_root,
        "secret-scanner",
        LOG_HELPER
        + "def scan(repo_root):\n"
        + "    _log('secret_scan')\n"
        + "    return "
        + repr(secret_result)
        + "\n"
        + "def scan_files(paths, repo_root=None):\n"
        + "    _log('scan_files')\n"
        + "    return "
        + repr(secret_result)
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    return 'secret_scanner@0.0.0'\n"
        + "def propose(repo_root):\n"
        + "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )
    write_module(
        repo_root,
        "provenance-writer",
        LOG_HELPER
        + "def write_provenance(component_id, inputs, repo_root):\n"
        + "    _log('write_provenance')\n"
        + "    return None\n"
        + "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        + "    _log('write_sealed_provenance')\n"
        + "    return None\n",
    )


def run(tmp_path, monkeypatch, loop_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_fakes(repo_root, loop_result)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m0")
    calls = log_path.read_text().split()
    assert "run_attempts" in calls
    assert "check_provenance" in calls
    return result


@pytest.mark.parametrize(
    "outcome, reason",
    [
        ("generation_failed", "model_call_error"),
        ("surface_failed", "surface_check_failed"),
        ("verification_failed", "verification_failed"),
        ("refused", "refused"),
    ],
)
def test_block_reason_from_last_attempt_outcome(tmp_path, monkeypatch, outcome, reason):
    result = run(tmp_path, monkeypatch, scenario(outcome))
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == reason


def test_all_failures_test_origin_gives_test_authoring_failed(tmp_path, monkeypatch):
    report = make_report(
        [
            failed_criterion("AC-FOO-001", "R-FOO-001", "test"),
            passed_criterion("AC-FOO-002", "R-FOO-002"),
        ]
    )
    gen = make_gen({"foo.py": "X = 1\n"}, None, None)
    surface = {"ok": True, "findings": []}
    attempt = make_attempt("verification_failed", None, True, "fail", ["R-FOO-001"])
    loop_result = make_loop_result(
        "verification_failed", "max_attempts", gen, report, surface, attempt
    )
    result = run(tmp_path, monkeypatch, loop_result)
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "test_authoring_failed"
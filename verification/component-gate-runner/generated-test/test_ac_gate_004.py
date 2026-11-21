# hotdocs-criterion: sha256:c897ea814e83425df9f70b7e9e9c6d54411370e260567860210f1d2417a77bb3
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_AC004_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


LOG_HELPER = (
    "import os\n"
    "\n"
    "def _log(name):\n"
    "    p = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    if p:\n"
    "        with open(p, 'a', encoding='utf-8') as f:\n"
    "            f.write(name + '\\n')\n"
    "\n"
)

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:00",
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


def _verification_report(criteria, overall):
    return {
        "component_id": "comp-foo",
        "criteria": criteria,
        "requirement_results": {
            c["covers"]: ("pass" if c["result"] == "pass" else "fail") for c in criteria
        },
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": ASSETS,
        "overall": overall,
    }


def _generation_result(files=None, model_call_error=None, refused=None):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:abc",
        "model": "m1",
        "prompt_version": "v12",
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


def _write_fakes(repo_root, loop_result):
    gen = repo_root / "gen"

    _write(
        gen / "provenance-checker" / "provenance_checker.py",
        LOG_HELPER
        + "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr("sha256:abc") + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr(ASSETS) + "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key')\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key')\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance')\n"
        "    return " + repr({
            "hit": False,
            "reason": "no manifest",
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
        }) + "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance')\n"
        "    return " + repr({
            "hit": False,
            "sealed": False,
            "reason": "not_sealed",
            "verification_report": None,
            "license_scan": None,
            "secret_scan": None,
            "owners": None,
            "source_hash": None,
            "written_at": None,
        }) + "\n",
    )

    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:abc",
        "spec": "",
        "interface": "",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
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
    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        LOG_HELPER
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return " + repr(bundle) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    return " + repr(criterion_bundle) + "\n",
    )

    _write(
        gen / "generation-loop" / "generation_loop.py",
        LOG_HELPER
        + "RETRIED_CATEGORIES = " + repr((
            "truncated_response", "missing_module", "empty_response",
            "agent_budget_exhausted", "agent_unfinished", "undecodable_file",
            "missing_asset", "malformed_layout",
        )) + "\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    return " + repr(loop_result) + "\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return " + repr({"file": None, "model_call_error": None}) + "\n"
        "    def judge(bundle):\n"
        "        return " + repr({"result": "pass", "rationale": None}) + "\n"
        "    return (test_author, judge)\n",
    )

    _write(
        gen / "provenance-tracker" / "provenance_tracker.py",
        LOG_HELPER
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    return {\n"
        "        'attempt_id': " + repr("2026-01-01T00:00:00Z-aaaaaa") + ",\n"
        "        'component_id': component_id,\n"
        "        'timestamp': " + repr("2026-01-01T00:00:00Z") + ",\n"
        "        'spec_bundle_hash': spec_bundle_hash,\n"
        "        'generation': " + repr({}) + ",\n"
        "        'verification': None,\n"
        "    }\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return " + repr({
            "scope": "whole-corpus",
            "ready": True,
            "components": {},
            "capabilities": {},
            "not_ready_reasons": [],
        }) + "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n",
    )

    _write(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        LOG_HELPER
        + "GATE_VERSION = " + repr("verifier-orchestrator@3.5.0") + "\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify')\n"
        "    return " + repr(_verification_report(
            [{"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}],
            "pass",
        )) + "\n",
    )

    _write(
        gen / "license-scanner" / "license_scanner.py",
        LOG_HELPER
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan')\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(LICENSE_RESULT["gate_version"]) + "\n",
    )

    _write(
        gen / "secret-scanner" / "secret_scanner.py",
        LOG_HELPER
        + "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(SECRET_RESULT["gate_version"]) + "\n"
        "\n"
        "def propose(repo_root):\n"
        "    return " + repr({"allowlist": {"version": 1, "entries": []}, "ineligible": []}) + "\n",
    )

    _write(
        gen / "provenance-writer" / "provenance_writer.py",
        LOG_HELPER
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance')\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance')\n"
        "    return None\n",
    )


def _implementation_fail_report():
    return _verification_report(
        [{
            "id": "AC-FOO-001",
            "covers": "R-FOO-001",
            "kind": "compiled",
            "result": "fail",
            "failure_origin": "implementation",
            "failure_detail": {"message": "result.foo equals 5 failed", "expected": 5, "actual": 3},
        }],
        "fail",
    )


MODEL_CALL_ERROR = {"category": "truncated_response", "message": "reply was cut off"}


def _loop_for(outcome):
    if outcome == "generation_failed":
        gen_result = _generation_result(model_call_error=MODEL_CALL_ERROR)
        attempt = _attempt("generation_failed", error_category="truncated_response")
        report = None
        stop = "max_attempts"
    elif outcome == "surface_failed":
        gen_result = _generation_result(files={"foo.py": "x = 1\n"})
        attempt = _attempt("surface_failed", surface_ok=False)
        report = None
        stop = "max_attempts"
    elif outcome == "verification_failed":
        gen_result = _generation_result(files={"foo.py": "x = 1\n"})
        attempt = _attempt("verification_failed", surface_ok=True, overall="fail",
                           failed=["R-FOO-001"])
        report = _implementation_fail_report()
        stop = "max_attempts"
    elif outcome == "refused":
        gen_result = _generation_result(refused="spec asks for prohibited content")
        attempt = _attempt("refused")
        report = None
        stop = "refused"
    else:
        raise AssertionError(outcome)
    surface = None
    if outcome in ("surface_failed", "verification_failed"):
        surface = {
            "ok": outcome != "surface_failed",
            "findings": [] if outcome != "surface_failed" else [
                {"kind": "import_error", "message": "cannot import foo"}
            ],
        }
    return {
        "passed": False,
        "stop_reason": stop,
        "attempts": [attempt],
        "generation_result": gen_result,
        "verification_report": report,
        "surface_report": surface,
    }


def _run(tmp_path, monkeypatch, loop_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log))
    _write_fakes(repo_root, loop_result)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m1")
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, calls


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
    result, calls = _run(tmp_path, monkeypatch, _loop_for(outcome))

    assert "run_attempts" in calls
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == reason
    if reason == "model_call_error":
        assert field(result, "model_call_error") == MODEL_CALL_ERROR
    else:
        assert field(result, "model_call_error") is None


def test_verification_failed_with_only_test_origin_fails_is_test_authoring_failed(
    tmp_path, monkeypatch
):
    report = _verification_report(
        [
            {
                "id": "AC-FOO-001",
                "covers": "R-FOO-001",
                "kind": "generated-test",
                "result": "fail",
                "failure_origin": "test",
                "failure_detail": {"message": "no test could be written",
                                   "expected": None, "actual": None},
            },
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "fail",
    )
    loop_result = {
        "passed": False,
        "stop_reason": "max_attempts",
        "attempts": [_attempt("verification_failed", surface_ok=True, overall="fail",
                              failed=["R-FOO-001"])],
        "generation_result": _generation_result(files={"foo.py": "x = 1\n"}),
        "verification_report": report,
        "surface_report": {"ok": True, "findings": []},
    }

    result, calls = _run(tmp_path, monkeypatch, loop_result)

    assert "run_attempts" in calls
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "test_authoring_failed"
    assert field(result, "model_call_error") is None
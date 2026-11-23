# hotdocs-criterion: sha256:28c73c55f1c8f1071d5dd8261eba853d763f0a9ee722c03440fb5b5283ba74ed
import os
from pathlib import Path

import pytest

import component_gate_runner


COMPONENT_ID = "comp-foo"
LOG_ENV = "GATE_TEST_LOG_AC_GATE_004"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import os\n"
    "\n"
    "def _log(name):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as handle:\n"
    "        handle.write(name + '\\n')\n"
    "\n"
)


def write_module(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    directory = Path(repo_root) / "gen" / slug
    directory.mkdir(parents=True, exist_ok=True)
    (directory / (module_name + ".py")).write_text(source)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

SPEC_BUNDLE_HASH = "sha256:abc123"

LICENSE_SCAN = {
    "component_id": COMPONENT_ID,
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

SECRET_SCAN = {
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


def generation_result(files=None, model_call_error=None, refused=None):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model": "m-test",
        "prompt_version": "v1",
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


def verification_report(criteria):
    requirement_results = {}
    for c in criteria:
        prior = requirement_results.get(c["covers"])
        if c["result"] == "fail" or prior == "fail":
            requirement_results[c["covers"]] = "fail"
        else:
            requirement_results[c["covers"]] = c["result"]
    overall = "fail" if any(c["result"] == "fail" for c in criteria) else "pass"
    return {
        "component_id": COMPONENT_ID,
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
        "overall": overall,
    }


def failed_criterion(criterion_id, covers, origin):
    return {
        "id": criterion_id,
        "covers": covers,
        "kind": "generated-test",
        "result": "fail",
        "failure_detail": {"message": "check failed", "expected": 1, "actual": 2},
        "failure_origin": origin,
    }


def passed_criterion(criterion_id, covers):
    return {"id": criterion_id, "covers": covers, "kind": "compiled", "result": "pass"}


def attempt(number, outcome, surface_ok=None, overall=None, error_category=None,
            failed_requirements=None):
    return {
        "number": number,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": failed_requirements if failed_requirements is not None else [],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def first_attempt_other_than(outcome):
    # An earlier attempt with a different outcome, so only the last one decides.
    if outcome == "surface_failed":
        return attempt(1, "verification_failed", surface_ok=True, overall="fail",
                       failed_requirements=["R-FOO-001"])
    return attempt(1, "surface_failed", surface_ok=False)


def scenario_for(outcome, verification_origin="implementation", with_second_pass=False):
    surface_bad = {"ok": False, "findings": [{"kind": "import_error", "message": "no module"}]}
    surface_ok = {"ok": True, "findings": []}
    if outcome == "generation_failed":
        gen = generation_result(model_call_error={"category": "network", "message": "boom"})
        report = None
        surface = surface_bad
        last = attempt(2, "generation_failed", error_category="network")
    elif outcome == "refused":
        gen = generation_result(refused="not allowed")
        report = None
        surface = surface_bad
        last = attempt(2, "refused")
    elif outcome == "surface_failed":
        gen = generation_result(files={"foo.py": "X = 1\n"})
        report = verification_report([failed_criterion("AC-FOO-001", "R-FOO-001", "implementation")])
        surface = surface_bad
        last = attempt(2, "surface_failed", surface_ok=False)
    elif outcome == "verification_failed":
        gen = generation_result(files={"foo.py": "X = 1\n"})
        criteria = [failed_criterion("AC-FOO-001", "R-FOO-001", verification_origin)]
        if with_second_pass:
            criteria.append(passed_criterion("AC-FOO-002", "R-FOO-002"))
        report = verification_report(criteria)
        surface = surface_ok
        failed = ["R-FOO-001"] if verification_origin == "implementation" else []
        last = attempt(2, "verification_failed", surface_ok=True, overall="fail",
                       failed_requirements=failed)
    else:
        raise AssertionError("unknown outcome " + outcome)
    # surface_report is the last one made; for generation failures the
    # earlier attempt's surface report remains the last one made.
    return {
        "passed": False,
        "stop_reason": "max_attempts",
        "attempts": [first_attempt_other_than(outcome), last],
        "generation_result": gen,
        "verification_report": report,
        "surface_report": surface,
    }


def build_repo(repo_root, loop_result):
    write_module(repo_root, "provenance-checker", LOG_HELPER + (
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr(SPEC_BUNDLE_HASH) + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,"
        " 'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},"
        " 'lockfile_sha256': None}]\n"
        "    def __getitem__(self, name):\n"
        "        return getattr(self, name)\n"
        "    def get(self, name, default=None):\n"
        "        return getattr(self, name, default)\n"
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
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,"
        " 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance')\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',"
        " 'verification_report': None, 'license_scan': None, 'secret_scan': None,"
        " 'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    write_module(repo_root, "spec-bundle-assembler", LOG_HELPER + (
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': "
        + repr(SPEC_BUNDLE_HASH) + ", 'spec': '', 'interface': '', 'constraints': '',"
        " 'dependency_interfaces': {}, 'dependency_context': {}, 'dependency_usage': {},"
        " 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,"
        " 'covers': '', 'criterion_text': '', 'requirement_text': '', 'interface': '',"
        " 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    write_module(repo_root, "generation-loop", LOG_HELPER + (
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',"
        " 'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',"
        " 'missing_asset', 'malformed_layout')\n"
        "\n"
        "LOOP_RESULT = " + repr(loop_result) + "\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',"
        " max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,"
        " allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    return LOOP_RESULT\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    ))

    write_module(repo_root, "provenance-tracker", LOG_HELPER + (
        "def write_attempt_record(component_id, generation_result, verification_report,"
        " spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,"
        " 'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,"
        " 'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},"
        " 'capabilities': {}, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    ))

    write_module(repo_root, "verifier-orchestrator", LOG_HELPER + (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify')\n"
        "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},"
        " 'interface_drift': False, 'mutation_score': None, 'mutation_error': None,"
        " 'assets': [], 'overall': 'pass'}\n"
    ))

    write_module(repo_root, "license-scanner", LOG_HELPER + (
        "RESULT = " + repr(LICENSE_SCAN) + "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan')\n"
        "    return dict(RESULT)\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
    ))

    write_module(repo_root, "secret-scanner", LOG_HELPER + (
        "RESULT = " + repr(SECRET_SCAN) + "\n"
        "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return dict(RESULT)\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    result = dict(RESULT)\n"
        "    result['scope'] = 'precommit'\n"
        "    return result\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))

    write_module(repo_root, "provenance-writer", LOG_HELPER + (
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance')\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance')\n"
        "    return None\n"
    ))


def run(tmp_path, monkeypatch, loop_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_repo(repo_root, loop_result)
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")
    calls = [line for line in log_path.read_text().splitlines() if line]
    assert "run_attempts" in calls, calls
    assert "check_provenance" in calls, calls
    return result


@pytest.mark.parametrize(
    "outcome,reason",
    [
        ("generation_failed", "model_call_error"),
        ("surface_failed", "surface_check_failed"),
        ("verification_failed", "verification_failed"),
        ("refused", "refused"),
    ],
)
def test_block_reason_follows_last_attempt_outcome(tmp_path, monkeypatch, outcome, reason):
    loop_result = scenario_for(outcome, verification_origin="implementation")
    result = run(tmp_path, monkeypatch, loop_result)
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == reason


def test_verification_failed_with_only_test_origin_failures_is_test_authoring_failed(
    tmp_path, monkeypatch
):
    loop_result = scenario_for(
        "verification_failed", verification_origin="test", with_second_pass=True
    )
    result = run(tmp_path, monkeypatch, loop_result)
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "test_authoring_failed"
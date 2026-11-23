# hotdocs-criterion: sha256:0733621ddcd13d31e459b9fbf1d844e6d76f307c1f26b1ab3e0c476e652b28b0
import json
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_AC008_LOG"

COMPONENT_ID = "comp-foo"

G1 = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:k",
    "model": "m-test",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {},
    "model_call_error": {"category": "truncated_response", "message": "g1 truncated"},
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

G2 = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:k",
    "model": "m-test",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {"foo.py": "VALUE = 2\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

R2 = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:aa",
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "overall": "pass",
}

ATTEMPT1 = {
    "number": 1,
    "outcome": "generation_failed",
    "retry_feedback": [],
    "error_category": "truncated_response",
    "surface_ok": None,
    "overall": None,
    "failed_requirements": [],
    "transcript_sha256": None,
    "reauthored_tests": [],
}

ATTEMPT2 = {
    "number": 2,
    "outcome": "passed",
    "retry_feedback": [],
    "error_category": None,
    "surface_ok": True,
    "overall": "pass",
    "failed_requirements": [],
    "transcript_sha256": None,
    "reauthored_tests": [],
}

SURFACE2 = {"ok": True, "findings": []}

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

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as fh:\n"
    "        fh.write(json.dumps({'fn': fn, 'args': kw}, default=str) + '\\n')\n"
    "\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


def provenance_checker_source():
    return (
        LOG_HELPER
        + "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
        "    return ProvenanceKey(" + repr("sha256:k") + ", " + repr(GATE_VERSIONS) + ", "
        + repr([{"kind": "python", "path": ".", "definition_sha256": None,
                 "adapter_sha256": "sha256:aa", "versions": {"python": "3.12.4"},
                 "lockfile_sha256": None}]) + ")\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions, repo_root=repo_root)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None, 'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


def spec_bundle_assembler_source():
    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
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
    return (
        LOG_HELPER
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, repo_root=repo_root, mode=mode)\n"
        "    return " + repr(bundle) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id, repo_root=repo_root)\n"
        "    return " + repr(criterion_bundle) + "\n"
    )


def generation_loop_source(two_attempts):
    if two_attempts:
        calls = (
            "    if on_attempt is not None:\n"
            "        on_attempt(ATTEMPT1, G1, None)\n"
            "        on_attempt(ATTEMPT2, G2, R2)\n"
        )
        attempts_expr = "[ATTEMPT1, ATTEMPT2]"
    else:
        calls = (
            "    if on_attempt is not None:\n"
            "        on_attempt(ATTEMPT2, G2, R2)\n"
        )
        attempts_expr = "[ATTEMPT2]"
    return (
        LOG_HELPER
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response', "
        "'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file', 'missing_asset', 'malformed_layout')\n"
        "\n"
        "G1 = " + repr(G1) + "\n"
        "G2 = " + repr(G2) + "\n"
        "R2 = " + repr(R2) + "\n"
        "ATTEMPT1 = " + repr(ATTEMPT1) + "\n"
        "ATTEMPT2 = " + repr(ATTEMPT2) + "\n"
        "SURFACE2 = " + repr(SURFACE2) + "\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed, repo_root=repo_root)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        "                 on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, repo_root=repo_root, model=model, mode=mode, max_attempts=max_attempts)\n"
        + calls
        + "    return {\n"
        "        'passed': True,\n"
        "        'stop_reason': 'passed',\n"
        "        'attempts': " + attempts_expr + ",\n"
        "        'generation_result': G2,\n"
        "        'verification_report': R2,\n"
        "        'surface_report': SURFACE2,\n"
        "    }\n"
    )


def provenance_tracker_source(raises):
    if raises:
        body = "    raise RuntimeError('attempt record write failed')\n"
    else:
        body = (
            "    return {\n"
            "        'attempt_id': '2026-10-25T14:32:01Z-a1b2c3',\n"
            "        'component_id': component_id,\n"
            "        'timestamp': '2026-10-25T14:32:01Z',\n"
            "        'spec_bundle_hash': spec_bundle_hash,\n"
            "        'generation': json.loads(json.dumps(generation_result, default=str)),\n"
            "        'verification': json.loads(json.dumps(verification_report, default=str)),\n"
            "    }\n"
        )
    return (
        LOG_HELPER
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id, generation_result=generation_result,\n"
        "         verification_report=verification_report, spec_bundle_hash=spec_bundle_hash, repo_root=repo_root)\n"
        + body
        + "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {}, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )


def verifier_orchestrator_source():
    return (
        LOG_HELPER
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id, repo_root=repo_root)\n"
        "    return " + repr(R2) + "\n"
    )


def license_scanner_source():
    return (
        LOG_HELPER
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id, repo_root=repo_root)\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    )


def secret_scanner_source():
    return (
        LOG_HELPER
        + "def scan(repo_root):\n"
        "    _log('secret_scan', repo_root=repo_root)\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    r = " + repr(SECRET_RESULT) + "\n"
        "    r['scope'] = 'precommit'\n"
        "    return r\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


def provenance_writer_source():
    return (
        LOG_HELPER
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id, repo_root=repo_root)\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
        "    return None\n"
    )


def build_repo(repo_root, two_attempts, tracker_raises):
    write_fake(repo_root, "provenance-checker", provenance_checker_source())
    write_fake(repo_root, "spec-bundle-assembler", spec_bundle_assembler_source())
    write_fake(repo_root, "generation-loop", generation_loop_source(two_attempts))
    write_fake(repo_root, "provenance-tracker", provenance_tracker_source(tracker_raises))
    write_fake(repo_root, "verifier-orchestrator", verifier_orchestrator_source())
    write_fake(repo_root, "license-scanner", license_scanner_source())
    write_fake(repo_root, "secret-scanner", secret_scanner_source())
    write_fake(repo_root, "provenance-writer", provenance_writer_source())


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_on_attempt_writes_one_attempt_record_per_attempt(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_repo(repo_root, two_attempts=True, tracker_raises=False)

    component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")

    records = [e["args"] for e in read_log(log_path) if e["fn"] == "write_attempt_record"]
    assert len(records) == 2

    first, second = records
    assert first["component_id"] == "comp-foo"
    assert first["generation_result"] == G1
    assert first["verification_report"] is None
    assert first["spec_bundle_hash"] == "sha256:k"

    assert second["component_id"] == "comp-foo"
    assert second["generation_result"] == G2
    assert second["verification_report"] == R2
    assert second["spec_bundle_hash"] == "sha256:k"


def test_write_attempt_record_exception_does_not_change_result(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_repo(repo_root, two_attempts=False, tracker_raises=True)

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")

    records = [e for e in read_log(log_path) if e["fn"] == "write_attempt_record"]
    assert len(records) >= 1, "the raising write_attempt_record fake was never called"

    assert field(result, "blocked") is False
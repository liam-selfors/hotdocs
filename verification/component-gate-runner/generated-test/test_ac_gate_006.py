# hotdocs-criterion: sha256:aae360410e13ae16b8782e60e0ad827ca7eeb7745df0bd2db216e5fec4d68e9f
import json
from pathlib import Path

import pytest

import component_gate_runner


COMPONENT_ID = "comp-foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _attempt(number, outcome, surface_ok, overall, failed=None, error_category=None):
    return {
        "number": number,
        "outcome": outcome,
        "retry_feedback": [],
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": list(failed or []),
        "transcript_sha256": None,
        "reauthored_tests": [],
    }


def _generation_result(files, model_call_error=None):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:abc123",
        "model": "m-test",
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


VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.92,
    "mutation_error": None,
    "assets": [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:feed",
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "drivers": [],
    "overall": "pass",
    "marker": "loop-verification-report",
}

LICENSE_RESULT = {
    "component_id": COMPONENT_ID,
    "gate_version": "license_scanner@4.0.3+9f2c41ab07de",
    "evaluated": True,
    "reason": None,
    "similarity_score": 0.25,
    "block_threshold": 0.7,
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


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "LOG = {log}\n"
    "def _log(fn, **kw):\n"
    "    rec = dict(kw)\n"
    "    rec['fn'] = fn\n"
    "    with open(LOG, 'a') as f:\n"
    "        f.write(json.dumps(rec, default=repr, sort_keys=True) + '\\n')\n"
)


def _helper(log_path):
    # Replace the placeholder by concatenation (no str.format over brace text).
    head, tail = LOG_HELPER.split("{log}")
    return head + repr(str(log_path)) + tail


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


def _write_fakes(repo_root, log_path, loop_result):
    h = _helper(log_path)

    _write(
        repo_root,
        "provenance-checker",
        h
        + "class ProvenanceKey:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc123'\n"
        "        self.spec_bundle_parts = {'spec': 'sha256:s1', 'dependency_code': 'sha256:d1'}\n"
        "        self.gate_versions = {'verifier': 'v@1'}\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,"
        " 'adapter_sha256': 'sha256:feed', 'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}]\n"
        "        self.drivers = []\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return ProvenanceKey()\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash,"
        " gate_versions=gate_versions)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,"
        " 'license_scan': None, 'secret_scan': None}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,"
        " 'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    _write(
        repo_root,
        "spec-bundle-assembler",
        h
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123', 'spec': 's',"
        " 'interface': 'i', 'constraints': 'c', 'dependency_interfaces': {}, 'dependency_context': {},"
        " 'dependency_usage': {}, 'vars': {}, 'glossary': 'g', 'hint_code': None,"
        " 'spec_bundle_parts': {'spec': 'sha256:s1', 'dependency_code': 'sha256:d1'}}\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',"
        " 'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',"
        " 'dependency_interfaces': {}, 'testing': ''}\n",
    )

    _write(
        repo_root,
        "generation-loop",
        h
        + "RESULT = " + repr(loop_result) + "\n"
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',"
        " 'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file', 'missing_asset', 'malformed_layout')\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,"
        " retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model, mode=mode, max_attempts=max_attempts)\n"
        "    for entry in RESULT['attempts']:\n"
        "        if on_attempt is not None:\n"
        "            on_attempt(entry, RESULT['generation_result'], RESULT['verification_report'])\n"
        "    _log('run_attempts_done')\n"
        "    return RESULT\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n",
    )

    _write(
        repo_root,
        "provenance-tracker",
        h
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
        "    d = os.path.join(str(repo_root), '.hotdocs', 'attempts', component_id)\n"
        "    os.makedirs(d, exist_ok=True)\n"
        "    n = len(os.listdir(d))\n"
        "    aid = '2026-10-25T14:32:0' + str(n) + 'Z-a' + str(n)\n"
        "    rec = {'attempt_id': aid, 'component_id': component_id, 'timestamp': '2026-10-25T14:32:01Z',"
        " 'spec_bundle_hash': spec_bundle_hash, 'generation': generation_result,"
        " 'verification': verification_report}\n"
        "    with open(os.path.join(d, aid + '.json'), 'w') as f:\n"
        "        f.write(json.dumps(rec, default=repr))\n"
        "    return rec\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},"
        " 'secret_scan': None, 'not_ready_reasons': []}\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id=component_id)\n"
        "    return []\n",
    )

    _write(
        repo_root,
        "verifier-orchestrator",
        h
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "REPORT = " + repr(VERIFICATION_REPORT) + "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return REPORT\n",
    )

    _write(
        repo_root,
        "license-scanner",
        h
        + "RESULT = " + repr(LICENSE_RESULT) + "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return RESULT\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n",
    )

    _write(
        repo_root,
        "secret-scanner",
        h
        + "RESULT = " + repr(SECRET_RESULT) + "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return RESULT\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    r = dict(RESULT)\n"
        "    r['scope'] = 'precommit'\n"
        "    return r\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )

    _write(
        repo_root,
        "provenance-writer",
        h
        + "class MissingInputError(Exception):\n"
        "    pass\n"
        "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id, inputs=dict(inputs))\n"
        "    return None\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n",
    )


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _run(tmp_path, loop_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _write_fakes(repo_root, log_path, loop_result)
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")
    return result, _read_log(log_path)


def _indices(calls, fn):
    return [i for i, c in enumerate(calls) if c["fn"] == fn]


def test_passing_miss_writes_provenance_once_after_scans(tmp_path):
    attempts = [
        _attempt(1, "verification_failed", True, "fail", failed=["R-FOO-001"]),
        _attempt(2, "passed", True, "pass"),
    ]
    gen = _generation_result({"foo.py": "x = 1\n"})
    loop_result = {
        "passed": True,
        "stop_reason": "passed",
        "attempts": attempts,
        "generation_result": gen,
        "verification_report": VERIFICATION_REPORT,
        "surface_report": {"ok": True, "findings": []},
    }

    result, calls = _run(tmp_path, loop_result)

    writes = _indices(calls, "write_provenance")
    assert len(writes) == 1, calls
    w = writes[0]

    lic = _indices(calls, "license_scan")
    sec = _indices(calls, "secret_scan")
    assert lic and sec, calls
    assert max(lic) < w
    assert max(sec) < w
    records = _indices(calls, "write_attempt_record")
    assert len(records) == 2
    assert max(records) < w
    assert _indices(calls, "run_attempts_done")[0] < w

    call = calls[w]
    assert call["component_id"] == COMPONENT_ID
    inputs = call["inputs"]
    assert inputs["gate_versions"] == {"verifier": "v@1"}
    assert inputs["provenance_hit"] is False
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == attempts
    assert inputs["generation_result"] == gen
    assert inputs["verification_report"] == VERIFICATION_REPORT
    assert inputs["license_scan_result"] == LICENSE_RESULT
    assert inputs["secret_scan_result"] == SECRET_RESULT

    assert field(result, "blocked") is False


def test_generation_failed_with_no_files_writes_no_provenance(tmp_path):
    attempts = [
        _attempt(1, "generation_failed", None, None, error_category="network"),
    ]
    gen = _generation_result({}, model_call_error={"category": "network", "message": "down"})
    loop_result = {
        "passed": False,
        "stop_reason": "not_retried",
        "attempts": attempts,
        "generation_result": gen,
        "verification_report": None,
        "surface_report": None,
    }

    result, calls = _run(tmp_path, loop_result)

    assert _indices(calls, "write_provenance") == [], calls
    assert field(result, "blocked") is True


def test_surface_failure_writes_no_provenance(tmp_path):
    surface_report = {
        "ok": False,
        "findings": [{"kind": "asset_error", "message": "static/a.js: no interface file"}],
    }
    attempts = [
        _attempt(1, "surface_failed", False, None),
    ]
    gen = _generation_result({"foo.py": "x = 1\n"})
    loop_result = {
        "passed": False,
        "stop_reason": "max_attempts",
        "attempts": attempts,
        "generation_result": gen,
        "verification_report": None,
        "surface_report": surface_report,
    }

    result, calls = _run(tmp_path, loop_result)

    assert _indices(calls, "write_provenance") == [], calls
    assert field(result, "block_reason") == "surface_check_failed"
    assert field(result, "verification") is None
    assert field(result, "surface_report") == surface_report
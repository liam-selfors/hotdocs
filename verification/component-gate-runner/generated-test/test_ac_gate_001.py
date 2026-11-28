# hotdocs-criterion: sha256:49c9e8db40ad1ec38d15da2a6124f1eb87bb0ffbfc3d67b9cdab15558086d350
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PASS_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "pass",
}

FAIL_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "fail",
         "failure_detail": {"message": "x failed", "expected": 1, "actual": 2},
         "failure_origin": "implementation"},
    ],
    "requirement_results": {"R-FOO-001": "fail"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "assets": [],
    "drivers": [],
    "overall": "fail",
}

LICENSE_SCAN = {
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

SECRET_SCAN = {
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

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:k",
    "model": "m",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {"foo.py": "X = 1\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

LOOP_RESULT = {
    "passed": True,
    "stop_reason": "passed",
    "attempts": [
        {"number": 1, "outcome": "passed", "retry_feedback": [],
         "error_category": None, "surface_ok": True, "overall": "pass",
         "failed_requirements": [], "transcript_sha256": None,
         "reauthored_tests": []},
    ],
    "generation_result": GENERATION_RESULT,
    "verification_report": PASS_REPORT,
    "surface_report": {"ok": True, "findings": []},
}


def _common(log):
    return (
        "import json\n"
        "LOG = " + repr(str(log)) + "\n"
        "def _log(fn, **kw):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(json.dumps({'fn': fn, 'args': kw}, default=repr) + '\\n')\n"
        "\n"
    )


def _write(repo_root, slug, module, source):
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


def _install_fakes(repo_root, log, hit_report):
    common = _common(log)

    checker = (
        common
        + "VR = " + repr(hit_report) + "\n"
        + "LS = " + repr(LICENSE_SCAN) + "\n"
        + "SS = " + repr(SECRET_SCAN) + "\n"
        + "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr("sha256:k") + "\n"
        "        self.spec_bundle_parts = " + repr({"spec": "sha256:s", "dependency_code": "sha256:d"}) + "\n"
        "        self.gate_versions = " + repr({"verifier": "v@1"}) + "\n"
        "        self.assets = []\n"
        "        self.drivers = []\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
        "    return _Key()\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash,\n"
        "         gate_versions=gate_versions, repo_root=str(repo_root), spec_bundle_parts=spec_bundle_parts)\n"
        "    return {'hit': True, 'reason': None, 'verification_report': VR, 'license_scan': LS, 'secret_scan': SS}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None, 'written_at': None}\n"
    )
    _write(repo_root, "provenance-checker", "provenance_checker", checker)

    assembler = (
        common
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k', 'spec': '', 'interface': '',\n"
        "            'constraints': '', 'dependency_interfaces': {}, 'dependency_context': {}, 'dependency_usage': {},\n"
        "            'vars': {}, 'glossary': '', 'hint_code': None,\n"
        "            'spec_bundle_parts': {'spec': 'sha256:s', 'dependency_code': 'sha256:d'}}\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '', 'criterion_text': '',\n"
        "            'requirement_text': '', 'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    )
    _write(repo_root, "spec-bundle-assembler", "spec_bundle_assembler", assembler)

    loop = (
        common
        + "RESULT = " + repr(LOOP_RESULT) + "\n"
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file', 'missing_asset', 'malformed_layout')\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        "                 on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model, mode=mode, max_attempts=max_attempts)\n"
        "    return RESULT\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
    )
    _write(repo_root, "generation-loop", "generation_loop", loop)

    tracker = (
        common
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
        "            'secret_scan': None, 'not_ready_reasons': []}\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id=component_id)\n"
        "    return []\n"
    )
    _write(repo_root, "provenance-tracker", "provenance_tracker", tracker)

    verifier = (
        common
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "VR = " + repr(PASS_REPORT) + "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return VR\n"
    )
    _write(repo_root, "verifier-orchestrator", "verifier_orchestrator", verifier)

    license_ = (
        common
        + "LS = " + repr(LICENSE_SCAN) + "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return LS\n"
        "def gate_version(repo_root):\n"
        "    _log('license_gate_version')\n"
        "    return LS['gate_version']\n"
    )
    _write(repo_root, "license-scanner", "license_scanner", license_)

    secret = (
        common
        + "SS = " + repr(SECRET_SCAN) + "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return SS\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return SS\n"
        "def gate_version(repo_root):\n"
        "    _log('secret_gate_version')\n"
        "    return SS['gate_version']\n"
        "def propose(repo_root):\n"
        "    _log('propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )
    _write(repo_root, "secret-scanner", "secret_scanner", secret)

    writer = (
        common
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id)\n"
        "    return None\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n"
    )
    _write(repo_root, "provenance-writer", "provenance_writer", writer)


def _read_log(log):
    if not Path(log).exists():
        return []
    return [json.loads(line) for line in Path(log).read_text().splitlines() if line.strip()]


def test_ac_gate_001_short_circuit_on_passing_hit(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    _install_fakes(repo_root, log, PASS_REPORT)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _read_log(log)
    names = [c["fn"] for c in calls]
    assert "check_provenance" in names, names
    idx = names.index("check_provenance")
    assert "current_provenance_key" in names[:idx], names

    cp_args = calls[idx]["args"]
    assert cp_args["spec_bundle_hash"] == "sha256:k"
    assert cp_args["gate_versions"] == {"verifier": "v@1"}

    assert names[idx + 1:] == [], names

    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    assert field(result, "verification") == PASS_REPORT


def test_ac_gate_001_failed_hit_proceeds_as_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    _install_fakes(repo_root, log, FAIL_REPORT)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    names = [c["fn"] for c in _read_log(log)]
    assert names.count("run_attempts") == 1, names
    assert field(result, "provenance_hit") is False
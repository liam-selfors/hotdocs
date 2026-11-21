# hotdocs-criterion: sha256:230737ebdbd65b2c38dd6376c45ae440bde334676db251d64a451ebe4ccacbf9
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
SPEC_HASH = "sha256:abc123"
GATE_VERSIONS = {"verifier": "v@1"}
ASSET = {
    "kind": "python",
    "path": ".",
    "definition_sha256": None,
    "adapter_sha256": "sha256:00",
    "versions": {"python": "3.12.4"},
    "lockfile_sha256": None,
}


def _gen(files, model_call_error=None, retry_feedback=None):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_HASH,
        "model": "m1",
        "prompt_version": "v12",
        "cache_hit": False,
        "files": files,
        "model_call_error": model_call_error,
        "refused": None,
        "retry_feedback": retry_feedback,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }


def _report(overall, result):
    return {
        "component_id": COMPONENT_ID,
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": result},
        ],
        "requirement_results": {"R-FOO-001": result},
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [ASSET],
        "overall": overall,
    }


GEN_FIRST = _gen({"foo.py": "X = 0\n"})
GEN_PASS = _gen({"foo.py": "X = 1\n"}, retry_feedback=["R-FOO-001"])
GEN_ERROR = _gen({}, model_call_error={"category": "network", "message": "down"},
                 retry_feedback=["R-FOO-001"])
REPORT_FAIL = _report("fail", "fail")
REPORT_PASS = _report("pass", "pass")

ATTEMPT_1 = {
    "number": 1, "outcome": "verification_failed", "retry_feedback": [],
    "error_category": None, "surface_ok": True, "overall": "fail",
    "failed_requirements": ["R-FOO-001"], "transcript_sha256": None,
    "reauthored_tests": [],
}
ATTEMPT_2_PASS = {
    "number": 2, "outcome": "passed", "retry_feedback": ["R-FOO-001"],
    "error_category": None, "surface_ok": True, "overall": "pass",
    "failed_requirements": [], "transcript_sha256": None,
    "reauthored_tests": [],
}
ATTEMPT_2_FAIL = {
    "number": 2, "outcome": "generation_failed", "retry_feedback": ["R-FOO-001"],
    "error_category": "network", "surface_ok": None, "overall": None,
    "failed_requirements": [], "transcript_sha256": None,
    "reauthored_tests": [],
}

LICENSE_RESULT = {
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
SECRET_RESULT = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+fake",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


PRELUDE = (
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ['HOTDOCS_TEST_LOG'], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, default=str, sort_keys=True) + '\\n')\n"
    "\n"
)


def _provenance_checker_src():
    return (
        PRELUDE
        + "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        + "ASSET = " + repr(ASSET) + "\n"
        + "\n"
        + "class _Key:\n"
        + "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        + "        self.spec_bundle_hash = spec_bundle_hash\n"
        + "        self.gate_versions = gate_versions\n"
        + "        self.assets = assets\n"
        + "\n"
        + "def current_sealed_key(component_id, repo_root):\n"
        + "    _log({'fn': 'current_sealed_key', 'component_id': component_id})\n"
        + "    return None\n"
        + "\n"
        + "def current_provenance_key(component_id, repo_root):\n"
        + "    _log({'fn': 'current_provenance_key', 'component_id': component_id})\n"
        + "    return _Key(SPEC_HASH, dict(GATE_VERSIONS), [dict(ASSET)])\n"
        + "\n"
        + "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        + "    _log({'fn': 'check_provenance', 'component_id': component_id,\n"
        + "          'spec_bundle_hash': spec_bundle_hash, 'gate_versions': gate_versions})\n"
        + "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        + "            'license_scan': None, 'secret_scan': None}\n"
        + "\n"
        + "def check_sealed_provenance(component_id, repo_root):\n"
        + "    _log({'fn': 'check_sealed_provenance', 'component_id': component_id})\n"
        + "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        + "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        + "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


def _spec_bundle_assembler_src():
    return (
        PRELUDE
        + "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        + "\n"
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        + "    _log({'fn': 'assemble', 'component_id': component_id, 'mode': mode})\n"
        + "    return {'component_id': component_id, 'spec_bundle_hash': SPEC_HASH,\n"
        + "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
        + "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        + "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        + "\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    _log({'fn': 'assemble_criterion', 'component_id': component_id})\n"
        + "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        + "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        + "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    )


def _generation_loop_src():
    return (
        PRELUDE
        + "GEN_FIRST = " + repr(GEN_FIRST) + "\n"
        + "GEN_PASS = " + repr(GEN_PASS) + "\n"
        + "GEN_ERROR = " + repr(GEN_ERROR) + "\n"
        + "REPORT_FAIL = " + repr(REPORT_FAIL) + "\n"
        + "REPORT_PASS = " + repr(REPORT_PASS) + "\n"
        + "ATTEMPT_1 = " + repr(ATTEMPT_1) + "\n"
        + "ATTEMPT_2_PASS = " + repr(ATTEMPT_2_PASS) + "\n"
        + "ATTEMPT_2_FAIL = " + repr(ATTEMPT_2_FAIL) + "\n"
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        + "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        + "                      'missing_asset', 'malformed_layout')\n"
        + "\n"
        + "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        + "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        + "                 allow_unisolated_exec=False, on_attempt=None):\n"
        + "    _log({'fn': 'run_attempts', 'component_id': component_id, 'model': model})\n"
        + "    scenario = os.environ['HOTDOCS_TEST_SCENARIO']\n"
        + "    if scenario == 'pass':\n"
        + "        steps = [(ATTEMPT_1, GEN_FIRST, REPORT_FAIL), (ATTEMPT_2_PASS, GEN_PASS, REPORT_PASS)]\n"
        + "        passed = True\n"
        + "        stop_reason = 'passed'\n"
        + "        last_report = REPORT_PASS\n"
        + "        last_gen = GEN_PASS\n"
        + "        surface = {'ok': True, 'findings': []}\n"
        + "    else:\n"
        + "        steps = [(ATTEMPT_1, GEN_FIRST, REPORT_FAIL), (ATTEMPT_2_FAIL, GEN_ERROR, None)]\n"
        + "        passed = False\n"
        + "        stop_reason = 'not_retried'\n"
        + "        last_report = REPORT_FAIL\n"
        + "        last_gen = GEN_ERROR\n"
        + "        surface = {'ok': True, 'findings': []}\n"
        + "    attempts = []\n"
        + "    for attempt, gen, report in steps:\n"
        + "        attempts.append(attempt)\n"
        + "        if on_attempt is not None:\n"
        + "            on_attempt(attempt, gen, report)\n"
        + "    return {'passed': passed, 'stop_reason': stop_reason, 'attempts': attempts,\n"
        + "            'generation_result': last_gen, 'verification_report': last_report,\n"
        + "            'surface_report': surface}\n"
        + "\n"
        + "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        + "    _log({'fn': 'make_closures', 'model': model})\n"
        + "    def test_author(bundle):\n"
        + "        return {'model_call_error': None, 'file': None}\n"
        + "    def judge(bundle):\n"
        + "        return {'result': 'pass', 'rationale': None}\n"
        + "    return (test_author, judge)\n"
    )


def _provenance_tracker_src():
    return (
        PRELUDE
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        + "                         spec_bundle_hash, repo_root):\n"
        + "    _log({'fn': 'write_attempt_record', 'component_id': component_id,\n"
        + "          'spec_bundle_hash': spec_bundle_hash})\n"
        + "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
        + "    d.mkdir(parents=True, exist_ok=True)\n"
        + "    n = len(list(d.iterdir()))\n"
        + "    attempt_id = '2026-10-25T14-32-0' + str(n) + 'Z-a' + str(n)\n"
        + "    record = {'attempt_id': attempt_id, 'component_id': component_id,\n"
        + "              'timestamp': '2026-10-25T14:32:01Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        + "              'generation': generation_result, 'verification': verification_report}\n"
        + "    (d / (attempt_id + '.json')).write_text(json.dumps(record, default=str), encoding='utf-8')\n"
        + "    return record\n"
        + "\n"
        + "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        + "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        + "            'capabilities': {}, 'not_ready_reasons': []}\n"
        + "\n"
        + "def last_requirement_failures(component_id, repo_root):\n"
        + "    return []\n"
    )


def _verifier_orchestrator_src():
    return (
        PRELUDE
        + "REPORT_PASS = " + repr(REPORT_PASS) + "\n"
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        + "DEFAULT_TEST_TIMEOUT = 300.0\n"
        + "\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    _log({'fn': 'verify', 'component_id': component_id})\n"
        + "    return REPORT_PASS\n"
    )


def _license_scanner_src():
    return (
        PRELUDE
        + "LICENSE_RESULT = " + repr(LICENSE_RESULT) + "\n"
        + "\n"
        + "def scan(component_id, repo_root):\n"
        + "    _log({'fn': 'license_scan', 'component_id': component_id})\n"
        + "    return LICENSE_RESULT\n"
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    return LICENSE_RESULT['gate_version']\n"
    )


def _secret_scanner_src():
    return (
        PRELUDE
        + "SECRET_RESULT = " + repr(SECRET_RESULT) + "\n"
        + "\n"
        + "def scan(repo_root):\n"
        + "    _log({'fn': 'secret_scan'})\n"
        + "    return SECRET_RESULT\n"
        + "\n"
        + "def scan_files(paths, repo_root=None):\n"
        + "    _log({'fn': 'secret_scan_files'})\n"
        + "    result = dict(SECRET_RESULT)\n"
        + "    result['scope'] = 'precommit'\n"
        + "    return result\n"
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    return SECRET_RESULT['gate_version']\n"
        + "\n"
        + "def propose(repo_root):\n"
        + "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )


def _provenance_writer_src():
    return (
        PRELUDE
        + "def _plain(value):\n"
        + "    if isinstance(value, dict):\n"
        + "        return {str(k): _plain(v) for k, v in value.items()}\n"
        + "    if isinstance(value, (list, tuple)):\n"
        + "        return [_plain(v) for v in value]\n"
        + "    if hasattr(value, 'to_dict') and callable(value.to_dict):\n"
        + "        return _plain(value.to_dict())\n"
        + "    return value\n"
        + "\n"
        + "def write_provenance(component_id, inputs, repo_root):\n"
        + "    _log({'fn': 'write_provenance', 'component_id': component_id,\n"
        + "          'inputs_is_dict': isinstance(inputs, dict), 'inputs': _plain(inputs)})\n"
        + "    return None\n"
        + "\n"
        + "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        + "    _log({'fn': 'write_sealed_provenance', 'component_id': component_id})\n"
        + "    return None\n"
    )


def _build_repo(tmp_path, monkeypatch, scenario):
    repo_root = tmp_path / "repo"
    fakes = {
        ("provenance-checker", "provenance_checker"): _provenance_checker_src(),
        ("spec-bundle-assembler", "spec_bundle_assembler"): _spec_bundle_assembler_src(),
        ("generation-loop", "generation_loop"): _generation_loop_src(),
        ("provenance-tracker", "provenance_tracker"): _provenance_tracker_src(),
        ("verifier-orchestrator", "verifier_orchestrator"): _verifier_orchestrator_src(),
        ("license-scanner", "license_scanner"): _license_scanner_src(),
        ("secret-scanner", "secret_scanner"): _secret_scanner_src(),
        ("provenance-writer", "provenance_writer"): _provenance_writer_src(),
    }
    for (slug, module), src in fakes.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(src, encoding="utf-8")
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("HOTDOCS_TEST_LOG", str(log_path))
    monkeypatch.setenv("HOTDOCS_TEST_SCENARIO", scenario)
    return repo_root, log_path


def _read_log(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _indices(calls, fn):
    return [i for i, c in enumerate(calls) if c["fn"] == fn]


def test_write_provenance_called_once_after_scans_with_built_inputs(tmp_path, monkeypatch):
    repo_root, log_path = _build_repo(tmp_path, monkeypatch, "pass")

    component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m1")

    calls = _read_log(log_path)
    assert _indices(calls, "run_attempts"), calls

    wp = _indices(calls, "write_provenance")
    assert len(wp) == 1, calls
    wp_i = wp[0]

    lic = _indices(calls, "license_scan")
    sec = _indices(calls, "secret_scan")
    assert lic and sec, calls
    assert wp_i > max(lic), calls
    assert wp_i > max(sec), calls

    records = _indices(calls, "write_attempt_record")
    assert len(records) == 2, calls
    assert wp_i > max(records), calls

    entry = calls[wp_i]
    assert entry["component_id"] == COMPONENT_ID
    assert entry["inputs_is_dict"] is True
    inputs = entry["inputs"]

    assert inputs["gate_versions"] == {"verifier": "v@1"}
    assert inputs["provenance_hit"] is False
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == [ATTEMPT_1, ATTEMPT_2_PASS]
    assert inputs["generation_result"] == GEN_PASS
    assert inputs["verification_report"] == REPORT_PASS
    assert inputs["license_scan_result"] == LICENSE_RESULT
    assert inputs["secret_scan_result"] == SECRET_RESULT
    assert inputs["component_id"] == COMPONENT_ID


def test_write_provenance_never_called_when_last_generation_has_no_files(tmp_path, monkeypatch):
    repo_root, log_path = _build_repo(tmp_path, monkeypatch, "fail")

    component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m1")

    calls = _read_log(log_path)
    assert _indices(calls, "run_attempts"), calls
    assert _indices(calls, "write_provenance") == [], calls
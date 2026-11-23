# hotdocs-criterion: sha256:88714c31c23310fc4339fb020f13f2c26098857fd4bc61674389990fe5f446b0
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
SPEC_HASH = "sha256:" + "ab" * 32
GATE_VERSIONS = {"verifier": "v@1"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = (
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(name, **args):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'call': name, 'args': args}, default=str) + '\\n')\n"
    "\n"
)


def _gen_result(files, model_call_error=None):
    return {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_HASH,
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


def _ver_report(overall):
    result = "pass" if overall == "pass" else "fail"
    criterion = {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": result}
    if result == "fail":
        criterion["failure_detail"] = {"message": "x failed", "expected": 1, "actual": 2}
        criterion["failure_origin"] = "implementation"
    return {
        "component_id": COMPONENT_ID,
        "criteria": [criterion],
        "requirement_results": {"R-FOO-001": result},
        "interface_drift": False,
        "mutation_score": 0.9,
        "mutation_error": None,
        "assets": [{"kind": "python", "path": ".", "definition_sha256": None,
                    "adapter_sha256": "sha256:" + "cd" * 32,
                    "versions": {"python": "3.12.4"}, "lockfile_sha256": None}],
        "overall": overall,
    }


def _attempt(number, outcome, retry_feedback, error_category, surface_ok, overall, failed):
    return {
        "number": number,
        "outcome": outcome,
        "retry_feedback": retry_feedback,
        "error_category": error_category,
        "surface_ok": surface_ok,
        "overall": overall,
        "failed_requirements": failed,
        "transcript_sha256": None,
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
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def _write(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(PRELUDE + source, encoding="utf-8")


def _setup(repo_root, loop_result, per_attempt):
    # provenance-checker
    _write(repo_root, "provenance-checker", (
        "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        "\n"
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = SPEC_HASH\n"
        "        self.gate_versions = dict(GATE_VERSIONS)\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                        'adapter_sha256': None, 'versions': {}, 'lockfile_sha256': None}]\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id,\n"
        "         spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    ))

    # spec-bundle-assembler
    _write(repo_root, "spec-bundle-assembler", (
        "SPEC_HASH = " + repr(SPEC_HASH) + "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': SPEC_HASH,\n"
        "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '',\n"
        "            'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
    ))

    # generation-loop
    _write(repo_root, "generation-loop", (
        "LOOP_RESULT = " + repr(loop_result) + "\n"
        "PER_ATTEMPT = " + repr(per_attempt) + "\n"
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model)\n"
        "    for i, attempt in enumerate(LOOP_RESULT['attempts']):\n"
        "        gen, report = PER_ATTEMPT[i]\n"
        "        if i == len(LOOP_RESULT['attempts']) - 1:\n"
        "            gen = LOOP_RESULT['generation_result']\n"
        "            report = LOOP_RESULT['verification_report']\n"
        "        if on_attempt is not None:\n"
        "            on_attempt(attempt, gen, report)\n"
        "    return LOOP_RESULT\n"
        "\n"
        "def _test_author(bundle):\n"
        "    return {'model_call_error': None, 'file': None}\n"
        "\n"
        "def _judge(bundle):\n"
        "    return {'result': 'pass', 'rationale': None}\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model, seed=seed)\n"
        "    return (_test_author, _judge)\n"
    ))

    # provenance-tracker
    _write(repo_root, "provenance-tracker", (
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id,\n"
        "         spec_bundle_hash=spec_bundle_hash)\n"
        "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
        "    d.mkdir(parents=True, exist_ok=True)\n"
        "    n = len(list(d.iterdir())) + 1\n"
        "    attempt_id = '2026-01-01T00:00:0' + str(n) + 'Z-a' + str(n)\n"
        "    record = {'attempt_id': attempt_id, 'component_id': component_id,\n"
        "              'timestamp': '2026-01-01T00:00:0' + str(n) + 'Z',\n"
        "              'spec_bundle_hash': spec_bundle_hash,\n"
        "              'generation': json.loads(json.dumps(generation_result, default=str)),\n"
        "              'verification': json.loads(json.dumps(verification_report, default=str))}\n"
        "    (d / ('attempt-' + str(n).zfill(4) + '.json')).write_text(json.dumps(record))\n"
        "    return record\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures', component_id=component_id)\n"
        "    return []\n"
    ))

    # verifier-orchestrator
    _write(repo_root, "verifier-orchestrator", (
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "REPORT = " + repr(_ver_report("pass")) + "\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return REPORT\n"
    ))

    # license-scanner
    _write(repo_root, "license-scanner", (
        "RESULT = " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return RESULT\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
    ))

    # secret-scanner
    _write(repo_root, "secret-scanner", (
        "RESULT = " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return RESULT\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    r = dict(RESULT)\n"
        "    r['scope'] = 'precommit'\n"
        "    return r\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return RESULT['gate_version']\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    ))

    # provenance-writer
    _write(repo_root, "provenance-writer", (
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id, inputs=inputs)\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id, inputs=inputs)\n"
        "    return None\n"
    ))


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _prepare(tmp_path, monkeypatch, loop_result, per_attempt):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    _setup(repo_root, loop_result, per_attempt)
    return repo_root, log_path


def test_provenance_written_once_after_scans_on_passing_miss(tmp_path, monkeypatch):
    gen = _gen_result({"foo.py": "x = 1\n"})
    first_report = _ver_report("fail")
    last_report = _ver_report("pass")
    attempts = [
        _attempt(1, "verification_failed", [], None, True, "fail", ["R-FOO-001"]),
        _attempt(2, "passed", ["R-FOO-001"], None, True, "pass", []),
    ]
    loop_result = {
        "passed": True,
        "stop_reason": "passed",
        "attempts": attempts,
        "generation_result": gen,
        "verification_report": last_report,
        "surface_report": {"ok": True, "findings": []},
    }
    per_attempt = [(gen, first_report), (gen, last_report)]
    repo_root, log_path = _prepare(tmp_path, monkeypatch, loop_result, per_attempt)

    component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")

    calls = _read_log(log_path)
    names = [c["call"] for c in calls]

    assert names.count("write_attempt_record") == 2
    assert len(list((repo_root / ".hotdocs" / "attempts" / COMPONENT_ID).iterdir())) == 2

    assert names.count("write_provenance") == 1
    wp_index = names.index("write_provenance")
    assert "license_scan" in names and "secret_scan" in names
    assert names.index("license_scan") < wp_index
    assert names.index("secret_scan") < wp_index

    inputs = calls[wp_index]["args"]["inputs"]
    assert inputs["gate_versions"] == {"verifier": "v@1"}
    assert inputs["provenance_hit"] is False
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == attempts
    assert inputs["generation_result"] == gen
    assert inputs["verification_report"] == last_report
    assert inputs["license_scan_result"] == LICENSE_RESULT
    assert inputs["secret_scan_result"] == SECRET_RESULT


def test_no_provenance_when_last_generation_has_no_files(tmp_path, monkeypatch):
    gen = _gen_result({}, model_call_error={"category": "network", "message": "down"})
    attempts = [
        _attempt(1, "generation_failed", [], "network", None, None, []),
    ]
    loop_result = {
        "passed": False,
        "stop_reason": "not_retried",
        "attempts": attempts,
        "generation_result": gen,
        "verification_report": None,
        "surface_report": None,
    }
    per_attempt = [(gen, None)]
    repo_root, log_path = _prepare(tmp_path, monkeypatch, loop_result, per_attempt)

    component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")

    names = [c["call"] for c in _read_log(log_path)]
    assert "run_attempts" in names
    assert "write_provenance" not in names


def test_no_provenance_on_surface_failure(tmp_path, monkeypatch):
    gen = _gen_result({"foo.py": "x = 1\n"})
    surface_report = {
        "ok": False,
        "findings": [{"kind": "asset_error", "message": "static/a.js: no interface file"}],
    }
    attempts = [
        _attempt(1, "surface_failed", [], None, False, None, []),
    ]
    loop_result = {
        "passed": False,
        "stop_reason": "max_attempts",
        "attempts": attempts,
        "generation_result": gen,
        "verification_report": None,
        "surface_report": surface_report,
    }
    per_attempt = [(gen, None)]
    repo_root, log_path = _prepare(tmp_path, monkeypatch, loop_result, per_attempt)

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m-test")

    names = [c["call"] for c in _read_log(log_path)]
    assert "run_attempts" in names
    assert "write_provenance" not in names
    assert field(result, "block_reason") == "surface_check_failed"
    assert field(result, "verification") is None
    returned_surface = field(result, "surface_report")
    assert field(returned_surface, "ok") is False
    assert field(returned_surface, "findings") == surface_report["findings"]
    assert returned_surface == surface_report
# hotdocs-criterion: sha256:d19748b19ac1e271bbf6efb4933722c1ebdf819aa4f74ce41ea39f0a2da55f54
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(fn, **kw):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(json.dumps({'fn': fn, 'args': kw}, default=repr, sort_keys=True) + '\\n')\n"
    "\n"
    "class _Obj:\n"
    "    def __init__(self, **kw):\n"
    "        self.__dict__.update(kw)\n"
    "\n"
)


def _provenance_checker_src(sealed):
    return (
        LOG_HEADER
        + "SEALED = " + repr(sealed) + "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    if not SEALED:\n"
        "        return None\n"
        "    return _Obj(owners=['pipeline-team'], source_path='pipeline/foo/',\n"
        "                source_hash='sha256:k', verifier_version='verifier-orchestrator@2.0.0')\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return _Obj(\n"
        "        spec_bundle_hash='sha256:abc',\n"
        "        gate_versions={\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "            'generator': 'generator@3.0.0+v11',\n"
        "        },\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
        "                 'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


SPEC_BUNDLE_ASSEMBLER_SRC = (
    LOG_HEADER
    + "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, mode=mode)\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
    "            'spec': 's', 'interface': 'i', 'constraints': 'c',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP_SRC = (
    LOG_HEADER
    + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, model=model)\n"
    "    gen = {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc', 'model': model,\n"
    "           'prompt_version': 'v1', 'cache_hit': False, 'files': {'foo.py': 'X = 1\\n'},\n"
    "           'model_call_error': None, 'refused': None, 'retry_feedback': None,\n"
    "           'mode': 'single', 'transcript_sha256': None, 'turns': 1, 'tool_calls': 0,\n"
    "           'isolation': None}\n"
    "    report = {'component_id': component_id,\n"
    "              'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "                            'result': 'pass'}],\n"
    "              'requirement_results': {'R-FOO-001': 'pass'}, 'interface_drift': False,\n"
    "              'mutation_score': 0.9, 'mutation_error': None, 'assets': [], 'overall': 'pass'}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, gen, report)\n"
    "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [attempt],\n"
    "            'generation_result': gen, 'verification_report': report,\n"
    "            'surface_report': {'ok': True, 'findings': []}}\n"
)


PROVENANCE_TRACKER_SRC = (
    LOG_HEADER
    + "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness')\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', component_id=component_id)\n"
    "    return []\n"
)


def _verifier_src(overall):
    return (
        LOG_HEADER
        + "OVERALL = " + repr(overall) + "\n"
        "GATE_VERSION = 'verifier-orchestrator@2.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    second = {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled',\n"
        "              'result': 'pass'}\n"
        "    results = {'R-FOO-001': 'pass', 'R-FOO-002': 'pass'}\n"
        "    if OVERALL == 'fail':\n"
        "        second = {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled',\n"
        "                  'result': 'fail', 'failure_origin': 'implementation',\n"
        "                  'failure_detail': {'message': 'x equals 1 failed',\n"
        "                                     'expected': 1, 'actual': 2}}\n"
        "        results = {'R-FOO-001': 'pass', 'R-FOO-002': 'fail'}\n"
        "    return {'component_id': component_id,\n"
        "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
        "                          'kind': 'compiled', 'result': 'pass'}, second],\n"
        "            'requirement_results': results, 'interface_drift': False,\n"
        "            'mutation_score': None, 'mutation_error': None,\n"
        "            'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                        'adapter_sha256': 'sha256:00',\n"
        "                        'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
        "            'overall': OVERALL}\n"
    )


LICENSE_SCANNER_SRC = (
    LOG_HEADER
    + "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id)\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "            'cache_hit': False}\n"
)


SECRET_SCANNER_SRC = (
    LOG_HEADER
    + "def _result(scope):\n"
    "    return {'scope': scope, 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
    "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return _result('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files')\n"
    "    return _result('precommit')\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER_SRC = (
    LOG_HEADER
    + "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "_SEALED_KEYS = ('component_id', 'owners', 'source_path', 'source_hash',\n"
    "                'verifier_version', 'verification_report')\n"
    "\n"
    "def _plain(v, keys):\n"
    "    if isinstance(v, dict):\n"
    "        return dict(v)\n"
    "    return {k: getattr(v, k, None) for k in keys}\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id,\n"
    "         inputs=_plain(inputs, _SEALED_KEYS))\n"
    "    return None\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _setup(tmp_path, monkeypatch, sealed, overall="pass"):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    log.write_text("")
    monkeypatch.setenv(LOG_ENV, str(log))
    gen = repo_root / "gen"
    _write(gen / "provenance-checker" / "provenance_checker.py", _provenance_checker_src(sealed))
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write(gen / "generation-loop" / "generation_loop.py", GENERATION_LOOP_SRC)
    _write(gen / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER_SRC)
    _write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", _verifier_src(overall))
    _write(gen / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_SRC)
    _write(gen / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC)
    _write(gen / "provenance-writer" / "provenance_writer.py", PROVENANCE_WRITER_SRC)
    return repo_root, log


def _calls(log):
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _names(calls):
    return [c["fn"] for c in calls]


def test_sealed_component_pass_skips_generation_and_writes_sealed_provenance(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, sealed=True, overall="pass")
    assert not (repo_root / "specs" / "components" / "foo" / "component.md").exists()

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log)
    names = _names(calls)
    for never in ("check_provenance", "current_provenance_key", "assemble",
                  "run_attempts", "write_attempt_record", "write_provenance"):
        assert names.count(never) == 0, (never, names)
    for once in ("verify", "license_scan", "secret_scan"):
        assert names.count(once) == 1, (once, names)
    assert names.count("write_sealed_provenance") == 1, names

    w = names.index("write_sealed_provenance")
    assert w > names.index("verify")
    assert w > names.index("license_scan")
    assert w > names.index("secret_scan")

    args = calls[w]["args"]
    assert args["component_id"] == "comp-foo"
    inputs = args["inputs"]
    assert inputs["component_id"] == "comp-foo"
    assert inputs["owners"] == ["pipeline-team"]
    assert inputs["source_path"] == "pipeline/foo/"
    assert inputs["source_hash"] == "sha256:k"
    assert inputs["verifier_version"] == "verifier-orchestrator@2.0.0"
    report = inputs["verification_report"]
    assert isinstance(report, dict)
    assert report["overall"] == "pass"
    assert len(report["criteria"]) == 2
    assert report["component_id"] == "comp-foo"

    verification = field(result, "verification")
    assert json.loads(json.dumps(verification)) == report

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False


def test_sealed_component_fail_blocks_and_still_writes_sealed_provenance(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, sealed=True, overall="fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"

    calls = _calls(log)
    names = _names(calls)
    assert names.count("write_sealed_provenance") == 1, names
    w = names.index("write_sealed_provenance")
    assert w > names.index("verify")
    inputs = calls[w]["args"]["inputs"]
    assert inputs["verification_report"]["overall"] == "fail"
    assert len(inputs["verification_report"]["criteria"]) == 2
    assert json.loads(json.dumps(field(result, "verification"))) == inputs["verification_report"]


def test_non_sealed_component_takes_generation_path(tmp_path, monkeypatch):
    repo_root, log = _setup(tmp_path, monkeypatch, sealed=False, overall="pass")

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    names = _names(_calls(log))
    assert names.count("write_sealed_provenance") == 0, names
    assert names.count("make_closures") == 0, names

    expected = ["current_provenance_key", "check_provenance", "assemble", "run_attempts",
                "write_attempt_record", "license_scan", "secret_scan", "write_provenance"]
    for name in expected:
        assert names.count(name) == 1, (name, names)
    observed = [n for n in names if n in expected]
    assert observed == expected, names
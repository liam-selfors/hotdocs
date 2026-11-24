# hotdocs-criterion: sha256:a68b46078c737a65e69030bbecbff68575a498ce3f69bf7404c0b0d9905bf700
import json
import os
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


PRELUDE = (
    "import json\n"
    "import os\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry, sort_keys=True) + '\\n')\n"
    "\n"
    "\n"
    "def _f(value, name, default=None):\n"
    "    if isinstance(value, dict):\n"
    "        return value.get(name, default)\n"
    "    return getattr(value, name, default)\n"
    "\n"
    "\n"
    "class _Obj:\n"
    "    def __init__(self, **kw):\n"
    "        self.__dict__.update(kw)\n"
    "\n"
    "    def to_dict(self):\n"
    "        return dict(self.__dict__)\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return self.__dict__[key]\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return self.__dict__.get(key, default)\n"
    "\n"
    "\n"
)

PROVENANCE_CHECKER = PRELUDE + (
    "class SealedKey(_Obj):\n"
    "    pass\n"
    "\n"
    "\n"
    "class ProvenanceKey(_Obj):\n"
    "    pass\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    if os.environ.get('GATE_TEST_SEALED') != '1':\n"
    "        return None\n"
    "    return SealedKey(owners=['pipeline-team'], source_path='pipeline/foo/',\n"
    "                     source_hash='sha256:k',\n"
    "                     verifier_version='verifier-orchestrator@2.0.0')\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey(\n"
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
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': True, 'reason': 'no manifest',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = PRELUDE + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'call': 'assemble', 'component_id': component_id, 'mode': mode})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
    "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'call': 'assemble_criterion', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP = PRELUDE + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures', 'model': model})\n"
    "\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "\n"
    "    return (test_author, judge)\n"
    "\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'component_id': component_id})\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
    "        'model': model, 'prompt_version': 'v11', 'cache_hit': False,\n"
    "        'files': {'foo.py': 'x = 1\\n'}, 'model_call_error': None, 'refused': None,\n"
    "        'retry_feedback': None, 'mode': 'single', 'transcript_sha256': None,\n"
    "        'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
    "    }\n"
    "    verification_report = {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "                      'result': 'pass'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False, 'mutation_score': 0.9, 'mutation_error': None,\n"
    "        'assets': [], 'overall': 'pass',\n"
    "    }\n"
    "    surface_report = {'ok': True, 'findings': []}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, verification_report)\n"
    "    return _Obj(passed=True, stop_reason='passed', attempts=[attempt],\n"
    "                generation_result=generation_result,\n"
    "                verification_report=verification_report,\n"
    "                surface_report=surface_report)\n"
)

VERIFIER_ORCHESTRATOR = PRELUDE + (
    "GATE_VERSION = 'verifier-orchestrator@2.0.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "\n"
    "class VerificationReport(_Obj):\n"
    "    pass\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id})\n"
    "    overall = os.environ.get('GATE_TEST_OVERALL', 'pass')\n"
    "    if overall == 'pass':\n"
    "        second = {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled',\n"
    "                  'result': 'pass'}\n"
    "        results = {'R-FOO-001': 'pass', 'R-FOO-002': 'pass'}\n"
    "    else:\n"
    "        second = {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled',\n"
    "                  'result': 'fail', 'failure_origin': 'implementation',\n"
    "                  'failure_detail': {'message': 'm', 'expected': 1, 'actual': 2}}\n"
    "        results = {'R-FOO-001': 'pass', 'R-FOO-002': 'fail'}\n"
    "    return VerificationReport(\n"
    "        component_id=component_id,\n"
    "        criteria=[{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "                   'result': 'pass'}, second],\n"
    "        requirement_results=results,\n"
    "        interface_drift=False, mutation_score=None, mutation_error=None,\n"
    "        assets=[], overall=overall,\n"
    "    )\n"
)

LICENSE_SCANNER = PRELUDE + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan', 'component_id': component_id})\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "            'cache_hit': False}\n"
)

SECRET_SCANNER = PRELUDE + (
    "class SecretScanResult(_Obj):\n"
    "    pass\n"
    "\n"
    "\n"
    "def _result(scope):\n"
    "    return SecretScanResult(scope=scope, gate_version='secret_scanner@0.0.0',\n"
    "                            flagged=False, matches=[], allowed=[],\n"
    "                            unused_allowlist_entries=[], notified=False,\n"
    "                            notification_delivery_error=None, cache_hit=False)\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return _result('full')\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log({'call': 'secret_scan_files'})\n"
    "    return _result('precommit')\n"
    "\n"
    "\n"
    "def propose(repo_root):\n"
    "    _log({'call': 'propose'})\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_WRITER = PRELUDE + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    report = _f(inputs, 'verification_report')\n"
    "    if hasattr(report, 'to_dict'):\n"
    "        report = report.to_dict()\n"
    "    owners = _f(inputs, 'owners')\n"
    "    _log({'call': 'write_sealed_provenance', 'component_id': component_id,\n"
    "          'inputs_is_dict': isinstance(inputs, dict),\n"
    "          'input_keys': sorted(inputs.keys()) if isinstance(inputs, dict) else None,\n"
    "          'inputs_component_id': _f(inputs, 'component_id'),\n"
    "          'owners': list(owners) if owners is not None else None,\n"
    "          'source_path': _f(inputs, 'source_path'),\n"
    "          'source_hash': _f(inputs, 'source_hash'),\n"
    "          'verifier_version': _f(inputs, 'verifier_version'),\n"
    "          'verification_report': report})\n"
    "    return None\n"
)

PROVENANCE_TRACKER = PRELUDE + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-000001', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log({'call': 'check_readiness'})\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log({'call': 'last_requirement_failures'})\n"
    "    return []\n"
)

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER,
}


def _setup(tmp_path, monkeypatch, sealed, overall):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for (slug, module_name), source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (module_name + ".py")).write_text(source, encoding="utf-8")
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.setenv("GATE_TEST_SEALED", "1" if sealed else "0")
    monkeypatch.setenv("GATE_TEST_OVERALL", overall)
    return repo_root, log_path


def _calls(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _names(calls):
    return [c["call"] for c in calls]


def _assert_sealed_write(entry, overall):
    assert entry["component_id"] == "comp-foo"
    assert entry["inputs_component_id"] == "comp-foo"
    assert entry["owners"] == ["pipeline-team"]
    assert entry["source_path"] == "pipeline/foo/"
    assert entry["source_hash"] == "sha256:k"
    assert entry["verifier_version"] == "verifier-orchestrator@2.0.0"
    if entry["inputs_is_dict"]:
        assert entry["input_keys"] == sorted([
            "component_id", "owners", "source_path", "source_hash",
            "verifier_version", "verification_report",
        ])
    report = entry["verification_report"]
    assert report is not None
    assert report["overall"] == overall
    assert report["component_id"] == "comp-foo"
    assert len(report["criteria"]) == 2


def test_sealed_component_pass(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, sealed=True, overall="pass")
    assert not (repo_root / "specs" / "components" / "foo" / "component.md").exists()

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = _calls(log_path)
    names = _names(calls)
    for never in ("check_provenance", "current_provenance_key", "assemble",
                  "run_attempts", "write_attempt_record", "write_provenance"):
        assert names.count(never) == 0, never
    assert names.count("verify") == 1
    assert names.count("license_scan") == 1
    assert names.count("secret_scan") == 1
    assert names.count("write_sealed_provenance") == 1
    w = names.index("write_sealed_provenance")
    assert w > names.index("verify")
    assert w > names.index("license_scan")
    assert w > names.index("secret_scan")
    _assert_sealed_write(calls[w], "pass")

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(field(result, "verification"), "overall") == "pass"


def test_sealed_component_fail_still_writes(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, sealed=True, overall="fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    calls = _calls(log_path)
    names = _names(calls)
    assert names.count("write_sealed_provenance") == 1
    w = names.index("write_sealed_provenance")
    assert w > names.index("verify")
    assert w > names.index("license_scan")
    assert w > names.index("secret_scan")
    _assert_sealed_write(calls[w], "fail")


def test_non_sealed_component_never_writes_sealed(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, sealed=False, overall="pass")

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    names = _names(_calls(log_path))
    assert names.count("write_sealed_provenance") == 0
    assert names.count("make_closures") == 0
    expected = [
        "current_provenance_key", "check_provenance", "assemble", "run_attempts",
        "write_attempt_record", "license_scan", "secret_scan", "write_provenance",
    ]
    for name in expected:
        assert names.count(name) == 1, name
    observed = [n for n in names if n in expected]
    assert observed == expected
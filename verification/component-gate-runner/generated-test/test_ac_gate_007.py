# hotdocs-criterion: sha256:7eee27e2147723ede25d2567c508ede32c310ba3852cc123a0a53454c0f4cc41
import json
import os
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(fn, data):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps({'fn': fn, 'data': data}, default=repr) + '\\n')\n"
    "\n"
    "def _cfg():\n"
    "    return json.loads(os.environ['GATE_TEST_CFG'])\n"
    "\n"
    "def _plain(v):\n"
    "    if isinstance(v, dict):\n"
    "        return v\n"
    "    return dict((k, x) for k, x in vars(v).items() if not k.startswith('_'))\n"
    "\n"
)

PROVENANCE_CHECKER = COMMON + (
    "class _Obj:\n"
    "    def __init__(self, **kw):\n"
    "        for k, v in kw.items():\n"
    "            setattr(self, k, v)\n"
    "\n"
    "GATE_VERSIONS = {'compiler': 'criterion-compiler@1.0.0', 'generated_test': 'generated_test@1.0.0',\n"
    "    'verifier': 'verifier-orchestrator@2.0.0', 'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "    'secret_scanner': 'secret_scanner@0.0.0', 'generator': 'generator@3.0.0+v11'}\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', {'component_id': component_id})\n"
    "    if not _cfg()['sealed']:\n"
    "        return None\n"
    "    return _Obj(owners=['pipeline-team'], source_path='pipeline/foo/', source_hash='sha256:k',\n"
    "                verifier_version='verifier-orchestrator@2.0.0')\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', {'component_id': component_id})\n"
    "    return _Obj(spec_bundle_hash='sha256:b', gate_versions=dict(GATE_VERSIONS),\n"
    "                assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                         'adapter_sha256': 'sha256:a', 'versions': {'python': '3.12.4'},\n"
    "                         'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', {'component_id': component_id, 'spec_bundle_hash': spec_bundle_hash})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', {'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = COMMON + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', {'component_id': component_id, 'mode': mode})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:b', 'spec': '',\n"
    "            'interface': '', 'constraints': '', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', {'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP = COMMON + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file', 'missing_asset',\n"
    "    'malformed_layout')\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', {'model': model, 'seed': seed})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log('run_attempts', {'component_id': component_id, 'model': model})\n"
    "    gen = {'component_id': component_id, 'spec_bundle_hash': 'sha256:b', 'model': model,\n"
    "           'prompt_version': 'v1', 'cache_hit': False, 'files': {'foo.py': 'x = 1\\n'},\n"
    "           'model_call_error': None, 'refused': None, 'retry_feedback': None, 'mode': 'single',\n"
    "           'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "    report = {'component_id': component_id,\n"
    "              'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    "              'requirement_results': {'R-FOO-001': 'pass'}, 'interface_drift': False,\n"
    "              'mutation_score': None, 'mutation_error': None, 'assets': [], 'overall': 'pass'}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [], 'error_category': None,\n"
    "               'surface_ok': True, 'overall': 'pass', 'failed_requirements': [],\n"
    "               'transcript_sha256': None, 'reauthored_tests': []}\n"
    "    on_attempt(attempt, gen, report)\n"
    "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [attempt],\n"
    "            'generation_result': gen, 'verification_report': report,\n"
    "            'surface_report': {'ok': True, 'findings': []}}\n"
)

PROVENANCE_TRACKER = COMMON + (
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', {'component_id': component_id, 'spec_bundle_hash': spec_bundle_hash})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness', {})\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', {})\n"
    "    return []\n"
)

VERIFIER_ORCHESTRATOR = COMMON + (
    "GATE_VERSION = 'verifier-orchestrator@2.0.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', {'component_id': component_id})\n"
    "    return _cfg()['report']\n"
)

LICENSE_SCANNER = COMMON + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', {'component_id': component_id})\n"
    "    return {'component_id': component_id, 'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
    "            'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
)

SECRET_SCANNER = COMMON + (
    "def _result():\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan', {})\n"
    "    return _result()\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', {})\n"
    "    r = _result()\n"
    "    r['scope'] = 'precommit'\n"
    "    return r\n"
    "\n"
    "def propose(repo_root):\n"
    "    _log('propose', {})\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_WRITER = COMMON + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', {'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', {'component_id': component_id, 'inputs': _plain(inputs)})\n"
    "    return None\n"
)

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER,
    ("generation-loop", "generation_loop"): GENERATION_LOOP,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_ORCHESTRATOR,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER,
}


def make_report(overall):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled",
             "result": "pass" if overall == "pass" else "fail"},
            {"id": "AC-FOO-002", "covers": "R-FOO-002", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {
            "R-FOO-001": "pass" if overall == "pass" else "fail",
            "R-FOO-002": "pass",
        },
        "interface_drift": False,
        "mutation_score": None,
        "mutation_error": None,
        "assets": [],
        "overall": overall,
    }


def setup_repo(tmp_path, monkeypatch, sealed, overall="pass"):
    repo_root = tmp_path / "repo"
    for (slug, module), source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(source)
    log = tmp_path / "calls.log"
    log.write_text("")
    report = make_report(overall)
    monkeypatch.setenv("GATE_TEST_LOG", str(log))
    monkeypatch.setenv("GATE_TEST_CFG", json.dumps({"sealed": sealed, "report": report}))
    return repo_root, log, report


def read_calls(log):
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def names(calls):
    return [c["fn"] for c in calls]


SEALED_FORBIDDEN = [
    "check_provenance", "current_provenance_key", "assemble", "run_attempts",
    "write_attempt_record", "write_provenance",
]


def check_sealed_common(calls, report):
    ns = names(calls)
    for fn in SEALED_FORBIDDEN:
        assert fn not in ns, fn + " must not be called for a sealed component"
    assert ns.count("verify") == 1
    assert ns.count("license_scan") == 1
    assert ns.count("secret_scan") == 1
    assert ns.count("write_sealed_provenance") == 1
    w = ns.index("write_sealed_provenance")
    assert w > ns.index("verify")
    assert w > ns.index("license_scan")
    assert w > ns.index("secret_scan")
    call = calls[w]["data"]
    assert call["component_id"] == "comp-foo"
    inputs = call["inputs"]
    assert inputs["component_id"] == "comp-foo"
    assert inputs["owners"] == ["pipeline-team"]
    assert inputs["source_path"] == "pipeline/foo/"
    assert inputs["source_hash"] == "sha256:k"
    assert inputs["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert inputs["verification_report"] == report


def test_sealed_component_pass(tmp_path, monkeypatch):
    repo_root, log, report = setup_repo(tmp_path, monkeypatch, sealed=True, overall="pass")
    assert not (repo_root / "specs" / "components" / "foo" / "component.md").exists()
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_calls(log)
    check_sealed_common(calls, report)
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "verification") == report
    assert field(result, "attempts") == []


def test_sealed_component_fail(tmp_path, monkeypatch):
    repo_root, log, report = setup_repo(tmp_path, monkeypatch, sealed=True, overall="fail")
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    calls = read_calls(log)
    check_sealed_common(calls, report)
    w = names(calls).index("write_sealed_provenance")
    assert calls[w]["data"]["inputs"]["verification_report"]["overall"] == "fail"
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "provenance_hit") is False


def test_non_sealed_component_takes_generation_path(tmp_path, monkeypatch):
    repo_root, log, report = setup_repo(tmp_path, monkeypatch, sealed=False)
    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")
    ns = names(read_calls(log))
    assert "write_sealed_provenance" not in ns
    assert "make_closures" not in ns
    expected = [
        "current_provenance_key", "check_provenance", "assemble", "run_attempts",
        "write_attempt_record", "license_scan", "secret_scan", "write_provenance",
    ]
    for fn in expected:
        assert ns.count(fn) == 1, fn
    assert [n for n in ns if n in expected] == expected
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
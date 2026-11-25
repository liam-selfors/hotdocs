# hotdocs-criterion: sha256:3f95594423fea40741bb903bb94d00f9a3cbe4dce88a7e34b69703147814d079
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "from dataclasses import dataclass\n"
    "\n"
    "\n"
    "def _log(rec):\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps(rec, default=repr) + '\\n')\n"
    "\n"
    "\n"
)


CHECKER_SRC = COMMON + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'event': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'event': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey(\n"
    "        'sha256:abc123',\n"
    "        {'verifier': 'v@1'},\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.0'},\n"
    "          'lockfile_sha256': None}],\n"
    "    )\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'event': 'check_provenance', 'component_id': component_id,\n"
    "          'spec_bundle_hash': spec_bundle_hash, 'gate_versions': gate_versions})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'event': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


ASSEMBLER_SRC = COMMON + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'event': 'assemble', 'component_id': component_id, 'mode': mode})\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc123',\n"
    "        'spec': 'spec text',\n"
    "        'interface': 'interface text',\n"
    "        'constraints': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '',\n"
    "        'hint_code': None,\n"
    "    }\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'event': 'assemble_criterion', 'component_id': component_id})\n"
    "    return {\n"
    "        'component_id': component_id, 'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "        'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': '',\n"
    "    }\n"
)


LOOP_SRC = COMMON + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class SurfaceReport:\n"
    "    ok: bool\n"
    "    findings: list\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class AttemptLoopResult:\n"
    "    passed: bool\n"
    "    stop_reason: str\n"
    "    attempts: list\n"
    "    generation_result: object\n"
    "    verification_report: object\n"
    "    surface_report: object\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
    "                'attempts': self.attempts,\n"
    "                'generation_result': self.generation_result,\n"
    "                'verification_report': self.verification_report,\n"
    "                'surface_report': self.surface_report.to_dict()\n"
    "                if self.surface_report is not None else None}\n"
    "\n"
    "\n"
    "def _gen(component_id, files, model_call_error, retry_feedback):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc123',\n"
    "        'model': 'test-model',\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'files': files,\n"
    "        'model_call_error': model_call_error,\n"
    "        'refused': None,\n"
    "        'retry_feedback': retry_feedback,\n"
    "        'mode': 'single',\n"
    "        'transcript_sha256': None,\n"
    "        'turns': 1,\n"
    "        'tool_calls': 0,\n"
    "        'isolation': None,\n"
    "    }\n"
    "\n"
    "\n"
    "def _vr(component_id, overall, r2):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'},\n"
    "            {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled', 'result': r2},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass', 'R-FOO-002': r2},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                    'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.0'},\n"
    "                    'lockfile_sha256': None}],\n"
    "        'overall': overall,\n"
    "    }\n"
    "\n"
    "\n"
    "def _attempt(number, outcome, retry_feedback, error_category, surface_ok, overall, failed):\n"
    "    return {'number': number, 'outcome': outcome, 'retry_feedback': retry_feedback,\n"
    "            'error_category': error_category, 'surface_ok': surface_ok,\n"
    "            'overall': overall, 'failed_requirements': failed,\n"
    "            'transcript_sha256': None, 'reauthored_tests': []}\n"
    "\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'event': 'make_closures'})\n"
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
    "    scenario = os.environ['GATE_TEST_SCENARIO']\n"
    "    steps = []\n"
    "    if scenario == 'pass':\n"
    "        g1 = _gen(component_id, {'foo.py': 'x = 1\\n'}, None, None)\n"
    "        v1 = _vr(component_id, 'fail', 'fail')\n"
    "        s1 = SurfaceReport(True, [])\n"
    "        a1 = _attempt(1, 'verification_failed', [], None, True, 'fail', ['R-FOO-002'])\n"
    "        g2 = _gen(component_id, {'foo.py': 'x = 2\\n'}, None, ['R-FOO-002'])\n"
    "        v2 = _vr(component_id, 'pass', 'pass')\n"
    "        s2 = SurfaceReport(True, [])\n"
    "        a2 = _attempt(2, 'passed', ['R-FOO-002'], None, True, 'pass', [])\n"
    "        steps = [(a1, g1, v1, s1), (a2, g2, v2, s2)]\n"
    "        passed, stop = True, 'passed'\n"
    "    elif scenario == 'generation_failed':\n"
    "        g1 = _gen(component_id, {}, {'category': 'network', 'message': 'down'}, None)\n"
    "        a1 = _attempt(1, 'generation_failed', [], 'network', None, None, [])\n"
    "        steps = [(a1, g1, None, None)]\n"
    "        passed, stop = False, 'not_retried'\n"
    "    else:\n"
    "        for n in range(1, max_attempts + 1):\n"
    "            g = _gen(component_id, {'foo.py': 'x = ' + str(n) + '\\n'}, None, None)\n"
    "            s = SurfaceReport(False, [{'kind': 'asset_error',\n"
    "                                       'message': 'static/a.js: no interface file'}])\n"
    "            a = _attempt(n, 'surface_failed', [], None, False, None, [])\n"
    "            steps.append((a, g, None, s))\n"
    "        passed, stop = False, 'max_attempts'\n"
    "    attempts = []\n"
    "    for a, g, v, s in steps:\n"
    "        attempts.append(a)\n"
    "        if on_attempt is not None:\n"
    "            on_attempt(a, g, v)\n"
    "    last_a, last_g, last_v, last_s = steps[-1]\n"
    "    _log({'event': 'run_attempts', 'scenario': scenario,\n"
    "          'gen_id': id(last_g),\n"
    "          'vr_id': id(last_v) if last_v is not None else None,\n"
    "          'sr_id': id(last_s) if last_s is not None else None,\n"
    "          'attempts': attempts,\n"
    "          'attempt_ids': [id(a) for a in attempts],\n"
    "          'gen': last_g, 'vr': last_v})\n"
    "    return AttemptLoopResult(passed, stop, attempts, last_g, last_v, last_s)\n"
)


TRACKER_SRC = COMMON + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    n = len(list(d.iterdir())) + 1\n"
    "    attempt_id = '2026-01-01T00:00:0' + str(n) + 'Z-fake' + str(n)\n"
    "    record = {\n"
    "        'attempt_id': attempt_id,\n"
    "        'component_id': component_id,\n"
    "        'timestamp': '2026-01-01T00:00:0' + str(n) + 'Z',\n"
    "        'spec_bundle_hash': spec_bundle_hash,\n"
    "        'generation': json.loads(json.dumps(generation_result, default=repr)),\n"
    "        'verification': json.loads(json.dumps(verification_report, default=repr)),\n"
    "    }\n"
    "    (d / (attempt_id + '.json')).write_text(json.dumps(record))\n"
    "    _log({'event': 'write_attempt_record', 'component_id': component_id,\n"
    "          'gen_id': id(generation_result),\n"
    "          'vr_id': id(verification_report) if verification_report is not None else None})\n"
    "    return record\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
)


LICENSE_SRC = COMMON + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    result = {\n"
    "        'component_id': component_id,\n"
    "        'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "        'evaluated': False,\n"
    "        'reason': 'no-reference-corpus',\n"
    "        'similarity_score': None,\n"
    "        'block_threshold': None,\n"
    "        'blocked': False,\n"
    "        'matches': [],\n"
    "        'notified': False,\n"
    "        'notification_delivery_error': None,\n"
    "        'cache_hit': False,\n"
    "    }\n"
    "    _log({'event': 'license_scan', 'component_id': component_id, 'result_id': id(result)})\n"
    "    return result\n"
)


SECRET_SRC = COMMON + (
    "@dataclass\n"
    "class SecretScanResult:\n"
    "    scope: str\n"
    "    gate_version: str\n"
    "    flagged: bool\n"
    "    matches: list\n"
    "    allowed: list\n"
    "    unused_allowlist_entries: list\n"
    "    notified: bool\n"
    "    notification_delivery_error: object\n"
    "    cache_hit: bool\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'scope': self.scope, 'gate_version': self.gate_version,\n"
    "                'flagged': self.flagged, 'matches': self.matches,\n"
    "                'allowed': self.allowed,\n"
    "                'unused_allowlist_entries': self.unused_allowlist_entries,\n"
    "                'notified': self.notified,\n"
    "                'notification_delivery_error': self.notification_delivery_error,\n"
    "                'cache_hit': self.cache_hit}\n"
    "\n"
    "\n"
    "def _result(scope):\n"
    "    return SecretScanResult(scope, 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "                            False, [], [], [], False, None, False)\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "\n"
    "def scan(repo_root):\n"
    "    result = _result('full')\n"
    "    _log({'event': 'secret_scan', 'result_id': id(result)})\n"
    "    return result\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return _result('precommit')\n"
    "\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


WRITER_SRC = COMMON + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    ids = {}\n"
    "    for k in ('generation_result', 'verification_report',\n"
    "              'license_scan_result', 'secret_scan_result'):\n"
    "        v = inputs.get(k) if isinstance(inputs, dict) else getattr(inputs, k, None)\n"
    "        ids[k] = id(v) if v is not None else None\n"
    "    history = inputs.get('attempt_history', []) if isinstance(inputs, dict) else []\n"
    "    _log({'event': 'write_provenance', 'component_id': component_id,\n"
    "          'repo_root': str(repo_root),\n"
    "          'inputs_is_dict': isinstance(inputs, dict),\n"
    "          'keys': sorted(inputs.keys()) if isinstance(inputs, dict) else None,\n"
    "          'inputs': inputs if isinstance(inputs, dict) else repr(inputs),\n"
    "          'ids': ids,\n"
    "          'attempt_history_ids': [id(a) for a in history]})\n"
    "    return None\n"
    "\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'event': 'write_sealed_provenance', 'component_id': component_id})\n"
    "    return None\n"
)


VERIFIER_SRC = COMMON + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'event': 'verify', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)


FAKES = {
    "provenance-checker": CHECKER_SRC,
    "spec-bundle-assembler": ASSEMBLER_SRC,
    "generation-loop": LOOP_SRC,
    "provenance-tracker": TRACKER_SRC,
    "license-scanner": LICENSE_SRC,
    "secret-scanner": SECRET_SRC,
    "provenance-writer": WRITER_SRC,
    "verifier-orchestrator": VERIFIER_SRC,
}


def build_repo(tmp_path, monkeypatch, scenario):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for slug, src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(src)
    log = tmp_path / "calls.log"
    log.write_text("")
    monkeypatch.setenv("GATE_TEST_LOG", str(log))
    monkeypatch.setenv("GATE_TEST_SCENARIO", scenario)
    monkeypatch.setattr("sys.dont_write_bytecode", True)
    return repo_root, log


def read_log(log):
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def run(repo_root):
    return component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "test-model")


def test_passing_miss_writes_provenance_once_after_scans(tmp_path, monkeypatch):
    repo_root, log = build_repo(tmp_path, monkeypatch, "pass")
    run(repo_root)
    events = read_log(log)
    names = [e["event"] for e in events]

    writes = [e for e in events if e["event"] == "write_provenance"]
    assert len(writes) == 1, names
    w = writes[0]
    w_idx = names.index("write_provenance")

    assert "license_scan" in names and "secret_scan" in names, names
    assert names.index("license_scan") < w_idx
    assert names.index("secret_scan") < w_idx
    record_idxs = [i for i, n in enumerate(names) if n == "write_attempt_record"]
    assert len(record_idxs) == 2, names
    assert all(i < w_idx for i in record_idxs)

    assert w["component_id"] == COMPONENT_ID
    assert w["inputs_is_dict"] is True
    inputs = w["inputs"]
    assert inputs["component_id"] == COMPONENT_ID
    assert inputs["gate_versions"] == {"verifier": "v@1"}
    assert inputs["provenance_hit"] is False
    assert inputs["attempts"] == 2
    assert len(list((repo_root / ".hotdocs" / "attempts" / COMPONENT_ID).iterdir())) == 2

    loop = [e for e in events if e["event"] == "run_attempts"][0]
    assert inputs["attempt_history"] == loop["attempts"]
    assert len(inputs["attempt_history"]) == 2
    assert w["attempt_history_ids"] == loop["attempt_ids"]

    assert inputs["generation_result"] == loop["gen"]
    assert inputs["verification_report"] == loop["vr"]
    assert w["ids"]["generation_result"] == loop["gen_id"]
    assert w["ids"]["verification_report"] == loop["vr_id"]

    lic = [e for e in events if e["event"] == "license_scan"][0]
    sec = [e for e in events if e["event"] == "secret_scan"][0]
    assert w["ids"]["license_scan_result"] == lic["result_id"]
    assert w["ids"]["secret_scan_result"] == sec["result_id"]
    assert inputs["license_scan_result"]["component_id"] == COMPONENT_ID
    assert inputs["license_scan_result"]["reason"] == "no-reference-corpus"


def test_generation_failed_writes_no_provenance(tmp_path, monkeypatch):
    repo_root, log = build_repo(tmp_path, monkeypatch, "generation_failed")
    run(repo_root)
    names = [e["event"] for e in read_log(log)]
    assert "run_attempts" in names
    assert "write_provenance" not in names, names


def test_surface_failed_writes_no_provenance(tmp_path, monkeypatch):
    repo_root, log = build_repo(tmp_path, monkeypatch, "surface_failed")
    result = run(repo_root)
    events = read_log(log)
    names = [e["event"] for e in events]
    assert "run_attempts" in names
    assert "write_provenance" not in names, names

    assert field(result, "block_reason") == "surface_check_failed"
    assert field(result, "verification") is None
    sr = field(result, "surface_report")
    assert sr is not None
    loop = [e for e in events if e["event"] == "run_attempts"][0]
    assert id(sr) == loop["sr_id"]
    assert field(sr, "ok") is False
    assert field(sr, "findings") == [
        {"kind": "asset_error", "message": "static/a.js: no interface file"}
    ]
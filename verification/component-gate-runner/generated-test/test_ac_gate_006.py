# hotdocs-criterion: sha256:8b2017e052a28f20994148fc2cddd3a7e872aa2adca5b30d4f9ddb2e7a42887f
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
LOG_ENV = "GATE_TEST_LOG_AC_GATE_006"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import dataclasses\n"
    "import json\n"
    "import os\n"
    "\n"
    "\n"
    "def _conv(v):\n"
    "    if hasattr(v, 'to_dict') and callable(getattr(v, 'to_dict')):\n"
    "        return _conv(v.to_dict())\n"
    "    if dataclasses.is_dataclass(v) and not isinstance(v, type):\n"
    "        return dict((f.name, _conv(getattr(v, f.name))) for f in dataclasses.fields(v))\n"
    "    if isinstance(v, dict):\n"
    "        return dict((str(k), _conv(x)) for k, x in v.items())\n"
    "    if isinstance(v, (list, tuple)):\n"
    "        return [_conv(x) for x in v]\n"
    "    return v\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def _get(value, name):\n"
    "    if isinstance(value, dict):\n"
    "        return value.get(name)\n"
    "    return getattr(value, name, None)\n"
    "\n"
    "\n"
)


PROVENANCE_CHECKER = COMMON + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey(\n"
    "        'sha256:abc123',\n"
    "        {'verifier': 'v@1'},\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:def', 'versions': {'python': '3.12.4'},\n"
    "          'lockfile_sha256': None}],\n"
    "    )\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'spec_bundle_hash': spec_bundle_hash,\n"
    "          'gate_versions': _conv(gate_versions)})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance'})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER = COMMON + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'call': 'assemble', 'component_id': component_id, 'mode': mode})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP_BODY = (
    "@dataclasses.dataclass\n"
    "class GenerationResult:\n"
    "    component_id: object = None\n"
    "    spec_bundle_hash: object = None\n"
    "    model: object = None\n"
    "    prompt_version: object = None\n"
    "    cache_hit: object = False\n"
    "    files: object = None\n"
    "    model_call_error: object = None\n"
    "    refused: object = None\n"
    "    retry_feedback: object = None\n"
    "    mode: object = 'single'\n"
    "    transcript_sha256: object = None\n"
    "    turns: object = 1\n"
    "    tool_calls: object = 0\n"
    "    isolation: object = None\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class SurfaceReport:\n"
    "    ok: object = True\n"
    "    findings: object = None\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings or [])}\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class AttemptLoopResult:\n"
    "    passed: object = False\n"
    "    stop_reason: object = None\n"
    "    attempts: object = None\n"
    "    generation_result: object = None\n"
    "    verification_report: object = None\n"
    "    surface_report: object = None\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
    "                'attempts': _conv(self.attempts),\n"
    "                'generation_result': _conv(self.generation_result),\n"
    "                'verification_report': _conv(self.verification_report),\n"
    "                'surface_report': _conv(self.surface_report)}\n"
    "\n"
    "\n"
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "\n"
    "def _gen(component_id, files, mce=None, marker='g'):\n"
    "    return GenerationResult(component_id=component_id, spec_bundle_hash='sha256:abc123',\n"
    "                            model='test-model', prompt_version='v-' + marker,\n"
    "                            cache_hit=False, files=files, model_call_error=mce,\n"
    "                            refused=None, retry_feedback=None)\n"
    "\n"
    "\n"
    "def _vr(component_id, overall, marker):\n"
    "    return {'component_id': component_id,\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "                          'result': 'pass' if overall == 'pass' else 'fail'}],\n"
    "            'requirement_results': {'R-FOO-001': 'pass' if overall == 'pass' else 'fail'},\n"
    "            'interface_drift': False, 'mutation_score': None,\n"
    "            'mutation_error': None, 'assets': [], 'overall': overall,\n"
    "            'marker': marker}\n"
    "\n"
    "\n"
    "def _att(number, outcome, feedback, error_category, surface_ok, overall, failed):\n"
    "    return {'number': number, 'outcome': outcome, 'retry_feedback': feedback,\n"
    "            'error_category': error_category, 'surface_ok': surface_ok,\n"
    "            'overall': overall, 'failed_requirements': failed,\n"
    "            'transcript_sha256': None, 'reauthored_tests': []}\n"
    "\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures'})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'component_id': component_id})\n"
    "    if SCENARIO == 'pass':\n"
    "        gens = [_gen(component_id, {'foo.py': 'x = 1\\n'}, marker='one'),\n"
    "                _gen(component_id, {'foo.py': 'x = 2\\n'}, marker='two')]\n"
    "        vrs = [_vr(component_id, 'fail', 'vr-one'), _vr(component_id, 'pass', 'vr-two')]\n"
    "        surfaces = [SurfaceReport(True, []), SurfaceReport(True, [])]\n"
    "        attempts = [_att(1, 'verification_failed', [], None, True, 'fail', ['R-FOO-001']),\n"
    "                    _att(2, 'passed', ['R-FOO-001'], None, True, 'pass', [])]\n"
    "        passed, stop = True, 'passed'\n"
    "    elif SCENARIO == 'generation_failed':\n"
    "        gens = [_gen(component_id, {}, mce={'category': 'network', 'message': 'down'})]\n"
    "        vrs = [None]\n"
    "        surfaces = [None]\n"
    "        attempts = [_att(1, 'generation_failed', [], 'network', None, None, [])]\n"
    "        passed, stop = False, 'not_retried'\n"
    "    else:\n"
    "        gens = [_gen(component_id, {'foo.py': 'x = 1\\n'})]\n"
    "        vrs = [None]\n"
    "        surfaces = [SurfaceReport(False, [{'kind': 'asset_error',\n"
    "                                           'message': 'static/a.js: no interface file'}])]\n"
    "        attempts = [_att(1, 'surface_failed', [], None, False, None, [])]\n"
    "        passed, stop = False, 'max_attempts'\n"
    "    for a, g, v in zip(attempts, gens, vrs):\n"
    "        if on_attempt is not None:\n"
    "            on_attempt(a, g, v)\n"
    "    result = AttemptLoopResult(passed, stop, attempts, gens[-1], vrs[-1], surfaces[-1])\n"
    "    _log({'call': 'run_attempts_result',\n"
    "          'generation_result': _conv(gens[-1]),\n"
    "          'verification_report': _conv(vrs[-1]),\n"
    "          'attempts': _conv(attempts)})\n"
    "    return result\n"
)


PROVENANCE_TRACKER = COMMON + (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    n = len([p for p in d.iterdir() if p.is_file()]) + 1\n"
    "    stamp = '2026-10-25T14:32:0' + str(n) + 'Z'\n"
    "    record = {'attempt_id': stamp + '-a' + str(n), 'component_id': component_id,\n"
    "              'timestamp': stamp, 'spec_bundle_hash': spec_bundle_hash,\n"
    "              'generation': _conv(generation_result),\n"
    "              'verification': _conv(verification_report)}\n"
    "    (d / (str(n).zfill(4) + '-attempt.json')).write_text(json.dumps(record), encoding='utf-8')\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id,\n"
    "          'spec_bundle_hash': spec_bundle_hash})\n"
    "    return record\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


LICENSE_SCANNER = COMMON + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    result = {'component_id': component_id,\n"
    "              'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "              'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "              'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "              'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "              'cache_hit': False}\n"
    "    _log({'call': 'license_scan', 'result': _conv(result)})\n"
    "    return result\n"
)


SECRET_SCANNER = COMMON + (
    "@dataclasses.dataclass\n"
    "class SecretScanResult:\n"
    "    scope: object = 'full'\n"
    "    gate_version: object = None\n"
    "    flagged: object = False\n"
    "    matches: object = None\n"
    "    allowed: object = None\n"
    "    unused_allowlist_entries: object = None\n"
    "    notified: object = False\n"
    "    notification_delivery_error: object = None\n"
    "    cache_hit: object = False\n"
    "\n"
    "    def to_dict(self):\n"
    "        return dict((f.name, getattr(self, f.name)) for f in dataclasses.fields(self))\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+fake'\n"
    "\n"
    "\n"
    "def scan(repo_root):\n"
    "    result = SecretScanResult('full', 'secret_scanner@3.1.0+fake', False, [], [], [],\n"
    "                              False, None, False)\n"
    "    _log({'call': 'secret_scan', 'result': _conv(result)})\n"
    "    return result\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return SecretScanResult('precommit', None, False, [], [], [], False, None, False)\n"
    "\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER = COMMON + (
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id,\n"
    "          'inputs_is_dict': isinstance(inputs, dict),\n"
    "          'inputs': _conv(inputs)})\n"
    "    return None\n"
    "\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
    "    return None\n"
)


VERIFIER_ORCHESTRATOR = COMMON + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify'})\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)


def write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def build_repo(repo_root, scenario):
    write_fake(repo_root, "provenance-checker", PROVENANCE_CHECKER)
    write_fake(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER)
    write_fake(
        repo_root,
        "generation-loop",
        COMMON + "SCENARIO = " + repr(scenario) + "\n\n\n" + GENERATION_LOOP_BODY,
    )
    write_fake(repo_root, "provenance-tracker", PROVENANCE_TRACKER)
    write_fake(repo_root, "license-scanner", LICENSE_SCANNER)
    write_fake(repo_root, "secret-scanner", SECRET_SCANNER)
    write_fake(repo_root, "provenance-writer", PROVENANCE_WRITER)
    write_fake(repo_root, "verifier-orchestrator", VERIFIER_ORCHESTRATOR)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(tmp_path, monkeypatch, scenario):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_repo(repo_root, scenario)
    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "test-model")
    return repo_root, result, read_log(log_path)


def test_provenance_written_once_after_scans_with_exact_inputs(tmp_path, monkeypatch):
    repo_root, result, log = run(tmp_path, monkeypatch, "pass")
    calls = [e["call"] for e in log]

    assert calls.count("write_provenance") == 1, calls
    wp_index = calls.index("write_provenance")
    assert "license_scan" in calls and "secret_scan" in calls, calls
    assert calls.index("license_scan") < wp_index
    assert calls.index("secret_scan") < wp_index
    record_indices = [i for i, c in enumerate(calls) if c == "write_attempt_record"]
    assert len(record_indices) == 2, calls
    assert all(i < wp_index for i in record_indices)

    attempts_dir = repo_root / ".hotdocs" / "attempts" / COMPONENT_ID
    assert len([p for p in attempts_dir.iterdir() if p.is_file()]) == 2

    wp = log[wp_index]
    assert wp["component_id"] == COMPONENT_ID
    inputs = wp["inputs"]
    loop_result = next(e for e in log if e["call"] == "run_attempts_result")
    license_result = next(e for e in log if e["call"] == "license_scan")["result"]
    secret_result = next(e for e in log if e["call"] == "secret_scan")["result"]

    assert inputs["component_id"] == COMPONENT_ID
    assert inputs["gate_versions"] == {"verifier": "v@1"}
    assert inputs["provenance_hit"] is False
    assert inputs["attempts"] == 2
    assert inputs["attempt_history"] == loop_result["attempts"]
    assert len(inputs["attempt_history"]) == 2
    assert inputs["generation_result"] == loop_result["generation_result"]
    assert inputs["verification_report"] == loop_result["verification_report"]
    assert inputs["license_scan_result"] == license_result
    assert inputs["secret_scan_result"] == secret_result

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False


def test_no_provenance_when_last_generation_has_no_files(tmp_path, monkeypatch):
    repo_root, result, log = run(tmp_path, monkeypatch, "generation_failed")
    calls = [e["call"] for e in log]
    assert "run_attempts" in calls, calls
    assert "write_provenance" not in calls, calls
    assert field(result, "blocked") is True


def test_no_provenance_on_surface_failure(tmp_path, monkeypatch):
    repo_root, result, log = run(tmp_path, monkeypatch, "surface_failed")
    calls = [e["call"] for e in log]
    assert "run_attempts" in calls, calls
    assert "write_provenance" not in calls, calls

    assert field(result, "block_reason") == "surface_check_failed"
    assert field(result, "verification") is None
    surface = field(result, "surface_report")
    assert surface is not None
    assert field(surface, "ok") is False
    assert list(field(surface, "findings")) == [
        {"kind": "asset_error", "message": "static/a.js: no interface file"}
    ]
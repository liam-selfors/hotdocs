# hotdocs-criterion: sha256:5732a44a13180b88129fb12dcf3c722af9b3fc92de0131416023dbc60bfb5234
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"

EXPECTED_ATTEMPTS = [
    {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
     "error_category": None, "surface_ok": True, "overall": "fail",
     "failed_requirements": ["R-FOO-002"], "transcript_sha256": None,
     "reauthored_tests": []},
    {"number": 2, "outcome": "passed", "retry_feedback": ["R-FOO-002"],
     "error_category": None, "surface_ok": True, "overall": "pass",
     "failed_requirements": [], "transcript_sha256": None,
     "reauthored_tests": []},
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import os\n"
    "import json\n"
    "def _log(name):\n"
    "    with open(os.environ['HOTDOCS_FAKE_LOG'], 'a') as f:\n"
    "        f.write(name + '\\n')\n"
    "\n"
)


PROVENANCE_CHECKER_SRC = LOG_HELPER + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key')\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key')\n"
    "    return ProvenanceKey(\n"
    "        'sha256:abc123',\n"
    "        {'compiler': 'criterion-compiler@1.0.0',\n"
    "         'generated_test': 'generated_test@1.0.0',\n"
    "         'verifier': 'verifier-orchestrator@2.0.0',\n"
    "         'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "         'secret_scanner': 'secret_scanner@0.0.0',\n"
    "         'generator': 'generator@3.0.0+v11'},\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:abc', 'versions': {'python': '3.12.4'},\n"
    "          'lockfile_sha256': None}],\n"
    "    )\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance')\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance')\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble')\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "            'spec': 'spec', 'interface': 'interface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion')\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP_SRC = LOG_HELPER + (
    "import dataclasses\n"
    "\n"
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
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
    "@dataclasses.dataclass\n"
    "class VerificationReport:\n"
    "    component_id: object = None\n"
    "    criteria: object = None\n"
    "    requirement_results: object = None\n"
    "    interface_drift: object = False\n"
    "    mutation_score: object = None\n"
    "    mutation_error: object = None\n"
    "    assets: object = None\n"
    "    overall: object = None\n"
    "    def to_dict(self):\n"
    "        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class SurfaceReport:\n"
    "    ok: object = True\n"
    "    findings: object = None\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings or [])}\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class AttemptLoopResult:\n"
    "    passed: object = False\n"
    "    stop_reason: object = None\n"
    "    attempts: object = None\n"
    "    generation_result: object = None\n"
    "    verification_report: object = None\n"
    "    surface_report: object = None\n"
    "    def to_dict(self):\n"
    "        def conv(v):\n"
    "            return v.to_dict() if hasattr(v, 'to_dict') else (dataclasses.asdict(v) if dataclasses.is_dataclass(v) else v)\n"
    "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
    "                'attempts': self.attempts,\n"
    "                'generation_result': conv(self.generation_result),\n"
    "                'verification_report': conv(self.verification_report),\n"
    "                'surface_report': conv(self.surface_report)}\n"
    "\n"
    "def _gen(component_id, files):\n"
    "    return GenerationResult(component_id=component_id, spec_bundle_hash='sha256:abc123',\n"
    "        model='fake-model', prompt_version='v1', cache_hit=False, files=files,\n"
    "        model_call_error=None, refused=None, retry_feedback=None, mode='single',\n"
    "        transcript_sha256=None, turns=1, tool_calls=0, isolation=None)\n"
    "\n"
    "def _report(component_id, overall):\n"
    "    result = 'pass' if overall == 'pass' else 'fail'\n"
    "    crit = {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled', 'result': result}\n"
    "    if result == 'fail':\n"
    "        crit['failure_detail'] = {'message': 'x failed', 'expected': 1, 'actual': 2}\n"
    "        crit['failure_origin'] = 'implementation'\n"
    "    return VerificationReport(component_id=component_id, criteria=[crit],\n"
    "        requirement_results={'R-FOO-002': result}, interface_drift=False,\n"
    "        mutation_score=None, mutation_error=None,\n"
    "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                 'adapter_sha256': 'sha256:abc', 'versions': {'python': '3.12.4'},\n"
    "                 'lockfile_sha256': None}],\n"
    "        overall=overall)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts')\n"
    "    attempts = [\n"
    "        {'number': 1, 'outcome': 'verification_failed', 'retry_feedback': [],\n"
    "         'error_category': None, 'surface_ok': True, 'overall': 'fail',\n"
    "         'failed_requirements': ['R-FOO-002'], 'transcript_sha256': None,\n"
    "         'reauthored_tests': []},\n"
    "        {'number': 2, 'outcome': 'passed', 'retry_feedback': ['R-FOO-002'],\n"
    "         'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "         'failed_requirements': [], 'transcript_sha256': None,\n"
    "         'reauthored_tests': []},\n"
    "    ]\n"
    "    gen1 = _gen(component_id, {'foo.py': 'x = 1\\n'})\n"
    "    rep1 = _report(component_id, 'fail')\n"
    "    gen2 = _gen(component_id, {'foo.py': 'x = 2\\n'})\n"
    "    rep2 = _report(component_id, 'pass')\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempts[0], gen1, rep1)\n"
    "        on_attempt(attempts[1], gen2, rep2)\n"
    "    return AttemptLoopResult(passed=True, stop_reason='passed', attempts=attempts,\n"
    "        generation_result=gen2, verification_report=rep2,\n"
    "        surface_report=SurfaceReport(ok=True, findings=[]))\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures')\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


PROVENANCE_TRACKER_SRC = LOG_HELPER + (
    "from pathlib import Path\n"
    "_counter = [0]\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record')\n"
    "    _counter[0] += 1\n"
    "    n = _counter[0]\n"
    "    attempt_id = '2026-11-24T00:00:0' + str(n) + 'Z-fake' + str(n)\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    record = {'attempt_id': attempt_id, 'component_id': component_id,\n"
    "              'timestamp': '2026-11-24T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "              'generation': {}, 'verification': None}\n"
    "    (d / (attempt_id + '.json')).write_text(json.dumps(record))\n"
    "    return record\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness')\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures')\n"
    "    return []\n"
)


LICENSE_SCANNER_SRC = LOG_HELPER + (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan')\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "            'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)


SECRET_SCANNER_SRC = LOG_HELPER + (
    "import dataclasses\n"
    "\n"
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
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
    "    def to_dict(self):\n"
    "        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}\n"
    "\n"
    "def _result(scope):\n"
    "    return SecretScanResult(scope=scope, gate_version='secret_scanner@0.0.0',\n"
    "        flagged=False, matches=[], allowed=[], unused_allowlist_entries=[],\n"
    "        notified=False, notification_delivery_error=None, cache_hit=False)\n"
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


PROVENANCE_WRITER_SRC = LOG_HELPER + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance')\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance')\n"
    "    return None\n"
)


VERIFIER_ORCHESTRATOR_SRC = LOG_HELPER + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify')\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)


def _write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


def test_ac_gate_003a_loop_result_passed_through_unchanged(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    monkeypatch.setenv("HOTDOCS_FAKE_LOG", str(log_path))

    _write_fake(repo_root, "provenance-checker", PROVENANCE_CHECKER_SRC)
    _write_fake(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write_fake(repo_root, "generation-loop", GENERATION_LOOP_SRC)
    _write_fake(repo_root, "provenance-tracker", PROVENANCE_TRACKER_SRC)
    _write_fake(repo_root, "license-scanner", LICENSE_SCANNER_SRC)
    _write_fake(repo_root, "secret-scanner", SECRET_SCANNER_SRC)
    _write_fake(repo_root, "provenance-writer", PROVENANCE_WRITER_SRC)
    _write_fake(repo_root, "verifier-orchestrator", VERIFIER_ORCHESTRATOR_SRC)

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "fake-model"
    )

    calls = [line for line in log_path.read_text().splitlines() if line]
    assert calls.count("run_attempts") == 1, calls

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert list(field(result, "attempts")) == EXPECTED_ATTEMPTS
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
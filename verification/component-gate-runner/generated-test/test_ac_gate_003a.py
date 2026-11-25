# hotdocs-criterion: sha256:8b89f9c71d36a2ea915118efc63c5a1c359cc73a7d78945abd56b303a4d02efa
"""AC-GATE-003a: on a provenance miss, run_component_gates calls the
generation loop's run_attempts exactly once and passes its attempts list,
last generation result and last verification report through unchanged
(R-GATE-003)."""

import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-widget"

ATTEMPTS = [
    {"number": 1, "outcome": "verification_failed", "retry_feedback": [],
     "error_category": None, "surface_ok": True, "overall": "fail",
     "failed_requirements": ["R-WIDGET-001"], "transcript_sha256": None,
     "reauthored_tests": []},
    {"number": 2, "outcome": "passed", "retry_feedback": ["R-WIDGET-001"],
     "error_category": None, "surface_ok": True, "overall": "pass",
     "failed_requirements": [], "transcript_sha256": None,
     "reauthored_tests": []},
]

HASH = "sha256:" + "0" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _common_header(log_path):
    return (
        "import json\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "def _log(name, **kw):\n"
        "    entry = dict(kw)\n"
        "    entry['call'] = name\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry, default=str) + '\\n')\n"
    )


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source, encoding="utf-8")


def _build_fakes(repo_root, log_path):
    header = _common_header(log_path)

    provenance_checker = (
        header
        + "HASH = " + repr(HASH) + "\n"
        + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        + "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "               'adapter_sha256': HASH, 'versions': {'python': '3.12.4'},\n"
        "               'lockfile_sha256': None}]\n"
        "    return ProvenanceKey(HASH, dict(GATE_VERSIONS), assets)\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )
    _write(repo_root, "provenance-checker", provenance_checker)

    assembler = (
        header
        + "HASH = " + repr(HASH) + "\n"
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': HASH,\n"
        "            'spec': 'spec', 'interface': 'interface', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
        "            'testing': ''}\n"
    )
    _write(repo_root, "spec-bundle-assembler", assembler)

    loop = (
        header
        + "ATTEMPTS = " + repr(ATTEMPTS) + "\n"
        + "HASH = " + repr(HASH) + "\n"
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "class AttemptLoopResult:\n"
        "    def __init__(self, passed, stop_reason, attempts, generation_result,\n"
        "                 verification_report, surface_report):\n"
        "        self.passed = passed\n"
        "        self.stop_reason = stop_reason\n"
        "        self.attempts = attempts\n"
        "        self.generation_result = generation_result\n"
        "        self.verification_report = verification_report\n"
        "        self.surface_report = surface_report\n"
        "    def to_dict(self):\n"
        "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
        "                'attempts': self.attempts,\n"
        "                'generation_result': self.generation_result,\n"
        "                'verification_report': self.verification_report,\n"
        "                'surface_report': self.surface_report}\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
        "def _gen(component_id):\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': HASH,\n"
        "            'model': 'claude-sonnet-5', 'prompt_version': 'v12', 'cache_hit': False,\n"
        "            'files': {'widget.py': 'VALUE = 1\\n'}, 'model_call_error': None,\n"
        "            'refused': None, 'retry_feedback': None, 'mode': 'single',\n"
        "            'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
        "def _report(component_id, overall):\n"
        "    result = 'pass' if overall == 'pass' else 'fail'\n"
        "    crit = {'id': 'AC-WIDGET-001', 'covers': 'R-WIDGET-001', 'kind': 'compiled',\n"
        "            'result': result}\n"
        "    if result == 'fail':\n"
        "        crit['failure_detail'] = {'message': 'x failed', 'expected': 1, 'actual': 2}\n"
        "        crit['failure_origin'] = 'implementation'\n"
        "    return {'component_id': component_id, 'criteria': [crit],\n"
        "            'requirement_results': {'R-WIDGET-001': result},\n"
        "            'interface_drift': False, 'mutation_score': 0.9, 'mutation_error': None,\n"
        "            'assets': [], 'overall': overall}\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model, mode=mode,\n"
        "         max_attempts=max_attempts)\n"
        "    gen1 = _gen(component_id)\n"
        "    rep1 = _report(component_id, 'fail')\n"
        "    gen2 = _gen(component_id)\n"
        "    rep2 = _report(component_id, 'pass')\n"
        "    surf = {'ok': True, 'findings': []}\n"
        "    if on_attempt is not None:\n"
        "        on_attempt(ATTEMPTS[0], gen1, rep1)\n"
        "        on_attempt(ATTEMPTS[1], gen2, rep2)\n"
        "    return AttemptLoopResult(True, 'passed', ATTEMPTS, gen2, rep2, surf)\n"
    )
    _write(repo_root, "generation-loop", loop)

    tracker = (
        header
        + "import os\n"
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id)\n"
        "    d = os.path.join(str(repo_root), '.hotdocs', 'attempts', component_id)\n"
        "    os.makedirs(d, exist_ok=True)\n"
        "    n = len(os.listdir(d)) + 1\n"
        "    stamp = '2026-11-25T00:00:0' + str(n) + 'Z'\n"
        "    record = {'attempt_id': stamp + '-a' + str(n), 'component_id': component_id,\n"
        "              'timestamp': stamp, 'spec_bundle_hash': spec_bundle_hash,\n"
        "              'generation': generation_result, 'verification': verification_report}\n"
        "    with open(os.path.join(d, record['attempt_id'] + '.json'), 'w') as fh:\n"
        "        fh.write(json.dumps(record, default=str))\n"
        "    return record\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root, "provenance-tracker", tracker)

    license_scanner = (
        header
        + "GV = 'license_scanner@4.0.0-no-reference-corpus'\n"
        "def gate_version(repo_root):\n"
        "    return GV\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return {'component_id': component_id, 'gate_version': GV, 'evaluated': False,\n"
        "            'reason': 'no-reference-corpus', 'similarity_score': None,\n"
        "            'block_threshold': None, 'blocked': False, 'matches': [],\n"
        "            'notified': False, 'notification_delivery_error': None,\n"
        "            'cache_hit': False}\n"
    )
    _write(repo_root, "license-scanner", license_scanner)

    secret_scanner = (
        header
        + "GV = 'secret_scanner@0.0.0'\n"
        "class SecretScanResult:\n"
        "    def __init__(self, scope):\n"
        "        self.scope = scope\n"
        "        self.gate_version = GV\n"
        "        self.flagged = False\n"
        "        self.matches = []\n"
        "        self.allowed = []\n"
        "        self.unused_allowlist_entries = []\n"
        "        self.notified = False\n"
        "        self.notification_delivery_error = None\n"
        "        self.cache_hit = False\n"
        "    def to_dict(self):\n"
        "        return dict(vars(self))\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "def gate_version(repo_root):\n"
        "    return GV\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return SecretScanResult('full')\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return SecretScanResult('precommit')\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
    )
    _write(repo_root, "secret-scanner", secret_scanner)

    writer = (
        header
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
    _write(repo_root, "provenance-writer", writer)

    verifier = (
        header
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
        "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
        "            'assets': [], 'overall': 'pass'}\n"
    )
    _write(repo_root, "verifier-orchestrator", verifier)


def _calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gate_003a_loop_result_passed_through_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_fakes(repo_root, log_path)

    result = component_gate_runner.run_component_gates(
        COMPONENT_ID, repo_root, "claude-sonnet-5"
    )

    calls = _calls(log_path)
    run_attempts_calls = [c for c in calls if c["call"] == "run_attempts"]
    assert len(run_attempts_calls) == 1, calls

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None

    attempts = field(result, "attempts")
    assert list(attempts) == ATTEMPTS
    assert len(attempts) == 2
    assert [field(a, "number") for a in attempts] == [1, 2]
    assert [field(a, "outcome") for a in attempts] == ["verification_failed", "passed"]

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
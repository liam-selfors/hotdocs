# hotdocs-criterion: sha256:bbf92a729485052c2f2fe61c1ee883700a232cf0c2309d20964de4cd43c5c9d7
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
    "def _log(name, data):\n"
    "    entry = {'call': name}\n"
    "    entry.update(data)\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as f:\n"
    "        f.write(json.dumps(entry, default=repr) + '\\n')\n"
    "\n"
)


PROVENANCE_CHECKER = COMMON + (
    "class _Key:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:abc123'\n"
    "        self.gate_versions = {\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        }\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.0'},\n"
    "                        'lockfile_sha256': None}]\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', {'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', {'component_id': component_id})\n"
    "    return _Key()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', {'component_id': component_id})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', {'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER = COMMON + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', {'component_id': component_id, 'mode': mode})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', {'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '',\n"
    "            'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP = COMMON + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "class AttemptLoopResult:\n"
    "    def __init__(self, passed, stop_reason, attempts, generation_result,\n"
    "                 verification_report, surface_report):\n"
    "        self.passed = passed\n"
    "        self.stop_reason = stop_reason\n"
    "        self.attempts = attempts\n"
    "        self.generation_result = generation_result\n"
    "        self.verification_report = verification_report\n"
    "        self.surface_report = surface_report\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
    "                'attempts': self.attempts, 'generation_result': self.generation_result,\n"
    "                'verification_report': self.verification_report,\n"
    "                'surface_report': self.surface_report}\n"
    "\n"
    "def _gen(component_id, feedback):\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "            'model': 'test-model', 'prompt_version': 'v11', 'cache_hit': False,\n"
    "            'files': {'foo.py': 'x = 1\\n'}, 'model_call_error': None, 'refused': None,\n"
    "            'retry_feedback': feedback, 'mode': 'single', 'transcript_sha256': None,\n"
    "            'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "\n"
    "def _report(component_id):\n"
    "    return {'component_id': component_id,\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "                          'result': 'fail', 'failure_origin': 'implementation',\n"
    "                          'failure_detail': {'message': 'm', 'expected': 1, 'actual': 2}}],\n"
    "            'requirement_results': {'R-FOO-001': 'fail'}, 'interface_drift': False,\n"
    "            'mutation_score': None, 'mutation_error': None, 'assets': [],\n"
    "            'overall': 'fail'}\n"
    "\n"
    "def _surface():\n"
    "    return {'ok': True, 'findings': []}\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', {'component_id': component_id, 'model': model, 'mode': mode,\n"
    "                          'max_attempts': max_attempts, 'retry_feedback': retry_feedback,\n"
    "                          'seed': seed, 'allow_unisolated_exec': allow_unisolated_exec})\n"
    "    attempts = []\n"
    "    gen = None\n"
    "    rep = None\n"
    "    for n in (1, 2, 3):\n"
    "        fb = [] if n == 1 else ['R-FOO-001']\n"
    "        gen = _gen(component_id, fb or None)\n"
    "        rep = _report(component_id)\n"
    "        attempt = {'number': n, 'outcome': 'verification_failed', 'retry_feedback': fb,\n"
    "                   'error_category': None, 'surface_ok': True, 'overall': 'fail',\n"
    "                   'failed_requirements': ['R-FOO-001'], 'transcript_sha256': None,\n"
    "                   'reauthored_tests': []}\n"
    "        attempts.append(attempt)\n"
    "        if on_attempt is not None:\n"
    "            on_attempt(attempt, gen, rep)\n"
    "    return AttemptLoopResult(False, 'max_attempts', attempts, gen, rep, _surface())\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', {'model': model})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


PROVENANCE_TRACKER = COMMON + (
    "from pathlib import Path\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', {'component_id': component_id})\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    n = len(list(d.iterdir())) + 1\n"
    "    attempt_id = '2026-01-01T00:00:0' + str(n) + 'Z-a' + str(n)\n"
    "    record = {'attempt_id': attempt_id, 'component_id': component_id,\n"
    "              'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "              'generation': dict(generation_result),\n"
    "              'verification': dict(verification_report) if verification_report else None}\n"
    "    (d / (attempt_id + '.json')).write_text(json.dumps(record, default=repr))\n"
    "    return record\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
)


LICENSE_SCANNER = COMMON + (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', {'component_id': component_id})\n"
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


SECRET_SCANNER = COMMON + (
    "def scan(repo_root):\n"
    "    _log('secret_scan', {})\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
    "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
)


PROVENANCE_WRITER = COMMON + (
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', {'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', {'component_id': component_id})\n"
    "    return None\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generation-loop": GENERATION_LOOP,
    "provenance-tracker": PROVENANCE_TRACKER,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-writer": PROVENANCE_WRITER,
}


def _write_fakes(repo_root):
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_003b_run_attempts_called_once_and_blocked(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fakes(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "test-model"
    )

    calls = _read_log(log_path)
    run_calls = [c for c in calls if c["call"] == "run_attempts"]
    assert len(run_calls) == 1, calls
    assert run_calls[0]["retry_feedback"] is None
    assert run_calls[0]["max_attempts"] == 3

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"

    attempts = field(result, "attempts")
    assert len(attempts) == 3
    assert [field(a, "number") for a in attempts] == [1, 2, 3]
    assert field(attempts[-1], "outcome") == "verification_failed"
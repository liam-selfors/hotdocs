# hotdocs-criterion: sha256:385fc3867a5041a8e5807e1e8ae9c3f110c92742d78e41939692313f495e62a7
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_AC_GATE_005_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(fn, *args):\n"
    "    path = os.environ[" + repr(LOG_ENV) + "]\n"
    "    with open(path, 'a') as fh:\n"
    "        fh.write(json.dumps({'fn': fn, 'args': [str(a) for a in args],"
    " 'types': [type(a).__name__ for a in args]}) + '\\n')\n"
    "\n"
)


def _verification_report_source():
    return (
        "def _report(overall):\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}],\n"
        "        'requirement_results': {'R-FOO-001': 'pass'},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 0.9,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'overall': overall,\n"
        "    }\n"
        "\n"
    )


def _provenance_checker_source(hit):
    return (
        LOG_HELPER
        + _verification_report_source()
        + "HIT = " + repr(hit) + "\n"
        "\n"
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "GATE_VERSIONS = {\n"
        "    'compiler': 'criterion-compiler@1.0.0',\n"
        "    'generated_test': 'generated_test@1.0.0',\n"
        "    'verifier': 'verifier-orchestrator@2.0.0',\n"
        "    'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
        "    'secret_scanner': 'secret_scanner@0.0.0',\n"
        "    'generator': 'generator@3.0.0+v11',\n"
        "}\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id, repo_root)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id, repo_root)\n"
        "    return ProvenanceKey('sha256:abc123', dict(GATE_VERSIONS),\n"
        "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "          'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.0'},\n"
        "          'lockfile_sha256': None}])\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id, spec_bundle_hash, repo_root)\n"
        "    if HIT:\n"
        "        return {\n"
        "            'hit': True,\n"
        "            'reason': None,\n"
        "            'verification_report': _report('pass'),\n"
        "            'license_scan': {\n"
        "                'component_id': component_id,\n"
        "                'gate_version': 'license_scanner@4.0.0-cached',\n"
        "                'evaluated': False, 'reason': 'no-reference-corpus',\n"
        "                'similarity_score': None, 'block_threshold': None,\n"
        "                'blocked': False, 'matches': [], 'notified': False,\n"
        "                'notification_delivery_error': None, 'cache_hit': False,\n"
        "            },\n"
        "            'secret_scan': {\n"
        "                'scope': 'full', 'gate_version': 'secret_scanner@cached',\n"
        "                'flagged': False, 'matches': [], 'allowed': [],\n"
        "                'unused_allowlist_entries': [], 'notified': False,\n"
        "                'notification_delivery_error': None, 'cache_hit': False,\n"
        "            },\n"
        "        }\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id, repo_root)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


SPEC_BUNDLE_ASSEMBLER_SOURCE = (
    LOG_HELPER
    + "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id, repo_root, mode)\n"
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
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id, criterion_id, repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP_SOURCE = (
    LOG_HELPER
    + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "    'missing_asset', 'malformed_layout')\n"
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
    "                'attempts': self.attempts,\n"
    "                'generation_result': self.generation_result,\n"
    "                'verification_report': self.verification_report,\n"
    "                'surface_report': self.surface_report}\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id, repo_root, model)\n"
    "    generation_result = {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc123',\n"
    "        'model': model,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'files': {},\n"
    "        'model_call_error': {'category': 'truncated_response', 'message': 'cut off'},\n"
    "        'refused': None,\n"
    "        'retry_feedback': retry_feedback,\n"
    "        'mode': 'single',\n"
    "        'transcript_sha256': None,\n"
    "        'turns': 1,\n"
    "        'tool_calls': 0,\n"
    "        'isolation': None,\n"
    "    }\n"
    "    attempt = {'number': 1, 'outcome': 'generation_failed', 'retry_feedback': [],\n"
    "               'error_category': 'truncated_response', 'surface_ok': None,\n"
    "               'overall': None, 'failed_requirements': [],\n"
    "               'transcript_sha256': None, 'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, None)\n"
    "    return AttemptLoopResult(False, 'not_retried', [attempt], generation_result, None, None)\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model, seed, repo_root)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


PROVENANCE_TRACKER_SOURCE = (
    LOG_HELPER
    + "from pathlib import Path\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id, spec_bundle_hash, repo_root)\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / component_id\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    n = len(list(d.iterdir())) + 1\n"
    "    record = {'attempt_id': '2026-01-01T00:00:0' + str(n) + 'Z-a',\n"
    "              'component_id': component_id,\n"
    "              'timestamp': '2026-01-01T00:00:00Z',\n"
    "              'spec_bundle_hash': spec_bundle_hash,\n"
    "              'generation': {'files': {}}, 'verification': None}\n"
    "    (d / (record['attempt_id'] + '.json')).write_text(json.dumps(record))\n"
    "    return record\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness', repo_root)\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', component_id, repo_root)\n"
    "    return []\n"
)


LICENSE_SCANNER_SOURCE = (
    LOG_HELPER
    + "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id, repo_root)\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'gate_version': 'license_scanner@4.0.0-fake-marker',\n"
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
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-fake-marker'\n"
)


SECRET_SCANNER_SOURCE = (
    LOG_HELPER
    + "class SecretScanResult:\n"
    "    def __init__(self, scope, gate_version, flagged, matches, allowed,\n"
    "                 unused_allowlist_entries, notified, notification_delivery_error,\n"
    "                 cache_hit):\n"
    "        self.scope = scope\n"
    "        self.gate_version = gate_version\n"
    "        self.flagged = flagged\n"
    "        self.matches = matches\n"
    "        self.allowed = allowed\n"
    "        self.unused_allowlist_entries = unused_allowlist_entries\n"
    "        self.notified = notified\n"
    "        self.notification_delivery_error = notification_delivery_error\n"
    "        self.cache_hit = cache_hit\n"
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
    "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root)\n"
    "    return SecretScanResult('full', 'secret_scanner@fake-marker', False, [], [], [],\n"
    "                            False, None, False)\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', repo_root)\n"
    "    return SecretScanResult('precommit', 'secret_scanner@fake-marker', False, [], [], [],\n"
    "                            False, None, False)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@fake-marker'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER_SOURCE = (
    LOG_HELPER
    + "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id, repo_root)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id, repo_root)\n"
    "    return None\n"
)


VERIFIER_ORCHESTRATOR_SOURCE = (
    LOG_HELPER
    + _verification_report_source()
    + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id, repo_root)\n"
    "    return _report('pass')\n"
)


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


def _build(tmp_path, monkeypatch, hit):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    log.write_text("")
    monkeypatch.setenv(LOG_ENV, str(log))
    _write(repo_root, "provenance-checker", _provenance_checker_source(hit))
    _write(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER_SOURCE)
    _write(repo_root, "generation-loop", GENERATION_LOOP_SOURCE)
    _write(repo_root, "provenance-tracker", PROVENANCE_TRACKER_SOURCE)
    _write(repo_root, "license-scanner", LICENSE_SCANNER_SOURCE)
    _write(repo_root, "secret-scanner", SECRET_SCANNER_SOURCE)
    _write(repo_root, "provenance-writer", PROVENANCE_WRITER_SOURCE)
    _write(repo_root, "verifier-orchestrator", VERIFIER_ORCHESTRATOR_SOURCE)
    return repo_root, log


def _calls(log):
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def test_miss_with_generation_failed_invokes_both_scanners(tmp_path, monkeypatch):
    repo_root, log = _build(tmp_path, monkeypatch, hit=False)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model")

    calls = _calls(log)
    license_calls = [c for c in calls if c["fn"] == "license_scan"]
    secret_calls = [c for c in calls if c["fn"] == "secret_scan"]
    assert len(license_calls) == 1, calls
    assert len(secret_calls) == 1, calls
    assert license_calls[0]["args"] == ["comp-foo", str(repo_root)]
    assert license_calls[0]["types"][1] == type(repo_root).__name__
    assert secret_calls[0]["args"] == [str(repo_root)]
    assert secret_calls[0]["types"][0] == type(repo_root).__name__

    license_scan = field(result, "license_scan")
    secret_scan = field(result, "secret_scan")
    assert license_scan is not None
    assert secret_scan is not None
    assert field(license_scan, "gate_version") == "license_scanner@4.0.0-fake-marker"
    assert field(license_scan, "component_id") == "comp-foo"
    assert field(secret_scan, "gate_version") == "secret_scanner@fake-marker"
    assert field(secret_scan, "scope") == "full"
    assert field(result, "provenance_hit") is False


def test_short_circuiting_hit_calls_neither_scanner(tmp_path, monkeypatch):
    repo_root, log = _build(tmp_path, monkeypatch, hit=True)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model")

    calls = _calls(log)
    assert [c for c in calls if c["fn"] == "license_scan"] == [], calls
    assert [c for c in calls if c["fn"] == "secret_scan"] == [], calls
    assert any(c["fn"] == "check_provenance" for c in calls), calls
    assert field(result, "provenance_hit") is True
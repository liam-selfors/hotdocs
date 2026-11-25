# hotdocs-criterion: sha256:a8b1c10b8cc855a9c830487f82d0be6c4040d9009f533caa4f97d489f585ae71
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_TEST_FAKE_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(*parts):\n"
    "    p = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    if p:\n"
    "        with open(p, 'a') as f:\n"
    "            f.write(json.dumps([str(x) for x in parts]) + '\\n')\n"
    "\n"
    "class _Obj:\n"
    "    def __init__(self, **kw):\n"
    "        self._fields = list(kw)\n"
    "        for k, v in kw.items():\n"
    "            setattr(self, k, v)\n"
    "    def to_dict(self):\n"
    "        out = {}\n"
    "        for k in self._fields:\n"
    "            v = getattr(self, k)\n"
    "            out[k] = v.to_dict() if hasattr(v, 'to_dict') else v\n"
    "        return out\n"
    "\n"
)


GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}

SPEC_HASH = "sha256:" + "ab" * 32

LICENSE_MARKER = "license_scanner@4.0.0-no-reference-corpus"
SECRET_MARKER = "secret_scanner@9.9.9+fake-marker"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def provenance_checker_source(hit):
    if hit:
        check_body = (
            "    _log('check_provenance', component_id, spec_bundle_hash, repo_root)\n"
            "    return {\n"
            "        'hit': True,\n"
            "        'reason': None,\n"
            "        'verification_report': {\n"
            "            'component_id': component_id, 'criteria': [],\n"
            "            'requirement_results': {}, 'interface_drift': False,\n"
            "            'mutation_score': 0.9, 'mutation_error': None,\n"
            "            'assets': [], 'overall': 'pass'},\n"
            "        'license_scan': {\n"
            "            'component_id': component_id,\n"
            "            'gate_version': 'license_scanner@4.0.0-stored',\n"
            "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
            "            'similarity_score': None, 'block_threshold': None,\n"
            "            'blocked': False, 'matches': [], 'notified': False,\n"
            "            'notification_delivery_error': None, 'cache_hit': False},\n"
            "        'secret_scan': {\n"
            "            'scope': 'full', 'gate_version': 'secret_scanner@0.0.0',\n"
            "            'flagged': False, 'matches': [], 'allowed': [],\n"
            "            'unused_allowlist_entries': [], 'notified': False,\n"
            "            'notification_delivery_error': None, 'cache_hit': False},\n"
            "    }\n"
        )
    else:
        check_body = (
            "    _log('check_provenance', component_id, spec_bundle_hash, repo_root)\n"
            "    return {'hit': False, 'reason': 'no manifest',\n"
            "            'verification_report': None, 'license_scan': None,\n"
            "            'secret_scan': None}\n"
        )
    return (
        LOG_HELPER
        + "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id, repo_root)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id, repo_root)\n"
        "    return ProvenanceKey(" + repr(SPEC_HASH) + ", " + repr(GATE_VERSIONS) + ",\n"
        "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "          'adapter_sha256': None, 'versions': {}, 'lockfile_sha256': None}])\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        + check_body
        + "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id, repo_root)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None,\n"
        "            'secret_scan': None, 'owners': None, 'source_hash': None,\n"
        "            'written_at': None}\n"
    )


ASSEMBLER_SOURCE = (
    LOG_HELPER
    + "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id, repo_root, mode)\n"
    "    return {'component_id': component_id,\n"
    "            'spec_bundle_hash': " + repr(SPEC_HASH) + ",\n"
    "            'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id, criterion_id, repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)


GENERATION_LOOP_SOURCE = (
    LOG_HELPER
    + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id, repo_root, model)\n"
    "    gen = _Obj(component_id=component_id, spec_bundle_hash=" + repr(SPEC_HASH) + ",\n"
    "               model=model, prompt_version='v1', cache_hit=False, files={},\n"
    "               model_call_error={'category': 'network', 'message': 'down'},\n"
    "               refused=None, retry_feedback=retry_feedback, mode='single',\n"
    "               transcript_sha256=None, turns=1, tool_calls=0, isolation=None)\n"
    "    attempt = {'number': 1, 'outcome': 'generation_failed', 'retry_feedback': [],\n"
    "               'error_category': 'network', 'surface_ok': None, 'overall': None,\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    return _Obj(passed=False, stop_reason='not_retried', attempts=[attempt],\n"
    "                generation_result=gen, verification_report=None,\n"
    "                surface_report=None)\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model, seed, repo_root)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


LICENSE_SOURCE = (
    LOG_HELPER
    + "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id, repo_root)\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': " + repr(LICENSE_MARKER) + ",\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None,\n"
    "            'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return " + repr(LICENSE_MARKER) + "\n"
)


SECRET_SOURCE = (
    LOG_HELPER
    + "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root)\n"
    "    return _Obj(scope='full', gate_version=" + repr(SECRET_MARKER) + ",\n"
    "                flagged=False, matches=[], allowed=[],\n"
    "                unused_allowlist_entries=[], notified=False,\n"
    "                notification_delivery_error=None, cache_hit=False)\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', repo_root)\n"
    "    return _Obj(scope='precommit', gate_version=" + repr(SECRET_MARKER) + ",\n"
    "                flagged=False, matches=[], allowed=[],\n"
    "                unused_allowlist_entries=[], notified=False,\n"
    "                notification_delivery_error=None, cache_hit=False)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return " + repr(SECRET_MARKER) + "\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


WRITER_SOURCE = (
    LOG_HELPER
    + "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id, repo_root)\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id, repo_root)\n"
    "    return None\n"
)


TRACKER_SOURCE = (
    LOG_HELPER
    + "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id, repo_root)\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa',\n"
    "            'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z',\n"
    "            'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


VERIFIER_SOURCE = (
    LOG_HELPER
    + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id, repo_root)\n"
    "    return _Obj(component_id=component_id, criteria=[], requirement_results={},\n"
    "                interface_drift=False, mutation_score=None, mutation_error=None,\n"
    "                assets=[], overall='pass')\n"
)


def build_repo(repo_root, hit):
    gen = repo_root / "gen"
    write(gen / "provenance-checker" / "provenance_checker.py", provenance_checker_source(hit))
    write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SOURCE)
    write(gen / "generation-loop" / "generation_loop.py", GENERATION_LOOP_SOURCE)
    write(gen / "license-scanner" / "license_scanner.py", LICENSE_SOURCE)
    write(gen / "secret-scanner" / "secret_scanner.py", SECRET_SOURCE)
    write(gen / "provenance-writer" / "provenance_writer.py", WRITER_SOURCE)
    write(gen / "provenance-tracker" / "provenance_tracker.py", TRACKER_SOURCE)
    write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_SOURCE)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_miss_with_generation_failed_invokes_both_scanners(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root, hit=False)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model")

    calls = read_log(log_path)
    names = [c[0] for c in calls]
    assert "run_attempts" in names, calls

    license_calls = [c for c in calls if c[0] == "license_scan"]
    assert license_calls == [["license_scan", "comp-foo", str(repo_root)]], calls

    secret_calls = [c for c in calls if c[0] == "secret_scan"]
    assert secret_calls == [["secret_scan", str(repo_root)]], calls

    license_scan = field(result, "license_scan")
    secret_scan = field(result, "secret_scan")
    assert license_scan is not None
    assert secret_scan is not None
    assert field(license_scan, "gate_version") == LICENSE_MARKER
    assert field(license_scan, "component_id") == "comp-foo"
    assert field(secret_scan, "gate_version") == SECRET_MARKER
    assert field(result, "provenance_hit") is False


def test_short_circuiting_hit_calls_neither_scanner(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_repo(repo_root, hit=True)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model")

    calls = read_log(log_path)
    names = [c[0] for c in calls]
    assert "check_provenance" in names, calls
    assert "license_scan" not in names, calls
    assert "secret_scan" not in names, calls
    assert "secret_scan_files" not in names, calls
    assert field(result, "provenance_hit") is True
# hotdocs-criterion: sha256:ff76f10aa0ed084c3a9ef3e41a92e20aaaf48e737ceaa9b9cc7e68fea1823741
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_AC_GATE_002A"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
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


PROVENANCE_CHECKER_SRC = LOG_HELPER + (
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
    "        {\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        },\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "          'lockfile_sha256': None}],\n"
    "    )\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
    "    return {\n"
    "        'hit': False,\n"
    "        'reason': 'no manifest',\n"
    "        'verification_report': None,\n"
    "        'license_scan': None,\n"
    "        'secret_scan': None,\n"
    "    }\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + (
    "class SpecBundle:\n"
    "    _FIELDS = ('component_id', 'spec_bundle_hash', 'spec', 'interface', 'constraints',\n"
    "               'dependency_interfaces', 'dependency_context', 'dependency_usage',\n"
    "               'vars', 'glossary', 'hint_code')\n"
    "\n"
    "    def __init__(self, component_id, spec_bundle_hash, spec, interface, constraints,\n"
    "                 dependency_interfaces=None, dependency_context=None,\n"
    "                 dependency_usage=None, vars=None, glossary='', hint_code=None):\n"
    "        self.component_id = component_id\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.spec = spec\n"
    "        self.interface = interface\n"
    "        self.constraints = constraints\n"
    "        self.dependency_interfaces = dependency_interfaces or {}\n"
    "        self.dependency_context = dependency_context or {}\n"
    "        self.dependency_usage = dependency_usage or {}\n"
    "        self.vars = vars or {}\n"
    "        self.glossary = glossary\n"
    "        self.hint_code = hint_code\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        if key not in self._FIELDS:\n"
    "            raise KeyError(key)\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        if key in self._FIELDS:\n"
    "            return getattr(self, key)\n"
    "        return default\n"
    "\n"
    "    def keys(self):\n"
    "        return list(self._FIELDS)\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    bundle = SpecBundle(component_id, 'sha256:abc123', 'BUNDLE-MARKER-AC-GATE-002A',\n"
    "                        'interface text', 'constraints text')\n"
    "    _log({'call': 'assemble', 'component_id': component_id,\n"
    "          'repo_root': str(repo_root), 'mode': mode, 'bundle_id': id(bundle)})\n"
    "    return bundle\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'call': 'assemble_criterion', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)


GENERATION_LOOP_SRC = LOG_HELPER + (
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
    "\n"
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({\n"
    "        'call': 'run_attempts',\n"
    "        'component_id': component_id,\n"
    "        'bundle_id': id(bundle),\n"
    "        'bundle_marker': _get(bundle, 'spec'),\n"
    "        'repo_root': str(repo_root),\n"
    "        'model': model,\n"
    "        'mode': mode,\n"
    "        'max_attempts': max_attempts,\n"
    "        'retry_feedback': retry_feedback,\n"
    "        'seed': seed,\n"
    "        'llm_backend_id': id(llm_backend),\n"
    "        'llm_backend_token': getattr(llm_backend, 'token', None),\n"
    "        'allow_unisolated_exec': allow_unisolated_exec,\n"
    "        'on_attempt_callable': callable(on_attempt),\n"
    "    })\n"
    "    generation_result = {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc123',\n"
    "        'model': model,\n"
    "        'prompt_version': 'v12',\n"
    "        'cache_hit': False,\n"
    "        'files': {'foo.py': 'X = 1\\n'},\n"
    "        'model_call_error': None,\n"
    "        'refused': None,\n"
    "        'retry_feedback': retry_feedback,\n"
    "        'mode': mode,\n"
    "        'transcript_sha256': None,\n"
    "        'turns': 1,\n"
    "        'tool_calls': 0,\n"
    "        'isolation': None,\n"
    "    }\n"
    "    verification_report = {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
    "                      'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [],\n"
    "        'overall': 'pass',\n"
    "    }\n"
    "    surface_report = {'ok': True, 'findings': []}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': list(retry_feedback or []),\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, verification_report)\n"
    "    return AttemptLoopResult(True, 'passed', [attempt], generation_result,\n"
    "                             verification_report, surface_report)\n"
    "\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures'})\n"
    "\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "\n"
    "    return (test_author, judge)\n"
)


PROVENANCE_TRACKER_SRC = LOG_HELPER + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
    "    return {\n"
    "        'attempt_id': '2026-10-25T14:32:01Z-a1b2c3',\n"
    "        'component_id': component_id,\n"
    "        'timestamp': '2026-10-25T14:32:01Z',\n"
    "        'spec_bundle_hash': spec_bundle_hash,\n"
    "        'generation': {},\n"
    "        'verification': {},\n"
    "    }\n"
)


LICENSE_SCANNER_SRC = LOG_HELPER + (
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan', 'component_id': component_id})\n"
    "    return {\n"
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
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)


SECRET_SCANNER_SRC = LOG_HELPER + (
    "class SecretScanResult:\n"
    "    def __init__(self):\n"
    "        self.scope = 'full'\n"
    "        self.gate_version = 'secret_scanner@0.0.0'\n"
    "        self.flagged = False\n"
    "        self.matches = []\n"
    "        self.allowed = []\n"
    "        self.unused_allowlist_entries = []\n"
    "        self.notified = False\n"
    "        self.notification_delivery_error = None\n"
    "        self.cache_hit = False\n"
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
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return SecretScanResult()\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log({'call': 'secret_scan_files'})\n"
    "    result = SecretScanResult()\n"
    "    result.scope = 'precommit'\n"
    "    return result\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
)


PROVENANCE_WRITER_SRC = LOG_HELPER + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
    "    return None\n"
)


VERIFIER_ORCHESTRATOR_SRC = LOG_HELPER + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criteria': [],\n"
    "            'requirement_results': {}, 'interface_drift': False,\n"
    "            'mutation_score': None, 'mutation_error': None, 'assets': [],\n"
    "            'overall': 'pass'}\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER_SRC,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER_SRC,
    "generation-loop": GENERATION_LOOP_SRC,
    "provenance-tracker": PROVENANCE_TRACKER_SRC,
    "license-scanner": LICENSE_SCANNER_SRC,
    "secret-scanner": SECRET_SCANNER_SRC,
    "provenance-writer": PROVENANCE_WRITER_SRC,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR_SRC,
}


class _SentinelBackend:
    token = "sentinel-backend-ac-gate-002a"


def _write_fakes(repo_root):
    for slug, source in FAKES.items():
        directory = repo_root / "gen" / slug
        directory.mkdir(parents=True, exist_ok=True)
        (directory / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")


def _read_log(log_path):
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def test_ac_gate_002a_miss_calls_assemble_cold_then_run_attempts_with_own_params(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fakes(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    sentinel = _SentinelBackend()

    result = component_gate_runner.run_component_gates(
        "comp-foo",
        repo_root,
        "m",
        seed=3,
        llm_backend=sentinel,
        retry_feedback=["R-FOO-002"],
        max_attempts=2,
        mode="agentic",
        allow_unisolated_exec=True,
    )
    assert result is not None

    entries = _read_log(log_path)
    calls = [e["call"] for e in entries]

    # The invocation log shows assemble then run_attempts, each exactly once.
    assert calls.count("assemble") == 1, calls
    assert calls.count("run_attempts") == 1, calls
    assert calls.index("assemble") < calls.index("run_attempts"), calls
    # make_closures is never called on the non-sealed path.
    assert "make_closures" not in calls, calls

    assemble_entry = next(e for e in entries if e["call"] == "assemble")
    run_entry = next(e for e in entries if e["call"] == "run_attempts")

    # assemble received mode "cold".
    assert assemble_entry["mode"] == "cold"
    assert assemble_entry["component_id"] == "comp-foo"
    assert assemble_entry["repo_root"] == str(repo_root)

    # run_attempts received exactly the runner's own parameters.
    assert run_entry["component_id"] == "comp-foo"
    assert run_entry["bundle_id"] == assemble_entry["bundle_id"]
    assert run_entry["bundle_marker"] == "BUNDLE-MARKER-AC-GATE-002A"
    assert run_entry["repo_root"] == str(repo_root)
    assert run_entry["model"] == "m"
    assert run_entry["mode"] == "agentic"
    assert run_entry["max_attempts"] == 2
    assert run_entry["retry_feedback"] == ["R-FOO-002"]
    assert run_entry["seed"] == 3
    assert run_entry["llm_backend_id"] == id(sentinel)
    assert run_entry["llm_backend_token"] == _SentinelBackend.token
    assert run_entry["allow_unisolated_exec"] is True
    assert run_entry["on_attempt_callable"] is True

    # The result reflects the faked passing loop.
    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
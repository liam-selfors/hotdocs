# hotdocs-criterion: sha256:ff55816c700192867019bc2c01cab0debbaee904e5ddd751a9a2984ce24129ed
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_AC_GATE_002A_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "def _get(value, name):\n"
    "    if isinstance(value, dict):\n"
    "        return value.get(name)\n"
    "    return getattr(value, name, None)\n"
    "\n"
)


SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:" + "cd" * 32,
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]


PROVENANCE_CHECKER_SRC = (
    LOG_HELPER
    + "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
    + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
    + "ASSETS = " + repr(ASSETS) + "\n"
    + "\n"
    "class _ProvenanceKey:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = SPEC_BUNDLE_HASH\n"
    "        self.gate_versions = dict(GATE_VERSIONS)\n"
    "        self.assets = [dict(a) for a in ASSETS]\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return _ProvenanceKey()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


ASSEMBLER_SRC = (
    LOG_HELPER
    + "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
    + "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    bundle = {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': SPEC_BUNDLE_HASH,\n"
    "        'spec': 'spec text',\n"
    "        'interface': 'interface text',\n"
    "        'constraints': 'constraints text',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': 'glossary text',\n"
    "        'hint_code': None,\n"
    "    }\n"
    "    _log({'call': 'assemble', 'component_id': component_id,\n"
    "          'repo_root': str(repo_root), 'mode': mode, 'bundle_id': id(bundle)})\n"
    "    return bundle\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'call': 'assemble_criterion', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP_SRC = (
    LOG_HELPER
    + "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
    + "ASSETS = " + repr(ASSETS) + "\n"
    + "\n"
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'component_id': component_id,\n"
    "          'bundle_id': id(bundle), 'bundle_hash': _get(bundle, 'spec_bundle_hash'),\n"
    "          'repo_root': str(repo_root), 'repo_root_type': type(repo_root).__name__,\n"
    "          'model': model, 'mode': mode, 'max_attempts': max_attempts,\n"
    "          'retry_feedback': retry_feedback, 'seed': seed,\n"
    "          'backend_id': id(llm_backend), 'allow_unisolated_exec': allow_unisolated_exec,\n"
    "          'on_attempt_callable': callable(on_attempt)})\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': SPEC_BUNDLE_HASH,\n"
    "        'model': model, 'prompt_version': 'v11', 'cache_hit': False,\n"
    "        'files': {'foo.py': 'X = 1\\n'}, 'model_call_error': None, 'refused': None,\n"
    "        'retry_feedback': retry_feedback, 'mode': mode, 'transcript_sha256': None,\n"
    "        'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
    "    }\n"
    "    verification_report = {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False, 'mutation_score': 0.9, 'mutation_error': None,\n"
    "        'assets': [dict(a) for a in ASSETS], 'overall': 'pass',\n"
    "    }\n"
    "    surface_report = {'ok': True, 'findings': []}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': list(retry_feedback or []),\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, verification_report)\n"
    "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [attempt],\n"
    "            'generation_result': generation_result,\n"
    "            'verification_report': verification_report,\n"
    "            'surface_report': surface_report}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures'})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


TRACKER_SRC = (
    LOG_HELPER
    + "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log({'call': 'check_readiness'})\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log({'call': 'last_requirement_failures'})\n"
    "    return []\n"
)


LICENSE_SRC = (
    LOG_HELPER
    + "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
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


SECRET_SRC = (
    LOG_HELPER
    + "class SecretScanResult:\n"
    "    def __init__(self):\n"
    "        self.scope = 'full'\n"
    "        self.gate_version = 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
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
    "                'flagged': self.flagged, 'matches': list(self.matches),\n"
    "                'allowed': list(self.allowed),\n"
    "                'unused_allowlist_entries': list(self.unused_allowlist_entries),\n"
    "                'notified': self.notified,\n"
    "                'notification_delivery_error': self.notification_delivery_error,\n"
    "                'cache_hit': self.cache_hit}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return SecretScanResult()\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log({'call': 'secret_scan_files'})\n"
    "    r = SecretScanResult()\n"
    "    r.scope = 'precommit'\n"
    "    return r\n"
)


WRITER_SRC = (
    LOG_HELPER
    + "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
    "    return None\n"
)


VERIFIER_SRC = (
    LOG_HELPER
    + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)


def _write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source)


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_ac_gate_002a_miss_calls_assemble_then_run_attempts(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    _write_fake(repo_root, "provenance-checker", PROVENANCE_CHECKER_SRC)
    _write_fake(repo_root, "spec-bundle-assembler", ASSEMBLER_SRC)
    _write_fake(repo_root, "generation-loop", GENERATION_LOOP_SRC)
    _write_fake(repo_root, "provenance-tracker", TRACKER_SRC)
    _write_fake(repo_root, "license-scanner", LICENSE_SRC)
    _write_fake(repo_root, "secret-scanner", SECRET_SRC)
    _write_fake(repo_root, "provenance-writer", WRITER_SRC)
    _write_fake(repo_root, "verifier-orchestrator", VERIFIER_SRC)

    sentinel_backend = object()

    component_gate_runner.run_component_gates(
        "comp-foo",
        repo_root,
        "m",
        seed=3,
        llm_backend=sentinel_backend,
        retry_feedback=["R-FOO-002"],
        max_attempts=2,
        mode="agentic",
        allow_unisolated_exec=True,
    )

    entries = _read_log(log_path)
    calls = [e["call"] for e in entries]

    assert calls.count("assemble") == 1, calls
    assert calls.count("run_attempts") == 1, calls
    assert calls.index("assemble") < calls.index("run_attempts"), calls

    assemble_entry = next(e for e in entries if e["call"] == "assemble")
    run_entry = next(e for e in entries if e["call"] == "run_attempts")

    assert assemble_entry["mode"] == "cold"
    assert assemble_entry["component_id"] == "comp-foo"

    assert run_entry["component_id"] == "comp-foo"
    assert run_entry["bundle_id"] == assemble_entry["bundle_id"]
    assert run_entry["bundle_hash"] == SPEC_BUNDLE_HASH
    assert run_entry["repo_root"] == str(repo_root)
    assert run_entry["repo_root_type"] == type(repo_root).__name__
    assert run_entry["model"] == "m"
    assert run_entry["mode"] == "agentic"
    assert run_entry["max_attempts"] == 2
    assert run_entry["retry_feedback"] == ["R-FOO-002"]
    assert run_entry["seed"] == 3
    assert run_entry["backend_id"] == id(sentinel_backend)
    assert run_entry["allow_unisolated_exec"] is True
    assert run_entry["on_attempt_callable"] is True
# hotdocs-criterion: sha256:441585d2a0490037d3c96ec14c205480ea4d79c2dc4d6ccd6c5ef64fee89d7cc
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_AC_GATE_002A"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_PRELUDE = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(json.dumps(entry) + '\\n')\n"
    "\n"
)


PROVENANCE_CHECKER = LOG_PRELUDE + (
    "import types\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return types.SimpleNamespace(\n"
    "        spec_bundle_hash='sha256:abc123',\n"
    "        gate_versions={\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        },\n"
    "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                 'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "                 'lockfile_sha256': None}],\n"
    "    )\n"
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


SPEC_BUNDLE_ASSEMBLER = LOG_PRELUDE + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    bundle = {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc123',\n"
    "        'spec': 'BUNDLE-MARKER-AC-GATE-002A',\n"
    "        'interface': '',\n"
    "        'constraints': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '',\n"
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
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {},\n"
    "            'testing': ''}\n"
)


GENERATION_LOOP = LOG_PRELUDE + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'component_id': component_id,\n"
    "          'bundle_id': id(bundle),\n"
    "          'bundle_spec': (bundle.get('spec') if isinstance(bundle, dict) else getattr(bundle, 'spec', None)),\n"
    "          'repo_root': str(repo_root), 'repo_root_type': type(repo_root).__name__,\n"
    "          'model': model, 'mode': mode, 'max_attempts': max_attempts,\n"
    "          'retry_feedback': retry_feedback, 'seed': seed,\n"
    "          'llm_backend_id': id(llm_backend),\n"
    "          'llm_backend_marker': getattr(llm_backend, 'marker', None),\n"
    "          'allow_unisolated_exec': allow_unisolated_exec,\n"
    "          'on_attempt_callable': callable(on_attempt)})\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
    "        'model': model, 'prompt_version': 'v12', 'cache_hit': False,\n"
    "        'files': {'foo.py': 'x = 1\\n'}, 'model_call_error': None, 'refused': None,\n"
    "        'retry_feedback': retry_feedback, 'mode': mode, 'transcript_sha256': None,\n"
    "        'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
    "    }\n"
    "    verification_report = {\n"
    "        'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "        'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "        'assets': [], 'overall': 'pass',\n"
    "    }\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': list(retry_feedback or []),\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [attempt],\n"
    "            'generation_result': generation_result,\n"
    "            'verification_report': verification_report,\n"
    "            'surface_report': {'ok': True, 'findings': []}}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures'})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


PROVENANCE_TRACKER = LOG_PRELUDE + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
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


VERIFIER_ORCHESTRATOR = LOG_PRELUDE + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)


LICENSE_SCANNER = LOG_PRELUDE + (
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan', 'component_id': component_id})\n"
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


SECRET_SCANNER = LOG_PRELUDE + (
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0',\n"
    "            'flagged': False, 'matches': [], 'allowed': [],\n"
    "            'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return {'scope': 'precommit', 'flagged': False, 'matches': [], 'allowed': [],\n"
    "            'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER = LOG_PRELUDE + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
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


class SentinelBackend:
    marker = "SENTINEL-BACKEND-AC-GATE-002A"


def _write_fakes(repo_root):
    for (slug, module), source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(source)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_002a_miss_calls_assemble_then_run_attempts(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _write_fakes(repo_root)

    sentinel = SentinelBackend()

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", seed=3,
        llm_backend=sentinel, retry_feedback=["R-FOO-002"],
        max_attempts=2, mode="agentic", allow_unisolated_exec=True,
    )
    assert result is not None

    entries = _read_log(log_path)
    names = [e["call"] for e in entries]

    assert names.count("assemble") == 1, names
    assert names.count("run_attempts") == 1, names
    assert names.index("assemble") < names.index("run_attempts"), names

    assemble_entry = entries[names.index("assemble")]
    run_entry = entries[names.index("run_attempts")]

    assert assemble_entry["component_id"] == "comp-foo"
    assert assemble_entry["mode"] == "cold"
    assert assemble_entry["repo_root"] == str(repo_root)

    assert run_entry["component_id"] == "comp-foo"
    assert run_entry["bundle_id"] == assemble_entry["bundle_id"]
    assert run_entry["bundle_spec"] == "BUNDLE-MARKER-AC-GATE-002A"
    assert run_entry["repo_root"] == str(repo_root)
    assert run_entry["repo_root_type"] == type(repo_root).__name__
    assert run_entry["model"] == "m"
    assert run_entry["mode"] == "agentic"
    assert run_entry["max_attempts"] == 2
    assert run_entry["retry_feedback"] == ["R-FOO-002"]
    assert run_entry["seed"] == 3
    assert run_entry["llm_backend_id"] == id(sentinel)
    assert run_entry["llm_backend_marker"] == SentinelBackend.marker
    assert run_entry["allow_unisolated_exec"] is True
    assert run_entry["on_attempt_callable"] is True
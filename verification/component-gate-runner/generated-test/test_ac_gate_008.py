# hotdocs-criterion: sha256:aa15c0770efe8421f28205dd091399754f4baf9b2f692de3e56a7c7aee2643e7
import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_PATH"
SCENARIO_ENV = "GATE_TEST_SCENARIO"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "def _scenario():\n"
    "    return os.environ.get(" + repr(SCENARIO_ENV) + ", '')\n"
    "\n"
)


PROVENANCE_CHECKER = COMMON_HEADER + (
    "class _Key:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:k'\n"
    "        self.gate_versions = {\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        }\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': None, 'versions': {'python': '3'},\n"
    "                        'lockfile_sha256': None}]\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_provenance_key', 'component_id': component_id})\n"
    "    return _Key()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'fn': 'check_provenance', 'component_id': component_id,\n"
    "          'spec_bundle_hash': spec_bundle_hash})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'fn': 'check_sealed_provenance'})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER = COMMON_HEADER + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'fn': 'assemble', 'component_id': component_id, 'mode': mode})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:k',\n"
    "            'spec': '', 'interface': '', 'constraints': '',\n"
    "            'dependency_interfaces': {}, 'dependency_context': {},\n"
    "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP = COMMON_HEADER + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def _gen(marker, files, model_call_error):\n"
    "    return {'component_id': 'comp-foo', 'spec_bundle_hash': 'sha256:k',\n"
    "            'model': 'm', 'prompt_version': marker, 'cache_hit': False,\n"
    "            'files': files, 'model_call_error': model_call_error, 'refused': None,\n"
    "            'retry_feedback': None, 'mode': 'single', 'transcript_sha256': None,\n"
    "            'turns': 1, 'tool_calls': 0, 'isolation': None}\n"
    "\n"
    "def _report(marker, overall):\n"
    "    return {'component_id': 'comp-foo', 'marker': marker,\n"
    "            'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
    "                          'kind': 'compiled', 'result': 'pass' if overall == 'pass' else 'fail'}],\n"
    "            'requirement_results': {'R-FOO-001': 'pass' if overall == 'pass' else 'fail'},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': overall}\n"
    "\n"
    "def _attempt(number, outcome, error_category, surface_ok, overall, failed):\n"
    "    return {'number': number, 'outcome': outcome, 'retry_feedback': [],\n"
    "            'error_category': error_category, 'surface_ok': surface_ok,\n"
    "            'overall': overall, 'failed_requirements': failed,\n"
    "            'transcript_sha256': None, 'reauthored_tests': []}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'fn': 'make_closures'})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'fn': 'run_attempts', 'component_id': component_id})\n"
    "    if _scenario() == 'two':\n"
    "        g1 = _gen('g1', {}, {'category': 'truncated_response', 'message': 'cut'})\n"
    "        g2 = _gen('g2', {'foo.py': 'X = 1\\n'}, None)\n"
    "        r2 = _report('r2', 'fail')\n"
    "        a1 = _attempt(1, 'generation_failed', 'truncated_response', None, None, [])\n"
    "        a2 = _attempt(2, 'verification_failed', None, True, 'fail', ['R-FOO-001'])\n"
    "        _log({'fn': 'ids', 'g1': id(g1), 'g2': id(g2), 'r2': id(r2)})\n"
    "        if on_attempt is not None:\n"
    "            on_attempt(a1, g1, None)\n"
    "            on_attempt(a2, g2, r2)\n"
    "        return {'passed': False, 'stop_reason': 'max_attempts', 'attempts': [a1, a2],\n"
    "                'generation_result': g2, 'verification_report': r2,\n"
    "                'surface_report': {'ok': True, 'findings': []}}\n"
    "    g = _gen('gp', {'foo.py': 'X = 1\\n'}, None)\n"
    "    r = _report('rp', 'pass')\n"
    "    a = _attempt(1, 'passed', None, True, 'pass', [])\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(a, g, r)\n"
    "    return {'passed': True, 'stop_reason': 'passed', 'attempts': [a],\n"
    "            'generation_result': g, 'verification_report': r,\n"
    "            'surface_report': {'ok': True, 'findings': []}}\n"
)


PROVENANCE_TRACKER = COMMON_HEADER + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    def _get(v, name):\n"
    "        return v.get(name) if isinstance(v, dict) else getattr(v, name, None)\n"
    "    _log({'fn': 'write_attempt_record', 'component_id': component_id,\n"
    "          'gen_id': id(generation_result),\n"
    "          'gen_marker': _get(generation_result, 'prompt_version'),\n"
    "          'report_is_none': verification_report is None,\n"
    "          'report_id': None if verification_report is None else id(verification_report),\n"
    "          'report_marker': None if verification_report is None else _get(verification_report, 'marker'),\n"
    "          'spec_bundle_hash': spec_bundle_hash, 'repo_root': str(repo_root)})\n"
    "    if _scenario() == 'raise':\n"
    "        raise RuntimeError('write_attempt_record failed on purpose')\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


VERIFIER_ORCHESTRATOR = COMMON_HEADER + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'fn': 'verify', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
    "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
    "            'assets': [], 'overall': 'pass'}\n"
)


LICENSE_SCANNER = COMMON_HEADER + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log({'fn': 'license_scan', 'component_id': component_id})\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "            'cache_hit': False}\n"
)


SECRET_SCANNER = COMMON_HEADER + (
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log({'fn': 'secret_scan'})\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [],\n"
    "            'notified': False, 'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return scan(repo_root)\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER = COMMON_HEADER + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'fn': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'fn': 'write_sealed_provenance', 'component_id': component_id})\n"
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


def build_repo(tmp_path, monkeypatch, scenario):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for (slug, module_name), source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (module_name + ".py")).write_text(source, encoding="utf-8")
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.setenv(SCENARIO_ENV, scenario)
    return repo_root, log_path


def read_log(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_on_attempt_writes_one_attempt_record_per_attempt(tmp_path, monkeypatch):
    repo_root, log_path = build_repo(tmp_path, monkeypatch, "two")

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = read_log(log_path)
    ids = [e for e in entries if e["fn"] == "ids"]
    assert len(ids) == 1, entries
    ids = ids[0]
    records = [e for e in entries if e["fn"] == "write_attempt_record"]
    assert len(records) == 2, records

    first, second = records
    assert first["component_id"] == "comp-foo"
    assert first["gen_marker"] == "g1"
    assert first["gen_id"] == ids["g1"]
    assert first["report_is_none"] is True
    assert first["spec_bundle_hash"] == "sha256:k"
    assert first["repo_root"] == str(repo_root)

    assert second["component_id"] == "comp-foo"
    assert second["gen_marker"] == "g2"
    assert second["gen_id"] == ids["g2"]
    assert second["report_is_none"] is False
    assert second["report_marker"] == "r2"
    assert second["report_id"] == ids["r2"]
    assert second["spec_bundle_hash"] == "sha256:k"
    assert second["repo_root"] == str(repo_root)


def test_write_attempt_record_exception_does_not_change_result(tmp_path, monkeypatch):
    repo_root, log_path = build_repo(tmp_path, monkeypatch, "raise")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = read_log(log_path)
    records = [e for e in entries if e["fn"] == "write_attempt_record"]
    assert len(records) == 1, entries
    assert field(result, "blocked") is False
    assert field(result, "component_id") == "comp-foo"
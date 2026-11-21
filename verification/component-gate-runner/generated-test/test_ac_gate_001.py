# hotdocs-criterion: sha256:4fe9bd3dca5170f5e108125edb32d1f4cb638ce9f9bd35664b696ff7eb518345
import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_AC_GATE_001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_SRC = (
    "import json\n"
    "import os\n"
    "from types import SimpleNamespace\n"
    "\n"
    "\n"
    "def _log(fn, **params):\n"
    "    path = os.environ[" + repr(LOG_ENV) + "]\n"
    "    with open(path, 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps({'fn': fn, 'params': params}, default=str) + '\\n')\n"
    "\n"
    "\n"
    "def _verification_report(overall):\n"
    "    return {\n"
    "        'component_id': 'comp-foo',\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled',\n"
    "             'result': 'pass' if overall == 'pass' else 'fail'},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass' if overall == 'pass' else 'fail'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.92,\n"
    "        'mutation_error': None,\n"
    "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                    'adapter_sha256': 'sha256:ab', 'versions': {'python': '3.12.4'},\n"
    "                    'lockfile_sha256': None}],\n"
    "        'overall': overall,\n"
    "    }\n"
    "\n"
    "\n"
    "def _license_scan(blocked, tag):\n"
    "    return {\n"
    "        'component_id': 'comp-foo',\n"
    "        'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "        'evaluated': False,\n"
    "        'reason': 'no-reference-corpus',\n"
    "        'similarity_score': None,\n"
    "        'block_threshold': None,\n"
    "        'blocked': blocked,\n"
    "        'matches': [],\n"
    "        'notified': False,\n"
    "        'notification_delivery_error': None,\n"
    "        'cache_hit': tag == 'hit',\n"
    "    }\n"
    "\n"
    "\n"
    "def _secret_scan(tag):\n"
    "    return {\n"
    "        'scope': 'full',\n"
    "        'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "        'flagged': False,\n"
    "        'matches': [],\n"
    "        'allowed': [],\n"
    "        'unused_allowlist_entries': [],\n"
    "        'notified': False,\n"
    "        'notification_delivery_error': None,\n"
    "        'cache_hit': tag == 'hit',\n"
    "    }\n"
    "\n"
    "\n"
    "def _generation_result():\n"
    "    return {\n"
    "        'component_id': 'comp-foo',\n"
    "        'spec_bundle_hash': 'sha256:k',\n"
    "        'model': 'm',\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'files': {'foo.py': 'x = 1\\n'},\n"
    "        'model_call_error': None,\n"
    "        'refused': None,\n"
    "        'retry_feedback': None,\n"
    "        'mode': 'single',\n"
    "        'transcript_sha256': None,\n"
    "        'turns': 1,\n"
    "        'tool_calls': 0,\n"
    "        'isolation': None,\n"
    "    }\n"
    "\n"
)


def provenance_checker_src(overall):
    return COMMON_SRC + (
        "OVERALL = " + repr(overall) + "\n"
        "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id, repo_root=repo_root)\n"
        "    return None\n"
        "\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id, repo_root=repo_root)\n"
        "    return SimpleNamespace(\n"
        "        spec_bundle_hash='sha256:k',\n"
        "        gate_versions={'verifier': 'v@1'},\n"
        "        assets=[{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                 'adapter_sha256': 'sha256:ab', 'versions': {'python': '3.12.4'},\n"
        "                 'lockfile_sha256': None}],\n"
        "    )\n"
        "\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id,\n"
        "         spec_bundle_hash=spec_bundle_hash, gate_versions=gate_versions,\n"
        "         repo_root=repo_root)\n"
        "    return {\n"
        "        'hit': True,\n"
        "        'reason': None,\n"
        "        'verification_report': _verification_report(OVERALL),\n"
        "        'license_scan': _license_scan(False, 'hit'),\n"
        "        'secret_scan': _secret_scan('hit'),\n"
        "    }\n"
        "\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n"
    )


SPEC_BUNDLE_ASSEMBLER_SRC = COMMON_SRC + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, repo_root=repo_root, mode=mode)\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:k',\n"
    "        'spec': 'spec',\n"
    "        'interface': 'interface',\n"
    "        'constraints': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '',\n"
    "        'hint_code': None,\n"
    "    }\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id,\n"
    "         criterion_id=criterion_id, repo_root=repo_root)\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)


GENERATION_LOOP_SRC = COMMON_SRC + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log('run_attempts', component_id=component_id, repo_root=repo_root,\n"
    "         model=model, mode=mode, max_attempts=max_attempts,\n"
    "         retry_feedback=retry_feedback, seed=seed,\n"
    "         allow_unisolated_exec=allow_unisolated_exec)\n"
    "    return {\n"
    "        'passed': False,\n"
    "        'stop_reason': 'max_attempts',\n"
    "        'attempts': [\n"
    "            {'number': 1, 'outcome': 'verification_failed', 'retry_feedback': [],\n"
    "             'error_category': None, 'surface_ok': True, 'overall': 'fail',\n"
    "             'failed_requirements': ['R-FOO-001'], 'transcript_sha256': None,\n"
    "             'reauthored_tests': []},\n"
    "        ],\n"
    "        'generation_result': _generation_result(),\n"
    "        'verification_report': _verification_report('fail'),\n"
    "        'surface_report': {'ok': True, 'findings': []},\n"
    "    }\n"
    "\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log('make_closures', model=model, seed=seed, repo_root=repo_root)\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


PROVENANCE_TRACKER_SRC = COMMON_SRC + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id,\n"
    "         spec_bundle_hash=spec_bundle_hash, repo_root=repo_root)\n"
    "    return {'attempt_id': '2026-10-25T14:32:01Z-a1b2c3', 'component_id': component_id,\n"
    "            'timestamp': '2026-10-25T14:32:01Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log('check_readiness', repo_root=repo_root)\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log('last_requirement_failures', component_id=component_id, repo_root=repo_root)\n"
    "    return []\n"
)


VERIFIER_ORCHESTRATOR_SRC = COMMON_SRC + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=repo_root)\n"
    "    return _verification_report('pass')\n"
)


LICENSE_SCANNER_SRC = COMMON_SRC + (
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id, repo_root=repo_root)\n"
    "    return _license_scan(False, 'fresh')\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('license_gate_version', repo_root=repo_root)\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)


SECRET_SCANNER_SRC = COMMON_SRC + (
    "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root=repo_root)\n"
    "    return _secret_scan('fresh')\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', repo_root=repo_root)\n"
    "    result = _secret_scan('fresh')\n"
    "    result['scope'] = 'precommit'\n"
    "    return result\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    _log('secret_gate_version', repo_root=repo_root)\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "\n"
    "def propose(repo_root):\n"
    "    _log('propose', repo_root=repo_root)\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_WRITER_SRC = COMMON_SRC + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
    "\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id, repo_root=repo_root)\n"
    "    return None\n"
)


def write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def build_repo(tmp_path, monkeypatch, overall):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    write_fake(repo_root, "provenance-checker", provenance_checker_src(overall))
    write_fake(repo_root, "spec-bundle-assembler", SPEC_BUNDLE_ASSEMBLER_SRC)
    write_fake(repo_root, "generation-loop", GENERATION_LOOP_SRC)
    write_fake(repo_root, "provenance-tracker", PROVENANCE_TRACKER_SRC)
    write_fake(repo_root, "verifier-orchestrator", VERIFIER_ORCHESTRATOR_SRC)
    write_fake(repo_root, "license-scanner", LICENSE_SCANNER_SRC)
    write_fake(repo_root, "secret-scanner", SECRET_SCANNER_SRC)
    write_fake(repo_root, "provenance-writer", PROVENANCE_WRITER_SRC)
    return repo_root, log_path


def read_calls(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def expected_values():
    ns = {}
    exec(COMMON_SRC, ns)
    return ns


def test_passing_hit_short_circuits(tmp_path, monkeypatch):
    repo_root, log_path = build_repo(tmp_path, monkeypatch, "pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = read_calls(log_path)
    names = [c["fn"] for c in calls]
    assert "check_provenance" in names, names
    assert names.count("check_provenance") == 1, names
    cp_index = names.index("check_provenance")
    assert "current_provenance_key" in names[:cp_index], names
    # No dependency called after check_provenance.
    assert cp_index == len(names) - 1, names
    for forbidden in ("assemble", "run_attempts", "make_closures", "verify",
                      "license_scan", "secret_scan", "write_provenance",
                      "write_attempt_record", "write_sealed_provenance"):
        assert forbidden not in names, names

    cp = calls[cp_index]["params"]
    assert cp["component_id"] == "comp-foo"
    assert cp["spec_bundle_hash"] == "sha256:k"
    assert cp["gate_versions"] == {"verifier": "v@1"}
    assert cp["repo_root"] == str(repo_root)

    ns = expected_values()
    assert field(result, "provenance_hit") is True
    assert field(result, "blocked") is False
    assert field(result, "verification") == ns["_verification_report"]("pass")
    assert field(result, "license_scan") == ns["_license_scan"](False, "hit")
    assert field(result, "secret_scan") == ns["_secret_scan"]("hit")
    assert field(result, "attempts") == []


def test_hit_with_failed_report_proceeds_as_miss(tmp_path, monkeypatch):
    repo_root, log_path = build_repo(tmp_path, monkeypatch, "fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    calls = read_calls(log_path)
    names = [c["fn"] for c in calls]
    assert names.count("run_attempts") == 1, names
    assert field(result, "provenance_hit") is False
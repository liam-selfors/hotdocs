# hotdocs-criterion: sha256:71ff108b7cfa2dc88e99a3f0622d1b089de6e646a39ee03920435703fb73f186
import json
from pathlib import Path

import component_gate_runner


COMPONENT_ID = "comp-foo"
MODEL_CALL_ERROR = {"category": "timeout", "message": "t"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _header(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'call': name}) + '\\n')\n"
        "\n"
    )


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source, encoding="utf-8")


def _verification_report_src():
    return (
        "def _report(component_id):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [],\n"
        "        'requirement_results': {},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': None,\n"
        "        'mutation_error': None,\n"
        "        'assets': [],\n"
        "        'drivers': [],\n"
        "        'overall': 'pass',\n"
        "    }\n"
        "\n"
    )


def _build_fakes(repo_root, log_path):
    attempt = {
        "number": 1,
        "outcome": "generation_failed",
        "retry_feedback": [],
        "error_category": "timeout",
        "surface_ok": None,
        "overall": None,
        "failed_requirements": [],
        "transcript_sha256": None,
        "reauthored_tests": [],
    }
    generation_result = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": "sha256:abc",
        "model": "m",
        "prompt_version": "v1",
        "cache_hit": False,
        "files": {},
        "model_call_error": dict(MODEL_CALL_ERROR),
        "refused": None,
        "retry_feedback": None,
        "mode": "single",
        "transcript_sha256": None,
        "turns": 1,
        "tool_calls": 0,
        "isolation": None,
    }

    # provenance-checker
    _write(
        repo_root,
        "provenance-checker",
        _header(log_path)
        + "class ProvenanceKey:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = 'sha256:abc'\n"
        "        self.spec_bundle_parts = {'spec': 'sha256:01', 'dependency_code': 'sha256:02'}\n"
        "        self.gate_versions = {\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "            'generator': 'generator@3.0.0+v11',\n"
        "        }\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                        'adapter_sha256': 'sha256:03', 'versions': {'python': '3.12.4'},\n"
        "                        'lockfile_sha256': None}]\n"
        "        self.drivers = []\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key')\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key')\n"
        "    return ProvenanceKey()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance')\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance')\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    # spec-bundle-assembler
    _write(
        repo_root,
        "spec-bundle-assembler",
        _header(log_path)
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
        "            'spec': 's', 'interface': 'i', 'constraints': 'c',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
        "            'hint_code': None,\n"
        "            'spec_bundle_parts': {'spec': 'sha256:01', 'dependency_code': 'sha256:02'}}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n",
    )

    # generation-loop
    _write(
        repo_root,
        "generation-loop",
        _header(log_path)
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "ATTEMPT = " + repr(attempt) + "\n"
        "GENERATION_RESULT = " + repr(generation_result) + "\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    return {\n"
        "        'passed': False,\n"
        "        'stop_reason': 'not_retried',\n"
        "        'attempts': [dict(ATTEMPT)],\n"
        "        'generation_result': dict(GENERATION_RESULT),\n"
        "        'verification_report': None,\n"
        "        'surface_report': None,\n"
        "    }\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n",
    )

    # provenance-tracker
    _write(
        repo_root,
        "provenance-tracker",
        _header(log_path)
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n",
    )

    # verifier-orchestrator
    _write(
        repo_root,
        "verifier-orchestrator",
        _header(log_path)
        + _verification_report_src()
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify')\n"
        "    return _report(component_id)\n",
    )

    # license-scanner
    _write(
        repo_root,
        "license-scanner",
        _header(log_path)
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan')\n"
        "    return {'component_id': component_id,\n"
        "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
        "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
        "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
        "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
        "            'cache_hit': False}\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n",
    )

    # secret-scanner
    _write(
        repo_root,
        "secret-scanner",
        _header(log_path)
        + "def _result(scope):\n"
        "    return {'scope': scope, 'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
        "            'flagged': False, 'matches': [], 'allowed': [],\n"
        "            'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n"
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
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
        "\n"
        "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "\n"
        "def propose(repo_root):\n"
        "    _log('propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )

    # provenance-writer
    _write(
        repo_root,
        "provenance-writer",
        _header(log_path)
        + "class InvalidSealedInputError(Exception):\n"
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
        "    return None\n",
    )

    return attempt


def _calls(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)["call"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ac_gate_003c_model_call_error_blocks_with_null_verification(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    attempt = _build_fakes(repo_root, log_path)

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m")

    calls = _calls(log_path)
    assert "run_attempts" in calls, calls

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"
    assert field(result, "model_call_error") == MODEL_CALL_ERROR
    assert field(result, "verification") is None
    assert field(result, "attempts") == [attempt]
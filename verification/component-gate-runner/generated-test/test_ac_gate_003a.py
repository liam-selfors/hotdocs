# hotdocs-criterion: sha256:cd79a2a5466cd4c57a79dda325a79040be8c2c48051f0fc9c58594842b08216d
import json
import os

import component_gate_runner


LOG_ENV = "GATE_TEST_AC_GATE_003A_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name):\n"
    "    path = os.environ[" + repr(LOG_ENV) + "]\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'call': name}) + '\\n')\n"
    "\n"
)

VERIFICATION_REPORT_SRC = (
    "{'component_id': 'comp-foo',\n"
    " 'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    " 'requirement_results': {'R-FOO-001': 'pass'},\n"
    " 'interface_drift': False,\n"
    " 'mutation_score': 0.9,\n"
    " 'mutation_error': None,\n"
    " 'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "             'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "             'lockfile_sha256': None}],\n"
    " 'overall': 'pass'}"
)

LICENSE_SCAN_SRC = (
    "{'component_id': 'comp-foo', 'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    " 'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
    " 'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
    " 'notification_delivery_error': None, 'cache_hit': False}"
)

SECRET_SCAN_SRC = (
    "{'scope': 'full', 'gate_version': 'secret_scanner@3.1.0', 'flagged': False,\n"
    " 'matches': [], 'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
    " 'notification_delivery_error': None, 'cache_hit': False}"
)

GATE_VERSIONS_SRC = (
    "{'compiler': 'criterion-compiler@1.0.0', 'generated_test': 'generated_test@1.0.0',\n"
    " 'verifier': 'verifier-orchestrator@2.0.0',\n"
    " 'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    " 'secret_scanner': 'secret_scanner@3.1.0', 'generator': 'generator@3.0.0+v11'}"
)

FAKES = {
    "provenance-checker": (
        "provenance_checker",
        HEADER
        + "class _Key:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key')\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key')\n"
        "    return _Key('sha256:abc', " + GATE_VERSIONS_SRC + ",\n"
        "                [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
        "                  'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
        "                  'lockfile_sha256': None}])\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance')\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance')\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n",
    ),
    "spec-bundle-assembler": (
        "spec_bundle_assembler",
        HEADER
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
        "            'spec': 's', 'interface': 'i', 'constraints': 'c',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n",
    ),
    "generation-loop": (
        "generation_loop",
        HEADER
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    return {\n"
        "        'passed': True,\n"
        "        'stop_reason': 'passed',\n"
        "        'attempts': [{'number': 1, 'outcome': 'verification_failed'},\n"
        "                     {'number': 2, 'outcome': 'passed'}],\n"
        "        'generation_result': {\n"
        "            'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
        "            'model': model, 'prompt_version': 'v1', 'cache_hit': False,\n"
        "            'files': {'foo.py': 'X = 1\\n'}, 'model_call_error': None,\n"
        "            'refused': None, 'retry_feedback': None, 'mode': 'single',\n"
        "            'transcript_sha256': None, 'turns': 1, 'tool_calls': 0,\n"
        "            'isolation': None},\n"
        "        'verification_report': " + VERIFICATION_REPORT_SRC + ",\n"
        "        'surface_report': {'ok': True, 'findings': []},\n"
        "    }\n",
    ),
    "provenance-tracker": (
        "provenance_tracker",
        HEADER
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
        "            'capabilities': {}, 'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n",
    ),
    "verifier-orchestrator": (
        "verifier_orchestrator",
        HEADER
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify')\n"
        "    return " + VERIFICATION_REPORT_SRC + "\n",
    ),
    "license-scanner": (
        "license_scanner",
        HEADER
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan')\n"
        "    return " + LICENSE_SCAN_SRC + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n",
    ),
    "secret-scanner": (
        "secret_scanner",
        HEADER
        + "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return " + SECRET_SCAN_SRC + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return " + SECRET_SCAN_SRC + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0'\n"
        "\n"
        "def propose(repo_root):\n"
        "    _log('propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    ),
    "provenance-writer": (
        "provenance_writer",
        HEADER
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
    ),
}


def write_fakes(repo_root):
    for slug, (module_name, source) in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def read_calls(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)["call"]
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_ac_gate_003a_loop_result_passed_through_unchanged(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fakes(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "test-model"
    )

    calls = read_calls(log_path)
    assert calls.count("run_attempts") == 1, calls
    assert "make_closures" not in calls, calls

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "provenance_hit") is False

    expected_attempts = [
        {"number": 1, "outcome": "verification_failed"},
        {"number": 2, "outcome": "passed"},
    ]
    attempts = field(result, "attempts")
    assert list(attempts) == expected_attempts
    assert len(attempts) == 2

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
# hotdocs-criterion: sha256:6175ffefb67b24cc2bd4da7b8cc96cab355ae27538bd3a0714dd9e19ea4e277b
"""AC-GATE-003a: run_attempts is called exactly once; its attempts list and
last verification report are passed through unchanged (R-GATE-003)."""

import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_AC_GATE_003A"

COMPONENT_ID = "comp-foo"

ATTEMPTS = [
    {"number": 1, "outcome": "verification_failed"},
    {"number": 2, "outcome": "passed"},
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(json.dumps({'fn': name}) + '\\n')\n"
    "\n"
)


VERIFICATION_REPORT = {
    "component_id": COMPONENT_ID,
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [
        {
            "kind": "python",
            "path": ".",
            "definition_sha256": None,
            "adapter_sha256": "sha256:00",
            "versions": {"python": "3.12.4"},
            "lockfile_sha256": None,
        }
    ],
    "overall": "pass",
}

GENERATION_RESULT = {
    "component_id": COMPONENT_ID,
    "spec_bundle_hash": "sha256:abc",
    "model": "m1",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {"foo.py": "X = 1\n"},
    "model_call_error": None,
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

LOOP_RESULT = {
    "passed": True,
    "stop_reason": "passed",
    "attempts": ATTEMPTS,
    "generation_result": GENERATION_RESULT,
    "verification_report": VERIFICATION_REPORT,
    "surface_report": {"ok": True, "findings": []},
}

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v1",
}

LICENSE_SCAN = {
    "component_id": COMPONENT_ID,
    "gate_version": "license_scanner@4.0.0-no-reference-corpus",
    "evaluated": False,
    "reason": "no-reference-corpus",
    "similarity_score": None,
    "block_threshold": None,
    "blocked": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@0.0.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}


def write_module(repo_root, slug, body):
    module_name = slug.replace("-", "_")
    d = Path(repo_root) / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(LOG_HELPER + body)


def build_fakes(repo_root):
    write_module(
        repo_root,
        "provenance-checker",
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr("sha256:abc") + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr([{
            "kind": "python", "path": ".", "definition_sha256": None,
            "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
            "lockfile_sha256": None}]) + "\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key')\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key')\n"
        "    return _Key()\n"
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
    )
    write_module(
        repo_root,
        "spec-bundle-assembler",
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble')\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc',\n"
        "            'spec': '', 'interface': '', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
        "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
        "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n",
    )
    write_module(
        repo_root,
        "generation-loop",
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
        "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts')\n"
        "    return " + repr(LOOP_RESULT) + "\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n",
    )
    write_module(
        repo_root,
        "provenance-tracker",
        "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record')\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a1', 'component_id': component_id,\n"
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
    )
    write_module(
        repo_root,
        "verifier-orchestrator",
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify')\n"
        "    return " + repr(VERIFICATION_REPORT) + "\n",
    )
    write_module(
        repo_root,
        "license-scanner",
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan')\n"
        "    return " + repr(LICENSE_SCAN) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(LICENSE_SCAN["gate_version"]) + "\n",
    )
    write_module(
        repo_root,
        "secret-scanner",
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return " + repr(SECRET_SCAN) + "\n"
        "\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return " + repr(dict(SECRET_SCAN, scope="precommit")) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(SECRET_SCAN["gate_version"]) + "\n"
        "\n"
        "def propose(repo_root):\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )
    write_module(
        repo_root,
        "provenance-writer",
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance')\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance')\n"
        "    return None\n",
    )
    # A generator stand-in: this component must never call it itself.
    write_module(
        repo_root,
        "generator",
        "GATE_VERSION = 'generator@3.0.0'\n"
        "PROMPT_VERSION = 'v1'\n"
        "\n"
        "def generate(bundle, model, feedback, repo_root=None, llm_backend=None):\n"
        "    _log('generate')\n"
        "    return " + repr(GENERATION_RESULT) + "\n"
        "\n"
        "def commit_cache(result, repo_root=None):\n"
        "    _log('commit_cache')\n"
        "    return None\n",
    )


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line)["fn"] for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_003a_loop_attempts_passed_through(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_fakes(repo_root)

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, "m1")

    calls = read_log(log_path)
    assert calls.count("run_attempts") == 1, calls
    assert "generate" not in calls, calls
    assert "make_closures" not in calls, calls

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "attempts") == ATTEMPTS
    assert len(field(result, "attempts")) == 2
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
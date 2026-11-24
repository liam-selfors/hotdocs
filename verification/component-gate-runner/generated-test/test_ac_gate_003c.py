# hotdocs-criterion: sha256:4b2406a69e24edbaa979ee439cb795504fd9e69aae91434e381af4022f9aee19
import json
import os
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, data):\n"
    "    with open(os.environ['CGR_TEST_LOG'], 'a') as fh:\n"
    "        fh.write(json.dumps({'call': name, 'data': data}, default=str) + '\\n')\n"
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

SPEC_HASH = "sha256:abc123"

MODEL_CALL_ERROR = {"category": "timeout", "message": "t"}

ATTEMPT = {
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

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": SPEC_HASH,
    "model": "fake-model",
    "prompt_version": "v11",
    "cache_hit": False,
    "files": {},
    "model_call_error": MODEL_CALL_ERROR,
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

LICENSE_RESULT = {
    "component_id": "comp-foo",
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

SECRET_RESULT = {
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


def write_fake(repo_root, slug, body):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(COMMON_HEADER + body)


def build_fakes(repo_root):
    write_fake(
        repo_root,
        "provenance-checker",
        "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr(SPEC_HASH) + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,"
        " 'adapter_sha256': None, 'versions': {}, 'lockfile_sha256': None}]\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', [component_id])\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', [component_id])\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', [component_id, spec_bundle_hash])\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,"
        " 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', [component_id])\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',"
        " 'verification_report': None, 'license_scan': None, 'secret_scan': None,"
        " 'owners': None, 'source_hash': None, 'written_at': None}\n",
    )
    write_fake(
        repo_root,
        "spec-bundle-assembler",
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', [component_id, mode])\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': " + repr(SPEC_HASH) + ","
        " 'spec': '', 'interface': '', 'constraints': '', 'dependency_interfaces': {},"
        " 'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '',"
        " 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', [component_id, criterion_id])\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',"
        " 'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',"
        " 'dependency_interfaces': {}, 'testing': ''}\n",
    )
    write_fake(
        repo_root,
        "generation-loop",
        "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',"
        " 'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',"
        " 'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',"
        " max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,"
        " allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', [component_id, model, mode, max_attempts])\n"
        "    attempt = " + repr(ATTEMPT) + "\n"
        "    gen = " + repr(GENERATION_RESULT) + "\n"
        "    if on_attempt is not None:\n"
        "        on_attempt(attempt, gen, None)\n"
        "    return {'passed': False, 'stop_reason': 'not_retried', 'attempts': [attempt],"
        " 'generation_result': gen, 'verification_report': None, 'surface_report': None}\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', [model, seed])\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'skipped', 'rationale': None}\n"
        "    return (test_author, judge)\n",
    )
    write_fake(
        repo_root,
        "provenance-tracker",
        "def write_attempt_record(component_id, generation_result, verification_report,"
        " spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', [component_id, spec_bundle_hash])\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,"
        " 'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,"
        " 'generation': dict(generation_result) if isinstance(generation_result, dict) else {},"
        " 'verification': None}\n",
    )
    write_fake(
        repo_root,
        "license-scanner",
        "def scan(component_id, repo_root):\n"
        "    _log('license_scan', [component_id])\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(LICENSE_RESULT["gate_version"]) + "\n",
    )
    write_fake(
        repo_root,
        "secret-scanner",
        "def scan(repo_root):\n"
        "    _log('secret_scan', [])\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return " + repr(SECRET_RESULT["gate_version"]) + "\n",
    )
    write_fake(
        repo_root,
        "provenance-writer",
        "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', [component_id])\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', [component_id])\n"
        "    return None\n",
    )
    write_fake(
        repo_root,
        "verifier-orchestrator",
        "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', [component_id])\n"
        "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},"
        " 'interface_drift': False, 'mutation_score': None, 'mutation_error': None,"
        " 'assets': [], 'overall': 'pass'}\n",
    )


def read_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line)["call"] for line in log_path.read_text().splitlines() if line.strip()]


def test_ac_gate_003c_model_call_error_blocks(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv("CGR_TEST_LOG", str(log_path))
    build_fakes(repo_root)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model")

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"
    assert field(result, "model_call_error") == MODEL_CALL_ERROR
    assert field(result, "verification") is None
    assert field(result, "provenance_hit") is False

    attempts = field(result, "attempts")
    assert list(attempts) == [ATTEMPT]

    calls = read_calls(log_path)
    assert calls.count("run_attempts") == 1
    assert "make_closures" not in calls
    assert "write_provenance" not in calls
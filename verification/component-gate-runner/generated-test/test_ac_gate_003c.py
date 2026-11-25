# hotdocs-criterion: sha256:3b1ebae0e447e131409486c58f435ff2d02318200fa9cdd96ffc10c80d605570
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_TEST_003C_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(name, **kw):\n"
    "    path = os.environ[" + repr(LOG_ENV) + "]\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps({'call': name, 'args': {k: repr(v) for k, v in kw.items()}}) + '\\n')\n"
    "\n"
)


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
    "spec_bundle_hash": "sha256:abc123",
    "model": "fake-model",
    "prompt_version": "v1",
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
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@2.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
    "generator": "generator@3.0.0+v11",
}


def write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def build_fakes(repo_root):
    write_fake(
        repo_root,
        "provenance-checker",
        LOG_HELPER
        + "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "        self.assets = assets\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return ProvenanceKey(" + repr("sha256:abc123") + ", " + repr(GATE_VERSIONS) + ", "
        + repr([{"kind": "python", "path": ".", "definition_sha256": None,
                 "adapter_sha256": "sha256:00", "versions": {"python": "3.12.4"},
                 "lockfile_sha256": None}]) + ")\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('check_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        "            'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    write_fake(
        repo_root,
        "spec-bundle-assembler",
        LOG_HELPER
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc123',\n"
        "            'spec': '', 'interface': '', 'constraints': '',\n"
        "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '',\n"
        "            'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n",
    )

    write_fake(
        repo_root,
        "generation-loop",
        LOG_HELPER
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        "                      'missing_asset', 'malformed_layout')\n"
        "\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        "                 allow_unisolated_exec=False, on_attempt=None):\n"
        "    _log('run_attempts', component_id=component_id, model=model)\n"
        "    attempt = " + repr(ATTEMPT) + "\n"
        "    generation_result = " + repr(GENERATION_RESULT) + "\n"
        "    if on_attempt is not None:\n"
        "        on_attempt(attempt, generation_result, None)\n"
        "    return {'passed': False, 'stop_reason': 'not_retried', 'attempts': [attempt],\n"
        "            'generation_result': generation_result, 'verification_report': None,\n"
        "            'surface_report': None}\n"
        "\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures', model=model)\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n",
    )

    write_fake(
        repo_root,
        "provenance-tracker",
        LOG_HELPER
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        "                         spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id,\n"
        "         verification_report=verification_report)\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': dict(generation_result), 'verification': None}\n",
    )

    write_fake(
        repo_root,
        "license-scanner",
        LOG_HELPER
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return " + repr(LICENSE_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n",
    )

    write_fake(
        repo_root,
        "secret-scanner",
        LOG_HELPER
        + "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return " + repr(SECRET_RESULT) + "\n"
        "\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n",
    )

    write_fake(
        repo_root,
        "provenance-writer",
        LOG_HELPER
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id)\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n",
    )


def read_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line)["call"] for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gate_003c_model_call_error_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    build_fakes(repo_root)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "fake-model")

    calls = read_calls(log_path)
    assert "run_attempts" in calls, calls
    assert calls.count("run_attempts") == 1, calls

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"
    assert field(result, "model_call_error") == MODEL_CALL_ERROR
    mce = field(result, "model_call_error")
    assert field(mce, "category") == "timeout"
    assert field(mce, "message") == "t"
    assert field(result, "verification") is None
    assert field(result, "provenance_hit") is False
    assert field(result, "attempts") == [ATTEMPT]
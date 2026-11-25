# hotdocs-criterion: sha256:c17a47833269fa3a4fdc1a2a3e6f8d73f0863cd11c86cccdcb13b55217a7fb95
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_TEST_LOG_AC_GATE_002B"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(rec):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(json.dumps(rec) + '\\n')\n"
    "\n"
)


PROVENANCE_CHECKER_SRC = (
    LOG_HELPER
    + "class SealedKey:\n"
    "    def __init__(self, owners, source_path, source_hash, verifier_version):\n"
    "        self.owners = owners\n"
    "        self.source_path = source_path\n"
    "        self.source_hash = source_hash\n"
    "        self.verifier_version = verifier_version\n"
    "\n"
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key', 'component_id': component_id, 'repo_root': str(repo_root)})\n"
    "    return SealedKey(\n"
    "        " + repr(["pipeline-team"]) + ",\n"
    "        " + repr("legacy/foo/") + ",\n"
    "        " + repr("sha256:" + "0" * 64) + ",\n"
    "        " + repr("verifier-orchestrator@2.0.0") + ",\n"
    "    )\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey(" + repr("sha256:" + "1" * 64) + ", " + repr({
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.0.0",
        "verifier": "verifier-orchestrator@2.0.0",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        "secret_scanner": "secret_scanner@0.0.0",
        "generator": "generator@3.0.0+v11",
    }) + ", [])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': True, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None,\n"
    "            'source_hash': None, 'written_at': None}\n"
)


GENERATION_LOOP_SRC = (
    LOG_HELPER
    + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def _test_author_sentinel(bundle):\n"
    "    return {'model_call_error': None, 'file': None}\n"
    "\n"
    "_test_author_sentinel.sentinel_tag = 'test_author_sentinel'\n"
    "\n"
    "def _judge_sentinel(bundle):\n"
    "    return {'result': 'pass', 'rationale': None}\n"
    "\n"
    "_judge_sentinel.sentinel_tag = 'judge_sentinel'\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures', 'model': model, 'seed': seed,\n"
    "          'repo_root': str(repo_root), 'repo_root_type': type(repo_root).__name__,\n"
    "          'llm_backend_is_none': llm_backend is None,\n"
    "          'test_author_id': id(_test_author_sentinel), 'judge_id': id(_judge_sentinel)})\n"
    "    return (_test_author_sentinel, _judge_sentinel)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'component_id': component_id})\n"
    "    raise RuntimeError('run_attempts must not be called for a sealed component')\n"
)


VERIFIER_SRC = (
    LOG_HELPER
    + "GATE_VERSION = 'verifier-orchestrator@2.0.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id, 'repo_root': str(repo_root),\n"
    "          'judge_id': id(judge), 'test_author_id': id(test_author),\n"
    "          'judge_tag': getattr(judge, 'sentinel_tag', None),\n"
    "          'test_author_tag': getattr(test_author, 'sentinel_tag', None)})\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': None,\n"
    "        'mutation_error': None,\n"
    "        'assets': [],\n"
    "        'overall': 'pass',\n"
    "    }\n"
)


LICENSE_SRC = (
    LOG_HELPER
    + "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
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
)


SECRET_SRC = (
    LOG_HELPER
    + "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return {\n"
    "        'scope': 'full',\n"
    "        'gate_version': 'secret_scanner@0.0.0',\n"
    "        'flagged': False,\n"
    "        'matches': [],\n"
    "        'allowed': [],\n"
    "        'unused_allowlist_entries': [],\n"
    "        'notified': False,\n"
    "        'notification_delivery_error': None,\n"
    "        'cache_hit': False,\n"
    "    }\n"
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


def _write_fake(repo_root, slug, source):
    module_name = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module_name + ".py")).write_text(source, encoding="utf-8")


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_sealed_component_wires_make_closures_into_verify(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    _write_fake(repo_root, "provenance-checker", PROVENANCE_CHECKER_SRC)
    _write_fake(repo_root, "generation-loop", GENERATION_LOOP_SRC)
    _write_fake(repo_root, "verifier-orchestrator", VERIFIER_SRC)
    _write_fake(repo_root, "license-scanner", LICENSE_SRC)
    _write_fake(repo_root, "secret-scanner", SECRET_SRC)
    _write_fake(repo_root, "provenance-writer", WRITER_SRC)

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m", seed=5)
    assert result is not None

    calls = _read_log(log_path)

    mc = [c for c in calls if c["call"] == "make_closures"]
    assert len(mc) == 1, calls
    mc = mc[0]
    assert mc["model"] == "m"
    assert mc["seed"] == 5
    assert mc["repo_root"] == str(repo_root)
    assert mc["llm_backend_is_none"] is True

    vc = [c for c in calls if c["call"] == "verify"]
    assert len(vc) == 1, calls
    vc = vc[0]
    assert vc["component_id"] == "comp-foo"
    assert vc["judge_id"] == mc["judge_id"]
    assert vc["test_author_id"] == mc["test_author_id"]
    assert vc["judge_tag"] == "judge_sentinel"
    assert vc["test_author_tag"] == "test_author_sentinel"

    assert not [c for c in calls if c["call"] == "run_attempts"]

    names = [c["call"] for c in calls]
    assert names.index("make_closures") < names.index("verify")
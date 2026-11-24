# hotdocs-criterion: sha256:d3a2cbe328c9da36e0a002eb3799bab99bbb3bf58ba8a3bd867b8dccf70e78a3
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_GATE_TEST_LOG"


COMMON_HEAD = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(record):\n"
    "    path = os.environ[" + repr(LOG_ENV) + "]\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record) + '\\n')\n"
    "\n"
)


PROVENANCE_CHECKER_SRC = COMMON_HEAD + (
    "class SealedKey:\n"
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
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    return SealedKey(\n"
    "        owners=['pipeline-team'],\n"
    "        source_path='legacy/foo/',\n"
    "        source_hash='sha256:' + '0' * 64,\n"
    "        verifier_version='verifier-orchestrator@2.0.0',\n"
    "    )\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey(\n"
    "        spec_bundle_hash='sha256:' + '1' * 8,\n"
    "        gate_versions={\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        },\n"
    "        assets=[],\n"
    "    )\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': True, 'reason': 'no manifest',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


GENERATION_LOOP_SRC = COMMON_HEAD + (
    "def _sentinel_test_author(bundle):\n"
    "    return {'model_call_error': None, 'file': None}\n"
    "\n"
    "_sentinel_test_author.hotdocs_sentinel = 'test_author'\n"
    "\n"
    "def _sentinel_judge(bundle):\n"
    "    return {'result': 'pass', 'rationale': None}\n"
    "\n"
    "_sentinel_judge.hotdocs_sentinel = 'judge'\n"
    "\n"
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({\n"
    "        'call': 'make_closures',\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'seed_type': type(seed).__name__,\n"
    "        'repo_root': str(repo_root),\n"
    "        'repo_root_type': type(repo_root).__name__,\n"
    "        'llm_backend': repr(llm_backend),\n"
    "        'test_author_id': id(_sentinel_test_author),\n"
    "        'judge_id': id(_sentinel_judge),\n"
    "    })\n"
    "    return (_sentinel_test_author, _sentinel_judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'component_id': component_id})\n"
    "    raise AssertionError('run_attempts must not be called for a sealed component')\n"
)


VERIFIER_SRC = COMMON_HEAD + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({\n"
    "        'call': 'verify',\n"
    "        'component_id': component_id,\n"
    "        'judge_id': id(judge),\n"
    "        'test_author_id': id(test_author),\n"
    "        'judge_tag': getattr(judge, 'hotdocs_sentinel', None),\n"
    "        'test_author_tag': getattr(test_author, 'hotdocs_sentinel', None),\n"
    "    })\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': None,\n"
    "        'mutation_error': None,\n"
    "        'assets': [],\n"
    "        'overall': 'pass',\n"
    "    }\n"
)


LICENSE_SRC = COMMON_HEAD + (
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
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)


SECRET_SRC = COMMON_HEAD + (
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return {\n"
    "        'scope': 'full',\n"
    "        'gate_version': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "        'flagged': False,\n"
    "        'matches': [],\n"
    "        'allowed': [],\n"
    "        'unused_allowlist_entries': [],\n"
    "        'notified': False,\n"
    "        'notification_delivery_error': None,\n"
    "        'cache_hit': False,\n"
    "    }\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
)


WRITER_SRC = COMMON_HEAD + (
    "class InvalidSealedInputError(Exception):\n"
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


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ac_gate_002b_sealed_component_wires_make_closures_into_verify(tmp_path, monkeypatch):
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

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m", seed=5)

    records = _read_log(log_path)

    closures_calls = [r for r in records if r["call"] == "make_closures"]
    assert len(closures_calls) == 1, records
    mc = closures_calls[0]
    assert mc["model"] == "m"
    assert mc["seed"] == 5
    assert mc["seed_type"] == "int"
    assert mc["repo_root"] == str(repo_root)
    assert mc["repo_root_type"] == type(repo_root).__name__
    assert mc["llm_backend"] == repr(None)

    verify_calls = [r for r in records if r["call"] == "verify"]
    assert len(verify_calls) == 1, records
    vc = verify_calls[0]
    assert vc["component_id"] == "comp-foo"
    assert vc["judge_tag"] == "judge"
    assert vc["test_author_tag"] == "test_author"
    assert vc["judge_id"] == mc["judge_id"]
    assert vc["test_author_id"] == mc["test_author_id"]

    assert not any(r["call"] == "run_attempts" for r in records)
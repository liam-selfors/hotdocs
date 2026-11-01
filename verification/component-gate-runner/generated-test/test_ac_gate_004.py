import os

import component_gate_runner


def _get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_common_fixture(repo_root):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "sealed: false\n"
        "---\n\n"
        "# Purpose\n\n"
        "A synthetic fixture component for testing AC-GATE-004.\n",
    )

    _write(
        repo_root / "gen" / "provenance-checker" / "provenance_checker.py",
        "class ProvenanceKey:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    return ProvenanceKey(\n"
        "        spec_bundle_hash='sha256:' + 'a' * 64,\n"
        "        gate_versions={\n"
        "            'compiler': 'criterion-compiler@1.0.0',\n"
        "            'generated_test': 'generated_test@1.0.0',\n"
        "            'verifier': 'verifier-orchestrator@2.0.0',\n"
        "            'license_scanner': 'license_scanner@3.1.0',\n"
        "            'secret_scanner': 'secret_scanner@0.0.0',\n"
        "        },\n"
        "    )\n\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    return {\n"
        "        'hit': False,\n"
        "        'verification_report': None,\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "    }\n",
    )

    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + 'a' * 64,\n"
        "        'spec': 'spec text',\n"
        "        'interface': 'interface text',\n"
        "        'constraints': 'constraints text',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': 'glossary text',\n"
        "        'hint_code': None,\n"
        "    }\n",
    )

    _write(
        repo_root / "gen" / "license-scanner" / "license_scanner.py",
        "def scan(component_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'gate_version': 'license_scanner@3.1.0',\n"
        "        'similarity_score': 0.0,\n"
        "        'block_threshold': 0.70,\n"
        "        'blocked': False,\n"
        "        'matches': [],\n"
        "        'notified': False,\n"
        "        'notification_delivery_error': None,\n"
        "        'cache_hit': False,\n"
        "    }\n\n"
        "def gate_version(repo_root):\n"
        "    return 'license_scanner@3.1.0'\n",
    )

    _write(
        repo_root / "gen" / "secret-scanner" / "secret_scanner.py",
        "def scan(repo_root):\n"
        "    return {\n"
        "        'scope': 'full',\n"
        "        'gate_version': 'secret_scanner@2.0.0',\n"
        "        'flagged': False,\n"
        "        'matches': [],\n"
        "        'notified': False,\n"
        "        'notification_delivery_error': None,\n"
        "        'cache_hit': False,\n"
        "    }\n\n"
        "def gate_version(repo_root):\n"
        "    return 'secret_scanner@2.0.0'\n",
    )

    _write(
        repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py",
        "import os\n\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
        "    attempts_dir = os.path.join(str(repo_root), '.hotdocs', 'attempts', slug)\n"
        "    os.makedirs(attempts_dir, exist_ok=True)\n"
        "    idx = len(os.listdir(attempts_dir))\n"
        "    with open(os.path.join(attempts_dir, 'attempt-%d.json' % idx), 'w') as f:\n"
        "        f.write('{}')\n"
        "    return {\n"
        "        'attempt_id': '2026-01-01T00:00:00Z-%d' % idx,\n"
        "        'component_id': component_id,\n"
        "        'timestamp': '2026-01-01T00:00:00Z',\n"
        "        'spec_bundle_hash': spec_bundle_hash,\n"
        "        'generation': generation_result,\n"
        "        'verification': verification_report,\n"
        "    }\n",
    )

    _write(
        repo_root / "gen" / "provenance-writer" / "provenance_writer.py",
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    return None\n",
    )

    _write(
        repo_root / "gen" / "verifier-orchestrator" / "verifier_orchestrator.py",
        "import os\n\n"
        "GATE_VERSION = 'verifier-orchestrator@2.0.0'\n\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    log_path = os.environ['GATE_TEST_VERIFY_LOG']\n"
        "    with open(log_path, 'a') as f:\n"
        "        f.write(component_id + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criteria': [],\n"
        "        'requirement_results': {},\n"
        "        'interface_drift': False,\n"
        "        'mutation_score': 0.0,\n"
        "        'overall': 'fail',\n"
        "    }\n",
    )


def test_model_call_error_blocks_without_verify(tmp_path):
    repo_root = tmp_path
    _build_common_fixture(repo_root)

    _write(
        repo_root / "gen" / "generator" / "generator.py",
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle['component_id'] if isinstance(bundle, dict) else bundle.component_id\n"
        "    sbh = bundle['spec_bundle_hash'] if isinstance(bundle, dict) else bundle.spec_bundle_hash\n"
        "    return {\n"
        "        'component_id': cid,\n"
        "        'spec_bundle_hash': sbh,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'files': {},\n"
        "        'model_call_error': {'category': 'network', 'message': 'connection reset'},\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "    }\n",
    )

    verify_log = tmp_path / "verify_calls.log"
    os.environ["GATE_TEST_VERIFY_LOG"] = str(verify_log)
    try:
        result = component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="test-model", seed=0
        )
    finally:
        del os.environ["GATE_TEST_VERIFY_LOG"]

    assert verify_log.exists() is False

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "model_call_error"
    model_call_error = _get(result, "model_call_error")
    assert _get(model_call_error, "category") == "network"
    assert _get(model_call_error, "message") == "connection reset"
    assert _get(result, "verification") is None


def test_verification_failure_blocks_with_reason(tmp_path):
    repo_root = tmp_path
    _build_common_fixture(repo_root)

    _write(
        repo_root / "gen" / "generator" / "generator.py",
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle['component_id'] if isinstance(bundle, dict) else bundle.component_id\n"
        "    sbh = bundle['spec_bundle_hash'] if isinstance(bundle, dict) else bundle.spec_bundle_hash\n"
        "    return {\n"
        "        'component_id': cid,\n"
        "        'spec_bundle_hash': sbh,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'files': {'foo.py': \"print('hello')\"},\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "    }\n",
    )

    verify_log = tmp_path / "verify_calls.log"
    os.environ["GATE_TEST_VERIFY_LOG"] = str(verify_log)
    try:
        result = component_gate_runner.run_component_gates(
            "comp-foo", repo_root, model="test-model", seed=0
        )
    finally:
        del os.environ["GATE_TEST_VERIFY_LOG"]

    assert verify_log.exists() is True
    calls = verify_log.read_text().splitlines()
    assert len(calls) == 1
    assert calls[0] == "comp-foo"

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "verification_failed"
    assert _get(result, "model_call_error") is None
    verification = _get(result, "verification")
    assert verification is not None
    assert _get(verification, "overall") == "fail"
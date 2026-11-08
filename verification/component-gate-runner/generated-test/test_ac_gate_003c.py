import component_gate_runner


def _get(obj, name):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def test_model_call_error_blocks_generator_called_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    component_dir = repo_root / "specs" / "components" / "sample"
    component_dir.mkdir(parents=True)
    (component_dir / "component.md").write_text(
        "---\n"
        "id: comp-sample\n"
        "title: Sample Component\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n\n"
        "# Sample Component\n\n"
        "## Purpose\n\n"
        "Fixture component for AC-GATE-003c.\n"
    )

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    generator_log = log_dir / "generator_calls.log"

    def _write_module(slug, module_name, content):
        mod_dir = repo_root / "gen" / slug
        mod_dir.mkdir(parents=True)
        (mod_dir / (module_name + ".py")).write_text(content)

    _write_module(
        "provenance-checker",
        "provenance_checker",
        "class _Key:\n"
        "    spec_bundle_hash = 'sha256:' + '1' * 64\n"
        "    gate_versions = {\n"
        "        'compiler': 'criterion-compiler@1.0.0',\n"
        "        'generated_test': 'generated_test@1.0.0',\n"
        "        'verifier': 'verifier-orchestrator@2.0.0',\n"
        "        'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
        "        'secret_scanner': 'secret_scanner@0.0.0',\n"
        "    }\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    return _Key()\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    return {\n"
        "        'hit': False,\n"
        "        'verification_report': None,\n"
        "        'license_scan': None,\n"
        "        'secret_scan': None,\n"
        "    }\n"
    )

    _write_module(
        "spec-bundle-assembler",
        "spec_bundle_assembler",
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '1' * 64,\n"
        "        'spec': '',\n"
        "        'interface': '',\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': None,\n"
        "    }\n"
    )

    generator_log_repr = repr(str(generator_log))
    _write_module(
        "generator",
        "generator",
        "def generate(bundle, model, retry_feedback, *, repo_root=None, llm_backend=None):\n"
        "    with open(" + generator_log_repr + ", 'a') as f:\n"
        "        f.write('call\\n')\n"
        "    component_id = bundle['component_id'] if isinstance(bundle, dict) else bundle.component_id\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '1' * 64,\n"
        "        'model': model,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'files': {},\n"
        "        'model_call_error': {'category': 'timeout', 'message': 't'},\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "    }\n"
    )

    _write_module(
        "license-scanner",
        "license_scanner",
        "def scan(component_id, repo_root):\n"
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

    _write_module(
        "secret-scanner",
        "secret_scanner",
        "def scan(repo_root):\n"
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
    )

    _write_module(
        "provenance-tracker",
        "provenance_tracker",
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    return {\n"
        "        'attempt_id': '2026-01-01T00:00:00Z-abc123',\n"
        "        'component_id': component_id,\n"
        "        'timestamp': '2026-01-01T00:00:00Z',\n"
        "        'spec_bundle_hash': spec_bundle_hash,\n"
        "        'generation': generation_result,\n"
        "        'verification': verification_report,\n"
        "    }\n"
    )

    result = component_gate_runner.run_component_gates(
        "comp-sample",
        repo_root,
        "claude-sonnet-5",
        seed=0,
        llm_backend=None,
        retry_feedback=None,
    )

    assert generator_log.read_text().count("call\n") == 1

    assert _get(result, "blocked") is True
    assert _get(result, "block_reason") == "model_call_error"
    assert _get(result, "model_call_error") == {"category": "timeout", "message": "t"}
    assert _get(result, "verification") is None
# hotdocs-criterion: sha256:937ba233f8cfb5892baa618d024f2928a59c13c3b3903569fc774e05e09e6964
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_TEST_LOG"
HIT_ENV = "HOTDOCS_TEST_HIT"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(event, **kw):\n"
    "    path = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    if path:\n"
    "        entry = dict(kw)\n"
    "        entry['event'] = event\n"
    "        with open(path, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
)

GATE_VERSIONS_SRC = (
    "GATE_VERSIONS = {\n"
    "    'compiler': 'criterion-compiler@1.0.0',\n"
    "    'generated_test': 'generated_test@1.1.0',\n"
    "    'verifier': 'verifier-orchestrator@2.2.0',\n"
    "    'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "    'secret_scanner': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "}\n"
    "\n"
)

VERIFICATION_REPORT_SRC = (
    "def _report(component_id):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'generated-test', 'result': 'pass'},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'overall': 'pass',\n"
    "    }\n"
    "\n"
)

LICENSE_RESULT_SRC = (
    "def _license(component_id):\n"
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
)

SECRET_RESULT_SRC = (
    "def _secret(scope='full'):\n"
    "    return {\n"
    "        'scope': scope,\n"
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
)

PROVENANCE_CHECKER_SRC = (
    LOG_HELPER
    + GATE_VERSIONS_SRC
    + VERIFICATION_REPORT_SRC
    + LICENSE_RESULT_SRC
    + SECRET_RESULT_SRC
    + "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id, repo_root=str(repo_root))\n"
    "    return ProvenanceKey('sha256:abc123', dict(GATE_VERSIONS))\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id, repo_root=str(repo_root))\n"
    "    if os.environ.get(" + repr(HIT_ENV) + ") == '1':\n"
    "        return {\n"
    "            'hit': True,\n"
    "            'verification_report': _report(component_id),\n"
    "            'license_scan': _license(component_id),\n"
    "            'secret_scan': _secret(),\n"
    "        }\n"
    "    return {'hit': False, 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id, repo_root=str(repo_root))\n"
    "    return {\n"
    "        'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "        'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "        'owners': None, 'source_hash': None, 'written_at': None,\n"
    "    }\n"
)

SPEC_BUNDLE_ASSEMBLER_SRC = (
    LOG_HELPER
    + "def assemble(component_id, repo_root=None, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, repo_root=str(repo_root), mode=mode)\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc123',\n"
    "        'spec': 'Foo doubles a number.',\n"
    "        'interface': '# Library',\n"
    "        'constraints': 'None.',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '',\n"
    "        'hint_code': None,\n"
    "    }\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root=None):\n"
    "    _log('assemble_criterion', component_id=component_id, repo_root=str(repo_root))\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001',\n"
    "        'criterion_text': 'Given x',\n"
    "        'requirement_text': 'R-FOO-001',\n"
    "        'interface': '# Library',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "    }\n"
)

GENERATOR_SRC = (
    LOG_HELPER
    + "GATE_VERSION = 'generator@2.0.0'\n"
    "PROMPT_VERSION = 'v10'\n"
    "\n"
    "def _get(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    _log('generate', model=model, repo_root=str(repo_root))\n"
    "    return {\n"
    "        'component_id': _get(bundle, 'component_id'),\n"
    "        'spec_bundle_hash': _get(bundle, 'spec_bundle_hash'),\n"
    "        'model': model,\n"
    "        'prompt_version': PROMPT_VERSION,\n"
    "        'cache_hit': False,\n"
    "        'files': {},\n"
    "        'model_call_error': {'category': 'network', 'message': 'simulated failure'},\n"
    "        'refused': None,\n"
    "        'retry_feedback': retry_feedback,\n"
    "    }\n"
)

VERIFIER_SRC = (
    LOG_HELPER
    + VERIFICATION_REPORT_SRC
    + "GATE_VERSION = 'verifier-orchestrator@2.2.0'\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id, repo_root=str(repo_root))\n"
    "    return _report(component_id)\n"
)

LICENSE_SCANNER_SRC = (
    LOG_HELPER
    + LICENSE_RESULT_SRC
    + "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id, repo_root=str(repo_root))\n"
    "    return _license(component_id)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SCANNER_SRC = (
    LOG_HELPER
    + SECRET_RESULT_SRC
    + "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan', repo_root=str(repo_root))\n"
    "    return _secret('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files', repo_root=str(repo_root))\n"
    "    return _secret('precommit')\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_TRACKER_SRC = (
    LOG_HELPER
    + "from pathlib import Path\n"
    "\n"
    "def _plain(value):\n"
    "    if value is None or isinstance(value, dict):\n"
    "        return value\n"
    "    if hasattr(value, 'to_dict'):\n"
    "        return value.to_dict()\n"
    "    return {k: v for k, v in vars(value).items() if not k.startswith('_')}\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record', component_id=component_id, repo_root=str(repo_root))\n"
    "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
    "    attempt_id = '2026-11-17T00:00:00Z-aaaaaa'\n"
    "    record = {\n"
    "        'attempt_id': attempt_id,\n"
    "        'component_id': component_id,\n"
    "        'timestamp': '2026-11-17T00:00:00Z',\n"
    "        'spec_bundle_hash': spec_bundle_hash,\n"
    "        'generation': _plain(generation_result),\n"
    "        'verification': _plain(verification_report),\n"
    "    }\n"
    "    target = Path(repo_root) / '.hotdocs' / 'attempts' / slug\n"
    "    target.mkdir(parents=True, exist_ok=True)\n"
    "    (target / (attempt_id.replace(':', '-') + '.json')).write_text(json.dumps(record, default=str), encoding='utf-8')\n"
    "    return record\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)

PROVENANCE_WRITER_SRC = (
    LOG_HELPER
    + "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id, repo_root=str(repo_root))\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id, repo_root=str(repo_root))\n"
    "    return None\n"
)

TEST_AUTHOR_SRC = (
    LOG_HELPER
    + "GATE_VERSION = 'generated_test@1.1.0'\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    _log('author_test', model=model, repo_root=str(repo_root))\n"
    "    return {\n"
    "        'component_id': 'comp-foo',\n"
    "        'criterion_id': 'AC-FOO-001',\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'file': None,\n"
    "        'model_call_error': {'category': 'network', 'message': 'simulated failure'},\n"
    "    }\n"
)

LLM_ENDPOINT_SRC = (
    LOG_HELPER
    + "DEFAULT_TIMEOUT_SECONDS = 600\n"
    "PROVIDERS = {}\n"
    "\n"
    "class ModelResolutionError(Exception):\n"
    "    pass\n"
    "\n"
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    _log('complete', model=model)\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
    "\n"
    "def parse_model(model):\n"
    "    return (None, model)\n"
    "\n"
    "def resolve_provider(model, config=None):\n"
    "    return {'provider': None, 'model': model, 'base_url': None, 'api_key_env': None, 'timeout_seconds': 600, 'auth': None}\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER_SRC,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER_SRC,
    "generator": GENERATOR_SRC,
    "verifier-orchestrator": VERIFIER_SRC,
    "license-scanner": LICENSE_SCANNER_SRC,
    "secret-scanner": SECRET_SCANNER_SRC,
    "provenance-tracker": PROVENANCE_TRACKER_SRC,
    "provenance-writer": PROVENANCE_WRITER_SRC,
    "test-author": TEST_AUTHOR_SRC,
    "llm-endpoint": LLM_ENDPOINT_SRC,
}


def write_fixture(repo_root):
    (repo_root / "specs" / "components" / "foo" / "requirements").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "acceptance").mkdir(parents=True)
    (repo_root / "specs" / "components" / "foo" / "interface").mkdir(parents=True)
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** \u2014 a test term.\n", encoding="utf-8"
    )
    base = repo_root / "specs" / "components" / "foo"
    (base / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
        encoding="utf-8",
    )
    (base / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
        encoding="utf-8",
    )
    (base / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
        encoding="utf-8",
    )
    (base / "interface" / "library.md").write_text(
        "# Library\n\n```\nfoo(x: int) -> int\n```\n", encoding="utf-8"
    )
    (base / "constraints.md").write_text("# Constraints\n\nNone.\n", encoding="utf-8")


def write_fakes(repo_root):
    for slug, source in FAKES.items():
        module_name = slug.replace("-", "_")
        target = repo_root / "gen" / slug
        target.mkdir(parents=True, exist_ok=True)
        (target / (module_name + ".py")).write_text(source, encoding="utf-8")


def read_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def same_path(a, b):
    return Path(a).resolve() == Path(b).resolve()


def mock_backend(prompt, model, **params):
    return {"text": "pass", "model": model, "backend": "mock", "model_call_error": None}


def setup_repo(tmp_path, monkeypatch, hit):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fixture(repo_root)
    write_fakes(repo_root)
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.setenv(HIT_ENV, "1" if hit else "0")
    return repo_root, log_path


def test_miss_with_model_call_error_invokes_both_scanners(tmp_path, monkeypatch):
    repo_root, log_path = setup_repo(tmp_path, monkeypatch, hit=False)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0, llm_backend=mock_backend
    )

    entries = read_log(log_path)
    events = [e["event"] for e in entries]
    assert "check_provenance" in events, events
    assert "generate" in events, events

    license_calls = [e for e in entries if e["event"] == "license_scan"]
    secret_calls = [e for e in entries if e["event"] == "secret_scan"]
    assert len(license_calls) == 1, events
    assert len(secret_calls) == 1, events
    assert license_calls[0]["component_id"] == "comp-foo"
    assert same_path(license_calls[0]["repo_root"], repo_root)
    assert same_path(secret_calls[0]["repo_root"], repo_root)

    assert field(result, "provenance_hit") is False
    assert field(result, "block_reason") == "model_call_error"

    license_scan = field(result, "license_scan")
    secret_scan = field(result, "secret_scan")
    assert license_scan is not None
    assert secret_scan is not None
    assert field(license_scan, "component_id") == "comp-foo"
    assert field(license_scan, "gate_version") == "license_scanner@4.0.0-no-reference-corpus"
    assert field(license_scan, "evaluated") is False
    assert field(license_scan, "reason") == "no-reference-corpus"
    assert field(secret_scan, "scope") == "full"
    assert field(secret_scan, "gate_version") == "secret_scanner@3.1.0+detect-secrets.1.5.0"
    assert field(secret_scan, "flagged") is False


def test_short_circuiting_hit_calls_neither_scanner(tmp_path, monkeypatch):
    repo_root, log_path = setup_repo(tmp_path, monkeypatch, hit=True)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0, llm_backend=mock_backend
    )

    entries = read_log(log_path)
    events = [e["event"] for e in entries]
    assert "check_provenance" in events, events
    assert "license_scan" not in events, events
    assert "secret_scan" not in events, events
    assert "secret_scan_files" not in events, events

    assert field(result, "provenance_hit") is True
# hotdocs-criterion: sha256:6aff62c634b4843f9d69055a696a7f343c290c5951501f5c60d89bb34de1af47
import os
from pathlib import Path

import component_gate_runner


ERROR = {"category": "timeout", "message": "t"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import os\n"
    "\n"
    "def _log(name):\n"
    "    path = os.environ.get('GATE_TEST_LOG')\n"
    "    if path:\n"
    "        with open(path, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(name + '\\n')\n"
    "\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
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
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
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
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _write_fakes(repo_root):
    gen = repo_root / "gen"
    gate_versions = {
        "compiler": "criterion-compiler@1.0.0",
        "generated_test": "generated_test@1.1.0",
        "verifier": "verifier-orchestrator@2.2.0",
        "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
        "secret_scanner": "secret_scanner@0.0.0",
    }
    spec_hash = "sha256:" + "ab" * 32

    _write(
        gen / "provenance-checker" / "provenance_checker.py",
        LOG_HELPER
        + "class _Key:\n"
        "    def __init__(self, spec_bundle_hash, gate_versions):\n"
        "        self.spec_bundle_hash = spec_bundle_hash\n"
        "        self.gate_versions = gate_versions\n"
        "    def __getitem__(self, k):\n"
        "        return getattr(self, k)\n"
        "    def get(self, k, d=None):\n"
        "        return getattr(self, k, d)\n"
        "\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('provenance_checker.current_sealed_key')\n"
        "    return None\n"
        "\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('provenance_checker.current_provenance_key')\n"
        "    return _Key(" + repr(spec_hash) + ", dict(" + repr(gate_versions) + "))\n"
        "\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        "    _log('provenance_checker.check_provenance')\n"
        "    return {'hit': False, 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
        "\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('provenance_checker.check_sealed_provenance')\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
        "            'written_at': None}\n",
    )

    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        LOG_HELPER
        + "class _Bundle:\n"
        "    def __init__(self, **kw):\n"
        "        self.__dict__.update(kw)\n"
        "    def __getitem__(self, k):\n"
        "        return self.__dict__[k]\n"
        "    def get(self, k, d=None):\n"
        "        return self.__dict__.get(k, d)\n"
        "\n"
        "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    _log('spec_bundle_assembler.assemble')\n"
        "    return _Bundle(component_id=component_id, spec_bundle_hash=" + repr(spec_hash) + ",\n"
        "                   spec='s', interface='i', constraints='c', dependency_interfaces={},\n"
        "                   dependency_context={}, dependency_usage={}, vars={}, glossary='g',\n"
        "                   hint_code=None)\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root=None):\n"
        "    _log('spec_bundle_assembler.assemble_criterion')\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
        "            'dependency_interfaces': {}}\n",
    )

    _write(
        gen / "generator" / "generator.py",
        LOG_HELPER
        + "GATE_VERSION = 'generator@2.0.0'\n"
        "PROMPT_VERSION = 'v10'\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generator.generate')\n"
        "    sbh = bundle.get('spec_bundle_hash') if hasattr(bundle, 'get') else getattr(bundle, 'spec_bundle_hash', None)\n"
        "    return {'component_id': 'comp-foo', 'spec_bundle_hash': sbh, 'model': model,\n"
        "            'prompt_version': PROMPT_VERSION, 'cache_hit': False, 'files': {},\n"
        "            'model_call_error': dict(" + repr(ERROR) + "), 'refused': None,\n"
        "            'retry_feedback': retry_feedback}\n",
    )

    _write(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        LOG_HELPER
        + "GATE_VERSION = 'verifier-orchestrator@2.2.0'\n"
        "\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verifier_orchestrator.verify')\n"
        "    return {'component_id': component_id, 'criteria': [], 'requirement_results': {},\n"
        "            'interface_drift': False, 'mutation_score': None, 'mutation_error': None,\n"
        "            'overall': 'pass'}\n",
    )

    _write(
        gen / "license-scanner" / "license_scanner.py",
        LOG_HELPER
        + "def gate_version(repo_root):\n"
        "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
        "\n"
        "def scan(component_id, repo_root):\n"
        "    _log('license_scanner.scan')\n"
        "    return {'component_id': component_id, 'gate_version': gate_version(repo_root),\n"
        "            'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
        "            'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n",
    )

    _write(
        gen / "secret-scanner" / "secret_scanner.py",
        LOG_HELPER
        + "def gate_version(repo_root):\n"
        "    return 'secret_scanner@0.0.0'\n"
        "\n"
        "def scan(repo_root):\n"
        "    _log('secret_scanner.scan')\n"
        "    return {'scope': 'full', 'gate_version': gate_version(repo_root), 'flagged': False,\n"
        "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
        "            'notification_delivery_error': None, 'cache_hit': False}\n",
    )

    _write(
        gen / "provenance-tracker" / "provenance_tracker.py",
        LOG_HELPER
        + "import json\n"
        "from pathlib import Path\n"
        "\n"
        "def _plain(v):\n"
        "    if v is None or isinstance(v, (str, int, float, bool)):\n"
        "        return v\n"
        "    if isinstance(v, dict):\n"
        "        return {str(k): _plain(x) for k, x in v.items()}\n"
        "    if isinstance(v, (list, tuple)):\n"
        "        return [_plain(x) for x in v]\n"
        "    if hasattr(v, 'to_dict'):\n"
        "        return _plain(v.to_dict())\n"
        "    if hasattr(v, '__dict__'):\n"
        "        return {k: _plain(x) for k, x in vars(v).items() if not k.startswith('_')}\n"
        "    return repr(v)\n"
        "\n"
        "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('provenance_tracker.write_attempt_record')\n"
        "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
        "    ts = '2026-01-01T00:00:00Z'\n"
        "    rec = {'attempt_id': ts + '-a1b2c3', 'component_id': component_id, 'timestamp': ts,\n"
        "           'spec_bundle_hash': spec_bundle_hash, 'generation': _plain(generation_result),\n"
        "           'verification': _plain(verification_report)}\n"
        "    d = Path(repo_root) / '.hotdocs' / 'attempts' / slug\n"
        "    d.mkdir(parents=True, exist_ok=True)\n"
        "    (d / (rec['attempt_id'] + '.json')).write_text(json.dumps(rec), encoding='utf-8')\n"
        "    return rec\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('provenance_tracker.check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
        "            'not_ready_reasons': []}\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n",
    )

    _write(
        gen / "provenance-writer" / "provenance_writer.py",
        LOG_HELPER
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('provenance_writer.write_provenance')\n"
        "    return None\n"
        "\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('provenance_writer.write_sealed_provenance')\n"
        "    return None\n",
    )

    _write(
        gen / "test-author" / "test_author.py",
        LOG_HELPER
        + "GATE_VERSION = 'generated_test@1.1.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log('test_author.author_test')\n"
        "    return {'component_id': 'comp-foo', 'criterion_id': 'AC-FOO-001', 'model': model,\n"
        "            'seed': seed, 'prompt_version': 'v1', 'cache_hit': False, 'file': None,\n"
        "            'model_call_error': {'category': 'network', 'message': 'n'}}\n",
    )

    _write(
        gen / "llm-endpoint" / "llm_endpoint.py",
        LOG_HELPER
        + "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('llm_endpoint.complete')\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n",
    )


def test_ac_gate_003c_model_call_error_blocks_after_single_generator_call(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))

    _build_fixture(repo_root)
    _write_fakes(repo_root)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0, llm_backend=None, retry_feedback=None
    )

    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]

    assert calls.count("generator.generate") == 1, calls
    assert "verifier_orchestrator.verify" not in calls, calls

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"
    mce = field(result, "model_call_error")
    assert field(mce, "category") == "timeout"
    assert field(mce, "message") == "t"
    if isinstance(mce, dict):
        assert mce == ERROR
    assert field(result, "verification") is None
    assert field(result, "provenance_hit") is False
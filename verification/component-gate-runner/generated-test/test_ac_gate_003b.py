# hotdocs-criterion: sha256:550889f3a8ae7ef2e755f69d6869bef60a4bcba2bb4d955826f7c190bf0bd844
import os
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_ENV = "GATE_TEST_AC_GATE_003B_LOG"

LOG_HELPER = (
    "import os\n"
    "\n"
    "def _log(line):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "def _f(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
    "_HASH = 'sha256:' + '0' * 64\n"
    "\n"
)


PROVENANCE_CHECKER = LOG_HELPER + (
    "import types\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key')\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key')\n"
    "    return types.SimpleNamespace(\n"
    "        spec_bundle_hash=_HASH,\n"
    "        gate_versions={\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.1.0',\n"
    "            'verifier': 'verifier-orchestrator@2.2.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "        },\n"
    "    )\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance')\n"
    "    return {'hit': False, 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance')\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER = LOG_HELPER + (
    "def assemble(component_id, repo_root=None, mode='cold'):\n"
    "    _log('assemble ' + repr(mode))\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': _HASH,\n"
    "        'spec': 'Foo doubles a number.',\n"
    "        'interface': 'foo(x: int) -> int',\n"
    "        'constraints': 'None.',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '- **Foo** - a test term.',\n"
    "        'hint_code': None,\n"
    "    }\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root=None):\n"
    "    _log('assemble_criterion')\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001',\n"
    "        'criterion_text': 'Given x = 2',\n"
    "        'requirement_text': 'foo(x) MUST return 2 * x.',\n"
    "        'interface': 'foo(x: int) -> int',\n"
    "        'glossary': '- **Foo** - a test term.',\n"
    "        'dependency_interfaces': {},\n"
    "    }\n"
)


GENERATOR = LOG_HELPER + (
    "GATE_VERSION = 'generator@2.0.0'\n"
    "PROMPT_VERSION = 'v10'\n"
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    _log('generate ' + repr(retry_feedback))\n"
    "    return {\n"
    "        'component_id': _f(bundle, 'component_id'),\n"
    "        'spec_bundle_hash': _f(bundle, 'spec_bundle_hash'),\n"
    "        'model': model,\n"
    "        'prompt_version': PROMPT_VERSION,\n"
    "        'cache_hit': False,\n"
    "        'files': {'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
    "        'model_call_error': None,\n"
    "        'refused': None,\n"
    "        'retry_feedback': retry_feedback,\n"
    "    }\n"
)


VERIFIER_ORCHESTRATOR = LOG_HELPER + (
    "GATE_VERSION = 'verifier-orchestrator@2.2.0'\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify')\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'generated-test', 'result': 'pass'},\n"
    "            {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'generated-test', 'result': 'fail',\n"
    "             'failure_detail': {'message': 'foo(3) equals 6 failed', 'expected': 6, 'actual': 5},\n"
    "             'failure_origin': 'implementation'},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass', 'R-FOO-002': 'fail'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'overall': 'fail',\n"
    "    }\n"
)


LICENSE_SCANNER = LOG_HELPER + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan')\n"
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


SECRET_SCANNER = LOG_HELPER + (
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "def _result(scope):\n"
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
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return _result('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files')\n"
    "    return _result('precommit')\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_TRACKER = LOG_HELPER + (
    "import json\n"
    "from pathlib import Path\n"
    "\n"
    "def _plain(value):\n"
    "    if value is None or isinstance(value, dict):\n"
    "        return value\n"
    "    if hasattr(value, 'to_dict'):\n"
    "        return value.to_dict()\n"
    "    return dict(vars(value))\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record')\n"
    "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
    "    record = {\n"
    "        'attempt_id': '2026-11-17T00:00:00Z-aaaaaa',\n"
    "        'component_id': component_id,\n"
    "        'timestamp': '2026-11-17T00:00:00Z',\n"
    "        'spec_bundle_hash': spec_bundle_hash,\n"
    "        'generation': _plain(generation_result),\n"
    "        'verification': _plain(verification_report),\n"
    "    }\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / slug\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    (d / (record['attempt_id'].replace(':', '-') + '.json')).write_text(json.dumps(record, default=str), encoding='utf-8')\n"
    "    return record\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {}, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


PROVENANCE_WRITER = LOG_HELPER + (
    "class InvalidSealedInputError(Exception):\n"
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
    "    return None\n"
)


TEST_AUTHOR = LOG_HELPER + (
    "GATE_VERSION = 'generated_test@1.1.0'\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    _log('author_test')\n"
    "    return {\n"
    "        'component_id': _f(bundle, 'component_id'),\n"
    "        'criterion_id': _f(bundle, 'criterion_id'),\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'file': {'path': 'verification/foo/generated-test/test_ac_foo_001.py', 'content': 'def test_x():\\n    pass\\n'},\n"
    "        'model_call_error': None,\n"
    "    }\n"
)


LLM_ENDPOINT = LOG_HELPER + (
    "DEFAULT_TIMEOUT_SECONDS = 600\n"
    "\n"
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    _log('complete')\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generator": GENERATOR,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-tracker": PROVENANCE_TRACKER,
    "provenance-writer": PROVENANCE_WRITER,
    "test-author": TEST_AUTHOR,
    "llm-endpoint": LLM_ENDPOINT,
}


COMPONENT_MD = (
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
    "Foo doubles a number.\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    for n in ("001", "002"):
        rid = "R-FOO-" + n
        _write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** \u2014 `foo(x)` MUST return `2 * x`.\n",
        )
        acid = "AC-FOO-" + n
        _write(
            comp / "acceptance" / (acid + ".md"),
            "# " + acid + "\n\n"
            "Covers: " + rid + "\n"
            "Kind: generated-test\n\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n",
        )
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    for slug, source in FAKES.items():
        module_name = slug.replace("-", "_")
        _write(repo_root / "gen" / slug / (module_name + ".py"), source)


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def test_ac_gate_003b_single_generator_call_no_retry_feedback_blocks_on_verification_failure(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    _build_fixture(repo_root)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock-model", seed=0, llm_backend=None
    )

    calls = _read_log(log_path)
    generate_calls = [c for c in calls if c.startswith("generate ")]
    assert len(generate_calls) == 1, calls
    assert generate_calls[0] == "generate " + repr(None), generate_calls

    # The faked verify must have produced the failing report the result reflects.
    assert "verify" in calls, calls

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"
    assert field(result, "model_call_error") is None

    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "fail"
    assert field(verification, "requirement_results") == {"R-FOO-001": "pass", "R-FOO-002": "fail"}
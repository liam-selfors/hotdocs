# hotdocs-criterion: sha256:f1c836830657b1982d254092825bb870b69a89db5da3fb1799c10848fe0dadb8
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE012_CALL_LOG"
HIT_ENV = "GATE012_HIT"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_SRC = (
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(entry):\n"
    "    path = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "def _verification_report(component_id):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [\n"
    "            {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'generated-test', 'result': 'pass'},\n"
    "        ],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                    'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "                    'lockfile_sha256': None}],\n"
    "        'overall': 'pass',\n"
    "    }\n"
    "\n"
    "def _license_scan(component_id):\n"
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
    "def _secret_scan():\n"
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
)


PROVENANCE_CHECKER_SRC = COMMON_SRC + (
    "class _Key:\n"
    "    def __init__(self):\n"
    "        self.spec_bundle_hash = 'sha256:abc'\n"
    "        self.gate_versions = {\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        }\n"
    "        self.assets = [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                        'adapter_sha256': 'sha256:00', 'versions': {'python': '3.12.4'},\n"
    "                        'lockfile_sha256': None}]\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key'})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key'})\n"
    "    return _Key()\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance'})\n"
    "    if os.environ.get(" + repr(HIT_ENV) + ") == '1':\n"
    "        return {'hit': True, 'reason': None,\n"
    "                'verification_report': _verification_report(component_id),\n"
    "                'license_scan': _license_scan(component_id),\n"
    "                'secret_scan': _secret_scan()}\n"
    "    return {'hit': False, 'reason': 'spec changed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance'})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER_SRC = COMMON_SRC + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'call': 'assemble'})\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc',\n"
    "        'spec': 'spec',\n"
    "        'interface': 'interface',\n"
    "        'constraints': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'dependency_context': {},\n"
    "        'dependency_usage': {},\n"
    "        'vars': {},\n"
    "        'glossary': '',\n"
    "        'hint_code': None,\n"
    "    }\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'call': 'assemble_criterion'})\n"
    "    return {\n"
    "        'component_id': component_id, 'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001', 'criterion_text': '', 'requirement_text': '',\n"
    "        'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': '',\n"
    "    }\n"
)


GENERATION_LOOP_SRC = COMMON_SRC + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    target = Path(repo_root) / 'verification' / 'foo' / 'generated-test' / 'test_ac_foo_001.py'\n"
    "    _log({'call': 'run_attempts', 'exists': target.exists()})\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': 'sha256:abc', 'model': model,\n"
    "        'prompt_version': 'v1', 'cache_hit': False, 'files': {'foo.py': 'X = 1\\n'},\n"
    "        'model_call_error': None, 'refused': None, 'retry_feedback': retry_feedback,\n"
    "        'mode': 'single', 'transcript_sha256': None, 'turns': 1, 'tool_calls': 0,\n"
    "        'isolation': None,\n"
    "    }\n"
    "    report = _verification_report(component_id)\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, report)\n"
    "    return {\n"
    "        'passed': True,\n"
    "        'stop_reason': 'passed',\n"
    "        'attempts': [attempt],\n"
    "        'generation_result': generation_result,\n"
    "        'verification_report': report,\n"
    "        'surface_report': {'ok': True, 'findings': []},\n"
    "    }\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures'})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)


PROVENANCE_TRACKER_SRC = COMMON_SRC + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record'})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log({'call': 'check_readiness'})\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {},\n"
    "            'capabilities': {}, 'secret_scan': None, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log({'call': 'last_requirement_failures'})\n"
    "    return []\n"
)


LICENSE_SCANNER_SRC = COMMON_SRC + (
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan'})\n"
    "    return _license_scan(component_id)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)


SECRET_SCANNER_SRC = COMMON_SRC + (
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return _secret_scan()\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
)


PROVENANCE_WRITER_SRC = COMMON_SRC + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance'})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance'})\n"
    "    return None\n"
)


VERIFIER_SRC = COMMON_SRC + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify'})\n"
    "    return _verification_report(component_id)\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root, log_path, monkeypatch, hit):
    monkeypatch.setenv(LOG_ENV, str(log_path))
    if hit:
        monkeypatch.setenv(HIT_ENV, "1")
    else:
        monkeypatch.delenv(HIT_ENV, raising=False)

    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — foo MUST do a thing.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\n`foo()`\n")

    gen = repo_root / "gen"
    _write(gen / "provenance-checker" / "provenance_checker.py", PROVENANCE_CHECKER_SRC)
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", SPEC_BUNDLE_ASSEMBLER_SRC)
    _write(gen / "generation-loop" / "generation_loop.py", GENERATION_LOOP_SRC)
    _write(gen / "provenance-tracker" / "provenance_tracker.py", PROVENANCE_TRACKER_SRC)
    _write(gen / "license-scanner" / "license_scanner.py", LICENSE_SCANNER_SRC)
    _write(gen / "secret-scanner" / "secret_scanner.py", SECRET_SCANNER_SRC)
    _write(gen / "provenance-writer" / "provenance_writer.py", PROVENANCE_WRITER_SRC)
    _write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_SRC)

    test_file = repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_001.py"
    _write(test_file, "def test_placeholder():\n    assert True\n")
    return test_file


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_reauthor_deletes_test_file_before_run_attempts_on_miss(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    test_file = _build_repo(repo_root, log_path, monkeypatch, hit=False)
    assert test_file.exists()

    component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--reauthor=AC-FOO-001",
         "--repo-root=" + str(repo_root)]
    )

    entries = _read_log(log_path)
    run_calls = [e for e in entries if e.get("call") == "run_attempts"]
    assert len(run_calls) >= 1, entries
    assert run_calls[0]["exists"] is False


def test_reauthor_keeps_test_file_on_short_circuiting_hit(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    test_file = _build_repo(repo_root, log_path, monkeypatch, hit=True)
    assert test_file.exists()

    component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--reauthor=AC-FOO-001",
         "--repo-root=" + str(repo_root)]
    )

    entries = _read_log(log_path)
    assert any(e.get("call") == "check_provenance" for e in entries), entries
    assert not any(e.get("call") == "run_attempts" for e in entries), entries
    assert test_file.exists()


def test_reauthor_unknown_criterion_is_usage_error(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_repo(repo_root, log_path, monkeypatch, hit=False)
    capsys.readouterr()

    rc = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--reauthor=AC-FOO-009",
         "--repo-root=" + str(repo_root)]
    )
    captured = capsys.readouterr()

    assert rc == 2
    err_lines = [line for line in captured.err.splitlines() if line.strip()]
    assert err_lines, captured.err
    first = err_lines[0]
    assert first.startswith("usage error: "), first
    assert "AC-FOO-009 is not a generated-test criterion of comp-foo" in first
    assert _read_log(log_path) == []
# hotdocs-criterion: sha256:36a049b354fb2b8d0790143ebe330b3b2e133a1589dea787e9d55d48dadaef05
import json
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_TEST_LOG_AC_GATE_010"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(entry):\n"
    "    path = os.environ[" + repr(LOG_ENV) + "]\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
)

PROVENANCE_CHECKER_SRC = LOG_HELPER + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key'})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key'})\n"
    "    return ProvenanceKey(\n"
    "        'sha256:' + 'ab' * 32,\n"
    "        {\n"
    "            'compiler': 'criterion-compiler@1.0.0',\n"
    "            'generated_test': 'generated_test@1.0.0',\n"
    "            'verifier': 'verifier-orchestrator@2.0.0',\n"
    "            'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'secret_scanner': 'secret_scanner@0.0.0',\n"
    "            'generator': 'generator@3.0.0+v11',\n"
    "        },\n"
    "        [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "          'adapter_sha256': 'sha256:' + 'cd' * 32,\n"
    "          'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
    "    )\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance'})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance'})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
    "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
    "            'owners': None, 'source_hash': None, 'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'call': 'assemble', 'mode': mode})\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:' + 'ab' * 32,\n"
    "        'spec': 'spec', 'interface': 'interface', 'constraints': '',\n"
    "        'dependency_interfaces': {}, 'dependency_context': {},\n"
    "        'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None,\n"
    "    }\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'call': 'assemble_criterion'})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id,\n"
    "            'covers': '', 'criterion_text': '', 'requirement_text': '',\n"
    "            'interface': '', 'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP_SRC = LOG_HELPER + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "class AttemptLoopResult:\n"
    "    def __init__(self, passed, stop_reason, attempts, generation_result,\n"
    "                 verification_report, surface_report):\n"
    "        self.passed = passed\n"
    "        self.stop_reason = stop_reason\n"
    "        self.attempts = attempts\n"
    "        self.generation_result = generation_result\n"
    "        self.verification_report = verification_report\n"
    "        self.surface_report = surface_report\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'passed': self.passed, 'stop_reason': self.stop_reason,\n"
    "                'attempts': self.attempts,\n"
    "                'generation_result': self.generation_result,\n"
    "                'verification_report': self.verification_report,\n"
    "                'surface_report': self.surface_report}\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'call': 'make_closures'})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single',\n"
    "                 max_attempts=3, retry_feedback=None, seed=0, llm_backend=None,\n"
    "                 allow_unisolated_exec=False, on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'max_attempts': max_attempts, 'mode': mode,\n"
    "          'max_attempts_type': type(max_attempts).__name__})\n"
    "    generation_result = {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:' + 'ab' * 32,\n"
    "        'model': model, 'prompt_version': 'v11', 'cache_hit': False,\n"
    "        'files': {'foo.py': 'X = 1\\n'}, 'model_call_error': None,\n"
    "        'refused': None, 'retry_feedback': retry_feedback, 'mode': mode,\n"
    "        'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
    "    }\n"
    "    verification_report = {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001',\n"
    "                      'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False, 'mutation_score': 1.0, 'mutation_error': None,\n"
    "        'assets': [{'kind': 'python', 'path': '.', 'definition_sha256': None,\n"
    "                    'adapter_sha256': 'sha256:' + 'cd' * 32,\n"
    "                    'versions': {'python': '3.12.4'}, 'lockfile_sha256': None}],\n"
    "        'overall': 'pass',\n"
    "    }\n"
    "    surface_report = {'ok': True, 'findings': []}\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
    "               'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "               'failed_requirements': [], 'transcript_sha256': None,\n"
    "               'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, verification_report)\n"
    "    return AttemptLoopResult(True, 'passed', [attempt], generation_result,\n"
    "                             verification_report, surface_report)\n"
)

PROVENANCE_TRACKER_SRC = LOG_HELPER + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record'})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3',\n"
    "            'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z',\n"
    "            'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': dict(generation_result),\n"
    "            'verification': dict(verification_report) if verification_report is not None else None}\n"
)

LICENSE_SCANNER_SRC = LOG_HELPER + (
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan'})\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None,\n"
    "            'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SCANNER_SRC = LOG_HELPER + (
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@0.0.0',\n"
    "            'flagged': False, 'matches': [], 'allowed': [],\n"
    "            'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
)

PROVENANCE_WRITER_SRC = LOG_HELPER + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance'})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance'})\n"
    "    return None\n"
)

VERIFIER_SRC = LOG_HELPER + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify'})\n"
    "    return {'component_id': component_id, 'criteria': [],\n"
    "            'requirement_results': {}, 'interface_drift': False,\n"
    "            'mutation_score': None, 'mutation_error': None, 'assets': [],\n"
    "            'overall': 'pass'}\n"
)

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER_SRC,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER_SRC,
    ("generation-loop", "generation_loop"): GENERATION_LOOP_SRC,
    ("provenance-tracker", "provenance_tracker"): PROVENANCE_TRACKER_SRC,
    ("license-scanner", "license_scanner"): LICENSE_SCANNER_SRC,
    ("secret-scanner", "secret_scanner"): SECRET_SCANNER_SRC,
    ("provenance-writer", "provenance_writer"): PROVENANCE_WRITER_SRC,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_SRC,
}

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: true\n"
    "source_path: legacy/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "A fixture component.\n"
)

VALID_TOML = "[generate]\nmax_attempts = 5\nmode = \"agentic\"\n"


def make_repo(tmp_path, monkeypatch, toml_text=None):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for (slug, module), src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(src, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "foo"
    comp.mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    if toml_text is not None:
        (repo_root / "hotdocs.toml").write_text(toml_text, encoding="utf-8")
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    return repo_root, log_path


def read_calls(log_path):
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def run_attempts_calls(log_path):
    return [c for c in read_calls(log_path) if c.get("call") == "run_attempts"]


def test_file_values_reach_run_attempts(tmp_path, monkeypatch, capsys):
    repo_root, log_path = make_repo(tmp_path, monkeypatch, VALID_TOML)
    code = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)]
    )
    captured = capsys.readouterr()
    calls = run_attempts_calls(log_path)
    assert len(calls) == 1, (code, captured.err, read_calls(log_path))
    assert calls[0]["max_attempts"] == 5
    assert calls[0]["max_attempts_type"] == "int"
    assert calls[0]["mode"] == "agentic"


def test_flags_override_file_values(tmp_path, monkeypatch, capsys):
    repo_root, log_path = make_repo(tmp_path, monkeypatch, VALID_TOML)
    code = component_gate_runner.main(
        [
            "generate", "comp-foo", "--model=m",
            "--repo-root=" + str(repo_root),
            "--max-attempts=1", "--mode=single",
        ]
    )
    captured = capsys.readouterr()
    calls = run_attempts_calls(log_path)
    assert len(calls) == 1, (code, captured.err, read_calls(log_path))
    assert calls[0]["max_attempts"] == 1
    assert calls[0]["max_attempts_type"] == "int"
    assert calls[0]["mode"] == "single"


@pytest.mark.parametrize(
    "toml_text, extra",
    [
        ("[generate]\nmax_attempts = 5\nmode = \"turbo\"\n", []),
        (VALID_TOML, ["--max-attempts=0"]),
        (VALID_TOML, ["--mode=turbo"]),
        (None, ["--max-attempts=0"]),
        (None, ["--mode=turbo"]),
    ],
    ids=[
        "file-mode-turbo",
        "flag-max-attempts-0-with-file",
        "flag-mode-turbo-with-file",
        "flag-max-attempts-0",
        "flag-mode-turbo",
    ],
)
def test_invalid_values_are_usage_errors(tmp_path, monkeypatch, capsys, toml_text, extra):
    repo_root, log_path = make_repo(tmp_path, monkeypatch, toml_text)
    code = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)] + extra
    )
    captured = capsys.readouterr()
    assert code == 2
    err_lines = captured.err.splitlines()
    assert err_lines, "expected stderr output"
    assert err_lines[0].startswith("usage error: ")
    assert run_attempts_calls(log_path) == []
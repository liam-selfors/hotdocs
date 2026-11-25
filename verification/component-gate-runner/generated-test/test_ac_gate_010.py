# hotdocs-criterion: sha256:8a8617a9fa5c4ecd58525b19f589db034318af3d1623afefec4f8664b4330f7e
import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE010_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json\n"
    "import os\n"
    "import types\n"
    "\n"
    "def _log(rec):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as f:\n"
    "        f.write(json.dumps(rec) + '\\n')\n"
    "\n"
)

VERIFICATION_REPORT_SRC = (
    "def _report(component_id):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criteria': [{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}],\n"
    "        'requirement_results': {'R-FOO-001': 'pass'},\n"
    "        'interface_drift': False,\n"
    "        'mutation_score': 0.9,\n"
    "        'mutation_error': None,\n"
    "        'assets': [],\n"
    "        'overall': 'pass',\n"
    "    }\n"
    "\n"
)

PROVENANCE_CHECKER_SRC = (
    LOG_HELPER
    + "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key'})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key'})\n"
    "    return types.SimpleNamespace(\n"
    "        spec_bundle_hash='sha256:abc',\n"
    "        gate_versions={'compiler': 'c@1', 'generated_test': 'g@1', 'verifier': 'v@1',\n"
    "                       'license_scanner': 'l@1', 'secret_scanner': 's@1', 'generator': 'gen@1+v1'},\n"
    "        assets=[],\n"
    "    )\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance'})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance'})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)

ASSEMBLER_SRC = (
    LOG_HELPER
    + "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'call': 'assemble'})\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'spec_bundle_hash': 'sha256:abc',\n"
    "        'spec': 'spec', 'interface': 'iface', 'constraints': '',\n"
    "        'dependency_interfaces': {}, 'dependency_context': {}, 'dependency_usage': {},\n"
    "        'vars': {}, 'glossary': '', 'hint_code': None,\n"
    "    }\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'call': 'assemble_criterion'})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP_SRC = (
    LOG_HELPER
    + VERIFICATION_REPORT_SRC
    + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log({'call': 'run_attempts', 'max_attempts': max_attempts, 'mode': mode})\n"
    "    generation_result = {\n"
    "        'component_id': component_id, 'spec_bundle_hash': 'sha256:abc', 'model': model,\n"
    "        'prompt_version': 'v1', 'cache_hit': False, 'files': {'foo.py': 'X = 1\\n'},\n"
    "        'model_call_error': None, 'refused': None, 'retry_feedback': retry_feedback,\n"
    "        'mode': mode, 'transcript_sha256': None, 'turns': 1, 'tool_calls': 0, 'isolation': None,\n"
    "    }\n"
    "    report = _report(component_id)\n"
    "    attempt = {'number': 1, 'outcome': 'passed', 'retry_feedback': [], 'error_category': None,\n"
    "               'surface_ok': True, 'overall': 'pass', 'failed_requirements': [],\n"
    "               'transcript_sha256': None, 'reauthored_tests': []}\n"
    "    if on_attempt is not None:\n"
    "        on_attempt(attempt, generation_result, report)\n"
    "    return {\n"
    "        'passed': True, 'stop_reason': 'passed', 'attempts': [attempt],\n"
    "        'generation_result': generation_result, 'verification_report': report,\n"
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

TRACKER_SRC = (
    LOG_HELPER
    + "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record'})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'secret_scan': None, 'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)

LICENSE_SRC = (
    LOG_HELPER
    + "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan'})\n"
    "    return {'component_id': component_id, 'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
    "            'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SRC = (
    LOG_HELPER
    + "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return {'scope': 'full', 'gate_version': 'secret_scanner@3.1.0', 'flagged': False,\n"
    "            'matches': [], 'allowed': [], 'unused_allowlist_entries': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return scan(repo_root)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0'\n"
)

WRITER_SRC = (
    LOG_HELPER
    + "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance'})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance'})\n"
    "    return None\n"
)

VERIFIER_SRC = (
    LOG_HELPER
    + VERIFICATION_REPORT_SRC
    + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify'})\n"
    "    return _report(component_id)\n"
)

FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER_SRC,
    ("spec-bundle-assembler", "spec_bundle_assembler"): ASSEMBLER_SRC,
    ("generation-loop", "generation_loop"): GENERATION_LOOP_SRC,
    ("provenance-tracker", "provenance_tracker"): TRACKER_SRC,
    ("license-scanner", "license_scanner"): LICENSE_SRC,
    ("secret-scanner", "secret_scanner"): SECRET_SRC,
    ("provenance-writer", "provenance_writer"): WRITER_SRC,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_SRC,
}


def build_repo(repo_root, toml_text):
    repo_root.mkdir(parents=True, exist_ok=True)
    for (slug, module), src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (module + ".py")).write_text(src, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True, exist_ok=True)
    (comp / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp / "interface").mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(
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
        "A fixture component.\n",
        encoding="utf-8",
    )
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "**R-FOO-001** — Foo MUST exist.\n", encoding="utf-8"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n", encoding="utf-8"
    )
    (comp / "interface" / "library.md").write_text("# Library\n\nfoo()\n", encoding="utf-8")
    if toml_text is not None:
        (repo_root / "hotdocs.toml").write_text(toml_text, encoding="utf-8")


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run_attempts_calls(log_path):
    return [r for r in read_log(log_path) if r.get("call") == "run_attempts"]


VALID_TOML = "[generate]\nmax_attempts = 5\nmode = \"agentic\"\n"


@pytest.fixture
def log_path(tmp_path, monkeypatch):
    p = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(p))
    return p


def test_toml_values_reach_run_attempts(tmp_path, log_path, capsys):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, VALID_TOML)
    component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)]
    )
    capsys.readouterr()
    calls = run_attempts_calls(log_path)
    assert len(calls) == 1, read_log(log_path)
    assert calls[0]["max_attempts"] == 5
    assert calls[0]["mode"] == "agentic"


def test_flags_override_toml_values(tmp_path, log_path, capsys):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, VALID_TOML)
    component_gate_runner.main(
        [
            "generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root),
            "--max-attempts=1", "--mode=single",
        ]
    )
    capsys.readouterr()
    calls = run_attempts_calls(log_path)
    assert len(calls) == 1, read_log(log_path)
    assert calls[0]["max_attempts"] == 1
    assert calls[0]["mode"] == "single"


@pytest.mark.parametrize(
    "toml_text, extra",
    [
        ("[generate]\nmode = \"turbo\"\n", []),
        (None, ["--max-attempts=0"]),
        (None, ["--mode=turbo"]),
    ],
    ids=["toml-mode-turbo", "flag-max-attempts-0", "flag-mode-turbo"],
)
def test_invalid_values_are_usage_errors(tmp_path, log_path, capsys, toml_text, extra):
    repo_root = tmp_path / "repo"
    build_repo(repo_root, toml_text)
    capsys.readouterr()
    rc = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)] + extra
    )
    captured = capsys.readouterr()
    assert rc == 2
    lines = captured.err.splitlines()
    assert lines, "expected a usage error on stderr"
    assert lines[0].startswith("usage error: "), captured.err
    assert run_attempts_calls(log_path) == []
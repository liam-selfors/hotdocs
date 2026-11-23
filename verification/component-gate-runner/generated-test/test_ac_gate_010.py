# hotdocs-criterion: sha256:9f90171952eaa46f3d28ad5be15aaa81f2cf3c6e7104defb24d545249658507e
import json
import os
from pathlib import Path

import pytest

import component_gate_runner


LOG_ENV = "GATE_AC010_LOG"

TOML_VALID = "[generate]\nmax_attempts = 5\nmode = \"agentic\"\n"
TOML_BAD_MODE = "[generate]\nmax_attempts = 5\nmode = \"turbo\"\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


HEADER = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(rec):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(rec, default=repr) + '\\n')\n"
    "\n"
    "class _Obj:\n"
    "    def __init__(self, **kw):\n"
    "        self.__dict__.update(kw)\n"
    "    def to_dict(self):\n"
    "        return dict(self.__dict__)\n"
    "\n"
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

PROVENANCE_CHECKER = HEADER + (
    "class _Key:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions, assets):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "        self.assets = assets\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_sealed_key'})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'fn': 'current_provenance_key'})\n"
    "    return _Key('sha256:abc', {'compiler': 'c@1', 'generated_test': 'g@1', 'verifier': 'v@1',\n"
    "                'license_scanner': 'l@1', 'secret_scanner': 's@1', 'generator': 'gen@1+v1'},\n"
    "                [{'kind': 'python', 'path': '.', 'definition_sha256': None, 'adapter_sha256': None,\n"
    "                  'versions': {}, 'lockfile_sha256': None}])\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'fn': 'check_provenance'})\n"
    "    return {'hit': False, 'reason': 'no manifest', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'fn': 'check_sealed_provenance'})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)

SPEC_BUNDLE_ASSEMBLER = HEADER + (
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'fn': 'assemble', 'mode': mode})\n"
    "    return {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc', 'spec': '',\n"
    "            'interface': '', 'constraints': '', 'dependency_interfaces': {},\n"
    "            'dependency_context': {}, 'dependency_usage': {}, 'vars': {}, 'glossary': '',\n"
    "            'hint_code': None}\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'fn': 'assemble_criterion'})\n"
    "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
    "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
    "            'dependency_interfaces': {}, 'testing': ''}\n"
)

GENERATION_LOOP = HEADER + (
    "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
    "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
    "                      'missing_asset', 'malformed_layout')\n"
    "\n"
    "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
    "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
    "                 on_attempt=None):\n"
    "    _log({'fn': 'run_attempts', 'max_attempts': max_attempts, 'mode': mode})\n"
    "    gen = {'component_id': component_id, 'spec_bundle_hash': 'sha256:abc', 'model': model,\n"
    "           'prompt_version': 'v1', 'cache_hit': False, 'files': {'foo.py': 'X = 1\\n'},\n"
    "           'model_call_error': None, 'refused': None, 'retry_feedback': retry_feedback,\n"
    "           'mode': mode, 'transcript_sha256': None, 'turns': 1, 'tool_calls': 0,\n"
    "           'isolation': None}\n"
    "    return {\n"
    "        'passed': True,\n"
    "        'stop_reason': 'passed',\n"
    "        'attempts': [{'number': 1, 'outcome': 'passed', 'retry_feedback': [],\n"
    "                      'error_category': None, 'surface_ok': True, 'overall': 'pass',\n"
    "                      'failed_requirements': [], 'transcript_sha256': None,\n"
    "                      'reauthored_tests': []}],\n"
    "        'generation_result': gen,\n"
    "        'verification_report': _report(component_id),\n"
    "        'surface_report': {'ok': True, 'findings': []},\n"
    "    }\n"
    "\n"
    "def make_closures(model, seed, repo_root, llm_backend=None):\n"
    "    _log({'fn': 'make_closures'})\n"
    "    def test_author(bundle):\n"
    "        return {'model_call_error': None, 'file': None}\n"
    "    def judge(bundle):\n"
    "        return {'result': 'pass', 'rationale': None}\n"
    "    return (test_author, judge)\n"
)

PROVENANCE_TRACKER = HEADER + (
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log({'fn': 'write_attempt_record'})\n"
    "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
    "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "            'generation': {}, 'verification': None}\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    _log({'fn': 'check_readiness'})\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    _log({'fn': 'last_requirement_failures'})\n"
    "    return []\n"
)

VERIFIER_ORCHESTRATOR = HEADER + (
    "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
    "DEFAULT_TEST_TIMEOUT = 300.0\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'fn': 'verify'})\n"
    "    return _Obj(**_report(component_id))\n"
)

LICENSE_SCANNER = HEADER + (
    "def scan(component_id, repo_root):\n"
    "    _log({'fn': 'license_scan'})\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
    "            'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
)

SECRET_SCANNER = HEADER + (
    "def _result(scope):\n"
    "    return _Obj(scope=scope, gate_version='secret_scanner@3.1.0', flagged=False, matches=[],\n"
    "                allowed=[], unused_allowlist_entries=[], notified=False,\n"
    "                notification_delivery_error=None, cache_hit=False)\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log({'fn': 'secret_scan'})\n"
    "    return _result('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log({'fn': 'secret_scan_files'})\n"
    "    return _result('precommit')\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0'\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_WRITER = HEADER + (
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'fn': 'write_provenance'})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'fn': 'write_sealed_provenance'})\n"
    "    return None\n"
)

FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generation-loop": GENERATION_LOOP,
    "provenance-tracker": PROVENANCE_TRACKER,
    "verifier-orchestrator": VERIFIER_ORCHESTRATOR,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-writer": PROVENANCE_WRITER,
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


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    return repo_root, log_path


def read_calls(log_path):
    text = log_path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run_attempts_calls(log_path):
    return [c for c in read_calls(log_path) if c.get("fn") == "run_attempts"]


def test_file_values_used_when_flags_absent(repo):
    repo_root, log_path = repo
    (repo_root / "hotdocs.toml").write_text(TOML_VALID, encoding="utf-8")

    code = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)]
    )

    assert code == 0
    calls = run_attempts_calls(log_path)
    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 5
    assert calls[0]["mode"] == "agentic"


def test_flags_override_file_values(repo):
    repo_root, log_path = repo
    (repo_root / "hotdocs.toml").write_text(TOML_VALID, encoding="utf-8")

    code = component_gate_runner.main(
        [
            "generate",
            "comp-foo",
            "--model=m",
            "--repo-root=" + str(repo_root),
            "--max-attempts=1",
            "--mode=single",
        ]
    )

    assert code == 0
    calls = run_attempts_calls(log_path)
    assert len(calls) == 1
    assert calls[0]["max_attempts"] == 1
    assert calls[0]["mode"] == "single"


@pytest.mark.parametrize(
    "toml_text, extra_flags",
    [
        (TOML_BAD_MODE, []),
        (None, ["--max-attempts=0"]),
        (None, ["--mode=turbo"]),
    ],
    ids=["file-mode-turbo", "flag-max-attempts-0", "flag-mode-turbo"],
)
def test_invalid_values_are_usage_errors(repo, capsys, toml_text, extra_flags):
    repo_root, log_path = repo
    if toml_text is not None:
        (repo_root / "hotdocs.toml").write_text(toml_text, encoding="utf-8")
    capsys.readouterr()

    code = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--repo-root=" + str(repo_root)]
        + extra_flags
    )

    captured = capsys.readouterr()
    assert code == 2
    lines = captured.err.splitlines()
    assert lines, "expected output on stderr"
    assert lines[0].startswith("usage error: ")
    assert run_attempts_calls(log_path) == []
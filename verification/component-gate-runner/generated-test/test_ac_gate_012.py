# hotdocs-criterion: sha256:78233a3edc4b4d53e37ad5eed9550308997b4ee5a9b91484f988901265247dc8
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_AC012_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(line):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a') as f:\n"
    "        f.write(line + '\\n')\n"
    "\n"
)


VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"},
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": [],
    "overall": "pass",
}

LICENSE_SCAN = {
    "component_id": "comp-foo",
    "gate_version": "license_scanner@4.0.0-no-reference-corpus",
    "evaluated": False,
    "reason": "no-reference-corpus",
    "similarity_score": None,
    "block_threshold": None,
    "blocked": False,
    "matches": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

SECRET_SCAN = {
    "scope": "full",
    "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "flagged": False,
    "matches": [],
    "allowed": [],
    "unused_allowlist_entries": [],
    "notified": False,
    "notification_delivery_error": None,
    "cache_hit": False,
}

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@3.5.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": "sha256:00",
    "model": "m",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {},
    "model_call_error": {"category": "network", "message": "fake"},
    "refused": None,
    "retry_feedback": None,
    "mode": "single",
    "transcript_sha256": None,
    "turns": 1,
    "tool_calls": 0,
    "isolation": None,
}

LOOP_RESULT = {
    "passed": False,
    "stop_reason": "not_retried",
    "attempts": [
        {"number": 1, "outcome": "generation_failed", "retry_feedback": [],
         "error_category": "network", "surface_ok": None, "overall": None,
         "failed_requirements": [], "transcript_sha256": None,
         "reauthored_tests": []},
    ],
    "generation_result": GENERATION_RESULT,
    "verification_report": None,
    "surface_report": None,
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(repo_root, check_result):
    # Spec corpus
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
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
    write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — Foo MUST do a thing.\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # The existing generated test file
    write(
        repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_001.py",
        "def test_x():\n    assert True\n",
    )

    gen = repo_root / "gen"

    write(
        gen / "provenance-checker" / "provenance_checker.py",
        COMMON
        + "CHECK_RESULT = " + repr(check_result) + "\n"
        + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
        + "\n"
        + "class _Key:\n"
        + "    def __init__(self):\n"
        + "        self.spec_bundle_hash = " + repr("sha256:" + "ab" * 32) + "\n"
        + "        self.gate_versions = dict(GATE_VERSIONS)\n"
        + "        self.assets = []\n"
        + "\n"
        + "def current_sealed_key(component_id, repo_root):\n"
        + "    _log('current_sealed_key')\n"
        + "    return None\n"
        + "\n"
        + "def current_provenance_key(component_id, repo_root):\n"
        + "    _log('current_provenance_key')\n"
        + "    return _Key()\n"
        + "\n"
        + "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
        + "    _log('check_provenance')\n"
        + "    return dict(CHECK_RESULT)\n"
        + "\n"
        + "def check_sealed_provenance(component_id, repo_root):\n"
        + "    _log('check_sealed_provenance')\n"
        + "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed',\n"
        + "            'verification_report': None, 'license_scan': None, 'secret_scan': None,\n"
        + "            'owners': None, 'source_hash': None, 'written_at': None}\n",
    )

    write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        COMMON
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        + "    _log('assemble')\n"
        + "    return {'component_id': component_id, 'spec_bundle_hash': " + repr("sha256:" + "ab" * 32) + ",\n"
        + "            'spec': '', 'interface': '', 'constraints': '',\n"
        + "            'dependency_interfaces': {}, 'dependency_context': {},\n"
        + "            'dependency_usage': {}, 'vars': {}, 'glossary': '', 'hint_code': None}\n"
        + "\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    _log('assemble_criterion')\n"
        + "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': '',\n"
        + "            'criterion_text': '', 'requirement_text': '', 'interface': '',\n"
        + "            'glossary': '', 'dependency_interfaces': {}, 'testing': ''}\n",
    )

    write(
        gen / "generation-loop" / "generation_loop.py",
        COMMON
        + "LOOP_RESULT = " + repr(LOOP_RESULT) + "\n"
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        + "                      'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file',\n"
        + "                      'missing_asset', 'malformed_layout')\n"
        + "\n"
        + "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        + "                 retry_feedback=None, seed=0, llm_backend=None,\n"
        + "                 allow_unisolated_exec=False, on_attempt=None):\n"
        + "    p = Path(repo_root) / 'verification' / 'foo' / 'generated-test' / 'test_ac_foo_001.py'\n"
        + "    _log('run_attempts exists=' + str(p.exists()))\n"
        + "    return dict(LOOP_RESULT)\n"
        + "\n"
        + "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        + "    _log('make_closures')\n"
        + "    def test_author(bundle):\n"
        + "        return {'model_call_error': None, 'file': None}\n"
        + "    def judge(bundle):\n"
        + "        return {'result': 'pass', 'rationale': None}\n"
        + "    return (test_author, judge)\n",
    )

    write(
        gen / "provenance-tracker" / "provenance_tracker.py",
        COMMON
        + "def write_attempt_record(component_id, generation_result, verification_report,\n"
        + "                         spec_bundle_hash, repo_root):\n"
        + "    _log('write_attempt_record')\n"
        + "    return {'attempt_id': '2026-01-01T00:00:00Z-aaaaaa', 'component_id': component_id,\n"
        + "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        + "            'generation': {}, 'verification': None}\n",
    )

    write(
        gen / "license-scanner" / "license_scanner.py",
        COMMON
        + "LICENSE_SCAN = " + repr(LICENSE_SCAN) + "\n"
        + "\n"
        + "def scan(component_id, repo_root):\n"
        + "    _log('license_scan')\n"
        + "    return dict(LICENSE_SCAN)\n"
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    _log('license_gate_version')\n"
        + "    return LICENSE_SCAN['gate_version']\n",
    )

    write(
        gen / "secret-scanner" / "secret_scanner.py",
        COMMON
        + "SECRET_SCAN = " + repr(SECRET_SCAN) + "\n"
        + "\n"
        + "def scan(repo_root):\n"
        + "    _log('secret_scan')\n"
        + "    return dict(SECRET_SCAN)\n"
        + "\n"
        + "def scan_files(paths, repo_root=None):\n"
        + "    _log('secret_scan_files')\n"
        + "    d = dict(SECRET_SCAN)\n"
        + "    d['scope'] = 'precommit'\n"
        + "    return d\n"
        + "\n"
        + "def gate_version(repo_root):\n"
        + "    _log('secret_gate_version')\n"
        + "    return SECRET_SCAN['gate_version']\n"
        + "\n"
        + "def propose(repo_root):\n"
        + "    _log('secret_propose')\n"
        + "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )

    write(
        gen / "provenance-writer" / "provenance_writer.py",
        COMMON
        + "def write_provenance(component_id, inputs, repo_root):\n"
        + "    _log('write_provenance')\n"
        + "    return None\n"
        + "\n"
        + "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        + "    _log('write_sealed_provenance')\n"
        + "    return None\n",
    )

    write(
        gen / "verifier-orchestrator" / "verifier_orchestrator.py",
        COMMON
        + "GATE_VERSION = 'verifier-orchestrator@3.5.0'\n"
        + "DEFAULT_TEST_TIMEOUT = 300.0\n"
        + "VERIFICATION_REPORT = " + repr(VERIFICATION_REPORT) + "\n"
        + "\n"
        + "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        + "    _log('verify')\n"
        + "    return dict(VERIFICATION_REPORT)\n",
    )


def setup(tmp_path, monkeypatch, check_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log))
    monkeypatch.chdir(repo_root)
    build_repo(repo_root, check_result)
    return repo_root, log


def read_log(log):
    if not log.exists():
        return []
    return [line for line in log.read_text().splitlines() if line.strip()]


def test_reauthor_deletes_test_file_before_run_attempts_on_miss(tmp_path, monkeypatch):
    check_result = {
        "hit": False,
        "reason": "spec changed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
    repo_root, log = setup(tmp_path, monkeypatch, check_result)
    test_file = repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_001.py"
    assert test_file.exists()

    component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--reauthor=AC-FOO-001",
         "--repo-root=" + str(repo_root)]
    )

    calls = read_log(log)
    run_calls = [c for c in calls if c.startswith("run_attempts")]
    assert run_calls, "run_attempts was never called; calls: " + repr(calls)
    assert run_calls[0] == "run_attempts exists=False", repr(run_calls)


def test_reauthor_deletes_nothing_on_short_circuiting_hit(tmp_path, monkeypatch):
    check_result = {
        "hit": True,
        "reason": None,
        "verification_report": VERIFICATION_REPORT,
        "license_scan": LICENSE_SCAN,
        "secret_scan": SECRET_SCAN,
    }
    repo_root, log = setup(tmp_path, monkeypatch, check_result)
    test_file = repo_root / "verification" / "foo" / "generated-test" / "test_ac_foo_001.py"
    assert test_file.exists()

    component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--reauthor=AC-FOO-001",
         "--repo-root=" + str(repo_root)]
    )

    assert test_file.exists()


def test_reauthor_unknown_criterion_is_usage_error(tmp_path, monkeypatch, capsys):
    check_result = {
        "hit": False,
        "reason": "spec changed",
        "verification_report": None,
        "license_scan": None,
        "secret_scan": None,
    }
    repo_root, log = setup(tmp_path, monkeypatch, check_result)
    assert not (repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-009.md").exists()
    capsys.readouterr()

    code = component_gate_runner.main(
        ["generate", "comp-foo", "--model=m", "--reauthor=AC-FOO-009",
         "--repo-root=" + str(repo_root)]
    )

    captured = capsys.readouterr()
    assert code == 2
    lines = captured.err.splitlines()
    assert lines, "nothing printed to stderr"
    first = lines[0]
    assert first.startswith("usage error: "), repr(first)
    assert "AC-FOO-009 is not a generated-test criterion of comp-foo" in first, repr(first)
    assert read_log(log) == []
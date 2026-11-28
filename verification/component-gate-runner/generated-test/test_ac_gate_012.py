# hotdocs-criterion: sha256:98430b8bdeff6cab53b7c1d829515634d7c05704812b94254e9a58bc16eba85e
import json
from pathlib import Path

import component_gate_runner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SPEC_HASH = "sha256:" + "a" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.0.0",
    "verifier": "verifier-orchestrator@4.0.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
    "generator": "generator@3.0.0+v11",
}

SPEC_PARTS = {"spec": "sha256:" + "b" * 64, "dependency_code": "sha256:" + "c" * 64}

ASSETS = [
    {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": "sha256:" + "d" * 64,
        "versions": {"python": "3.12.4"},
        "lockfile_sha256": None,
    }
]

VERIFICATION_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "assets": ASSETS,
    "drivers": [],
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

GENERATION_RESULT = {
    "component_id": "comp-foo",
    "spec_bundle_hash": SPEC_HASH,
    "model": "m",
    "prompt_version": "v1",
    "cache_hit": False,
    "files": {},
    "model_call_error": {"category": "truncated_response", "message": "cut off"},
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
    "stop_reason": "max_attempts",
    "attempts": [
        {
            "number": 1,
            "outcome": "generation_failed",
            "retry_feedback": [],
            "error_category": "truncated_response",
            "surface_ok": None,
            "overall": None,
            "failed_requirements": [],
            "transcript_sha256": None,
            "reauthored_tests": [],
        }
    ],
    "generation_result": GENERATION_RESULT,
    "verification_report": None,
    "surface_report": None,
}

SPEC_BUNDLE = {
    "component_id": "comp-foo",
    "spec_bundle_hash": SPEC_HASH,
    "spec": "spec",
    "interface": "interface",
    "constraints": "",
    "dependency_interfaces": {},
    "dependency_context": {},
    "dependency_usage": {},
    "vars": {},
    "glossary": "",
    "hint_code": None,
    "spec_bundle_parts": SPEC_PARTS,
}

MISS = {
    "hit": False,
    "reason": "spec changed",
    "verification_report": None,
    "license_scan": None,
    "secret_scan": None,
}

HIT = {
    "hit": True,
    "reason": None,
    "verification_report": VERIFICATION_REPORT,
    "license_scan": LICENSE_SCAN,
    "secret_scan": SECRET_SCAN,
}


def _header(log):
    return (
        "import json\n"
        "import os\n"
        "from pathlib import Path\n"
        "LOG = " + repr(str(log)) + "\n"
        "def _log(name, **kw):\n"
        "    entry = {'call': name}\n"
        "    entry.update(kw)\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
    )


def _write(repo_root, slug, source):
    module = slug.replace("-", "_")
    d = repo_root / "gen" / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / (module + ".py")).write_text(source)


def _write_fakes(repo_root, log, check_result):
    h = _header(log)
    _write(
        repo_root,
        "provenance-checker",
        h
        + "CHECK_RESULT = " + repr(check_result) + "\n"
        + "class _Key:\n"
        "    def __init__(self):\n"
        "        self.spec_bundle_hash = " + repr(SPEC_HASH) + "\n"
        "        self.spec_bundle_parts = " + repr(SPEC_PARTS) + "\n"
        "        self.gate_versions = " + repr(GATE_VERSIONS) + "\n"
        "        self.assets = " + repr(ASSETS) + "\n"
        "        self.drivers = []\n"
        "def current_sealed_key(component_id, repo_root):\n"
        "    _log('current_sealed_key', component_id=component_id)\n"
        "    return None\n"
        "def current_provenance_key(component_id, repo_root):\n"
        "    _log('current_provenance_key', component_id=component_id)\n"
        "    return _Key()\n"
        "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root, spec_bundle_parts=None):\n"
        "    _log('check_provenance', component_id=component_id)\n"
        "    return CHECK_RESULT\n"
        "def check_sealed_provenance(component_id, repo_root):\n"
        "    _log('check_sealed_provenance', component_id=component_id)\n"
        "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
        "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
        "            'written_at': None}\n",
    )
    _write(
        repo_root,
        "spec-bundle-assembler",
        h
        + "BUNDLE = " + repr(SPEC_BUNDLE) + "\n"
        + "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log('assemble', component_id=component_id, mode=mode)\n"
        "    return BUNDLE\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion', component_id=component_id)\n"
        "    return {'component_id': component_id, 'criterion_id': criterion_id, 'covers': 'R-FOO-001',\n"
        "            'criterion_text': '', 'requirement_text': '', 'interface': '', 'glossary': '',\n"
        "            'dependency_interfaces': {}, 'testing': ''}\n",
    )
    _write(
        repo_root,
        "generation-loop",
        h
        + "LOOP_RESULT = " + repr(LOOP_RESULT) + "\n"
        + "RETRIED_CATEGORIES = ('truncated_response', 'missing_module', 'empty_response',\n"
        "    'agent_budget_exhausted', 'agent_unfinished', 'undecodable_file', 'missing_asset',\n"
        "    'malformed_layout')\n"
        "def run_attempts(component_id, bundle, repo_root, model, *, mode='single', max_attempts=3,\n"
        "                 retry_feedback=None, seed=0, llm_backend=None, allow_unisolated_exec=False,\n"
        "                 on_attempt=None):\n"
        "    target = Path(repo_root) / 'verification' / 'foo' / 'generated-test' / 'test_ac_foo_001.py'\n"
        "    _log('run_attempts', component_id=component_id, exists=os.path.exists(str(target)))\n"
        "    return LOOP_RESULT\n"
        "def make_closures(model, seed, repo_root, llm_backend=None):\n"
        "    _log('make_closures')\n"
        "    def test_author(bundle):\n"
        "        return {'model_call_error': None, 'file': None}\n"
        "    def judge(bundle):\n"
        "        return {'result': 'pass', 'rationale': None}\n"
        "    return (test_author, judge)\n",
    )
    _write(
        repo_root,
        "provenance-tracker",
        h
        + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
        "    _log('write_attempt_record', component_id=component_id)\n"
        "    return {'attempt_id': '2026-01-01T00:00:00Z-a1b2c3', 'component_id': component_id,\n"
        "            'timestamp': '2026-01-01T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
        "            'generation': {}, 'verification': None}\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
        "            'secret_scan': None, 'not_ready_reasons': []}\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n",
    )
    _write(
        repo_root,
        "verifier-orchestrator",
        h
        + "REPORT = " + repr(VERIFICATION_REPORT) + "\n"
        + "GATE_VERSION = 'verifier-orchestrator@4.0.0'\n"
        "DEFAULT_TEST_TIMEOUT = 300.0\n"
        "def verify(component_id, repo_root, judge=None, test_author=None):\n"
        "    _log('verify', component_id=component_id)\n"
        "    return REPORT\n",
    )
    _write(
        repo_root,
        "license-scanner",
        h
        + "RESULT = " + repr(LICENSE_SCAN) + "\n"
        + "def scan(component_id, repo_root):\n"
        "    _log('license_scan', component_id=component_id)\n"
        "    return RESULT\n"
        "def gate_version(repo_root):\n"
        "    _log('license_gate_version')\n"
        "    return RESULT['gate_version']\n",
    )
    _write(
        repo_root,
        "secret-scanner",
        h
        + "RESULT = " + repr(SECRET_SCAN) + "\n"
        + "class AllowlistInvalidError(Exception):\n"
        "    pass\n"
        "def scan(repo_root):\n"
        "    _log('secret_scan')\n"
        "    return RESULT\n"
        "def scan_files(paths, repo_root=None):\n"
        "    _log('secret_scan_files')\n"
        "    return RESULT\n"
        "def gate_version(repo_root):\n"
        "    _log('secret_gate_version')\n"
        "    return RESULT['gate_version']\n"
        "def propose(repo_root):\n"
        "    _log('propose')\n"
        "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n",
    )
    _write(
        repo_root,
        "provenance-writer",
        h
        + "class InvalidSealedInputError(Exception):\n"
        "    pass\n"
        "class MissingInputError(Exception):\n"
        "    pass\n"
        "def write_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_provenance', component_id=component_id)\n"
        "    return None\n"
        "def write_sealed_provenance(component_id, inputs, repo_root):\n"
        "    _log('write_sealed_provenance', component_id=component_id)\n"
        "    return None\n",
    )


def _write_corpus(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n"
    )
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — foo MUST do a thing.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When foo runs\n"
        "Then it works\n"
        "```\n"
    )
    test_dir = repo_root / "verification" / "foo" / "generated-test"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "test_ac_foo_001.py"
    test_file.write_text("def test_placeholder():\n    assert True\n")
    return test_file


def _read_log(log):
    if not log.exists():
        return []
    return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]


def _argv(repo_root, reauthor):
    return [
        "generate",
        "comp-foo",
        "--model=m",
        "--reauthor=" + reauthor,
        "--repo-root=" + str(repo_root),
    ]


def test_reauthor_deletes_test_before_run_attempts_on_miss(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    _write_corpus(repo_root)
    _write_fakes(repo_root, log, MISS)

    component_gate_runner.main(_argv(repo_root, "AC-FOO-001"))

    entries = [e for e in _read_log(log) if e["call"] == "run_attempts"]
    assert len(entries) == 1, _read_log(log)
    assert entries[0]["exists"] is False


def test_reauthor_keeps_test_on_short_circuiting_hit(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    test_file = _write_corpus(repo_root)
    _write_fakes(repo_root, log, HIT)

    component_gate_runner.main(_argv(repo_root, "AC-FOO-001"))

    assert test_file.exists()


def test_reauthor_unknown_criterion_is_usage_error(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "calls.log"
    _write_corpus(repo_root)
    _write_fakes(repo_root, log, MISS)
    capsys.readouterr()

    code = component_gate_runner.main(_argv(repo_root, "AC-FOO-009"))

    err = capsys.readouterr().err
    assert code == 2
    lines = err.splitlines()
    assert lines, "expected stderr output"
    first = lines[0]
    assert first.startswith("usage error: ")
    assert "AC-FOO-009 is not a generated-test criterion of comp-foo" in first
    assert _read_log(log) == []
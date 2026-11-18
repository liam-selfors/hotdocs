# hotdocs-criterion: sha256:5966be4b6643ea3c6b264d27c8309834c326d69d50036863b1e37ed34312f5dd
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "GATE_FAKE_LOG"
SEALED_ENV = "GATE_FAKE_SEALED"
OVERALL_ENV = "GATE_FAKE_OVERALL"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_HELPER = (
    "import json as _json\n"
    "import os as _os\n"
    "\n"
    "def _log(entry):\n"
    "    path = _os.environ['" + LOG_ENV + "']\n"
    "    with open(path, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(_json.dumps(entry, sort_keys=True) + '\\n')\n"
    "\n"
    "def _f(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
)


PROVENANCE_CHECKER_SRC = LOG_HELPER + (
    "class SealedKey:\n"
    "    def __init__(self, owners, source_path, source_hash, verifier_version):\n"
    "        self.owners = owners\n"
    "        self.source_path = source_path\n"
    "        self.source_hash = source_hash\n"
    "        self.verifier_version = verifier_version\n"
    "\n"
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    if _os.environ.get('" + SEALED_ENV + "') == '1':\n"
    "        return SealedKey(['pipeline-team'], 'pipeline/foo/', 'sha256:k', 'verifier-orchestrator@2.0.0')\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey('sha256:abc', {\n"
    "        'compiler': 'criterion-compiler@1.0.0',\n"
    "        'generated_test': 'generated_test@1.0.0',\n"
    "        'verifier': 'verifier-orchestrator@2.0.0',\n"
    "        'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "        'secret_scanner': 'secret_scanner@0.0.0',\n"
    "    })\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log({'call': 'check_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log({'call': 'check_sealed_provenance', 'component_id': component_id})\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_HELPER + (
    "from dataclasses import dataclass, field as _field\n"
    "\n"
    "class _Mapping:\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "@dataclass\n"
    "class SpecBundle(_Mapping):\n"
    "    component_id: str\n"
    "    spec_bundle_hash: str\n"
    "    spec: str\n"
    "    interface: str\n"
    "    constraints: str\n"
    "    dependency_interfaces: dict = _field(default_factory=dict)\n"
    "    dependency_context: dict = _field(default_factory=dict)\n"
    "    dependency_usage: dict = _field(default_factory=dict)\n"
    "    vars: dict = _field(default_factory=dict)\n"
    "    glossary: str = ''\n"
    "    hint_code: object = None\n"
    "\n"
    "@dataclass\n"
    "class CriterionBundle(_Mapping):\n"
    "    component_id: str\n"
    "    criterion_id: str\n"
    "    covers: str\n"
    "    criterion_text: str\n"
    "    requirement_text: str\n"
    "    interface: str\n"
    "    glossary: str\n"
    "    dependency_interfaces: dict = _field(default_factory=dict)\n"
    "\n"
    "def assemble(component_id, repo_root=None, mode='cold'):\n"
    "    _log({'call': 'assemble', 'component_id': component_id})\n"
    "    return SpecBundle(component_id, 'sha256:abc', 'spec', 'iface', 'None.')\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root=None):\n"
    "    _log({'call': 'assemble_criterion', 'component_id': component_id})\n"
    "    return CriterionBundle(component_id, criterion_id, 'R-FOO-001', 'c', 'r', 'i', 'g')\n"
)


GENERATOR_SRC = LOG_HELPER + (
    "from dataclasses import dataclass\n"
    "\n"
    "GATE_VERSION = 'generator@2.0.0'\n"
    "PROMPT_VERSION = 'v10'\n"
    "\n"
    "@dataclass\n"
    "class GenerationResult:\n"
    "    component_id: str\n"
    "    spec_bundle_hash: str\n"
    "    model: str\n"
    "    prompt_version: str\n"
    "    cache_hit: bool\n"
    "    files: dict\n"
    "    model_call_error: object\n"
    "    refused: object\n"
    "    retry_feedback: object\n"
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    cid = _f(bundle, 'component_id')\n"
    "    _log({'call': 'generate', 'component_id': cid})\n"
    "    return GenerationResult(cid, _f(bundle, 'spec_bundle_hash'), model, PROMPT_VERSION, False,\n"
    "                            {'foo.py': 'def foo(x):\\n    return 2 * x\\n'}, None, None, retry_feedback)\n"
)


VERIFIER_SRC = LOG_HELPER + (
    "from dataclasses import dataclass, asdict\n"
    "\n"
    "GATE_VERSION = 'verifier-orchestrator@2.0.0'\n"
    "\n"
    "@dataclass\n"
    "class VerificationReport:\n"
    "    component_id: str\n"
    "    criteria: list\n"
    "    requirement_results: dict\n"
    "    interface_drift: bool\n"
    "    mutation_score: object\n"
    "    mutation_error: object\n"
    "    overall: str\n"
    "    def to_dict(self):\n"
    "        return asdict(self)\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id})\n"
    "    overall = _os.environ.get('" + OVERALL_ENV + "', 'pass')\n"
    "    first = {'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'compiled', 'result': 'pass'}\n"
    "    if overall == 'pass':\n"
    "        second = {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled', 'result': 'pass'}\n"
    "    else:\n"
    "        second = {'id': 'AC-FOO-002', 'covers': 'R-FOO-002', 'kind': 'compiled', 'result': 'fail',\n"
    "                  'failure_detail': {'message': 'foo equals 4 failed', 'expected': 4, 'actual': 3},\n"
    "                  'failure_origin': 'implementation'}\n"
    "    rr = {'R-FOO-001': 'pass', 'R-FOO-002': second['result']}\n"
    "    return VerificationReport(component_id, [first, second], rr, False, None, None, overall)\n"
)


LICENSE_SRC = LOG_HELPER + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan', 'component_id': component_id})\n"
    "    return {'component_id': component_id, 'gate_version': gate_version(repo_root),\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus', 'similarity_score': None,\n"
    "            'block_threshold': None, 'blocked': False, 'matches': [], 'notified': False,\n"
    "            'notification_delivery_error': None, 'cache_hit': False}\n"
)


SECRET_SRC = LOG_HELPER + (
    "from dataclasses import dataclass, asdict, field as _field\n"
    "\n"
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "@dataclass\n"
    "class SecretScanResult:\n"
    "    scope: str\n"
    "    gate_version: str\n"
    "    flagged: bool\n"
    "    matches: list = _field(default_factory=list)\n"
    "    allowed: list = _field(default_factory=list)\n"
    "    unused_allowlist_entries: list = _field(default_factory=list)\n"
    "    notified: bool = False\n"
    "    notification_delivery_error: object = None\n"
    "    cache_hit: bool = False\n"
    "    def to_dict(self):\n"
    "        return asdict(self)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return SecretScanResult('full', gate_version(repo_root), False)\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log({'call': 'secret_scan_files'})\n"
    "    return SecretScanResult('precommit', gate_version(repo_root), False)\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


WRITER_SRC = LOG_HELPER + (
    "from dataclasses import dataclass\n"
    "\n"
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "@dataclass\n"
    "class SealedProvenanceInputs:\n"
    "    component_id: str\n"
    "    owners: list\n"
    "    source_path: str\n"
    "    source_hash: str\n"
    "    verifier_version: str\n"
    "    verification_report: object\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    rep = _f(inputs, 'verification_report')\n"
    "    crit = [dict(c) for c in _f(rep, 'criteria')]\n"
    "    _log({'call': 'write_sealed_provenance', 'arg_component_id': component_id,\n"
    "          'component_id': _f(inputs, 'component_id'),\n"
    "          'owners': list(_f(inputs, 'owners')),\n"
    "          'source_path': _f(inputs, 'source_path'),\n"
    "          'source_hash': _f(inputs, 'source_hash'),\n"
    "          'verifier_version': _f(inputs, 'verifier_version'),\n"
    "          'report_component_id': _f(rep, 'component_id'),\n"
    "          'report_overall': _f(rep, 'overall'),\n"
    "          'report_criteria': crit})\n"
    "    return None\n"
)


TRACKER_SRC = LOG_HELPER + (
    "from pathlib import Path as _Path\n"
    "import dataclasses as _dc\n"
    "\n"
    "def _plain(v):\n"
    "    if v is None:\n"
    "        return None\n"
    "    if hasattr(v, 'to_dict') and callable(v.to_dict):\n"
    "        return v.to_dict()\n"
    "    if _dc.is_dataclass(v):\n"
    "        return {f.name: getattr(v, f.name) for f in _dc.fields(v)}\n"
    "    return dict(v)\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
    "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
    "    d = _Path(repo_root) / '.hotdocs' / 'attempts' / slug\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    n = len(list(d.iterdir()))\n"
    "    attempt_id = '2026-11-17T00:00:0' + str(n) + 'Z-a1b2c3'\n"
    "    record = {'attempt_id': attempt_id, 'component_id': component_id,\n"
    "              'timestamp': '2026-11-17T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "              'generation': _plain(generation_result), 'verification': _plain(verification_report)}\n"
    "    (d / (attempt_id + '.json')).write_text(_json.dumps(record, default=str), encoding='utf-8')\n"
    "    return record\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


TEST_AUTHOR_SRC = LOG_HELPER + (
    "GATE_VERSION = 'generated_test@1.1.0'\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    _log({'call': 'author_test'})\n"
    "    return {'component_id': _f(bundle, 'component_id'), 'criterion_id': _f(bundle, 'criterion_id'),\n"
    "            'model': model, 'seed': seed, 'prompt_version': 'v1', 'cache_hit': False,\n"
    "            'file': None, 'model_call_error': {'category': 'network', 'message': 'fake'}}\n"
)


LLM_SRC = LOG_HELPER + (
    "DEFAULT_TIMEOUT_SECONDS = 600\n"
    "\n"
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    _log({'call': 'complete'})\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
)


FAKES = {
    ("provenance-checker", "provenance_checker"): PROVENANCE_CHECKER_SRC,
    ("spec-bundle-assembler", "spec_bundle_assembler"): SPEC_BUNDLE_ASSEMBLER_SRC,
    ("generator", "generator"): GENERATOR_SRC,
    ("verifier-orchestrator", "verifier_orchestrator"): VERIFIER_SRC,
    ("license-scanner", "license_scanner"): LICENSE_SRC,
    ("secret-scanner", "secret_scanner"): SECRET_SRC,
    ("provenance-writer", "provenance_writer"): WRITER_SRC,
    ("provenance-tracker", "provenance_tracker"): TRACKER_SRC,
    ("test-author", "test_author"): TEST_AUTHOR_SRC,
    ("llm-endpoint", "llm_endpoint"): LLM_SRC,
}


def _setup(tmp_path, monkeypatch, sealed, overall):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    for (slug, module_name), src in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (module_name + ".py")).write_text(src, encoding="utf-8")
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.setenv(SEALED_ENV, "1" if sealed else "0")
    monkeypatch.setenv(OVERALL_ENV, overall)
    # No component.md for comp-foo is created on purpose.
    assert not (repo_root / "specs" / "components" / "foo" / "component.md").exists()
    return repo_root, log_path


def _read_log(log_path):
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def _names(entries):
    return [e["call"] for e in entries]


NEVER_SEALED = [
    "check_provenance",
    "current_provenance_key",
    "assemble",
    "generate",
    "write_attempt_record",
    "write_provenance",
]


def _assert_sealed_calls(entries, expected_overall, expected_criteria_results):
    names = _names(entries)
    for n in NEVER_SEALED:
        assert n not in names, (n, names)
    assert names.count("current_sealed_key") == 1, names
    assert names.count("verify") == 1, names
    assert names.count("license_scan") == 1, names
    assert names.count("secret_scan") == 1, names
    assert names.count("write_sealed_provenance") == 1, names

    i_verify = names.index("verify")
    i_lic = names.index("license_scan")
    i_sec = names.index("secret_scan")
    i_write = names.index("write_sealed_provenance")
    assert names.index("current_sealed_key") < i_verify
    assert i_write > i_verify
    assert i_write > i_lic
    assert i_write > i_sec

    w = entries[i_write]
    assert w["arg_component_id"] == "comp-foo"
    assert w["component_id"] == "comp-foo"
    assert w["owners"] == ["pipeline-team"]
    assert w["source_path"] == "pipeline/foo/"
    assert w["source_hash"] == "sha256:k"
    assert w["verifier_version"] == "verifier-orchestrator@2.0.0"
    assert w["report_component_id"] == "comp-foo"
    assert w["report_overall"] == expected_overall
    assert len(w["report_criteria"]) == 2
    assert [c["id"] for c in w["report_criteria"]] == ["AC-FOO-001", "AC-FOO-002"]
    assert [c["result"] for c in w["report_criteria"]] == expected_criteria_results


def test_sealed_component_pass(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, sealed=True, overall="pass")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = _read_log(log_path)
    _assert_sealed_calls(entries, "pass", ["pass", "pass"])

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is False
    assert field(result, "component_id") == "comp-foo"

    # No attempt record and no .provenance.json for a sealed component.
    assert not (repo_root / ".hotdocs" / "attempts" / "foo").exists()
    assert not (repo_root / "gen" / "foo" / ".provenance.json").exists()


def test_sealed_component_fail_still_writes_sealed_provenance(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, sealed=True, overall="fail")

    result = component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = _read_log(log_path)
    _assert_sealed_calls(entries, "fail", ["pass", "fail"])

    assert field(result, "provenance_hit") is False
    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "verification_failed"


def test_non_sealed_component_never_writes_sealed_provenance(tmp_path, monkeypatch):
    repo_root, log_path = _setup(tmp_path, monkeypatch, sealed=False, overall="pass")

    component_gate_runner.run_component_gates("comp-foo", repo_root, "m")

    entries = _read_log(log_path)
    names = _names(entries)
    assert "write_sealed_provenance" not in names, names
    assert names[0] == "current_sealed_key", names
    for n in [
        "current_provenance_key",
        "check_provenance",
        "assemble",
        "generate",
        "verify",
        "license_scan",
        "secret_scan",
        "write_attempt_record",
        "write_provenance",
    ]:
        assert n in names, (n, names)
    assert names.index("current_provenance_key") < names.index("check_provenance")
    assert names.index("check_provenance") < names.index("assemble")
    assert names.index("assemble") < names.index("generate")
    assert names.index("generate") < names.index("verify")
    assert names.index("write_attempt_record") < names.index("write_provenance")
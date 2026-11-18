# hotdocs-criterion: sha256:84fbe24d0ccc4528d31f01b24ff25295229fe850c3aa48c12e297d7dbdb6be31
import json
from pathlib import Path

import component_gate_runner


SPEC_BUNDLE_HASH = "sha256:k"
COMPONENT_ID = "comp-foo"
MODEL = "claude-sonnet-5"

GEN_FILES = {"foo.py": "def foo(x):\n    return 2 * x\n"}
GEN_ERROR = {"category": "network", "message": "connection refused"}

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@3.1.0+detect-secrets.1.5.0",
}

FAIL_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {
            "id": "AC-FOO-001",
            "covers": "R-FOO-001",
            "kind": "generated-test",
            "result": "fail",
            "failure_detail": {"message": "foo(2) returned 5", "expected": 4, "actual": 5},
            "failure_origin": "implementation",
        }
    ],
    "requirement_results": {"R-FOO-001": "fail"},
    "interface_drift": False,
    "mutation_score": None,
    "mutation_error": None,
    "overall": "fail",
}

PASS_REPORT = {
    "component_id": "comp-foo",
    "criteria": [
        {
            "id": "AC-FOO-001",
            "covers": "R-FOO-001",
            "kind": "generated-test",
            "result": "pass",
        }
    ],
    "requirement_results": {"R-FOO-001": "pass"},
    "interface_drift": False,
    "mutation_score": 0.9,
    "mutation_error": None,
    "overall": "pass",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON = (
    "import copy\n"
    "import dataclasses\n"
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def _plain(v):\n"
    "    if v is None or isinstance(v, (bool, int, float, str)):\n"
    "        return v\n"
    "    if isinstance(v, dict):\n"
    "        return {str(k): _plain(x) for k, x in v.items()}\n"
    "    if isinstance(v, (list, tuple)):\n"
    "        return [_plain(x) for x in v]\n"
    "    if isinstance(v, Path):\n"
    "        return str(v)\n"
    "    td = getattr(v, 'to_dict', None)\n"
    "    if callable(td):\n"
    "        return _plain(td())\n"
    "    if dataclasses.is_dataclass(v) and not isinstance(v, type):\n"
    "        return {f.name: _plain(getattr(v, f.name)) for f in dataclasses.fields(v)}\n"
    "    return repr(v)\n"
    "\n"
    "\n"
    "def _log(name, **extra):\n"
    "    rec = {'call': name}\n"
    "    rec.update(extra)\n"
    "    with open(os.environ['GATE_TEST_LOG'], 'a') as fh:\n"
    "        fh.write(json.dumps(rec) + '\\n')\n"
    "\n"
    "\n"
    "def _slug(component_id):\n"
    "    return component_id[5:] if component_id.startswith('comp-') else component_id\n"
    "\n"
    "\n"
)


PROVENANCE_CHECKER = (
    COMMON
    + "GATE_VERSIONS = " + repr(GATE_VERSIONS) + "\n"
    + "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
    + "\n"
    "\n"
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key', component_id=component_id)\n"
    "    return None\n"
    "\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key', component_id=component_id)\n"
    "    return ProvenanceKey(SPEC_BUNDLE_HASH, dict(GATE_VERSIONS))\n"
    "\n"
    "\n"
    "def check_provenance(component_id, spec_bundle_hash, gate_versions, repo_root):\n"
    "    _log('check_provenance', component_id=component_id, spec_bundle_hash=spec_bundle_hash)\n"
    "    return {'hit': False, 'verification_report': None, 'license_scan': None, 'secret_scan': None}\n"
    "\n"
    "\n"
    "def check_sealed_provenance(component_id, repo_root):\n"
    "    _log('check_sealed_provenance', component_id=component_id)\n"
    "    return {'hit': False, 'sealed': False, 'reason': 'not_sealed', 'verification_report': None,\n"
    "            'license_scan': None, 'secret_scan': None, 'owners': None, 'source_hash': None,\n"
    "            'written_at': None}\n"
)


SPEC_BUNDLE_ASSEMBLER = (
    COMMON
    + "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
    + "\n"
    "\n"
    "class _Mapping:\n"
    "    def __getitem__(self, key):\n"
    "        if key not in [f.name for f in dataclasses.fields(self)]:\n"
    "            raise KeyError(key)\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        try:\n"
    "            return self[key]\n"
    "        except KeyError:\n"
    "            return default\n"
    "\n"
    "    def keys(self):\n"
    "        return [f.name for f in dataclasses.fields(self)]\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class SpecBundle(_Mapping):\n"
    "    component_id: str\n"
    "    spec_bundle_hash: str\n"
    "    spec: str\n"
    "    interface: str\n"
    "    constraints: str\n"
    "    dependency_interfaces: dict = dataclasses.field(default_factory=dict)\n"
    "    dependency_context: dict = dataclasses.field(default_factory=dict)\n"
    "    dependency_usage: dict = dataclasses.field(default_factory=dict)\n"
    "    vars: dict = dataclasses.field(default_factory=dict)\n"
    "    glossary: str = ''\n"
    "    hint_code: object = None\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CriterionBundle(_Mapping):\n"
    "    component_id: str\n"
    "    criterion_id: str\n"
    "    covers: str\n"
    "    criterion_text: str\n"
    "    requirement_text: str\n"
    "    interface: str\n"
    "    glossary: str\n"
    "    dependency_interfaces: dict = dataclasses.field(default_factory=dict)\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log('assemble', component_id=component_id, mode=mode)\n"
    "    return SpecBundle(\n"
    "        component_id=component_id,\n"
    "        spec_bundle_hash=SPEC_BUNDLE_HASH,\n"
    "        spec='Foo doubles a number.',\n"
    "        interface='foo(x: int) -> int',\n"
    "        constraints='None.',\n"
    "        glossary='- **Foo** - a test term.',\n"
    "    )\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log('assemble_criterion', component_id=component_id, criterion_id=criterion_id)\n"
    "    return CriterionBundle(\n"
    "        component_id=component_id,\n"
    "        criterion_id=criterion_id,\n"
    "        covers='R-FOO-001',\n"
    "        criterion_text='Given x = 2 When foo(x) is called Then it returns 4',\n"
    "        requirement_text='foo(x) MUST return 2 * x.',\n"
    "        interface='foo(x: int) -> int',\n"
    "        glossary='- **Foo** - a test term.',\n"
    "    )\n"
)


GENERATOR = (
    COMMON
    + "GEN_FILES = " + repr(GEN_FILES) + "\n"
    + "GEN_ERROR = " + repr(GEN_ERROR) + "\n"
    + "SPEC_BUNDLE_HASH = " + repr(SPEC_BUNDLE_HASH) + "\n"
    + "GATE_VERSION = 'generator@2.0.0'\n"
    "PROMPT_VERSION = 'v10'\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
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
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    _log('generate', model=model)\n"
    "    bundle_hash = bundle['spec_bundle_hash'] if isinstance(bundle, dict) else getattr(bundle, 'spec_bundle_hash', SPEC_BUNDLE_HASH)\n"
    "    if os.environ.get('GATE_TEST_GEN_MODE') == 'error':\n"
    "        return GenerationResult(\n"
    "            component_id=bundle['component_id'],\n"
    "            spec_bundle_hash=bundle_hash,\n"
    "            model=model,\n"
    "            prompt_version=PROMPT_VERSION,\n"
    "            cache_hit=False,\n"
    "            files={},\n"
    "            model_call_error=dict(GEN_ERROR),\n"
    "            refused=None,\n"
    "            retry_feedback=retry_feedback,\n"
    "        )\n"
    "    return GenerationResult(\n"
    "        component_id=bundle['component_id'],\n"
    "        spec_bundle_hash=bundle_hash,\n"
    "        model=model,\n"
    "        prompt_version=PROMPT_VERSION,\n"
    "        cache_hit=False,\n"
    "        files=dict(GEN_FILES),\n"
    "        model_call_error=None,\n"
    "        refused=None,\n"
    "        retry_feedback=retry_feedback,\n"
    "    )\n"
)


VERIFIER_ORCHESTRATOR = (
    COMMON
    + "FAIL_REPORT = " + repr(FAIL_REPORT) + "\n"
    + "PASS_REPORT = " + repr(PASS_REPORT) + "\n"
    + "GATE_VERSION = 'verifier-orchestrator@2.2.0'\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class VerificationReport:\n"
    "    component_id: str\n"
    "    criteria: list\n"
    "    requirement_results: dict\n"
    "    interface_drift: bool\n"
    "    mutation_score: object\n"
    "    mutation_error: object\n"
    "    overall: str\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {f.name: copy.deepcopy(getattr(self, f.name)) for f in dataclasses.fields(self)}\n"
    "\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify', component_id=component_id)\n"
    "    if os.environ.get('GATE_TEST_VERIFY') == 'pass':\n"
    "        return VerificationReport(**copy.deepcopy(PASS_REPORT))\n"
    "    return VerificationReport(**copy.deepcopy(FAIL_REPORT))\n"
)


LICENSE_SCANNER = (
    COMMON
    + "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan', component_id=component_id)\n"
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


SECRET_SCANNER = (
    COMMON
    + "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class SecretScanResult:\n"
    "    scope: str\n"
    "    gate_version: str\n"
    "    flagged: bool\n"
    "    matches: list\n"
    "    allowed: list\n"
    "    unused_allowlist_entries: list\n"
    "    notified: bool\n"
    "    notification_delivery_error: object\n"
    "    cache_hit: bool\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {f.name: copy.deepcopy(getattr(self, f.name)) for f in dataclasses.fields(self)}\n"
    "\n"
    "\n"
    "def _clean(scope):\n"
    "    return SecretScanResult(\n"
    "        scope=scope,\n"
    "        gate_version='secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
    "        flagged=False,\n"
    "        matches=[],\n"
    "        allowed=[],\n"
    "        unused_allowlist_entries=[],\n"
    "        notified=False,\n"
    "        notification_delivery_error=None,\n"
    "        cache_hit=False,\n"
    "    )\n"
    "\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return _clean('full')\n"
    "\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log('secret_scan_files')\n"
    "    return _clean('precommit')\n"
    "\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_TRACKER = (
    COMMON
    + "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    generation = _plain(generation_result)\n"
    "    verification = _plain(verification_report)\n"
    "    _log('write_attempt_record', component_id=component_id, generation=generation,\n"
    "         verification=verification, verification_is_none=verification_report is None,\n"
    "         spec_bundle_hash=spec_bundle_hash)\n"
    "    if os.environ.get('GATE_TEST_TRACKER_RAISE') == '1':\n"
    "        raise RuntimeError('attempt record store unavailable')\n"
    "    attempt_id = '2026-11-17T00:00:00Z-a1b2c3'\n"
    "    record = {\n"
    "        'attempt_id': attempt_id,\n"
    "        'component_id': component_id,\n"
    "        'timestamp': '2026-11-17T00:00:00Z',\n"
    "        'spec_bundle_hash': spec_bundle_hash,\n"
    "        'generation': generation,\n"
    "        'verification': verification,\n"
    "    }\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / _slug(component_id)\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    (d / (attempt_id.replace(':', '-') + '.json')).write_text(json.dumps(record))\n"
    "    return record\n"
    "\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'not_ready_reasons': []}\n"
    "\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)


PROVENANCE_WRITER = (
    COMMON
    + "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_provenance', component_id=component_id)\n"
    "    return None\n"
    "\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log('write_sealed_provenance', component_id=component_id)\n"
    "    return None\n"
)


TEST_AUTHOR = (
    COMMON
    + "GATE_VERSION = 'generated_test@1.1.0'\n"
    "\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    _log('author_test', model=model)\n"
    "    cid = bundle['criterion_id']\n"
    "    return {\n"
    "        'component_id': bundle['component_id'],\n"
    "        'criterion_id': cid,\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'file': {'path': 'verification/foo/generated-test/test_ac_foo_001.py',\n"
    "                 'content': 'def test_x():\\n    assert True\\n'},\n"
    "        'model_call_error': None,\n"
    "    }\n"
)


LLM_ENDPOINT = (
    COMMON
    + "DEFAULT_TIMEOUT_SECONDS = 600\n"
    "\n"
    "\n"
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    _log('complete', model=model)\n"
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
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)


def build_repo(tmp_path, monkeypatch, gen_mode="files", verify_mode="fail", tracker_raise=False):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "specs").mkdir()
    (repo_root / "specs" / "glossary.md").write_text("# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir()
    (comp / "interface").mkdir()
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "interface" / "library.md").write_text("# Library\n\n```\nfoo(x: int) -> int\n```\n")
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")

    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source)

    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    monkeypatch.setenv("GATE_TEST_LOG", str(log_path))
    monkeypatch.setenv("GATE_TEST_GEN_MODE", gen_mode)
    monkeypatch.setenv("GATE_TEST_VERIFY", verify_mode)
    if tracker_raise:
        monkeypatch.setenv("GATE_TEST_TRACKER_RAISE", "1")
    else:
        monkeypatch.delenv("GATE_TEST_TRACKER_RAISE", raising=False)
    return repo_root, log_path


def read_log(log_path):
    lines = [l for l in Path(log_path).read_text().splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def roundtrip(value):
    return json.loads(json.dumps(value))


def test_attempt_record_written_once_after_scans_with_full_results(tmp_path, monkeypatch):
    repo_root, log_path = build_repo(tmp_path, monkeypatch, gen_mode="files", verify_mode="fail")

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    records = read_log(log_path)
    calls = [r["call"] for r in records]

    assert calls.count("write_attempt_record") == 1, calls
    assert "license_scan" in calls, calls
    assert "secret_scan" in calls, calls
    assert "generate" in calls, calls
    assert "verify" in calls, calls

    idx = calls.index("write_attempt_record")
    assert idx > calls.index("license_scan"), calls
    assert idx > calls.index("secret_scan"), calls
    assert idx > calls.index("generate"), calls
    assert idx > calls.index("verify"), calls

    rec = records[idx]
    assert rec["component_id"] == "comp-foo"
    assert rec["spec_bundle_hash"] == "sha256:k"

    expected_generation = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:k",
        "model": MODEL,
        "prompt_version": "v10",
        "cache_hit": False,
        "files": GEN_FILES,
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    assert rec["generation"] == roundtrip(expected_generation)

    assert rec["verification_is_none"] is False
    assert rec["verification"] == roundtrip(FAIL_REPORT)

    assert field(result, "blocked") is True


def test_attempt_record_gets_none_report_on_model_call_error(tmp_path, monkeypatch):
    repo_root, log_path = build_repo(tmp_path, monkeypatch, gen_mode="error", verify_mode="fail")

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    records = read_log(log_path)
    calls = [r["call"] for r in records]

    assert calls.count("write_attempt_record") == 1, calls
    rec = records[calls.index("write_attempt_record")]
    assert rec["verification_is_none"] is True
    assert rec["verification"] is None
    assert rec["generation"]["model_call_error"] == GEN_ERROR
    assert rec["spec_bundle_hash"] == "sha256:k"

    assert field(result, "blocked") is True
    assert field(result, "block_reason") == "model_call_error"


def test_attempt_record_exception_does_not_change_result(tmp_path, monkeypatch):
    repo_root, log_path = build_repo(
        tmp_path, monkeypatch, gen_mode="files", verify_mode="pass", tracker_raise=True
    )

    result = component_gate_runner.run_component_gates(COMPONENT_ID, repo_root, MODEL)

    records = read_log(log_path)
    calls = [r["call"] for r in records]
    assert "write_attempt_record" in calls, calls

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "component_id") == "comp-foo"
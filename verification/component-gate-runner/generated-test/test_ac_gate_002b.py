# hotdocs-criterion: sha256:117acfe22f6b5d98f3d65e80e6128b2c13ebbc102a3fb53cf86fb19abaa09762
import json
import os
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_AC_GATE_002B_LOG"

BUNDLE_HASH = "sha256:" + "ab" * 32
SPEC_MARKER = "SPEC-MARKER-AC-GATE-002b"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


LOG_PRELUDE = (
    "import json\n"
    "import os\n"
    "\n"
    "def _log(entry):\n"
    "    with open(os.environ[" + repr(LOG_ENV) + "], 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "def _field(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
)


PROVENANCE_CHECKER_SRC = LOG_PRELUDE + (
    "class ProvenanceKey:\n"
    "    def __init__(self, spec_bundle_hash, gate_versions):\n"
    "        self.spec_bundle_hash = spec_bundle_hash\n"
    "        self.gate_versions = gate_versions\n"
    "\n"
    "def current_sealed_key(component_id, repo_root):\n"
    "    _log({'call': 'current_sealed_key', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log({'call': 'current_provenance_key', 'component_id': component_id})\n"
    "    return ProvenanceKey(" + repr(BUNDLE_HASH) + ", {\n"
    "        'compiler': 'criterion-compiler@1.0.0',\n"
    "        'generated_test': 'generated_test@1.1.0',\n"
    "        'verifier': 'verifier-orchestrator@2.2.0',\n"
    "        'license_scanner': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "        'secret_scanner': 'secret_scanner@3.1.0+detect-secrets.1.5.0',\n"
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


SPEC_BUNDLE_ASSEMBLER_SRC = LOG_PRELUDE + (
    "import dataclasses\n"
    "from dataclasses import dataclass\n"
    "\n"
    "@dataclass\n"
    "class SpecBundle:\n"
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
    "    def _names(self):\n"
    "        return [f.name for f in dataclasses.fields(self)]\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        if key in self._names():\n"
    "            return getattr(self, key)\n"
    "        raise KeyError(key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        if key in self._names():\n"
    "            return getattr(self, key)\n"
    "        return default\n"
    "\n"
    "    def keys(self):\n"
    "        return list(self._names())\n"
    "\n"
    "    def __contains__(self, key):\n"
    "        return key in self._names()\n"
    "\n"
    "@dataclass\n"
    "class CriterionBundle:\n"
    "    component_id: str\n"
    "    criterion_id: str\n"
    "    covers: str\n"
    "    criterion_text: str\n"
    "    requirement_text: str\n"
    "    interface: str\n"
    "    glossary: str\n"
    "    dependency_interfaces: dict = dataclasses.field(default_factory=dict)\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'call': 'assemble', 'component_id': component_id, 'mode': mode})\n"
    "    return SpecBundle(\n"
    "        component_id=component_id,\n"
    "        spec_bundle_hash=" + repr(BUNDLE_HASH) + ",\n"
    "        spec=" + repr(SPEC_MARKER) + ",\n"
    "        interface='# Library',\n"
    "        constraints='None.',\n"
    "        glossary='- **Foo** - a test term.',\n"
    "        hint_code=None,\n"
    "    )\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    _log({'call': 'assemble_criterion', 'component_id': component_id})\n"
    "    return CriterionBundle(component_id, criterion_id, 'R-FOO-001', 'Given', 'R', '# Library', '')\n"
)


GENERATOR_SRC = LOG_PRELUDE + (
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
    "    def to_dict(self):\n"
    "        return dict(self.__dict__)\n"
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    _log({'call': 'generate',\n"
    "          'bundle_component_id': _field(bundle, 'component_id'),\n"
    "          'bundle_spec_bundle_hash': _field(bundle, 'spec_bundle_hash'),\n"
    "          'bundle_spec': _field(bundle, 'spec'),\n"
    "          'model': model,\n"
    "          'retry_feedback': list(retry_feedback) if retry_feedback is not None else None})\n"
    "    return GenerationResult(\n"
    "        component_id=_field(bundle, 'component_id'),\n"
    "        spec_bundle_hash=_field(bundle, 'spec_bundle_hash'),\n"
    "        model=model,\n"
    "        prompt_version=PROMPT_VERSION,\n"
    "        cache_hit=False,\n"
    "        files={'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
    "        model_call_error=None,\n"
    "        refused=None,\n"
    "        retry_feedback=retry_feedback,\n"
    "    )\n"
)


VERIFIER_SRC = LOG_PRELUDE + (
    "from dataclasses import dataclass\n"
    "\n"
    "GATE_VERSION = 'verifier-orchestrator@2.2.0'\n"
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
    "\n"
    "    def to_dict(self):\n"
    "        return {\n"
    "            'component_id': self.component_id,\n"
    "            'criteria': [dict(c) for c in self.criteria],\n"
    "            'requirement_results': dict(self.requirement_results),\n"
    "            'interface_drift': self.interface_drift,\n"
    "            'mutation_score': self.mutation_score,\n"
    "            'mutation_error': self.mutation_error,\n"
    "            'overall': self.overall,\n"
    "        }\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log({'call': 'verify', 'component_id': component_id,\n"
    "          'judge_callable': callable(judge), 'test_author_callable': callable(test_author)})\n"
    "    return VerificationReport(\n"
    "        component_id=component_id,\n"
    "        criteria=[{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'generated-test', 'result': 'pass'}],\n"
    "        requirement_results={'R-FOO-001': 'pass'},\n"
    "        interface_drift=False,\n"
    "        mutation_score=1.0,\n"
    "        mutation_error=None,\n"
    "        overall='pass',\n"
    "    )\n"
)


LICENSE_SCANNER_SRC = LOG_PRELUDE + (
    "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log({'call': 'license_scan', 'component_id': component_id})\n"
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


SECRET_SCANNER_SRC = LOG_PRELUDE + (
    "class AllowlistInvalidError(Exception):\n"
    "    pass\n"
    "\n"
    "class SecretScanResult:\n"
    "    def __init__(self, scope):\n"
    "        self.scope = scope\n"
    "        self.gate_version = 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "        self.flagged = False\n"
    "        self.matches = []\n"
    "        self.allowed = []\n"
    "        self.unused_allowlist_entries = []\n"
    "        self.notified = False\n"
    "        self.notification_delivery_error = None\n"
    "        self.cache_hit = False\n"
    "\n"
    "    def to_dict(self):\n"
    "        return dict(self.__dict__)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@3.1.0+detect-secrets.1.5.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log({'call': 'secret_scan'})\n"
    "    return SecretScanResult('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    _log({'call': 'secret_scan_files'})\n"
    "    return SecretScanResult('precommit')\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)


PROVENANCE_TRACKER_SRC = LOG_PRELUDE + (
    "from pathlib import Path\n"
    "\n"
    "def _plain(value):\n"
    "    if value is None:\n"
    "        return None\n"
    "    if isinstance(value, dict):\n"
    "        return dict(value)\n"
    "    if hasattr(value, 'to_dict'):\n"
    "        return value.to_dict()\n"
    "    return dict(vars(value))\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report, spec_bundle_hash, repo_root):\n"
    "    _log({'call': 'write_attempt_record', 'component_id': component_id})\n"
    "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / slug\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    n = len(list(d.iterdir()))\n"
    "    attempt_id = '2026-11-17T00:00:00Z-' + str(n).zfill(6)\n"
    "    record = {\n"
    "        'attempt_id': attempt_id,\n"
    "        'component_id': component_id,\n"
    "        'timestamp': '2026-11-17T00:00:00Z',\n"
    "        'spec_bundle_hash': spec_bundle_hash,\n"
    "        'generation': _plain(generation_result),\n"
    "        'verification': _plain(verification_report),\n"
    "    }\n"
    "    (d / (attempt_id.replace(':', '-') + '.json')).write_text(json.dumps(record, default=str), encoding='utf-8')\n"
    "    return record\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {}, 'not_ready_reasons': []}\n"
)


PROVENANCE_WRITER_SRC = LOG_PRELUDE + (
    "class InvalidSealedInputError(Exception):\n"
    "    pass\n"
    "\n"
    "class MissingInputError(Exception):\n"
    "    pass\n"
    "\n"
    "def write_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_provenance', 'component_id': component_id})\n"
    "    return None\n"
    "\n"
    "def write_sealed_provenance(component_id, inputs, repo_root):\n"
    "    _log({'call': 'write_sealed_provenance', 'component_id': component_id})\n"
    "    return None\n"
)


TEST_AUTHOR_SRC = LOG_PRELUDE + (
    "GATE_VERSION = 'generated_test@1.1.0'\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    _log({'call': 'author_test', 'model': model})\n"
    "    cid = _field(bundle, 'criterion_id')\n"
    "    return {\n"
    "        'component_id': _field(bundle, 'component_id'),\n"
    "        'criterion_id': cid,\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'file': {'path': 'verification/foo/generated-test/test_x.py', 'content': 'def test_x():\\n    assert True\\n'},\n"
    "        'model_call_error': None,\n"
    "    }\n"
)


LLM_ENDPOINT_SRC = LOG_PRELUDE + (
    "DEFAULT_TIMEOUT_SECONDS = 600\n"
    "PROVIDERS = {}\n"
    "\n"
    "class ModelResolutionError(Exception):\n"
    "    pass\n"
    "\n"
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    _log({'call': 'complete', 'model': model})\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    "\n"
    "def parse_model(model):\n"
    "    return (None, model)\n"
)


FAKES = {
    "provenance-checker": PROVENANCE_CHECKER_SRC,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER_SRC,
    "generator": GENERATOR_SRC,
    "verifier-orchestrator": VERIFIER_SRC,
    "license-scanner": LICENSE_SCANNER_SRC,
    "secret-scanner": SECRET_SCANNER_SRC,
    "provenance-tracker": PROVENANCE_TRACKER_SRC,
    "provenance-writer": PROVENANCE_WRITER_SRC,
    "test-author": TEST_AUTHOR_SRC,
    "llm-endpoint": LLM_ENDPOINT_SRC,
}


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write(
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
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
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
    write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def install_fakes(repo_root):
    for slug, src in FAKES.items():
        module_name = slug.replace("-", "_")
        write(repo_root / "gen" / slug / (module_name + ".py"), src)


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_miss_calls_assemble_generate_verify_in_order(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    install_fakes(repo_root)

    log_path = tmp_path / "calls.log"
    monkeypatch.setenv(LOG_ENV, str(log_path))

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "m", retry_feedback=["R-FOO-002"]
    )
    assert result is not None
    assert field(result, "provenance_hit") is False

    entries = read_log(log_path)
    tracked = [e for e in entries if e["call"] in ("assemble", "generate", "verify")]
    names = [e["call"] for e in tracked]
    assert names == ["assemble", "generate", "verify"], names

    assemble_entry = tracked[0]
    assert assemble_entry["component_id"] == "comp-foo"
    assert assemble_entry["mode"] == "cold"

    generate_entry = tracked[1]
    assert generate_entry["bundle_component_id"] == "comp-foo"
    assert generate_entry["bundle_spec_bundle_hash"] == BUNDLE_HASH
    assert generate_entry["bundle_spec"] == SPEC_MARKER
    assert generate_entry["model"] == "m"
    assert generate_entry["retry_feedback"] == ["R-FOO-002"]

    verify_entry = tracked[2]
    assert verify_entry["component_id"] == "comp-foo"
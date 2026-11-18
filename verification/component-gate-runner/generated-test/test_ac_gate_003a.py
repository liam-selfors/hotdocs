# hotdocs-criterion: sha256:ecc49f29ba60b9e7e98a1eec1d069ac8e4d30c7f0f0c2bf9a6f1ea08397b57c7
import json
from pathlib import Path

import component_gate_runner


LOG_ENV = "HOTDOCS_GATE_TEST_LOG"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMMON_HEADER = (
    "import json\n"
    "import os\n"
    "from pathlib import Path\n"
    "\n"
    "def _log(line):\n"
    "    path = os.environ.get(" + repr(LOG_ENV) + ")\n"
    "    if path:\n"
    "        with open(path, 'a', encoding='utf-8') as fh:\n"
    "            fh.write(line + '\\n')\n"
    "\n"
    "class _Obj:\n"
    "    def __init__(self, **kw):\n"
    "        for k, v in kw.items():\n"
    "            setattr(self, k, v)\n"
    "        self._keys = list(kw.keys())\n"
    "    def __getitem__(self, k):\n"
    "        if k not in self._keys:\n"
    "            raise KeyError(k)\n"
    "        return getattr(self, k)\n"
    "    def get(self, k, default=None):\n"
    "        return getattr(self, k) if k in self._keys else default\n"
    "    def keys(self):\n"
    "        return list(self._keys)\n"
    "    def __contains__(self, k):\n"
    "        return k in self._keys\n"
    "    def to_dict(self):\n"
    "        return {k: getattr(self, k) for k in self._keys}\n"
    "\n"
)

HASH = "sha256:" + "0" * 64

GATE_VERSIONS = {
    "compiler": "criterion-compiler@1.0.0",
    "generated_test": "generated_test@1.1.0",
    "verifier": "verifier-orchestrator@2.2.0",
    "license_scanner": "license_scanner@4.0.0-no-reference-corpus",
    "secret_scanner": "secret_scanner@0.0.0",
}

PROVENANCE_CHECKER = (
    COMMON_HEADER
    + "def current_sealed_key(component_id, repo_root):\n"
    "    _log('current_sealed_key')\n"
    "    return None\n"
    "\n"
    "def current_provenance_key(component_id, repo_root):\n"
    "    _log('current_provenance_key')\n"
    "    return _Obj(spec_bundle_hash=" + repr(HASH) + ", gate_versions=" + repr(GATE_VERSIONS) + ")\n"
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

SPEC_BUNDLE_ASSEMBLER = (
    COMMON_HEADER
    + "def assemble(component_id, repo_root=None, mode='cold'):\n"
    "    _log('assemble ' + repr(mode))\n"
    "    return _Obj(component_id=component_id, spec_bundle_hash=" + repr(HASH) + ",\n"
    "                spec='Foo doubles a number.', interface='foo(x: int) -> int',\n"
    "                constraints='None.', dependency_interfaces={}, dependency_context={},\n"
    "                dependency_usage={}, vars={}, glossary='- **Foo** - a test term.',\n"
    "                hint_code=None)\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root=None):\n"
    "    _log('assemble_criterion')\n"
    "    return _Obj(component_id=component_id, criterion_id=criterion_id, covers='R-FOO-001',\n"
    "                criterion_text='', requirement_text='', interface='', glossary='',\n"
    "                dependency_interfaces={})\n"
)

GENERATOR = (
    COMMON_HEADER
    + "GATE_VERSION = 'generator@2.0.0'\n"
    "PROMPT_VERSION = 'v10'\n"
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    _log('generate ' + json.dumps({'model': model, 'retry_feedback': retry_feedback}))\n"
    "    cid = bundle['component_id'] if isinstance(bundle, dict) else getattr(bundle, 'component_id')\n"
    "    sbh = bundle['spec_bundle_hash'] if isinstance(bundle, dict) else getattr(bundle, 'spec_bundle_hash')\n"
    "    return _Obj(component_id=cid, spec_bundle_hash=sbh, model=model,\n"
    "                prompt_version=PROMPT_VERSION, cache_hit=False,\n"
    "                files={'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
    "                model_call_error=None, refused=None, retry_feedback=retry_feedback)\n"
)

VERIFIER = (
    COMMON_HEADER
    + "GATE_VERSION = 'verifier-orchestrator@2.2.0'\n"
    "\n"
    "def verify(component_id, repo_root, judge=None, test_author=None):\n"
    "    _log('verify')\n"
    "    return _Obj(component_id=component_id,\n"
    "                criteria=[{'id': 'AC-FOO-001', 'covers': 'R-FOO-001', 'kind': 'generated-test',\n"
    "                           'result': 'pass'}],\n"
    "                requirement_results={'R-FOO-001': 'pass'},\n"
    "                interface_drift=False, mutation_score=1.0, mutation_error=None,\n"
    "                overall='pass')\n"
)

LICENSE_SCANNER = (
    COMMON_HEADER
    + "def gate_version(repo_root):\n"
    "    return 'license_scanner@4.0.0-no-reference-corpus'\n"
    "\n"
    "def scan(component_id, repo_root):\n"
    "    _log('license_scan')\n"
    "    return {'component_id': component_id,\n"
    "            'gate_version': 'license_scanner@4.0.0-no-reference-corpus',\n"
    "            'evaluated': False, 'reason': 'no-reference-corpus',\n"
    "            'similarity_score': None, 'block_threshold': None, 'blocked': False,\n"
    "            'matches': [], 'notified': False, 'notification_delivery_error': None,\n"
    "            'cache_hit': False}\n"
)

SECRET_SCANNER = (
    COMMON_HEADER
    + "def _result(scope):\n"
    "    return _Obj(scope=scope, gate_version='secret_scanner@0.0.0', flagged=False,\n"
    "                matches=[], allowed=[], unused_allowlist_entries=[], notified=False,\n"
    "                notification_delivery_error=None, cache_hit=False)\n"
    "\n"
    "def gate_version(repo_root):\n"
    "    return 'secret_scanner@0.0.0'\n"
    "\n"
    "def scan(repo_root):\n"
    "    _log('secret_scan')\n"
    "    return _result('full')\n"
    "\n"
    "def scan_files(paths, repo_root=None):\n"
    "    return _result('precommit')\n"
    "\n"
    "def propose(repo_root):\n"
    "    return {'allowlist': {'version': 1, 'entries': []}, 'ineligible': []}\n"
)

PROVENANCE_TRACKER = (
    COMMON_HEADER
    + "_counter = [0]\n"
    "\n"
    "def write_attempt_record(component_id, generation_result, verification_report,\n"
    "                         spec_bundle_hash, repo_root):\n"
    "    _log('write_attempt_record')\n"
    "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
    "    d = Path(repo_root) / '.hotdocs' / 'attempts' / slug\n"
    "    d.mkdir(parents=True, exist_ok=True)\n"
    "    _counter[0] += 1\n"
    "    attempt_id = '2026-11-17T00:00:00Z-' + str(_counter[0]).zfill(6)\n"
    "    rec = {'attempt_id': attempt_id, 'component_id': component_id,\n"
    "           'timestamp': '2026-11-17T00:00:00Z', 'spec_bundle_hash': spec_bundle_hash,\n"
    "           'generation': {'component_id': component_id}, 'verification': None}\n"
    "    (d / (attempt_id + '.json')).write_text(json.dumps(rec), encoding='utf-8')\n"
    "    return rec\n"
    "\n"
    "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    "    return {'scope': 'whole-corpus', 'ready': True, 'components': {}, 'capabilities': {},\n"
    "            'not_ready_reasons': []}\n"
    "\n"
    "def last_requirement_failures(component_id, repo_root):\n"
    "    return []\n"
)

PROVENANCE_WRITER = (
    COMMON_HEADER
    + "class InvalidSealedInputError(Exception):\n"
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

TEST_AUTHOR = (
    COMMON_HEADER
    + "GATE_VERSION = 'generated_test@1.1.0'\n"
    "\n"
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    _log('author_test')\n"
    "    return {'component_id': 'comp-foo', 'criterion_id': 'AC-FOO-001', 'model': model,\n"
    "            'seed': seed, 'prompt_version': 'v1', 'cache_hit': False,\n"
    "            'file': {'path': 'verification/foo/generated-test/test_ac_foo_001.py',\n"
    "                     'content': 'def test_x():\\n    assert True\\n'},\n"
    "            'model_call_error': None}\n"
)

LLM_ENDPOINT = (
    COMMON_HEADER
    + "def complete(prompt, model, *, backend=None, **params):\n"
    "    _log('complete')\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'mock', 'model_call_error': None}\n"
)

FAKES = {
    "provenance-checker": PROVENANCE_CHECKER,
    "spec-bundle-assembler": SPEC_BUNDLE_ASSEMBLER,
    "generator": GENERATOR,
    "verifier-orchestrator": VERIFIER,
    "license-scanner": LICENSE_SCANNER,
    "secret-scanner": SECRET_SCANNER,
    "provenance-tracker": PROVENANCE_TRACKER,
    "provenance-writer": PROVENANCE_WRITER,
    "test-author": TEST_AUTHOR,
    "llm-endpoint": LLM_ENDPOINT,
}


def _write_fakes(repo_root):
    for slug, source in FAKES.items():
        d = repo_root / "gen" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / (slug.replace("-", "_") + ".py")).write_text(source, encoding="utf-8")


def _write_component(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    comp.mkdir(parents=True, exist_ok=True)
    (comp / "component.md").write_text(
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
        encoding="utf-8",
    )


def test_ac_gate_003a_generator_called_once_and_passing_candidate(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    monkeypatch.setenv(LOG_ENV, str(log_path))

    _write_fakes(repo_root)
    _write_component(repo_root)

    result = component_gate_runner.run_component_gates(
        "comp-foo", repo_root, "mock:model", seed=0, llm_backend=None, retry_feedback=None
    )

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    generate_calls = [ln for ln in lines if ln.startswith("generate ")]
    assert len(generate_calls) == 1, lines

    assert field(result, "blocked") is False
    assert field(result, "block_reason") is None
    assert field(result, "model_call_error") is None
    verification = field(result, "verification")
    assert verification is not None
    assert field(verification, "overall") == "pass"
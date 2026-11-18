# hotdocs-criterion: sha256:955620e12cc7bf393c7f974429b33a5a362796b1f6bdbe8825c583f465880290
import json
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_LINTER_BODY = (
    "import json\n"
    "from dataclasses import dataclass, field as dc_field\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class Finding:\n"
    "    rule_id: str\n"
    "    severity: str\n"
    "    file: str\n"
    "    line: int\n"
    "    message: str\n"
    "    rationale: object = None\n"
    "\n"
    "    def to_json(self):\n"
    "        out = {'rule_id': self.rule_id, 'severity': self.severity,\n"
    "               'file': self.file, 'line': self.line, 'message': self.message}\n"
    "        if self.rationale is not None:\n"
    "            out['rationale'] = self.rationale\n"
    "        return out\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class LintReport:\n"
    "    findings: list = dc_field(default_factory=list)\n"
    "\n"
    "    @property\n"
    "    def hard_failures(self):\n"
    "        return sum(1 for f in self.findings if f.severity == 'fail')\n"
    "\n"
    "    @property\n"
    "    def warnings(self):\n"
    "        return sum(1 for f in self.findings if f.severity == 'warn')\n"
    "\n"
    "    @property\n"
    "    def skipped(self):\n"
    "        return sum(1 for f in self.findings if f.severity == 'skipped')\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        if key == 'summary':\n"
    "            return {'hard_failures': self.hard_failures,\n"
    "                    'warnings': self.warnings, 'skipped': self.skipped}\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        try:\n"
    "            return self[key]\n"
    "        except AttributeError:\n"
    "            return default\n"
    "\n"
    "    def to_json(self):\n"
    "        return {'findings': [f.to_json() for f in self.findings],\n"
    "                'summary': self['summary']}\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def lint(paths, repo_root, strict=False, judge=None):\n"
    "    _log({'fn': 'lint'})\n"
    "    return LintReport(findings=[])\n"
    "\n"
    "\n"
    "def load_corpus(repo_root):\n"
    "    raise NotImplementedError('fake spec-linter: load_corpus not faked')\n"
)

FAKE_IMPACT_BODY = (
    "import json\n"
    "from dataclasses import dataclass, field as dc_field\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class ImpactedComponent:\n"
    "    component_id: str\n"
    "    reason: str\n"
    "    via: object = None\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class BlastRadiusReport:\n"
    "    impacted: list = dc_field(default_factory=list)\n"
    "    precondition_error: object = None\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def compute_blast_radius(changed_ids, repo_root):\n"
    "    _log({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
    "    return BlastRadiusReport(\n"
    "        impacted=[ImpactedComponent(component_id='comp-foo', reason='direct', via=None)],\n"
    "        precondition_error=None,\n"
    "    )\n"
)

FAKE_ASSEMBLER_BODY = (
    "import json\n"
    "from dataclasses import dataclass, field as dc_field\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class SpecBundle:\n"
    "    component_id: str\n"
    "    spec_bundle_hash: str\n"
    "    spec: str\n"
    "    interface: str\n"
    "    constraints: str\n"
    "    dependency_interfaces: dict = dc_field(default_factory=dict)\n"
    "    dependency_context: dict = dc_field(default_factory=dict)\n"
    "    dependency_usage: dict = dc_field(default_factory=dict)\n"
    "    vars: dict = dc_field(default_factory=dict)\n"
    "    glossary: str = ''\n"
    "    hint_code: object = None\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        try:\n"
    "            return getattr(self, key)\n"
    "        except AttributeError:\n"
    "            raise KeyError(key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "    def keys(self):\n"
    "        return ['component_id', 'spec_bundle_hash', 'spec', 'interface',\n"
    "                'constraints', 'dependency_interfaces', 'dependency_context',\n"
    "                'dependency_usage', 'vars', 'glossary', 'hint_code']\n"
    "\n"
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
    "    dependency_interfaces: dict = dc_field(default_factory=dict)\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    _log({'fn': 'assemble', 'component_id': component_id, 'mode': mode})\n"
    "    hint_code = {'foo.py': 'def foo(x):\\n    return 2 * x\\n'} if mode == 'hint' else None\n"
    "    return SpecBundle(\n"
    "        component_id=component_id,\n"
    "        spec_bundle_hash='sha256:fakebundle-' + component_id + '-' + str(mode),\n"
    "        spec='Foo doubles a number.',\n"
    "        interface='foo(x: int) -> int',\n"
    "        constraints='None.',\n"
    "        glossary='- **Foo** \\u2014 a test term.',\n"
    "        hint_code=hint_code,\n"
    "    )\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    raise NotImplementedError('fake assembler: assemble_criterion not faked')\n"
)

FAKE_GENERATOR_BODY = (
    "import json\n"
    "from dataclasses import dataclass\n"
    "\n"
    "GATE_VERSION = 'generator@2.0.0'\n"
    "PROMPT_VERSION = 'v10'\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class GenerationResult:\n"
    "    component_id: str\n"
    "    spec_bundle_hash: str\n"
    "    model: str\n"
    "    prompt_version: str\n"
    "    cache_hit: bool\n"
    "    files: object\n"
    "    model_call_error: object\n"
    "    refused: object\n"
    "    retry_feedback: object\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "\n"
    "def _bfield(bundle, name):\n"
    "    return bundle[name] if isinstance(bundle, dict) else getattr(bundle, name)\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
    "    cid = _bfield(bundle, 'component_id')\n"
    "    h = _bfield(bundle, 'spec_bundle_hash')\n"
    "    _log({'fn': 'generate', 'component_id': cid, 'spec_bundle_hash': h,\n"
    "          'model': model})\n"
    "    return GenerationResult(\n"
    "        component_id=cid,\n"
    "        spec_bundle_hash=h,\n"
    "        model=model,\n"
    "        prompt_version=PROMPT_VERSION,\n"
    "        cache_hit=False,\n"
    "        files={'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
    "        model_call_error=None,\n"
    "        refused=None,\n"
    "        retry_feedback=retry_feedback,\n"
    "    )\n"
)

FAKE_ENDPOINT_BODY = (
    "import json\n"
    "\n"
    "DEFAULT_TIMEOUT_SECONDS = 600\n"
    "\n"
    "\n"
    "class ModelResolutionError(Exception):\n"
    "    pass\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def _count_complete_calls():\n"
    "    n = 0\n"
    "    try:\n"
    "        with open(LOG, 'r', encoding='utf-8') as fh:\n"
    "            for line in fh:\n"
    "                line = line.strip()\n"
    "                if line and json.loads(line).get('fn') == 'complete':\n"
    "                    n += 1\n"
    "    except FileNotFoundError:\n"
    "        pass\n"
    "    return n\n"
    "\n"
    "\n"
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    prior = _count_complete_calls()\n"
    "    _log({'fn': 'complete', 'model': model})\n"
    "    if prior == 0:\n"
    "        text = json.dumps({'completeness_score': 0.9, 'score': 0.9,\n"
    "                           'completeness_rationale': 'Looks complete.',\n"
    "                           'rationale': 'Looks complete.'})\n"
    "    else:\n"
    "        text = json.dumps({'redundancy_flags': [], 'flags': []})\n"
    "    return {'text': text, 'model': model, 'backend': 'fake',\n"
    "            'model_call_error': None}\n"
    "\n"
    "\n"
    "def parse_model(model):\n"
    "    if ':' in model:\n"
    "        head, rest = model.split(':', 1)\n"
    "        if head in ('claude-cli', 'anthropic', 'openai', 'openai-compatible', 'gemini', 'ollama'):\n"
    "            return (head, rest)\n"
    "    return (None, model)\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_fake(repo_root, slug, body, log_path):
    module_name = slug.replace("-", "_")
    source = "LOG = " + repr(str(log_path)) + "\n\n" + body
    _write(repo_root / "gen" / slug / (module_name + ".py"), source)


def _build_corpus(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
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
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
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
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "legacy" / "foo" / "foo.py", "def foo(x):\n    return 2 * x\n")


def _setup(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    _build_corpus(repo_root)
    _write_fake(repo_root, "spec-linter", FAKE_LINTER_BODY, log_path)
    _write_fake(repo_root, "impact-analyzer", FAKE_IMPACT_BODY, log_path)
    _write_fake(repo_root, "spec-bundle-assembler", FAKE_ASSEMBLER_BODY, log_path)
    _write_fake(repo_root, "generator", FAKE_GENERATOR_BODY, log_path)
    _write_fake(repo_root, "llm-endpoint", FAKE_ENDPOINT_BODY, log_path)
    return repo_root, log_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    entries = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _preview_keys(hint_previews):
    if isinstance(hint_previews, dict):
        return sorted(hint_previews.keys())
    return sorted(list(hint_previews))


def test_hint_preview_with_model_assembles_hint_and_generates_once(tmp_path):
    repo_root, log_path = _setup(tmp_path)

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    hint_previews = field(report, "hint_previews")
    assert _preview_keys(hint_previews) == ["comp-foo"]

    entries = _read_log(log_path)
    assembles = [e for e in entries if e["fn"] == "assemble"]
    generates = [e for e in entries if e["fn"] == "generate"]

    assert assembles, "assemble was never called"
    assert all(e["mode"] == "hint" for e in assembles), assembles
    assert not any(e["mode"] == "cold" for e in assembles)
    foo_assembles = [e for e in assembles if e["component_id"] == "comp-foo"]
    assert foo_assembles, assembles

    assert len(generates) == 1, generates
    gen_call = generates[0]
    assert gen_call["component_id"] == "comp-foo"
    assert gen_call["spec_bundle_hash"] == "sha256:fakebundle-comp-foo-hint"
    assert gen_call["model"] == "fake-model"


def test_hint_preview_without_model_assembles_hint_and_never_generates(tmp_path):
    repo_root, log_path = _setup(tmp_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    hint_previews = field(report, "hint_previews")
    assert _preview_keys(hint_previews) == ["comp-foo"]

    entries = _read_log(log_path)
    assembles = [e for e in entries if e["fn"] == "assemble"]
    generates = [e for e in entries if e["fn"] == "generate"]

    assert assembles, "assemble was never called"
    assert all(e["mode"] == "hint" for e in assembles), assembles
    assert any(e["component_id"] == "comp-foo" for e in assembles), assembles
    assert generates == [], generates
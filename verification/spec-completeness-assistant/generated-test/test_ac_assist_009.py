# hotdocs-criterion: sha256:7d12056bbb5e1cf055ac8925ade26fd2c4eb1d0a5f3570fd6f02edc7451b9c8a
import importlib.util
import json
import sys
from pathlib import Path

import pytest

import spec_completeness_assistant


WARN_RULE_ID = "R-LINT-007"
FAIL_RULE_ID = "R-LINT-003"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _real_spec_linter_path():
    try:
        gen = next(
            p
            for p in Path(spec_completeness_assistant.__file__).resolve().parents
            if p.name == "gen"
        )
    except StopIteration:
        return None
    base = gen / "spec-linter"
    if (base / "spec_linter.py").is_file():
        return str(base / "spec_linter.py")
    if (base / "spec_linter" / "__init__.py").is_file():
        return str(base / "spec_linter" / "__init__.py")
    return None


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_corpus(root):
    _write(root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = root / "specs" / "components" / "foo"
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
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
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
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _spec_linter_source(severity, rule_id):
    return (
        "import dataclasses\n"
        "import importlib.util\n"
        "import sys\n"
        "\n"
        "SEVERITY = " + repr(severity) + "\n"
        "RULE_ID = " + repr(rule_id) + "\n"
        "REAL_PATH = " + repr(_real_spec_linter_path()) + "\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class Finding:\n"
        "    rule_id: str\n"
        "    severity: str\n"
        "    file: str\n"
        "    line: int\n"
        "    message: str\n"
        "    rationale: object = None\n"
        "\n"
        "    def to_json(self):\n"
        "        d = {\n"
        "            'rule_id': self.rule_id,\n"
        "            'severity': self.severity,\n"
        "            'file': self.file,\n"
        "            'line': self.line,\n"
        "            'message': self.message,\n"
        "        }\n"
        "        if self.rationale is not None:\n"
        "            d['rationale'] = self.rationale\n"
        "        return d\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class LintReport:\n"
        "    findings: list\n"
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
        "    def to_json(self):\n"
        "        return {\n"
        "            'findings': [f.to_json() for f in self.findings],\n"
        "            'summary': {\n"
        "                'hard_failures': self.hard_failures,\n"
        "                'warnings': self.warnings,\n"
        "                'skipped': self.skipped,\n"
        "            },\n"
        "        }\n"
        "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    return LintReport(findings=[Finding(\n"
        "        RULE_ID, SEVERITY, 'specs/components/foo/component.md', 1,\n"
        "        'fake finding from the test stand-in',\n"
        "    )])\n"
        "\n"
        "\n"
        "def load_corpus(repo_root):\n"
        "    name = '_fake_backing_real_spec_linter'\n"
        "    spec = importlib.util.spec_from_file_location(name, REAL_PATH)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    sys.modules[name] = module\n"
        "    spec.loader.exec_module(module)\n"
        "    return module.load_corpus(repo_root)\n"
    )


IMPACT_SOURCE = (
    "def compute_blast_radius(changed_ids, repo_root):\n"
    "    return {\n"
    "        'impacted': [\n"
    "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
    "        ],\n"
    "        'precondition_error': None,\n"
    "    }\n"
)


ASSEMBLER_SOURCE = (
    "import dataclasses\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
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
    "    def __getitem__(self, key):\n"
    "        if key not in self.keys():\n"
    "            raise KeyError(key)\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key) if key in self.keys() else default\n"
    "\n"
    "    def keys(self):\n"
    "        return [f.name for f in dataclasses.fields(self)]\n"
    "\n"
    "    def __iter__(self):\n"
    "        return iter(self.keys())\n"
    "\n"
    "    def __len__(self):\n"
    "        return len(self.keys())\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
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
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    return SpecBundle(\n"
    "        component_id=component_id,\n"
    "        spec_bundle_hash='sha256:' + '0' * 64,\n"
    "        spec='# Foo\\n\\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.',\n"
    "        interface='# Library\\n\\nfoo(x: int) -> int',\n"
    "        constraints='None.',\n"
    "        glossary='- **Foo** — a test term.',\n"
    "        hint_code=({} if mode == 'hint' else None),\n"
    "    )\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return CriterionBundle(\n"
    "        component_id=component_id,\n"
    "        criterion_id=criterion_id,\n"
    "        covers='R-FOO-001',\n"
    "        criterion_text='Given x = 2',\n"
    "        requirement_text='foo(x) MUST return 2 * x',\n"
    "        interface='foo(x: int) -> int',\n"
    "        glossary='- **Foo** — a test term.',\n"
    "    )\n"
)


def _generator_source(log_path):
    return (
        "import dataclasses\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'generator@2.0.0'\n"
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
        "    files: object\n"
        "    model_call_error: object\n"
        "    refused: object\n"
        "    retry_feedback: object\n"
        "\n"
        "\n"
        "def _get(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
        "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('generate\\t' + str(model) + '\\n')\n"
        "    return GenerationResult(\n"
        "        component_id=_get(bundle, 'component_id'),\n"
        "        spec_bundle_hash=_get(bundle, 'spec_bundle_hash'),\n"
        "        model=model,\n"
        "        prompt_version=PROMPT_VERSION,\n"
        "        cache_hit=False,\n"
        "        files={'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
        "        model_call_error=None,\n"
        "        refused=None,\n"
        "        retry_feedback=retry_feedback,\n"
        "    )\n"
    )


def _llm_endpoint_source(log_path):
    completeness = json.dumps({"completeness_score": 0.7, "completeness_rationale": "AC missing"})
    redundancy = json.dumps({"redundancy_flags": []})
    return (
        "import os\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "RESPONSES = [" + repr(completeness) + ", " + repr(redundancy) + "]\n"
        "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    count = 0\n"
        "    if os.path.exists(LOG):\n"
        "        with open(LOG, 'r', encoding='utf-8') as fh:\n"
        "            count = len([ln for ln in fh.read().splitlines() if ln.strip()])\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete\\t' + str(model) + '\\n')\n"
        "    return {\n"
        "        'text': RESPONSES[count % 2],\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n"
        "\n"
        "\n"
        "def parse_model(model):\n"
        "    return (None, model)\n"
        "\n"
        "\n"
        "def resolve_provider(model, config=None):\n"
        "    return {\n"
        "        'provider': None, 'model': model, 'base_url': None,\n"
        "        'api_key_env': None, 'timeout_seconds': DEFAULT_TIMEOUT_SECONDS,\n"
        "        'auth': None,\n"
        "    }\n"
    )


def _make_repo(root, severity="warn", rule_id=WARN_RULE_ID, with_model_fakes=False):
    root.mkdir(parents=True, exist_ok=True)
    _write_corpus(root)
    gen = root / "gen"
    _write(gen / "spec-linter" / "spec_linter.py", _spec_linter_source(severity, rule_id))
    _write(gen / "impact-analyzer" / "impact_analyzer.py", IMPACT_SOURCE)
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SOURCE)
    llm_log = root / "llm_calls.log"
    gen_log = root / "generator_calls.log"
    if with_model_fakes:
        _write(gen / "generator" / "generator.py", _generator_source(gen_log))
        _write(gen / "llm-endpoint" / "llm_endpoint.py", _llm_endpoint_source(llm_log))
    return root, llm_log


def _run(argv):
    try:
        return spec_completeness_assistant.main(argv)
    except SystemExit as exc:
        return exc.code


def _parse_json(out):
    out = out.strip()
    try:
        return json.loads(out)
    except ValueError:
        start = out.index("{")
        end = out.rindex("}")
        return json.loads(out[start : end + 1])


def test_degraded_json_and_text(tmp_path, capsys):
    root, llm_log = _make_repo(tmp_path / "repo")

    code = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", "--repo-root=" + str(root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    report = _parse_json(out)
    assert list(field(report, "predicted_blast_radius")) == ["comp-foo"]
    assert field(report, "degraded") is True

    code = spec_completeness_assistant.main(
        ["--changed", "R-FOO-001", "--repo-root", str(root), "--format", "text"]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert WARN_RULE_ID in out
    assert "comp-foo" in out


def test_model_json_and_text(tmp_path, capsys):
    root, llm_log = _make_repo(tmp_path / "repo", with_model_fakes=True)

    if llm_log.exists():
        llm_log.unlink()
    code = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            "--repo-root=" + str(root),
            "--model=fake-model",
            "--format=json",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert llm_log.exists(), "faked llm-endpoint was never called"
    lines = [ln for ln in llm_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    for ln in lines:
        assert ln.split("\t", 1)[1] == "fake-model"
    report = _parse_json(out)
    assert field(report, "degraded") is False
    assert field(report, "completeness_score") == pytest.approx(0.7)

    llm_log.unlink()
    code = spec_completeness_assistant.main(
        [
            "--changed=R-FOO-001",
            "--repo-root=" + str(root),
            "--model=fake-model",
            "--format=text",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "0.7" in out


def test_fail_finding_returns_1(tmp_path, capsys):
    root, _ = _make_repo(tmp_path / "repo", severity="fail", rule_id=FAIL_RULE_ID)
    code = spec_completeness_assistant.main(
        ["--changed=R-FOO-001", "--repo-root=" + str(root), "--format=json"]
    )
    capsys.readouterr()
    assert code == 1


@pytest.mark.parametrize(
    "argv_builder",
    [
        lambda r: [],
        lambda r: ["serve", "--changed=R-FOO-001"],
        lambda r: ["--repo-root=" + r, "--format=json"],
        lambda r: ["--changed=R-FOO-001", "--repo-root=" + r, "--format=bogus"],
        lambda r: ["--changed=R-FOO-001", "--repo-root=" + r, "--no-such-flag"],
        lambda r: ["--repo-root=" + r, "--changed"],
    ],
    ids=["empty", "stray-word", "no-changed", "bad-format", "unknown-arg", "changed-no-value"],
)
def test_usage_errors_return_2(tmp_path, capsys, argv_builder):
    root, _ = _make_repo(tmp_path / "repo")
    code = _run(argv_builder(str(root)))
    capsys.readouterr()
    assert code == 2
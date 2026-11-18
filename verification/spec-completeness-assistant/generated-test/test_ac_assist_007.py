# hotdocs-criterion: sha256:91f31f4c4f254c983050e58e26ffde26238d94633802a01c13ee06acf3b8e4c3
import importlib.util
import sys
from pathlib import Path

import spec_completeness_assistant


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
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


def _log_helper(log_path):
    return (
        "def _log(line):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
    )


def _write_fakes(repo_root, log_path):
    gen = repo_root / "gen"
    helper = _log_helper(log_path)

    linter_src = (
        "import dataclasses\n"
        "\n"
        + helper
        + "@dataclasses.dataclass\n"
        "class Finding:\n"
        "    rule_id: str\n"
        "    severity: str\n"
        "    file: str\n"
        "    line: object\n"
        "    message: str\n"
        "    rationale: object = None\n"
        "\n"
        "    def to_json(self):\n"
        "        d = {'rule_id': self.rule_id, 'severity': self.severity, 'file': self.file,\n"
        "             'line': self.line, 'message': self.message}\n"
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
        "        return {'findings': [f.to_json() for f in self.findings],\n"
        "                'summary': {'hard_failures': self.hard_failures,\n"
        "                            'warnings': self.warnings,\n"
        "                            'skipped': self.skipped}}\n"
        "\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('spec-linter lint')\n"
        "    return LintReport(findings=[Finding(\n"
        "        rule_id='R-LINT-099', severity='warn',\n"
        "        file='specs/components/foo/component.md', line=3,\n"
        "        message='a fake warning')])\n"
        "\n"
        "\n"
        "def load_corpus(repo_root):\n"
        "    _log('spec-linter load_corpus')\n"
        "    return None\n"
    )
    _write(gen / "spec-linter" / "spec_linter.py", linter_src)

    impact_src = (
        helper
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('impact-analyzer compute_blast_radius')\n"
        "    return {'impacted': [{'component_id': 'comp-foo', 'reason': 'direct', 'via': None}],\n"
        "            'precondition_error': None}\n"
    )
    _write(gen / "impact-analyzer" / "impact_analyzer.py", impact_src)

    assembler_src = (
        "import dataclasses\n"
        "\n"
        + helper
        + "@dataclasses.dataclass\n"
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
        "    _log('spec-bundle-assembler assemble ' + component_id + ' ' + mode)\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + '0' * 64,\n"
        "        spec='Foo doubles a number.',\n"
        "        interface='foo(x: int) -> int',\n"
        "        constraints='None.',\n"
        "        glossary='- **Foo** — a test term.',\n"
        "        hint_code=({'foo.py': 'def foo(x):\\n    return 2 * x\\n'} if mode == 'hint' else None),\n"
        "    )\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('spec-bundle-assembler assemble_criterion')\n"
        "    return CriterionBundle(component_id, criterion_id, 'R-FOO-001', '', '', '', '')\n"
    )
    _write(gen / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_src)

    generator_src = (
        helper
        + "GATE_VERSION = 'generator@2.0.0'\n"
        "PROMPT_VERSION = 'v10'\n"
        "\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generator generate')\n"
        "    return {'component_id': 'comp-foo', 'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "            'model': model, 'prompt_version': PROMPT_VERSION, 'cache_hit': False,\n"
        "            'files': {'foo.py': 'def foo(x):\\n    return 2 * x\\n'},\n"
        "            'model_call_error': None, 'refused': None,\n"
        "            'retry_feedback': retry_feedback}\n"
    )
    _write(gen / "generator" / "generator.py", generator_src)

    endpoint_src = (
        helper
        + "DEFAULT_TIMEOUT_SECONDS = 600\n"
        "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('llm-endpoint complete')\n"
        "    return {'text': '{}', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
    )
    _write(gen / "llm-endpoint" / "llm_endpoint.py", endpoint_src)


def test_ac_assist_007_degraded_mode_makes_no_model_call(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")

    _build_corpus(repo_root)
    _write_fakes(repo_root, log_path)

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    lint_findings = list(field(report, "lint_findings"))
    assert len(lint_findings) == 1
    assert field(lint_findings[0], "severity") == "warn"
    assert field(lint_findings[0], "rule_id") == "R-LINT-099"

    assert list(field(report, "predicted_blast_radius")) == ["comp-foo"]

    hint_previews = field(report, "hint_previews")
    assert "comp-foo" in hint_previews

    assert field(report, "degraded") is True
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []

    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    # Fakes for the non-model steps actually ran.
    assert any(ln.startswith("spec-linter lint") for ln in lines), lines
    assert any(ln.startswith("impact-analyzer compute_blast_radius") for ln in lines), lines
    assert any(ln == "spec-bundle-assembler assemble comp-foo hint" for ln in lines), lines
    # No model call of any kind.
    assert not any(ln.startswith("llm-endpoint") for ln in lines), lines
    assert not any(ln.startswith("generator") for ln in lines), lines
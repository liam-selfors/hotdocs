# hotdocs-criterion: sha256:0dbd531749952e258873a0971fe1e4af96dd73fc484d68fcca7e8eee96188cad
import importlib.util
import os
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


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
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
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
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
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def fake_linter_source(log_path):
    return (
        "import dataclasses\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
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
        "        d = {'rule_id': self.rule_id, 'severity': self.severity,\n"
        "             'file': self.file, 'line': self.line, 'message': self.message}\n"
        "        if self.rationale is not None:\n"
        "            d['rationale'] = self.rationale\n"
        "        return d\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class LintReport:\n"
        "    findings: list = dataclasses.field(default_factory=list)\n"
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
        "    _log('lint')\n"
        "    return LintReport(findings=[])\n"
    )


def fake_impact_source(log_path):
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('compute_blast_radius')\n"
        "    return {\n"
        "        'impacted': [\n"
        "            {'component_id': 'comp-foo', 'reason': 'direct', 'via': None},\n"
        "        ],\n"
        "        'precondition_error': None,\n"
        "    }\n"
    )


def fake_assembler_source(log_path):
    return (
        "import dataclasses\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "class _Mapping:\n"
        "    def __getitem__(self, key):\n"
        "        if key not in self.keys():\n"
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
        "    def __iter__(self):\n"
        "        return iter(self.keys())\n"
        "\n"
        "    def __len__(self):\n"
        "        return len(self.keys())\n"
        "\n"
        "    def __contains__(self, key):\n"
        "        return key in self.keys()\n"
        "\n"
        "    def items(self):\n"
        "        return [(k, getattr(self, k)) for k in self.keys()]\n"
        "\n"
        "    def values(self):\n"
        "        return [getattr(self, k) for k in self.keys()]\n"
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
        "    _log('assemble ' + component_id + ' ' + mode)\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + '0' * 64,\n"
        "        spec='# Foo\\n\\nFoo doubles a number.',\n"
        "        interface='# Library',\n"
        "        constraints='None.',\n"
        "        dependency_interfaces={},\n"
        "        dependency_context={},\n"
        "        dependency_usage={},\n"
        "        vars={},\n"
        "        glossary='- **Foo** — a test term.',\n"
        "        hint_code=({} if mode == 'hint' else None),\n"
        "    )\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion ' + component_id + ' ' + criterion_id)\n"
        "    return CriterionBundle(\n"
        "        component_id=component_id,\n"
        "        criterion_id=criterion_id,\n"
        "        covers='R-FOO-001',\n"
        "        criterion_text='Given x = 2',\n"
        "        requirement_text='foo(x) MUST return 2 * x.',\n"
        "        interface='# Library',\n"
        "        glossary='- **Foo** — a test term.',\n"
        "        dependency_interfaces={},\n"
        "    )\n"
    )


def snapshot(repo_root):
    result = {}
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            full = Path(dirpath) / name
            rel = full.relative_to(repo_root)
            if "__pycache__" in rel.parts:
                continue
            result[rel.as_posix()] = full.read_bytes()
    return result


def test_ac_assist_008_report_exposes_decision_fields_and_repo_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "fake_calls.log"

    build_corpus(repo_root)
    write(
        repo_root / "gen" / "spec-linter" / "spec_linter.py",
        fake_linter_source(log_path),
    )
    write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        fake_impact_source(log_path),
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        fake_assembler_source(log_path),
    )

    before = snapshot(repo_root)
    assert before, "fixture snapshot should not be empty"

    report = spec_completeness_assistant.assist(["R-FOO-001"], repo_root)

    # The fakes actually ran.
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert "lint" in calls
    assert "compute_blast_radius" in calls
    assert any(line.startswith("assemble comp-foo") for line in calls)

    # The report exposes the fields a calling tool needs to record an
    # accept/override decision against the suggestions it carries.
    for name in (
        "lint_findings",
        "predicted_blast_radius",
        "hint_previews",
        "completeness_score",
        "completeness_rationale",
        "redundancy_flags",
        "degraded",
    ):
        assert has_field(report, name), "report missing field " + repr(name)

    assert list(field(report, "lint_findings")) == []
    assert list(field(report, "predicted_blast_radius")) == ["comp-foo"]
    previews = field(report, "hint_previews")
    assert "comp-foo" in previews
    assert field(report, "degraded") is True
    assert field(report, "completeness_score") is None
    assert not field(report, "redundancy_flags")

    # The component itself captured/stored nothing: repo_root is unchanged.
    after = snapshot(repo_root)
    assert sorted(after.keys()) == sorted(before.keys())
    for rel, content in before.items():
        assert after[rel] == content, "file changed: " + rel
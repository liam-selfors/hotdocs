# hotdocs-criterion: sha256:3cf400526d750b99773dc74c18c5204462b7fce5461537f113438d6071110db9
import importlib.util
import sys
from pathlib import Path

import spec_completeness_assistant


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FINDING = {
    "rule_id": "R-LINT-003",
    "severity": "fail",
    "file": "specs/components/foo/component.md",
    "line": 12,
    "message": "depends_on references 'comp-bar', which does not exist",
}


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _write_fixture_corpus(repo_root):
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


def _log_prelude(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(name):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
    )


def _lint_source(log_path, severity):
    return (
        "import dataclasses\n"
        "\n"
        + _log_prelude(log_path)
        + "SEVERITY = " + repr(severity) + "\n"
        "RULE_ID = " + repr(FINDING["rule_id"]) + "\n"
        "FILE = " + repr(FINDING["file"]) + "\n"
        "LINE = " + repr(FINDING["line"]) + "\n"
        "MESSAGE = " + repr(FINDING["message"]) + "\n"
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
        "        d = dict(rule_id=self.rule_id, severity=self.severity, file=self.file,\n"
        "                 line=self.line, message=self.message)\n"
        "        if self.rationale is not None:\n"
        "            d['rationale'] = self.rationale\n"
        "        return d\n"
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
        "        return dict(findings=[f.to_json() for f in self.findings],\n"
        "                    summary=dict(hard_failures=self.hard_failures,\n"
        "                                 warnings=self.warnings, skipped=self.skipped))\n"
        "\n"
        "def lint(paths, repo_root, strict=False, judge=None):\n"
        "    _log('spec_linter.lint')\n"
        "    return LintReport(findings=[Finding(RULE_ID, SEVERITY, FILE, LINE, MESSAGE)])\n"
    )


def _impact_source(log_path):
    return (
        _log_prelude(log_path)
        + "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log('impact_analyzer.compute_blast_radius')\n"
        "    return dict(impacted=[], precondition_error=None)\n"
    )


def _assembler_source(log_path):
    return (
        _log_prelude(log_path)
        + "def assemble(component_id, repo_root=None, mode='cold'):\n"
        "    _log('spec_bundle_assembler.assemble')\n"
        "    return dict(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + '0' * 64,\n"
        "        spec='spec',\n"
        "        interface='interface',\n"
        "        constraints='constraints',\n"
        "        dependency_interfaces=dict(),\n"
        "        dependency_context=dict(),\n"
        "        dependency_usage=dict(),\n"
        "        vars=dict(),\n"
        "        glossary='',\n"
        "        hint_code=(dict() if mode == 'hint' else None),\n"
        "    )\n"
    )


def _generator_source(log_path):
    return (
        _log_prelude(log_path)
        + "GATE_VERSION = 'generator@2.0.0'\n"
        "PROMPT_VERSION = 'v10'\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    _log('generator.generate')\n"
        "    cid = bundle['component_id'] if isinstance(bundle, dict) else bundle.component_id\n"
        "    h = bundle['spec_bundle_hash'] if isinstance(bundle, dict) else bundle.spec_bundle_hash\n"
        "    return dict(\n"
        "        component_id=cid,\n"
        "        spec_bundle_hash=h,\n"
        "        model=model,\n"
        "        prompt_version=PROMPT_VERSION,\n"
        "        cache_hit=False,\n"
        "        files={'x.py': 'pass\\n'},\n"
        "        model_call_error=None,\n"
        "        refused=None,\n"
        "        retry_feedback=retry_feedback,\n"
        "    )\n"
    )


def _llm_source(log_path):
    text = (
        '{"completeness_score": 0.5, "completeness_rationale": "ok", '
        '"score": 0.5, "rationale": "ok", "redundancy_flags": [], "flags": []}'
    )
    return (
        _log_prelude(log_path)
        + "TEXT = " + repr(text) + "\n"
        "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log('llm_endpoint.complete')\n"
        "    return dict(text=TEXT, model=model, backend='fake', model_call_error=None)\n"
    )


def _setup(tmp_path, severity):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("")
    _write_fixture_corpus(repo_root)
    gen = repo_root / "gen"
    _write(gen / "spec-linter" / "spec_linter.py", _lint_source(log_path, severity))
    _write(gen / "impact-analyzer" / "impact_analyzer.py", _impact_source(log_path))
    _write(
        gen / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _assembler_source(log_path),
    )
    _write(gen / "generator" / "generator.py", _generator_source(log_path))
    _write(gen / "llm-endpoint" / "llm_endpoint.py", _llm_source(log_path))
    return repo_root, log_path


def _log_lines(log_path):
    return [line for line in log_path.read_text().splitlines() if line.strip()]


def test_fail_finding_halts_assist(tmp_path):
    repo_root, log_path = _setup(tmp_path, "fail")

    report = spec_completeness_assistant.assist(
        ["R-FOO-001"], repo_root, model="fake-model"
    )

    findings = list(field(report, "lint_findings"))
    assert len(findings) == 1
    entry = findings[0]
    for key, expected in FINDING.items():
        assert field(entry, key) == expected
    if isinstance(entry, dict):
        assert set(entry.keys()) == set(FINDING.keys())

    assert list(field(report, "predicted_blast_radius")) == []
    assert dict(field(report, "hint_previews")) == {}
    assert field(report, "completeness_score") is None
    assert field(report, "completeness_rationale") is None
    assert list(field(report, "redundancy_flags")) == []

    lines = _log_lines(log_path)
    assert any(line.startswith("spec_linter.lint") for line in lines)
    for forbidden in ("impact_analyzer", "generator", "llm_endpoint"):
        assert not any(line.startswith(forbidden) for line in lines), lines


def test_warn_finding_proceeds_past_lint(tmp_path):
    repo_root, log_path = _setup(tmp_path, "warn")

    try:
        spec_completeness_assistant.assist(
            ["R-FOO-001"], repo_root, model="fake-model"
        )
    except Exception:
        # The criterion only concerns whether assist proceeds past linting;
        # what happens after the blast-radius call is not asserted here.
        pass

    lines = _log_lines(log_path)
    assert any(line.startswith("spec_linter.lint") for line in lines), lines
    assert any(
        line.startswith("impact_analyzer.compute_blast_radius") for line in lines
    ), lines
"""CS-AMBIGUITY-001 (Covers: P-AMBIGUITY-GATE).

Given a component spec whose Behavior section contains a requirement with no
  covering acceptance criterion
When the spec change is submitted to the pipeline
Then spec-linter reports a fail-severity finding and the merge is blocked
  before generation runs
"""

import capability_scenario_verifier
import citation_checker
import corpus_graph_builder
import corpus_loader
import criterion_compiler
import docs_site_renderer
import llm_endpoint
import size_checker
import spec_completeness_assistant
import spec_linter
import test_author
import verifier_orchestrator

import json
import shutil
from pathlib import Path


UNCOVERED_ID = "R-WIDGET-002"


def field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(behavior_ids):
    behavior_lines = "\n".join(
        f"- `{rid}` — the widget behaves as its requirement file states."
        for rid in behavior_ids
    )
    return (
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/widget/\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component used to exercise traceability checks.\n"
        "\n"
        "## Behavior\n"
        "\n"
        f"{behavior_lines}\n"
    )


def _build_fixture(repo_root: Path, with_uncovered: bool) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **widget** — the fixture component in this corpus.\n",
    )
    _write(repo_root / "legacy" / "widget" / "widget.py", "def widget_value():\n    return 1\n")

    behavior_ids = ["R-WIDGET-001"] + ([UNCOVERED_ID] if with_uncovered else [])
    comp_dir = repo_root / "specs" / "components" / "widget"
    _write(comp_dir / "component.md", _component_md(behavior_ids))

    _write(
        comp_dir / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n`widget_value()` MUST return `1`.\n",
    )
    _write(
        comp_dir / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a widget fixture\n"
        "When widget_value is called\n"
        "Then the result is 1\n"
        "```\n",
    )
    if with_uncovered:
        # A requirement with no acceptance criterion carrying `Covers: R-WIDGET-002`.
        _write(
            comp_dir / "requirements" / f"{UNCOVERED_ID}.md",
            f"# {UNCOVERED_ID}\n\n`widget_value()` MUST never return a negative number.\n",
        )


def _fail_findings(report):
    return [f for f in field(report, "findings") or [] if field(f, "severity") == "fail"]


def _mentions_uncovered(finding) -> bool:
    text = f"{field(finding, 'file') or ''} {field(finding, 'message') or ''}"
    return UNCOVERED_ID in text


def test_uncovered_requirement_fails_lint_and_blocks_merge(tmp_path, capsys):
    baseline_root = tmp_path / "baseline"
    _build_fixture(baseline_root, with_uncovered=False)
    baseline = spec_linter.lint(None, baseline_root)
    assert not any(_mentions_uncovered(f) for f in _fail_findings(baseline))

    repo_root = tmp_path / "changed"
    _build_fixture(repo_root, with_uncovered=True)

    report = spec_linter.lint(None, repo_root)
    fails = _fail_findings(report)
    uncovered_fails = [f for f in fails if _mentions_uncovered(f)]
    assert uncovered_fails, (
        "expected a fail-severity finding for the uncovered requirement; got "
        f"{[(field(f, 'rule_id'), field(f, 'severity'), field(f, 'file'), field(f, 'message')) for f in field(report, 'findings') or []]}"
    )

    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard >= 1
    assert hard > (
        baseline["hard_failures"] if isinstance(baseline, dict) else baseline.hard_failures
    )

    # The merge gate: the linter's CLI exits 1 on any fail-severity finding.
    exit_code = spec_linter.main([f"--repo-root={repo_root}", "--format=json"])
    capsys.readouterr()
    assert exit_code == 1


def test_uncovered_requirement_stops_pipeline_before_generation(tmp_path):
    fixture_root = tmp_path / "fixture"
    _build_fixture(fixture_root, with_uncovered=True)

    repo_root = tmp_path / "pipeline"
    shutil.copytree(fixture_root, repo_root)

    log_path = tmp_path / "invocations.log"
    log_literal = repr(str(log_path))

    log_helper = (
        "import json\n"
        "def _log(record):\n"
        f"    with open({log_literal}, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
    )

    _write(
        repo_root / "gen" / "impact-analyzer" / "impact_analyzer.py",
        log_helper
        + "\n"
        "def compute_blast_radius(changed_ids, repo_root):\n"
        "    _log({'fn': 'compute_blast_radius', 'changed_ids': list(changed_ids)})\n"
        "    return ['comp-widget']\n",
    )
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        log_helper
        + "\n"
        "def assemble(component_id, repo_root=None, mode='full', **kwargs):\n"
        "    _log({'fn': 'assemble', 'component_id': component_id, 'mode': mode})\n"
        "    return {'component_id': component_id, 'mode': mode, 'files': {}}\n",
    )
    _write(
        repo_root / "gen" / "generator" / "generator.py",
        log_helper
        + "\n"
        "def generate(bundle, model, retry_feedback=None, repo_root=None, llm_backend=None, **kwargs):\n"
        "    _log({'fn': 'generate', 'model': model})\n"
        "    return {'files': [], 'model_call_error': None}\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        log_helper
        + "\n"
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    _log({'fn': 'complete', 'model': model})\n"
        "    return {'text': '{}', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )

    def fake_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"fn": "llm_backend", "model": model}) + "\n")
        return {"text": "{}", "model": model, "backend": "fake", "model_call_error": None}

    result = spec_completeness_assistant.assist(
        [UNCOVERED_ID], repo_root, model="fake-model", llm_backend=fake_backend
    )

    lint_findings = field(result, "lint_findings") or []
    fails = [f for f in lint_findings if field(f, "severity") == "fail"]
    assert any(_mentions_uncovered(f) for f in fails), (
        f"expected a fail-severity lint finding for {UNCOVERED_ID}; got {lint_findings!r}"
    )

    calls = []
    if log_path.exists():
        calls = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    called = [c["fn"] for c in calls]
    assert "generate" not in called, f"generation ran despite a fail lint finding: {called}"
    assert "complete" not in called, f"a model call ran despite a fail lint finding: {called}"
    assert "llm_backend" not in called, f"a model call ran despite a fail lint finding: {called}"
    assert not (repo_root / "gen" / "widget").exists()
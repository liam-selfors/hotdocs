# hotdocs-criterion: sha256:79b17241908ec9aa3a9d13408402fa05198c36150d3862982523f2fa552a7468
import importlib.util
import json
import sys
from pathlib import Path

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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, cover_second_requirement):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** \u2014 a small thing the foo component manages.\n",
    )
    comp = specs / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo manages widgets.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `R-FOO-001` \u2014 foo stores a widget.\n"
        "- `R-FOO-002` \u2014 foo deletes a widget.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001: Store a widget\n"
        "\n"
        "`store(name)` MUST record the widget under `name`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002: Delete a widget\n"
        "\n"
        "`delete(name)` MUST remove the widget recorded under `name`.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "store(name: str) -> None\n"
        "delete(name: str) -> None\n"
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an empty foo store\n"
        "When store is called with name \"a\"\n"
        "Then the widget \"a\" is recorded\n"
        "```\n",
    )
    if cover_second_requirement:
        _write(
            comp / "acceptance" / "AC-FOO-002.md",
            "# AC-FOO-002\n"
            "\n"
            "Covers: R-FOO-002\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given a foo store holding widget \"a\"\n"
            "When delete is called with name \"a\"\n"
            "Then the widget \"a\" is no longer recorded\n"
            "```\n",
        )


def _fail_findings(report):
    out = []
    for f in field(report, "findings"):
        if field(f, "severity") == "fail":
            out.append(
                (
                    field(f, "rule_id"),
                    str(field(f, "file")),
                    str(field(f, "message")),
                )
            )
    return out


def _mentions_uncovered(finding):
    rule_id, file, message = finding
    return "R-FOO-002" in file or "R-FOO-002" in message


def test_uncovered_requirement_fails_lint_and_blocks_before_generation(tmp_path):
    # Control: every requirement covered.
    control_root = tmp_path / "control"
    control_root.mkdir()
    _build_corpus(control_root, cover_second_requirement=True)
    control_report = spec_linter.lint(None, control_root)
    control_fails = _fail_findings(control_report)
    assert not any(_mentions_uncovered(f) for f in control_fails), control_fails

    # Defect: R-FOO-002 in the Behavior section has no covering criterion.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, cover_second_requirement=False)

    report = spec_linter.lint(None, repo_root)
    fails = _fail_findings(report)
    new_fails = [f for f in fails if f not in control_fails]
    assert new_fails, "expected a new fail-severity finding, got: " + repr(fails)
    assert any(_mentions_uncovered(f) for f in new_fails), new_fails
    assert field(report, "hard_failures") >= 1

    # The merge gate: spec-linter's CLI exits 1 on a fail-severity finding.
    exit_code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    assert exit_code == 1

    # Generation never runs: the pipeline stops at the lint failure, so no
    # model call is ever dispatched.
    log_path = tmp_path / "backend_calls.log"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        return {
            "text": "{}",
            "model": model,
            "backend": "fake",
            "model_call_error": None,
        }

    assist_report = spec_completeness_assistant.assist(
        ["R-FOO-002"], repo_root, model="fake-model", llm_backend=backend
    )
    lint_findings = field(assist_report, "lint_findings")
    assert any(field(f, "severity") == "fail" for f in lint_findings), lint_findings
    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == [], "generation/model calls ran despite a lint failure: " + repr(calls)
# hotdocs-criterion: sha256:72f18b70ecaf5786a29b49c9e991944737cbbc8e14185c56734fe64409fb1257
import importlib.util
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


REQ_ID = "R-FOO-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_real_spec_linter():
    gen = next(
        p
        for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    if (base / "spec_linter.py").is_file():
        path = base / "spec_linter.py"
    else:
        path = base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Widget** \u2014 a small unit of work handled by the foo component.\n",
    )
    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "realizes: []\n"
        "uses_var: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `" + REQ_ID + "`: doubling returns twice its input.\n",
    )
    write(
        comp / "requirements" / (REQ_ID + ".md"),
        "# " + REQ_ID + "\n"
        "\n"
        "`double(x)` MUST return twice `x`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "double(x: int) -> int\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: " + REQ_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the number 2\n"
        "When double is called with it\n"
        "Then the result is 4\n"
        "```\n",
    )
    write(repo_root / "legacy" / "foo" / "foo.py", "def double(x):\n    return 2 * x\n")
    return comp


def fail_findings(report):
    return [f for f in field(report, "findings") if field(f, "severity") == "fail"]


def mentions_req(finding):
    text = str(field(finding, "file")) + " " + str(field(finding, "message"))
    return REQ_ID in text or "foo" in str(field(finding, "file"))


def test_uncovered_requirement_fails_lint_and_blocks_before_generation(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp = build_corpus(repo_root)
    linter = load_real_spec_linter()

    # Precondition: the corpus with full coverage is lint-clean.
    baseline = linter.lint(None, repo_root)
    assert field(baseline, "hard_failures") == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in fail_findings(baseline)
    ]

    # The spec change: the requirement loses its only covering criterion.
    (comp / "acceptance" / "AC-FOO-001.md").unlink()

    # Then: spec-linter reports a fail-severity finding.
    report = linter.lint(None, repo_root)
    fails = fail_findings(report)
    assert field(report, "hard_failures") >= 1
    assert fails, "expected a fail-severity finding for the uncovered requirement"
    assert any(mentions_req(f) for f in fails), [
        (field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in fails
    ]

    # The lint gate blocks the merge: exit code 1.
    code = linter.main(["--repo-root=" + str(repo_root), "--format=json"])
    capsys.readouterr()
    assert code == 1

    # Submitted to the pipeline with a model configured: the lint failure
    # stops it before any generation (no model call is ever made).
    log_path = tmp_path / "backend_calls.log"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "text": "{}",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    assist_report = spec_completeness_assistant.assist(
        [REQ_ID], repo_root, model="claude-sonnet-5", llm_backend=backend
    )
    capsys.readouterr()

    lint_findings = field(assist_report, "lint_findings")
    assist_fails = [f for f in lint_findings if field(f, "severity") == "fail"]
    assert assist_fails, "pipeline should surface the fail-severity lint finding"

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == [], "generation/model calls ran despite a blocking lint failure"
    assert not (repo_root / "gen" / "foo").exists()
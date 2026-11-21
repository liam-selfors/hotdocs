# hotdocs-criterion: sha256:0bbe243507f2d9bde5d0cf7d0d83db8a4be0cf211f779192ec1ba145c9fc7db2
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
import spec_reviewer
import test_author
import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def component_md():
    return (
        "---\n"
        + "id: comp-foo\n"
        + "title: Foo\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "sealed: true\n"
        + "source_path: legacy/foo/\n"
        + "depends_on: []\n"
        + "realizes: []\n"
        + "uses_var: []\n"
        + "---\n"
        + "\n"
        + "# Foo\n"
        + "\n"
        + "## Purpose\n"
        + "\n"
        + "Foo returns small fixed numbers.\n"
        + "\n"
        + "## Behavior\n"
        + "\n"
        + "- `R-FOO-001`: `foo()` returns `1`.\n"
        + "- `R-FOO-002`: `bar()` returns `2`.\n"
    )


def requirement_md(req_id, fn, value):
    return (
        "# " + req_id + "\n"
        + "\n"
        + "`" + fn + "()` MUST return `" + value + "`.\n"
    )


def acceptance_md(ac_id, req_id, fn, value):
    return (
        "# " + ac_id + "\n"
        + "\n"
        + "Covers: " + req_id + "\n"
        + "Kind: generated-test\n"
        + "\n"
        + "```gherkin\n"
        + "Given the foo module\n"
        + "When " + fn + " is called\n"
        + "Then it returns " + value + "\n"
        + "```\n"
    )


def library_md():
    return (
        "# Library\n"
        + "\n"
        + "```\n"
        + "foo() -> int\n"
        + "bar() -> int\n"
        + "```\n"
    )


def glossary_md():
    return (
        "# Glossary\n"
        + "\n"
        + "- **Foo** — the fixture component.\n"
    )


def build_corpus(root, cover_second):
    comp = root / "specs" / "components" / "foo"
    write(root / "specs" / "glossary.md", glossary_md())
    write(comp / "component.md", component_md())
    write(comp / "interface" / "library.md", library_md())
    write(comp / "requirements" / "R-FOO-001.md", requirement_md("R-FOO-001", "foo", "1"))
    write(comp / "requirements" / "R-FOO-002.md", requirement_md("R-FOO-002", "bar", "2"))
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance_md("AC-FOO-001", "R-FOO-001", "foo", "1"))
    if cover_second:
        write(comp / "acceptance" / "AC-FOO-002.md", acceptance_md("AC-FOO-002", "R-FOO-002", "bar", "2"))
    else:
        ac2 = comp / "acceptance" / "AC-FOO-002.md"
        if ac2.exists():
            ac2.unlink()


def test_uncovered_requirement_fails_lint_and_blocks_merge(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Baseline: the corpus is otherwise lint-clean, every requirement covered.
    build_corpus(repo_root, cover_second=True)
    baseline = spec_linter.lint(None, repo_root)
    baseline_fails = [
        f for f in field(baseline, "findings") if field(f, "severity") == "fail"
    ]
    assert field(baseline, "hard_failures") == 0, baseline_fails

    # The spec change: R-FOO-002 is left with no covering acceptance criterion.
    build_corpus(repo_root, cover_second=False)
    report = spec_linter.lint(None, repo_root)

    findings = field(report, "findings")
    fails = [f for f in findings if field(f, "severity") == "fail"]
    assert field(report, "hard_failures") >= 1
    assert fails, findings
    assert any(
        "R-FOO-002" in str(field(f, "message")) or "R-FOO-002" in str(field(f, "file"))
        for f in fails
    ), fails

    # The merge gate: the lint CLI exits 1 on a fail-severity finding.
    code = spec_linter.main(["--repo-root=" + str(repo_root), "--format=json"])
    assert code == 1

    # Blocked before generation runs: nothing was generated or verified.
    assert not (repo_root / "gen" / "foo").exists()
    assert not (repo_root / "verification" / "foo").exists()
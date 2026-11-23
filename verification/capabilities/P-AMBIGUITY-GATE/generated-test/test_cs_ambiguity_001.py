# hotdocs-criterion: sha256:dbbe1080141d7e63d0562fa23ac0ef7b0db47383c435b14e3a79b2d1e3fa4209
import json
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
import spec_reviewer
import test_author
import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root, with_criterion):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this fixture corpus.\n",
    )
    comp_dir = specs / "components" / "foo"
    _write(
        comp_dir / "component.md",
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
        "Foo returns its input unchanged.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `R-FOO-001`: `foo(x)` returns `x`.\n",
    )
    _write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "`foo(x)` MUST return `x` unchanged.\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    if with_criterion:
        _write(
            comp_dir / "acceptance" / "AC-FOO-001.md",
            "# AC-FOO-001\n"
            "\n"
            "Covers: R-FOO-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given an integer 3\n"
            "When foo is called with it\n"
            "Then the result is 3\n"
            "```\n",
        )


def _fail_findings(report):
    return [f for f in field(report, "findings") if field(f, "severity") == "fail"]


def _key(f):
    return (field(f, "rule_id"), field(f, "file"), field(f, "message"))


def test_uncovered_requirement_fails_lint_and_blocks_merge_before_generation(tmp_path, capsys):
    clean_root = tmp_path / "clean"
    clean_root.mkdir()
    _build_corpus(clean_root, with_criterion=True)

    # Precondition: the corpus is otherwise lint-clean.
    clean_report = spec_linter.lint(None, clean_root)
    assert field(clean_report, "hard_failures") == 0
    clean_keys = set(_key(f) for f in _fail_findings(clean_report))

    repo_root = tmp_path / "broken"
    repo_root.mkdir()
    _build_corpus(repo_root, with_criterion=False)

    report = spec_linter.lint(None, repo_root)
    fails = _fail_findings(report)
    assert field(report, "hard_failures") >= 1
    assert len(fails) >= 1

    new_fails = [f for f in fails if _key(f) not in clean_keys]
    assert new_fails, "expected a fail-severity finding for the uncovered requirement"
    assert any(
        "R-FOO-001" in str(field(f, "message")) or "R-FOO-001" in str(field(f, "file"))
        for f in new_fails
    ), "a fail finding should name the uncovered requirement R-FOO-001"

    # The merge gate is blocked: the lint CLI exits 1 on a fail finding.
    capsys.readouterr()
    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    assert code == 1
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert any(f["severity"] == "fail" for f in payload["findings"])
    assert payload["summary"]["hard_failures"] >= 1

    # Blocked before generation runs: linting produced no generated or
    # verification artifacts.
    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification").exists()
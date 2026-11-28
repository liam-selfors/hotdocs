# hotdocs-criterion: sha256:a84889a7ac04aff74ec7625a6b836dff4fd2584e77a2a9d811ca59e1f21e6564
import importlib.util
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(p for p in Path(capability_scenario_verifier.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n\nCanonical vocabulary for this fixture corpus.\n",
    )
    comp_dir = specs / "components" / "foo"
    write(
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
        "Foo returns one.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `R-FOO-001` — `foo()` returns 1.\n",
    )
    write(
        comp_dir / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n`foo()` MUST return 1.\n",
    )
    acceptance = comp_dir / "acceptance" / "AC-FOO-001.md"
    write(
        acceptance,
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the foo component\n"
        "When foo() is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    write(repo_root / "legacy" / "foo" / "foo.py", "def foo():\n    return 1\n")
    return acceptance


def test_uncovered_requirement_blocks_merge_before_generation(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    acceptance = build_fixture(repo_root)

    spec_linter = load_spec_linter()

    # Precondition: the corpus is otherwise lint-clean.
    baseline = spec_linter.lint(None, repo_root)
    assert field(baseline, "hard_failures") == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in field(baseline, "findings")
        if field(f, "severity") == "fail"
    ]

    # The spec change: the requirement loses its only covering criterion.
    acceptance.unlink()

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    fails = [f for f in findings if field(f, "severity") == "fail"]

    assert field(report, "hard_failures") >= 1
    assert fails, findings
    assert any(
        str(field(f, "file")).replace("\\", "/").startswith("specs/components/foo/")
        or "R-FOO-001" in str(field(f, "message"))
        for f in fails
    ), [(field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in fails]

    # The merge is blocked: the lint gate exits non-zero on a fail finding.
    exit_code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    assert exit_code == 1

    # Blocked before generation runs: nothing was generated or verified.
    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification").exists()
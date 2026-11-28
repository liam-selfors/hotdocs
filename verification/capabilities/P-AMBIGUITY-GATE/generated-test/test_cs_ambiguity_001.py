# hotdocs-criterion: sha256:66a5c140eecf722d940186b0aa05d9b319ac692dde5285f6b87312bfcab54ec9
"""CS-AMBIGUITY-001: an uncovered requirement is a fail-severity lint finding
that blocks the merge before generation runs (P-AMBIGUITY-GATE)."""

import importlib.util
import sys
from pathlib import Path

import capability_scenario_verifier


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_spec_linter():
    gen = next(
        p
        for p in Path(capability_scenario_verifier.__file__).resolve().parents
        if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    return load_module(path, "spec_linter")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "Canonical vocabulary for this fixture corpus.\n"
        "\n"
        "- **widget** — a thing the foo component counts.\n",
    )
    comp = specs / "components" / "foo"
    _write(
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
        "Counts widgets.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- R-FOO-001: counting widgets.\n"
        "- R-FOO-002: rejecting a negative count.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "`count_widgets(n)` MUST return `n` for a non-negative integer `n`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "`count_widgets(n)` MUST raise `ValueError` for a negative `n`.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "count_widgets(n: int) -> int\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a non-negative integer 3\n"
        "When count_widgets is called with it\n"
        "Then it returns 3\n"
        "```\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a negative integer -1\n"
        "When count_widgets is called with it\n"
        "Then it raises ValueError\n"
        "```\n",
    )
    return comp


def test_uncovered_requirement_fails_lint_and_blocks_merge(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp = _build_corpus(repo_root)

    spec_linter = _load_spec_linter()

    # Precondition: the corpus, with every requirement covered, is lint-clean.
    baseline = spec_linter.lint(None, repo_root)
    assert field(baseline, "hard_failures") == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in field(baseline, "findings")
        if field(f, "severity") == "fail"
    ]

    # The spec change: R-FOO-002 loses its only covering acceptance criterion.
    (comp / "acceptance" / "AC-FOO-002.md").unlink()

    report = spec_linter.lint(None, repo_root)
    fails = [f for f in field(report, "findings") if field(f, "severity") == "fail"]
    assert field(report, "hard_failures") >= 1
    assert fails, "expected a fail-severity finding for the uncovered requirement"
    assert any(
        "R-FOO-002" in str(field(f, "message")) or "R-FOO-002" in str(field(f, "file"))
        for f in fails
    ), [(field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in fails]

    # The gate blocks the merge: the lint CLI exits 1 on a fail finding.
    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    capsys.readouterr()
    assert code == 1

    # Blocked before generation: nothing was generated or verified.
    assert not (repo_root / "gen").exists()
    assert not (repo_root / "verification").exists()
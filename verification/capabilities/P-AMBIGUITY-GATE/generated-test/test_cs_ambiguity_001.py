# hotdocs-criterion: sha256:f5737f8ef956efdbe66ec4713ffff0efa8398388706e1f02dcbfe4be62fec7d3
"""CS-AMBIGUITY-001: a requirement with no covering acceptance criterion is a
structural ambiguity that spec-linter reports as a fail-severity finding,
blocking the merge before any generation runs."""

import importlib.util
import json
import sys
from pathlib import Path

import capability_scenario_verifier


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "- **Widget** — a value `foo` computes.\n",
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
        "Computes a widget.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `R-FOO-001` — `foo(x)` returns `x` doubled.\n"
        "- `R-FOO-002` — `foo(x)` raises `ValueError` for a negative `x`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "`foo(x)` MUST return `x` doubled.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "`foo(x)` MUST raise `ValueError` when `x` is negative.\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
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
        "Given an integer x of 3\n"
        "When foo is called with x\n"
        "Then the result is 6\n"
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
        "Given an integer x of -1\n"
        "When foo is called with x\n"
        "Then a ValueError is raised\n"
        "```\n",
    )
    return comp


def test_uncovered_requirement_is_fail_finding_and_blocks_merge(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp = _build_corpus(repo_root)
    spec_linter = _load_spec_linter()

    # Precondition: the fully covered corpus is lint-clean.
    baseline = spec_linter.lint(None, repo_root)
    assert field(baseline, "hard_failures") == 0, [
        (field(f, "rule_id"), field(f, "file"), field(f, "message"))
        for f in field(baseline, "findings")
    ]

    # The spec change: R-FOO-002 loses its only covering criterion.
    (comp / "acceptance" / "AC-FOO-002.md").unlink()

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    fails = [f for f in findings if field(f, "severity") == "fail"]
    assert field(report, "hard_failures") >= 1
    assert fails, findings

    def mentions_uncovered(f):
        text = str(field(f, "file")) + " " + str(field(f, "message"))
        return "R-FOO-002" in text

    assert any(mentions_uncovered(f) for f in fails), [
        (field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in fails
    ]

    # The merge is blocked: the linter's gate exits non-zero.
    code = spec_linter.main(["--repo-root=" + str(repo_root), "--format=json"])
    assert code == 1

    # Blocked before generation runs: linting produced no generated artifacts.
    assert not (repo_root / "gen" / "foo").exists()
    assert not (repo_root / "verification" / "foo").exists()


def test_json_report_carries_fail_finding(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp = _build_corpus(repo_root)
    spec_linter = _load_spec_linter()
    assert field(spec_linter.lint(None, repo_root), "hard_failures") == 0

    (comp / "acceptance" / "AC-FOO-002.md").unlink()
    capsys.readouterr()
    code = spec_linter.main(["--repo-root=" + str(repo_root), "--format=json"])
    out = capsys.readouterr().out
    assert code == 1
    data = json.loads(out)
    assert data["summary"]["hard_failures"] >= 1
    assert any(f["severity"] == "fail" for f in data["findings"])
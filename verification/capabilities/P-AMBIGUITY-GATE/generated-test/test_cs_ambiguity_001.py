# hotdocs-criterion: sha256:4e3ad4db24ee57344daf21091bb73e63ba42fb699db1f3699bf254b1bd731b3f
"""CS-AMBIGUITY-001: a requirement with no covering acceptance criterion is a
fail-severity spec-linter finding, and the merge is blocked before generation
runs (spec-linter exits 1, writing nothing under gen/ or verification/)."""

import importlib.util
import json
import sys
from pathlib import Path

import capability_scenario_verifier


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
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


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
        "- **Widget** \u2014 a small fixture thing.\n",
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
        "Foo returns numbers for the fixture.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "- `R-FOO-001` \u2014 `foo(x)` returns `x`.\n"
        "- `R-FOO-002` \u2014 `foo(x)` raises `ValueError` for a negative `x`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "`foo(x)` MUST return `x` unchanged for a non-negative `x`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "`foo(x)` MUST raise `ValueError` for a negative `x`.\n",
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
        "Given a non-negative integer x\n"
        "When foo is called with x\n"
        "Then it returns x\n"
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
        "Given a negative integer x\n"
        "When foo is called with x\n"
        "Then it raises ValueError\n"
        "```\n",
    )
    return comp


def test_cs_ambiguity_001_uncovered_requirement_blocks_merge(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    comp = _build_corpus(repo_root)

    spec_linter = _load_spec_linter()

    # Precondition: the corpus, with every requirement covered, is lint-clean.
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # The spec change: R-FOO-002 in the Behavior section loses its only
    # covering acceptance criterion; everything else stays lint-clean.
    (comp / "acceptance" / "AC-FOO-002.md").unlink()

    report = spec_linter.lint(None, repo_root)
    findings = list(field(report, "findings"))
    fails = [f for f in findings if field(f, "severity") == "fail"]

    assert field(report, "hard_failures") >= 1
    assert fails, "expected a fail-severity finding for uncovered R-FOO-002"
    assert any(
        "R-FOO-002" in str(field(f, "message"))
        or str(field(f, "file")).replace("\\", "/").startswith("specs/components/foo/")
        for f in fails
    ), [
        (field(f, "rule_id"), field(f, "file"), field(f, "message")) for f in fails
    ]

    # The pipeline's lint gate blocks the merge: exit code 1.
    capsys.readouterr()
    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out
    assert code == 1

    parsed = json.loads(out)
    assert any(f["severity"] == "fail" for f in parsed["findings"])
    assert parsed["summary"]["hard_failures"] >= 1

    # Blocked before generation: nothing was generated or verified.
    assert not (repo_root / "gen" / "foo").exists()
    assert not (repo_root / "verification").exists()
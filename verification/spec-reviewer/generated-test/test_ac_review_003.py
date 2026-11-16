import importlib.util
import sys
from pathlib import Path

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _load_spec_linter():
    gen = next(
        p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen"
    )
    base = gen / "spec-linter"
    path = (
        base / "spec_linter.py"
        if (base / "spec_linter.py").is_file()
        else base / "spec_linter" / "__init__.py"
    )
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = module
    spec.loader.exec_module(module)
    return module


def _build_corpus(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
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
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `4`, honoring `--opt=`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = `7` and `--slow`\n"
        "When foo(x) is called with `--opt=<v>`\n"
        "Then it returns `4`, and `--fast` and `foo` are honored,\n"
        "  and `--fast` again\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
        "\n"
        "`foo` accepts `--opt=` followed by a value.\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def test_ac_review_003_invisible_reference_from_when_and_then_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    lint_report = spec_linter.lint(None, repo_root)
    hard = (
        lint_report["hard_failures"]
        if isinstance(lint_report, dict)
        else lint_report.hard_failures
    )
    assert hard == 0

    report = spec_reviewer.check(["AC-FOO-001"], repo_root)

    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "criterion_id") == "AC-FOO-001"
    assert field(finding, "kind") == "invisible_reference"
    assert field(finding, "token") == "--fast"
    assert (
        field(finding, "message")
        == "`--fast` appears in AC-FOO-001 but not in what its test author sees"
    )

    assert dict(field(report, "writable")) == {"AC-FOO-001": None}
    assert list(field(report, "gaps")) == []
    assert field(report, "degraded") is True
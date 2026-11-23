# hotdocs-criterion: sha256:2585d1ae85ce41d9d144e2b491f4a3cb783edf8d29ca8fe6092d8d88492aa3b8
import importlib.util
import sys
from pathlib import Path

import spec_reviewer


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


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a test term.\n",
    )
    comp = specs / "components" / "foo"
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
        "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`, so 4 for an x of 2, "
        "and MUST honor `--opt=`.\n",
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
        "```\n",
    )
    _write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def _load_spec_linter():
    gen = next(p for p in Path(spec_reviewer.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    return load_module(path, "spec_linter")


def test_ac_review_003_invisible_reference_only_for_when_then_tokens(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    report = spec_reviewer.check(["AC-FOO-001"], repo_root)

    findings = list(field(report, "findings"))
    assert len(findings) == 1, findings
    finding = findings[0]
    assert field(finding, "criterion_id") == "AC-FOO-001"
    assert field(finding, "kind") == "invisible_reference"
    assert field(finding, "token") == "--fast"
    assert field(finding, "message") == (
        "`--fast` appears in AC-FOO-001 but not in what its test author sees"
    )

    assert dict(field(report, "writable")) == {"AC-FOO-001": None}
    assert list(field(report, "gaps")) == []
    assert field(report, "degraded") is True
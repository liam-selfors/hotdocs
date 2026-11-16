import spec_bundle_assembler

import importlib.util
import sys
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _load_spec_linter():
    gen = next(
        p
        for p in Path(spec_bundle_assembler.__file__).resolve().parents
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


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


VAR_DESCRIPTION_LINE = "Description: the base URL the Foo service is reached at."
VAR_NAME_LINE = "Name: VAR-FOO-URL"
VAR_TYPE_LINE = "Type: url"
VAR_REQUIRED_LINE = "Required: optional"
VAR_SENSITIVITY_LINE = "Sensitivity: public"

VAR_BODY = (
    "# VAR-FOO-URL\n"
    "\n"
    "- " + VAR_NAME_LINE + "\n"
    "- " + VAR_TYPE_LINE + "\n"
    "- " + VAR_REQUIRED_LINE + "\n"
    "- " + VAR_DESCRIPTION_LINE + "\n"
    "- " + VAR_SENSITIVITY_LINE + "\n"
)


def _build_corpus(repo_root: Path) -> None:
    specs = repo_root / "specs"

    _write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
    )

    _write(
        specs / "vars" / "VAR-FOO-URL.md",
        "---\n"
        "id: VAR-FOO-URL\n"
        "title: Foo URL\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n" + VAR_BODY,
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
        "uses_var: [VAR-FOO-URL]\n"
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
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )

    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
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


def test_ac_assemble_003_vars_contains_full_declaration(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard = report["hard_failures"] if isinstance(report, dict) else report.hard_failures
    assert hard == 0, getattr(report, "findings", report)

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    vars_field = field(bundle, "vars")
    assert "VAR-FOO-URL" in vars_field, vars_field
    content = vars_field["VAR-FOO-URL"]
    assert isinstance(content, str)

    # The declaration's full body content is present.
    assert VAR_BODY.strip() in content, content

    # Each declared property is carried through.
    for line in (
        VAR_NAME_LINE,
        VAR_TYPE_LINE,
        VAR_REQUIRED_LINE,
        VAR_DESCRIPTION_LINE,
        VAR_SENSITIVITY_LINE,
    ):
        assert line in content, (line, content)

    # Only the declared var is included.
    assert set(vars_field.keys()) == {"VAR-FOO-URL"}
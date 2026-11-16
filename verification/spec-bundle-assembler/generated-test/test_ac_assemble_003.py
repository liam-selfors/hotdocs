import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    try:
        return value[name]
    except Exception:
        pass
    return getattr(value, name, default)


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


VAR_DESCRIPTION = "The base URL the Foo service is reached at."
VAR_TYPE_LINE = "Type: string (URL)"
VAR_REQUIRED_LINE = "Required: yes"
VAR_SENSITIVITY_LINE = "Sensitivity: public"


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

    _write(
        repo_root / "specs" / "vars" / "VAR-FOO-URL.md",
        "---\n"
        "id: VAR-FOO-URL\n"
        "title: Foo URL\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "type: string\n"
        "required: true\n"
        "sensitivity: public\n"
        "---\n"
        "\n"
        "# VAR-FOO-URL\n"
        "\n"
        + VAR_DESCRIPTION
        + "\n"
        "\n"
        "- " + VAR_TYPE_LINE + "\n"
        "- " + VAR_REQUIRED_LINE + "\n"
        "- " + VAR_SENSITIVITY_LINE + "\n",
    )

    _write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x\n",
    )


def test_ac_assemble_003_bundle_vars_contains_full_declaration(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    sentinel_value = "https://sentinel-value-should-never-appear.invalid/xyz"
    monkeypatch.setenv("VAR_FOO_URL", sentinel_value)

    spec_linter = _load_spec_linter()
    report = spec_linter.lint(None, repo_root)
    hard_failures = _field(report, "hard_failures")
    if hard_failures is None:
        summary = _field(report, "summary", {}) or {}
        hard_failures = _field(summary, "hard_failures", 0)
    assert hard_failures == 0, _field(report, "findings")

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    vars_field = _field(bundle, "vars")
    assert vars_field is not None, "SpecBundle has no vars field"
    keys = list(vars_field.keys()) if hasattr(vars_field, "keys") else []
    assert "VAR-FOO-URL" in keys, f"vars keys were {keys!r}"

    content = vars_field["VAR-FOO-URL"]
    assert isinstance(content, str)
    assert content.strip() != ""

    assert VAR_DESCRIPTION in content
    assert VAR_TYPE_LINE in content
    assert VAR_REQUIRED_LINE in content
    assert VAR_SENSITIVITY_LINE in content
    assert "# VAR-FOO-URL" in content

    assert sentinel_value not in content
    for v in vars_field.values():
        assert sentinel_value not in str(v)
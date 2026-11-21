# hotdocs-criterion: sha256:223622a80c2d581ecdc5afd33db1e6b2b4db32001befd8ad8df97689e68df70d
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
    gen = next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


VAR_BODY_LINES = [
    "# VAR-FOO-URL",
    "Name: VAR-FOO-URL",
    "Type: string (URL)",
    "Required: required",
    "Sensitivity: non-sensitive",
    "Description: The base URL foo calls to fetch its multiplier.",
]


def build_fixture(repo_root):
    specs = repo_root / "specs"

    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a test term.\n",
    )

    write(
        specs / "vars" / "VAR-FOO-URL.md",
        "---\n"
        "id: VAR-FOO-URL\n"
        "title: Foo URL\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        + VAR_BODY_LINES[0] + "\n"
        "\n"
        + VAR_BODY_LINES[1] + "\n"
        "\n"
        + VAR_BODY_LINES[2] + "\n"
        "\n"
        + VAR_BODY_LINES[3] + "\n"
        "\n"
        + VAR_BODY_LINES[4] + "\n"
        "\n"
        + VAR_BODY_LINES[5] + "\n",
    )

    comp = specs / "components" / "foo"
    write(
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
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
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
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


def test_ac_assemble_003_vars_contains_full_declaration(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)

    vars_field = field(bundle, "vars")
    assert "VAR-FOO-URL" in vars_field, vars_field
    content = vars_field["VAR-FOO-URL"]
    assert isinstance(content, str)

    for line in VAR_BODY_LINES:
        assert line in content, (line, content)
import tempfile
from pathlib import Path

import spec_bundle_assembler


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_ac_assemble_003_vars_field_contains_full_var_declaration():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)

        _write(
            repo_root / "specs" / "glossary.md",
            "# Glossary\n"
            "\n"
            "- **Foo** — a test term.\n",
        )

        _write(
            repo_root / "specs" / "vars" / "VAR-FOO-URL.md",
            "---\n"
            "id: VAR-FOO-URL\n"
            "title: Foo URL\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "---\n"
            "\n"
            "# VAR-FOO-URL\n"
            "\n"
            "Type: string\n"
            "Required: yes\n"
            "Description: The URL endpoint for the Foo service.\n"
            "Sensitivity: low\n",
        )

        _write(
            repo_root / "specs" / "components" / "foo" / "component.md",
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
            repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
            "# R-FOO-001\n"
            "\n"
            "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
        )

        _write(
            repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
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
            repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
            "# Library\n"
            "\n"
            "```\n"
            "foo(x: int) -> int\n"
            "```\n",
        )

        _write(
            repo_root / "specs" / "components" / "foo" / "constraints.md",
            "# Constraints\n"
            "\n"
            "None.\n",
        )

        bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

        vars_field = (
            bundle.get("vars")
            if isinstance(bundle, dict)
            else getattr(bundle, "vars", None)
        )

        assert vars_field is not None
        assert "VAR-FOO-URL" in vars_field

        declaration = vars_field["VAR-FOO-URL"]

        # R-ASSEMBLE-003: full declaration content means name, type,
        # required/optional, description and sensitivity must all be present.
        assert "VAR-FOO-URL" in declaration
        assert "Type: string" in declaration
        assert "Required: yes" in declaration
        assert "Description: The URL endpoint for the Foo service." in declaration
        assert "Sensitivity: low" in declaration

        # There is no value to include for a var declaration.
        assert "value" not in declaration.lower()
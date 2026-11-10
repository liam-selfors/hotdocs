import importlib.util
import sys
import tempfile
from pathlib import Path

import spec_bundle_assembler


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n",
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


def _field(value, name):
    return value.get(name) if isinstance(value, dict) else getattr(value, name, None)


def _collect_strings(value, out):
    if isinstance(value, str):
        out.append(value)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_strings(v, out)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            _collect_strings(v, out)


def test_cold_bundle_excludes_acceptance_content():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_fixture(repo_root)

        spec_linter = _load_spec_linter()
        report = spec_linter.lint(None, repo_root)
        hard_failures = _field(report, "hard_failures")
        assert hard_failures == 0

        bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")

        spec_text = _field(bundle, "spec")
        interface_text = _field(bundle, "interface")
        constraints_text = _field(bundle, "constraints")

        assert spec_text is not None
        assert interface_text is not None
        assert constraints_text is not None

        assert "Foo doubles a number." in spec_text
        assert "2 * x" in spec_text
        assert "foo(x: int) -> int" in interface_text
        assert "None." in constraints_text

        forbidden_snippets = [
            "Given x = 2",
            "foo(x) is called",
            "Then it returns 4",
            "AC-FOO-001",
            "gherkin",
            "Kind: generated-test",
        ]

        bundle_field_names = [
            "component_id",
            "spec_bundle_hash",
            "spec",
            "interface",
            "constraints",
            "dependency_interfaces",
            "dependency_context",
            "dependency_usage",
            "vars",
            "glossary",
            "hint_code",
        ]

        all_strings = []
        for field_name in bundle_field_names:
            _collect_strings(_field(bundle, field_name), all_strings)

        for snippet in forbidden_snippets:
            for text in all_strings:
                assert snippet not in text

        assert _field(bundle, "hint_code") is None
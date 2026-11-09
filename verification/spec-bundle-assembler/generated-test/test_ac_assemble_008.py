import tempfile
from pathlib import Path

import spec_bundle_assembler


def _get(bundle, name):
    if isinstance(bundle, dict):
        return bundle.get(name)
    return getattr(bundle, name, None)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _build_corpus(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", (
        "# Glossary\n"
        "\n"
        "- **Foo** — a test term.\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "component.md", (
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
        "Foo doubles a number.\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md", (
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md", (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "interface" / "library.md", (
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n"
    ))
    _write(repo_root / "specs" / "components" / "foo" / "constraints.md", (
        "# Constraints\n"
        "\n"
        "None.\n"
    ))


def test_ac_assemble_008_hint_mode_adds_hint_code_and_changes_hash():
    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _build_corpus(repo_root)

        gen_foo_py_content = "def foo(x):\n    return 2 * x\n"
        _write(repo_root / "gen" / "foo" / "foo.py", gen_foo_py_content)

        cold_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
        hint_bundle = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

        cold_hint_code = _get(cold_bundle, "hint_code")
        assert cold_hint_code is None

        hint_hint_code = _get(hint_bundle, "hint_code")
        assert isinstance(hint_hint_code, dict)
        assert hint_hint_code.get("foo.py") == gen_foo_py_content

        shared_fields = [
            "component_id",
            "spec",
            "interface",
            "constraints",
            "dependency_interfaces",
            "dependency_context",
            "dependency_usage",
            "vars",
            "glossary",
        ]
        for field in shared_fields:
            assert _get(cold_bundle, field) == _get(hint_bundle, field), field

        cold_hash = _get(cold_bundle, "spec_bundle_hash")
        hint_hash = _get(hint_bundle, "spec_bundle_hash")
        assert cold_hash is not None
        assert hint_hash is not None
        assert cold_hash != hint_hash
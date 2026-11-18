# hotdocs-criterion: sha256:c793056106067d4182aadd61c729b97f5319a5c32a303418016f73e9a63ee59d
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_spec_linter():
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a test term.\n",
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
    write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n"
        "    return 2 * x\n",
    )


def test_hint_mode_adds_hint_code_and_changes_only_hash(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)

    # Existing gen/<component>/ content for comp-foo (slug "foo").
    gen_files = {
        "foo.py": "def foo(x):\n    return x + x\n",
        "sub/notes.txt": "hint notes for foo\n",
    }
    for rel, text in gen_files.items():
        write(repo_root / "gen" / "foo" / rel, text)

    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    cold = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    hint = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

    # Cold mode carries no hint code.
    assert field(cold, "hint_code") is None

    # Hint mode: hint_code holds gen/foo/ content keyed by relative path.
    hint_code = field(hint, "hint_code")
    assert hint_code is not None
    normalized = {str(k).replace("\\", "/"): v for k, v in dict(hint_code).items()}
    assert set(normalized.keys()) == set(gen_files.keys())
    for rel, text in gen_files.items():
        value = normalized[rel]
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        assert value == text

    # Every other field except spec_bundle_hash matches cold mode.
    for name in (
        "component_id",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
    ):
        assert field(hint, name) == field(cold, name), name

    # hint_code is kept separate: gen content does not leak into cold fields.
    for name in ("spec", "interface", "constraints", "glossary"):
        assert "hint notes for foo" not in field(hint, name)

    # spec_bundle_hash differs between modes.
    cold_hash = field(cold, "spec_bundle_hash")
    hint_hash = field(hint, "spec_bundle_hash")
    assert cold_hash
    assert hint_hash
    assert cold_hash != hint_hash
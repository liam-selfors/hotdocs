# hotdocs-criterion: sha256:85ccbbde868b6f89630c4ec2455da57e7b78f29fb96e1ab0e9fa415ef2da3356
import importlib.util
import sys
from pathlib import Path

import spec_bundle_assembler


def component_files(slug, depends_on="[]", extra_frontmatter="", purpose="Foo doubles a number."):
    """The files of one fixture component, keyed by path under repo_root."""
    upper = slug.upper()
    base = f"specs/components/{slug}/"
    return {
        base + "component.md": (
            "---\n"
            f"id: comp-{slug}\n"
            f"title: {slug.capitalize()}\n"
            "status: draft\n"
            "owners: [team-a]\n"
            "sealed: true\n"
            f"source_path: legacy/{slug}/\n"
            f"depends_on: {depends_on}\n"
            + extra_frontmatter +
            "---\n"
            "\n"
            f"# {slug.capitalize()}\n"
            "\n"
            "## Purpose\n"
            "\n"
            f"{purpose}\n"
        ),
        base + f"requirements/R-{upper}-001.md": (
            f"# R-{upper}-001\n"
            "\n"
            f"**R-{upper}-001** — `foo(x)` MUST return `2 * x`.\n"
        ),
        base + f"acceptance/AC-{upper}-001.md": (
            f"# AC-{upper}-001\n"
            "\n"
            f"Covers: R-{upper}-001\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
            "```\n"
        ),
        base + "interface/library.md": "# Library\n\n```\nfoo(x: int) -> int\n```\n",
        base + "constraints.md": "# Constraints\n\nNone.\n",
    }


def write_fixture(repo_root, files):
    files = {"specs/glossary.md": "# Glossary\n\n- **Foo** — a test term.\n", **files}
    for rel, text in files.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def _as_text(value):
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return value


def test_ac_assemble_008_hint_mode_adds_hint_code_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fixture(repo_root, component_files("foo"))

    gen_files = {
        "foo.py": "def foo(x):\n    # HINT-MARKER-MAIN-7731\n    return 2 * x\n",
        "sub/notes.txt": "HINT-MARKER-NESTED-4412\n",
    }
    for rel, text in gen_files.items():
        path = repo_root / "gen" / "foo" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    _lint_clean(repo_root)

    cold = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="cold")
    hint = spec_bundle_assembler.assemble("comp-foo", repo_root, mode="hint")

    # Cold mode carries no hint code.
    assert field(cold, "hint_code") is None

    # Hint mode: hint_code holds gen/foo/ content keyed by relative path.
    hint_code = field(hint, "hint_code")
    assert hint_code is not None
    assert isinstance(hint_code, dict)
    for rel, text in gen_files.items():
        assert rel in hint_code, (rel, sorted(hint_code))
        assert _as_text(hint_code[rel]) == text

    # Every other field except the hash fields matches cold mode.
    same_fields = [
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
    for name in same_fields:
        assert field(hint, name) == field(cold, name), name

    # The hint content never leaks into the cold bundle's own fields.
    for name in ("spec", "interface", "constraints", "glossary"):
        value = field(hint, name)
        assert "HINT-MARKER-MAIN-7731" not in value, name
        assert "HINT-MARKER-NESTED-4412" not in value, name

    # spec_bundle_hash and spec_bundle_parts' spec differ from cold mode's.
    cold_hash = field(cold, "spec_bundle_hash")
    hint_hash = field(hint, "spec_bundle_hash")
    assert isinstance(cold_hash, str) and cold_hash.startswith("sha256:")
    assert isinstance(hint_hash, str) and hint_hash.startswith("sha256:")
    assert hint_hash != cold_hash

    cold_parts = field(cold, "spec_bundle_parts")
    hint_parts = field(hint, "spec_bundle_parts")
    assert "spec" in cold_parts and "spec" in hint_parts
    assert hint_parts["spec"] != cold_parts["spec"]
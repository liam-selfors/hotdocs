# hotdocs-criterion: sha256:cb018862a959c680dd14f85c55c275a9cc6523e2b21da5f751ce8545f7451c7f
import importlib.util
import sys
from pathlib import Path

import pytest

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


def assert_lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


BAZ_MD = "specs/components/baz/component.md"
FOO_MD = "specs/components/foo/component.md"


def append_section(rel, section):
    def edit(repo_root):
        path = repo_root / rel
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        path.write_text(text + section, encoding="utf-8")
    return edit


def replace_foo_purpose(repo_root):
    path = repo_root / FOO_MD
    text = path.read_text(encoding="utf-8")
    assert "Foo doubles a number." in text
    path.write_text(text.replace("Foo doubles a number.", "Foo triples a number."), encoding="utf-8")


def build(repo_root):
    files = {}
    files.update(component_files("foo"))
    files.update(component_files("baz", depends_on="[comp-foo]"))
    write_fixture(repo_root, files)


def hash_before_after(repo_root, edit):
    build(repo_root)
    assert_lint_clean(repo_root)
    before = field(spec_bundle_assembler.assemble("comp-baz", repo_root), "spec_bundle_hash")
    edit(repo_root)
    assert_lint_clean(repo_root)
    after = field(spec_bundle_assembler.assemble("comp-baz", repo_root), "spec_bundle_hash")
    assert isinstance(before, str) and before.startswith("sha256:")
    assert isinstance(after, str) and after.startswith("sha256:")
    return before, after


@pytest.mark.parametrize(
    "edit",
    [
        append_section(BAZ_MD, "## Change log\n\n- D1.\n"),
        append_section(FOO_MD, "## Scope\n\nAll of it.\n"),
    ],
    ids=["baz-change-log", "foo-scope"],
)
def test_edit_leaves_spec_bundle_hash_unchanged(tmp_path, edit):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    before, after = hash_before_after(repo_root, edit)
    assert after == before


@pytest.mark.parametrize(
    "edit",
    [
        append_section(BAZ_MD, "## Scope\n\nAll of it.\n"),
        replace_foo_purpose,
    ],
    ids=["baz-scope", "foo-purpose"],
)
def test_edit_changes_spec_bundle_hash(tmp_path, edit):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    before, after = hash_before_after(repo_root, edit)
    assert after != before
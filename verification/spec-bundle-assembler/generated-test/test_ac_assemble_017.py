# hotdocs-criterion: sha256:6d2475b24dfe7e865f84cfb61fadeb2d7295c5e65c30a078a5c078599389739d
"""AC-ASSEMBLE-017: with no gen/ under repo_root, assemble and
assemble_criterion fall back to the tool root's spec-linter and
graph-query-engine, succeed, and never create repo_root/gen."""

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


def tool_gen():
    return next(
        p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen"
    )


def load_tool_spec_linter():
    base = tool_gen() / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def test_assemble_without_gen_uses_tool_root_and_creates_no_gen(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    write_fixture(repo_root, component_files("foo"))
    assert not (repo_root / "gen").exists()

    # The dependencies the fallback must find exist under the tool root.
    gen = tool_gen()
    assert (gen / "spec-linter").is_dir()
    assert (gen / "graph-query-engine").is_dir()

    spec_linter = load_tool_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0
    assert not (repo_root / "gen").exists()

    bundle = spec_bundle_assembler.assemble("comp-foo", repo_root)
    assert field(bundle, "component_id") == "comp-foo"
    assert "MUST return `2 * x`" in field(bundle, "spec")
    assert "foo(x: int) -> int" in field(bundle, "interface")
    assert "None." in field(bundle, "constraints")
    assert "a test term" in field(bundle, "glossary")
    assert str(field(bundle, "spec_bundle_hash")).startswith("sha256:")
    assert field(bundle, "hint_code") is None

    crit = spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)
    assert field(crit, "component_id") == "comp-foo"
    assert field(crit, "criterion_id") == "AC-FOO-001"
    assert field(crit, "covers") == "R-FOO-001"
    assert "Given x = 2" in field(crit, "criterion_text")
    assert "MUST return `2 * x`" in field(crit, "requirement_text")
    assert "foo(x: int) -> int" in field(crit, "interface")

    assert not (repo_root / "gen").exists()


def test_tool_root_linter_still_gates_without_gen(tmp_path):
    """The fallback linter really runs: a non-lint-clean corpus is refused,
    and still no gen/ appears under repo_root."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    files = component_files("foo")
    ac = "specs/components/foo/acceptance/AC-FOO-001.md"
    files[ac] = files[ac].replace("Kind: generated-test\n", "")
    write_fixture(repo_root, files)
    assert not (repo_root / "gen").exists()

    with pytest.raises(Exception):
        spec_bundle_assembler.assemble("comp-foo", repo_root)
    with pytest.raises(Exception):
        spec_bundle_assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    assert not (repo_root / "gen").exists()
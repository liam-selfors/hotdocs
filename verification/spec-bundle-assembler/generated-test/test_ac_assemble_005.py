# hotdocs-criterion: sha256:e7b4492157e2024ccdef8b5ef53f86c1089c362b032e9581b8004c8bd12526b9
import importlib.util
import json
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


def load_spec_linter():
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    return spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def build_clean(repo_root):
    files = {}
    files.update(component_files("foo"))
    files.update(component_files("baz", depends_on="[comp-foo]"))
    write_fixture(repo_root, files)


def break_baz(repo_root):
    """Delete the Kind: line from baz's acceptance file: a hard lint failure."""
    path = repo_root / "specs/components/baz/acceptance/AC-BAZ-001.md"
    text = path.read_text(encoding="utf-8")
    new = "".join(
        line for line in text.splitlines(keepends=True)
        if not line.startswith("Kind:")
    )
    assert new != text
    path.write_text(new, encoding="utf-8")


def looks_like_bundle(stdout):
    stdout = stdout.strip()
    if not stdout:
        return False
    try:
        doc = json.loads(stdout)
    except ValueError:
        return False
    return isinstance(doc, dict) and ("spec" in doc or "spec_bundle_hash" in doc)


@pytest.mark.parametrize("component_id", ["comp-foo", "comp-baz"])
def test_cli_refuses_with_precondition_failure_when_corpus_not_lint_clean(tmp_path, capsys, component_id):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_clean(repo_root)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # Control: the clean corpus assembles.
    capsys.readouterr()
    rc_clean = spec_bundle_assembler.main(
        [component_id, "--repo-root=" + str(repo_root), "--format=json"]
    )
    clean_out = capsys.readouterr().out
    assert rc_clean == 0
    assert looks_like_bundle(clean_out)

    # Introduce a hard-fail finding in baz (somewhere in the corpus).
    break_baz(repo_root)
    assert spec_linter.lint(None, repo_root).hard_failures > 0

    rc = spec_bundle_assembler.main(
        [component_id, "--repo-root=" + str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert rc == 1
    assert not looks_like_bundle(out)


@pytest.mark.parametrize("component_id", ["comp-foo", "comp-baz"])
def test_library_refuses_to_produce_bundle_when_corpus_not_lint_clean(tmp_path, component_id):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_clean(repo_root)
    spec_linter = load_spec_linter()
    assert spec_linter.lint(None, repo_root).hard_failures == 0

    # Control: the clean corpus yields a bundle.
    clean = spec_bundle_assembler.assemble(component_id, repo_root)
    assert field(clean, "component_id") == component_id
    assert field(clean, "spec")

    break_baz(repo_root)
    assert spec_linter.lint(None, repo_root).hard_failures > 0

    try:
        result = spec_bundle_assembler.assemble(component_id, repo_root)
    except Exception:
        return  # precondition failure raised: no bundle produced
    # If a result is returned instead, it must not be a (partial) bundle.
    is_bundle = isinstance(result, spec_bundle_assembler.SpecBundle) if hasattr(
        spec_bundle_assembler, "SpecBundle") else False
    assert not is_bundle
    spec_text = None
    try:
        spec_text = field(result, "spec")
    except (KeyError, AttributeError, TypeError):
        spec_text = None
    assert not spec_text
# hotdocs-criterion: sha256:0a64e6891043139eb47855456807017b61eda01dc7fa27f17b2ca839cda24ae6
import importlib.util
import json
import sys
from pathlib import Path

import spec_bundle_assembler


FIELDS = [
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
    "spec_bundle_parts",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def snapshot_corpus(repo_root):
    return {
        str(p.relative_to(repo_root)): p.read_bytes()
        for p in sorted(repo_root.rglob("*"))
        if p.is_file()
    }


def bundle_bytes(bundle):
    data = {name: field(bundle, name) for name in FIELDS}
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def test_assemble_twice_on_unchanged_corpus_is_byte_identical(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    files = {}
    files.update(component_files("foo"))
    files.update(component_files("baz", depends_on="[comp-foo]", purpose="Baz uses foo."))
    write_fixture(repo_root, files)
    lint_clean(repo_root)

    before = snapshot_corpus(repo_root)

    for component_id in ("comp-foo", "comp-baz"):
        first = spec_bundle_assembler.assemble(component_id, repo_root)
        second = spec_bundle_assembler.assemble(component_id, repo_root)

        assert field(first, "component_id") == component_id
        first_bytes = bundle_bytes(first)
        second_bytes = bundle_bytes(second)
        assert first_bytes == second_bytes
        assert field(first, "spec_bundle_hash") == field(second, "spec_bundle_hash")
        for name in FIELDS:
            assert field(first, name) == field(second, name), name

    # The corpus really was unchanged between and after the runs.
    assert snapshot_corpus(repo_root) == before
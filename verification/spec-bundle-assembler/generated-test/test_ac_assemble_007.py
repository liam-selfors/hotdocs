# hotdocs-criterion: sha256:96e68dffef6cba449504b402e039937661b73a21e21f814b2e1e58bfb11d6777
import hashlib
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


def lint_clean(repo_root):
    gen = next(p for p in Path(spec_bundle_assembler.__file__).resolve().parents if p.name == "gen")
    base = gen / "spec-linter"
    path = base / "spec_linter.py" if (base / "spec_linter.py").is_file() else base / "spec_linter" / "__init__.py"
    spec = importlib.util.spec_from_file_location("spec_linter", path)
    spec_linter = importlib.util.module_from_spec(spec)
    sys.modules["spec_linter"] = spec_linter
    spec.loader.exec_module(spec_linter)
    assert spec_linter.lint(None, repo_root).hard_failures == 0


def build_fixture(repo_root):
    files = {}
    files.update(component_files("foo"))
    files.update(component_files("bar", depends_on="[comp-foo]"))
    write_fixture(repo_root, files)
    code = repo_root / "legacy" / "foo" / "foo.py"
    code.parent.mkdir(parents=True, exist_ok=True)
    code.write_text("def foo(x): return 2 * x\n", encoding="utf-8")


def expected_hash(repo_root):
    # Every path the comp-bar cold bundle reads in this fixture. No section
    # of either component.md is cut: bar's has no Rationale / Open questions /
    # Change log, and foo's has only Purpose. No Implements, assets, types or
    # vars are present.
    paths = [
        "specs/components/bar/component.md",
        "specs/components/bar/constraints.md",
        "specs/components/bar/requirements/R-BAR-001.md",
        "specs/components/bar/interface/library.md",
        "specs/components/foo/component.md",
        "specs/components/foo/interface/library.md",
        "legacy/foo/foo.py",
        "specs/glossary.md",
    ]
    stream = b"cold" + b"\0"
    for rel in sorted(set(paths)):
        stream += rel.encode("utf-8") + b"\0"
        stream += (repo_root / rel).read_bytes() + b"\0"
    return "sha256:" + hashlib.sha256(stream).hexdigest()


def test_ac_assemble_007_spec_bundle_hash(tmp_path):
    repo_root = tmp_path
    build_fixture(repo_root)
    lint_clean(repo_root)

    # Scenario 1: the hash equals the stream the test builds itself.
    bundle = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    first = field(bundle, "spec_bundle_hash")
    assert first == expected_hash(repo_root)

    # Scenario 2: a manifest in the code directory changes no hash.
    (repo_root / "legacy" / "foo" / ".provenance.json").write_text(
        '{"anything": "at all"}\n', encoding="utf-8"
    )
    bundle2 = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    assert field(bundle2, "spec_bundle_hash") == first

    # Scenario 3: a change to the dependency's code changes the hash.
    code = repo_root / "legacy" / "foo" / "foo.py"
    code.write_text(code.read_text(encoding="utf-8") + "# an extra line\n", encoding="utf-8")
    bundle3 = spec_bundle_assembler.assemble("comp-bar", repo_root, mode="cold")
    assert field(bundle3, "spec_bundle_hash") != first